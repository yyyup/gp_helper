import bpy
import re
from bpy.props import EnumProperty, BoolProperty, IntProperty, StringProperty, FloatProperty
from ..utils.insert_keyframes import (
    get_3d_view_items,
    get_graph_editor_items,
    get_timeline_dopesheet_items,
)
from .. import utils
from ..anim_offset import support
from ..utils.curve import is_fcurve_in_radians, get_nla_strip_offset
import math
import numpy as np
from .. import __package__ as base_package


class AMP_OT_cleanup_keyframes_from_locked_transforms(bpy.types.Operator):
    bl_idname = "anim.amp_cleanup_keyframes_from_locked_transforms"
    bl_label = "Magic Clean-up"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """
    - Delete Locked (default): deletes all fcurves from locked transform channels.
    - Reset to default values (default): will restore the locked transform channels to default values.
    - Delete Unchanged: deletes all the redundant keyframes that do not contribute to the animation.
    - Cleanup Keyframes: deletes any channel that contains keys but is on default values"""

    delete_locked: bpy.props.BoolProperty(
        name="Delete Locked",
        description="Delete keyframes from locked transform channels",
        default=True,
    )
    reset_to_default: bpy.props.BoolProperty(
        name="Reset Locked to default",
        description="Reset the transform values to their default",
        default=True,
    )
    delete_unchanged: bpy.props.BoolProperty(
        name="Delete Unchanged Keyframes",
        description="Delete keyframes where the value does not change",
        default=False,
    )
    cleanup_keyframes: bpy.props.BoolProperty(
        name="Delete Unnecessary Keyframes",
        description="Delete keyframes that only contain default values",
        default=False,
    )
    affect_scope: bpy.props.EnumProperty(
        name="Affect Scope",
        description="Affect either all or only selected bones/objects",
        items=[
            ("ALL", "All", "Affect all bones/objects"),
            ("SELECTED", "Selected", "Affect only selected bones/objects"),
        ],
        default="SELECTED",
    )

    def execute(self, context):
        objects = []
        if context.mode == "OBJECT":
            objects = bpy.data.objects if self.affect_scope == "ALL" else context.selected_objects

        elif context.mode == "POSE":
            if self.affect_scope == "ALL":
                # Target all bones of the active armature if in pose mode and "ALL" is selected
                armatures = [
                    obj
                    for obj in bpy.data.objects
                    if obj.type == "ARMATURE" and obj.animation_data and obj.animation_data.action
                ]
                for armature in armatures:
                    self.cleanup_fcurves_general(armature)
                return {"FINISHED"}
            else:
                # Target only the selected armature's selected bones if in pose mode and "SELECTED" is selected
                objects = context.selected_objects

        for obj in objects:
            if obj.type == "ARMATURE" and obj.animation_data and obj.animation_data.action:
                self.cleanup_fcurves_general(obj)
                self.apply_cleanup(context)
            elif obj.type != "ARMATURE" and obj.animation_data and obj.animation_data.action:
                self.cleanup_fcurves_for_object(obj)
                self.apply_cleanup(context)
        return {"FINISHED"}

    def cleanup_fcurves_general(self, obj):
        bones = obj.pose.bones if self.affect_scope == "ALL" else [bone for bone in obj.pose.bones if bone.bone.select]
        for bone in bones:
            self.cleanup_bone_fcurves(obj, bone)

    def cleanup_bone_fcurves(self, obj, bone):
        for transform in ["location", "rotation_euler", "rotation_quaternion", "scale"]:
            data_path_prefix = f'pose.bones["{bone.name}"].'
            self.cleanup_fcurves(obj, bone, transform, data_path_prefix)

    def cleanup_fcurves_for_object(self, obj):
        utils.dprint(f"\nChecking {obj.name} for object transforms...")
        transforms_to_check = ["location", "scale", "rotation_euler"]

        # Include quaternion rotations if the object's rotation mode is QUATERNION
        if obj.rotation_mode == "QUATERNION":
            transforms_to_check.append("rotation_quaternion")

        for transform in transforms_to_check:
            # No need to skip based on rotation mode, handle directly in cleanup_fcurves
            self.cleanup_fcurves(obj, None, transform, "")

    def cleanup_fcurves(self, obj, bone, transform_type, data_path_prefix):
        utils.dprint(f"\nChecking {obj.name} - {bone.name if bone else 'Object'} for {transform_type}...")
        indices = range(3) if transform_type in ["location", "rotation_euler", "scale"] else range(4)
        for index in indices:
            if self.is_channel_locked(bone if bone else obj, transform_type, index, bone is not None):
                data_path = f"{data_path_prefix}{transform_type}" if bone else f"{transform_type}"
                if self.delete_locked:
                    self.delete_fcurve(obj, data_path, index)

                if self.reset_to_default:
                    self.reset_property_to_default(obj, bone, transform_type, index)
            else:
                utils.dprint(f"Channel not locked or not applicable: {transform_type}[{index}]")

    def delete_fcurve(self, obj, data_path, index):
        fcurves = (
            utils.curve.all_fcurves(obj.animation_data.action)
            if obj.animation_data and obj.animation_data.action
            else None
        )
        if fcurves:
            target_fcurve = next(
                (f for f in fcurves if f.data_path == data_path and f.array_index == index),
                None,
            )
            if target_fcurve:
                utils.dprint(f"Deleting F-Curve: {data_path}[{index}]")
                # Use the new helper function for removal (supports Blender 4.4+)
                action = obj.animation_data.action
                if not utils.curve.remove_fcurve_from_action(action, target_fcurve):
                    utils.dprint(f"Failed to remove F-Curve: {data_path}[{index}]")
            else:
                utils.dprint(f"F-Curve not found for deletion: {data_path}[{index}]")

    def reset_property_to_default(self, obj, bone, transform_type, index):
        if bone:  # Handling for bones
            if transform_type == "rotation_quaternion":
                default_values = (1.0, 0.0, 0.0, 0.0)  # Default quaternion values
                if index == 0:
                    bone.rotation_quaternion[index] = default_values[index]  # Reset 'w' component
                else:
                    bone.rotation_quaternion[index] = default_values[index]  # Reset 'x', 'y', 'z' components
            else:
                # For location and scale, and euler rotations of bones
                default_value = 0.0 if transform_type != "scale" else 1.0
                setattr(bone, transform_type, (default_value, default_value, default_value))  # Reset the vector
        else:  # Handling for objects
            if transform_type == "rotation_quaternion":
                # Reset the entire quaternion for objects
                obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            else:
                # For location, scale, and euler rotations of objects
                default_value = 0.0 if transform_type != "scale" else 1.0
                if transform_type == "location" or transform_type == "scale":
                    current_value = getattr(obj, transform_type)
                    new_value = [default_value if i == index else current_value[i] for i in range(len(current_value))]
                    setattr(obj, transform_type, new_value)
                elif transform_type == "rotation_euler":
                    obj.rotation_euler[index] = default_value  # Directly set euler components

    def is_channel_locked(self, target, transform_type, index, is_bone=True):
        locked = False
        if is_bone:
            # Bone logic
            if transform_type in ["location", "scale"]:
                locked = getattr(target, f"lock_{transform_type}")[index]
            elif transform_type == "rotation_euler":
                locked = target.lock_rotation[index] if index < len(target.lock_rotation) else False
            elif transform_type == "rotation_quaternion":
                locked = target.lock_rotation_w if index == 0 else target.lock_rotation[index - 1]
        else:
            # Object logic
            if transform_type in ["location", "scale"]:
                locked = getattr(target, f"lock_{transform_type}")[index]
            elif transform_type == "rotation_quaternion":
                # Check if the object's rotation mode is quaternion and adjust accordingly
                if index == 0:
                    locked = target.lock_rotation_w
                else:
                    locked = target.lock_rotation[index - 1]
            elif transform_type == "rotation_euler":
                locked = target.lock_rotation[index]

        utils.dprint(f"{'Locked' if locked else 'Unlocked'}: {target.name} - {transform_type}[{index}]")
        return locked

    def delete_unchanged_keyframes(self, fcurves):
        """Delete keyframes that do not contribute to the animation."""
        for fcurve in fcurves:
            keyframes_to_remove = []

            # Using range(1, len(fcurve.keyframe_points) - 1) ensures we don't consider the first and last keyframe for removal
            for i in range(1, len(fcurve.keyframe_points) - 1):
                prev_keyframe = fcurve.keyframe_points[i - 1]
                current_keyframe = fcurve.keyframe_points[i]
                next_keyframe = fcurve.keyframe_points[i + 1]

                # Check if the current keyframe's value is the same as the previous and next keyframe's value
                if current_keyframe.co[1] == prev_keyframe.co[1] and current_keyframe.co[1] == next_keyframe.co[1]:
                    keyframes_to_remove.append(i)

            # Remove keyframes in reverse order to prevent index shifting
            for index in reversed(keyframes_to_remove):
                fcurve.keyframe_points.remove(fcurve.keyframe_points[index])

    def cleanup_flat_fcurves(self, fcurves):
        """Remove F-Curves that are flat and do not contribute to the animation."""
        fcurves_to_remove = []
        for fcurve in fcurves:
            if all(keyframe.co[1] == fcurve.keyframe_points[0].co[1] for keyframe in fcurve.keyframe_points):
                fcurves_to_remove.append(fcurve)
        # Remove flat F-Curves
        for fcurve in fcurves_to_remove:
            fcurves.remove(fcurve)

    def get_targets(self, context):
        targets = []
        if context.mode == "OBJECT":
            targets = bpy.data.objects if self.affect_scope == "ALL" else context.selected_objects
        elif context.mode == "POSE":
            if self.affect_scope == "ALL":
                targets = [
                    obj
                    for obj in bpy.data.objects
                    if obj.type == "ARMATURE" and obj.animation_data and obj.animation_data.action
                ]
            else:
                targets = context.selected_objects
        return targets

    def apply_cleanup(self, context):
        """Apply cleanup operations based on user properties."""
        if context.mode == "POSE" and self.affect_scope == "SELECTED":
            armature = context.active_object
            if armature and armature.type == "ARMATURE" and armature.animation_data and armature.animation_data.action:
                action = armature.animation_data.action
                for bone in context.selected_pose_bones:
                    for fcurve in utils.curve.all_fcurves(action):
                        # Check if the fcurve belongs to the current bone
                        if fcurve.data_path.startswith(f'pose.bones["{bone.name}"]'):
                            self.cleanup_action([fcurve])
        else:
            targets = self.get_targets(context)
            for obj in targets:
                if obj.animation_data and obj.animation_data.action:
                    self.cleanup_action(utils.curve.all_fcurves(obj.animation_data.action))

    def cleanup_action(self, fcurves):
        """Apply cleanup operations to a single action."""
        if self.delete_unchanged:
            self.delete_unchanged_keyframes(fcurves)
        if self.cleanup_keyframes:
            self.cleanup_flat_fcurves(fcurves)


