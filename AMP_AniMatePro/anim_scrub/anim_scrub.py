import bpy
from .. import utils

from .. import __package__ as base_package


##################################
### Scrubbing Helper functions ###
##################################


def navigate_through_markers(self, context, frame_movement):
    markers = context.scene.timeline_markers
    current_frame = context.scene.frame_current
    marker_frames = [marker.frame for marker in markers]
    prefs = context.preferences.addons[base_package].preferences
    # Check if there are any markers in the timeline
    if not marker_frames:
        # If no markers are found, set an error message and exit the function
        prefs.scrubbing_error = "NO MARKERS IN THE TIMELINE"
        return

    # If there are markers, proceed with navigating through them
    marker_frames.sort()

    if frame_movement > 0:  # Moving forward
        next_marker_frame = next((frame for frame in marker_frames if frame > current_frame), None)
        if next_marker_frame is not None:
            context.scene.frame_current = next_marker_frame
    elif frame_movement < 0:  # Moving backward
        previous_marker_frame = next((frame for frame in reversed(marker_frames) if frame < current_frame), None)
        if previous_marker_frame is not None:
            context.scene.frame_current = previous_marker_frame

    # Clear the error message if successful navigation occurs
    prefs.scrubbing_error = ""


def navigate_through_keyframes(self, context, frame_movement):
    frame_movement = int(frame_movement)
    prefs = context.preferences.addons[base_package].preferences
    active_object = context.active_object
    pose_mode = active_object and active_object.type == "ARMATURE" and active_object.mode == "POSE"

    if not active_object or not active_object.select_get():
        prefs.scrubbing_error = "NO OBJECT SELECTED"
        return

    if not active_object.animation_data or not active_object.animation_data.action:
        prefs.scrubbing_error = "NO KEYFRAMES FOUND"
        return

    keyframe_frames = set()
    if pose_mode:
        selected_bones = [bone.name for bone in active_object.pose.bones if bone.bone.select]
        if not selected_bones:
            prefs.scrubbing_error = "NO BONE SELECTED"
            return

        # Filter fcurves for those related to selected bones
        for fcurve in utils.curve.all_fcurves(active_object.animation_data.action):
            for bone_name in selected_bones:
                if fcurve.data_path.startswith(f'pose.bones["{bone_name}"]'):
                    keyframe_frames.update(int(keyframe.co[0]) for keyframe in fcurve.keyframe_points)
    else:
        # For objects outside of pose mode, consider the object's keyframes
        keyframe_frames = {
            int(keyframe.co[0])
            for fcurve in utils.curve.all_fcurves(active_object.animation_data.action)
            for keyframe in fcurve.keyframe_points
        }

    # Proceed if there are keyframes to navigate through
    if keyframe_frames:
        current_frame = context.scene.frame_current
        target_frame = navigate_through_keyframes_logic(frame_movement, keyframe_frames, current_frame)

        if target_frame is not None:
            context.scene.frame_current = target_frame

    else:
        prefs.scrubbing_error = "NO KEYFRAMES FOUND"


def navigate_through_keyframes_logic(frame_movement, keyframe_frames, current_frame):
    keyframe_frames = sorted(keyframe_frames)
    if frame_movement > 0:  # Moving forward
        for frame in keyframe_frames:
            if frame > current_frame:
                return frame
    else:  # Moving backward
        for frame in reversed(keyframe_frames):
            if frame < current_frame:
                return frame
    return None


# def apply_frame_limits(context, proposed_frame):
#     prefs = context.preferences.addons[base_package].preferences

#     if prefs.limit_to_active_range:
#         if context.scene.use_preview_range:
#             lower_limit, upper_limit = (
#                 context.scene.frame_preview_start,
#                 context.scene.frame_preview_end,
#             )
#         else:
#             lower_limit, upper_limit = (
#                 context.scene.frame_start,
#                 context.scene.frame_end,
#             )
#     else:
#         return proposed_frame

#     if context.active_object and context.active_object.animation_data:
#         action = context.active_object.animation_data.action
#     else:
#         action = None

