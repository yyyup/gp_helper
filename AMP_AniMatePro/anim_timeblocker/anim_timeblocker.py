import bpy
import gpu
import blf
import bmesh
import math
import numpy as np
import uuid
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from .. import __package__ as base_package
from .. import utils
from ..utils import ensure_alpha, get_dpi_scale
from ..utils.curve import get_nla_strip_offset, gather_fcurves
from ..utils.customIcons import get_icon


addon_keymaps = []


def graph_to_screen(context, graph_x, graph_y):
    """Convert graph coordinates to screen coordinates."""
    if not context.region or not context.region.view2d or graph_x is None or graph_y is None:
        return None, None
    region = context.region
    view2d = region.view2d

    # Handle NLA strip offset if in tweak mode
    if (
        context.active_object
        and context.active_object.animation_data
        and context.active_object.animation_data.use_tweak_mode
    ):
        screen_x, screen_y = view2d.view_to_region(
            context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x), graph_y, clip=False
        )
    else:
        screen_x, screen_y = view2d.view_to_region(graph_x, graph_y, clip=False)

    return screen_x, screen_y


def screen_to_graph(context, screen_x, screen_y):
    """Convert screen coordinates to graph coordinates."""
    region = context.region
    view2d = region.view2d
    graph_x, graph_y = view2d.region_to_view(screen_x, screen_y)

    # Handle NLA strip offset if in tweak mode
    if (
        context.active_object
        and context.active_object.animation_data
        and context.active_object.animation_data.use_tweak_mode
    ):
        return context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x, invert=True), graph_y
    else:
        return graph_x, graph_y


def get_view_bounds(context):
    """Retrieve minimum and maximum view bounds in graph space."""
    region = context.region
    view2d = region.view2d

    view_min_x, view_min_y = view2d.region_to_view(0, 0)
    view_max_x, view_max_y = view2d.region_to_view(region.width, region.height)

    return view_min_x, view_min_y, view_max_x, view_max_y


def draw_timeblocker_gui(context):
    """Global Draw Handler Function for Animation Time Blocker Tool."""

    prefs = utils.get_prefs()
    scale = get_dpi_scale()

    pin_color_source = prefs.tw_pin_color  # Reusing timewarper colors
    color_mult_normal = 0.8
    color_mult_hover = 1.5

    text_x, text_y = int(30 * scale), int(120 * scale)
    draw_gui_help_text(context, text_x, text_y)

    # Draw all handles
    for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
        try:
            handle = TimeBlocker(handle_data)

            handle_uid = handle_data.uid

            # Check if handle is hovered
            pin_color = tuple(
                c * color_mult_hover if handle_uid in AMP_OT_anim_timeblocker.hovered_handles else c * color_mult_normal
                for c in pin_color_source
            )

            handle.draw(context, pin_color)

        except Exception as e:
            print(f"Error drawing handle: {e}")
            continue


def draw_gui_help_text(context, x, y):
    """Draw GUI help text in the Graph Editor."""

    prefs = utils.get_prefs()
    scale = get_dpi_scale()

    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 5, 0, 0, 0, 1)
    blf.shadow_offset(0, int(2 * scale), int(-2 * scale))

    font_id = 0
    blf.size(font_id, int(12 * scale))

    safe_text_color = ensure_alpha(prefs.text_color)
    blf.color(0, *safe_text_color)

    if prefs.timeline_gui_toggle:
        props = context.scene.anim_timeblocker_settings
        lines = [
            "__________________________________________",
            "Anim Time Blocker Help:",
            "__________________________________________",
            "",
            "LMB Drag Handles to retime keyframes",
            "SHIFT while dragging to move handles ahead",
            "CTRL while dragging to move handles behind",
            "RMB to open options panel",
            "__________________________________________",
            f"Scope: {props.scope}",
            "__________________________________________",
        ]

        if props.tb_realtime_updates:
            lines.insert(-2, "Realtime Keyframe Updates (R) - Enabled")
        else:
            lines.insert(-2, "Realtime Keyframe Updates (R) - Disabled")

        if props.tb_snap_to_frame:
            lines.insert(-2, "Snap to Frame (F) - Enabled")
        else:
            lines.insert(-2, "Snap to Frame (F) - Disabled")

        lines.extend(
            [
                "E - Evenly distribute handles across scene range",
                "End Animation Time Blocker - (ESC, ENTER)",
                "__________________________________________",
            ]
        )

        for i, line in enumerate(reversed(lines)):
            text_width, text_height = blf.dimensions(font_id, line)
            blf.position(0, x, y, 0)
            blf.draw(0, line)
            y += text_height + int(5 * scale)
    else:
        blf.position(0, int(20 * scale), int(30 * scale), 0)
        blf.draw(0, "GUI Help (H)")

    blf.disable(0, blf.SHADOW)


class AnimTimeBlockerPin(bpy.types.PropertyGroup):
    """Property group for storing animation time blocker pin data."""

    uid: bpy.props.StringProperty(
        name="UID",
        default="",
        description="Unique identifier for each Animation Time Blocker Pin",
    )
    frame: bpy.props.FloatProperty(
        name="Frame",
        default=0.0,
        description="Frame position of the handle",
    )


