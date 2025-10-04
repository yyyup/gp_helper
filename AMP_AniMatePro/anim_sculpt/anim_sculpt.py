import bpy
import gpu
import blf
import time
import math
import numpy as np

from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_circle_2d
from bpy.types import Scene
from bpy_extras.view3d_utils import location_3d_to_region_2d
from bpy.props import EnumProperty, FloatProperty, BoolProperty, IntProperty
from mathutils import Vector

from ..utils import ensure_alpha
from ..utils.curve import is_fcurve_in_radians, get_nla_strip_offset
from ..utils.customIcons import get_icon
from .. import utils
from .. import __package__ as base_package


def graph_to_screen(context, graph_x, graph_y):
    if not context.region or not context.region.view2d or graph_x is None or graph_y is None:
        return float("inf"), float("inf")
    region = context.region
    view2d = region.view2d
    screen_x, screen_y = view2d.view_to_region(
        context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x, invert=True), graph_y, clip=False
    )

    return screen_x, screen_y


def screen_to_graph(context, screen_x, screen_y):
    region = context.region
    view2d = region.view2d
    graph_x, graph_y = view2d.region_to_view(screen_x, screen_y)

    return context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x, invert=True), graph_y


def get_scale_factors(context):
    region = context.region
    view2d = region.view2d
    bottom_left_view = view2d.region_to_view(0, 0)
    top_right_view = view2d.region_to_view(region.width, region.height)
    view_width_units = top_right_view[0] - bottom_left_view[0]
    view_height_units = top_right_view[1] - bottom_left_view[1]
    scale_x = view_width_units / region.width
    scale_y = view_height_units / region.height
    return scale_x, scale_y


def draw_text_bottom_center(context, text):
    region = context.region
    viewport_width = region.width
    bottom_center_x = viewport_width / 2

    # BLF setup for drawing
    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 5, 0, 0, 0, 0.5)
    blf.shadow_offset(0, 1, -1)
    blf.color(1, 1, 1, 1, 1)
    blf.size(0, 20)
    text_width, text_height = blf.dimensions(0, text)
    blf.position(0, bottom_center_x - (text_width / 2), 20, 0)
    blf.draw(0, text)
    blf.disable(0, blf.SHADOW)


def draw_gui_help_text(context, x, y):
    """Draw GUI help text in the Graph Editor."""

    prefs = bpy.context.preferences.addons[base_package].preferences

    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 6, 0, 0, 0, 1)
    blf.shadow_offset(0, 2, -2)
    font_id = 0
    blf.size(font_id, 12)

    safe_text_color = ensure_alpha(prefs.text_color)
    blf.color(0, *safe_text_color)

    if prefs.timeline_gui_toggle:

        lines = [
            "______________________",
            "Anim Sculpt Help:",
            "______________________",
            "",
            "Drag Mouse - Tweak",
            "Drag + Shift - Smooth",
            "Drag + CTRL + Shift - Average",
            "",
            "______________________",
            "Adjust Radius (R | MWHEEL)",
            "Adjust Blend Radius (B | SHIFT + MWHEEL)",
            "Adjust Strength (S | CTRL + MWHEEL)",
            "______________________",
            "",
            "______________________",
            "L - Cycle Sculpt Lock Mode",
            "______________________",
            "",
            "ESC or Right Click - Exit",
        ]

        for line in reversed(lines):
            text_width, text_height = blf.dimensions(font_id, line)
            blf.position(font_id, x, y, 0)
            blf.draw(font_id, line)
            y += text_height + 5
    else:
        blf.position(0, 20, 30, 0)
        blf.draw(0, "GUI Help (H)")

    blf.disable(0, blf.SHADOW)


def calculate_influence(distance, radius, blend_radius):
    if distance <= radius:
        return 1.0
    elif distance > radius and distance <= radius + blend_radius:
        return 1 - (distance - radius) / blend_radius
    return 0.0