#     if action is not None and action.use_cyclic and (upper_limit - lower_limit) > 1:
#         range_size = upper_limit - lower_limit + 1
#         new_frame = ((proposed_frame - lower_limit) % range_size) + lower_limit

#     else:
#         new_frame = max(min(proposed_frame, upper_limit), lower_limit)

#     return new_frame


def apply_frame_limits(context, proposed_frame):
    prefs = context.preferences.addons[base_package].preferences

    # If limit_to_active_range is False, allow unrestricted movement
    if not prefs.limit_to_active_range:
        return proposed_frame

    # Determine frame range
    if context.scene.use_preview_range:
        lower_limit = context.scene.frame_preview_start
        upper_limit = context.scene.frame_preview_end
    else:
        lower_limit = context.scene.frame_start
        upper_limit = context.scene.frame_end

    # Get active action if available
    action = None
    if context.active_object and context.active_object.animation_data:
        action = context.active_object.animation_data.action

    # Handle cyclic animations
    if action and action.use_cyclic and (upper_limit - lower_limit) > 1:
        # Calculate relative position within range
        range_size = upper_limit - lower_limit + 1
        relative_pos = proposed_frame - lower_limit

        # Handle both positive and negative wrapping
        if relative_pos >= 0:
            wrapped_pos = relative_pos % range_size
        else:
            wrapped_pos = range_size - (abs(relative_pos) % range_size)
            if wrapped_pos == range_size:
                wrapped_pos = 0

        new_frame = lower_limit + wrapped_pos
    else:
        # Simple clamping for non-cyclic animations
        new_frame = max(lower_limit, min(proposed_frame, upper_limit))

    return new_frame


def navigate_through_frames(self, context, current_frame):

    if abs(self.cumulative_delta_x) >= 1.0:
        proposed_frame_movement = int(self.cumulative_delta_x)
        proposed_new_frame = current_frame + proposed_frame_movement

        # Apply frame limits here
        new_frame = apply_frame_limits(context, proposed_new_frame)
        context.scene.frame_current = new_frame

        # Adjust the cumulative delta by the applied frame movement
        actual_frame_movement = new_frame - current_frame
        self.cumulative_delta_x -= actual_frame_movement

        # # Check if we've hit a limit and reset the delta so the playhead can change direction
        if new_frame == context.scene.frame_start or new_frame == context.scene.frame_end:
            self.cumulative_delta_x = 0.0


# Local increments working with the mouse movement
def handle_scrubbing_modes(self, context, event, current_frame):

    scene = context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset
    prefs = context.preferences.addons[base_package].preferences

    # Calculate the immediate change in mouse X position from the last event
    immediate_delta_x = event.mouse_x - event.mouse_prev_x

    # Adjust immediate_delta_x based on the sensitivity setting
    adjusted_delta_x = immediate_delta_x * prefs.timeline_sensitivity * 4

    # Reduction factor for MARKERS and KEYFRAMES mode
    reduction_factor = 0.1

    # Apply reduction factor for MARKERS and KEYFRAMES mode
    if prefs.current_mode in ["MARKERS", "KEYFRAMES"]:
        adjusted_delta_x *= reduction_factor

    # Update the cumulative adjusted delta
    self.cumulative_delta_x += adjusted_delta_x

    # Determine frame movement based on the cumulative delta
    frame_movement = int(self.cumulative_delta_x)

    # if not self.adjusting_quick_anim_offset:

    if frame_movement != 0:
        # Perform navigation based on the current mode

        if prefs.current_mode == "MARKERS":
            navigate_through_markers(self, context, frame_movement)
            # Reset the cumulative delta after navigating
            self.cumulative_delta_x -= frame_movement

        elif prefs.current_mode == "KEYFRAMES":
            navigate_through_keyframes(self, context, frame_movement)

            # Reset the cumulative delta after navigating
            self.cumulative_delta_x -= frame_movement
        else:
            # For general frame navigation
            navigate_through_frames(self, context, current_frame)


