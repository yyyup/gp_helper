import bpy
from bpy.props import IntProperty, EnumProperty
from bpy.types import Operator, Panel, PropertyGroup
from .. import utils
import math
import numpy as np


class AnimNudgerSettings(PropertyGroup):
    frames_to_nudge: IntProperty(
        name="Frames to Nudge",
        description="Number of frames to nudge the keyframes",
        default=1,
        min=1,
        max=1000,
        options={"HIDDEN"},
    )


class AMP_OT_anim_nudger(Operator):
    bl_idname = "anim.timeline_anim_nudger"
    bl_label = "Anim Nudger"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Nudge keyframes:
- If keyframes are selected, nudge only the selected keyframes.
- If no keyframes are selected, nudge the keyframes on or to the current frame
- Nudge them by the specified number of frames"""

    direction: EnumProperty(
        name="Direction",
        description="Direction to nudge the keyframes",
        items=[
            ("LEFT", "Left", ""),
            ("RIGHT", "Right", ""),
        ],
        default="RIGHT",
    )

    def execute(self, context):
        if not context.active_object or not context.active_object.animation_data:
            self.report({"WARNING"}, "No animation data found.")
            return {"CANCELLED"}
        self.playhead = context.active_object.animation_data.nla_tweak_strip_time_to_scene(
            context.scene.frame_current, invert=True
        )
        settings = context.scene.anim_nudger_settings
        frames_to_nudge = settings.frames_to_nudge
        direction = self.direction

        if not context.selected_objects:
            self.report({"WARNING"}, "No selected objects with animation data found.")
            return {"CANCELLED"}

        utils.dprint(f"[DEBUG] Executing AnimNudger: Direction={direction}, Frames={frames_to_nudge}")

        if self.are_keyframes_selected(context):
            self.nudge_selected_keyframes(context, direction, frames_to_nudge)
        else:
            if self.has_keyframes_on_current_frame(context):
                self.move_current_frame_keyframes_and_playhead(context, direction, frames_to_nudge)
            else:
                self.snap_nearest_keyframes(context, direction)

        # Update fcurves - handle cases where visible_fcurves might not be available
        try:
            if context.visible_fcurves:
                for fcurve in context.visible_fcurves:
                    fcurve.update()
        except (AttributeError, TypeError):
            # Fallback: update all fcurves from the active object's action
            if (
                context.active_object
                and context.active_object.animation_data
                and context.active_object.animation_data.action
            ):
                for fcurve in utils.curve.all_fcurves(context.active_object.animation_data.action):
                    fcurve.update()

        context.area.tag_redraw()

        return {"FINISHED"}

    def are_keyframes_selected(self, context):
        action = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        if not action:
            return False

        # Get fcurves in a context-aware way
        fcurves = utils.curve.get_context_aware_visible_fcurves(context, action)
        for fcurve in fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    return True
        return False

    def get_fcurves_keyframes(self, fcurves, only_selected=False, frame_filter=None):
        all_keyframes = []
        all_handles_left = []
        all_handles_right = []
        refs = []
        fcurve_map = []
        for f in fcurves:
            frames = []
            handles_l = []
            handles_r = []
            key_refs = []
            for k in f.keyframe_points:
                if only_selected and not k.select_control_point:
                    continue
                if frame_filter and not frame_filter(k.co.x):
                    continue
                frames.append(k.co.x)
                handles_l.append(k.handle_left.x)
                handles_r.append(k.handle_right.x)
                key_refs.append(k)
            if frames:
                all_keyframes.append(frames)
                all_handles_left.append(handles_l)
                all_handles_right.append(handles_r)
                refs.append(key_refs)
                fcurve_map.append(f)
        return fcurve_map, refs, all_keyframes, all_handles_left, all_handles_right

    def set_fcurves_keyframes(self, fcurve_map, refs, frames_arr, handles_left_arr, handles_right_arr):
        for f, f_refs, f_frames, f_hl, f_hr in zip(fcurve_map, refs, frames_arr, handles_left_arr, handles_right_arr):
            for k, frame, hl, hr in zip(f_refs, f_frames, f_hl, f_hr):
                old_x = k.co.x
                k.co.x = frame
                k.handle_left.x = hl
                k.handle_right.x = hr
                utils.dprint(f"[DEBUG] Moved keyframe from {old_x} to {k.co.x}")
        if fcurve_map:
            fcurve_map[0].id_data.update_tag()

    def nudge_selected_keyframes(self, context, direction, frames):
        action = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        if not action:
            return
        delta = -frames if direction == "LEFT" else frames

        # Get fcurves in a context-aware way
        visible_fcurves = utils.curve.get_context_aware_visible_fcurves(context, action)
        fmap, refs, frames_arr, hl_arr, hr_arr = self.get_fcurves_keyframes(visible_fcurves, only_selected=True)
        if not frames_arr:
            return

        for i in range(len(frames_arr)):
            frames_arr[i] = np.array(frames_arr[i], dtype=float)
            hl_arr[i] = np.array(hl_arr[i], dtype=float)
            hr_arr[i] = np.array(hr_arr[i], dtype=float)
            frames_arr[i] += delta
            hl_arr[i] += delta
            hr_arr[i] += delta

        self.set_fcurves_keyframes(fmap, refs, frames_arr, hl_arr, hr_arr)

    def has_keyframes_on_current_frame(self, context):
        playhead = self.playhead  # use stored playhead
        action = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        if not action:
            return False

        # Get fcurves in a context-aware way
        visible_fcurves = utils.curve.get_context_aware_visible_fcurves(context, action)
        for fcurve in visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if math.isclose(keyframe.co.x, playhead, abs_tol=0.1):
                    return True
        return False

    def move_current_frame_keyframes_and_playhead(self, context, direction, frames):
        action = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        if not action:
            return
        delta = -frames if direction == "LEFT" else frames
        playhead = self.playhead

        def frame_filter(x):
            return math.isclose(x, playhead, abs_tol=0.1)

        # Get fcurves in a context-aware way
        visible_fcurves = utils.curve.get_context_aware_visible_fcurves(context, action)
        fmap, refs, frames_arr, hl_arr, hr_arr = self.get_fcurves_keyframes(
            visible_fcurves, only_selected=False, frame_filter=frame_filter
        )
        for i in range(len(frames_arr)):
            frames_arr[i] = np.array(frames_arr[i], dtype=float)
            hl_arr[i] = np.array(hl_arr[i], dtype=float)
            hr_arr[i] = np.array(hr_arr[i], dtype=float)
            frames_arr[i] += delta
            hl_arr[i] += delta
            hr_arr[i] += delta

        self.set_fcurves_keyframes(fmap, refs, frames_arr, hl_arr, hr_arr)

        context.scene.frame_current = (
            int(context.active_object.animation_data.nla_tweak_strip_time_to_scene(playhead)) + delta
        )

    def snap_nearest_keyframes(self, context, direction):
        playhead = self.playhead
        action = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        if not action:
            return

        # Get fcurves in a context-aware way
        visible_fcurves = utils.curve.get_context_aware_visible_fcurves(context, action)

        kfs = []
        for f in visible_fcurves:
            for k in f.keyframe_points:
                kfs.append(k.co.x)
        kfs = sorted(set(kfs))
        if not kfs:
            return

        if direction == "RIGHT":
            nearest = None
            for kf in reversed(kfs):
                if kf < playhead:
                    nearest = kf
                    break
            if nearest is not None:
                self.move_keyframes(context, nearest, playhead)
        else:
            nearest = None
            for kf in kfs:
                if kf > playhead:
                    nearest = kf
                    break
            if nearest is not None:
                self.move_keyframes(context, nearest, playhead)

    def move_keyframes(self, context, from_frame, to_frame):
        action = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        if not action:
            return
        delta = to_frame - from_frame

        def frame_filter(x):
            return math.isclose(x, from_frame, abs_tol=0.1)

        # Get fcurves in a context-aware way
        visible_fcurves = utils.curve.get_context_aware_visible_fcurves(context, action)
        fmap, refs, frames_arr, hl_arr, hr_arr = self.get_fcurves_keyframes(visible_fcurves, frame_filter=frame_filter)
        for i in range(len(frames_arr)):
            frames_arr[i] = np.array(frames_arr[i], dtype=float)
            hl_arr[i] = np.array(hl_arr[i], dtype=float)
            hr_arr[i] = np.array(hr_arr[i], dtype=float)
            frames_arr[i] += delta
            hl_arr[i] += delta
            hr_arr[i] += delta

        self.set_fcurves_keyframes(fmap, refs, frames_arr, hl_arr, hr_arr)


class AMP_OT_anim_pusher(Operator):
    bl_idname = "anim.anim_pusher"
    bl_label = "Anim Pusher"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Push the keyframes to the left or right of the playhead by 1 frame:
- Adding will shift all keyframes head of the playhead and the and the scene range by 1.
- Removing will shift all keyframes head of the playhead and the scene range by -1.
- If keyframes are present on the current frame, can't remove the in-between frame"""

    operation: EnumProperty(
        name="Operation",
        description="Add or Remove an in-between frame",
        items=[
            ("ADD", "Add", ""),
            ("REMOVE", "Remove", ""),
        ],
        default="ADD",
    )

    def execute(self, context):
        operation = self.operation
        if not context.active_object or not context.active_object.animation_data:
            self.report({"WARNING"}, "No animation data found.")
            return {"CANCELLED"}
        playhead = context.active_object.animation_data.nla_tweak_strip_time_to_scene(
            context.scene.frame_current, invert=True
        )
        scene = context.scene

        if not context.selected_objects:
            self.report({"WARNING"}, "No selected objects with animation data found.")
            return {"CANCELLED"}
        if operation == "ADD":
            self.add_inbetween(context, playhead)
        elif operation == "REMOVE":
            if self.has_keyframes_on_frame(context, playhead):
                self.report({"WARNING"}, "Can't remove in-between with keyframes on the current frame")
                return {"CANCELLED"}
            self.remove_inbetween(context, playhead)

        context.area.tag_redraw()
        return {"FINISHED"}

    def add_inbetween(self, context, playhead):
        for obj in context.selected_objects:
            fcurves = utils.curve.all_fcurves(obj.animation_data.action)
            if not obj.animation_data or not obj.animation_data.action:
                continue
            self.shift_keyframes_numpy(fcurves, playhead, 1)
        context.scene.frame_end += 1

    def remove_inbetween(self, context, playhead):
        for obj in context.selected_objects:
            fcurves = utils.curve.all_fcurves(obj.animation_data.action)
            if not obj.animation_data or not obj.animation_data.action:
                continue
            self.shift_keyframes_numpy(fcurves, playhead, -1, strictly_greater=True)

        if context.scene.frame_end > playhead:
            context.scene.frame_end -= 1

    def has_keyframes_on_frame(self, context, frame):
        # Check all selected objects for keyframes on the specified frame
        for obj in context.selected_objects:
            if not obj.animation_data or not obj.animation_data.action:
                continue
            fcurves = utils.curve.all_fcurves(obj.animation_data.action)
            for fcurve in fcurves:
                for keyframe in fcurve.keyframe_points:
                    if math.isclose(keyframe.co.x, frame, abs_tol=0.1):
                        return True
        return False

    def shift_keyframes_numpy(self, fcurves, pivot_frame, delta, strictly_greater=False):
        def frame_filter(x):
            return x > pivot_frame if strictly_greater else x >= pivot_frame

        frames_list = []
        hl_list = []
        hr_list = []
        refs_list = []
        f_map = []
        for f in fcurves:
            frames = []
            hl = []
            hr = []
            refs = []
            for k in f.keyframe_points:
                if frame_filter(k.co.x):
                    frames.append(k.co.x)
                    hl.append(k.handle_left.x)
                    hr.append(k.handle_right.x)
                    refs.append(k)
            if frames:
                frames_list.append(np.array(frames, dtype=float))
                hl_list.append(np.array(hl, dtype=float))
                hr_list.append(np.array(hr, dtype=float))
                refs_list.append(refs)
                f_map.append(f)

        for i in range(len(frames_list)):
            old_frames = frames_list[i].copy()
            frames_list[i] += delta
            hl_list[i] += delta
            hr_list[i] += delta
            for old, new in zip(old_frames, frames_list[i]):
                utils.dprint(f"[DEBUG] Moved keyframe from {old} to {new}")

        for f, r, fr, hl, hr in zip(f_map, refs_list, frames_list, hl_list, hr_list):
            for k, ff, hll, hrr in zip(r, fr, hl, hr):
                k.co.x = ff
                k.handle_left.x = hll
                k.handle_right.x = hrr
            f.id_data.update_tag()


classes = (
    AnimNudgerSettings,
    AMP_OT_anim_nudger,
    AMP_OT_anim_pusher,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.anim_nudger_settings = bpy.props.PointerProperty(type=AnimNudgerSettings)
    utils.dprint("AnimNudger addon registered.")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.anim_nudger_settings
    utils.dprint("AnimNudger addon unregistered.")


if __name__ == "__main__":
    register()