def anim_sculpt_brush(
    self,
    context,
    delta_x,
    delta_y,
    last_mouse_x,
    last_mouse_y,
    brush_mode_function,
    selected_average=False,
    use_neighbours=False,
    offset=0,
):
    settings = context.scene.keyframe_sculpt_settings

    radius = settings.radius
    blend_radius = settings.blend_radius
    strength = settings.strength / 100

    scale_x, scale_y = get_scale_factors(context)
    cursor_graph_x, cursor_graph_y = screen_to_graph(context, last_mouse_x, last_mouse_y)

    if settings.scope in {"PIN_SELECTED", "ONLY_SELECTED"}:
        fcurves = context.selected_editable_fcurves
    elif settings.scope == "VISIBLE":
        fcurves = context.visible_fcurves
    else:
        fcurves = []
        self.report({"WARNING"}, "No valid fcurves found in the current scope")

    selected_keyframes = []
    selected_keyframe_values = []
    selected_avg_value = 0

    if self.calculated_selected_kf_average == 0 and selected_average:
        for fcurve in fcurves:
            keyframes = fcurve.keyframe_points
            is_rotation_curve = is_fcurve_in_radians(fcurve)
            for keyframe in keyframes:
                if keyframe.select_control_point and keyframe not in selected_keyframes:
                    value = keyframe.co[1]
                    if is_rotation_curve:
                        value = math.degrees(value)
                    selected_keyframes.append(keyframe)
                    selected_keyframe_values.append(value)

        if selected_keyframe_values:
            selected_avg_value = sum(selected_keyframe_values) / len(selected_keyframe_values)
        selected_final_avg_value = self.calculated_selected_kf_average = selected_avg_value
    else:
        selected_final_avg_value = max(self.calculated_selected_kf_average, selected_avg_value)

    neighbours_distances = self.neighbours_distances_cached
    if use_neighbours and not neighbours_distances:
        self.report({"INFO"}, "Calculating neighbours")
        for fcurve in fcurves:
            keyframes = fcurve.keyframe_points
            times = np.array([kf.co[0] for kf in keyframes])
            distances = np.zeros(len(keyframes))
            distances[1:-1] = (times[2:] - times[1:-1]) + (times[1:-1] - times[:-2])
            neighbours_distances[fcurve] = distances

        self.neighbours_distances_cached = neighbours_distances

    elif not use_neighbours:
        # Clear the cached values if not needed
        self.neighbours_distances_cached = {}
    else:
        neighbours_distances = self.neighbours_distances_cached

    for fcurve in fcurves:
        keyframes = fcurve.keyframe_points
        num_keyframes = len(keyframes)
        if num_keyframes == 0:
            continue

        keyframe_times = np.array([keyframe.co[0] for keyframe in keyframes])
        keyframe_values = np.array([keyframe.co[1] for keyframe in keyframes])
        keyframe_select = np.array([keyframe.select_control_point for keyframe in keyframes], dtype=bool)
        keyframe_is_border = np.zeros(num_keyframes, dtype=bool)
        keyframe_is_border[0] = True
        keyframe_is_border[-1] = True

        # Filter keyframes outside horizontal influence
        mask_horizontal = (keyframe_times >= cursor_graph_x - radius - blend_radius) & (
            keyframe_times <= cursor_graph_x + radius + blend_radius
        )

        # Exclude selected keyframes if scope is 'PIN_SELECTED'
        if settings.scope == "PIN_SELECTED":
            mask_pin_selected = ~keyframe_select
        else:
            mask_pin_selected = np.ones(num_keyframes, dtype=bool)

        # Exclude border keyframes if pin_border_keyframes is True
        if settings.pin_border_keyframes:
            mask_pin_border = ~keyframe_is_border
        else:
            mask_pin_border = np.ones(num_keyframes, dtype=bool)

        # Combine masks
        mask = mask_horizontal & mask_pin_selected & mask_pin_border

        # Proceed only with masked keyframes
        keyframes_masked = [keyframe for keyframe, m in zip(keyframes, mask) if m]
        keyframe_times_masked = keyframe_times[mask]
        keyframe_values_masked = keyframe_values[mask]

        # Handle is_rotation_curve
        is_rotation_curve = is_fcurve_in_radians(fcurve)
        if is_rotation_curve:
            keyframe_values_masked = np.degrees(keyframe_values_masked)
            d2r_conversion = math.pi / 180
        else:
            d2r_conversion = 1.0

        # Compute normalized distances
        normalized_distance_x = (cursor_graph_x - keyframe_times_masked) / radius
        normalized_distance_y = (cursor_graph_y - keyframe_values_masked) / radius

        # Compute ellipse_check
        ellipse_check = (normalized_distance_x / scale_x) ** 2 + (normalized_distance_y / scale_y) ** 2

        blend_threshold = ((radius + blend_radius) / radius) ** 2

        mask_inside_ellipse = ellipse_check <= 1
        mask_in_blend = (ellipse_check > 1) & (ellipse_check <= blend_threshold)
        mask_outside = ellipse_check > blend_threshold

        influence = np.zeros(len(keyframes_masked))
        influence[mask_inside_ellipse] = 1.0
        influence[mask_in_blend] = 1 - (np.sqrt(ellipse_check[mask_in_blend]) - 1) / (blend_radius / radius)
        # influence[mask_outside] remains zero

        indices = np.nonzero(influence > 0)[0]

        if len(indices) > 0:
            # Prepare data for brush_mode_function
            keyframes_influenced = [keyframes_masked[i] for i in indices]
            influence_values = influence[indices]

            for idx, (keyframe, influence_value) in enumerate(zip(keyframes_influenced, influence_values)):
                brush_mode_function(
                    context,
                    influence_value,
                    delta_x,
                    delta_y,
                    keyframe,
                    d2r_conversion,
                    strength,
                    fcurve,
                    fcurves,
                    selected_keyframes,
                    selected_final_avg_value,
                    neighbours_distances,
                )

        fcurve.update()
    context.area.tag_redraw()