class AMP_OT_select_fcurves(bpy.types.Operator):
    bl_idname = "anim.amp_toggle_fcurves_selection"
    bl_label = "Toggle Specific F-Curves Selection"
    bl_options = {"REGISTER"}
    bl_description = (
        "Toggle F-Curves selection or visibility based on type "
        "(Translation, Rotation, Scale, Constraints, Others, All)\n"
        "- Isolate this type of fcurves.\n"
        "- Shift + Click Display all fcurves"
    )

    action_type: EnumProperty(
        items=[
            ("TRANSLATION", "Translation", ""),
            ("ROTATION", "Rotation", ""),
            ("SCALE", "Scale", ""),
            ("SHAPES", "Shapes", "Select F-Curves related to Shape Keys"),
            ("CONST", "Constraints", "Select F-Curves related to Constraint Influences"),
            ("CUSTOMPROPS", "CUSTOMPROPS", "Select F-Curves for Custom Properties"),
            ("ALL", "All", "Select all F-Curves for the object/bone"),
        ],
        name="Action Type",
        description="Type of action to select/deselect or show/hide F-Curves for",
    )

    extra_options: EnumProperty(
        name="Extra Options",
        description="Additional selection options.",
        items=[
            ("NONE", "None", "No extra action"),
            ("TOGGLE_VISIBILITY", "Toggle Visibility", "Toggle the visibility of the F-Curves"),
            ("DESELECT_ALL", "Deselect All", "Deselect all F-Curves before selecting the specified type"),
        ],
        default="NONE",
    )

    transform_if_selected: BoolProperty(
        name="Transform if Selected",
        description="Transform keyframes if any keyframe is already selected",
        default=False,
    )

    isolate: EnumProperty(
        name="Isolate",
        description="Isolate the selected F-Curves by hiding all others",
        items=[
            ("ISOLATE", "Isolate", "Isolate the selected F-Curves"),
            ("EXIT_ISOLATE", "Un Isolate", "Exit the isolate mode"),
            ("NONE", "Keep visibility", "No isolation action"),
        ],
        default="ISOLATE",
    )

    cycle: BoolProperty(
        name="Cycle",
        description="Cycle through the F-Curves",
        default=False,
    )

    # Modifier keys
    ctrl_pressed: BoolProperty(default=False)
    shift_pressed: BoolProperty(default=False)
    alt_pressed: BoolProperty(default=False)
    os_key: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        # Always allow the operator to run, but provide graceful handling in execute
        # This way users can still access the operator even without animation data
        return True

    def invoke(self, context, event):
        self.ctrl_pressed = event.ctrl
        self.shift_pressed = event.shift
        self.alt_pressed = event.alt
        self.os_key = event.oskey
        return self.execute(context)

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        self.isolate = "ISOLATE" if prefs.isolate_fcurves else "EXIT_ISOLATE"
        self.cycle = prefs.cycle_fcurves

        if self.shift_pressed and self.ctrl_pressed:
            self.extra_options = "DESELECT_ALL"
            self.isolate = "EXIT_ISOLATE"
            self.cycle = True
        elif self.shift_pressed:
            self.extra_options = "DESELECT_ALL"
            self.isolate = "EXIT_ISOLATE"
        elif self.ctrl_pressed or self.os_key:
            self.extra_options = "DESELECT_ALL"
            self.cycle = True
        elif self.alt_pressed:
            self.extra_options = "TOGGLE_VISIBILITY"

        if prefs.expand_curve_groups:
            editor_types = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}
            for win in context.window_manager.windows:
                for area in win.screen.areas:
                    if area.type not in editor_types:
                        continue
                    region = next((r for r in area.regions if r.type == "WINDOW"), None)
                    if not region:
                        continue
                    ov = context.copy()
                    ov.update({"window": win, "screen": win.screen, "area": area, "region": region})
                    with context.temp_override(**ov):
                        bpy.ops.anim.channels_expand()

        if context.mode == "OBJECT":
            objects, bones = context.selected_objects, []
        elif context.mode == "POSE":
            objects, bones = [], context.selected_pose_bones
        else:
            objects, bones = [context.active_object], []
        if self.action_type != getattr(prefs, "last_transform_type", None):
            prefs.deselect_state_index = -1

        prefs.last_transform_type = self.action_type

        if self.transform_if_selected and context.selected_editable_keyframes:
            self.apply_transform(context)
            return {"FINISHED"}

        editor_types = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}
        overrides = []

        for win in context.window_manager.windows:
            for area in win.screen.areas:
                if area.type not in editor_types:
                    continue
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if not region:
                    continue
                ov = context.copy()
                ov.update({"window": win, "screen": win.screen, "area": area, "region": region})
                overrides.append(ov)

        if not overrides:
            self.report({"WARNING"}, "No Editor with Curve Channels open.")
            return {"CANCELLED"}

        # Determine the current cycle index once for all editors
        current_cycle_index = None
        if self.cycle and self.extra_options == "DESELECT_ALL":
            wm = bpy.context.window_manager
            current_cycle_index = wm.get("cycle_axis_index", 0)

        for i, ov in enumerate(overrides):

            with context.temp_override(**ov):
                # Check if there's valid animation data before proceeding
                has_animation_data = False
                if bpy.context.active_object and bpy.context.active_object.animation_data:
                    action = bpy.context.active_object.animation_data.action
                    if action and action.fcurves:
                        has_animation_data = True

                # Store selection state to restore later
                selected_bones = []
                selected_objects = []
                active_object = context.active_object

                if context.mode == "POSE" and context.selected_pose_bones:
                    selected_bones = [bone.name for bone in context.selected_pose_bones]
                elif context.mode == "OBJECT" and context.selected_objects:
                    selected_objects = [obj.name for obj in context.selected_objects]

                # Only proceed with operations if there's animation data or if we're in a valid editor context
                try:
                    bpy.ops.anim.channels_select_all(action="DESELECT")
                except RuntimeError:
                    # Failed to deselect channels, likely no proper animation context
                    pass

                # Restore selection based on context mode
                if context.mode == "POSE" and selected_bones and active_object:
                    if active_object.type == "ARMATURE":
                        for bone_name in selected_bones:
                            if bone_name in active_object.pose.bones:
                                active_object.pose.bones[bone_name].bone.select = True
                elif context.mode == "OBJECT" and selected_objects:
                    # Restore object selection
                    for obj_name in selected_objects:
                        if obj_name in bpy.data.objects:
                            bpy.data.objects[obj_name].select_set(True)

                # Handle solo fcurve only for Graph Editors, but only if it won't interfere with multi-editor functionality
                # Ensure all F-curves are visible before applying new filtering
                if bpy.context.area.type == "GRAPH_EDITOR" and has_animation_data:
                    try:
                        bpy.ops.graph.reveal(select=False)
                    except RuntimeError:
                        # Failed to reveal, likely no F-curves in graph editor
                        pass

                if prefs.solo_fcurve and bpy.context.area.type == "GRAPH_EDITOR" and has_animation_data:

                    graph_editors_only = all(ov_check["area"].type == "GRAPH_EDITOR" for ov_check in overrides)
                    if graph_editors_only:
                        isolate_fcurve(self, bpy.context)

                if self.extra_options == "DESELECT_ALL":
                    try:
                        if bpy.context.area.type == "GRAPH_EDITOR":
                            bpy.ops.graph.select_all(action="DESELECT")
                        else:
                            bpy.ops.action.select_all(action="DESELECT")
                    except RuntimeError:
                        # Failed to deselect, likely no proper animation context
                        pass

                # Only handle cycling state once (on first editor), but pass the cycle index to all
                is_first_editor = i == 0
                self.handle_fcurves_selection(
                    objects, bones, bpy.context, handle_cycle_state=is_first_editor, cycle_index=current_cycle_index
                )

                if self.isolate == "ISOLATE" and bpy.context.area.type == "GRAPH_EDITOR" and has_animation_data:
                    try:
                        bpy.ops.graph.hide(unselected=True)
                    except RuntimeError:
                        # Failed to hide, likely no F-curves to hide
                        pass

                elif self.isolate == "EXIT_ISOLATE" and bpy.context.area.type == "GRAPH_EDITOR":
                    try:
                        bpy.ops.graph.reveal()
                    except RuntimeError:
                        # Failed to reveal, likely no F-curves to reveal
                        pass

        # utils.curve.deselect_all_keyframes_in_editors(context)

        try:
            if prefs.zoom_to_visible_curve and not prefs.smart_zoom:
                bpy.ops.anim.amp_zoom_frame_editors()
            elif prefs.smart_zoom:
                bpy.ops.anim.amp_smart_zoom_frame_editors(frame_range_smart_zoom=prefs.frame_range_smart_zoom)

        except RuntimeError:
            # Failed to zoom, likely no animation data to frame
            pass
        return {"FINISHED"}

    def handle_fcurves_selection(self, objects, bones, context, handle_cycle_state=True, cycle_index=None):
        if not objects and not bones:
            return
        all_fcurves = []

        match_criteria = self.get_matching_criteria()
        for obj in objects:
            if obj.animation_data and obj.animation_data.action:
                for fc in utils.curve.all_fcurves(obj.animation_data.action):
                    if self.action_type == "ALL" or match_criteria(fc.data_path):
                        all_fcurves.append(fc)

        for bone in bones:
            obj = bone.id_data
            if obj.animation_data and obj.animation_data.action:
                for fc in utils.curve.all_fcurves(obj.animation_data.action):
                    prefix = f'pose.bones["{bone.name}"]'
                    if fc.data_path.startswith(prefix):
                        sub = fc.data_path[len(prefix) :]
                        if self.action_type == "ALL" or match_criteria(sub):
                            all_fcurves.append(fc)

        all_fcurves = list(set(all_fcurves))

        if self.extra_options == "TOGGLE_VISIBILITY":
            self.toggle_visibility(all_fcurves)
        elif self.extra_options == "DESELECT_ALL":
            self.cycle_deselect_fcurves(all_fcurves, handle_cycle_state, cycle_index)
        else:
            self.toggle_selection(all_fcurves)

        # Expand groups for selected F-curves if preference is enabled
        prefs = bpy.context.preferences.addons[base_package].preferences
        if prefs.expand_curve_groups:
            try:
                bpy.ops.anim.channels_expand()
            except RuntimeError:
                pass  # Operator not available in current context

        if self.isolate == "ISOLATE" and context.area.type == "GRAPH_EDITOR":
            try:
                bpy.ops.graph.hide(unselected=True)
            except RuntimeError:
                # Failed to hide, likely no F-curves to hide
                pass
        elif self.isolate == "EXIT_ISOLATE" and context.area.type == "GRAPH_EDITOR":
            try:
                bpy.ops.graph.reveal()
            except RuntimeError:
                # Failed to reveal, likely no F-curves to reveal
                pass

    def get_matching_criteria(self):
        """Return a function that matches F-Curve data paths based on the action type."""
        # TRANSFORM ROTATION SCALE SHAPES CONST CUSTOMPROPS
        if self.action_type == "TRANSLATION":
            pattern = re.compile(r"location$")
            return lambda dp: bool(pattern.search(dp))
        elif self.action_type == "ROTATION":
            pattern = re.compile(r"rotation_quaternion$|rotation_euler$|rotation_axis_angle$")
            return lambda dp: bool(pattern.search(dp))
        elif self.action_type == "SCALE":
            pattern = re.compile(r"scale$")
            return lambda dp: bool(pattern.search(dp))
        elif self.action_type == "SHAPES":
            pattern = re.compile(r'^key_blocks\[".*"\]$')
            return lambda dp: bool(pattern.match(dp))
        elif self.action_type == "CONST":
            return lambda dp: dp.endswith(("influence", "weight", "enabled"))
        elif self.action_type == "CUSTOMPROPS":
            pattern = re.compile(r'\["[^"]+"\]$')
            return lambda dp: bool(pattern.search(dp))
        else:
            return lambda dp: False

    def get_transform_paths(self, action_type):
        """Return the relevant transform paths based on the action_type."""
        base_paths = {
            "TRANSLATION": ["location"],
            "ROTATION": ["rotation_euler", "rotation_quaternion", "rotation_axis_angle"],
            "SCALE": ["scale"],
        }
        return base_paths.get(action_type, [])

    def toggle_visibility(self, fcurves):
        """Toggle visibility of the provided F-Curves based on majority state."""
        if not fcurves:
            return

        # Count how many F-Curves are currently visible
        visible_count = sum(not fc.hide for fc in fcurves)
        # Determine the majority state
        should_hide = visible_count >= len(fcurves) / 2

        # Toggle visibility
        for fc in fcurves:
            fc.hide = should_hide

    def toggle_selection(self, fcurves):
        """Toggle selection state of the provided F-Curves based on majority state."""
        if not fcurves:
            return

        # Count how many F-Curves are currently selected
        selected_count = sum(fc.select for fc in fcurves)
        # Determine the majority state
        should_deselect = selected_count >= len(fcurves) / 2

        # Toggle selection
        for fc in fcurves:
            fc.select = not should_deselect

    def deselect_all_fcurves(self, fcurves):
        """Deselect all provided F-Curves."""
        if not fcurves:
            return

        for fc in fcurves:
            fc.select = False

    def cycle_deselect_fcurves(self, fcurves, handle_cycle_state=True, cycle_index=None):
        """Cycle through fcurves by isolating channels based on transformation type.

        For non-rotation transformations (or when only one rotation type is present):
        - The cycle order is the sorted order of available array_index values.

        For ROTATION:
        - If both Euler and quaternion curves are present, they are cycled in sync:
            * Euler: cycle order is sorted (typically [0, 1, 2] corresponding to X, Y, Z)
            * Quaternions: if a full set {0,1,2,3} exists, force the order [1, 2, 3, 0]
                so that on cycle step 0 quats show X (array_index 1), step 1 show Y (2),
                step 2 show Z (3), and step 3 show W (0).
            * On the fourth step Euler remains deselected.
        - If only one rotation type is present, use that type’s order.
        """
        wm = bpy.context.window_manager

        # If not cycling, simply select all matching fcurves and reset counter.
        if not self.cycle:
            for fc in fcurves:
                fc.select = True
            if handle_cycle_state:
                wm["cycle_axis_index"] = 0
            return

        # Start by deselecting all fcurves.
        for fc in fcurves:
            fc.select = False

        # Use passed cycle_index if available, otherwise get from window manager
        if cycle_index is not None:
            current_cycle = cycle_index
        else:
            current_cycle = wm.get("cycle_axis_index", 0)

        # Separate fcurves by type
        euler_fcurves = [
            fc for fc in fcurves if ("rotation_euler" in fc.data_path or "rotation_axis_angle" in fc.data_path)
        ]
        quat_fcurves = [fc for fc in fcurves if "rotation_quaternion" in fc.data_path]
        other_transform_fcurves = [
            fc
            for fc in fcurves
            if any(transform in fc.data_path for transform in ["location", "scale"]) and hasattr(fc, "array_index")
        ]
        non_indexed_fcurves = [
            fc
            for fc in fcurves
            if not hasattr(fc, "array_index")
            or (
                hasattr(fc, "array_index")
                and not any(transform in fc.data_path for transform in ["location", "scale", "rotation"])
            )
        ]

        # Define the standard cycle order: X=0, Y=1, Z=2, W=3
        standard_order = [0, 1, 2, 3]

        # For quaternions, map the indices to match our X,Y,Z,W order
        quat_index_map = {0: 1, 1: 2, 2: 3, 3: 0}  # cycle step -> quat array_index

        # Determine maximum cycle steps (4 for quaternions, 3 for others)
        has_quaternions = bool(quat_fcurves)
        max_steps = 4 if has_quaternions else 3

        if current_cycle >= max_steps:
            current_cycle = 0

        # Select fcurves based on current cycle step
        current_axis = standard_order[current_cycle] if current_cycle < len(standard_order) else None

        # Select Euler/axis-angle rotation fcurves (X=0, Y=1, Z=2)
        if current_cycle < 3:  # X, Y, Z steps
            for fc in euler_fcurves:
                if hasattr(fc, "array_index") and fc.array_index == current_axis:
                    fc.select = True

        # Select quaternion fcurves with remapped indices
        if has_quaternions and current_cycle < 4:
            quat_target_index = quat_index_map[current_cycle]
            for fc in quat_fcurves:
                if hasattr(fc, "array_index") and fc.array_index == quat_target_index:
                    fc.select = True

        # Select other transform fcurves (location, scale) for X, Y, Z
        if current_cycle < 3:  # X, Y, Z steps only
            for fc in other_transform_fcurves:
                if hasattr(fc, "array_index") and fc.array_index == current_axis:
                    fc.select = True

        # Select non-indexed fcurves (custom properties, etc.) only on X step (step 0)
        if current_cycle == 0:
            for fc in non_indexed_fcurves:
                fc.select = True

        if handle_cycle_state:
            wm["cycle_axis_index"] = current_cycle + 1

    def apply_transform(self, context):
        """Apply transformation based on the selected action type and editor context."""
        if context.area.type == "GRAPH_EDITOR":
            # Apply transformations specific to Graph Editor
            if self.action_type == "TRANSLATION":
                bpy.ops.transform.translate("INVOKE_DEFAULT")
            elif self.action_type == "ROTATION":
                bpy.ops.transform.rotate("INVOKE_DEFAULT")
            elif self.action_type == "SCALE":
                bpy.ops.transform.resize("INVOKE_DEFAULT")
        elif context.area.type == "DOPESHEET_EDITOR":
            # Apply transformations specific to Dopesheet Editor
            if self.action_type == "TRANSLATION":
                bpy.ops.transform.transform("INVOKE_DEFAULT", mode="TIME_TRANSLATE")
            elif self.action_type == "ROTATION":
                # Implement rotation transform if needed
                pass
            elif self.action_type == "SCALE":
                bpy.ops.transform.transform("INVOKE_DEFAULT", mode="TIME_SCALE")


