from multiprocessing import context
import bpy
import time
from bpy.types import Panel, Operator
from bpy.props import EnumProperty

from .. import utils
from .anim_mopaths_ui import motion_path_options

from .. import __package__ as base_package

# Global variables to store state
_last_keyframe_data = None
_last_transform_data = None
_last_frame = None
_handlers_registered = False
_last_transform_operator = None
_last_active_object = None
_last_active_bone = None
_last_is_sculpting = False
_is_handler_running = False
_update_scheduled = False


def get_keyframe_data(context):
    """Retrieve data for all keyframes in the active action."""
    data = []
    action = None
    if context.object and context.object.animation_data:
        action = context.object.animation_data.action
    if not action:
        return data

    for fcu in utils.curve.all_fcurves(action):
        for kp in fcu.keyframe_points:
            data.append((fcu.data_path, kp.co[:], kp.handle_left[1], kp.handle_right[1]))

    return data


def get_transform_data(context):
    """Retrieve the location, rotation, and scale of the active object or pose bone."""
    data = []
    if context.mode == "POSE" and context.active_pose_bone:
        for bone in context.selected_pose_bones:
            loc = bone.location.copy()
            # Handle rotation based on rotation_mode
            if bone.rotation_mode in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}:
                rot = bone.rotation_euler.copy()
            else:
                rot = bone.rotation_quaternion.copy()
            scale = bone.scale.copy()
            data.append((loc, rot, scale))

    elif context.mode == "OBJECT" and context.active_object:
        for ob in context.selected_objects:
            loc = ob.location.copy()
            # Handle rotation based on rotation_mode
            if ob.rotation_mode in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}:
                rot = ob.rotation_euler.copy()
            else:
                rot = ob.rotation_quaternion.copy()
            scale = ob.scale.copy()
            data.append((loc, rot, scale))

    return data


def get_changed_properties(current_transform_data, last_transform_data):
    """
    Compare current and last transform data to determine which properties have changed.

    Args:
        current_transform_data (list): Current transform data.
        last_transform_data (list): Last transform data.

    Returns:
        set: A set containing the names of changed properties ('location', 'rotation', 'scale').
    """
    changed = set()
    for current, last in zip(current_transform_data, last_transform_data):
        loc_current, rot_current, scale_current = current
        loc_last, rot_last, scale_last = last

        if loc_current != loc_last:
            changed.add("location")
        if rot_current != rot_last:
            changed.add("rotation")
        if scale_current != scale_last:
            changed.add("scale")

    return changed


def insert_keyframes(context, properties):
    """
    Insert keyframes for the specified transform properties of the active object or selected pose bones,
    using only necessary keyframes and optionally applying cycle-aware keying.
    Only inserts keyframes if autokey is enabled and the user preference allows it.

    Args:
        context: Blender context.
        properties (set): Set of properties to key ('location', 'rotation', 'scale').

    Returns:
        bool: True if keyframes were inserted, False otherwise.
    """

    # Check if autokey is enabled and user wants to respect it
    autokey_enabled = context.scene.tool_settings.use_keyframe_insert_auto

    if not autokey_enabled:
        return False

    mode = context.mode

    if mode == "OBJECT":
        targets = context.selected_objects
        for target in targets:
            if not target.animation_data:
                target.animation_data_create()
            if not target.animation_data.action:
                target.animation_data.action = bpy.data.actions.new(name="Action")

    elif mode == "POSE":
        ob = context.active_object
        targets = context.selected_pose_bones
        if not ob.animation_data:
            ob.animation_data_create()
        if not ob.animation_data.action:
            ob.animation_data.action = bpy.data.actions.new(name="Action")
    else:
        return False

    props_to_key = []
    if "location" in properties:
        props_to_key.append("location")
    if "rotation" in properties:
        rotation_mode = getattr(targets[0], "rotation_mode", "")
        if rotation_mode.upper() in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}:
            props_to_key.append("rotation_euler")
        else:
            props_to_key.append("rotation_quaternion")
    if "scale" in properties:
        props_to_key.append("scale")

    options = {"INSERTKEY_NEEDED"}

    cycle_aware_enabled = getattr(context.scene.tool_settings, "use_keyframe_cycle_aware", False)
    if cycle_aware_enabled:
        options.add("INSERTKEY_CYCLE_AWARE")

    current_frame = context.scene.frame_current

    if mode == "OBJECT":
        for target in targets:
            for prop in props_to_key:
                try:
                    target.keyframe_insert(data_path=prop, frame=current_frame, options=options)
                except RuntimeError as e:
                    print(f"Warning: {e} for object '{target.name}' property '{prop}' at frame {current_frame}")
    elif mode == "POSE":
        ob = context.active_object
        for bone in targets:
            bone_name = bone.name
            for prop in props_to_key:
                data_path = f'pose.bones["{bone_name}"].{prop}'
                try:
                    ob.keyframe_insert(data_path=data_path, frame=current_frame, options=options)
                except RuntimeError as e:
                    print(f"Warning: {e} for bone '{bone_name}' property '{prop}' at frame {current_frame}")

    return True


