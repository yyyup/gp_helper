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
            ("SOURCE", "Source", "Source interpolation", "LOOP_BACK", 0),
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
            ("SOURCE", "Source", "Source handles", "LOOP_BACK", 5),
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
    blended_fcurves = []

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def execute(self, context):
        ob = context.active_object
        if ob.animation_data is None or ob.animation_data.action is None or ob.animation_data.nla_tracks is None:
            self.report({"WARNING"}, "No animation data found")
            return {"CANCELLED"}

        blend_operations = self.get_nla_track_data(ob)

        self.frame_range = utils.curve.determine_frame_range(self, context)
        self.original_data = {}
        self.blended_fcurves = {}

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
            self.blended_fcurves = self.blend_fcurve_keyframes(self.baked_fcurves, self.frame_range, blend_operations)
            print(self.blended_fcurves)
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
        fcurves_dict = {}
        obj = context.active_object
        if obj and obj.animation_data:
            if obj.animation_data.action:
                for fcurve in utils.curve.all_fcurves(obj.animation_data.action):
                    key = (fcurve.data_path, fcurve.array_index)
                    fcurves_dict[key] = fcurve

            if obj.animation_data.nla_tracks:
                for track in obj.animation_data.nla_tracks:
                    if not track.mute:
                        for strip in track.strips:
                            if strip.action:
                                for fcurve in strip.action.fcurves:
                                    key = (fcurve.data_path, fcurve.array_index)
                                    fcurves_dict[key] = fcurve
        return fcurves_dict

    def smart_keyframe_cleanup(self, context, original_data, baked_fcurves):
        for fcurve in baked_fcurves:
            key = (fcurve.data_path, fcurve.array_index)
            if key in original_data:
                original_array = original_data[key]
                original_frames = set(original_array["frame"])  # Extracting frame numbers directly

                baked_frames = set(int(kp.co.x) for kp in fcurve.keyframe_points)
                frames_to_remove = baked_frames - original_frames

                for frame in frames_to_remove:
                    for kp in list(fcurve.keyframe_points):
                        if int(kp.co.x) == frame:
                            fcurve.keyframe_points.remove(kp)
                fcurve.update()
            else:
                print(f"No original data found for fcurve key: {key}")

    def store_original_data(self, fcurves_dict):
        data = {}
        for key, fcurve in fcurves_dict.items():
            frame_data = [
                (
                    int(kp.co.x),
                    kp.co.y,
                    kp.interpolation,
                    kp.handle_left_type,
                    kp.handle_right_type,
                    kp.handle_left.x,
                    kp.handle_left.y,
                    kp.handle_right.x,
                    kp.handle_right.y,
                )
                for kp in fcurve.keyframe_points
            ]

            dtype = [
                ("frame", int),
                ("val", float),
                ("int", "U10"),
                ("hl_t", "U15"),
                ("hr_t", "U15"),
                ("hl_x", float),
                ("hl_y", float),
                ("hr_x", float),
                ("hr_y", float),
            ]
            data[key] = np.array(frame_data, dtype=dtype)

        return data

    def restore_original_data(self, baked_fcurves, original_data):
        for fcurve in baked_fcurves:
            key = (fcurve.data_path, fcurve.array_index)
            if key in original_data:
                original_array = original_data[key]

                # Loop over keyframe points and restore data
                for kp in fcurve.keyframe_points:
                    frame = int(kp.co.x)
                    idx = np.where(original_array["frame"] == frame)[0]
                    if idx.size > 0:
                        original_kp_data = original_array[idx[0]]

                        kp.co.y = original_kp_data["val"]
                        kp.interpolation = (
                            original_kp_data["int"] if self.interpolation_type == "SOURCE" else self.interpolation_type
                        )
                        kp.handle_left_type = original_kp_data["hl_t"] if self.handles == "SOURCE" else self.handles
                        kp.handle_right_type = original_kp_data["hr_t"] if self.handles == "SOURCE" else self.handles

                        # Optionally restore handles if SOURCE is selected
                        if self.handles == "SOURCE":
                            kp.handle_left.x, kp.handle_left.y = original_kp_data["hl_x"], original_kp_data["hl_y"]
                            kp.handle_right.x, kp.handle_right.y = original_kp_data["hr_x"], original_kp_data["hr_y"]
            else:
                print(f"No original data found for fcurve {key}")

            # Update the curve to apply changes
            fcurve.update()

    def mute_relevant_constraints(self, context, ob, original_fcurves, frame_range):

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

    def blend_fcurve_keyframes(self, fcurves_data, frame_range, blend_operations):
        result_data = {}
        for key, fcurve in fcurves_data.items():
            frames_data = {frame: [] for frame in range(frame_range[0], frame_range[1] + 1)}

            for kp in fcurve.keyframe_points:
                frame = int(kp.co.x)
                if frame_range[0] <= frame <= frame_range[1]:
                    # Ensure a default order if the key is not found
                    layer_info = blend_operations.get((fcurve.data_path, fcurve.array_index), {"order": 0})
                    frames_data[frame].append(
                        {
                            "frame": frame,
                            "val": kp.co.y,
                            "hl_x": kp.handle_left.x,
                            "hl_y": kp.handle_left.y,
                            "hr_x": kp.handle_right.x,
                            "hr_y": kp.handle_right.y,
                            "interpolation": kp.interpolation,
                            "hl_type": kp.handle_left_type,
                            "hr_type": kp.handle_right_type,
                            "layer": layer_info["order"],
                        }
                    )

            # Process blending for each frame using the 'layer' order
            for frame, keyframes in frames_data.items():
                if not keyframes:
                    continue

                keyframes.sort(key=lambda x: x["layer"])  # Now safe because 'layer' is always included

                final_val = None
                final_hl = final_hr = (0, 0)
                final_hl_type = final_hr_type = "FREE"
                for kf in keyframes:
                    influence = blend_operations.get(kf["layer"], {}).get("influence", 1)
                    blend_type = blend_operations.get(kf["layer"], {}).get("blend_type", "REPLACE")

                    if final_val is None:
                        final_val = kf["val"] * influence
                        final_hl = (kf["hl_x"] * influence, kf["hl_y"] * influence)
                        final_hr = (kf["hr_x"] * influence, kf["hr_y"] * influence)
                    else:
                        if blend_type == "REPLACE":
                            final_val = final_val * (1 - influence) + kf["val"] * influence
                            final_hl = tuple(
                                hl1 * (1 - influence) + hl2 * influence
                                for hl1, hl2 in zip(final_hl, (kf["hl_x"], kf["hl_y"]))
                            )
                            final_hr = tuple(
                                hr1 * (1 - influence) + hr2 * influence
                                for hr1, hr2 in zip(final_hr, (kf["hr_x"], kf["hr_y"]))
                            )
                        elif blend_type == "COMBINE":
                            final_val += kf["val"] * influence
                            final_hl = tuple(
                                hl1 + hl2 * influence for hl1, hl2 in zip(final_hl, (kf["hl_x"], kf["hl_y"]))
                            )
                            final_hr = tuple(
                                hr1 + hr2 * influence for hr1, hr2 in zip(final_hr, (kf["hr_x"], kf["hr_y"]))
                            )

                # Store the result for the frame
                result_data.setdefault(key, []).append(
                    {
                        "frame": frame,
                        "val": final_val,
                        "hl_x": final_hl[0],
                        "hl_y": final_hl[1],
                        "hr_x": final_hr[0],
                        "hr_y": final_hr[1],
                        "int": "BEZIER",
                        "hl_t": final_hl_type,
                        "hr_t": final_hr_type,
                    }
                )

        return result_data

    def get_nla_track_data(self, obj):
        """Retrieves NLA strip data from a Blender object, providing the necessary information
        for blending operations based on each strip's settings."""
        blend_operations = {}
        if obj.animation_data:
            for index, track in enumerate(reversed(list(obj.animation_data.nla_tracks))):
                for strip in track.strips:
                    if not strip.mute:  # Only consider unmuted strips
                        # Using tuple of action name and index as a unique key for blend operations
                        blend_operations[(strip.action.name, index)] = {
                            "blend_type": strip.blend_type,
                            "influence": strip.influence,
                            "order": index,  # Order based on the track position from top to bottom
                        }
        return blend_operations

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