class AMP_OT_insert_keyframe(bpy.types.Operator):
    """Insert Keyframe with Context-Aware Behavior"""

    bl_idname = "anim.amp_timeline_insert_keyframe"
    bl_label = "Insert Keyframe"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None
    _timer_started = False

    def modal(self, context, event):
        if event.type == "TIMER" and self._timer_started:
            # Timer event has occurred, show the menu
            # self.show_context_menu(context)
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            self._timer_started = False
            return {"FINISHED"}

        if event.type == "TIMER":  # Catch all timer events, ensuring no stray timers
            return {"RUNNING_MODAL"}

        if event.value == "RELEASE" and self._timer_started:
            # The "I" key was released before the timer event, insert keyframe and cancel the timer
            context.window_manager.event_timer_remove(self._timer)
            self.insert_keyframe_based_on_context(context)
            self._timer = None
            self._timer_started = False
            return {"FINISHED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        # Assuming this operator is only called with the "I" key, start the timer immediately
        self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        self._timer_started = True
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def insert_keyframe_based_on_context(self, context):
        # Insert keyframe based on the current context and user preference
        prefs = bpy.context.preferences.addons[base_package].preferences
        if context.area.type == "VIEW_3D":
            method = prefs.default_3d_view_insert_keyframe
            try:
                bpy.ops.anim.keyframe_insert_menu(type=method)
            except Exception as e:
                self.report({"WARNING"}, f"Error inserting keyframe: {e}")

        elif context.area.type == "GRAPH_EDITOR":
            method = prefs.default_graph_editor_insert_keyframe
            try:
                bpy.ops.graph.keyframe_insert(type=method)
            except Exception as e:
                self.report({"WARNING"}, f"Error inserting keyframe: {e}")

        elif context.area.type in ["DOPESHEET_EDITOR", "TIMELINE"]:
            method = prefs.default_timeline_dopesheet_insert_keyframe
            try:
                bpy.ops.action.keyframe_insert(type=method)
            except Exception as e:
                self.report({"WARNING"}, f"Error inserting keyframe: {e}")

    # def show_context_menu(self, context):
    #     # Show the context-sensitive menu for keyframe insertion
    #     bpy.ops.wm.call_menu(name="TIMELINE_MT_dynamic_keyframe_insert_menu")


class AMP_OT_SetKeyframesValue(bpy.types.Operator):
    """Set Keyframes to a Specified Value or Their Default Value"""

    bl_idname = "anim.amp_set_keyframes_value"
    bl_label = "Set Keyframes Value"
    bl_options = {"REGISTER", "UNDO"}

    reset_to_default: bpy.props.BoolProperty(
        name="Reset to Default", description="Reset keyframes to their default values", default=False
    )
    set_value: bpy.props.FloatProperty(name="Set Value", description="Value to set the keyframes to", default=0.0)

    def get_default_value(self, fcurve):
        """Determine the default value based on the fcurve data path and array index."""
        data_path = fcurve.data_path
        array_index = fcurve.array_index

        if "location" in data_path:
            return 0.0
        elif "rotation_euler" in data_path:
            return 0.0
        elif "rotation_quaternion" in data_path:
            return 1.0 if array_index == 0 else 0.0
        elif "scale" in data_path:
            return 1.0
        else:
            return 0.0

    def execute(self, context):
        obj = context.active_object
        action = obj.animation_data.action

        if not action:
            self.report({"WARNING"}, "No animation data found.")
            return {"CANCELLED"}

        for fcurve in context.selected_visible_fcurves:
            if utils.curve.all_fcurves(action):
                default_value = self.get_default_value(fcurve)
                for keyframe in fcurve.keyframe_points:
                    # Only affect selected keyframes
                    if keyframe.select_control_point:
                        if self.reset_to_default:
                            keyframe.co[1] = default_value
                        else:
                            keyframe.co[1] = self.set_value

            fcurve.update()

        return {"FINISHED"}


def AnimResetKeyframeValueButtons(layout, context):
    prefs = bpy.context.preferences.addons[base_package].preferences

    row = layout.row(align=True)

    reset_op = row.operator(
        "anim.amp_set_keyframes_value",
        text="",
        icon="LOOP_BACK",
    )
    reset_op.reset_to_default = True
    row.label(text="Reset to default")

    set_value_row = layout.row(align=True)

    set_op = set_value_row.operator(
        "anim.amp_set_keyframes_value",
        text="",
        icon="DRIVER_TRANSFORM",
    )
    set_op.reset_to_default = False
    set_op.set_value = prefs.set_keyframe_value

    set_value_row.prop(prefs, "set_keyframe_value", text="", emboss=False)


class AMP_OT_MovePlayHeadToKeyframe(bpy.types.Operator):

    bl_description = """Move playhead to the first selected keyframe in the Graph Editor."""
    bl_idname = "anim.amp_move_playhead_to_first_selected_keyframe"
    bl_label = "Move Playhead to First Selected Keyframe"
    bl_options = {"REGISTER", "UNDO"}

    def jump_to_keyframe(self, context):
        obj = context.active_object
        selected_keyframes = []

        if obj is None:
            self.report({"WARNING"}, "No active object found.")
            return {"CANCELLED"}

        if obj.animation_data and obj.animation_data.action:
            selected_keyframes = utils.select_keyframes(context)

            utils.move_playhead_to_lowest_keyframe(selected_keyframes)

        if not selected_keyframes:
            return {"CANCELLED"}

    def execute(self, context):
        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            self.jump_to_keyframe(context)

        return {"FINISHED"}


class AMP_OT_SelectKeyframeAndMovePlayehad(bpy.types.Operator):
    """Select keyframes and move playhead to the first selected keyframe"""

    bl_options = {"REGISTER", "UNDO"}
    bl_idname = "anim.amp_select_keyframe_and_move_playhead"
    bl_label = "Select Keyframe and Move Playhead"

    def execute(self, context):
        try:
            bpy.ops.graph.clickselect(deselect_all=True)
        except RuntimeError:
            # Failed to click select, likely no graph editor context
            pass
        bpy.ops.anim.amp_move_playhead_to_first_selected_keyframe()
        return {"FINISHED"}


class AMP_OT_select_or_transform_keyframes(bpy.types.Operator):

    bl_idname = "anim.amp_select_or_transform_keyframes"
    bl_label = "Select or Transform Keyframes"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Select keyframes of a specific transform type or perform the transform if already selected"

    transform_type: bpy.props.StringProperty()  # 'MOVE', 'ROTATE', 'SCALE'

    def execute(self, context):
        # Determine if any keyframes are already selected
        obj = context.active_object
        already_selected = False
        if obj.animation_data and obj.animation_data.action:
            fcurves = utils.curve.all_fcurves(obj.animation_data.action)
            for fcurve in fcurves:
                for keyframe in fcurve.keyframe_points:
                    if keyframe.select_control_point:
                        already_selected = True
                        break
                if already_selected:
                    break

        # If keyframes are already selected, invoke the corresponding function
        if already_selected:
            if self.transform_type == "MOVE":
                bpy.ops.transform.translate("INVOKE_DEFAULT")
            elif self.transform_type == "ROTATE":
                bpy.ops.transform.rotate("INVOKE_DEFAULT")
            elif self.transform_type == "SCALE":
                bpy.ops.transform.resize("INVOKE_DEFAULT")
            return {"FINISHED"}

        # If no keyframes are selected, select keyframes based on the transform type
        for fcurve in fcurves:
            data_path = fcurve.data_path
            if self.transform_type == "MOVE" and "location" in data_path:
                fcurve.select = True
            elif self.transform_type == "ROTATE" and "rotation" in data_path:
                fcurve.select = True
            elif self.transform_type == "SCALE" and "scale" in data_path:
                fcurve.select = True

        # Ensure the UI updates to show the selection
        for area in context.screen.areas:
            if area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
                area.tag_redraw()

        return {"FINISHED"}


class AMP_OT_JumpToKeyframe(bpy.types.Operator):
    bl_idname = "anim.amp_jump_to_keyframe"
    bl_label = "Jump to Keyframe"
    bl_options = {"UNDO"}
    bl_description = (
        "Jump to the next or previous keyframe in Graph, Dope Sheet, or Timeline; " "optionally select it after jumping"
    )

    direction: EnumProperty(
        name="Direction",
        items=[
            ("NEXT", "Next", "Jump to the next keyframe"),
            ("PREVIOUS", "Previous", "Jump to the previous keyframe"),
        ],
        default="NEXT",
    )
    select_keyframes: BoolProperty(
        name="Select Keyframes",
        description="Select the keyframe after jumping to it",
        default=False,
    )

    def execute(self, context):
        valid = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}

        # decide whether to override or use current
        if context.area and context.area.type in valid:
            use_override = False
            target_area = context.area.type
        else:
            override = utils.find_editor_override(context, valid)
            if not override:
                self.report({"WARNING"}, "No Graph, Dope Sheet, or Timeline found")
                return {"CANCELLED"}
            use_override = True
            target_area = override["area"].type

        # map area to operator depending on blender version
        if bpy.app.version < (4, 5, 0):
            op_map = {
                "GRAPH_EDITOR": ("graph", "keyframe_jump"),
                "DOPESHEET_EDITOR": ("screen", "keyframe_jump"),
                "TIMELINE": ("screen", "keyframe_jump"),
            }
        else:
            op_map = {
                "GRAPH_EDITOR": ("screen", "keyframe_jump"),
                "DOPESHEET_EDITOR": ("screen", "keyframe_jump"),
                "TIMELINE": ("screen", "keyframe_jump"),
            }

        mod_name, func_name = op_map[target_area]
        kwargs = {"next": (self.direction == "NEXT")}

        def do_jump():
            op_mod = getattr(bpy.ops, mod_name)
            op_func = getattr(op_mod, func_name)
            return op_func(**kwargs)

        prefs = utils.get_prefs()
        # perform jump (and selection) in appropriate context
        try:
            if use_override:
                with context.temp_override(**override):
                    result = do_jump()
                    if prefs.select_keyframes_on_current_frame and self.select_keyframes:
                        utils.curve.select_keyframe_in_editors(context)
            else:
                result = do_jump()
                if prefs.select_keyframes_on_current_frame and self.select_keyframes:
                    utils.curve.select_keyframe_in_editors(context)

        except RuntimeError:
            msg = "No editable keyframes visible" if target_area == "GRAPH_EDITOR" else "No keyframes visible"
            self.report({"INFO"}, msg)
            return {"CANCELLED"}

        if result != {"FINISHED"}:
            self.report({"INFO"}, "No keyframe jump performed")
            return {"CANCELLED"}

        return {"FINISHED"}