def update_motion_paths(context):
    """Wrapper to handle exceptions during motion path calculation."""
    prefs = bpy.context.preferences.addons[base_package].preferences
    global _last_active_object, _last_active_bone

    if prefs.clear_previous:

        is_armature = context.active_object.type == "ARMATURE"

        if is_armature:
            if context.active_pose_bone != _last_active_bone:
                _last_active_bone = context.active_pose_bone
                try:
                    bpy.ops.object.paths_clear()
                    bpy.ops.pose.paths_clear()
                except Exception as e:
                    print(f"Error clearing paths for bone: {e}")

        elif context.active_object != _last_active_object:
            _last_active_object = context.active_object
            try:
                bpy.ops.object.paths_clear()
                bpy.ops.pose.paths_clear()
            except Exception as e:
                print(f"Error clearing paths for object: {e}")

        try:
            if is_armature:
                bpy.ops.pose.paths_calculate()
                # Apply settings after calculating
                apply_motion_path_settings_to_selected(context)
            else:
                bpy.ops.object.paths_calculate()
                # Apply settings after calculating
                apply_motion_path_settings_to_selected(context)
        except Exception as e:
            print(f"Error updating motion paths: {e}")

    else:
        try:
            bpy.ops.object.paths_update_visible()
            # Apply settings after updating
            apply_motion_path_settings_to_selected(context)
        except Exception as e:
            print(f"Error updating visible motion paths: {e}")


def perform_motion_path_update():
    global _update_scheduled
    context = bpy.context

    was_playing = context.screen.is_animation_playing

    if was_playing:

        try:
            bpy.ops.screen.animation_play()
        except RuntimeError as e:
            print(f"Error stopping animation playback: {e}")

    update_motion_paths(context)

    if was_playing:

        try:
            bpy.ops.screen.animation_play()
        except RuntimeError as e:
            print(f"Error resuming animation playback: {e}")

    _update_scheduled = False
    return None