class TimeBlocker:
    """Class representing a single animation time blocker."""

    def __init__(self, handle_data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scale = get_dpi_scale()
        self.handle_data = handle_data
        self.size = 25 * scale
        self.is_hovered = False
        self.is_dragging = False
        self.initial_frame = None
        self.y_offset = 60 * scale
        self.drag_offset_x = 0
        self.drag_offset_y = 0

    def get_screen_position(self, context):
        """Get the screen position of this handle."""
        if not self.handle_data or not hasattr(self.handle_data, "frame"):
            return None, None

        frame_x = self.handle_data.frame
        screen_x, _ = graph_to_screen(context, frame_x, 0)
        if screen_x is None:
            return None, None

        screen_y = self.y_offset
        return screen_x, screen_y

    def draw(self, context, color):
        """Draw the handle on screen."""
        scale = get_dpi_scale()
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        region_height = context.region.height

        screen_x, screen_y = self.get_screen_position(context)
        if screen_x is None or screen_y is None:
            return

        # Draw vertical line spanning the viewport
        line_vertices = [(screen_x, 0), (screen_x, region_height)]
        batch_line = batch_for_shader(shader, "LINES", {"pos": line_vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch_line.draw(shader)

        # Draw circle at current Y position
        circle_vertices = self._get_circle_vertices(screen_x, screen_y)
        batch_circle = batch_for_shader(shader, "TRI_FAN", {"pos": circle_vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch_circle.draw(shader)

        # Draw frame number centered in the circle
        frame_number = int(round(self.handle_data.frame))
        text = str(frame_number)

        # Configure font settings
        font_id = 0
        font_size = 8 * scale
        blf.size(font_id, font_size)
        blf.color(font_id, 1, 1, 1, 1)

        # Shadow color
        blf.enable(0, blf.SHADOW)
        blf.shadow(font_id, 5, 0, 0, 0, 0.5)
        blf.shadow_offset(font_id, int(2 * scale), int(-2 * scale))

        # Calculate text dimensions to center it
        text_width, text_height = blf.dimensions(font_id, text)

        # Position the text so that it's centered in the circle
        text_x = screen_x - text_width / 2
        text_y = screen_y - text_height / 2

        # Draw the text
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, text)

        blf.disable(0, blf.SHADOW)

    def _get_circle_vertices(self, screen_x, screen_y, num_segments=16):
        """Generate vertices for drawing a circle at screen coordinates."""
        vertices = []
        radius = self.size / 2
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = screen_x + radius * math.cos(angle)
            y = screen_y + radius * math.sin(angle)
            vertices.append((x, y))
        return vertices

    def check_hover(self, mouse_x, mouse_y, context):
        """Check if mouse is hovering over this handle."""
        if not self.handle_data:
            return False

        half_size = self.size / 2
        screen_x, screen_y = self.get_screen_position(context)

        if screen_x is None or screen_y is None:
            return False

        # Check circular hover based on current position and size
        distance = math.hypot(mouse_x - screen_x, mouse_y - screen_y)
        if distance <= half_size:
            self.is_hovered = True
            return True
        else:
            self.is_hovered = False
            return False

    def start_drag(self, mouse_x, mouse_y, context):
        """Initialize drag operation."""
        self.is_dragging = True
        # Store initial frame value - snapping will be handled by the main operator
        self.initial_frame = self.handle_data.frame

        screen_x, screen_y = self.get_screen_position(context)
        if screen_x is not None and screen_y is not None:
            self.drag_offset_x = mouse_x - screen_x
            self.drag_offset_y = mouse_y - screen_y

    def drag(self, context, mouse_x, mouse_y):
        """Update handle position during drag."""
        if not self.is_dragging:
            return

        # Convert mouse position to graph coordinates
        adjusted_mouse_x = mouse_x - self.drag_offset_x
        graph_x, _ = screen_to_graph(context, adjusted_mouse_x, mouse_y)

        if graph_x is not None:
            self.handle_data.frame = graph_x

    def end_drag(self, context):
        """End drag operation."""
        if self.is_dragging:
            self.is_dragging = False
            # Don't reset initial_frame here - let the main operator handle it
            # self.initial_frame = None


class AMP_OT_anim_timeblocker(bpy.types.Operator):
    """Animation Time Blocker Tool for retiming keyframes."""

    bl_idname = "anim.amp_anim_timeblocker"
    bl_label = "Animation Time Blocker"
    bl_options = {"REGISTER"}
    bl_description = """Animation Time Blocker Tool for retiming keyframes in the Graph Editor or Dope Sheet Editor.
RMB to open options panel."""

    scope: bpy.props.EnumProperty(
        name="Scope",
        description="Determine which keyframes are affected",
        items=[
            ("SCENE", "Scene", "Affect keyframes from the whole scene (selectable objects)"),
            ("ACTION", "Action", "Affect all fcurves in the active action"),
            (
                "SELECTED_ELEMENTS",
                "Selected Elements",
                "Apply to animation data for any selected object in Object Mode or for selected bones in Pose Mode",
            ),
            ("VISIBLE_FCURVES", "Visible FCurves", "Affect all visible (and editable) fcurves"),
            ("SELECTED_KEYS", "Selected Keys", "Affect only selected keyframes on visible fcurves"),
        ],
        default="ACTION",
    )

    # Class variables to manage state
    _is_running = False
    _handles = []
    _current_instance = None  # Store reference to running instance

    hovered_handles = set()
    dragging_handle = None
    drag_mode = "NORMAL"

    @classmethod
    def poll(cls, context):
        return (
            context.area
            and context.area.type in {"GRAPH_EDITOR"}
            and context.active_object
            and context.active_object.animation_data
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handles = []
        self.initial_keyframe_positions = {}
        self.initial_pin_positions = {}  # Store initial pin positions at drag start
        self.mouse_x = 0
        self.mouse_y = 0
        self.last_modifier_state = "NORMAL"  # Track modifier state changes

        # Undo stack management like timewarper
        self.undos = 0
        self.message = "Animation Time Blocker Active"
        self._undo_pushed = False

        # Store initial context for change detection
        self.initial_active_object = None
        self.initial_area_type = None
        self.initial_mode = None

    def invoke(self, context, event):
        if AMP_OT_anim_timeblocker._is_running:
            self.report({"WARNING"}, "Animation Time Blocker is already running")
            return {"CANCELLED"}

        # Push undo state like timewarper
        bpy.ops.ed.undo_push(message="Animation Time Blocker started")
        self.undos += 2

        # Check for animation data
        if not self._check_animation_data(context):
            self.report({"WARNING"}, "No animation data found")
            return {"CANCELLED"}

        # Initialize timewarper-style utilities
        prefs = utils.get_prefs()
        utils.amp_draw_header_handler(action="ADD", color=prefs.tw_topbar_color)
        utils.add_message(self.message)
        utils.refresh_ui(context)

        # Store initial context for change detection
        self.initial_active_object = context.active_object
        self.initial_area_type = context.area.type if context.area else None
        self.initial_mode = context.mode if hasattr(context, "mode") else None

        self.init_tool(context)

        # Add draw handler
        self._handles.append(
            bpy.types.SpaceGraphEditor.draw_handler_add(draw_timeblocker_gui, (context,), "WINDOW", "POST_PIXEL")
        )

        AMP_OT_anim_timeblocker._is_running = True
        AMP_OT_anim_timeblocker._current_instance = self  # Store reference to this instance
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return {"FINISHED"}

    def modal(self, context, event):
        prefs = utils.get_prefs()
        screen = context.screen

        # Check if context.area and context.region are valid
        if context.area is None or context.region is None:
            self.cancel(context)
            return {"CANCELLED"}

        # Check if the user switched out of the Graph Editor or Dope Sheet Editor
        if context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
            self.cancel(context)
            return {"CANCELLED"}

        if not AMP_OT_anim_timeblocker._is_running:
            return {"CANCELLED"}

        context.area.tag_redraw()

        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y

        # Update hover states
        self.update_hover(context, self.mouse_x, self.mouse_y)

        # Handle ESC during animation playback
        if event.type == "ESC" and event.value == "PRESS" and screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
            return {"RUNNING_MODAL"}

        # Handle events
        elif event.type in {"RET", "ESC"} and event.value == "PRESS":
            self.cancel(context)
            return {"FINISHED"}

        elif event.type == "RIGHTMOUSE" and event.value == "PRESS" and event.shift:
            # SHIFT+RMB cancels like timewarper
            if event.value == "RELEASE" and event.shift:
                self.cancel(context)
            return {"RUNNING_MODAL"}

        elif event.type == "RIGHTMOUSE" and event.value == "PRESS":
            # Regular RMB - show panel popup like timewarper
            bpy.ops.wm.call_panel(name="AMP_PT_AnimTimeBlockerOptions", keep_open=True)
            context.window.cursor_modal_set("DEFAULT")
            return {"RUNNING_MODAL"}

        elif event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                self.handle_click(context, event)
            elif event.value == "RELEASE":
                self.handle_release(context, event)
            return {"RUNNING_MODAL"}

        elif event.type == "MOUSEMOVE":
            if self.dragging_handle:
                self.handle_drag(context, event)
            return {"RUNNING_MODAL"}

        elif event.type in {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL"}:
            # Handle immediate modifier key changes during drag
            if self.dragging_handle and event.value in {"PRESS", "RELEASE"}:
                self.handle_modifier_change(context, event)
            return {"RUNNING_MODAL"}

        elif event.type == "R" and event.value == "PRESS":
            # Toggle realtime updates
            props = context.scene.anim_timeblocker_settings
            props.tb_realtime_updates = not props.tb_realtime_updates
            return {"RUNNING_MODAL"}

        elif event.type == "F" and event.value == "PRESS":
            # Toggle snap to frame
            props = context.scene.anim_timeblocker_settings
            props.tb_snap_to_frame = not props.tb_snap_to_frame
            return {"RUNNING_MODAL"}

        elif event.type == "H" and event.value == "PRESS":
            # Toggle help display
            prefs = utils.get_prefs()
            prefs.timeline_gui_toggle = not prefs.timeline_gui_toggle
            return {"RUNNING_MODAL"}

        elif event.type == "E" and event.value == "PRESS":
            # Evenly distribute handles across scene frame range
            self.evenly_distribute_handles(context)
            return {"RUNNING_MODAL"}

        elif event.type == "Z" and event.value == "PRESS" and (event.ctrl or event.oskey):
            # Handle undo during operation - matches timewarper exactly
            self._undo_pushed = True

            if self.undos > 2:
                self.undos -= 1
                bpy.ops.ed.undo()
                return {"RUNNING_MODAL"}
            else:
                return {"RUNNING_MODAL"}

        # MMB and scroll wheel passthrough
        elif event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
            return {"PASS_THROUGH"}

        # Handle undo stack management - matches timewarper
        if self._undo_pushed:
            self.update_handles(context)
            self.restore_state(context)
            self._undo_pushed = False

        return {"PASS_THROUGH"}

    def _context_changed(self, context):
        """Check if significant context changes occurred that should cancel the modal."""
        # Check if active object changed
        if context.active_object != self.initial_active_object:
            return True

        # Check if mode changed (Object/Edit/Pose mode switches)
        current_mode = context.mode if hasattr(context, "mode") else None
        if current_mode != self.initial_mode:
            return True

        # Check if area type changed (should be caught by earlier check, but double-check)
        current_area_type = context.area.type if context.area else None
        if current_area_type != self.initial_area_type:
            return True

        # Check if active object lost its animation data
        if self.initial_active_object and context.active_object:
            if not context.active_object.animation_data:
                return True

        # Check if we're no longer in a valid animation context
        if not self._check_animation_data(context):
            return True

        return False

    def snap_frame(self, frame_x):
        """Snap frame to nearest integer if snap is enabled."""
        props = bpy.context.scene.anim_timeblocker_settings
        if props.tb_snap_to_frame:
            return round(frame_x)
        return frame_x

    def handle_click(self, context, event):
        """Handle mouse click events."""
        # Check for modifiers
        if event.shift:
            self.drag_mode = "MOVE_AHEAD"
            self.last_modifier_state = "MOVE_AHEAD"
        elif event.ctrl:
            self.drag_mode = "MOVE_BEHIND"
            self.last_modifier_state = "MOVE_BEHIND"
        else:
            self.drag_mode = "NORMAL"
            self.last_modifier_state = "NORMAL"

        # Find handle at mouse position
        handle = self.get_handle_at_position(self.mouse_x, self.mouse_y, context)
        if handle:
            self.dragging_handle = handle
            handle.start_drag(self.mouse_x, self.mouse_y, context)

            # Store initial state of ALL handles and keyframes at drag start
            self.store_initial_state(context)

            # Ensure the dragging handle's initial frame is also snapped for consistency
            if hasattr(handle, "initial_frame"):
                handle.initial_frame = self.snap_frame(handle.initial_frame)

    def handle_release(self, context, event):
        """Handle mouse release events."""
        if self.dragging_handle:
            self.dragging_handle.end_drag(context)

            # Apply final keyframe updates if realtime was disabled
            props = context.scene.anim_timeblocker_settings
            if not props.tb_realtime_updates:
                self.update_keyframe_positions(context)

            # Check for overlapping handles and merge them
            self.merge_overlapping_handles(context)

            # Update all fcurves to ensure keyframes are properly merged
            self.refresh_fcurves(context)

            # Push undo for the completed drag operation like timewarper
            self.tb_push_undo()

            # Reset drag state
            self.dragging_handle = None
            self.drag_mode = "NORMAL"
            self.last_modifier_state = "NORMAL"
            self.clear_initial_state()

            # Reset the initial frame for the dragged handle
            for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
                handle = TimeBlocker(handle_data)
                handle.initial_frame = None

    def merge_overlapping_handles(self, context):
        """Merge handles that are on the same frame after dragging."""
        handles_to_remove = []
        frame_tolerance = 0.5

        pins = list(context.scene.anim_timeblocker_settings.timeblocker_pins)

        for i, handle_a in enumerate(pins):
            for j, handle_b in enumerate(pins[i + 1 :], i + 1):
                # Check if handles are on the same frame (within tolerance)
                if abs(handle_a.frame - handle_b.frame) < frame_tolerance:
                    # Mark the second handle for removal (keep the first one)
                    handles_to_remove.append(j)

        # Remove duplicate handles (sort in reverse order to maintain indices)
        for idx in sorted(set(handles_to_remove), reverse=True):
            context.scene.anim_timeblocker_settings.timeblocker_pins.remove(idx)

    def refresh_fcurves(self, context):
        """Refresh all fcurves to ensure keyframes are properly sorted and merged."""
        fcurves = self.get_fcurves_by_scope(context)

        for fcurve in fcurves:
            # Update the fcurve to ensure keyframes are sorted by frame
            try:
                fcurve.update()
            except:
                pass

            # Force keyframe sorting by frame position
            keyframes = list(fcurve.keyframe_points)
            keyframes.sort(key=lambda kf: kf.co[0])

        # Trigger area redraw
        context.area.tag_redraw()

    def handle_drag(self, context, event):
        """Handle mouse drag events."""
        if not self.dragging_handle:
            return

        # Update handle position during drag
        old_frame = self.dragging_handle.handle_data.frame
        self.dragging_handle.drag(context, self.mouse_x, self.mouse_y)

        # Apply snapping
        new_frame = self.snap_frame(self.dragging_handle.handle_data.frame)
        self.dragging_handle.handle_data.frame = new_frame

        # Calculate movement direction and update affected handles
        if hasattr(self.dragging_handle, "initial_frame") and self.dragging_handle.initial_frame is not None:
            movement_direction = new_frame - self.dragging_handle.initial_frame
            self.update_affected_handles_with_direction(context, movement_direction)

        # Update keyframes if realtime is enabled
        props = context.scene.anim_timeblocker_settings
        if props.tb_realtime_updates:
            self.update_keyframe_positions_during_drag(context)

    def handle_modifier_change(self, context, event):
        """Handle immediate modifier key changes during drag - triggers pin reset."""
        if not self.dragging_handle:
            return

        # Determine current modifier state based on actual key states
        current_modifier_state = "NORMAL"
        if event.shift:
            current_modifier_state = "MOVE_AHEAD"
        elif event.ctrl:
            current_modifier_state = "MOVE_BEHIND"

        # If modifier state changed, restore all handles to initial positions
        # and apply new logic immediately - NO undo push here, only on drag release
        if current_modifier_state != self.last_modifier_state:
            self.restore_handles_to_initial_state(context)
            self.drag_mode = current_modifier_state
            self.last_modifier_state = current_modifier_state

            # Immediately update affected handles based on current position and new mode
            # Use the current snapped position of the dragging handle to ensure consistency
            if hasattr(self.dragging_handle, "initial_frame") and self.dragging_handle.initial_frame is not None:
                current_frame = self.snap_frame(self.dragging_handle.handle_data.frame)
                self.dragging_handle.handle_data.frame = current_frame  # Ensure main handle is also snapped
                # Use the snapped initial frame for consistent offset calculation
                movement_direction = current_frame - self.dragging_handle.initial_frame
                self.update_affected_handles_with_direction(context, movement_direction)

            # Update keyframes if realtime is enabled
            props = context.scene.anim_timeblocker_settings
            if props.tb_realtime_updates:
                self.update_keyframe_positions_during_drag(context)

    def update_hover(self, context, mouse_x, mouse_y):
        """Update hover states for all handles."""
        # Reset cursor to default like timewarper
        bpy.context.window.cursor_set("DEFAULT")
        self.hovered_handles.clear()

        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            handle = TimeBlocker(handle_data)
            if handle.check_hover(mouse_x, mouse_y, context):
                self.hovered_handles.add(handle_data.uid)
                # Set cursor to hand when hovering over handles
                bpy.context.window.cursor_set("HAND")

    def get_handle_at_position(self, x, y, context):
        """Get handle at given screen position."""
        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            handle = TimeBlocker(handle_data)
            if handle.check_hover(x, y, context):
                return handle
        return None

    def update_keyframe_positions_during_drag(self, context):
        """Update keyframe positions during continuous dragging with advanced SHIFT/CTRL logic."""
        if not self.dragging_handle or not hasattr(self, "initial_keyframe_positions"):
            return

        # Get all affected handles (including the dragged one)
        affected_handles = [self.dragging_handle.handle_data]

        # Add other handles based on drag mode and direction
        if self.drag_mode != "NORMAL":
            for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
                if handle_data.uid != self.dragging_handle.handle_data.uid:
                    affected_handles.append(handle_data)

        # Update keyframes for each affected handle
        fcurves = self.get_fcurves_by_scope(context)
        for fcurve in fcurves:
            if fcurve not in self.initial_keyframe_positions:
                continue

            initial_positions = self.initial_keyframe_positions[fcurve]

            for i, keyframe in enumerate(fcurve.keyframe_points):
                if i >= len(initial_positions):
                    continue

                initial_pos = initial_positions[i]
                initial_frame_pos = initial_pos["co"][0]

                # Find which handle this keyframe belongs to and calculate offset
                keyframe_moved = False
                for handle_data in affected_handles:
                    if handle_data.uid in self.initial_pin_positions:
                        initial_handle_frame = self.initial_pin_positions[handle_data.uid]
                        current_handle_frame = handle_data.frame

                        # Check if this keyframe is at this handle's position
                        if abs(initial_frame_pos - initial_handle_frame) < 0.5:
                            frame_offset = current_handle_frame - initial_handle_frame

                            # Update keyframe position
                            keyframe.co[0] = initial_pos["co"][0] + frame_offset
                            keyframe.handle_left[0] = initial_pos["handle_left"][0] + frame_offset
                            keyframe.handle_right[0] = initial_pos["handle_right"][0] + frame_offset
                            keyframe_moved = True
                            break

                # If no handle moved this keyframe, restore it to initial position
                if not keyframe_moved and self.drag_mode != "NORMAL":
                    keyframe.co[0] = initial_pos["co"][0]
                    keyframe.handle_left[0] = initial_pos["handle_left"][0]
                    keyframe.handle_right[0] = initial_pos["handle_right"][0]

    def update_keyframe_positions(self, context):
        """Update keyframe positions based on handle movements."""
        if not self.dragging_handle or not hasattr(self, "initial_keyframe_positions"):
            return

        old_frame = self.dragging_handle.initial_frame
        new_frame = self.dragging_handle.handle_data.frame

        if old_frame is None or old_frame == new_frame:
            return

        frame_offset = new_frame - old_frame

        # Get keyframes to move based on scope and drag mode
        keyframes_to_move = self.get_keyframes_at_frame(context, old_frame)

        # Handle different drag modes
        if self.drag_mode == "MOVE_AHEAD":
            # Move all keyframes from this frame onwards
            keyframes_to_move.extend(self.get_keyframes_after_frame(context, old_frame))
        elif self.drag_mode == "MOVE_BEHIND":
            # Move all keyframes from this frame backwards
            keyframes_to_move.extend(self.get_keyframes_before_frame(context, old_frame))

        # Apply the movement
        for fcurve, keyframe_idx in keyframes_to_move:
            try:
                fcurve.keyframe_points[keyframe_idx].co[0] += frame_offset
                fcurve.keyframe_points[keyframe_idx].handle_left[0] += frame_offset
                fcurve.keyframe_points[keyframe_idx].handle_right[0] += frame_offset
            except (IndexError, AttributeError):
                continue

    def get_keyframes_at_frame(self, context, frame):
        """Get all keyframes at the specified frame based on current scope."""
        keyframes = []
        fcurves = self.get_fcurves_by_scope(context)

        for fcurve in fcurves:
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if abs(keyframe.co[0] - frame) < 0.5:  # Tolerance for frame matching
                    keyframes.append((fcurve, i))

        return keyframes

    def get_keyframes_after_frame(self, context, frame):
        """Get all keyframes after the specified frame."""
        keyframes = []
        fcurves = self.get_fcurves_by_scope(context)

        for fcurve in fcurves:
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.co[0] > frame:
                    keyframes.append((fcurve, i))

        return keyframes

    def get_keyframes_before_frame(self, context, frame):
        """Get all keyframes before the specified frame."""
        keyframes = []
        fcurves = self.get_fcurves_by_scope(context)

        for fcurve in fcurves:
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.co[0] < frame:
                    keyframes.append((fcurve, i))

        return keyframes

    def get_fcurves_by_scope(self, context):
        """Get fcurves based on the current scope setting using unified curve utilities."""
        props = context.scene.anim_timeblocker_settings

        # Use the unified gather_fcurves method from utils.curve
        fcurves = gather_fcurves(props.scope, context)

        return list(fcurves)

    def update_affected_handles_during_drag(self, context, reference_frame, frame_offset):
        """Update handles that are affected by drag modes during continuous dragging."""
        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            if handle_data == self.dragging_handle.handle_data:
                continue

            # Get the initial position of this handle
            initial_frame = None
            for stored_fcurve, positions in self.initial_keyframe_positions.items():
                # Try to find the initial frame for this handle by checking stored positions
                # This is a simplified approach - in a real implementation you might want to store handle initial positions separately
                pass

            # For now, update based on current position relative to reference
            if self.drag_mode == "MOVE_AHEAD" and handle_data.frame > reference_frame:
                # Find the original position and apply offset
                original_frame = handle_data.frame - frame_offset
                if original_frame > reference_frame - 0.5:
                    handle_data.frame = original_frame + frame_offset
            elif self.drag_mode == "MOVE_BEHIND" and handle_data.frame < reference_frame:
                # Find the original position and apply offset
                original_frame = handle_data.frame - frame_offset
                if original_frame < reference_frame + 0.5:
                    handle_data.frame = original_frame + frame_offset

    def update_affected_handles(self, context, reference_frame, frame_offset):
        """Update handles that are affected by drag modes."""
        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            if handle_data == self.dragging_handle.handle_data:
                continue

            if self.drag_mode == "MOVE_AHEAD" and handle_data.frame > reference_frame:
                handle_data.frame += frame_offset
            elif self.drag_mode == "MOVE_BEHIND" and handle_data.frame < reference_frame:
                handle_data.frame += frame_offset

    def init_tool(self, context):
        """Initialize the animation time blocker tool."""
        self.clear_handles(context)
        self.create_handles_from_keyframes(context)

    def clear_handles(self, context):
        """Clear all existing handles."""
        context.scene.anim_timeblocker_settings.timeblocker_pins.clear()

    def create_handles_from_keyframes(self, context):
        """Create handles at keyframe positions based on current scope."""
        props = context.scene.anim_timeblocker_settings
        keyframe_frames = set()

        # Get all unique frame positions with keyframes
        fcurves = self.get_fcurves_by_scope(context)
        for fcurve in fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe_frames.add(int(round(keyframe.co[0])))

        # Create handles for each unique frame
        for frame in sorted(keyframe_frames):
            handle_data = context.scene.anim_timeblocker_settings.timeblocker_pins.add()
            handle_data.uid = str(uuid.uuid4())
            handle_data.frame = float(frame)

    def store_initial_keyframe_positions(self, context):
        """Store initial keyframe positions for undo functionality."""
        self.initial_keyframe_positions = {}
        fcurves = self.get_fcurves_by_scope(context)

        for fcurve in fcurves:
            fcurve_positions = []
            for keyframe in fcurve.keyframe_points:
                fcurve_positions.append(
                    {
                        "co": keyframe.co.copy(),
                        "handle_left": keyframe.handle_left.copy(),
                        "handle_right": keyframe.handle_right.copy(),
                    }
                )
            self.initial_keyframe_positions[fcurve] = fcurve_positions

    def clear_initial_keyframe_positions(self):
        """Clear stored initial keyframe positions."""
        self.initial_keyframe_positions = {}

    def store_initial_state(self, context):
        """Store initial state of all handles and keyframes at drag start."""
        # Store initial pin positions with consistent snapping
        self.initial_pin_positions = {}
        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            # Store snapped positions to ensure consistency throughout drag operation
            snapped_frame = self.snap_frame(handle_data.frame)
            self.initial_pin_positions[handle_data.uid] = snapped_frame
            # Also update the actual handle position to match snapped value
            handle_data.frame = snapped_frame

        # Store initial keyframe positions
        self.store_initial_keyframe_positions(context)

    def clear_initial_state(self):
        """Clear all stored initial state."""
        self.initial_pin_positions = {}
        self.clear_initial_keyframe_positions()

    def restore_handles_to_initial_state(self, context):
        """Restore all handles except the dragged one to their initial positions."""
        if not self.initial_pin_positions or not self.dragging_handle:
            return

        # Restore all handles except the one being dragged
        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            if handle_data.uid != self.dragging_handle.handle_data.uid:
                if handle_data.uid in self.initial_pin_positions:
                    handle_data.frame = self.initial_pin_positions[handle_data.uid]

    def update_affected_handles_with_direction(self, context, movement_direction):
        """Update handles that should move with the active handle based on direction and mode."""
        if not self.dragging_handle or self.drag_mode == "NORMAL":
            return

        active_handle = self.dragging_handle.handle_data
        current_frame = active_handle.frame

        # Calculate the offset from initial position
        if hasattr(self.dragging_handle, "initial_frame") and self.dragging_handle.initial_frame is not None:
            frame_offset = current_frame - self.dragging_handle.initial_frame
        else:
            return

        # Reset all non-dragging handles to their initial positions first
        for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
            if handle_data.uid != active_handle.uid and handle_data.uid in self.initial_pin_positions:
                handle_data.frame = self.initial_pin_positions[handle_data.uid]

        # Now apply the movement logic based on mode and current offset position
        if self.drag_mode == "MOVE_AHEAD":
            # SHIFT: Move all handles ahead in the direction of movement
            if frame_offset > 0:  # Moving right from initial position
                # Move all handles to the right of the initial position
                for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
                    if (
                        handle_data.uid != active_handle.uid
                        and handle_data.uid in self.initial_pin_positions
                        and self.initial_pin_positions[handle_data.uid] > self.dragging_handle.initial_frame
                    ):
                        new_frame = self.initial_pin_positions[handle_data.uid] + frame_offset
                        handle_data.frame = self.snap_frame(new_frame)
            elif frame_offset < 0:  # Moving left from initial position
                # Move all handles to the left of the initial position
                for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
                    if (
                        handle_data.uid != active_handle.uid
                        and handle_data.uid in self.initial_pin_positions
                        and self.initial_pin_positions[handle_data.uid] < self.dragging_handle.initial_frame
                    ):
                        new_frame = self.initial_pin_positions[handle_data.uid] + frame_offset
                        handle_data.frame = self.snap_frame(new_frame)

        elif self.drag_mode == "MOVE_BEHIND":
            # CTRL: Move all handles behind the movement (opposite direction)
            if frame_offset > 0:  # Moving right, so move handles to the left
                for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
                    if (
                        handle_data.uid != active_handle.uid
                        and handle_data.uid in self.initial_pin_positions
                        and self.initial_pin_positions[handle_data.uid] < self.dragging_handle.initial_frame
                    ):
                        new_frame = self.initial_pin_positions[handle_data.uid] + frame_offset
                        handle_data.frame = self.snap_frame(new_frame)
            elif frame_offset < 0:  # Moving left, so move handles to the right
                for handle_data in context.scene.anim_timeblocker_settings.timeblocker_pins:
                    if (
                        handle_data.uid != active_handle.uid
                        and handle_data.uid in self.initial_pin_positions
                        and self.initial_pin_positions[handle_data.uid] > self.dragging_handle.initial_frame
                    ):
                        new_frame = self.initial_pin_positions[handle_data.uid] + frame_offset
                        handle_data.frame = self.snap_frame(new_frame)

    def evenly_distribute_handles(self, context):
        """Evenly distribute handles across the scene frame range or preview range."""
        scene = context.scene

        # Check if preview range is enabled
        if scene.use_preview_range:
            # Use preview range
            frame_start = scene.frame_preview_start
            frame_end = scene.frame_preview_end

            # Get all handles
            all_handles = list(context.scene.anim_timeblocker_settings.timeblocker_pins)

            # Filter handles that are within the preview range (including at boundaries)
            handles = [h for h in all_handles if frame_start <= h.frame <= frame_end]

            if len(handles) < 3:
                self.report({"WARNING"}, "Need at least 3 handles within the preview range to distribute evenly")
                return
        else:
            # Use scene frame range
            frame_start = scene.frame_start
            frame_end = scene.frame_end

            # Get all handles
            handles = list(context.scene.anim_timeblocker_settings.timeblocker_pins)

            if len(handles) < 3:
                self.report({"WARNING"}, "Need at least 3 handles to distribute evenly")
                return

        # Sort handles by their CURRENT frame position before distributing
        handles.sort(key=lambda h: h.frame)

        # Snapshot the CURRENT state just before distribution
        # This captures the current positions, not the original initialization positions
        current_keyframe_positions = {}
        fcurves = self.get_fcurves_by_scope(context)
        for fcurve in fcurves:
            fcurve_positions = []
            for keyframe in fcurve.keyframe_points:
                fcurve_positions.append(
                    {
                        "co": keyframe.co.copy(),
                        "handle_left": keyframe.handle_left.copy(),
                        "handle_right": keyframe.handle_right.copy(),
                    }
                )
            current_keyframe_positions[fcurve] = fcurve_positions

        # Store current handle positions before distribution for reference
        pre_distribution_positions = {}
        for handle_data in handles:
            pre_distribution_positions[handle_data.uid] = handle_data.frame

        # Calculate even distribution
        if len(handles) == 1:
            # Single handle goes to the middle
            new_frame = float((frame_start + frame_end) // 2)
            handles[0].frame = new_frame
        else:
            # Multiple handles: first on frame_start, last on frame_end, rest evenly spaced
            frame_range = frame_end - frame_start

            step = frame_range / (len(handles) - 1)

            for i, handle_data in enumerate(handles):
                if i == 0:
                    # First handle on first frame
                    new_frame = float(frame_start)
                elif i == len(handles) - 1:
                    # Last handle on last frame
                    new_frame = float(frame_end)
                else:
                    # Intermediate handles evenly spaced and rounded to nearest frame
                    new_frame = round(frame_start + (step * i))

                handle_data.frame = float(new_frame)

        # Move keyframes to match the new handle positions
        # Use the current keyframe positions, not the initial ones from drag start
        # When preview range is active, only move keyframes for handles that were within the range
        for fcurve in fcurves:
            if fcurve not in current_keyframe_positions:
                continue

            current_positions = current_keyframe_positions[fcurve]

            for i, keyframe in enumerate(fcurve.keyframe_points):
                if i >= len(current_positions):
                    continue

                current_pos = current_positions[i]
                current_frame_pos = current_pos["co"][0]

                # Find which handle this keyframe belongs to and calculate offset
                for handle_data in handles:
                    if handle_data.uid in pre_distribution_positions:
                        pre_handle_frame = pre_distribution_positions[handle_data.uid]
                        new_handle_frame = handle_data.frame

                        # Check if this keyframe is at this handle's pre-distribution position
                        if abs(current_frame_pos - pre_handle_frame) < 0.5:
                            frame_offset = new_handle_frame - pre_handle_frame

                            # Update keyframe position
                            keyframe.co[0] = current_pos["co"][0] + frame_offset
                            keyframe.handle_left[0] = current_pos["handle_left"][0] + frame_offset
                            keyframe.handle_right[0] = current_pos["handle_right"][0] + frame_offset
                            break

        # Push undo for the completed distribution operation like timewarper
        self.tb_push_undo()

        # Trigger redraw to show updated positions
        if context.area:
            context.area.tag_redraw()

    def cancel(self, context):
        """Cancel the animation time blocker tool."""
        AMP_OT_anim_timeblocker._is_running = False
        AMP_OT_anim_timeblocker._current_instance = None  # Clear instance reference

        # Remove draw handlers
        for handle in self._handles:
            try:
                bpy.types.SpaceGraphEditor.draw_handler_remove(handle, "WINDOW")
            except ValueError:
                pass
        self._handles.clear()

        # Clear handles
        self.clear_handles(context)

        # Clean up undo stack like timewarper
        utils.amp_draw_header_handler(action="REMOVE")
        utils.remove_message()
        utils.refresh_ui(context)

        # Reset cursor like timewarper
        bpy.context.window.cursor_set("DEFAULT")

        # Clean up excess undo states
        for i in range(self.undos):
            bpy.ops.ed.undo_push(message="IGNORE")

        # Only tag redraw if area is still valid
        if context.area:
            context.area.tag_redraw()

    def update_handles(self, context):
        """Update handles by re-reading from scene data - equivalent to timewarper's update_elements."""
        # This method is called after undo to refresh internal state
        # Since timeblocker creates handles dynamically, we just trigger a redraw
        # Only tag redraw if area is still valid
        if context.area:
            context.area.tag_redraw()

    def restore_state(self, context):
        """Restore state after undo - equivalent to timewarper's restore_state."""
        # Re-initialize the tool to match current scene state
        # This ensures handles are recreated from current keyframe positions
        self.clear_handles(context)
        self.create_handles_from_keyframes(context)
        # Only tag redraw if area is still valid
        if context.area:
            context.area.tag_redraw()

    def tb_push_undo(self):
        """Push undo immediately like timewarper."""
        bpy.ops.ed.undo_push(message="Animation Time Blocker saved state")
        self.undos += 1

    def _check_animation_data(self, context):
        """Check if there's animation data available."""
        if context.active_object and context.active_object.animation_data:
            if context.active_object.animation_data.action:
                return True

        # Check for any animation data in the scene
        for obj in context.scene.objects:
            if obj.animation_data and obj.animation_data.action:
                return True

        return False


class AMP_PT_AnimTimeBlockerOptions(bpy.types.Panel):
    """Panel for animation time blocker options - identical to timewarper."""

    bl_label = ""
    bl_idname = "AMP_PT_AnimTimeBlockerOptions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        props = context.scene.anim_timeblocker_settings

        layout.label(text="Animation Time Blocker", icon="TIME")
        layout.separator()

        layout.prop(props, "scope", text="Scope")
        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "tb_realtime_updates", text="Realtime Updates")
        col.prop(props, "tb_snap_to_frame", text="Snap to Frame")

        layout.separator()

        # Add information section like timewarper
        layout.label(text="Controls:", icon="INFO")
        layout.label(text="LMB Drag: Move handles")
        layout.label(text="SHIFT + Drag: Move handles ahead")
        layout.label(text="CTRL + Drag: Move handles behind")
        layout.label(text="E: Evenly distribute handles")
        layout.label(text="R: Toggle realtime updates")
        layout.label(text="F: Toggle snap to frame")
        layout.label(text="H: Toggle help display")
        layout.label(text="ESC/ENTER: Exit tool")


def update_scope(self, context):
    """Update scope and recreate handles when scope changes."""
    # Use direct reference to running instance instead of searching
    if AMP_OT_anim_timeblocker._current_instance is not None:
        op = AMP_OT_anim_timeblocker._current_instance
        # Push undo state before changing scope like timewarper
        op.tb_push_undo()
        # Recreate handles based on new scope
        op.init_tool(context)
        # Trigger redraw to show new handles
        if context.area:
            context.area.tag_redraw()


class AMP_PG_AnimTimeBlockerSettings(bpy.types.PropertyGroup):
    """Property group for animation time blocker settings."""

    scope: bpy.props.EnumProperty(
        name="Scope",
        description="Scope of the Animation Time Blocker tool",
        items=(
            ("SCENE", "Scene", "Apply to keyframes in the entire scene"),
            ("ACTION", "Action", "Apply to all fcurves in the active action"),
            (
                "SELECTED_ELEMENTS",
                "Selected Elements",
                "Apply to animation data for any selected object in Object Mode or for selected bones in Pose Mode",
            ),
            ("VISIBLE_FCURVES", "Visible FCurves", "Apply to all visible fcurves"),
            ("SELECTED_KEYS", "Selected Keys", "Apply to selected keyframes on visible fcurves"),
        ),
        default="ACTION",
        update=update_scope,
    )
    tb_realtime_updates: bpy.props.BoolProperty(
        name="Realtime Updates", default=True, description="Update keyframes in real-time while dragging handles"
    )
    tb_snap_to_frame: bpy.props.BoolProperty(
        name="Snap Frames", default=True, description="Snap handles to integer frame values"
    )
    timeblocker_pins: bpy.props.CollectionProperty(
        type=AnimTimeBlockerPin, description="Collection of animation time blocker pins"
    )


classes = (
    AnimTimeBlockerPin,
    AMP_OT_anim_timeblocker,
    AMP_PT_AnimTimeBlockerOptions,
    AMP_PG_AnimTimeBlockerSettings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.anim_timeblocker_settings = bpy.props.PointerProperty(type=AMP_PG_AnimTimeBlockerSettings)


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Scene, "anim_timeblocker_settings"):
        del bpy.types.Scene.anim_timeblocker_settings


if __name__ == "__main__":
    register()