class AMP_OT_SelectFCurveChannels(bpy.types.Operator):
    bl_idname = "anim.amp_select_fcurve_channels"
    bl_label = "Select F-Curve Channels"
    bl_options = {"UNDO"}
    bl_description = (
        "Select entire F-Curve channels in all open Graph, Dope Sheet, "
        "and Timeline editors for the given axis and transform channel "
        "for all selected objects/bones"
        "   - Shift to add to selection"
        "   - Ctrl to toggle visibility"
    )

    axis: EnumProperty(
        name="Axis",
        items=[
            ("X", "X", "X axis"),
            ("Y", "Y", "Y axis"),
            ("Z", "Z", "Z axis"),
            ("W", "W", "W axis / angle"),
        ],
        default="X",
    )
    channel: EnumProperty(
        name="Transform Channel",
        items=[
            ("LOC", "Location", "Location channels"),
            ("ROT", "Rotation", "Rotation channels"),
            ("SCA", "Scale", "Scale channels"),
        ],
        default="LOC",
    )

    def invoke(self, context, event):
        # Capture modifiers: shift = add to selection, ctrl = toggle visibility
        self._add = event.shift
        self._toggle = event.ctrl
        return self.execute(context)

    def execute(self, context):
        valid = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}

        # index lookup tables
        base_idx = {"X": 0, "Y": 1, "Z": 2, "W": 3}
        quat_idx = {"W": 0, "X": 1, "Y": 2, "Z": 3}
        axisangle_idx = {"W": 0, "X": 1, "Y": 2, "Z": 3}

        # choose suffixes by channel
        if self.channel == "LOC":
            suffixes = ("location",)
        elif self.channel == "ROT":
            suffixes = (
                "rotation_euler",
                "rotation_quaternion",
                "rotation_axis_angle",
            )
        else:
            suffixes = ("scale",)

        # Get selected objects and bones
        if context.mode == "OBJECT":
            selected_objects = context.selected_objects
            selected_bones = []
        elif context.mode == "POSE":
            selected_objects = []
            selected_bones = context.selected_pose_bones
        else:
            selected_objects = [context.active_object] if context.active_object else []
            selected_bones = []

        # Collect all relevant actions and F-curves
        target_fcurves = []

        # Process selected objects
        for obj in selected_objects:
            if obj and obj.animation_data and obj.animation_data.action:
                action = obj.animation_data.action
                for fcu in utils.curve.all_fcurves(action):
                    path = fcu.data_path
                    suffix = next((s for s in suffixes if path.endswith(s)), None)
                    if suffix and self._matches_axis(fcu, suffix, base_idx, quat_idx, axisangle_idx):
                        target_fcurves.append(fcu)

        # Process selected pose bones
        for bone in selected_bones:
            obj = bone.id_data
            if obj and obj.animation_data and obj.animation_data.action:
                action = obj.animation_data.action
                bone_prefix = f'pose.bones["{bone.name}"]'
                for fcu in utils.curve.all_fcurves(action):
                    path = fcu.data_path
                    if path.startswith(bone_prefix):
                        suffix = next((s for s in suffixes if path.endswith(s)), None)
                        if suffix and self._matches_axis(fcu, suffix, base_idx, quat_idx, axisangle_idx):
                            target_fcurves.append(fcu)

        # Remove duplicates while preserving order
        target_fcurves = list(dict.fromkeys(target_fcurves))

        if not target_fcurves:
            self.report({"INFO"}, "No matching F-Curve channels found for selected elements")
            return {"CANCELLED"}

        found_editor = False

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type not in valid:
                    continue

                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if not region:
                    continue

                space = next((s for s in area.spaces if s.type == area.type), area.spaces.active)

                found_editor = True
                override = context.copy()
                override.update(
                    {
                        "window": window,
                        "screen": window.screen,
                        "area": area,
                        "region": region,
                        "space_data": space,
                    }
                )

                with context.temp_override(**override):
                    # Clear selection only if not adding selection and not toggling visibility
                    if not self._add and not self._toggle:
                        try:
                            bpy.ops.anim.channels_select_all(action="DESELECT")
                        except RuntimeError:
                            pass

                    # Apply operations to all target F-curves
                    for fcu in target_fcurves:
                        # Toggle visibility if ctrl pressed
                        if self._toggle:
                            fcu.hide = not fcu.hide
                            if fcu.group:
                                fcu.group.show_expanded = True

                        # Ensure visible before selecting
                        if area.type == "GRAPH_EDITOR" and getattr(fcu, "hide", False):
                            fcu.hide = False
                            if fcu.group:
                                fcu.group.show_expanded = True

                        # Select the channel
                        if not self._toggle:
                            fcu.select = True

                    # Expand groups for selected F-curves if preference is enabled
                    prefs = bpy.context.preferences.addons[base_package].preferences
                    if prefs.expand_curve_groups:
                        try:
                            bpy.ops.anim.channels_expand()
                        except RuntimeError:
                            pass  # Operator not available in current context

                    try:
                        utils.refresh_ui(bpy.context)
                    except Exception:
                        pass

        if not found_editor:
            self.report({"WARNING"}, "No Graph, Dope Sheet or Timeline editors open")
            return {"CANCELLED"}

        return {"FINISHED"}

    def _matches_axis(self, fcu, suffix, base_idx, quat_idx, axisangle_idx):
        """Check if the F-curve matches the selected axis."""
        if suffix == "rotation_quaternion":
            idx = quat_idx[self.axis]
        elif suffix == "rotation_axis_angle":
            idx = axisangle_idx[self.axis]
        else:
            idx = base_idx[self.axis]

        return fcu.array_index == idx