def handle_scrubbing_tap_action(self, context):
    """Handle the tap action for the scrubbing operator"""
    prefs = context.preferences.addons[base_package].preferences
    spacebar_action = prefs.mode

    if context.area is None:
        return {"CANCELLED"}

    if self.drag_started:
        return

    if spacebar_action == "PLAY":
        if not prefs.animation_was_playing:
            # Store the current frame before stopping
            prefs.last_scrub_frame = context.scene.frame_current
            bpy.ops.screen.animation_play()
            # prefs.animation_was_playing = True
            self.cumulative_delta_x = 0.0
            # print("play: drag_started", self.drag_started)
        elif prefs.animation_was_playing:  # not bpy.context.screen.is_animation_playing:
            # When stopping, reset the frame if needed and clear the state
            # bpy.ops.screen.animation_play()
            prefs.animation_was_playing = False
            # Reset the cumulative delta to prevent frame snapping
            self.cumulative_delta_x = 0.0
            # print("play: drag_started", self.drag_started

    elif spacebar_action == "TOOLBAR":
        bpy.ops.wm.toolbar("INVOKE_DEFAULT")

    elif spacebar_action == "SEARCH":
        bpy.ops.wm.search_menu("INVOKE_DEFAULT")

    return {"FINISHED"}


###############################
###############################