def amp_realtime_motion_paths_handler(scene, depsgraph):
    global _is_handler_running, _update_scheduled
    global _last_keyframe_data, _last_transform_data, _last_frame, _last_transform_operator, _last_is_sculpting

    if _is_handler_running:
        return

    _is_handler_running = True
    try:
        prefs = bpy.context.preferences.addons[base_package].preferences
        settings_sculpt = getattr(scene, "keyframe_sculpt_settings", None)
        if not settings_sculpt:
            return

        context = bpy.context

        if prefs.realtime_mograph and not getattr(prefs, "is_scrubbing", False):
            if (context.mode == "OBJECT" and not context.active_object) or (
                context.mode == "POSE" and not context.active_pose_bone
            ):
                return

            current_keyframe_data = get_keyframe_data(context)
            current_transform_data = get_transform_data(context)
            current_frame = context.scene.frame_current

            target = context.active_object if context.mode == "OBJECT" else context.active_pose_bone

            graph_changed = current_keyframe_data != _last_keyframe_data
            transform_changed = current_transform_data != _last_transform_data
            frame_changed = current_frame != _last_frame

            if transform_changed:
                if not frame_changed and target:
                    # Detect which properties changed
                    changed_properties = get_changed_properties(current_transform_data, _last_transform_data)
                    anim_offset = scene.amp_timeline_tools.anim_offset

                    # Insert keyframes based on user preferences and autokey settings
                    if changed_properties and not anim_offset.mask_in_use:
                        keyframes_inserted = insert_keyframes(context, changed_properties)
                        # Note: insert_keyframes will handle checking autokey and user preferences

                # Always update motion paths when transforms change, regardless of autokey
                if not _update_scheduled:
                    _update_scheduled = True
                    bpy.app.timers.register(
                        perform_motion_path_update, first_interval=prefs.realtime_mopaths_timer_interval
                    )
                _last_transform_data = current_transform_data
                _last_frame = current_frame

            elif graph_changed:

                if not _update_scheduled:
                    _update_scheduled = True
                    bpy.app.timers.register(
                        perform_motion_path_update, first_interval=prefs.realtime_mopaths_timer_interval
                    )
                _last_keyframe_data = current_keyframe_data

        if settings_sculpt and settings_sculpt.is_sculpting != _last_is_sculpting:
            if not _update_scheduled:
                _update_scheduled = True
                bpy.app.timers.register(
                    perform_motion_path_update, first_interval=prefs.realtime_mopaths_timer_interval
                )
            _last_is_sculpting = settings_sculpt.is_sculpting

    finally:
        _is_handler_running = False