class AMP_OT_SetPreviewRange(bpy.types.Operator):
    """Set or clear the timeline's preview range based on current settings"""

    bl_idname = "anim.set_preview_range_key"
    bl_label = "Set or Clear Preview Range"
    bl_options = {"REGISTER", "UNDO"}

    def delete_markers(self, context):
        markers = bpy.context.scene.timeline_markers
        for marker in markers:
            if marker.name == "preview_range":
                markers.remove(marker)
                break

    def execute(self, context):
        scene = bpy.context.scene
        prefs = bpy.context.preferences.addons[base_package].preferences

        # Use the custom property for the operation started flag
        if scene.use_preview_range:
            scene.use_preview_range = False
            prefs.preview_range_set_scrub = False
            self.report({"INFO"}, "Timeline Preview range cleared")

        elif not scene.use_preview_range and not prefs.preview_range_set_scrub:
            prefs.preview_start_frame = scene.frame_current
            bpy.context.scene.timeline_markers.new(name="preview_range", frame=bpy.context.scene.frame_current)
            prefs.preview_range_set_scrub = True
            self.report({"INFO"}, f"Timeline Preview start set to frame {scene.frame_current}")

        elif not scene.use_preview_range and prefs.preview_range_set_scrub:
            scene.use_preview_range = True
            self.delete_markers(context)
            if scene.frame_current < prefs.preview_start_frame:
                scene.frame_preview_end = prefs.preview_start_frame
                scene.frame_preview_start = scene.frame_current
            else:
                scene.frame_preview_end = scene.frame_current
                scene.frame_preview_start = prefs.preview_start_frame
            self.report(
                {"INFO"},
                f"Timeline Preview range set from frame {scene.frame_preview_start} to frame {scene.frame_preview_end}",
            )
            prefs.preview_range_set_scrub = False

        utils.refresh_ui(context)

        return {"FINISHED"}


# class AMP_OT_select_keyframes_incurrent_frame(bpy.types.Operator):
#     bl_idname = "anim.amp_select_keyframes_in_current_frame"
#     bl_label = "Select Keyframes in Current Frame"
#     bl_description = "Select all keyframes in the current frame in the Graph Editor"
#     bl_options = {"REGISTER", "UNDO"}

#     def execute(self, context):
#         obj = context.active_object
#         if obj is None:
#             return {"CANCELLED"}

#         # Check if object has animation data before proceeding
#         if not obj.animation_data or not obj.animation_data.action:
#             return {"CANCELLED"}

#         frame = context.scene.frame_current

#         try:
#             utils.curve.select_keyframe_in_editors(context)
#         except (RuntimeError, TypeError):
#             # Failed to select keyframes, likely no proper animation context
#             pass

#         return {"FINISHED"}