def anim_sculpt_brush_tweak(
    context,
    influence,
    delta_x,
    delta_y,
    keyframe,
    d2r_conversion,
    strength,
    fcurve,
    fcurves,
    selected_keyframes,
    selected_avg_value,
    neighbours_values,
):
    settings = context.scene.keyframe_sculpt_settings
    # Apply movement based on influence
    if influence > 0:
        if settings.keyframes_sculpt_lock_mode != "LOCK_FRAMES":
            keyframe.co_ui[0] += delta_x * influence * strength
        if settings.keyframes_sculpt_lock_mode != "LOCK_VALUES":
            keyframe.co_ui[1] += delta_y * influence * strength * d2r_conversion


# def anim_sculpt_brush_smooth(
#     context,
#     influence,
#     delta_x,
#     delta_y,
#     keyframe,
#     d2r_conversion,
#     strength,
#     fcurve,
#     fcurves,
#     selected_keyframes,
#     selected_avg_value,
#     neighbours_distances,
# ):
#     settings = context.scene.keyframe_sculpt_settings
#     str_multiplier = settings.smoothing_multiplier

#     if influence <= 0:
#         return  # Skip keyframes outside the brush influence

#     keyframes = fcurve.keyframe_points
#     num_keyframes = len(keyframes)
#     index = keyframes[:].index(keyframe)

#     # Dynamically calculate Y value for smoothing using cached distances
#     if 0 < index < num_keyframes - 1 and fcurve in neighbours_distances:
#         prev_kf = keyframes[index - 1]
#         next_kf = keyframes[index + 1]

#         weighted_avg_value = (prev_kf.co[1] + next_kf.co[1]) / 2.0

#         decay_factor = 0.01
#         total_distance = neighbours_distances[fcurve][index]

#         # Apply exponential decay based on total_distance
#         decay = math.exp(-decay_factor * total_distance)

#         # Apply the decay to reduce the adjustment
#         adjustment = influence * strength * decay * (weighted_avg_value - keyframe.co[1]) * str_multiplier

#         # Apply the adjustment
#         keyframe.co_ui[1] += adjustment


def anim_sculpt_brush_smooth(
    context,
    influence,
    delta_x,
    delta_y,
    keyframe,
    d2r_conversion,
    strength,
    fcurve,
    fcurves,
    selected_keyframes,
    selected_avg_value,
    neighbours_distances,
):
    settings = context.scene.keyframe_sculpt_settings
    str_multiplier = settings.smoothing_multiplier * 0.7

    if influence <= 0:
        return  # Skip keyframes outside the brush influence

    keyframes = fcurve.keyframe_points
    num_keyframes = len(keyframes)
    index = keyframes[:].index(keyframe)

    if 0 < index < num_keyframes - 1:
        prev_kf = keyframes[index - 1]
        next_kf = keyframes[index + 1]

        t_prev = prev_kf.co[0]
        y_prev = prev_kf.co[1]
        t_curr = keyframe.co[0]
        y_curr = keyframe.co[1]
        t_next = next_kf.co[0]
        y_next = next_kf.co[1]

        # Handle rotation curves
        is_rotation_curve = is_fcurve_in_radians(fcurve)
        if is_rotation_curve:
            y_prev = math.degrees(y_prev)
            y_curr = math.degrees(y_curr)
            y_next = math.degrees(y_next)

        # Compute expected value at t_curr based on linear interpolation
        if t_next != t_prev:
            y_expected = y_prev + ((y_next - y_prev) / (t_next - t_prev)) * (t_curr - t_prev)
        else:
            y_expected = (y_prev + y_next) / 2.0  # Fallback in case t_prev == t_next

        # Compute adjustment
        adjustment = influence * strength * (y_expected - y_curr) * str_multiplier

        # Convert adjustment back to radians if necessary
        if is_rotation_curve:
            adjustment = math.radians(adjustment)

        # Apply the adjustment
        keyframe.co_ui[1] += adjustment


def get_fcurve_default_value(fcurve):
    path = fcurve.data_path.lower()
    idx = fcurve.array_index
    if "rotation_quaternion" in path and idx == 0:
        return 1.0  # W component of a quaternion
    if "scale" in path:
        return 1.0  # default scale
    return 0.0  # any other curve