class AMP_OT_scrub(bpy.types.Operator):
    bl_idname = "anim.amp_timeline_scrub"
    bl_label = "Scrub Timeline"
    bl_options = {"REGISTER", "GRAB_CURSOR", "BLOCKING"}

    prefs = bpy.context.preferences.addons[base_package].preferences
    marker_key: bpy.props.StringProperty(default="CTRL")
    keyframe_key: bpy.props.StringProperty(default="SHIFT")
    toggle_gui_key: bpy.props.StringProperty(default="H")
    timeline_gui_toggle: bpy.props.BoolProperty(default=False)
    timeline_gui_color: bpy.props.FloatVectorProperty(
        name="GUI Color", default=(1.0, 1.0, 1.0), subtype="COLOR", min=0.0, max=1.0
    )
    timeline_sensitivity: bpy.props.FloatProperty(default=0.1)
    is_cleaning_up: bpy.props.BoolProperty(default=False)

    # Flags to indicate which operator to call next
    call_breakdown = bpy.props.BoolProperty(default=False)
    call_blend_to_neighbor = bpy.props.BoolProperty(default=False)
    call_relax = bpy.props.BoolProperty(default=False)

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        prefs = bpy.context.preferences.addons[base_package].preferences
        self.acumulate_mask_mover = 0
        self.is_hotkey_held = False
        self.scrubbing_key_pressed = False
        self.last_wheel_event_time = None
        self.is_sensitivity_mode_active = False
        self.initial_mouse_position = (0, 0)
        self.drag_started = False
        self.last_direction = None
        self.is_playing = False
        self.play_direction = "forward"
        self.want_to_play_reverse = False
        self.want_to_play_forward = False
        self.region = None
        self.region_x_min = None
        self.region_y_min = None
        self.region_x_max = None
        self.region_y_max = None
        self.lmb_pressed = False
        self.pause_dragging = False
        self.store_mouse_pos = False
        self.mask_mouse_offset_x = 0
        self.mask_mouse_offset_y = 0
        self.adjusting_quick_anim_offset = False
        prefs.is_scrubbing = True
        self.lmb_needed = prefs.use_lmb_for_scrubbing
        self.toggle_for_scrubbing = prefs.toggle_for_scrubbing
        self.cumulative_delta_x = 0.0
        self.animation_was_playing = False

    def finish(self, context):
        # Remove the GUI and the frame number from the cursor
        self.is_cleaning_up = True
        self.remove_draw_handler(context)
        prefs = context.preferences.addons[base_package].preferences
        anim_offset = context.scene.amp_timeline_tools.anim_offset

        # Restore the cursor to its initial screen coordinates if the property is set to True
        if prefs.lock_text_in_place:
            self.set_cursor_position(self.initial_screen_x, self.initial_screen_y)

        # Remove the error messages if any
        prefs.scrubbing_error = ""

        # Select the keyframes in the current frame
        if prefs.select_keyframes_on_current_frame:
            try:
                utils.curve.select_keyframe_in_editors(context)
                # bpy.ops.anim.amp_select_keyframes_in_current_frame()
            except RuntimeError:
                # Failed to select keyframes, likely no animation data or wrong context
                pass

        # Return the frame to the rage so anim offset does nto bug out
        # if anim_offset.mask_in_use:
        #     lower_limit, upper_limit = (
        #         max(context.scene.frame_preview_start, context.scene.frame_start),
        #         min(context.scene.frame_preview_end, context.scene.frame_end),
        #     )
        #     if context.scene.frame_current < lower_limit:
        #         context.scene.frame_current = lower_limit
        #     elif context.scene.frame_current > upper_limit:
        #         context.scene.frame_current = upper_limit

        self.cumulative_delta_x = 0.0
        prefs.is_scrubbing = False

        # Make the cursor visible again
        context.window.cursor_modal_restore()
        utils.refresh_ui(context)

    def refresh_draw_handler(self, mouse_x, mouse_y, context):
        def draw_function(_self, _context):

            utils.draw_callback_px(self, _context, mouse_x, mouse_y, context.area.type)

        # Remove the previous handler if it exists, using the appropriate method for each space type
        if hasattr(self, "_handle"):
            space_type = context.area.type
            if space_type == "VIEW_3D" and hasattr(bpy.types, "SpaceView3D"):
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            elif space_type == "GRAPH_EDITOR" and hasattr(bpy.types, "SpaceGraphEditor"):
                bpy.types.SpaceGraphEditor.draw_handler_remove(self._handle, "WINDOW")
            elif space_type == "DOPESHEET_EDITOR" and hasattr(bpy.types, "SpaceDopeSheetEditor"):
                bpy.types.SpaceDopeSheetEditor.draw_handler_remove(self._handle, "WINDOW")
            elif space_type == "NLA_EDITOR" and hasattr(bpy.types, "SpaceNLA"):
                bpy.types.SpaceNLA.draw_handler_remove(self._handle, "WINDOW")
            del self._handle

        # Add the handler back, again using the appropriate method for the space type
        if space_type == "VIEW_3D":
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_function, (self, context), "WINDOW", "POST_PIXEL"
            )
        elif space_type == "GRAPH_EDITOR":
            self._handle = bpy.types.SpaceGraphEditor.draw_handler_add(
                draw_function, (self, context), "WINDOW", "POST_PIXEL"
            )
        elif space_type == "DOPESHEET_EDITOR":
            self._handle = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
                draw_function, (self, context), "WINDOW", "POST_PIXEL"
            )
        elif space_type == "NLA_EDITOR":
            self._handle = bpy.types.SpaceNLA.draw_handler_add(draw_function, (self, context), "WINDOW", "POST_PIXEL")
        else:
            pass

        # Force a redraw of the area to reflect changes
        if hasattr(self, "_handle"):
            context.area.tag_redraw()

    def set_cursor_position(self, x, y):
        bpy.context.window.cursor_warp(x, y)

    def add_draw_handler(self, context, mouse_x, mouse_y):
        # Define the draw callback function correctly
        def draw_function(_self, _context):
            utils.draw_callback_px(self, _context, mouse_x, mouse_y, context.area.type)

        # Check if context.area is valid
        if context.area is None:
            return

        # Determine the correct space type and add the draw handler
        space_type = context.area.type
        if space_type == "VIEW_3D":
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_function, (self, context), "WINDOW", "POST_PIXEL"
            )
        elif space_type == "GRAPH_EDITOR":
            self._handle = bpy.types.SpaceGraphEditor.draw_handler_add(
                draw_function, (self, context), "WINDOW", "POST_PIXEL"
            )
        elif space_type == "DOPESHEET_EDITOR":
            self._handle = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
                draw_function, (self, context), "WINDOW", "POST_PIXEL"
            )
        elif space_type == "NLA_EDITOR":
            self._handle = bpy.types.SpaceNLA.draw_handler_add(draw_function, (self, context), "WINDOW", "POST_PIXEL")

    def remove_draw_handler(self, context):
        if hasattr(self, "_handle"):
            # Determine the correct space type and remove the draw handler
            space_type = context.area.type
            draw_handler_remove_method = {
                "VIEW_3D": bpy.types.SpaceView3D.draw_handler_remove,
                "GRAPH_EDITOR": bpy.types.SpaceGraphEditor.draw_handler_remove,
                "DOPESHEET_EDITOR": bpy.types.SpaceDopeSheetEditor.draw_handler_remove,
                "NLA_EDITOR": bpy.types.SpaceNLA.draw_handler_remove,
            }.get(space_type)

            if draw_handler_remove_method:
                draw_handler_remove_method(self._handle, "WINDOW")
                self._handle = None

    def invoke(self, context, event):
        prefs = bpy.context.preferences.addons[base_package].preferences
        # prefs.animation_animation_ = False

        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
            prefs.animation_was_playing = True

        self.drag_started = False  # Initialize a flag to track if dragging has started

        # Retrieve the current region's boundaries
        try:
            self.region = context.region
            self.region_x_min = self.region.x
            self.region_y_min = self.region.y
            self.region_x_max = self.region.x + self.region.width
            self.region_y_max = self.region.y + self.region.height
        except AttributeError:
            pass

        self.lmb_pressed = False

        # Store the active area and region when the operator is invoked
        self._active_area = context.area
        self._active_region = context.region

        self.cumulative_delta_x = 0.0  # Initialize cumulative delta tracker

        # Store the initial screen coordinates of the cursor if the property is set to True
        if prefs.lock_text_in_place:
            self.initial_screen_x = event.mouse_x
            self.initial_screen_y = event.mouse_y

        self.initial_mouse_x = event.mouse_x
        self.initial_mouse_y = event.mouse_y
        self.initial_mouse_x_offset = None

        self.adjusting_quick_anim_offset = False

        # Existing initialization code
        prefs.initial_mouse_x = event.mouse_x
        prefs.initial_frame = context.scene.frame_current
        prefs.has_dragged = False
        context.window_manager.modal_handler_add(self)

        # Store initial mouse position
        self.initial_mouse_position = (event.mouse_x, event.mouse_y)

        # Save the active region when the modal is invoked
        self._active_region = context.region

        # Hide the cursor
        context.window.cursor_modal_set("NONE")

        self.scrubbing_key = utils.find_key_for_operator("anim.amp_timeline_scrub")
        self.is_cleaning_up = False  # Initialize the cleanup flag
        self.add_draw_handler(context, event.mouse_x, event.mouse_y)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):

        if self.is_cleaning_up:
            return {"CANCELLED"}

        prefs = context.preferences.addons[base_package].preferences
        current_mode = prefs.current_mode
        mouse_x, mouse_y = event.mouse_x, event.mouse_y
        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset
        self.mouse_x, self.mouse_y = mouse_x, mouse_y
        # self.refresh_draw_handler(self.mouse_x, self.mouse_y, context)

        scrubbing_key_pressed = event.type == self.scrubbing_key and event.value == "PRESS"
        scrubbing_key_released = event.type == self.scrubbing_key and event.value == "RELEASE"

        # scrubbing_key_released = False

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self.lmb_pressed = True

        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self.lmb_pressed = False

        # Set the scrubbing mode based on the pressed key only if not in sensitivity mode
        utils.set_mode_based_on_key(context, event, self.marker_key, self.keyframe_key)

        # Activate AnimOffset quick mask
        # if event.type == prefs.quick_anim_offset_key and event.value == "PRESS":

        if anim_offset.quick_anim_offset_in_use and utils.matches_key_combination(event, prefs.quick_anim_offset_key):
            bpy.ops.anim.amp_deactivate_anim_offset()
        elif not anim_offset.quick_anim_offset_in_use and utils.matches_key_combination(
            event, prefs.quick_anim_offset_key
        ):
            bpy.ops.anim.amp_activate_anim_offset()

        if scrubbing_key_released and not self.drag_started and not prefs.toggle_for_scrubbing:
            # The scrubbing key was pressed and released without sufficient dragging
            handle_scrubbing_tap_action(self, context)
            self.finish(context)
            return {"FINISHED"}

        # If the toolbar key is released or another ending condition is met, exit
        if scrubbing_key_released and self.drag_started and not prefs.toggle_for_scrubbing:
            self.finish(context)
            return {"FINISHED"}

        # if anim_offset.mask_in_use:
        #     utils.quick_anim_offset_mask(self, context, event)

        # GUI help toggle
        # if event.type == self.gui_help_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.gui_help_key):
            utils.toggle_gui(context)
            utils.refresh_ui(context)
            self.drag_started = True

        # Adjust sensitivity based on mouse wheel events
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and prefs.use_mwheel_to_sensitivity:
            utils.change_scrub_sensitivity(self, context, event)
            self.drag_started = True
            utils.refresh_ui(context)

        if event.type in {"ESC", "RIGHTMOUSE", "RET"}:
            self.cancel(context)
            return {"CANCELLED"}

        # if not anim_offset.quick_anim_offset_in_use:

        # Toggle limit_to_active_range when 'L' key is pressed
        # if event.type == self.limit_to_range_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.limit_to_range_key):
            prefs.limit_to_active_range = not prefs.limit_to_active_range
            self.drag_started = True

        # Add marker at the current frame
        if self.drag_started and current_mode == "SCRUBBING":
            # if event.type == self.add_marker_key and event.value == "PRESS":
            if utils.matches_key_combination(event, prefs.add_marker_key):
                utils.add_marker_scrubbing(context)  # Add marker at current frame

        # Remove marker from the current frame
        if self.drag_started and current_mode == "MARKERS":
            if utils.matches_key_combination(event, prefs.remove_marker_keyframe_key, ignore_modifiers=True):
                print("deleteing marker")
                utils.remove_marker_scrubbing(context)

        # Remove keyframes from selected objects
        if self.drag_started and current_mode != "MARKERS":
            if utils.matches_key_combination(event, prefs.remove_marker_keyframe_key, ignore_modifiers=True):
                print("deleteing keyframe")
                # try:
                utils.remove_keyframe_scrubbing(context)
                # except Exception as e:
                #     pass

        # Move to the next keyframe
        if utils.matches_key_combination(event, prefs.next_keyframe_key):
            # bpy.ops.screen.keyframe_jump(next=True)  # Move to next keyframe
            bpy.ops.anim.amp_jump_to_keyframe(direction="NEXT")
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Copy pose
        if utils.matches_key_combination(event, prefs.copy_pose_key):
            if context.mode != "POSE" or (context.mode == "POSE" and event.shift):
                if hasattr(bpy.ops.transform, "amp_copy_transforms"):
                    bpy.ops.transform.amp_copy_transforms(use_world=True)

            else:
                bpy.ops.pose.copy()
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Paste pose
        if utils.matches_key_combination(event, prefs.paste_pose_key):
            if context.mode != "POSE" or (context.mode == "POSE" and event.shift):
                if hasattr(bpy.ops.transform, "amp_paste_transforms"):
                    bpy.ops.transform.amp_paste_transforms(use_world=True, use_keyframe=True, quick_paste=True)
            elif context.mode == "POSE" and event.ctrl:
                bpy.ops.anim.amp_propagate_pose_to_range()
            else:
                bpy.ops.pose.paste()
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Nudge Right
        if utils.matches_key_combination(event, prefs.scrub_nudge_key_R):
            bpy.ops.anim.timeline_anim_nudger(direction="RIGHT")
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Nudge Left
        if utils.matches_key_combination(event, prefs.scrub_nudge_key_L):
            bpy.ops.anim.timeline_anim_nudger(direction="LEFT")
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Push Right
        if utils.matches_key_combination(event, prefs.scrub_pusher_key_R):
            bpy.ops.anim.anim_pusher(operation="ADD")
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Push Left
        if utils.matches_key_combination(event, prefs.scrub_pusher_key_L):
            bpy.ops.anim.anim_pusher(operation="REMOVE")
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Move to the previous keyframe
        if utils.matches_key_combination(event, prefs.prev_keyframe_key):
            # bpy.ops.screen.keyframe_jump(next=False)  # Move to previous keyframe
            bpy.ops.anim.amp_jump_to_keyframe(direction="PREVIOUS")
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Move to the previous frame
        # if event.type == self.prev_frame_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.prev_frame_key):
            context.scene.frame_current = context.scene.frame_current - 1  # Previous frame
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Move to the next frame
        # if event.type == self.next_frame_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.next_frame_key):
            context.scene.frame_current = context.scene.frame_current + 1  # Next frame
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Insert keyframe at the current frame
        # if event.type == self.insert_keyframe_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.insert_keyframe_key):
            if event.shift:
                utils.insert_keyframe(self, context, force_insert=True)
            else:
                utils.insert_keyframe(self, context)
            self.drag_started = True

        #
        # if event.type == self.set_preview_range_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.set_preview_range_key):
            bpy.ops.anim.set_preview_range_key()
            self.drag_started = True

        # if event.type == self.breakdown_pose_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.breakdown_pose_key):
            prefs.scrubbing_error = ""
            context.window.cursor_modal_restore()
            self.finish(context)
            try:
                bpy.ops.pose.breakdown("INVOKE_DEFAULT")
            except Exception as e:
                self.report({"WARNING"}, f"Breakdowner: {str(e)}")
            return {"FINISHED"}

        # if event.type == self.blend_to_neighbor_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.blend_to_neighbor_key):
            prefs.scrubbing_error = ""
            context.window.cursor_modal_restore()
            self.finish(context)
            try:
                bpy.ops.pose.blend_to_neighbor("INVOKE_DEFAULT")
            except Exception as e:
                self.report({"WARNING"}, f"Blend to neighbor: {str(e)}")
            return {"FINISHED"}

        # if event.type == self.relax_to_breakdown_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.relax_to_breakdown_key):
            prefs.scrubbing_error = ""
            context.window.cursor_modal_restore()
            self.finish(context)
            try:
                bpy.ops.pose.relax("INVOKE_DEFAULT")
            except Exception as e:
                self.report({"WARNING"}, f"Relax ro neighbor: {str(e)}")
            return {"FINISHED"}

        # Handle play forward animation key
        if utils.matches_key_combination(event, prefs.play_animation_key) or (
            self.toggle_for_scrubbing and event.type == self.scrubbing_key and event.value == "PRESS"
        ):
            if self.is_playing and self.play_direction == "forward":
                # Stop if already playing forward
                bpy.ops.screen.animation_play()
                self.is_playing = False
                self.play_direction = "stopped"
            elif self.is_playing and self.play_direction == "reverse":
                # If playing in reverse, stop first then play forward immediately
                bpy.ops.screen.animation_play()  # Stop the reverse playback
                bpy.ops.screen.animation_play()  # Start playing forward
                self.is_playing = True
                self.play_direction = "forward"
            else:
                # Not playing, so start playing forward
                bpy.ops.screen.animation_play()
                self.is_playing = True
                self.play_direction = "forward"
            self.pause_dragging = True
            self.drag_started = True

        # Handle play reverse animation key
        # if event.type == self.play_reverse_animation_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.play_reverse_animation_key) or (
            self.toggle_for_scrubbing and event.type == self.scrubbing_key and event.value == "PRESS" and event.shift
        ):
            if self.is_playing and self.play_direction == "reverse":
                # Stop if already playing in reverse
                bpy.ops.screen.animation_play()
                self.is_playing = False
                self.play_direction = "stopped"
            elif self.is_playing and self.play_direction == "forward":
                # If playing forward, stop first then play in reverse immediately
                bpy.ops.screen.animation_play()  # Stop the forward playback
                bpy.ops.screen.animation_play(reverse=True)  # Start playing in reverse
                self.is_playing = True
                self.play_direction = "reverse"
            else:
                # Not playing, so start playing in reverse
                bpy.ops.screen.animation_play(reverse=True)
                self.is_playing = True
                self.play_direction = "reverse"
            self.pause_dragging = True
            self.drag_started = True

        # Move to the first frame of the active range
        # if event.type == self.first_frame_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.first_frame_key):
            # First frame of active range
            if context.scene.use_preview_range:
                context.scene.frame_current = context.scene.frame_preview_start
            else:
                context.scene.frame_current = context.scene.frame_start
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Move to the last frame of the active range
        # if event.type == self.last_frame_key and event.value == "PRESS":
        if utils.matches_key_combination(event, prefs.last_frame_key):
            # Last frame of active range
            if context.scene.use_preview_range:
                context.scene.frame_current = context.scene.frame_preview_end
            else:
                context.scene.frame_current = context.scene.frame_end
            self.pause_dragging = True
            self.store_mouse_pos = False
            self.drag_started = True

        # Calculate movement and check if drag started
        if event.type == "MOUSEMOVE" and not self.drag_started:
            distance_moved = (
                (event.mouse_x - self.initial_mouse_position[0]) ** 2
                + (event.mouse_y - self.initial_mouse_position[1]) ** 2
            ) ** 0.5
            if distance_moved > prefs.drag_threshold:
                # context.window.cursor_modal_set("NONE")
                self.initial_mouse_position = (self.mouse_x, self.mouse_y)
                prefs.animation_animation_ = False
                self.drag_started = True

        if event.type == "MOUSEMOVE" and self.pause_dragging:
            if not self.store_mouse_pos:
                self.snapshot_x = event.mouse_x
                self.snapshot_y = event.mouse_y
                self.store_mouse_pos = True
            else:
                distance_moved = (
                    (event.mouse_x - self.snapshot_x) ** 2 + (event.mouse_y - self.snapshot_y) ** 2
                ) ** 0.5
                if distance_moved > prefs.drag_threshold:
                    self.pause_dragging = False

        if self.lmb_needed and not self.lmb_pressed:
            # Calculate the distance from the current mouse position to the initial position
            delta_x = abs(event.mouse_x - self.initial_mouse_x)
            delta_y = abs(event.mouse_y - self.initial_mouse_y)

            # Check if the mouse has moved more than 50 pixels away in either X or Y direction
            if delta_x > 50 or delta_y > 50:
                # Move the mouse back to its initial position
                context.window.cursor_warp(self.initial_mouse_x, self.initial_mouse_y)

            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE" and self.drag_started and not self.pause_dragging:

            # Stop the animation if it was playing and handle scrubbing modes
            # if bpy.context.screen.is_animation_playing:
            #     bpy.ops.screen.animation_play()
            #     self.play_direction = "stopped"
            prefs.animation_was_playing = False

            current_frame = context.scene.frame_current
            handle_scrubbing_modes(self, context, event, current_frame)

        if not anim_offset.mask_in_use and self.mask_mouse_offset_x != 0:
            self.initial_mouse_x = self.mask_mouse_offset_x
            self.initial_mouse_y = self.mask_mouse_offset_y
            self.initial_mouse_x_offset = self.mask_mouse_offset_x

            self.mask_mouse_offset_x = 0
            self.mask_mouse_offset_y = 0

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        # self.remove_draw_handler(context)
        prefs = context.preferences.addons[base_package].preferences
        # Restore the cursor
        prefs.scrubbing_error = ""
        context.window.cursor_modal_restore()
        self.finish(context)


def AnimScrubButton(layout, context):
    prefs = context.preferences.addons[base_package].preferences
    layout.prop(
        prefs,
        "scrub_timeline_keymap_kmi_active",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_scrubber_on")
            if prefs.scrub_timeline_keymap_kmi_active
            else utils.customIcons.get_icon_id("AMP_scrubber")
        ),
        emboss=False,
    )


classes = (
    # AMP_OT_ScrubbingTapActionOperator,
    AMP_OT_scrub,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
