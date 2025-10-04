import bpy
from bpy.app.handlers import persistent
from typing import Dict

realtime_looper_handler_active = False
_is_copy_in_progress = False
_last_copied_values = {}


def ensure_keyframe_exists(fcurve, frame):
    keyframes = fcurve.keyframe_points
    low, high = 0, len(keyframes) - 1
    while low <= high:
        mid = (low + high) // 2
        mid_frame = keyframes[mid].co.x
        if mid_frame == frame:
            return
        elif mid_frame < frame:
            low = mid + 1
        else:
            high = mid - 1
    val = fcurve.evaluate(frame)
    fcurve.keyframe_points.insert(frame, val)


def copy_keyframe_shape(src_kf, dst_kf):
    if not (src_kf and dst_kf):
        return
    dst_kf.handle_left_type = src_kf.handle_left_type
    dst_kf.handle_right_type = src_kf.handle_right_type
    dst_kf.interpolation = src_kf.interpolation
    dst_kf.co.y = src_kf.co.y
    dst_kf.co_ui.y = src_kf.co_ui.y
    src_co = src_kf.co
    dst_co = dst_kf.co
    for handle, src_handle in [(dst_kf.handle_left, src_kf.handle_left), (dst_kf.handle_right, src_kf.handle_right)]:
        handle[0] = dst_co[0] + (src_handle[0] - src_co[0])
        handle[1] = dst_co[1] + (src_handle[1] - src_co[1])


def get_keyframe_data(kf):
    return (
        kf.co.y,
        kf.interpolation,
        kf.handle_left_type,
        kf.handle_right_type,
        (kf.handle_left[0], kf.handle_left[1]),
        (kf.handle_right[0], kf.handle_right[1]),
    )


def match_first_last_if_modified(fcurve, start_frame, end_frame):
    global _is_copy_in_progress, _last_copied_values
    if _is_copy_in_progress:
        return
    keyframes = fcurve.keyframe_points
    if not keyframes:
        return
    start_kf = None
    end_kf = None
    for kf in keyframes:
        if kf.co.x == start_frame:
            start_kf = kf
        elif kf.co.x == end_frame:
            end_kf = kf
        if start_kf and end_kf:
            break
    if not (start_kf and end_kf):
        return

    # Check if either keyframe is actively selected (control point or handles).
    start_sel = start_kf.select_control_point or start_kf.select_left_handle or start_kf.select_right_handle
    end_sel = end_kf.select_control_point or end_kf.select_left_handle or end_kf.select_right_handle

    # Initialize stored data on first encounter.
    if fcurve not in _last_copied_values:
        _last_copied_values[fcurve] = {
            "start_data": get_keyframe_data(start_kf),
            "end_data": get_keyframe_data(end_kf),
            "last_source": None,
        }
        return

    _is_copy_in_progress = True
    stored = _last_copied_values[fcurve]
    current_start = get_keyframe_data(start_kf)
    current_end = get_keyframe_data(end_kf)
    if end_sel and not start_sel:
        # Last keyframe is being edited.
        copy_keyframe_shape(end_kf, start_kf)
        _last_copied_values[fcurve] = {"start_data": current_end, "end_data": current_end, "last_source": "end"}
    elif start_sel and not end_sel:
        # First keyframe is being edited.
        copy_keyframe_shape(start_kf, end_kf)
        _last_copied_values[fcurve] = {"start_data": current_start, "end_data": current_start, "last_source": "start"}
    else:
        # If no clear selection, compare stored values.
        start_changed = stored["start_data"] != current_start
        end_changed = stored["end_data"] != current_end
        if start_changed and stored["last_source"] != "start":
            copy_keyframe_shape(start_kf, end_kf)
            _last_copied_values[fcurve] = {
                "start_data": current_start,
                "end_data": current_start,
                "last_source": "start",
            }
        elif end_changed and stored["last_source"] != "end":
            copy_keyframe_shape(end_kf, start_kf)
            _last_copied_values[fcurve] = {"start_data": current_end, "end_data": current_end, "last_source": "end"}
    _is_copy_in_progress = False


def get_selected_elements():
    elements = []
    for obj in bpy.context.selected_objects:
        if obj.type == "ARMATURE" and obj.mode == "POSE":
            selected_bones = [b for b in obj.pose.bones if b.bone.select]
            elements.append((obj, selected_bones))
        else:
            elements.append((obj, None))
    return elements


@persistent
def anim_looper_update_handler(scene):
    if not realtime_looper_handler_active:
        return
    if not bpy.context.area or bpy.context.area.type == "VIEW_3D":
        return

    # Skip looper matching when anim_offset is active to avoid interference
    if hasattr(scene, "amp_timeline_tools") and hasattr(scene.amp_timeline_tools, "anim_offset"):
        anim_offset = scene.amp_timeline_tools.anim_offset
        if anim_offset.quick_anim_offset_in_use or anim_offset.mask_in_use:
            return
    wm = bpy.context.window_manager
    if getattr(wm, "anim_sculpt_running", False):
        fcurves = getattr(bpy.context, "visible_fcurves", [])
    else:
        fcurves = bpy.context.selected_editable_fcurves
    for fcurve in fcurves:
        if not (fcurve and hasattr(fcurve, "keyframe_points")):
            continue
        keyframes = fcurve.keyframe_points
        if len(keyframes) < 2:
            continue
        frames = sorted({kf.co.x for kf in keyframes})
        if len(frames) < 2:
            continue
        ensure_keyframe_exists(fcurve, frames[0])
        ensure_keyframe_exists(fcurve, frames[-1])
        match_first_last_if_modified(fcurve, frames[0], frames[-1])


class AMP_OT_ToggleRealtimeLooperHandler(bpy.types.Operator):
    bl_idname = "anim.amp_toggle_anim_looper_handler"
    bl_label = "Realtime Looper"
    bl_description = (
        "Ensure continuity between first and last keyframes, " "for keyframe value and handles relative positions"
    )

    def execute(self, context):
        global realtime_looper_handler_active
        realtime_looper_handler_active = not realtime_looper_handler_active
        if realtime_looper_handler_active:
            if anim_looper_update_handler not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(anim_looper_update_handler)
                context.scene.realtime_looper_handler_active = True
                bpy.context.scene.tool_settings.use_keyframe_cycle_aware = True
            self.report({"INFO"}, "Realtime Looper Enabled")
        else:
            try:
                bpy.app.handlers.depsgraph_update_post.remove(anim_looper_update_handler)
                context.scene.realtime_looper_handler_active = False
                bpy.context.scene.tool_settings.use_keyframe_cycle_aware = False
            except ValueError:
                pass
            self.report({"INFO"}, "Realtime Looper Disabled")
        return {"FINISHED"}


classes = (AMP_OT_ToggleRealtimeLooperHandler,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.realtime_looper_handler_active = bpy.props.BoolProperty(default=False)


def unregister():
    del bpy.types.Scene.realtime_looper_handler_active
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