def anim_brush_brush_average(
    context,
    influence,
    delta_x,
    delta_y,
    keyframe,
    d2r_conversion,
    strength,
    fcurve,
    fcurves,
    selected_keyframes,
    selected_avg_value,
    neighbours_values,
):
    """Apply averaging to keyframes, considering unit conversion for rotation curves."""

    # Early return if outside brush influence
    if influence <= 0:
        return

    # Skip if there's no valid average to move towards
    if math.isclose(selected_avg_value, 0.0):
        # Fallback to the default value of the curve
        selected_avg_value = get_fcurve_default_value(fcurve)

    settings = context.scene.keyframe_sculpt_settings
    str_multiplier = settings.smoothing_multiplier * 0.7 / 50

    is_rotation_curve = is_fcurve_in_radians(fcurve)

    # Convert keyframe value to degrees if needed
    keyframe_value = keyframe.co[1]
    if is_rotation_curve:
        keyframe_value = math.degrees(keyframe_value)

    # Calculate the adjustment towards the average value
    adjustment = influence * strength * (selected_avg_value - keyframe_value) * str_multiplier

    # Convert adjustment back to radians if necessary
    if is_rotation_curve:
        adjustment = math.radians(adjustment)

    # Apply adjustment
    keyframe.co_ui[1] += adjustment


