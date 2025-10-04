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
            ("SMART", "Smart", "Preserve the shape of the curve and keep the keyframes per FCurve", "SYSTEM", 0),
            ("STEP", "Step", "Create keyframes at regular intervals", "KEYTYPE_STEP_NEXT", 1),
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
            ("SOURCE", "Source", "Source interpolation", "LOOP_BACK", 0),
            ("BEZIER", "Bezier", "Bezier interpolation", "IPO_BEZIER", 1),
            ("LINEAR", "Linear", "Linear interpolation", "IPO_LINEAR", 2),
            ("CONSTANT", "Constant", "Constant interpolation", "IPO_CONSTANT", 3),
        ],
        default="SOURCE",
    )

    handles: bpy.props.EnumProperty(
        name="Handles",
        description="Handles to use when baking",
        items=[
            ("SOURCE", "Source", "Source handles", "LOOP_BACK", 0),
            ("FREE", "Free", "Free handles", "HANDLE_FREE", 1),
            ("ALIGNED", "Aligned", "Aligned handles", "HANDLE_ALIGNED", 2),
            ("VECTOR", "Vector", "Vector handles", "HANDLE_VECTOR", 3),
            ("AUTO", "Auto", "Auto handles", "HANDLE_AUTO", 4),
            ("AUTO_CLAMPED", "Auto Clamped", "Auto clamped handles", "HANDLE_AUTOCLAMPED", 5),
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

    # **Updated Property: Changed from BoolProperty to EnumProperty**
    action_override_type: bpy.props.EnumProperty(
        name="Action Override Type",
        description="Specify how to override the current action when baking",
        items=[
            ("OVERRIDE", "Override Current Action", "Override the current action"),
            ("MERGE_DOWN", "Merge Down", "Merge all tracks into the bottom NLA track"),
            ("MERGE_UP", "Merge Up", "Merge all tracks into the top NLA track"),
        ],
        default="OVERRIDE",
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
    original_keyframes = []

    frame_range = []
    baked_fcurves = []

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def execute(self, context):
        ob = context.active_object
        if ob.animation_data is None or ob.animation_data.action is None or not ob.animation_data.nla_tracks:
            self.report({"WARNING"}, "No animation data found")
            return {"CANCELLED"}

        self.frame_range = utils.curve.determine_frame_range(self, context)
        self.original_data = {}

        self.original_fcurves = self.all_fcurves_for_current_bake(context)

        if self.bake_type == "SMART":
            self.original_data = self.store_original_data(context, self.original_fcurves)

        # **Merge NLA Tracks Based on User Selection**
        self.merge_nla_tracks(ob)

        self.original_keyframes = set()

        self.smart_bake_animation(context, self.original_data)

        if self.bake_type == "SMART":
            self.baked_fcurves = self.all_fcurves_for_current_bake(context)
            self.smart_keyframe_cleanup(context, self.original_data, self.baked_fcurves)

        if self.mute_constraints:
            self.mute_relevant_constraints(context, ob, self.original_fcurves, self.frame_range)

        return {"FINISHED"}

    def merge_nla_tracks(self, obj):
        """Merge NLA tracks based on the selected override type."""
        nla_tracks = [track for track in obj.animation_data.nla_tracks if not track.mute and track.strips]

        if not nla_tracks:
            self.report({"WARNING"}, "No active NLA tracks to merge.")
            return

        # Determine the target track based on the selected option
        if self.action_override_type == "OVERRIDE":
            target_track = obj.animation_data.nla_tracks.active
            if not target_track:
                target_track = nla_tracks[0]
        elif self.action_override_type == "MERGE_DOWN":
            target_track = nla_tracks[-1]  # Bottom-most track
        elif self.action_override_type == "MERGE_UP":
            target_track = nla_tracks[0]  # Top-most track
        else:
            self.report({"WARNING"}, "Invalid Action Override Type selected.")
            return

        if target_track is None:
            self.report({"WARNING"}, "Target track is None. Cannot proceed with merging.")
            return

        print(f"Target Track: {target_track.name}")

        # Iterate over all NLA tracks and move their strips to the target track
        for track in nla_tracks[:]:  # Use a copy of the list to avoid modification issues
            if track == target_track:
                continue
            for strip in list(track.strips):
                # Debug: Check if 'track' attribute exists
                if not hasattr(strip, "track"):
                    self.report({"ERROR"}, f"NlaStrip '{strip.name}' has no 'track' attribute.")
                    continue

                try:
                    print(f"Moving Strip: {strip.name} from Track: {track.name} to Track: {target_track.name}")
                    strip.track = target_track
                except AttributeError as e:
                    self.report({"ERROR"}, f"Failed to move strip '{strip.name}': {e}")
                    continue
                except Exception as e:
                    self.report({"ERROR"}, f"An unexpected error occurred while moving strip '{strip.name}': {e}")
                    continue

            # After moving all strips, remove the now-empty track
            try:
                print(f"Removing empty Track: {track.name}")
                obj.animation_data.nla_tracks.remove(track)
            except Exception as e:
                self.report({"ERROR"}, f"Failed to remove track '{track.name}': {e}")

        self.report({"INFO"}, f"NLA tracks merged into '{target_track.name}'.")

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

    def blend_values(self, values, influences, blend_type):
        if blend_type == "REPLACE":
            return values[-1]
        elif blend_type == "COMBINE":
            normalized_influences = np.array(influences)
            total = np.sum(normalized_influences)
            if total == 0:
                normalized_influences = np.ones_like(normalized_influences) / len(normalized_influences)
            else:
                normalized_influences = normalized_influences / total
            return np.dot(values, normalized_influences)
        else:
            raise ValueError("Unsupported blend type")

    def blend_handles(self, handle_lefts, handle_rights, influences, blend_type):
        if not handle_lefts or not handle_rights:
            return bpy.types.Vector((0, 0, 0)), bpy.types.Vector((0, 0, 0))

        if blend_type == "REPLACE":
            return handle_lefts[-1], handle_rights[-1]
        elif blend_type == "COMBINE":
            normalized_influences = np.array(influences)
            total = np.sum(normalized_influences)
            if total == 0:
                normalized_influences = np.ones_like(normalized_influences) / len(normalized_influences)
            else:
                normalized_influences = normalized_influences / total
            blended_left = np.dot([handle.to_tuple() for handle in handle_lefts], normalized_influences)
            blended_right = np.dot([handle.to_tuple() for handle in handle_rights], normalized_influences)
            return bpy.types.Vector(blended_left), bpy.types.Vector(blended_right)
        else:
            raise ValueError("Unsupported blend type")

    def smart_bake_animation(self, context, data):
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE" and obj.animation_data:
                if obj.animation_data.action is None:
                    obj.animation_data.action = bpy.data.actions.new(name=f"BakedAction_{obj.name}")
                action = obj.animation_data.action
                fcurves = utils.curve.all_fcurves(action)
                for key, prop_data in data.items():
                    data_path, index, blend_type, _ = key
                    fcurve = fcurves.find(data_path, index=index)
                    if fcurve is None:
                        fcurve = fcurves.new(data_path, index=index)

                    fcurve.keyframe_points.clear()

                    unique_frames = np.unique(prop_data["frames"])
                    for frame in unique_frames:
                        frame_indices = np.where(prop_data["frames"] == frame)
                        if frame_indices[0].size > 0:
                            frame_values = prop_data["values"][frame_indices]
                            frame_influences = prop_data["influences"][frame_indices]
                            frame_handle_lefts = [prop_data["handle_lefts"][i] for i in frame_indices[0]]
                            frame_handle_rights = [prop_data["handle_rights"][i] for i in frame_indices[0]]
                            frame_interpolations = [prop_data["interpolations"][i] for i in frame_indices[0]]

                            baked_value = self.blend_values(frame_values, frame_influences, blend_type)
                            blended_handle_left, blended_handle_right = self.blend_handles(
                                frame_handle_lefts, frame_handle_rights, frame_influences, blend_type
                            )

                            keyframe = fcurve.keyframe_points.insert(frame, baked_value, options={"FAST"})
                            keyframe.interpolation = frame_interpolations[0]

                            keyframe.handle_left_type = prop_data["handle_left_types"][frame_indices[0][0]]
                            keyframe.handle_right_type = prop_data["handle_right_types"][frame_indices[0][0]]

                            keyframe.handle_left = blended_handle_left
                            keyframe.handle_right = blended_handle_right

                    fcurve.update()

        return {"FINISHED"}

    def store_original_data(self, context, fcurves):
        data = {}
        obj = context.active_object
        if obj and obj.animation_data:
            # Default blending settings when no NLA is involved
            default_blending_mode = obj.animation_data.action_blend_type
            default_influence = obj.animation_data.action_influence

            for fcurve in fcurves:
                action_name = fcurve.id_data.name  # Get the action name associated with the fcurve
                # Attempt to fetch NLA track info if available
                nla_track_info = self.get_nla_track_info(obj, action_name)

                blending_mode = nla_track_info if nla_track_info else default_blending_mode
                key = (fcurve.data_path, fcurve.array_index, blending_mode, action_name)
                frames = []
                values = []
                influences = []
                interpolations = []
                handle_left_types = []
                handle_right_types = []
                handle_lefts = []
                handle_rights = []

                for kp in fcurve.keyframe_points:
                    current_frame = int(kp.co.x)
                    frame_influence = self.get_frame_influence(obj, action_name, current_frame)

                    frames.append(current_frame)
                    values.append(kp.co.y)
                    influences.append(frame_influence)
                    interpolations.append(kp.interpolation)
                    handle_left_types.append(kp.handle_left_type)
                    handle_right_types.append(kp.handle_right_type)
                    handle_lefts.append(kp.handle_left.copy())
                    handle_rights.append(kp.handle_right.copy())

                data[key] = {
                    "frames": np.array(frames),
                    "values": np.array(values),
                    "influences": np.array(influences),
                    "interpolations": np.array(interpolations),
                    "handle_left_types": handle_left_types,  # Keep as lists for easier handling
                    "handle_right_types": handle_right_types,
                    "handle_lefts": handle_lefts,
                    "handle_rights": handle_rights,
                }

                print(f"Stored data for key {key} with blending {blending_mode}")

            print(f"Stored original data for {len(data)} fcurves")
        return data

    def get_nla_track_info(self, obj, action_name):
        """Retrieves blending mode and influence for the action's NLA track"""
        if obj.animation_data and obj.animation_data.nla_tracks:
            for track in obj.animation_data.nla_tracks:
                if not track.mute and track.active:
                    for strip in track.strips:
                        if strip.action and strip.action.name == action_name:
                            return strip.blend_type
        return None

    def get_frame_influence(self, obj, action_name, frame):
        """Retrieves the influence of a NLA strip at a specific frame if it is keyframed."""
        if obj.animation_data and obj.animation_data.nla_tracks:
            for track in obj.animation_data.nla_tracks:
                # Check all strips in each track
                for strip in track.strips:
                    # Match the action by name
                    if strip.action and strip.action.name == action_name:
                        # Check for F-Curves related to this strip's influence
                        if hasattr(strip, "fcurves") and strip.fcurves:
                            for fcurve in strip.fcurves:
                                if fcurve.data_path == "influence":
                                    # Evaluate the influence at the given frame
                                    evaluated_influence = fcurve.evaluate(frame)
                                    return evaluated_influence
                        # Fallback to the static influence of the strip if no F-Curve is found
                        return strip.influence
        # If no matching strip is found or other conditions fail
        print("No matching NLA strip found, defaulting to zero influence.")
        return 0.0

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

                        # Uncomment if you want to restore handle positions
                        # if self.handles == "SOURCE":
                        #     kp.handle_left.x, kp.handle_left.y = original_kp_data["hl"]
                        #     kp.handle_right.x, kp.handle_right.y = original_kp_data["hr"]

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
        # **Updated Property: Changed from BoolProperty to EnumProperty**
        container_action.prop(self, "action_override_type")
        container_action.prop(self, "visual_keying")

        # container_range = layout.box()
        # container_range.prop(self, "range_options")
        # row = container_range.row(align=True)
        # row.active = self.range_options == "RANGE"
        # row.prop(self, "range")

        container_curves = layout.box()
        container_curves.prop(self, "interpolation_type")
        row = container_curves.row(align=True)
        row.active = self.interpolation_type == "BEZIER"
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