class AMP_OT_frame_action_range(bpy.types.Operator):
    """Frame all in the current editor and optionally set the scene frame range to the action's range"""

    bl_idname = "anim.amp_timeline_tools_frame_action_range"
    bl_label = "Frame Action Range"
    bl_options = {"REGISTER", "UNDO"}

    scene_range_to_action: bpy.props.BoolProperty(
        name="Set Scene Range to Action",
        description="Set the scene's start and end frame to match the active action's range",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.space_data is not None

    def execute(self, context):
        area_type = context.area.type

        # Frame all based on the current context (Graph Editor, NLA Editor, or Dope Sheet/Timeline)
        if area_type == "GRAPH_EDITOR":
            bpy.ops.graph.view_all()
        elif area_type == "NLA_EDITOR":
            bpy.ops.nla.view_all()
        elif area_type == "DOPESHEET_EDITOR":
            bpy.ops.action.view_all()
        else:
            self.report({"WARNING"}, "Active editor does not support framing.")
            return {"CANCELLED"}

        # Optionally set the scene frame range to match the active action's range
        if self.scene_range_to_action:
            # Get the active action
            action = (
                context.active_object.animation_data.action
                if (context.active_object and context.active_object.animation_data)
                else None
            )
            if action:
                if action.use_frame_range:
                    # Use the action's predefined frame range
                    min_frame, max_frame = action.frame_range
                    context.scene.frame_start = int(min_frame)
                    context.scene.frame_end = int(max_frame)
                else:
                    # Compute min and max frame from keyframes
                    min_frame, max_frame = float("inf"), -float("inf")
                    for fcurve in utils.curve.all_fcurves(action):
                        for keyframe in fcurve.keyframe_points:
                            min_frame = min(min_frame, keyframe.co.x)
                            max_frame = max(max_frame, keyframe.co.x)
                    if min_frame != float("inf") and max_frame != -float("inf"):
                        context.scene.frame_start = int(min_frame)
                        context.scene.frame_end = int(max_frame)
                    else:
                        self.report({"WARNING"}, "Active action has no keyframes.")
            else:
                self.report({"WARNING"}, "No active action found.")

        return {"FINISHED"}


class AMP_OT_quick_animoffset_mask(bpy.types.Operator):
    bl_idname = "anim.amp_timeline_tools_quick_animoffset_mask"
    bl_label = "Quick AnimOffset Mask"
    bl_description = "Quickly create a mask for the AnimOffset add-on duting scrubbing"
    message = "Quick AnimOffset Mask"

    def settup_anim_offset_with_mask(self, context, min_frame, max_frame, blend_range=0):
        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            utils.amp_draw_header_handler(action="REMOVE")
            anim_offset.user_scene_auto = scene.tool_settings.use_keyframe_insert_auto
            support.store_user_timeline_ranges(context)
            bpy.app.handlers.depsgraph_update_post.append(support.magnet_handlers)
            # utils.set_bar_color()
            utils.add_message(self.message)

        # Set the scene's frame range to the selected keyframes range
        scene.frame_start, scene.frame_end = min_frame, max_frame
        scene.frame_current = int((min_frame + max_frame) / 2)

        # Activate and set the preview range to the same as the selected keyframes range
        scene.use_preview_range = True
        scene.frame_preview_start, scene.frame_preview_end = (
            min_frame - blend_range,
            max_frame + blend_range,
        )

        scene.tool_settings.use_keyframe_insert_auto = False

        support.add_blends()
        support.set_blend_values(context)
        support.update_blend_range(self, context)
        anim_offset.mask_in_use = True

    def execute(self, context):
        obj = context.active_object
        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset
        # if (obj is not None and obj.type != "ARMATURE") or (
        #     obj.type == "ARMATURE" and context.selected_pose_bones != []
        # ):
        target_frame = int(utils.curve.find_closest_keyframe_to_playhead(context))
        context.scene.frame_current = target_frame
        min_frame = target_frame - anim_offset.ao_mask_range
        max_frame = target_frame + anim_offset.ao_mask_range
        utils.curve.select_keyframe_in_editors(context)

        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            utils.amp_draw_header_handler(action="ADD")
            blend_range = anim_offset.ao_blend_range
            bpy.ops.anim.amp_activate_anim_offset()
            self.settup_anim_offset_with_mask(context, min_frame, max_frame, blend_range)
            context.window.cursor_modal_set("NONE")
        else:
            # context.window.cursor_modal_set("DEFAULT")
            bpy.ops.anim.amp_deactivate_anim_offset()
        # support.update_blend_range(self, context)
        # else:
        #     self.report({"WARNING"}, "No armature with selected bones active.")
        return {"FINISHED"}


def isolate_fcurve(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    editor = getattr(bpy.ops, "graph") if context.area.type == "GRAPH_EDITOR" else getattr(bpy.ops, "action")
    selected_keyframes = False

    space = next(
        (area.spaces.active for area in context.screen.areas if area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}), None
    )
    if not space:
        self.report({"ERROR"}, "No suitable editor found.")
        return {"CANCELLED"}

    dopesheet = getattr(space, "dopesheet", None)

    if not dopesheet:
        self.report({"ERROR"}, "Dopesheet not found in the active editor.")
        return {"CANCELLED"}

    selected_frame_range = utils.curve.get_selected_keyframes_range(context)

    if selected_frame_range is None and not prefs.solo_fcurve:
        self.report({"WARNING"}, "No keyframes selected.")
        return {"CANCELLED"}

    for fcurve in context.selected_visible_fcurves:
        if any(
            keyframe.select_control_point or keyframe.select_left_handle or keyframe.select_right_handle
            for keyframe in fcurve.keyframe_points
        ):
            selected_keyframes = True

    if prefs.solo_fcurve:
        dopesheet.filter_text = ""

        if context.area.type == "GRAPH_EDITOR":
            try:
                bpy.ops.graph.reveal()
            except RuntimeError:
                # Failed to reveal, likely no F-curves to reveal
                pass
            prefs.solo_fcurve = False
            selected_keyframes = False

    elif selected_keyframes:
        for fcurve in context.selected_visible_fcurves:
            fcurve.select = False
            if any(
                keyframe.select_control_point or keyframe.select_left_handle or keyframe.select_right_handle
                for keyframe in fcurve.keyframe_points
            ):
                fcurve.select = True
                selected_keyframes = True

        editor.hide(unselected=True)
        prefs.solo_fcurve = True

        if len(context.selected_visible_fcurves) == 1:
            fcurve = context.selected_visible_fcurves[0]
            data_path = fcurve.data_path
            bone_or_object_name = None

            match = re.search(r'pose\.bones\["([^"]+)"\]', data_path)
            if match:
                bone_or_object_name = match.group(1)
            else:
                match = re.search(r'objects\["([^"]+)"\]', data_path)
                if match:
                    bone_or_object_name = match.group(1)

            if bone_or_object_name:
                dopesheet.filter_text = bone_or_object_name

    return {"FINISHED"}


class AMP_OT_isolate_selected_fcurves(bpy.types.Operator):
    bl_idname = "anim.amp_isolate_selected_fcurves"
    bl_label = "Toggle Isolate Selected F-Curves"
    bl_description = """Toggle isolation of F-Curves with selected keyframes
Press again to restore visibility and selection state of F-Curves
Default shortcut W"""

    # solo_fcurve = False

    @classmethod
    def poll(cls, context):
        return context.area.type in {"GRAPH_EDITOR"}

    def execute(self, context):
        isolate_fcurve(self, context)

        return {"FINISHED"}


class ANIM_OT_share_keyframes(bpy.types.Operator):
    bl_idname = "anim.amp_share_keyframes"
    bl_label = "Share Keyframes"
    bl_description = "Efficiently insert keyframes on frames where any selected objects or bones have keyframes, for all selected elements with animation data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mode = context.mode
        frames_set = set()
        elements = []

        if mode == "OBJECT":
            selected_objects = context.selected_objects
            for obj in selected_objects:
                if obj.animation_data and obj.animation_data.action:
                    action = obj.animation_data.action
                    for fcurve in utils.curve.all_fcurves(action):
                        frames_set.update(int(round(kp.co.x)) for kp in fcurve.keyframe_points)
                    elements.append(obj)
                elif obj.animation_data:
                    elements.append(obj)

        elif mode == "POSE":
            obj = context.active_object
            if obj.type != "ARMATURE":
                self.report({"ERROR"}, "Active object is not an armature")
                return {"CANCELLED"}

            selected_bones = context.selected_pose_bones
            action = obj.animation_data.action if obj.animation_data else None
            if action:
                for bone in selected_bones:
                    bone_fcurves = [
                        fc
                        for fc in utils.curve.all_fcurves(action)
                        if fc.data_path.startswith(f'pose.bones["{bone.name}"]')
                    ]
                    for fcurve in bone_fcurves:
                        frames_set.update(int(round(kp.co.x)) for kp in fcurve.keyframe_points)
                    elements.append(bone)
            else:

                pass
        else:
            self.report({"ERROR"}, "Mode not supported")
            return {"CANCELLED"}

        if not frames_set:
            self.report({"INFO"}, "No keyframes found among selected elements")
            return {"CANCELLED"}

        frames_list = sorted(frames_set)

        if mode == "OBJECT":
            for obj in elements:
                if not obj.animation_data or not obj.animation_data.action:
                    continue

                action = obj.animation_data.action

                fcurves = utils.curve.all_fcurves(action)
                data_paths = {}
                for fcurve in fcurves:
                    data_paths.setdefault((fcurve.data_path, fcurve.array_index), []).append(fcurve)

                for frame in frames_list:
                    for (data_path, array_index), fc_list in data_paths.items():
                        for fcurve in fc_list:
                            if not any(int(round(kp.co.x)) == frame for kp in fcurve.keyframe_points):
                                value = fcurve.evaluate(frame)
                                new_kp = fcurve.keyframe_points.insert(frame, value, options={"FAST"})
                                # new_kp.interpolation = "BEZIER"
                                new_kp.handle_left_type = "AUTO_CLAMPED"
                                new_kp.handle_right_type = "AUTO_CLAMPED"
                                fcurve.update()

        elif mode == "POSE":
            obj = context.active_object
            action = obj.animation_data.action

            for bone in elements:
                bone_fcurves = [
                    fc
                    for fc in utils.curve.all_fcurves(action)
                    if fc.data_path.startswith(f'pose.bones["{bone.name}"]')
                ]

                data_paths = {}
                for fcurve in bone_fcurves:
                    data_paths.setdefault((fcurve.data_path, fcurve.array_index), []).append(fcurve)

                for frame in frames_list:
                    for (data_path, array_index), fc_list in data_paths.items():
                        for fcurve in fc_list:
                            if not any(int(round(kp.co.x)) == frame for kp in fcurve.keyframe_points):
                                pattern = rf'^pose\.bones\["{re.escape(bone.name)}"\]\.(.+)$'
                                match = re.match(pattern, data_path)
                                if match:
                                    bone_data_path = match.group(1)
                                    value = fcurve.evaluate(frame)
                                    new_kp = fcurve.keyframe_points.insert(frame, value, options={"FAST"})
                                    # new_kp.interpolation = "BEZIER"
                                    new_kp.handle_left_type = "AUTO_CLAMPED"
                                    new_kp.handle_right_type = "AUTO_CLAMPED"
                                    fcurve.update()
                                else:
                                    self.report({"WARNING"}, f"Unrecognized data_path format: {data_path}")

        self.report({"INFO"}, f"{len(frames_list)} shared frames")
        return {"FINISHED"}


def AnimViewButtons(layout, context):
    row = layout.row(align=True)
    AnimCurvesSoloButton(
        row,
        text="",
    )
    AnimCurvesFrameSelectedButton(
        row,
        text="",
    )
    AnimCurvesFrameRange(
        row,
        text="",
    )


def AnimCurvesButtons(layout, context):
    row = layout.row(align=True)

    AnimCurvesAllButton(
        row,
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_select_curves_all"),
    )
    AnimCurvesLocButton(
        row,
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_select_curves_loc"),
    )
    AnimCurvesRotButton(
        row,
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_select_curves_rot"),
    )
    AnimCurvesScaleButton(
        row,
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_select_curves_scale"),
    )
    AnimCurvesOthersButton(
        row,
        text="CUSTOMPROPS",
        icon_value=utils.customIcons.get_icon_id("AMP_select_curves_others"),
    )
    AnimCurvesShapesButton(
        row,
        text="Shapes",
        **utils.customIcons.get_icon("AMP_select_curves_others"),
    )
    AnimCurvesConstraintsButton(
        row,
        text="Constraints",
        **utils.customIcons.get_icon("AMP_select_curves_others"),
    )

    AnimHandlesButtons(row, context)

    # popover with the animcurvespropertiespopover


def AnimCurvesLocButton(layout, text="Loc", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "TRANSLATION"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesRotButton(layout, text="Rot", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "ROTATION"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesScaleButton(layout, text="Scale", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "SCALE"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesShapesButton(layout, text="Shapes", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "SHAPES"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesConstraintsButton(layout, text="Constraints", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "CONST"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesOthersButton(layout, text="CUSTOMPROPS", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "CUSTOMPROPS"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesAllButton(layout, text="All", icon_value=1):
    op = layout.operator(
        "anim.amp_toggle_fcurves_selection",
        text=text,
        icon_value=icon_value,
    )
    op.action_type = "ALL"
    op.extra_options = "DESELECT_ALL"
    op.isolate = "ISOLATE"
    op.transform_if_selected = False


def AnimCurvesFrameSelectedButton(layout, text="Frame"):
    has_selected_keyframes = True if bpy.context.selected_editable_keyframes else False
    layout.operator(
        "anim.amp_zoom_frame_editors",
        text=text,
        icon_value=(
            utils.customIcons.get_icon_id("AMP_zoom_curve_selected")
            if has_selected_keyframes
            else utils.customIcons.get_icon_id("AMP_zoom_curve_all")
        ),
    )


def AnimCurvesSoloButton(layout, text="Solo"):
    context = bpy.context
    prefs = context.preferences.addons[base_package].preferences
    row_solo = layout.row(align=True)
    has_selected_keyframes = True if bpy.context.selected_editable_keyframes else False
    is_solo = True if prefs.solo_fcurve else False
    row_solo.active = has_selected_keyframes or is_solo
    icon_value = (
        utils.customIcons.get_icon_id("AMP_solo_curve_on")
        if is_solo
        else utils.customIcons.get_icon_id("AMP_solo_curve_off")
    )
    row_solo.operator(
        "anim.amp_isolate_selected_fcurves",
        text="",
        icon_value=icon_value,
        depress=False,
    )


def AnimCurvesFrameRange(layout, text="Frame Range"):
    layout.operator(
        "anim.amp_timeline_tools_frame_action_range",
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_frame_action"),
    ).scene_range_to_action = True


def AnimHandlesButtons(layout, context):
    if context.area.type == "GRAPH_EDITOR":
        if context.space_data.show_handles:
            show_handles_icon = utils.customIcons.get_icon_id("AMP_handles_off")
        elif not context.space_data.show_handles:
            show_handles_icon = utils.customIcons.get_icon_id("AMP_handles_on")
        layout.prop(
            context.space_data,
            "show_handles",
            text="",
            icon_value=show_handles_icon,
            toggle=True,
        )

        sub_row = layout.row(align=True)
        sub_row.active = context.space_data.show_handles
        if context.space_data.use_only_selected_keyframe_handles:
            only_sel_handles_icon = utils.customIcons.get_icon_id("AMP_handles_all")
        elif not context.space_data.use_only_selected_keyframe_handles:
            only_sel_handles_icon = utils.customIcons.get_icon_id("AMP_handles_selected")
        sub_row.prop(
            context.space_data,
            "use_only_selected_keyframe_handles",
            text="",
            icon_value=only_sel_handles_icon,
            toggle=True,
            invert_checkbox=True,
        )


class AMP_OT_toggle_curve_show_handles(bpy.types.Operator):
    bl_idname = "anim.amp_toggle_curve_handles"
    bl_label = "Show Keyframe Handles"
    bl_description = "Show or hide keyframe handles in the Graph Editor"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context.area.type == "GRAPH_EDITOR"

    def execute(self, context):
        context.space_data.show_handles = not context.space_data.show_handles
        return {"FINISHED"}


class AMP_OT_toggle_curve_show_only_selected_handles(bpy.types.Operator):
    bl_idname = "anim.amp_oggle_curve_show_only_selected_handles"
    bl_label = "Only Selected Keyframe Handles"
    bl_description = "Display curve handles only for selected keyframes in the Graph Editor"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context.area.type == "GRAPH_EDITOR"

    def execute(self, context):
        context.space_data.use_only_selected_keyframe_handles = (
            not context.space_data.use_only_selected_keyframe_handles
        )
        return {"FINISHED"}


# * Toggle properties ---------------------------------------------------------


class AMP_PT_anim_curves_properties(bpy.types.Panel):
    bl_label = "Anim Curves Properties"
    bl_idname = "AMP_PT_anim_curves_properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    # bl_category = "AMP"
    bl_context = ""
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        space = context.space_data
        prefs = context.preferences.addons[base_package].preferences
        column = layout.column()

        column.label(text="Toggles when isolating F-Curves")

        row = column.row()
        row.active = not prefs.smart_zoom
        row.prop(prefs, "zoom_to_visible_curve", text="", icon="FULLSCREEN_ENTER")
        row.label(text="Zoom to whole visible F-Curves")

        row = column.row()
        row.prop(prefs, "smart_zoom", text="", icon="FULLSCREEN_ENTER")
        row.label(text="Smart zoom to frame range")
        sub_row = row.row()
        sub_row.scale_x = 0.65
        sub_row.prop(prefs, "frame_range_smart_zoom", text="")

        row = column.row()
        row.prop(prefs, "cycle_fcurves", text="", icon="RECOVER_LAST")
        row.label(text="Cycle F-Curves")

        row = column.row()
        row.prop(
            prefs,
            "isolate_fcurves",
            text="",
            icon="HIDE_OFF" if prefs.isolate_fcurves else "HIDE_ON",
        )
        row.label(text="Isolate F-Curves")

        row = column.row()
        row.prop(
            prefs, "expand_curve_groups", text="", icon="DOWNARROW_HLT" if prefs.expand_curve_groups else "RIGHTARROW"
        )

        row.label(text="Expand Curve Groups")

        column.separator()

        column.label(text="Graph/Dope Editor Tweaks")
        row = column.row()

        if bpy.app.version < (4, 2):
            if context.area.type == "GRAPH_EDITOR":
                row.prop(
                    space,
                    "autolock_translation_axis",
                    text="",
                    icon="ORIENTATION_VIEW" if space.autolock_translation_axis else "UNLOCKED",
                    emboss=True,
                )

                row.label(text="Auto-Lock Key Axis")
        else:
            if context.area.type == "GRAPH_EDITOR":
                row.prop(
                    space,
                    "use_auto_lock_translation_axis",
                    text="",
                    icon="ORIENTATION_VIEW" if space.use_auto_lock_translation_axis else "UNLOCKED",
                    emboss=True,
                )

            row.label(text="Auto-Lock Key Axis")

        row = column.row()
        jump_icon = "KEYFRAME_HLT" if prefs.graph_editor_jump_to_keyframe_kmi_active else "KEYFRAME"
        row.prop(
            prefs,
            "graph_editor_jump_to_keyframe_kmi_active",
            text="",
            icon=jump_icon,
            emboss=True,
        )

        row.label(text="Move Playhead to Keyframe")

        row = column.row()
        jumpG = "EVENT_G"
        row.prop(
            prefs,
            "graph_editor_jump_to_keyframe_ctrl_g_kmi_active",
            text="",
            icon=jumpG,
            emboss=True,
        )

        row.label(text="Move to first selected keyframe")

        column.separator()

        column.label(text="Scrubber Tweaks")

        row = column.row()
        row.prop(prefs, "select_keyframes_on_current_frame", text="", icon="KEYTYPE_KEYFRAME_VEC")
        row.label(text="Select Keyframes on Current Frame")


def AnimCurvesZoomToSelectedButton(layout, text="Zoom"):
    prefs = bpy.context.preferences.addons[base_package].preferences

    layout.prop(
        prefs,
        "zoom_to_visible_curve",
        text=text,
        icon="NORMALIZE_FCURVES",  # if prefs.zoom_to_visible_curve else "ZOOM_OUT",
        # emboss=False,
    )


def AnimCurvesCollapseButton(layout, text="Collapse"):
    prefs = bpy.context.preferences.addons[base_package].preferences

    layout.prop(
        prefs,
        "expand_curve_groups",
        text=text,
        icon="DOWNARROW_HLT" if prefs.expand_curve_groups else "RIGHTARROW",
        # emboss=False,
    )


def AnimCycleButton(layout, text="Cycle"):
    prefs = bpy.context.preferences.addons[base_package].preferences

    layout.prop(
        prefs,
        "cycle_fcurves",
        text=text,
        icon="RECOVER_LAST",
        # emboss=False,
    )


def AnimIsolateButton(layout, text="Isolate"):
    prefs = bpy.context.preferences.addons[base_package].preferences

    layout.prop(
        prefs,
        "isolate_fcurves",
        text=text,
        icon="RESTRICT_VIEW_ON",
        # emboss=False,
    )


class AMP_OT_FrameEditors(bpy.types.Operator):
    bl_idname = "anim.amp_zoom_frame_editors"
    bl_label = "Frame sel/all Keyframes"
    bl_description = """Alternate between frame all and frame selected keyframes"""

    ignore_selected: bpy.props.BoolProperty(
        name="Ignore Selected",
        description="Frame all keyframes instead of selected keyframes",
        default=False,
    )

    def execute(self, context):
        has_selected_keyframes = True if bpy.context.selected_editable_keyframes else False

        # Find all target areas of type GRAPH_EDITOR or DOPESHEET_EDITOR,
        # but skip Dope Sheet areas that are in Timeline mode to avoid switching the Timeline.
        target_areas = []
        for area in context.screen.areas:
            if area.type == "GRAPH_EDITOR":
                target_areas.append(area)
            elif area.type == "DOPESHEET_EDITOR":
                space = area.spaces.active
                # In some Blender versions Timeline is a mode of the Dope Sheet, skip it.
                mode = getattr(space, "mode", None)
                ui_mode = getattr(space, "ui_mode", None)
                if mode == "TIMELINE" or ui_mode == "TIMELINE":
                    continue
                target_areas.append(area)

        if not target_areas:
            self.report({"WARNING"}, "No GRAPH_EDITOR or DOPESHEET_EDITOR areas found.")
            return {"CANCELLED"}

        for area in target_areas:
            window = context.window
            override = context.copy()
            override["window"] = window
            override["screen"] = context.screen
            override["area"] = area
            region = next((reg for reg in area.regions if reg.type == "WINDOW"), None)
            if region is None:
                continue
            override["region"] = region

            with context.temp_override(**override):
                if area.type == "GRAPH_EDITOR":
                    editor = bpy.ops.graph
                else:
                    editor = bpy.ops.action
                if has_selected_keyframes and not self.ignore_selected:
                    editor.view_selected()
                else:
                    editor.view_all()

        return {"FINISHED"}


class AMP_OT_SmartZoom(bpy.types.Operator):
    bl_idname = "anim.amp_smart_zoom_frame_editors"
    bl_label = "Smart Zoom"
    bl_description = "Smart zoom in animation editors"

    frame_range_smart_zoom: bpy.props.IntProperty(
        name="Frame Range", description="Frame range to zoom in on either side of the current frame", default=0, min=0
    )

    horizontal_padding: bpy.props.IntProperty(
        name="Horizontal Padding",
        description="Extra frames to add on each side",
        default=1,
        min=0,
    )

    vertical_padding: bpy.props.IntProperty(
        name="Vertical Padding",
        description="Extra pixels to add above and below the value range",
        default=50,
        min=0,
    )

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}

    def execute(self, context):
        prefs = context.preferences.addons[base_package].preferences
        frame_range = self.frame_range_smart_zoom if self.frame_range_smart_zoom > 0 else prefs.frame_range_smart_zoom

        current_frame = context.scene.frame_current

        # Adjust frame start and end by including horizontal padding
        frame_start = current_frame - frame_range - self.horizontal_padding
        frame_end = current_frame + frame_range + self.horizontal_padding

        area = context.area
        region = next((reg for reg in area.regions if reg.type == "WINDOW"), None)

        if not region:
            self.report({"WARNING"}, "Couldn't find the region")
            return {"CANCELLED"}

        if area.type == "GRAPH_EDITOR":
            bpy.ops.graph.view_all()
            self.smart_zoom_graph_editor(context, frame_start, frame_end, area, region)
        elif area.type == "DOPESHEET_EDITOR":
            self.smart_zoom_dopesheet(context, frame_start, frame_end, area, region)
        else:
            self.report({"WARNING"}, "Area type not supported")
            return {"CANCELLED"}

        return {"FINISHED"}

    def smart_zoom_graph_editor(self, context, frame_start, frame_end, area, region):
        space = area.spaces.active
        if not isinstance(space, bpy.types.SpaceGraphEditor):
            return

        # Collect F-Curves visible in the Graph Editor
        fcurves = context.visible_fcurves

        if not fcurves:
            self.report({"INFO"}, "No visible F-Curves found for zooming")
            return

        # Initialize min and max values
        value_min = None
        value_max = None

        # Cache the rotation status of each fcurve to reduce redundant calls
        rotation_fcurves = {fcurve: is_fcurve_in_radians(fcurve) for fcurve in fcurves}

        # Collect unique frame samples to minimize redundant evaluations
        frame_samples = [frame_start, context.scene.frame_current, frame_end]

        for fcurve in fcurves:
            is_rotation_fcurve = rotation_fcurves[fcurve]
            keyframe_points = fcurve.keyframe_points

            # Process keyframe points within the frame range
            for kp in keyframe_points:
                x = kp.co.x
                if frame_start <= x <= frame_end:
                    value = kp.co.y
                    if is_rotation_fcurve:
                        value = math.degrees(value)

                    # Update min and max
                    if value_min is None or value < value_min:
                        value_min = value
                    if value_max is None or value > value_max:
                        value_max = value

            # Evaluate fcurve at frame_samples
            for frame in frame_samples:
                value = fcurve.evaluate(frame)
                if is_rotation_fcurve:
                    value = math.degrees(value)

                # Update min and max
                if value_min is None or value < value_min:
                    value_min = value
                if value_max is None or value > value_max:
                    value_max = value

        # Handle case where no values were found
        if value_min is None or value_max is None:
            value_min, value_max = -1, 1

        # Ensure value_min != value_max to prevent zero range
        if value_min == value_max:
            value_min -= 0.5
            value_max += 0.5

        # Access the view2d data
        v2d = region.view2d

        if space.use_normalization:
            # **Normalization is ON**

            # Define a standard Y-range when normalized
            normalized_min, normalized_max = -1, 1

            # Convert normalized Y-values to pixel coordinates
            _, ymin_px = v2d.view_to_region(0, normalized_min, clip=False)
            _, ymax_px = v2d.view_to_region(0, normalized_max, clip=False)

            # Apply **fixed** vertical padding in pixels
            ymin_px -= self.vertical_padding
            ymax_px += self.vertical_padding

            # Clamp to region bounds
            ymin_px = max(ymin_px, 0)
            ymax_px = min(ymax_px, region.height)

        else:
            # **Normalization is OFF**

            # Calculate Y-range and apply **dynamic** proportional padding
            y_range = value_max - value_min
            padding_percentage = 0.1  # 10% padding
            padding_value = y_range * padding_percentage

            value_min_padded = value_min - padding_value
            value_max_padded = value_max + padding_value

            # Convert padded Y-values to pixel coordinates
            _, ymin_px = v2d.view_to_region(0, value_min_padded, clip=False)
            _, ymax_px = v2d.view_to_region(0, value_max_padded, clip=False)

            # Ensure sorted order
            ymin_px, ymax_px = sorted((ymin_px, ymax_px))

        # Convert frame range to pixel coordinates
        xmin_px, _ = v2d.view_to_region(frame_start, 0, clip=False)
        xmax_px, _ = v2d.view_to_region(frame_end, 0, clip=False)

        # Ensure xmin <= xmax
        xmin_px, xmax_px = sorted((xmin_px, xmax_px))

        # Create an override context
        override = context.copy()
        override["area"] = area
        override["region"] = region
        override["window"] = context.window
        override["screen"] = context.screen
        override["space_data"] = space

        # Use the zoom border operator with the correct coordinates
        with bpy.context.temp_override(**override):
            bpy.ops.view2d.zoom_border(
                "EXEC_REGION_WIN",
                xmin=int(xmin_px),
                xmax=int(xmax_px),
                ymin=int(ymin_px),
                ymax=int(ymax_px),
            )

    def smart_zoom_dopesheet(self, context, frame_start, frame_end, area, region):
        v2d = region.view2d

        # Get the current vertical bounds in view coordinates
        v_bottom = v2d.region_to_view(0, 0)[1]
        v_top = v2d.region_to_view(0, region.height)[1]

        # Convert desired view coordinates to region coordinates (pixels)
        xmin_px, _ = v2d.view_to_region(frame_start, v_bottom, clip=False)
        xmax_px, _ = v2d.view_to_region(frame_end, v_top, clip=False)
        _, ymin_px = v2d.view_to_region(frame_start, v_bottom, clip=False)
        _, ymax_px = v2d.view_to_region(frame_start, v_top, clip=False)

        # Ensure xmin <= xmax and ymin <= ymax
        xmin_px, xmax_px = sorted((xmin_px, xmax_px))
        ymin_px, ymax_px = sorted((ymin_px, ymax_px))

        # Apply vertical padding in pixels
        vertical_padding_px = self.vertical_padding

        ymin_px -= vertical_padding_px
        ymax_px += vertical_padding_px

        # Clamp ymin_px and ymax_px to region bounds
        ymin_px = max(ymin_px, 0)
        ymax_px = min(ymax_px, region.height)

        # Create an override context
        override = context.copy()
        override["area"] = area
        override["region"] = region
        override["window"] = context.window
        override["screen"] = context.screen
        override["space_data"] = area.spaces.active

        # Use the zoom border operator with the correct enum
        with bpy.context.temp_override(**override):
            bpy.ops.view2d.zoom_border(
                "EXEC_REGION_WIN",
                xmin=int(xmin_px),
                xmax=int(xmax_px),
                ymin=int(ymin_px),
                ymax=int(ymax_px),
            )


# class AMP_OT_FrameEditors(bpy.types.Operator):
#     bl_idname = "anim.amp_zoom_frame_editors"
#     bl_label = "Frame sel/all Keyframes"
#     bl_description = """Alternate between frame all and frame selected keyframes"""

#     def execute(self, context):
#         if context.area.type == "GRAPH_EDITOR":
#             self.zoom_in_graph_editor(context)
#         elif context.area.type == "DOPESHEET_EDITOR":
#             self.zoom_in_dopesheet_editor(context)
#         else:
#             self.report({"WARNING"}, "Active editor does not support framing.")
#             return {"CANCELLED"}
#         return {"FINISHED"}

#     def zoom_in_graph_editor(self, context):
#         props = bpy.context.scene.timeline_scrub_settings

#         if props.frame_last_action:
#             bpy.ops.graph.view_selected()
#             props.frame_last_action = False

#         elif not props.frame_last_action:
#             bpy.ops.graph.view_all()
#             props.frame_last_action = True

#     def zoom_in_dopesheet_editor(self, context):
#         props = bpy.context.scene.timeline_scrub_settings

#         if props.frame_last_action:
#             bpy.ops.action.view_selected()
#             props.frame_last_action = False

#         elif not props.frame_last_action:

#             bpy.ops.action.view_all()
#             props.frame_last_action = True


# * Individual operators for toggling visibility of fcurves


class AMP_OT_view_anim_curves_all(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_all"
    bl_label = "View All Animation Curves"
    bl_description = "Toggle selection for all animation curves\nCTRL to Cyle\nALT to toggle selected"

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="ALL",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


class AMP_OT_view_anim_curves_loc(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_loc"
    bl_label = "Isolate Location Curves"
    bl_description = (
        "Toggle selection for location animation curves\nHold SHIFT to toggle all\nCTRL to Cyle\nALT to toggle selected"
    )

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="TRANSLATION",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


class AMP_OT_view_anim_curves_rot(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_rot"
    bl_label = "Isolate Rotation Curves"
    bl_description = (
        "Toggle selection for rotation animation curves\nHold SHIFT to toggle all\nCTRL to Cyle\nALT to toggle selected"
    )

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="ROTATION",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


class AMP_OT_view_anim_curves_scale(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_scale"
    bl_label = "IsoView Scale Curves"
    bl_description = (
        "Toggle selection for scale animation curves\nHold SHIFT to toggle all\nCTRL to Cyle\nALT to toggle selected"
    )

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="SCALE",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


class AMP_OT_view_anim_curves_custom_props(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_custom_props"
    bl_label = "Isolate Curves for Custom Properties"
    bl_description = "Toggle selection for custom properties animation curves\nHold SHIFT to toggle all\nCTRL to Cyle\nALT to toggle selected"

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="CUSTOMPROPS",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


class AMP_OT_view_anim_curves_shapes(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_shapes"
    bl_label = "Isolate Curves for Shape Keys"
    bl_description = (
        "Toggle selection for shape animation curves\nHold SHIFT to toggle all\nCTRL to Cyle\nALT to toggle selected"
    )

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="SHAPES",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


class AMP_OT_view_anim_curves_constraints(bpy.types.Operator):
    bl_idname = "anim.view_anim_curves_constraints"
    bl_label = "Isolate Curves for Constraints"
    bl_description = (
        "Toggle selection for constraint animation curves\nSHIFT to toggle all\nCTRL to Cyle\nALT to toggle selected"
    )

    def invoke(self, context, event):
        prefs = utils.get_prefs()
        bpy.ops.anim.amp_toggle_fcurves_selection(
            action_type="CONST",
            extra_options="DESELECT_ALL",
            isolate="ISOLATE" if prefs.isolate_fcurves else "NONE",
            transform_if_selected=False,
            ctrl_pressed=event.ctrl,
            shift_pressed=event.shift,
            alt_pressed=event.alt,
            os_key=event.oskey,
        )
        return {"FINISHED"}


classes = (
    AMP_OT_select_fcurves,
    # AMP_OT_select_keyframes_incurrent_frame,
    AMP_OT_insert_keyframe,
    AMP_OT_MovePlayHeadToKeyframe,
    AMP_OT_SelectKeyframeAndMovePlayehad,
    AMP_OT_select_or_transform_keyframes,
    AMP_OT_JumpToKeyframe,
    AMP_OT_SetPreviewRange,
    AMP_OT_frame_action_range,
    AMP_OT_quick_animoffset_mask,
    AMP_OT_isolate_selected_fcurves,
    AMP_OT_cleanup_keyframes_from_locked_transforms,
    AMP_OT_FrameEditors,
    AMP_OT_SmartZoom,
    AMP_PT_anim_curves_properties,
    AMP_OT_toggle_curve_show_handles,
    AMP_OT_toggle_curve_show_only_selected_handles,
    AMP_OT_SetKeyframesValue,
    AMP_OT_view_anim_curves_all,
    AMP_OT_view_anim_curves_loc,
    AMP_OT_view_anim_curves_rot,
    AMP_OT_view_anim_curves_scale,
    AMP_OT_view_anim_curves_custom_props,
    AMP_OT_view_anim_curves_shapes,
    AMP_OT_view_anim_curves_constraints,
    ANIM_OT_share_keyframes,
    AMP_OT_SelectFCurveChannels,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