class AMP_OT_anim_sculpt(bpy.types.Operator):
    """Animation Curves Sculptor
    Sculpt directly on the animation curves in the Graph Editor with a brush
    - LMB: Move keyframes around.
    - SHIFT + LMB: Smooth keyframes with neighbours.
    - CTRL + SHIFT + LMB: Average keyframes to selected."""

    bl_idname = "anim.amp_anim_sculpt"
    bl_label = "AnimSculpt"
    bl_options = {"REGISTER", "UNDO"}  # , "GRAB_CURSOR", "BLOCKING"}

    mode: EnumProperty(
        name="Mode",
        items=[
            ("SMOOTH", "Smoothing Mode", "", 0),
            ("TWEAK", "Tweaking Mode", "", 1),
            ("AVERAGE", "Average Mode", "", 2),
        ],
        default="TWEAK",
    )

    radius: FloatProperty(
        name="Radius",
        description="Radius of 100% influence",
        default=50,
        min=1,
        max=500,
    )

    blend_radius: FloatProperty(
        name="Blend Radius",
        description="Outer radius from which influence fades to 0%",
        default=100,
        min=1,
        max=500,
    )

    strength: FloatProperty(
        name="Strength",
        description="Strength of the brush",
        default=100,
        min=0.1,
        max=100,
        subtype="PERCENTAGE",
        precision=0,
    )

    cancel_sculpt: bpy.props.BoolProperty(default=False)

    dragging = False

    init_mouse_x = FloatProperty()
    init_mouse_y = FloatProperty()
    init_graph_x = FloatProperty()
    init_graph_y = FloatProperty()
    last_mouse_x = FloatProperty()
    last_mouse_y = FloatProperty()

    adjusting_value = False
    calculated_selected_kf_average = 0
    neighbours_distances_cached = {}

    rmb_pressed = False

    _handle = None

    initial_use_normalization = False
    initial_view_settings = {}

    stored_brush_x: FloatProperty(default=0.0)
    stored_brush_y: FloatProperty(default=0.0)

    mouse_x: FloatProperty(default=0.0)
    mouse_y: FloatProperty(default=0.0)

    offset = 0

    @classmethod
    def poll(cls, context):
        return (
            context.area.type == "GRAPH_EDITOR"
            and context.active_object is not None
            and context.active_object.animation_data is not None
        )

    def draw(self, context):
        layout = self.layout
        draw_anim_sculpt_options(layout, context)

    def _display_text(self, text, mouse_position, font_id=0, font_size=15):
        blf.size(font_id, font_size)

        # Split the text into lines
        lines = text.split("\n")
        # Adjust the total height calculation for spacing based on the number of lines
        total_height = len(lines) * (font_size * 1.5) - (font_size * 0.5)  # Slight adjustment for top line

        # Calculate the initial Y position for the first line, to ensure the text block is centered
        initial_y = mouse_position[1] + total_height / 2 - font_size

        for i, line in enumerate(lines):
            text_width, text_height = blf.dimensions(font_id, line)

            # Calculate the centered position based on text dimensions
            centered_position_x = mouse_position[0] - text_width / 2

            # Adjust vertical position for each line, starting from the top
            centered_position_y = initial_y - (font_size * 1.5) * i

            blf.position(font_id, centered_position_x, centered_position_y, 0)
            blf.draw(font_id, line)

    def draw_text_bottom_center(self, context, text):
        region = context.region
        viewport_width = region.width
        bottom_center_x = viewport_width / 2

        # BLF setup for drawing
        blf.size(0, 20)
        text_width, text_height = blf.dimensions(0, text)
        blf.position(0, bottom_center_x - (text_width / 2), 20, 0)
        blf.draw(0, text)

    def snap_keyframes_to_frames(self, context):
        fcurves = context.selected_editable_fcurves
        for fcurve in fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe.co[0] = round(keyframe.co[0])
        for fcurve in fcurves:
            fcurve.update()
        context.area.tag_redraw()

    def draw_callback(self, _self, context):
        settings = context.scene.keyframe_sculpt_settings

        # Fetch the theme color for selected keyframes
        theme = bpy.context.preferences.themes["Default"]
        vertex_select_color = theme.view_3d.vertex_select

        # Set alpha values for inner and outer circles
        inner_color = (1, 1, 1, 1)
        outer_color = (*vertex_select_color[:3], 0.8)

        position = (self.mouse_x, self.mouse_y)

        gpu.state.blend_set("ALPHA")

        # Draw the outer circle
        draw_circle_2d(position, outer_color, settings.radius + settings.blend_radius)

        # Draw the inner circle
        draw_circle_2d(position, inner_color, settings.radius)

        # Drawing mode description at the bottom center
        if self.mode == "SMOOTH":
            current_mode = "Smoothing"
        elif self.mode == "SMOOTH_MACRO":
            current_mode = "Macro Smoothing"
        elif self.mode == "AVERAGE":
            current_mode = "Average Smoothing"
        else:
            current_mode = "Tweaking"

        text_to_display = f"{current_mode}"
        draw_text_bottom_center(context, text_to_display)

        # Determine position for help text
        text_x, text_y = 30, 40  # Example starting position
        draw_gui_help_text(context, text_x, text_y)

        # Reset blend state and continue with the rest of the drawing logic

        # Centralized text display logic
        if self.show_text and (time.time() - self.show_text_start_time < 1.5):
            # Adjust the position as needed based on your specific UI design
            central_position = (self.mouse_x, self.mouse_y)
            self._display_text(self.text_to_show, central_position)

        gpu.state.blend_set("NONE")

    # def calculate_delta(self, current_mouse_x, current_mouse_y):
    #     # Calculate delta since last adjustment
    #     delta = current_mouse_x - self.last_adjust_mouse_x
    #     # Update last adjustment positions
    #     self.last_adjust_mouse_x = current_mouse_x
    #     self.last_adjust_mouse_y = current_mouse_y
    #     return delta

    def calculate_delta(self, current_mouse_x, current_mouse_y):
        delta = current_mouse_x - self.initial_mouse_x
        return delta

    def display_message(self, context, message, display_time=2.0):
        """Display a message for a given amount of time."""
        context.window_manager.keyframe_sculpt_message = message
        context.window_manager.keyframe_sculpt_message_show = True
        # Schedule message hiding
        bpy.app.timers.register(lambda: self.hide_message(context), first_interval=display_time)

    def hide_message(self, context):
        """Hide the message."""
        context.window_manager.keyframe_sculpt_message_show = False
        context.window_manager.keyframe_sculpt_message = ""
        return None

    def modal(self, context, event):
        settings = context.scene.keyframe_sculpt_settings
        prefs = utils.get_prefs()
        wm = context.window_manager

        # Check if we've been cancelled externally (e.g., from button in popup)
        if not wm.anim_sculpt_running:
            self.cancel(context)
            return {"CANCELLED"}

        obj = context.active_object
        # self.offset = get_nla_strip_offset(obj)
        self.offset = 0

        sculpting_key = event.type == self.sculpting_key and event.value == "PRESS"

        # Toggle GUI help text
        if event.type == "H" and event.value == "PRESS":
            prefs.timeline_gui_toggle = not prefs.timeline_gui_toggle

        # Handle pressing of sculpting keys (R, S, B)
        if event.type in {"S", "R", "B"} and event.value == "PRESS" and not self.adjusting_value:
            # Capture the current state for resetting later if needed
            self.initial_radius = settings.radius
            self.initial_blend_radius = settings.blend_radius
            self.initial_strength = settings.strength
            self.value_being_adjusted = event.type
            self.adjusting_value = True
            self.initial_mouse_position_adjust_brush_size = (event.mouse_region_x, event.mouse_region_y)

            # Store the current brush position
            self.stored_brush_x = self.mouse_x
            self.stored_brush_y = self.mouse_y

            self.initial_radius = settings.radius
            self.initial_blend_radius = settings.blend_radius
            self.initial_strength = settings.strength
            self.value_being_adjusted = event.type
            self.adjusting_value = True

            self.initial_mouse_x = event.mouse_x
            self.initial_mouse_y = event.mouse_y

        # Handle releasing of sculpting keys (R, S, B)
        if self.adjusting_value and event.value == "RELEASE" and event.type in {"S", "R", "B"}:
            self.adjusting_value = False

        if event.type == "MOUSEMOVE":

            if self.rmb_pressed:
                context.window.cursor_modal_set("NONE")

            if self.adjusting_value:
                delta = self.calculate_delta(event.mouse_x, event.mouse_y)
                factor = 0.33

                if self.value_being_adjusted == "S":
                    settings.strength += delta * 0.1
                    self.text_to_show = f"Strength:\n{settings.strength:.0f}%"
                elif self.value_being_adjusted == "R":
                    settings.radius += delta * factor
                    self.text_to_show = f"Radius:\n{settings.radius:.2f}"
                elif self.value_being_adjusted == "B":
                    settings.blend_radius += delta * factor
                    self.text_to_show = f"Blend Radius:\n{settings.blend_radius:.2f}"

                self.show_text = True
                self.show_text_start_time = time.time()

                # Warp cursor back to initial position
                context.window.cursor_warp(self.initial_mouse_x, self.initial_mouse_y)

            else:
                self.mouse_x, self.mouse_y = event.mouse_region_x, event.mouse_region_y
                self.init_mouse_x, self.init_mouse_y = screen_to_graph(context, self.mouse_x, self.mouse_y)

                # Handle brush movement only if dragging and not adjusting
                if self.dragging and not self.adjusting_value:
                    if event.shift and event.ctrl:
                        self.mode = "AVERAGE"
                    elif event.shift:
                        self.mode = "SMOOTH"
                    else:
                        self.mode = "TWEAK"

                    # Calculate deltas based on the last known position
                    delta_x = event.mouse_region_x - self.last_mouse_x
                    delta_y = event.mouse_region_y - self.last_mouse_y

                    # Update the last known position
                    self.last_mouse_x, self.last_mouse_y = (
                        event.mouse_region_x,
                        event.mouse_region_y,
                    )

                    scale_x, scale_y = get_scale_factors(context)
                    graph_delta_x = delta_x * scale_x
                    graph_delta_y = delta_y * scale_y

                    if self.mode == "SMOOTH":
                        anim_sculpt_brush(
                            self,
                            context,
                            graph_delta_x,
                            graph_delta_y,
                            self.last_mouse_x,
                            self.last_mouse_y,
                            anim_sculpt_brush_smooth,
                            False,
                            True,
                            self.offset,
                        )
                    elif self.mode == "TWEAK":
                        anim_sculpt_brush(
                            self,
                            context,
                            graph_delta_x,
                            graph_delta_y,
                            self.last_mouse_x,
                            self.last_mouse_y,
                            anim_sculpt_brush_tweak,
                            False,
                            False,
                            self.offset,
                        )
                    elif self.mode == "AVERAGE":
                        anim_sculpt_brush(
                            self,
                            context,
                            graph_delta_x,
                            graph_delta_y,
                            self.last_mouse_x,
                            self.last_mouse_y,
                            anim_brush_brush_average,
                            True,
                            False,
                            self.offset,
                        )

        context.area.tag_redraw()

        # Handle 'L' key to cycle through sculpt lock modes
        if event.type == "L" and event.value == "PRESS":
            current_mode_index = ["UNLOCKED", "LOCK_FRAMES", "LOCK_VALUES"].index(settings.keyframes_sculpt_lock_mode)
            new_mode_index = (current_mode_index + 1) % 3
            settings.keyframes_sculpt_lock_mode = [
                "UNLOCKED",
                "LOCK_FRAMES",
                "LOCK_VALUES",
            ][new_mode_index]

            # Display the new mode
            self.text_to_show = settings.keyframes_sculpt_lock_mode.replace("_", " ").title()
            self.show_text = True
            self.show_text_start_time = time.time()

        # Handle mouse wheel for adjusting brush parameters
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"} and (event.shift or event.ctrl):
            if event.shift:
                if event.type == "WHEELUPMOUSE":
                    settings.blend_radius += 5.0
                else:
                    settings.blend_radius = max(settings.blend_radius - 5.0, 0.0)
                self.text_to_show = f"Blend Radius:\n {settings.blend_radius:.2f}"
            elif event.ctrl:
                if event.type == "WHEELUPMOUSE":
                    settings.strength = min(settings.strength + 1, 100.0)
                else:
                    settings.strength = max(settings.strength - 1, 0.0)
                self.text_to_show = f"Strength:\n{settings.strength:.0f} %"
            else:
                if event.type == "WHEELUPMOUSE":
                    settings.radius += 5.0
                else:
                    settings.radius = max(settings.radius - 5.0, 1.0)
                self.text_to_show = f"Radius:\n{settings.radius:.2f}"
            self.show_text = True
            self.show_text_start_time = time.time()

        elif event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE", "MIDDLEMOUSE"}:
            return {"PASS_THROUGH"}

        if event.type == self.scrubbing_key:
            return {"PASS_THROUGH"}

        # Handle left mouse button for starting and stopping dragging
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self.last_mouse_x, self.last_mouse_y = (
                event.mouse_region_x,
                event.mouse_region_y,
            )
            self.init_mouse_x, self.init_mouse_y = (
                event.mouse_region_x,
                event.mouse_region_y,
            )
            self.dragging = True
            self.mode_message_shown = False
            prefs.is_sculpting = True
            context.window.cursor_modal_set("NONE")
            bpy.ops.ed.undo_push(message="Start Anim Sculpt")

        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            if settings.snap_to_frames:
                self.snap_keyframes_to_frames(context)
            self.dragging = False
            prefs.is_sculpting = False
            self.calculated_selected_kf_average = 0
            self.neighbours_distances_cached = {}

        # Handle canceling the operator
        if event.type in {"ESC", "RET"} or sculpting_key:
            # Finish the modal operation
            self.cancel(context)
            return {"CANCELLED"}

        # Handle right mouse button for options
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            bpy.ops.wm.call_panel(name="AMP_PT_AnimSculptOptions", keep_open=True)
            context.window.cursor_modal_set("DEFAULT")
            self.rmb_pressed = True

        # Handle undo/redo shortcuts
        if (event.type == "Z" and event.value == "PRESS") and (event.ctrl or event.oskey):
            bpy.ops.ed.undo()
            return {"RUNNING_MODAL"}

        if (event.type == "Z" and event.value == "PRESS") and (event.ctrl or event.oskey) and event.shift:
            bpy.ops.ed.redo()
            return {"RUNNING_MODAL"}

        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        if event.shift:
            bpy.ops.wm.call_panel(name="AMP_PT_AnimSculptOptions", keep_open=True)
            return {"FINISHED"}

        return self.execute(context)

    def execute(self, context):
        wm = context.window_manager

        # If AnimSculpt is already running, cancel it by setting the flag
        # The existing modal operator will detect this in its modal() method
        if wm.anim_sculpt_running:
            wm.anim_sculpt_running = False
            return {"CANCELLED"}

        # Checks for normalization on start and end
        self.initial_use_normalization = False
        self.initial_view_settings = {}

        self.initial_use_normalization = context.space_data.use_normalization
        if self.initial_use_normalization:
            context.space_data.use_normalization = False

        wm.anim_sculpt_running = True

        self.calculated_selected_kf_average = 0
        self.neighbours_distances_cached = {}
        self.sculpting_key = utils.find_key_for_operator("anim.amp_anim_sculpt")
        self.scrubbing_key = utils.find_key_for_operator("anim.amp_timeline_scrub")

        # Safeguard: Remove any existing draw handler to prevent duplicates
        if self._handle is not None:
            bpy.types.SpaceGraphEditor.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        if context.area.type == "GRAPH_EDITOR":
            # Get event from context - use mouse position from region
            self.mouse_x = context.region.width // 2  # Default to center if no event
            self.mouse_y = context.region.height // 2
            self.init_graph_x, self.init_graph_y = screen_to_graph(context, self.mouse_x, self.mouse_y)
            self.stored_brush_x = self.mouse_x
            self.stored_brush_y = self.mouse_y
            args = (self, context)
            self._handle = bpy.types.SpaceGraphEditor.draw_handler_add(self.draw_callback, args, "WINDOW", "POST_PIXEL")
            context.window.cursor_modal_set("NONE")
            context.window_manager.modal_handler_add(self)
            context.area.tag_redraw()
            self.text_to_show = ""
            self.show_text = False
            self.show_text_start_time = 0

            return {"RUNNING_MODAL"}
        else:
            wm.anim_sculpt_running = False
            return {"CANCELLED"}

    def cancel(self, context):
        settings = context.scene.keyframe_sculpt_settings
        prefs = utils.get_prefs()
        if self.initial_use_normalization:
            context.space_data.use_normalization = True

        wm = context.window_manager
        wm.anim_sculpt_running = False
        if self._handle:
            bpy.types.SpaceGraphEditor.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        prefs.is_sculpting = False
        context.window.cursor_modal_restore()
        context.area.tag_redraw()
        self.report({"INFO"}, "Anim sculpt cancelled")