class AMP_OT_RealtimeMotionPaths(Operator):

    bl_idname = "anim.amp_realtime_motion_paths"
    bl_label = "Auto Update Motion Paths"
    bl_options = {"REGISTER"}
    bl_description = """
    Auto-update motion paths based on user settings: either in real-time as keyframes are adjusted,
    or only after the keyframe adjustments are completed"""

    def invoke(self, context, event):
        prefs = bpy.context.preferences.addons[base_package].preferences
        global _last_keyframe_data, _last_transform_data, _last_frame, _handlers_registered

        if prefs.is_mopaths_active:
            # Stop the operator
            prefs.is_mopaths_active = False
            self.cancel(context)
            return {"CANCELLED"}

        else:
            # Start the operator
            _last_keyframe_data = get_keyframe_data(context)
            _last_transform_data = get_transform_data(context)
            _last_frame = context.scene.frame_current
            if not _handlers_registered:
                bpy.app.handlers.depsgraph_update_post.append(amp_realtime_motion_paths_handler)
                _handlers_registered = True
            prefs.is_mopaths_active = True
            return {"FINISHED"}

    def cancel(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.is_mopaths_active = False
        global _handlers_registered
        if _handlers_registered:
            try:
                bpy.app.handlers.depsgraph_update_post.remove(amp_realtime_motion_paths_handler)
            except ValueError:
                pass
            _handlers_registered = False
        return {"CANCELLED"}


def apply_motion_path_settings_to_object(obj, context):
    """Apply motion path settings from mp_props to an object or pose bone."""
    props = context.scene.mp_props

    # Handle pose bones differently than objects
    if hasattr(obj, "bone"):  # This is a pose bone
        # For pose bones, we need to check if it has a motion path
        if obj and obj.motion_path:
            mp = obj.motion_path

            # For pose bones, animation visualization settings are on the armature object
            armature = context.active_object
            if armature and armature.animation_visualization and armature.animation_visualization.motion_path:
                av = armature.animation_visualization.motion_path

                # Apply settings from mp_props
                if bpy.app.version >= (4, 2, 0):
                    av.use_camera_space_bake = props.use_camera_space_bake

                av.show_frame_numbers = props.show_frame_numbers
                av.show_keyframe_highlight = False
                av.show_keyframe_numbers = False

            # Apply motion path specific settings
            mp.lines = props.lines
            mp.line_thickness = props.line_thickness

            if bpy.app.version >= (4, 2, 0):
                mp.use_custom_color = props.use_custom_color
                if props.use_custom_color:
                    mp.color = props.color_before
                    mp.color_post = props.color_after

    else:  # This is a regular object
        if obj and obj.motion_path and obj.animation_visualization and obj.animation_visualization.motion_path:
            mp = obj.motion_path
            av = obj.animation_visualization.motion_path

            # Apply settings from mp_props
            if bpy.app.version >= (4, 2, 0):
                av.use_camera_space_bake = props.use_camera_space_bake

            av.show_frame_numbers = props.show_frame_numbers
            av.show_keyframe_highlight = False
            av.show_keyframe_numbers = False

            mp.lines = props.lines
            mp.line_thickness = props.line_thickness

            if bpy.app.version >= (4, 2, 0):
                mp.use_custom_color = props.use_custom_color
                if props.use_custom_color:
                    mp.color = props.color_before
                    mp.color_post = props.color_after


def apply_motion_path_settings_to_selected(context):
    """Apply motion path settings to all selected objects or pose bones."""
    if context.mode == "POSE" and context.selected_pose_bones:
        for bone in context.selected_pose_bones:
            apply_motion_path_settings_to_object(bone, context)
    elif context.mode == "OBJECT" and context.selected_objects:
        for obj in context.selected_objects:
            apply_motion_path_settings_to_object(obj, context)


class AMP_OT_QuickMotionPaths(bpy.types.Operator):
    bl_idname = "anim.amp_quick_motion_paths"
    bl_label = "Quick Motion Paths"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Refresh motion paths for objects or pose bones
    - Quick: Calculate motion paths without deleting existing ones
    - Delete All: Delete all existing motion paths before updating
    - Delete Current: Delete the current motion path before updating
    - Update All: Update all motion paths"""

    operation: EnumProperty(
        name="Operation",
        description="Choose the operation to perform",
        items=[
            ("QUICK", "Quick", "Calculate motion paths without deleting"),
            ("DELETE_ALL", "Delete All", "Delete all existing motion paths before updating"),
            ("DELETE_CURRENT", "Delete Current", "Delete the current motion path before updating"),
            ("UPDATE_ALL", "Update All", "Update all motion paths"),
        ],
        default="QUICK",
    )

    @classmethod
    def poll(cls, context):
        return (
            context.active_object
            if context.mode == "OBJECT"
            else context.active_pose_bone if context.mode == "POSE" else False
        )

    def execute(self, context):
        active_element = context.active_object if context.mode == "OBJECT" else context.active_pose_bone
        is_pose_mode = context.mode == "POSE"

        if self.operation == "DELETE_ALL":
            if is_pose_mode:
                bpy.ops.pose.paths_clear(only_selected=False)
            else:
                bpy.ops.object.paths_clear(only_selected=False)
            self.report({"INFO"}, "Deleted all motion paths")

        elif self.operation == "DELETE_CURRENT" and active_element:
            if is_pose_mode:
                bpy.ops.pose.paths_clear(only_selected=True)
                self.report({"INFO"}, f"Cleared motion paths for pose bone: {active_element.name}")
            else:
                bpy.ops.object.paths_clear(only_selected=True)
                self.report({"INFO"}, f"Cleared motion paths for object: {active_element.name}")

        elif self.operation == "UPDATE_ALL":
            bpy.ops.object.paths_update_visible()
            # Apply settings to all visible motion paths
            apply_motion_path_settings_to_selected(context)
            self.report({"INFO"}, "Updated all motion paths")

        elif self.operation == "QUICK":
            if is_pose_mode and active_element:
                bpy.ops.pose.paths_calculate()
                # Apply settings after calculating
                apply_motion_path_settings_to_object(active_element, context)
                self.report({"INFO"}, f"Calculated motion paths for pose bone: {active_element.name}")
            elif active_element:
                bpy.ops.object.paths_calculate()
                # Apply settings after calculating
                apply_motion_path_settings_to_object(active_element, context)
                self.report({"INFO"}, f"Calculated motion paths for object: {active_element.name}")
            else:
                self.report({"WARNING"}, "No active element to calculate motion paths")
                return {"CANCELLED"}

        else:
            self.report({"WARNING"}, "No valid operation selected")
            return {"CANCELLED"}

        return {"FINISHED"}


class AMP_PT_AnimMopathsGraph(Panel):
    bl_label = "Anim Mopaths"
    bl_idname = "AMP_PT_AnimMopathsGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation"
    bl_parent_id = "AMP_PT_AniMateProGraph"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        AnimMopathsHeader(self, context)

    def draw(self, context):
        layout = self.layout
        AnimMopathsButtons(layout, context)


class AMP_PT_AnimMopathsView(Panel):
    bl_label = "Anim Mopaths"
    bl_idname = "AMP_PT_AnimMopaths"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "AMP_PT_AniMateProView"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        AnimMopathsHeader(self, context)

    def draw(self, context):
        layout = self.layout
        AnimMopathsButtons(layout, context)


class AMP_PT_AnimMopathsPop(Panel):
    bl_label = "Anim Mopaths"
    bl_idname = "AMP_PT_AnimMopathsPop"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout
        AnimMopathsButtons(layout, context)


def AnimMopathsHeader(self, context):
    layout = self.layout
    column = layout.column()
    column.alignment = "LEFT"
    AnimMopathsButton(column, context, text="")


def AnimMopathsButtons(layout, context):
    prefs = context.preferences.addons[base_package].preferences

    row = layout.row(align=True)

    AnimMopathsButton(row, context)
    row.prop(prefs, "display_options", text="", icon="SETTINGS")

    if prefs.display_options:
        box = layout.box()
        box.use_property_split = True
        box.use_property_decorate = False
        box.label(text="Motion Paths Options")

        box.prop(prefs, "realtime_mopaths_timer_interval", slider=True)
        box.prop(prefs, "realtime_mograph")
        box.prop(prefs, "clear_previous")

    row = layout.row(align=True)
    quick = row.operator("anim.amp_quick_motion_paths", text="Quick Motion Paths", icon="PLAY")
    quick.operation = "QUICK"

    del_current = row.operator("anim.amp_quick_motion_paths", text="", icon="X")
    del_current.operation = "DELETE_CURRENT"

    row.prop(context.scene.mp_props, "quick_path_settings", text="", icon="SETTINGS")

    if context.scene.mp_props.quick_path_settings:
        AnimMopathsQuickPathSettings(layout, context)

    row = layout.row(align=True)
    op_update_all = row.operator("anim.amp_quick_motion_paths", text="Update All", icon="FILE_REFRESH")
    op_update_all.operation = "UPDATE_ALL"

    op_delete_all = row.operator("anim.amp_quick_motion_paths", text="", icon="X")
    op_delete_all.operation = "DELETE_ALL"


def AnimMopathsQuickPathSettings(layout, context):
    """Draws the quick path settings in the UI."""
    box = layout.box()
    box.use_property_split = True
    box.use_property_decorate = False

    col = box.column(align=True)
    motion_path_options(col, context.scene.mp_props)


def AnimMopathsButton(layout, context, text="Realtime Motion Paths"):

    prefs = context.preferences.addons[base_package].preferences
    button_text = text
    if prefs.is_mopaths_active:
        layout.alert = True
        icon_value = utils.customIcons.get_icon_id("AMP_anim_mopaths_on")
    elif not prefs.is_mopaths_active:
        icon_value = utils.customIcons.get_icon_id("AMP_anim_mopaths_off")

    layout.operator(
        AMP_OT_RealtimeMotionPaths.bl_idname,
        text=button_text,
        icon_value=icon_value,
        depress=False,
    )


classes = (
    AMP_OT_RealtimeMotionPaths,
    AMP_OT_QuickMotionPaths,
    # AMP_PT_AnimMopathsGraph,
    # AMP_PT_AnimMopathsView,
    AMP_PT_AnimMopathsPop,
)


def register():
    global _handlers_registered
    for cls in classes:
        bpy.utils.register_class(cls)

    prefs = bpy.context.preferences.addons[base_package].preferences

    if prefs.is_mopaths_active:
        prefs.is_mopaths_active = False


def unregister():
    global _handlers_registered
    if _handlers_registered:
        try:
            bpy.app.handlers.depsgraph_update_post.remove(amp_realtime_motion_paths_handler)
        except ValueError:
            pass
        _handlers_registered = False

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
