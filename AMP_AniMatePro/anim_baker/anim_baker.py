# channels_bake()
# bpy.ops.anim.channels_bake(range=(0, 0), step=1, remove_outside_range=False, interpolation_type='BEZIER', bake_modifiers=True)
# Create keyframes following the current shape of F-Curves of selected channels
# bpy.ops.anim.channels_bake

# store a list of frames where there are keys across all channels to bake as they are being baked
# 1 bake channels on all channels

import bpy
import numpy as np
from .. import utils


class AMP_OT_AnimBaker(bpy.types.Operator):
    bl_idname = "anim.amp_anim_baker"
    bl_label = "Anim Baker"
    bl_description = "Create keyframes following the current shape of F-Curves of selected channels"
    bl_options = {"REGISTER", "UNDO"}

    range_options: bpy.props.EnumProperty(
        name="Scope",
        description="Bake channels based on the selected scope",
        items=[
            ("SCENE", "Scene range", "Bake the scene range", "SCENE_DATA", 0),
            ("PREVIEW", "Preview range", "Bake the preview range", "PREVIEW_RANGE", 1),
            ("SELECTED", "Selected range", "Bake the selected keyframes range", "ACTION_TWEAK", 2),
            ("RANGE", "Custom range", "Bake the custom range", "CON_ACTION", 3),
        ],
        default="SCENE",
    )

    bake_type: bpy.props.EnumProperty(
        name="Bake Type",
        description="Bake channels based on the selected type",
        items=[
            (
                "SMART",
                "Smart",
                """Preserve the shape of the curve and keep the keyframes per FCurve
This method requires the NLA tracks to be either in Replace or Combine to evaluate properly
if using source interpolation and handles""",
                "SYSTEM",
                0,
            ),
            ("STEP", "Step", "Create keyframes at regular intervals", "NEXT_KEYFRAME", 1),
        ],
        default="SMART",
    )

    range: bpy.props.IntVectorProperty(
        name="Range",
        description="Range of frames to bake",
        size=2,
        default=(0, 0),
    )

    step: bpy.props.IntProperty(name="Step", default=1, description="Step to use when baking")

    interpolation_type: bpy.props.EnumProperty(
        name="Interpolation Type",
        description="Interpolation type to use when baking",
        items=[
            ("BEZIER", "Bezier", "Bezier interpolation", "IPO_BEZIER", 0),
            ("LINEAR", "Linear", "Linear interpolation", "IPO_LINEAR", 1),
            ("CONSTANT", "Constant", "Constant interpolation", "IPO_CONSTANT", 2),
            ("SOURCE", "Preserve", "Preserve FCurve shapes", "LOOP_BACK", 3),
        ],
        default="SOURCE",
    )

    handles: bpy.props.EnumProperty(
        name="Handles",
        description="Handles to use when baking",
        items=[
            ("FREE", "Free", "Free handles", "HANDLE_FREE", 0),
            ("ALIGNED", "Aligned", "Aligned handles", "HANDLE_ALIGNED", 1),
            ("VECTOR", "Vector", "Vector handles", "HANDLE_VECTOR", 2),
            ("AUTO", "Auto", "Auto handles", "HANDLE_AUTO", 3),
            ("AUTO_CLAMPED", "Auto Clamped", "Auto clamped handles", "HANDLE_AUTOCLAMPED", 4),
            ("SOURCE", "Preserve", "Preserve FCurve shapes", "LOOP_BACK", 5),
        ],
        default="SOURCE",
    )

    only_selected_bones: bpy.props.BoolProperty(
        name="Only Selected Bones", default=True, description="Only bake selected bones"
    )

    visual_keying: bpy.props.BoolProperty(
        name="Visual Keying", default=False, description="Insert keyframes for visual evaluation"
    )

    clear_constraints: bpy.props.BoolProperty(
        name="Clear Constraints", default=False, description="Clear constraints after baking"
    )

    mute_constraints: bpy.props.BoolProperty(
        name="Mute Keyed Constraints", default=False, description="Mute constraints after baking"
    )

    key_muted_constraints: bpy.props.BoolProperty(
        name="Key Muted Constraints",
        default=False,
        description="Key muted constraints at the start of the action after baking",
    )

    clear_parents: bpy.props.BoolProperty(name="Clear Parents", default=False, description="Clear parents after baking")

    overwrite_current_action: bpy.props.BoolProperty(
        name="Overwrite Current Action",
        default=False,
        description="Overwrite the current action with the baked information",
    )

    clear_nla_tracks: bpy.props.BoolProperty(
        name="Clear NLA Tracks", default=False, description="Clear all animations and tracks from the NLA after baking"
    )

    clean_curves: bpy.props.BoolProperty(name="Clean Curves", default=False, description="Clean curves after baking")

    bake_data: bpy.props.EnumProperty(
        name="Bake Data",
        description="Bake data based on the selected type",
        items=[
            ("POSE", "Pose", "Bake the pose data", "POSE_DATA", 0),
            ("OBJECT", "Object", "Bake the object data", "OBJECT_DATA", 1),
        ],
        default="POSE",
    )

    channels_location: bpy.props.BoolProperty(name="Location", default=True, description="Bake location channels")

    channels_rotation: bpy.props.BoolProperty(name="Rotation", default=True, description="Bake rotation channels")

    channels_scale: bpy.props.BoolProperty(name="Scale", default=True, description="Bake scale channels")

    channels_bbone: bpy.props.BoolProperty(name="B-Bone", default=True, description="Bake B-Bone channels")

    channels_props: bpy.props.BoolProperty(name="Props", default=True, description="Bake props channels")

    original_data = {}
    original_fcurves = []

    frame_range = []
    baked_fcurves = []

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def execute(self, context):
        ob = context.active_object
        if ob.animation_data is None or ob.animation_data.action is None or ob.animation_data.nla_tracks is None:
            self.report({"WARNING"}, "No animation data found")
            return {"CANCELLED"}

        self.frame_range = utils.curve.determine_frame_range(self, context)
        self.original_data = {}

        self.original_fcurves = self.all_fcurves_for_current_bake(context)

        # store all the information
        if self.bake_type == "SMART":
            self.original_data = self.store_original_data(self.original_fcurves)
            print(self.original_data)

        # Using Blender's NLA bake operator
        self.bake_action(context, self.frame_range)

        # Post-bake cleanup for SMART bake type
        if self.bake_type == "SMART":
            self.baked_fcurves = self.all_fcurves_for_current_bake(context)
            self.smart_keyframe_cleanup(context, self.original_data, self.baked_fcurves)
            self.restore_original_data(self.baked_fcurves, self.original_data)

        if self.mute_constraints:
            self.mute_relevant_constraints(context, ob, self.original_fcurves, self.frame_range)

        self.set_main_action(ob)

        if self.clear_nla_tracks:
            self.clear_nla(ob)

        return {"FINISHED"}

    def bake_action(self, context, frame_range):
        channel_args = self.get_channel_args()

        bpy.ops.nla.bake(
            frame_start=frame_range[0],
            frame_end=frame_range[1],
            step=1 if self.bake_type != "STEP" else self.step,
            only_selected=self.only_selected_bones,
            visual_keying=self.visual_keying,
            clear_constraints=self.clear_constraints,
            clear_parents=self.clear_parents,
            use_current_action=self.overwrite_current_action,
            clean_curves=self.clean_curves,
            bake_types={self.bake_data},
            channel_types=set(channel_args),
        )

    def get_channel_args(self):
        channel_args = []
        if self.channels_location:
            channel_args.append("LOCATION")
        if self.channels_rotation:
            channel_args.append("ROTATION")
        if self.channels_scale:
            channel_args.append("SCALE")
        if self.channels_bbone:
            channel_args.append("BBONE")
        if self.channels_props:
            channel_args.append("PROPS")
        return channel_args

    def all_fcurves_for_current_bake(self, context):
        fcurves = []

        # Get the active object
        obj = context.active_object
        if obj is None:
            return fcurves

        # Check if the active object has an action
        if obj.animation_data and obj.animation_data.action:
            for fcurve in utils.curve.all_fcurves(obj.animation_data.action):
                fcurves.append(fcurve)

        # Check for NLA tracks
        if obj.animation_data and obj.animation_data.nla_tracks:
            for track in obj.animation_data.nla_tracks:
                # Include only non-muted and visible (not hidden) tracks that are active
                if not track.mute:
                    for strip in track.strips:
                        if strip.action:
                            for fcurve in strip.action.fcurves:
                                fcurves.append(fcurve)

        return fcurves

    def smart_keyframe_cleanup(self, context, original_data, baked_fcurves):
        if not isinstance(original_data, dict):
            raise ValueError("Expected original_data to be a dictionary")

        stored_keys = set(original_data.keys())

        for fcurve in baked_fcurves:
            key = (fcurve.data_path, fcurve.array_index)
            if key in original_data:
                original_frames = set(original_data[key].keys())
                baked_frames = {int(kp.co.x) for kp in fcurve.keyframe_points}
                frames_to_remove = baked_frames - original_frames

                for frame in frames_to_remove:
                    for kp in list(fcurve.keyframe_points):
                        if int(kp.co.x) == frame:
                            fcurve.keyframe_points.remove(kp)
                fcurve.update()
            else:
                print(f"No original data found for fcurve key: {key}")

    def store_original_data(self, fcurves):
        data = {}
        for fcurve in fcurves:
            key = (fcurve.data_path, fcurve.array_index)
            frame_data = {}
            for kp in fcurve.keyframe_points:
                frame_data[int(kp.co.x)] = {
                    "val": kp.co.y,  # value
                    "int": kp.interpolation,  # interpolation
                    "hl_t": kp.handle_left_type,  # handle_left_type
                    "hr_t": kp.handle_right_type,  # handle_right_type
                    "hl": kp.handle_left.to_tuple(),  # handle_left
                    "hr": kp.handle_right.to_tuple(),  # handle_right
                }
            data[key] = frame_data
        return data

    def restore_original_data(self, baked_fcurves, original_data):
        for fcurve in baked_fcurves:
            key = (fcurve.data_path, fcurve.array_index)
            if key in original_data:
                for kp in fcurve.keyframe_points:
                    frame = int(kp.co.x)
                    if frame in original_data[key]:
                        original_kp_data = original_data[key][frame]
                        # Restore value
                        kp.co.y = original_kp_data["val"]

                        # Conditionally restore or apply new interpolation and handles
                        kp.interpolation = (
                            original_kp_data["int"] if self.interpolation_type == "SOURCE" else self.interpolation_type
                        )
                        kp.handle_left_type = original_kp_data["hl_t"] if self.handles == "SOURCE" else self.handles
                        kp.handle_right_type = original_kp_data["hr_t"] if self.handles == "SOURCE" else self.handles

                        # if self.handles == "SOURCE":
                        #     kp.handle_left.x, kp.handle_left.y = original_kp_data["hl"]
                        #     kp.handle_right.x, kp.handle_right.y = original_kp_data["hr"]

            else:
                print(f"No original data found for fcurve {key}")

            # Update the curve to apply changes
            fcurve.update()

    def mute_relevant_constraints(self, context, ob, original_fcurves, frame_range):

        # # Ensure the object is active and its data is updated
        # bpy.context.view_layer.objects.active = ob
        # ob.select_set(True)
        # bpy.context.view_layer.update()

        def is_property_animated(prop_name, data_path):
            return any(fc for fc in original_fcurves if fc.data_path == f"{data_path}.{prop_name}")

        for pb in ob.pose.bones:
            for constraint in pb.constraints:
                constraint_data_path = f'pose.bones["{pb.name}"].constraints["{constraint.name}"]'
                if any(
                    is_property_animated(prop.identifier, constraint_data_path)
                    for prop in constraint.bl_rna.properties
                    if prop.is_animatable and not prop.is_readonly
                ):
                    for prop in constraint.bl_rna.properties:
                        if prop.is_animatable and not prop.is_readonly:
                            ob.keyframe_delete(f"{constraint_data_path}.{prop.identifier}")

                    constraint.enabled = False
                    # Manually update dependency graph
                    bpy.context.evaluated_depsgraph_get().update()
                    if self.key_muted_constraints:
                        # Insert keyframe
                        ob.keyframe_insert(
                            data_path=f"{constraint_data_path}.enabled", frame=frame_range[0], group=constraint.name
                        )

        for constraint in ob.constraints:
            constraint_data_path = f'constraints["{constraint.name}"]'
            if any(
                is_property_animated(prop.identifier, constraint_data_path)
                for prop in constraint.bl_rna.properties
                if prop.is_animatable and not prop.is_readonly
            ):
                for prop in constraint.bl_rna.properties:
                    if prop.is_animatable and not prop.is_readonly:
                        ob.keyframe_delete(f"{constraint_data_path}.{prop.identifier}")
                constraint.enabled = False
                bpy.context.evaluated_depsgraph_get().update()
                if self.key_muted_constraints:
                    ob.keyframe_insert(
                        data_path=f"{constraint_data_path}.enabled", frame=self.range[0], group=constraint.name
                    )
                    print(f"Disabled and keyed object-level constraint {constraint.name}")

    def set_main_action(self, obj):
        """Set the main action properties for the active object's current action."""
        if obj.animation_data and obj.animation_data.action:
            # Set action extrapolation
            obj.animation_data.action_extrapolation = "HOLD"

            # Set action blend type
            obj.animation_data.action_blend_type = "REPLACE"

            # Set action influence
            obj.animation_data.action_influence = 1.0
        else:
            print("No action found for the active object.")

    def clear_nla(self, obj):
        """Remove all NLA tracks from the specified object, leaving only the active action."""
        if obj.animation_data:
            # Clear all NLA tracks using a loop
            tracks = obj.animation_data.nla_tracks
            for track in tracks:
                tracks.remove(track)
        else:
            print("No animation data found on the object.")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        layout.use_property_split = True
        layout.use_property_decorate = False

        container_action = layout.box()
        container_action.prop(self, "bake_type")
        row = container_action.row(align=True)
        row.active = self.bake_type == "STEP"
        row.prop(self, "step", text="Step")
        container_action.prop(self, "only_selected_bones")
        container_action.prop(self, "overwrite_current_action")
        container_action.prop(self, "clear_nla_tracks")
        container_action.prop(self, "visual_keying")

        # container_range = layout.box()
        # container_range.prop(self, "range_options")
        # row = container_range.row(align=True)
        # row.active = self.range_options == "RANGE"
        # row.prop(self, "range")

        container_curves = layout.box()
        container_curves.prop(self, "interpolation_type")
        row = container_curves.row(align=True)
        row.active = True if self.interpolation_type == "BEZIER" else False
        row.prop(self, "handles")
        container_curves.prop(self, "clean_curves")

        container_relations = layout.box()
        container_relations.prop(self, "clear_parents")
        container_relations.prop(self, "clear_constraints")
        container_relations.prop(self, "mute_constraints")
        row = container_relations.row(align=True)
        row.active = self.mute_constraints
        row.prop(self, "key_muted_constraints")

        container_data = layout.box()
        container_data.prop(self, "bake_data", expand=True)

        container_data.separator()

        col = container_data.column(align=True)
        col.prop(self, "channels_location", toggle=True)
        col.prop(self, "channels_rotation", toggle=True)
        col.prop(self, "channels_scale", toggle=True)
        col.prop(self, "channels_bbone", toggle=True)
        col.prop(self, "channels_props", toggle=True)


def AnimBakerButton(layout, context, text="", icon_value=None):
    # utils.customIcons.get_icon_id("AMP_anim_baker")
    layout.operator("anim.amp_anim_baker", text=text, icon_value=icon_value)


classes = (AMP_OT_AnimBaker,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