class AMP_PG_AnimSculptSettings(bpy.types.PropertyGroup):
    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Radius of 100% influence",
        default=50,
        min=1,
        max=500,
    )

    blend_radius: bpy.props.FloatProperty(
        name="Blend Offset",
        description="Offset from Radius where influence fades to 0%",
        default=50,
        min=0,
        max=500,
    )
    strength: bpy.props.FloatProperty(
        name="Strength",
        description="Strength of the brush",
        default=100,
        min=0.1,
        max=100,
        subtype="PERCENTAGE",
        precision=0,
    )

    smoothing_multiplier: bpy.props.FloatProperty(
        name="Smoothing Multiplier",
        description="Multiplier for smoothing strength",
        default=1.0,
        min=0.01,
        max=2.0,
    )

    keyframes_sculpt_lock_mode: bpy.props.EnumProperty(
        name="Sculpt Lock Mode",
        items=[
            ("UNLOCKED", "Unlocked", ""),
            ("LOCK_FRAMES", "Lock Frames", ""),
            ("LOCK_VALUES", "Lock Values", ""),
        ],
        default="LOCK_FRAMES",
        description="Control which aspects of the keyframes can be modified",
    )

    snap_to_frames: bpy.props.BoolProperty(
        name="Snap To Full Frames",
        description="Snap keyframe frames to the nearest integer value upon release",
        default=True,
    )

    scope: bpy.props.EnumProperty(
        name="Scope",
        items=[
            ("ONLY_SELECTED", "Only Selected fcurves", ""),
            ("PIN_SELECTED", "Pin Selected Keyframes", ""),
            ("VISIBLE", "Sculpt on Visible", ""),
        ],
        default="VISIBLE",
        description="Which keyframes to affect",
    )

    pin_border_keyframes: bpy.props.BoolProperty(
        name="Pin Border Keyframes",
        description="Pin keyframes at the border of each fcurve",
        default=True,
    )

    is_sculpting: bpy.props.BoolProperty(default=False)


