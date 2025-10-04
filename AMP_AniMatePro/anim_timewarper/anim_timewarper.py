import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
import math
from mathutils import Vector
import uuid
import numpy as np
import re
from .. import __package__ as base_package
from .. import utils
from ..utils import ensure_alpha, get_dpi_scale
from ..utils.curve import get_nla_strip_offset
from ..utils.customIcons import get_icon


addon_keymaps = []


def graph_to_screen(context, graph_x, graph_y):
    if not context.region or not context.region.view2d or graph_x is None or graph_y is None:
        return float("inf"), float("inf")
    region = context.region
    view2d = region.view2d
    screen_x, screen_y = view2d.view_to_region(
        context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x), graph_y, clip=False
    )

    return screen_x, screen_y


def screen_to_graph(context, screen_x, screen_y):
    region = context.region
    view2d = region.view2d
    graph_x, graph_y = view2d.region_to_view(screen_x, screen_y)

    return context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x, invert=True), graph_y


def get_view_bounds(context):
    """Retrieve minimum and maximum view bounds in graph space."""
    region = context.region
    view2d = region.view2d

    view_min_x, view_min_y = view2d.region_to_view(0, 0)
    view_max_x, view_max_y = view2d.region_to_view(region.width, region.height)

    return view_min_x, view_min_y, view_max_x, view_max_y


def ease_in_exponential(t):
    """Exponential ease-in function that handles scalar and array inputs."""
    t = np.asarray(t)
    return np.where(t == 0, 0.0, np.power(2, 10 * t - 10))


def ease_out_exponential(t):
    """Exponential ease-out function that handles scalar and array inputs."""
    t = np.asarray(t)
    return np.where(t == 1, 1.0, 1.0 - np.power(2, -10 * t))


def draw_timewarp_gui(context):
    """Global Draw Handler Function for Time Warp Tool."""

    prefs = context.preferences.addons[base_package].preferences

    pin_color_source = prefs.tw_pin_color
    bar_color_source = prefs.tw_bar_color
    easing_color_source = prefs.tw_easing_color

    color_mult_normal = 0.8
    color_mult_hover = 1.5

    text_x, text_y = 30, 120
    draw_gui_help_text(context, text_x, text_y)

    for pin_data in context.scene.timewarper_settings.timewarp_pins:

        try:
            pin = Pin(pin_data)

            color = tuple(
                c * color_mult_hover if pin_data.uid in AMP_OT_timewarp.hovered_pins else c * color_mult_normal
                for c in pin_color_source
            )
            pin.draw(context, color)
        except Exception as e:
            print(f"[ERROR] Failed to draw Pin UID: {pin_data.uid} - {e}")

    sorted_pins = sorted(context.scene.timewarper_settings.timewarp_pins, key=lambda p: p.position[0])

    for i in range(len(sorted_pins) - 1):
        start_pin = Pin(sorted_pins[i])
        end_pin = Pin(sorted_pins[i + 1])

        bar = Bar(start_pin, end_pin)

        bar_uid = f"{start_pin.pin_data.uid}"

        bar_color = tuple(
            c * color_mult_hover if bar_uid in AMP_OT_timewarp.hovered_bars else c * color_mult_normal
            for c in bar_color_source
        )

        bar.draw(context, bar_color)

        if i < len(context.scene.timewarper_settings.timewarp_easings):
            easing_data = context.scene.timewarper_settings.timewarp_easings[i]
            easing = Easing(easing_data, start_pin, end_pin, None)
            easing_color = tuple(
                c * color_mult_hover if easing_data.uid in AMP_OT_timewarp.hovered_easings else c * color_mult_normal
                for c in easing_color_source
            )
            easing.draw(context, easing_color)


def draw_gui_help_text(context, x, y):
    """Draw GUI help text in the Graph Editor."""

    prefs = bpy.context.preferences.addons[base_package].preferences

    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 5, 0, 0, 0, 1)
    blf.shadow_offset(0, 2, -2)

    font_id = 0
    blf.size(font_id, 12)

    safe_text_color = ensure_alpha(prefs.text_color)
    blf.color(0, *safe_text_color)

    if prefs.timeline_gui_toggle:
        props = context.scene.timewarper_settings
        lines = [
            "__________________________________________",
            "Anim Time Warper Help:",
            "__________________________________________",
            "",
            "LMB Drag Pins or Bars to move",
            "SHIFT while dragging to move pins ahead",
            "CTRL while dragging to move pins behind",
            "__________________________________________",
            "Realtime Keyframe Updates (R) - Enabled",
            "Snap to Frame (F) - Enabled",
            "__________________________________________",
            "Add Pins at selected keyframes (SHIFT A)",
            "or at mouse location if none selected",
            "Add Pin at current frame (ALT A)",
            "Delete Pin under mouse (SHIFT X)",
            "Delete All Pins (ALT X) ",
            "__________________________________________",
            "End Time Warper - (ESC, ENTER)",
            "__________________________________________",
        ]

        if props.tw_realtime_updates:
            lines[8] = "Realtime Keyframe Updates (R) - Enabled"
        else:
            lines[8] = "Realtime Keyframe Updates (R) - Disabled"

        if props.tw_snap_to_frame:
            lines[9] = "Snap to Frame (F) - Enabled"
        else:
            lines[9] = "Snap to Frame (F) - Disabled"

        for line in reversed(lines):
            text_width, text_height = blf.dimensions(font_id, line)
            blf.position(font_id, x, y, 0)
            blf.draw(font_id, line)
            y += text_height + 5
    else:
        blf.position(0, 20, 30, 0)
        blf.draw(0, "GUI Help (H)")

    blf.disable(0, blf.SHADOW)


class TimeWarpPin(bpy.types.PropertyGroup):
    uid: bpy.props.StringProperty(
        name="UID",
        default="",
        description="Unique identifier for each Time Warp Pin",
    )
    position: bpy.props.FloatVectorProperty(
        name="Position",
        size=2,
        default=(0.0, 0.0),
        description="Position of the Pin in graph space (X: Frame, Y: Value)",
    )


class TimeWarpEasing(bpy.types.PropertyGroup):
    uid: bpy.props.StringProperty(
        name="UID",
        default="",
        description="Unique identifier for each Time Warp Easing",
    )
    percentage: bpy.props.FloatProperty(
        name="Percentage",
        default=0.5,
        min=0.0,
        max=1.0,
        description="Percentage position of the Easing between two Pins",
    )


class Pin:

    def __init__(self, pin_data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scale = get_dpi_scale()
        self.pin_data = pin_data
        self.size = 25 * scale
        self.is_hovered = False
        self.initial_position = None
        self.y_offset = 60 * scale

    def get_screen_position(self, context):

        if not self.pin_data or not self.pin_data.id_data or not self.pin_data.position or not self.y_offset:
            return float("inf"), float("inf")

        frame_x, _ = self.pin_data.position
        screen_x, _ = graph_to_screen(context, frame_x, 0)
        screen_y = self.y_offset
        return screen_x, screen_y

    def draw(self, context, color):
        scale = get_dpi_scale()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        region_height = context.region.height

        screen_x, screen_y = self.get_screen_position(context)

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

        # **New Code: Draw Frame Number Centered in the Circle**
        frame_number = int(round(self.pin_data.position[0]))
        text = str(frame_number)

        # Configure font settings
        font_id = 0
        font_size = 8 * scale
        blf.size(font_id, font_size)
        blf.color(font_id, 1, 1, 1, 1)

        # shadow color
        blf.enable(0, blf.SHADOW)
        blf.shadow(font_id, 5, 0, 0, 0, 0.5)
        blf.shadow_offset(font_id, 2, -2)

        # Calculate text dimensions to center it
        text_width, text_height = blf.dimensions(font_id, text)

        # Position the text so that it's centered in the circle
        text_x = screen_x - text_width / 2
        text_y = screen_y - text_height / 2

        # Draw the text
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, text)

    def _get_circle_vertices(self, screen_x, screen_y, num_segments=16):
        """Generate vertices for drawing a circle at screen coordinates (screen_x, screen_y)."""
        vertices = []
        radius = self.size / 2
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = screen_x + math.cos(angle) * radius
            y = screen_y + math.sin(angle) * radius
            vertices.append((x, y))
        return vertices

    def check_hover(self, mouse_x, mouse_y, context):

        if not self.pin_data:
            return

        half_size = self.size / 2
        screen_x, screen_y = self.get_screen_position(context)

        # Check circular hover based on current position and size
        distance = math.hypot(mouse_x - screen_x, mouse_y - screen_y)
        if distance <= half_size:
            if not self.is_hovered:
                bpy.context.window.cursor_set("HAND")
            self.is_hovered = True
        else:
            if self.is_hovered:
                bpy.context.window.cursor_set("DEFAULT")
            self.is_hovered = False