class AMP_PT_AnimSculptOptions(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_AnimSculptOptions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        draw_anim_sculpt_options(layout, context)


def draw_anim_sculpt_options(layout, context):
    props = context.scene.keyframe_sculpt_settings
    layout.use_property_split = True
    layout.use_property_decorate = False

    layout.label(text="Anim Sculpt Options", **get_icon("AMP_anim_sculpt"))

    ui_column = layout.column()

    # Add Start/Stop AnimSculpt button
    ui_column.separator()

    # Check if anim sculpt is running to determine button text
    wm = context.window_manager
    button_text = "Stop AnimSculpt" if wm.anim_sculpt_running else "Start AnimSculpt"
    btn = ui_column.operator("anim.amp_anim_sculpt", text=button_text, **get_icon("AMP_anim_sculpt"))

    ui_column.separator()

    brushes_col = ui_column.column(align=True)
    brushes_col.label(text="        Tweak: LMB")
    brushes_col.label(text="        Smooth: SHIFT + LMB")
    brushes_col.label(text="        Average: CTRL + SHIFT + LMB")

    ui_column.separator(factor=2)

    box = ui_column.box()

    container = box.column(align=False)

    # Radius
    container.prop(props, "radius", text="Radius", slider=True)

    # Blend Radius
    container.prop(props, "blend_radius", text="Blend Radius", slider=True)

    # Strength
    container.prop(props, "strength", text="Strength", slider=True)

    # Smoothing Reduction
    container.prop(props, "smoothing_multiplier", text="Smoothing Multiplier", slider=True)

    # Scope
    container.prop(props, "scope", text="Scope")

    # Lock Mode
    container.prop(props, "keyframes_sculpt_lock_mode", text="Lock Mode")

    # Snap to Frames
    container.prop(props, "snap_to_frames", text="Snap to Full Frames")

    # Pin borders
    container.prop(props, "pin_border_keyframes", text="Pin Border Keyframes")


def AnimSculptButton(layout, context, label="", icon_value=1):
    row = layout.row(align=True)
    row.operator(
        "anim.amp_anim_sculpt",
        text=label,
        icon_value=icon_value,
    )


classes = (
    AMP_OT_anim_sculpt,
    AMP_PG_AnimSculptSettings,
    AMP_PT_AnimSculptOptions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add the property group to the Scene
    Scene.keyframe_sculpt_settings = bpy.props.PointerProperty(type=AMP_PG_AnimSculptSettings)

    # Add properties to the WindowManager to display messages
    bpy.types.WindowManager.keyframe_sculpt_message = bpy.props.StringProperty(default="")
    bpy.types.WindowManager.keyframe_sculpt_message_show = bpy.props.BoolProperty(default=False)

    # Add the property to track if the operator is running
    bpy.types.WindowManager.anim_sculpt_running = bpy.props.BoolProperty(default=False)


def unregister():
    # Delete the properties from the WindowManager for displaying messages
    del bpy.types.WindowManager.keyframe_sculpt_message
    del bpy.types.WindowManager.keyframe_sculpt_message_show

    # Remove the property tracking if the operator is running
    del bpy.types.WindowManager.anim_sculpt_running

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del Scene.keyframe_sculpt_settings