class Bar:

    def __init__(self, start_pin, end_pin, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scale = get_dpi_scale()
        self.start_pin = start_pin
        self.end_pin = end_pin
        self.height = 6 * scale
        self.padding = 2 * scale
        self.is_hovered = False
        self.y_offset = 75 * scale

    def get_bar_y_position(self, context):
        return 0 + self.y_offset

    def draw(self, context, color):
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        # Convert graph coordinates to screen coordinates for x positions
        x1, _ = graph_to_screen(context, self.start_pin.pin_data.position[0], 0)
        x2, _ = graph_to_screen(context, self.end_pin.pin_data.position[0], 0)

        # Dynamic Y position
        bar_y = self.get_bar_y_position(context)

        bar_vertices = [
            (x1 + self.padding, bar_y),
            (x2 - self.padding, bar_y),
            (x2 - self.padding, bar_y + self.height),
            (x1 + self.padding, bar_y + self.height),
        ]
        batch_bar = batch_for_shader(shader, "TRI_FAN", {"pos": bar_vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch_bar.draw(shader)

    def check_hover(self, mouse_x, mouse_y, context):

        # if not self.start_pin or not self.end_pin:
        #     return

        bar_y = self.get_bar_y_position(context)

        # Convert graph coordinates to screen coordinates for x positions
        x1, _ = graph_to_screen(context, self.start_pin.pin_data.position[0], 0)
        x2, _ = graph_to_screen(context, self.end_pin.pin_data.position[0], 0)

        # Calculate padded x positions
        x_min = x1 + self.padding
        x_max = x2 - self.padding
        y_min = bar_y
        y_max = bar_y + self.height

        # Check rectangular hover
        if x_min <= mouse_x <= x_max and y_min <= mouse_y <= y_max:
            # if self.is_hovered:
            #     bpy.context.window.cursor_set("HAND")
            self.is_hovered = True
        else:
            # if not self.is_hovered:
            #     bpy.context.window.cursor_set("DEFAULT")
            self.is_hovered = False


class Easing:
    def __init__(self, easing_data, start_pin, end_pin, timewarper, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scale = get_dpi_scale()
        self.easing_data = easing_data
        self.start_pin = start_pin
        self.end_pin = end_pin
        self.size = 15 * scale
        self.is_hovered = False
        self.is_dragging = False
        self.padding = 10 * scale
        self.timewarper = timewarper
        self.y_offset = 60 * scale

    def get_screen_position(self, context):

        if (
            not self.end_pin
            or not self.end_pin.pin_data
            or not self.start_pin
            or not self.start_pin.pin_data
            or not self.easing_data
            or not self.easing_data.percentage
            or not self.y_offset
        ):
            return float("inf"), float("inf")

        start_x = self.start_pin.pin_data.position[0]
        end_x = self.end_pin.pin_data.position[0]
        percentage = self.easing_data.percentage
        easing_x = start_x + (end_x - start_x) * percentage

        screen_x, _ = graph_to_screen(context, easing_x, 0)
        screen_y = 0 + self.y_offset
        return screen_x, screen_y

    def drag(self, context, mouse_x, mouse_y):
        if not self.is_dragging:
            return

        # Use offset to adjust for initial drag position
        graph_x, _ = screen_to_graph(context, mouse_x - self.offset_x, mouse_y - self.offset_y)
        start_x = self.start_pin.pin_data.position[0]
        end_x = self.end_pin.pin_data.position[0]

        if end_x == start_x:
            percentage = 0.0
        else:
            screen_start_x, _ = graph_to_screen(context, start_x, 0)
            screen_end_x, _ = graph_to_screen(context, end_x, 0)
            screen_x_padded = max(screen_start_x + self.padding, min(mouse_x, screen_end_x - self.padding))
            graph_x_padded, _ = screen_to_graph(context, screen_x_padded, 0)

            percentage = (graph_x_padded - start_x) / (end_x - start_x)
            percentage = max(0.0, min(1.0, percentage))

        # Update the easing position based on the new percentage
        self.easing_data.percentage = percentage

    def drag_end(self, context):
        if self.is_dragging:
            self.is_dragging = False
            bpy.context.window.cursor_set("DEFAULT")

            self.easing_data.percentage = 0.5

            # Save the current state to update initial keyframe positions
            # self.timewarper.save_state(context)

            # Trigger a redraw to apply updates
            context.area.tag_redraw()

    def draw(self, context, color):
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        screen_x, screen_y = self.get_screen_position(context)

        # Define rhombus vertices based on current position and size
        rhombus_vertices = self._get_rhombus_vertices(screen_x, screen_y)
        batch_rhombus = batch_for_shader(shader, "TRI_FAN", {"pos": rhombus_vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch_rhombus.draw(shader)

    def _get_rhombus_vertices(self, screen_x, screen_y, num_segments=4):
        """Generate vertices for drawing a rhombus at screen coordinates (screen_x, screen_y)
        with vertical and horizontal diagonals."""
        vertices = []
        radius_x = self.size / 2
        radius_y = self.size / 2
        angles = [0, 90, 180, 270]

        for angle in angles:
            rad = math.radians(angle)
            x = screen_x + math.cos(rad) * radius_x
            y = screen_y + math.sin(rad) * radius_y
            vertices.append((x, y))
        vertices.append(vertices[0])

        return vertices

    def check_hover(self, mouse_x, mouse_y, context):

        # if not self.is_hovered is None:
        #     return

        half_size = self.size / 2
        screen_x, screen_y = self.get_screen_position(context)

        # Check rhombus hover (distance from center for simplicity)
        distance = math.hypot(mouse_x - screen_x, mouse_y - screen_y)
        if distance <= half_size:
            self.is_hovered = True
        else:
            self.is_hovered = False

    def check_drag_start(self, mouse_x, mouse_y, context):
        half_size = self.size / 2
        screen_x, screen_y = self.get_screen_position(context)

        distance = math.hypot(mouse_x - screen_x, mouse_y - screen_y)
        if distance <= half_size:
            self.is_dragging = True
            self.offset_x = mouse_x - screen_x
            self.offset_y = mouse_y - screen_y
            bpy.context.window.cursor_set("HAND")

            return True
        return False


class AMP_OT_timewarp(bpy.types.Operator):

    bl_idname = "anim.amp_anim_timewarper"
    bl_label = "Time Warp"
    bl_options = {"REGISTER"}
    bl_description = """Time Warp Tool for animating keyframes in the Graph Editor or Dope Sheet Editor.
Hold SHIFT to launch the TimeWarp options panel."""

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

    tw_snap_to_frame: bpy.props.BoolProperty(
        name="Snap to Frame",
        description="Snap keyframes to nearest frame while dragging pins or bars",
        default=True,
    )

    slice_to_full_frames: bpy.props.BoolProperty(
        name="Slice to Full Frames",
        description="Slice keyframes to closest full frames on finish/cancel",
        default=True,
    )

    # Class variables to manage state
    _is_running = False
    _handles = []

    hovered_pins = set()
    hovered_bars = set()
    hovered_easings = set()

    @classmethod
    def poll(cls, context):
        return (
            context.area
            and context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}
            and context.active_object
            and context.active_object.animation_data
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pins = []
        self.bars = []
        self.easings = []
        self.mouse_x = 0
        self.mouse_y = 0
        self.dragging_element = None
        self.bar_initial_start_x = None
        self.bar_initial_end_x = None
        self.bar_initial_mouse_graph_x = None
        self.keyframes = []
        self.keyframes_initial_co_x = None
        self.keyframes_initial_handle_left_x = None
        self.keyframes_initial_handle_right_x = None
        self.undos = 0
        self.message = "Time Warp Active"

        # Store original state for ESC revert
        self.original_keyframe_positions = None
        self.original_marker_positions = None
        self.original_pin_positions = None

        self._last_hover_time = 0.0
        self._hover_debounce = 0.01

        self._undo_pushed = False

    def invoke(self, context, event):
        if event.shift:
            bpy.ops.wm.call_panel(name="AMP_PT_TimeWarperOptions", keep_open=True)
            return {"FINISHED"}

        bpy.ops.ed.undo_push(message="Time Warp started")
        self.undos += 2

        return self.execute(context)

    def execute(self, context):

        prefs = context.preferences.addons[base_package].preferences
        utils.amp_draw_header_handler(action="ADD", color=prefs.tw_topbar_color)
        utils.add_message(self.message)
        utils.refresh_ui(context)

        if AMP_OT_timewarp._is_running:
            self.cancel(context)
            return {"CANCELLED"}
        else:
            # Ensure an object with animation data is selected
            if not self._check_animation_data(context) and self.scope == "ACTION":
                self.report({"WARNING"}, "Select an object with animation data.")
                return {"CANCELLED"}

            # Initialize or restore state
            if len(context.scene.timewarper_settings.timewarp_pins) == 0:
                self.init_tool(context)
            else:
                self.restore_state(context)

            # Store original positions for ESC revert
            self.store_original_positions(context)

            # Add modal handler
            context.window_manager.modal_handler_add(self)

            # Add draw handler
            if not AMP_OT_timewarp._handles:
                AMP_OT_timewarp._handles = []
                for space_type in [bpy.types.SpaceGraphEditor, bpy.types.SpaceDopeSheetEditor]:
                    handle = space_type.draw_handler_add(draw_timewarp_gui, (context,), "WINDOW", "POST_PIXEL")
                    AMP_OT_timewarp._handles.append((handle, space_type))

            # Set class variable to True
            AMP_OT_timewarp._is_running = True

            return {"RUNNING_MODAL"}

    def modal(self, context, event):
        prefs = context.preferences.addons[base_package].preferences
        screen = context.screen

        # Check if context.area and context.region are valid
        if context.area is None or context.region is None:

            return self.cancel(context)

        # Check if the user switched out of the Graph Editor or Dope Sheet Editor
        if context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:

            return self.cancel(context)

        # Check if the user switched out of the Graph Editor
        if context.area is None or context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:

            return self.cancel(context)

        if not AMP_OT_timewarp._is_running:
            return {"CANCELLED"}

        if event.type == "ESC" and event.value == "PRESS" and screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=True)
            return {"RUNNING_MODAL"}

        elif event.type == "ESC" and event.value == "PRESS":
            # ESC reverts all changes to original positions
            self.restore_original_positions(context)
            
            # Cancel without applying slice
            props = context.scene.timewarper_settings
            temp_slice_setting = props.slice_to_full_frames
            props.slice_to_full_frames = False  # Temporarily disable slice
            self.cancel(context)
            props.slice_to_full_frames = temp_slice_setting  # Restore setting
            return {"CANCELLED"}

        elif event.type == "RET" and event.value == "PRESS":
            # Enter finishes with slice (if enabled)
            self.cancel(context)
            return {"CANCELLED"}

        if event.type == "RIGHTMOUSE" and event.value == "PRESS" and event.shift:
            if event.value == "RELEASE" and event.shift:
                self.cancel(context)
            return {"RUNNING_MODAL"}

        elif event.type == "RIGHTMOUSE" and event.value == "PRESS":
            bpy.ops.wm.call_panel(name="AMP_PT_TimeWarperOptions", keep_open=True)
            context.window.cursor_modal_set("DEFAULT")
            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":
            self.mouse_x = event.mouse_region_x
            self.mouse_y = event.mouse_region_y

            if self.dragging_element:
                props = context.scene.timewarper_settings
                self.handle_drag(context, event)
                if props.tw_realtime_updates:
                    self.update_keyframe_positions_proportionally(context, self.pins, self.easings)
            else:
                context.area.tag_redraw()
                if not self._undo_pushed:
                    self.update_hover(context, self.mouse_x, self.mouse_y)

                # self._undo_pushed = False

            context.area.tag_redraw()
            return {"PASS_THROUGH"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            element = self.get_element_at_position(self.mouse_x, self.mouse_y, context)
            if element:
                self.handle_click(context, event)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            if self.dragging_element:
                self.handle_release(context, event)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}

        # **Handle 'SHIFT A' Key Press to Add Pins at Selected Keyframes or at Mouse Location**
        if event.type == "A" and event.value == "PRESS" and event.shift:
            self.handle_shift_a_pin_creation(context, event)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # **Handle 'ALT A' Key Press to Add Pin at Current Frame (Playhead)**
        if event.type == "A" and event.value == "PRESS" and event.alt:
            current_frame = context.scene.frame_current
            self.add_pin(context, current_frame, 0.0)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # **Handle 'SHIFT X' to Delete Pin Under Mouse**
        if event.type == "X" and event.value == "PRESS" and event.shift:
            element = self.get_element_at_position(self.mouse_x, self.mouse_y, context)
            # **Delete the Hovered Pin**
            if isinstance(element, Pin):
                self.delete_pin(context, element)
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # **Handle 'ALT X' to Delete All Pins**
        if event.type == "X" and event.value == "PRESS" and event.alt:
            # **Delete All Pins**
            self.delete_all_pins(context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # **Handle 'R' Key Press to Toggle Realtime Updates**
        if event.type == "R" and event.value == "PRESS":
            props = context.scene.timewarper_settings
            props.tw_realtime_updates = not props.tw_realtime_updates
            self.report(
                {"INFO"},
                f"Realtime Time Warp Updates {'Enabled' if props.tw_realtime_updates else 'Disabled'}",
            )
            return {"RUNNING_MODAL"}

        # **Handle 'F' Key Press to Toggle Snap to Frame**
        if event.type == "F" and event.value == "PRESS":
            props = context.scene.timewarper_settings
            props.tw_snap_to_frame = not props.tw_snap_to_frame
            self.report(
                {"INFO"},
                f"Snap to Frame {'Enabled' if props.tw_snap_to_frame else 'Disabled'}",
            )
            return {"RUNNING_MODAL"}

        # **Handle 'H' Key Press to Toggle GUI Help Text**
        if event.type == "H" and event.value == "PRESS":
            prefs.timeline_gui_toggle = not prefs.timeline_gui_toggle
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "Z" and event.value == "PRESS" and (event.ctrl or event.oskey):

            self._undo_pushed = True

            if event.shift:
                # Handle Ctrl+Shift+Z (Redo)
                bpy.ops.ed.redo()
                return {"RUNNING_MODAL"}
            else:
                # Handle Ctrl+Z (Undo)
                if self.undos > 2:
                    self.undos -= 1
                    # self.restore_state(context)
                    bpy.ops.ed.undo()
                    # context.area.tag_redraw()
                    return {"RUNNING_MODAL"}
                else:
                    # self.restore_state(context)
                    # context.area.tag_redraw()
                    return {"RUNNING_MODAL"}

        if self._undo_pushed:
            self.update_elements(context)
            self.restore_state(context)
            self._undo_pushed = False

        return {"PASS_THROUGH"}

    def snap_frame(self, frame_x):
        """Snap the frame to the nearest whole number if tw_snap_to_frame is enabled."""
        props = bpy.context.scene.timewarper_settings
        if props.tw_snap_to_frame:
            return round(frame_x)
        return frame_x

    def snap_frame_array(self, frame_array):
        """Snap an array of frames to the nearest whole number if tw_snap_to_frame is enabled."""
        props = bpy.context.scene.timewarper_settings
        if props.tw_snap_to_frame:
            return np.round(frame_array)
        return frame_array

    def update_keyframe_positions_proportionally(self, context, pins, easings):
        props = context.scene.timewarper_settings
        action = context.active_object.animation_data.action
        if not action:
            return

        sorted_pins = sorted(pins, key=lambda pin: pin.pin_data.position[0])
        if not sorted_pins:
            return

        # Ensure all pins have initial_position set
        for pin in sorted_pins:
            if pin.initial_position is None:
                pin.initial_position = pin.pin_data.position[0]

        min_x0, max_x0 = sorted_pins[0].initial_position, sorted_pins[-1].initial_position
        if max_x0 == min_x0:
            max_x0 += 0.0001

        # Pre-calculate deltas
        delta_first_pin = sorted_pins[0].pin_data.position[0] - min_x0
        delta_last_pin = sorted_pins[-1].pin_data.position[0] - max_x0

        # Get the NumPy arrays of initial positions
        initial_x = self.keyframes_initial_co_x
        initial_handles_left_x = self.keyframes_initial_handle_left_x
        initial_handles_right_x = self.keyframes_initial_handle_right_x

        keyframes = self.keyframes
        num_keyframes = len(keyframes)

        # Initialize new positions arrays
        new_key_x = np.copy(initial_x)
        new_handles_left_x = np.copy(initial_handles_left_x)
        new_handles_right_x = np.copy(initial_handles_right_x)

        # Process keyframes before min_x0
        before_min_mask = initial_x <= min_x0
        new_key_x[before_min_mask] = initial_x[before_min_mask] + delta_first_pin

        # Process keyframes after max_x0
        after_max_mask = initial_x >= max_x0
        new_key_x[after_max_mask] = initial_x[after_max_mask] + delta_last_pin

        # Process keyframes between pins
        between_mask = np.logical_and(initial_x > min_x0, initial_x < max_x0)
        indices_between = np.where(between_mask)[0]
        initial_x_between = initial_x[between_mask]
        num_between = len(indices_between)
        new_key_x_between = np.zeros(num_between)

        # Process keyframes
        for i in range(len(sorted_pins) - 1):
            start_pin = sorted_pins[i]
            end_pin = sorted_pins[i + 1]
            start_x = start_pin.pin_data.position[0]
            end_x = end_pin.pin_data.position[0]
            original_start_x = start_pin.initial_position
            original_end_x = end_pin.initial_position

            if original_end_x == original_start_x:
                continue

            # Mask for keyframes in this segment
            segment_mask = np.logical_and(initial_x_between >= original_start_x, initial_x_between <= original_end_x)
            segment_indices = np.nonzero(segment_mask)[0]
            keyframe_indices = indices_between[segment_indices]

            if len(segment_indices) == 0:
                continue

            # Calculate relative positions within the segment
            rel_x = (initial_x_between[segment_indices] - original_start_x) / (original_end_x - original_start_x)

            # Retrieve the corresponding easing between these two pins
            easing = None
            for easing_instance in self.easings:
                if easing_instance.start_pin == start_pin and easing_instance.end_pin == end_pin:
                    easing = easing_instance
                    break

            if easing:
                # Apply easing to keyframes
                p = easing.easing_data.percentage
                if p == 0.5:
                    eased_rel_x = rel_x
                elif p > 0.5:
                    w = (p - 0.5) * 2
                    eased_rel_x = rel_x + w * (ease_out_exponential(rel_x) - rel_x)
                else:
                    w = (0.5 - p) * 2
                    eased_rel_x = rel_x + w * (ease_in_exponential(rel_x) - rel_x)
                eased_rel_x = np.clip(eased_rel_x, 0.0, 1.0)
            else:
                # Linear interpolation
                eased_rel_x = rel_x

            # Calculate the new positions
            new_x = start_x + eased_rel_x * (end_x - start_x)
            new_x = self.snap_frame_array(new_x)

            # Update keyframes
            new_key_x_between[segment_indices] = new_x

        # Assign back to new_key_x
        new_key_x[between_mask] = new_key_x_between

        # Now process handles separately
        # Combine handles into one array
        handles_x = np.concatenate([initial_handles_left_x, initial_handles_right_x])
        handles_new_x = np.copy(handles_x)

        # Initialize masks
        handles_before_min_mask = handles_x <= min_x0
        handles_after_max_mask = handles_x >= max_x0
        handles_between_mask = np.logical_and(handles_x > min_x0, handles_x < max_x0)

        # Process handles before min_x0
        handles_new_x[handles_before_min_mask] = handles_x[handles_before_min_mask] + delta_first_pin

        # Process handles after max_x0
        handles_new_x[handles_after_max_mask] = handles_x[handles_after_max_mask] + delta_last_pin

        # Process handles between pins
        handles_indices_between = np.where(handles_between_mask)[0]
        handles_x_between = handles_x[handles_between_mask]
        handles_new_x_between = np.zeros(len(handles_indices_between))

        for i in range(len(sorted_pins) - 1):
            start_pin = sorted_pins[i]
            end_pin = sorted_pins[i + 1]
            start_x = start_pin.pin_data.position[0]
            end_x = end_pin.pin_data.position[0]
            original_start_x = start_pin.initial_position
            original_end_x = end_pin.initial_position

            if original_end_x == original_start_x:
                continue

            # Mask for handles in this segment
            segment_mask = np.logical_and(handles_x_between >= original_start_x, handles_x_between <= original_end_x)
            segment_indices = np.nonzero(segment_mask)[0]
            handle_indices = handles_indices_between[segment_indices]

            if len(segment_indices) == 0:
                continue

            # Calculate relative positions within the segment
            rel_handles = (handles_x_between[segment_indices] - original_start_x) / (original_end_x - original_start_x)

            # Retrieve the corresponding easing between these two pins
            easing = None
            for easing_instance in self.easings:
                if easing_instance.start_pin == start_pin and easing_instance.end_pin == end_pin:
                    easing = easing_instance
                    break

            if easing:
                # Apply easing to handles
                p = easing.easing_data.percentage
                if p == 0.5:
                    eased_rel_handles = rel_handles
                elif p > 0.5:
                    w = (p - 0.5) * 2
                    eased_rel_handles = rel_handles + w * (ease_out_exponential(rel_handles) - rel_handles)
                else:
                    w = (0.5 - p) * 2
                    eased_rel_handles = rel_handles + w * (ease_in_exponential(rel_handles) - rel_handles)
                eased_rel_handles = np.clip(eased_rel_handles, 0.0, 1.0)
            else:
                # Linear interpolation
                eased_rel_handles = rel_handles

            # Calculate the new positions
            new_handles_x = start_x + eased_rel_handles * (end_x - start_x)
            new_handles_x = self.snap_frame_array(new_handles_x)

            # Update handles
            handles_new_x_between[segment_indices] = new_handles_x

        # Assign back to handles_new_x
        handles_new_x[handles_between_mask] = handles_new_x_between

        # Separate back into left and right handles
        num_handles = len(initial_handles_left_x)
        new_handles_left_x = handles_new_x[:num_handles]
        new_handles_right_x = handles_new_x[num_handles:]

        # Update keyframes
        for idx, keyframe in enumerate(keyframes):
            keyframe.co.x = new_key_x[idx]
            keyframe.handle_left.x = new_handles_left_x[idx]
            keyframe.handle_right.x = new_handles_right_x[idx]

        action.update_tag()
        context.area.tag_redraw()

        if props.tw_move_markers and self.markers:
            markers_frames = np.array(self.markers_initial_frames, dtype=float)
            new_marker_frames = np.copy(markers_frames)

            # Process markers before min_x0
            markers_before_min_mask = markers_frames <= min_x0
            new_marker_frames[markers_before_min_mask] = markers_frames[markers_before_min_mask] + delta_first_pin

            # Process markers after max_x0
            markers_after_max_mask = markers_frames >= max_x0
            new_marker_frames[markers_after_max_mask] = markers_frames[markers_after_max_mask] + delta_last_pin

            # Process markers between pins
            markers_between_mask = np.logical_and(markers_frames > min_x0, markers_frames < max_x0)
            markers_indices_between = np.where(markers_between_mask)[0]
            markers_frames_between = markers_frames[markers_between_mask]
            new_marker_frames_between = np.zeros(len(markers_indices_between))

            for i in range(len(sorted_pins) - 1):
                start_pin = sorted_pins[i]
                end_pin = sorted_pins[i + 1]
                start_x = start_pin.pin_data.position[0]
                end_x = end_pin.pin_data.position[0]
                original_start_x = start_pin.initial_position
                original_end_x = end_pin.initial_position

                if original_end_x == original_start_x:
                    continue

                # Mask for markers in this segment
                segment_mask = np.logical_and(
                    markers_frames_between >= original_start_x, markers_frames_between <= original_end_x
                )
                segment_indices = np.nonzero(segment_mask)[0]
                marker_indices = markers_indices_between[segment_indices]

                if len(segment_indices) == 0:
                    continue

                # Calculate relative positions within the segment
                rel_markers = (markers_frames_between[segment_indices] - original_start_x) / (
                    original_end_x - original_start_x
                )

                # Retrieve the corresponding easing between these two pins
                easing = None
                for easing_instance in self.easings:
                    if easing_instance.start_pin == start_pin and easing_instance.end_pin == end_pin:
                        easing = easing_instance
                        break

                if easing:
                    # Apply easing to markers
                    p = easing.easing_data.percentage
                    if p == 0.5:
                        eased_rel_markers = rel_markers
                    elif p > 0.5:
                        w = (p - 0.5) * 2
                        eased_rel_markers = rel_markers + w * (ease_out_exponential(rel_markers) - rel_markers)
                    else:
                        w = (0.5 - p) * 2
                        eased_rel_markers = rel_markers + w * (ease_in_exponential(rel_markers) - rel_markers)
                    eased_rel_markers = np.clip(eased_rel_markers, 0.0, 1.0)
                else:
                    # Linear interpolation
                    eased_rel_markers = rel_markers

                # Calculate the new positions
                new_marker_x = start_x + eased_rel_markers * (end_x - start_x)
                new_marker_x = self.snap_frame_array(new_marker_x)

                # Update markers
                new_marker_frames_between[segment_indices] = new_marker_x

            # Assign back to new_marker_frames
            new_marker_frames[markers_between_mask] = new_marker_frames_between

            # Round final values
            new_marker_frames = np.round(new_marker_frames)

            # Finally write the results back to each marker object
            for idx, marker in enumerate(self.markers):
                marker.frame = int(new_marker_frames[idx])

    def handle_click(self, context, event):
        # Check if clicking on any element to start dragging
        element = self.get_element_at_position(self.mouse_x, self.mouse_y, context)

        if element:
            if isinstance(element, Pin):
                self.dragging_element = element
                # Store initial positions of all pins at the start of the drag
                self.store_initial_pin_positions(context)

            elif isinstance(element, Bar):
                self.dragging_element = element
                # Store initial X positions for both start and end pins
                self.bar_initial_start_x = element.start_pin.pin_data.position[0]
                self.bar_initial_end_x = element.end_pin.pin_data.position[0]
                # Store initial mouse graph x
                self.bar_initial_mouse_graph_x, _ = screen_to_graph(context, event.mouse_region_x, event.mouse_region_y)
                # Store initial positions of all pins
                self.store_initial_pin_positions(context)

            elif isinstance(element, Easing):
                # Initiate dragging for Easing
                if element.check_drag_start(self.mouse_x, self.mouse_y, context):
                    self.dragging_element = element
                    # Store initial positions of all pins
                    self.store_initial_pin_positions(context)

            # Store initial keyframe and handle positions at the start of any drag
            self.store_initial_keyframe_positions(context)

            # Store initial marker positions
            self.store_initial_marker_positions(context)

    def handle_release(self, context, event):
        props = context.scene.timewarper_settings

        if self.dragging_element:
            if isinstance(self.dragging_element, Easing):
                if not props.tw_realtime_updates:
                    self.update_keyframe_positions_proportionally(context, self.pins, self.easings)

                self.dragging_element.drag_end(context)

                # **Save the new state for easings too**
                self.save_state(context)

                # **Clear initial pin positions**
                self.clear_initial_pin_positions()

                self.tw_push_undo()
            else:
                if not props.tw_realtime_updates:

                    self.update_keyframe_positions_proportionally(context, self.pins, self.easings)
                # **Save the new state**
                self.save_state(context)

                # **Finally, clear initial pin positions**
                self.clear_initial_pin_positions()

                self.tw_push_undo()

            self.dragging_element = None

        # if not props.tw_snap_to_frame:
        for fcurve in context.editable_fcurves:
            fcurve.update()

        # Rename marker
        if props.tw_move_markers and props.tw_rename_marker_numbers:
            for marker in self.markers:
                if re.search(r"_\d+$", marker.name):
                    base_name = re.sub(r"_\d+$", "", marker.name)
                    marker.name = f"{base_name}_{marker.frame}"

        return {"RUNNING_MODAL"}

    def handle_drag(self, context, event):
        if isinstance(self.dragging_element, Pin):
            self.drag_pin(context, self.dragging_element, event)
        elif isinstance(self.dragging_element, Bar):
            self.drag_bar(context, self.dragging_element, event)
        elif isinstance(self.dragging_element, Easing):
            self.drag_easing(context, self.dragging_element, event)

    def update_hover(self, context, mouse_x, mouse_y):

        if not self._is_running or not self.pins:
            return
        if not context or not context.area or not context.region:
            return
        bpy.context.window.cursor_set("DEFAULT")
        AMP_OT_timewarp.hovered_pins.clear()
        AMP_OT_timewarp.hovered_bars.clear()
        AMP_OT_timewarp.hovered_easings.clear()

        for pin in self.pins:
            if not pin or not pin.pin_data or not pin.pin_data.id_data:
                continue
            pin.check_hover(mouse_x, mouse_y, context)
            if pin.is_hovered:
                AMP_OT_timewarp.hovered_pins.add(pin.pin_data.uid)

        for bar in self.bars:
            if not bar.start_pin.pin_data or not bar.start_pin.pin_data.uid:
                continue
            if not bar.end_pin.pin_data or not bar.end_pin.pin_data.uid:
                continue
            bar.check_hover(mouse_x, mouse_y, context)
            if bar.is_hovered:
                bar_uid = f"{bar.start_pin.pin_data.uid}"
                AMP_OT_timewarp.hovered_bars.add(bar_uid)

        for easing in self.easings:
            if not easing or not easing.start_pin.pin_data or not easing.start_pin.pin_data.id_data:
                continue
            if not easing.end_pin.pin_data or not easing.end_pin.pin_data.id_data:
                continue
            easing.check_hover(mouse_x, mouse_y, context)
            if easing.is_hovered:
                AMP_OT_timewarp.hovered_easings.add(easing.easing_data.uid)

    def add_pin(self, context, graph_x, fixed_y):
        frame = self.snap_frame(graph_x)
        # Allow adding pins on contiguous frames, only restrict adding on the same frame
        for pin in self.pins:
            if pin.pin_data.position[0] == frame:
                self.report({"WARNING"}, f"A Pin already exists at frame {frame:.2f}.")
                return
        # Add new pin and set its position (Y is fixed)
        new_pin_data = context.scene.timewarper_settings.timewarp_pins.add()
        new_pin_data.position = (frame, fixed_y)  # Use snapped frame
        new_pin_data.uid = str(uuid.uuid4())
        new_pin = Pin(new_pin_data)
        self.pins.append(new_pin)
        # Force immediate redraw to use the updated position
        context.area.tag_redraw()
        self.tw_push_undo()
        self.update_elements(context)

    def delete_pin(self, context, pin):
        # Find the corresponding pin in the scene collection using UID
        index = -1
        for i, pin_data in enumerate(context.scene.timewarper_settings.timewarp_pins):
            if pin_data.uid == pin.pin_data.uid:
                index = i
                break
        if index >= 0:

            context.scene.timewarper_settings.timewarp_pins.remove(index)

            # Reconstruct 'self.pins' from 'context.scene.timewarper_settings.timewarp_pins'
            self.pins = []
            for pin_data in context.scene.timewarper_settings.timewarp_pins:
                # Validate pin data before adding
                if pin_data.uid:
                    pin = Pin(pin_data)
                    self.pins.append(pin)

            # Update elements and save state before triggering redraw
            self.update_elements(context)

            self.save_state(context)

            self.tw_push_undo()

            # **Trigger Redraw After Deletion**
            context.area.tag_redraw()

        else:
            self.report({"WARNING"}, "Failed to delete Pin: Pin data not found.")

    def delete_all_pins(self, context):
        """Delete all pins from the scene and internal lists."""

        # Clear the scene collection
        context.scene.timewarper_settings.timewarp_pins.clear()
        # Clear internal lists
        self.pins.clear()
        self.bars.clear()
        self.easings.clear()
        # Update UI elements
        self.update_elements(context)

        self.save_state(context)

        self.tw_push_undo()

        context.area.tag_redraw()

    def get_pin_at_position(self, x, y, context):
        for pin in self.pins:
            screen_x, screen_y = graph_to_screen(context, pin.pin_data.position[0], 0)
            screen_y = context.region.height - 25  # Fixed Y position
            distance = math.hypot(x - screen_x, y - screen_y)
            if distance <= pin.size / 2:
                return pin
        return None

    def get_element_at_position(self, x, y, context):

        for pin in self.pins:
            if not pin.pin_data or not pin.pin_data.id_data:
                continue
            screen_x, screen_y = pin.get_screen_position(context)
            if math.isinf(screen_x) or math.isinf(screen_y):
                continue
            distance = math.hypot(x - screen_x, y - screen_y)
            if distance <= pin.size / 2:
                return pin

        for bar in self.bars:
            if (
                not bar.start_pin.pin_data
                or not bar.start_pin.pin_data.id_data
                or not bar.end_pin.pin_data
                or not bar.end_pin.pin_data.id_data
            ):
                continue
            bar_y = bar.get_bar_y_position(context)
            x1, _ = bar.start_pin.get_screen_position(context)
            x2, _ = bar.end_pin.get_screen_position(context)
            if math.isinf(x1) or math.isinf(x2):
                continue
            x_min = min(x1, x2) + bar.padding
            x_max = max(x1, x2) - bar.padding
            y_min = bar_y
            y_max = bar_y + bar.height
            if x_min <= x <= x_max and y_min <= y <= y_max:
                return bar

        for easing in self.easings:
            if (
                not easing.start_pin.pin_data
                or not easing.start_pin.pin_data.id_data
                or not easing.end_pin.pin_data
                or not easing.end_pin.pin_data.id_data
            ):
                continue
            screen_x, screen_y = easing.get_screen_position(context)
            if math.isinf(screen_x) or math.isinf(screen_y):
                continue
            distance = math.hypot(x - screen_x, y - screen_y)
            if distance <= easing.size / 2:
                return easing

        return None

    def drag_pin(self, context, pin, event):
        # Convert mouse_x to graph_x
        graph_x, _ = screen_to_graph(context, event.mouse_region_x, event.mouse_region_y)
        graph_x = self.snap_frame(graph_x)  # Only snap if enabled in settings

        # Find constraints based on neighboring pins
        sorted_pins = sorted(self.pins, key=lambda p: p.pin_data.position[0])
        index = sorted_pins.index(pin)
        min_x = sorted_pins[index - 1].pin_data.position[0] + 1.0 if index > 0 else -math.inf
        max_x = sorted_pins[index + 1].pin_data.position[0] - 1.0 if index < len(sorted_pins) - 1 else math.inf
        # Clamp graph_x within constraints
        graph_x = max(min_x, min(graph_x, max_x))

        # Calculate delta_x based on initial position
        delta_x = graph_x - pin.initial_position

        # Update pin position (only X; Y is fixed)
        pin.pin_data.position = (graph_x, 0.0)

        # Determine direction of movement
        if delta_x > 0:
            direction = "right"
        elif delta_x < 0:
            direction = "left"
        else:
            direction = None  # No movement

        # Handle Shift-drag behavior
        if event.shift and not event.ctrl and delta_x != 0:

            for other_pin in self.pins:
                if other_pin == pin:
                    continue
                other_x = other_pin.initial_position
                if direction == "right" and other_x > pin.initial_position:
                    new_other_x = other_pin.initial_position + delta_x

                    other_index = sorted_pins.index(other_pin)
                    other_min_x = (
                        sorted_pins[other_index - 1].pin_data.position[0] + 1.0 if other_index > 0 else -math.inf
                    )
                    other_max_x = (
                        sorted_pins[other_index + 1].pin_data.position[0] - 1.0
                        if other_index < len(sorted_pins) - 1
                        else math.inf
                    )
                    new_other_x = max(other_min_x, min(new_other_x, other_max_x))
                    new_other_x = self.snap_frame(new_other_x)
                    other_pin.pin_data.position = (round(new_other_x), other_pin.pin_data.position[1])

                elif direction == "left" and other_x < pin.initial_position:
                    new_other_x = other_pin.initial_position + delta_x

                    other_index = sorted_pins.index(other_pin)
                    other_min_x = (
                        sorted_pins[other_index - 1].pin_data.position[0] + 1.0 if other_index > 0 else -math.inf
                    )
                    other_max_x = (
                        sorted_pins[other_index + 1].pin_data.position[0] - 1.0
                        if other_index < len(sorted_pins) - 1
                        else math.inf
                    )
                    new_other_x = max(other_min_x, min(new_other_x, other_max_x))
                    new_other_x = self.snap_frame(new_other_x)
                    other_pin.pin_data.position = (round(new_other_x), other_pin.pin_data.position[1])

        # Handle CTRL-drag behavior
        elif event.ctrl and not event.shift and delta_x != 0:
            # Pull from the elements not in the direction of movement
            for other_pin in self.pins:
                if other_pin == pin:
                    continue
                other_x = other_pin.initial_position
                if (direction == "right" and other_x < pin.initial_position) or (
                    direction == "left" and other_x > pin.initial_position
                ):
                    new_other_x = other_pin.initial_position + delta_x
                    # Remove constraints to allow movement beyond next pin
                    new_other_x = self.snap_frame(new_other_x)
                    other_pin.pin_data.position = (round(new_other_x), other_pin.pin_data.position[1])

        # Redraw to ensure visual update
        context.area.tag_redraw()

    def drag_bar(self, context, bar, event):
        # Current mouse position in graph coordinates
        current_mouse_graph_x, _ = screen_to_graph(context, event.mouse_region_x, event.mouse_region_y)

        # Calculate movement delta
        delta = current_mouse_graph_x - self.bar_initial_mouse_graph_x

        # Find sorted pins
        sorted_pins = sorted(self.pins, key=lambda p: p.pin_data.position[0])

        # Find the index of the bar's start pin
        start_index = sorted_pins.index(bar.start_pin)
        end_index = sorted_pins.index(bar.end_pin)

        # Find neighboring pins
        previous_pin = sorted_pins[start_index - 1] if start_index > 0 else None
        next_pin = sorted_pins[end_index + 1] if end_index < len(sorted_pins) - 1 else None

        # Calculate maximum allowed delta for dragging pins
        max_left_delta = (
            (previous_pin.pin_data.position[0] + 1.0) - self.bar_initial_start_x if previous_pin else -math.inf
        )
        max_right_delta = (next_pin.pin_data.position[0] - 1.0) - self.bar_initial_end_x if next_pin else math.inf

        # Clamp the delta within allowed bounds for dragging pins
        clamped_delta = max(max_left_delta, min(delta, max_right_delta))

        # Ensure the bar does not shrink or grow by preserving the original width
        original_length = self.bar_initial_end_x - self.bar_initial_start_x
        new_start_x = self.bar_initial_start_x + clamped_delta
        new_end_x = new_start_x + original_length
        new_start_x = round(new_start_x)
        new_end_x = round(new_end_x)

        # Apply the clamped delta to both start and end pins
        bar.start_pin.pin_data.position = (new_start_x, 0.0)
        bar.end_pin.pin_data.position = (new_end_x, 0.0)

        # Determine direction of movement
        if clamped_delta > 0:
            direction = "right"
        elif clamped_delta < 0:
            direction = "left"
        else:
            direction = None  # No movement

        # Handle Shift-drag behavior
        if event.shift and not event.ctrl and clamped_delta != 0:
            # Move the pins in the direction of movement
            for other_pin in self.pins:
                if other_pin in [bar.start_pin, bar.end_pin]:
                    continue
                other_x = other_pin.initial_position
                if direction == "right" and other_x > bar.end_pin.initial_position:
                    new_other_x = other_pin.initial_position + clamped_delta
                    # Apply constraints to prevent overlapping
                    other_index = sorted_pins.index(other_pin)
                    other_min_x = (
                        sorted_pins[other_index - 1].pin_data.position[0] + 1.0 if other_index > 0 else -math.inf
                    )
                    other_max_x = (
                        sorted_pins[other_index + 1].pin_data.position[0] - 1.0
                        if other_index < len(sorted_pins) - 1
                        else math.inf
                    )
                    new_other_x = max(other_min_x, min(new_other_x, other_max_x))
                    new_other_x = self.snap_frame(new_other_x)
                    other_pin.pin_data.position = (round(new_other_x), other_pin.pin_data.position[1])
                elif direction == "left" and other_x < bar.start_pin.initial_position:
                    new_other_x = other_pin.initial_position + clamped_delta
                    # Apply constraints to prevent overlapping
                    other_index = sorted_pins.index(other_pin)
                    other_min_x = (
                        sorted_pins[other_index - 1].pin_data.position[0] + 1.0 if other_index > 0 else -math.inf
                    )
                    other_max_x = (
                        sorted_pins[other_index + 1].pin_data.position[0] - 1.0
                        if other_index < len(sorted_pins) - 1
                        else math.inf
                    )
                    new_other_x = max(other_min_x, min(new_other_x, other_max_x))
                    new_other_x = self.snap_frame(new_other_x)
                    other_pin.pin_data.position = (round(new_other_x), other_pin.pin_data.position[1])

        # Handle CTRL-drag behavior
        elif event.ctrl and not event.shift and clamped_delta != 0:
            # Pull from the elements not in the direction of movement
            for other_pin in self.pins:
                if other_pin in [bar.start_pin, bar.end_pin]:
                    continue
                other_x = other_pin.initial_position
                if (direction == "right" and other_x < bar.start_pin.initial_position) or (
                    direction == "left" and other_x > bar.end_pin.initial_position
                ):
                    new_other_x = other_pin.initial_position + clamped_delta
                    # Remove constraints to allow movement beyond next pin
                    new_other_x = self.snap_frame(new_other_x)
                    other_pin.pin_data.position = (round(new_other_x), other_pin.pin_data.position[1])

        # Redraw the UI to reflect changes
        context.area.tag_redraw()

    def drag_easing(self, context, easing, event):
        easing.drag(context, event.mouse_region_x, event.mouse_region_y)
        # Removed self.update_elements(context) to centralize updates

    def update_elements(self, context):
        # Clear existing bars and easings
        self.bars.clear()
        self.easings.clear()

        # Rebuild self.pins by re-reading scene timewarper_settings
        self.pins.clear()
        for pin_data in context.scene.timewarper_settings.timewarp_pins:
            if pin_data.uid and pin_data.id_data:
                self.pins.append(Pin(pin_data))

        # Sort pins by their x position
        sorted_pins = sorted(self.pins, key=lambda p: p.pin_data.position[0])

        # Determine the desired number of easings based on the number of pins
        desired_easings = max(len(sorted_pins) - 1, 0)

        # Adjust the timewarp_easings collection to match the desired number of easings
        while len(context.scene.timewarper_settings.timewarp_easings) < desired_easings:
            new_easing_data = context.scene.timewarper_settings.timewarp_easings.add()
            new_easing_data.uid = str(uuid.uuid4())
            new_easing_data.percentage = 0.5  # Default to midpoint

        while len(context.scene.timewarper_settings.timewarp_easings) > desired_easings:
            try:
                context.scene.timewarper_settings.timewarp_easings.remove(
                    len(context.scene.timewarper_settings.timewarp_easings) - 1
                )

            except IndexError:
                # Safeguard against trying to remove from an empty collection

                break

        # Recreate Bars and Easings based on the sorted list
        for i in range(desired_easings):
            start_pin = sorted_pins[i]
            end_pin = sorted_pins[i + 1]
            bar = Bar(start_pin, end_pin)
            self.bars.append(bar)

            # Link the existing easing to the bar, passing self as the timewarper reference
            easing_data = context.scene.timewarper_settings.timewarp_easings[i]
            easing = Easing(easing_data, start_pin, end_pin, self)  # Pass 'self' here
            self.easings.append(easing)

    def init_tool(self, context):
        self.pins = []
        self.bars = []
        self.easings = []

        # Add draw handlers consistently as a list of tuples
        if not AMP_OT_timewarp._handles:
            AMP_OT_timewarp._handles = []
            for space_type in [bpy.types.SpaceGraphEditor, bpy.types.SpaceDopeSheetEditor]:
                handle = space_type.draw_handler_add(draw_timewarp_gui, (context,), "WINDOW", "POST_PIXEL")
                AMP_OT_timewarp._handles.append((handle, space_type))

        context.area.tag_redraw()

    # def restore_state(self, context):

    #     self.pins = []

    #     for pin_data in context.scene.timewarper_settings.timewarp_pins:
    #         # Assign a UID if missing
    #         if not pin_data.uid:
    #             pin_data.uid = str(uuid.uuid4())

    #         # Add all pins with a valid UID, regardless of position
    #         if pin_data.uid:
    #             pin = Pin(pin_data)
    #             self.pins.append(pin)

    def restore_state(self, context):
        self.pins = []
        for pin_data in context.scene.timewarper_settings.timewarp_pins:
            if not pin_data.uid or not pin_data.id_data:
                continue  # Skip invalid pins
            pin = Pin(pin_data)
            self.pins.append(pin)

        self.update_elements(context)

        sorted_pins = sorted(self.pins, key=lambda p: p.pin_data.position[0])

        self.bars = []
        self.easings = []

        for i in range(len(sorted_pins) - 1):
            start_pin = sorted_pins[i]
            end_pin = sorted_pins[i + 1]
            bar = Bar(start_pin, end_pin)
            self.bars.append(bar)

            # Restore or create easing
            if i < len(context.scene.timewarper_settings.timewarp_easings):
                easing_data = context.scene.timewarper_settings.timewarp_easings[i]
            else:
                easing_data = context.scene.timewarper_settings.timewarp_easings.add()
                easing_data.uid = str(uuid.uuid4())
                easing_data.percentage = 0.5

            easing = Easing(easing_data, start_pin, end_pin, self)
            self.easings.append(easing)

        if not AMP_OT_timewarp._handles:
            AMP_OT_timewarp._handles = []
            for space_type in [bpy.types.SpaceGraphEditor, bpy.types.SpaceDopeSheetEditor]:
                handle = space_type.draw_handler_add(draw_timewarp_gui, (context,), "WINDOW", "POST_PIXEL")
                AMP_OT_timewarp._handles.append((handle, space_type))

        context.area.tag_redraw()

    def save_state(self, context):

        existing_easings = {
            easing_data.uid: easing_data for easing_data in context.scene.timewarper_settings.timewarp_easings
        }

        for bar, easing in zip(self.bars, self.easings):
            uid = easing.easing_data.uid
            if uid in existing_easings:
                existing_easings[uid].percentage = easing.easing_data.percentage
            else:
                new_easing_data = context.scene.timewarper_settings.timewarp_easings.add()
                new_easing_data.uid = uid
                new_easing_data.percentage = easing.easing_data.percentage

        # add check so the pins are not invalid
        for pin in self.pins:
            if not pin.pin_data.id_data:
                continue
            pin.pin_data.position = (self.snap_frame(pin.pin_data.position[0]), pin.pin_data.position[1])

        self.keyframes_initial_co_x = np.array([kf.co.x for kf in self.keyframes])
        self.keyframes_initial_handle_left_x = np.array([kf.handle_left.x for kf in self.keyframes])
        self.keyframes_initial_handle_right_x = np.array([kf.handle_right.x for kf in self.keyframes])

    def tw_push_undo(self):
        bpy.ops.ed.undo_push(message="Time Warp saved state")
        self.undos += 1

    def cancel(self, context):

        utils.amp_draw_header_handler(action="REMOVE")
        utils.remove_message()
        utils.refresh_ui(context)

        # Apply slice to full frames if enabled
        props = context.scene.timewarper_settings
        if props.slice_to_full_frames and not props.tw_snap_to_frame:
            try:
                bpy.ops.anim.amp_anim_slicer(
                    insertion_type="CLOSEST_FULL_FRAME",
                    selection_mode="ALL_CURVES",
                    range_options="SCENE",
                    clear_others=True,
                    key_available=True,
                    key_location=False,
                    key_rotation=False,
                    key_scale=False,
                    key_custom=False,
                    kf_on_first=False,
                    kf_on_last=False,
                    clear_markers=False,
                )
            except:
                # Ignore errors if slicer is not available
                pass

        AMP_OT_timewarp._is_running = False
        if AMP_OT_timewarp._handles:
            for handle, space_type in AMP_OT_timewarp._handles:
                space_type.draw_handler_remove(handle, "WINDOW")
            AMP_OT_timewarp._handles = []

        bpy.context.window.cursor_set("DEFAULT")
        if context.area:
            context.area.tag_redraw()
        return {"CANCELLED"}

    def _check_animation_data(self, context):
        obj = context.active_object
        if obj and obj.animation_data and obj.animation_data.action:
            return True
        return False

    def store_initial_pin_positions(self, context):
        for pin in self.pins:
            if pin.initial_position is None:
                pin.initial_position = pin.pin_data.position[0]

    def clear_initial_pin_positions(self):
        for pin in self.pins:
            pin.initial_position = None

    def store_initial_keyframe_positions(self, context):
        scope = context.scene.timewarper_settings.scope
        props = context.scene.timewarper_settings
        keyframes = utils.curve.gather_keyframes(scope, context)
        initial_co_x = []
        initial_handle_left_x = []
        initial_handle_right_x = []

        for kf in keyframes:
            snapped = props.tw_snap_to_frame and round(kf.co.x) or kf.co.x
            initial_co_x.append(snapped)
            initial_handle_left_x.append(kf.handle_left.x)
            initial_handle_right_x.append(kf.handle_right.x)

        self.keyframes = keyframes
        self.keyframes_initial_co_x = np.array(initial_co_x)
        self.keyframes_initial_handle_left_x = np.array(initial_handle_left_x)
        self.keyframes_initial_handle_right_x = np.array(initial_handle_right_x)

    def store_initial_marker_positions(self, context):
        self.markers = []
        self.markers_initial_frames = []

        for m in context.scene.timeline_markers:
            self.markers.append(m)
            self.markers_initial_frames.append(m.frame)

    def store_original_positions(self, context):
        """Store the original keyframe and marker positions at the start of the operator for ESC revert."""
        scope = context.scene.timewarper_settings.scope
        keyframes = utils.curve.gather_keyframes(scope, context)
        
        # Store original keyframe positions
        self.original_keyframe_positions = []
        for kf in keyframes:
            self.original_keyframe_positions.append({
                'keyframe': kf,
                'co_x': kf.co.x,
                'co_y': kf.co.y,
                'handle_left_x': kf.handle_left.x,
                'handle_left_y': kf.handle_left.y,
                'handle_right_x': kf.handle_right.x,
                'handle_right_y': kf.handle_right.y,
            })
        
        # Store original marker positions
        self.original_marker_positions = []
        for marker in context.scene.timeline_markers:
            self.original_marker_positions.append({
                'marker': marker,
                'frame': marker.frame,
                'name': marker.name
            })
        
        # Store original pin positions
        self.original_pin_positions = []
        for pin_data in context.scene.timewarper_settings.timewarp_pins:
            self.original_pin_positions.append({
                'uid': pin_data.uid,
                'position': (pin_data.position[0], pin_data.position[1])
            })

    def restore_original_positions(self, context):
        """Restore all keyframes and markers to their original positions."""
        # Restore keyframes
        if self.original_keyframe_positions:
            for kf_data in self.original_keyframe_positions:
                kf = kf_data['keyframe']
                kf.co.x = kf_data['co_x']
                kf.co.y = kf_data['co_y']
                kf.handle_left.x = kf_data['handle_left_x']
                kf.handle_left.y = kf_data['handle_left_y']
                kf.handle_right.x = kf_data['handle_right_x']
                kf.handle_right.y = kf_data['handle_right_y']
        
        # Restore markers
        if self.original_marker_positions:
            for marker_data in self.original_marker_positions:
                marker = marker_data['marker']
                marker.frame = marker_data['frame']
                marker.name = marker_data['name']
        
        # Restore pins
        if self.original_pin_positions:
            for pin_data in self.original_pin_positions:
                # Find the pin by UID and restore its position
                for scene_pin in context.scene.timewarper_settings.timewarp_pins:
                    if scene_pin.uid == pin_data['uid']:
                        scene_pin.position = pin_data['position']
                        break
            
            # Update internal pin objects
            self.restore_state(context)
        
        # Update fcurves
        for fcurve in context.editable_fcurves:
            fcurve.update()
        
        # Update action
        if context.active_object and context.active_object.animation_data and context.active_object.animation_data.action:
            context.active_object.animation_data.action.update_tag()
        
        context.area.tag_redraw()

    def get_selected_keyframe_frames(self, context):
        """Get a unique sorted list of frames where keyframes are selected from visible fcurves."""
        selected_frames = set()

        # Try to get the correct animation data based on context
        try:
            if context.area.type == "GRAPH_EDITOR":
                # Get visible and editable fcurves from Graph Editor
                for fcurve in context.editable_fcurves:
                    if fcurve.select:  # Check if fcurve is selected/visible
                        for keyframe in fcurve.keyframe_points:
                            if keyframe.select_control_point:
                                selected_frames.add(keyframe.co.x)

            elif context.area.type == "DOPESHEET_EDITOR":
                # Get selected keyframes from Dope Sheet
                # In Dope Sheet, fcurve selection logic is different, so check all editable fcurves
                space = context.space_data

                # Check if we have a valid active object and action
                if context.active_object and context.active_object.animation_data:
                    action = context.active_object.animation_data.action
                    if action:
                        # Go through all fcurves in the action
                        for fcurve in action.fcurves:
                            for keyframe in fcurve.keyframe_points:
                                if keyframe.select_control_point:
                                    selected_frames.add(keyframe.co.x)

                # Fallback: use context.editable_fcurves
                if not selected_frames:
                    for fcurve in context.editable_fcurves:
                        for keyframe in fcurve.keyframe_points:
                            if keyframe.select_control_point:
                                selected_frames.add(keyframe.co.x)

        except Exception as e:
            print(f"Error getting selected keyframes: {e}")
            # Fallback to basic approach
            for fcurve in context.editable_fcurves:
                for keyframe in fcurve.keyframe_points:
                    if keyframe.select_control_point:
                        selected_frames.add(keyframe.co.x)

        # Convert to sorted list
        result = sorted(list(selected_frames))

        # Debug output to help troubleshoot (remove this later)
        if context.area.type == "DOPESHEET_EDITOR":
            print(f"Dope Sheet - Found {len(result)} selected keyframes at frames: {result}")

        return result

    def deselect_all_keyframes(self, context):
        """Deselect all keyframes in the current context (Graph Editor or Dope Sheet)."""
        for fcurve in context.editable_fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe.select_control_point = False
                keyframe.select_left_handle = False
                keyframe.select_right_handle = False

    def handle_shift_a_pin_creation(self, context, event):
        """Handle SHIFT+A key press: add pins at selected keyframes or at mouse location if none selected."""
        # Get selected keyframe frames
        selected_frames = self.get_selected_keyframe_frames(context)

        print(f"SHIFT+A pressed in {context.area.type}, found {len(selected_frames)} selected keyframes")

        if selected_frames:
            # If keyframes are selected, clear all pins and add pins at selected keyframe positions
            self.delete_all_pins_silent(context)

            # Add pins at each selected keyframe frame
            for frame in selected_frames:
                # Check if pin already exists at this frame to avoid duplicates
                frame_exists = any(pin.pin_data.position[0] == frame for pin in self.pins)
                if not frame_exists:
                    self.add_pin(context, frame, 0.0)

            # Deselect all keyframes
            self.deselect_all_keyframes(context)

            self.report({"INFO"}, f"Added {len(selected_frames)} pins at selected keyframe positions")
        else:
            # If no keyframes selected, add pin at mouse location (original SHIFT+A behavior)
            graph_x, _ = screen_to_graph(context, event.mouse_region_x, event.mouse_region_y)
            self.add_pin(context, graph_x, 0.0)
            print(f"No keyframes selected, added pin at mouse location: {graph_x}")

    def delete_all_pins_silent(self, context):
        """Delete all pins without pushing undo (used internally)."""
        # Clear the scene collection
        context.scene.timewarper_settings.timewarp_pins.clear()
        # Clear internal lists
        self.pins.clear()
        self.bars.clear()
        self.easings.clear()
        # Update UI elements
        self.update_elements(context)
        self.save_state(context)


class AMP_PT_TimeWarperOptions(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_TimeWarperOptions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        props = context.scene.timewarper_settings

        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.label(text="Anim TimeWarper Options", **get_icon("AMP_anim_timewarper"))

        ui_column = layout.column()

        # Add Start Timewarper button
        ui_column.separator()

        # Check if timewarper is running to determine button text
        button_text = "Stop Timewarper" if AMP_OT_timewarp._is_running else "Start Timewarper"
        start_button = ui_column.operator(
            "anim.amp_anim_timewarper", text=button_text, **get_icon("AMP_anim_timewarper")
        )

        ui_column.separator()

        ui_column.label(text="General", icon="SETTINGS")

        general_box = ui_column.box()
        general_box.prop(props, "scope", text="Scope")
        general_box.prop(props, "tw_realtime_updates", text="Realtime Updates")
        general_box.prop(props, "tw_snap_to_frame", text="Snap to Full Frames")

        # Slice to full frames - only enabled when snap is disabled
        slice_container = general_box.column()
        slice_container.active = not props.tw_snap_to_frame
        slice_container.prop(props, "slice_to_full_frames", text="Slice to Full Frames")

        ui_column.separator()

        ui_column.label(text="Markers", icon="MARKER")

        markers_box = ui_column.box()
        markers_box.prop(props, "tw_move_markers", text="Move Markers")
        markers_box.prop(props, "tw_rename_marker_numbers", text="Rename Marker Suffix")


def update_scope(self, context):
    # Find a running TimeWarp operator and update its state
    for op in context.window_manager.operators:
        if op.bl_idname == "anim.amp_anim_timewarper":
            # Update the operator's scope and reinitialize its keyframes
            op.scope = self.scope
            op.store_initial_keyframe_positions(context)
            context.area.tag_redraw()
            break


class AMP_PG_TimeWarperSettings(bpy.types.PropertyGroup):
    scope: bpy.props.EnumProperty(
        name="Scope",
        description="Scope of the Time Warper tool",
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
    tw_realtime_updates: bpy.props.BoolProperty(name="Realtime Updates", default=True)
    tw_snap_to_frame: bpy.props.BoolProperty(name="Snap Frames", default=True)
    slice_to_full_frames: bpy.props.BoolProperty(
        name="Slice to Full Frames",
        description="Slice keyframes to closest full frames on finish/cancel",
        default=True,
    )
    timewarp_pins: bpy.props.CollectionProperty(type=TimeWarpPin)
    timewarp_easings: bpy.props.CollectionProperty(type=TimeWarpEasing)
    tw_move_markers: bpy.props.BoolProperty(
        name="Move Markers",
        description="Move markers with retiming",
        default=True,
    )
    tw_rename_marker_numbers: bpy.props.BoolProperty(
        name="Rename Marker Suffix",
        description="If true, rename marker suffix to current frame number",
        default=True,
    )


classes = (
    TimeWarpPin,
    TimeWarpEasing,
    AMP_OT_timewarp,
    AMP_PG_TimeWarperSettings,
    AMP_PT_TimeWarperOptions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.timewarper_settings = bpy.props.PointerProperty(type=AMP_PG_TimeWarperSettings)


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
