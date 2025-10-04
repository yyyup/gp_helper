import bpy
import gpu
import blf
import math
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from .. import utils
from ..utils import ensure_alpha, get_dpi_scale, dprint


# Global variables for the draw handlers
_draw_handlers = {}
_is_handler_registered = False


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


def get_adaptive_second_interval(view_range_seconds):
    """Get appropriate second interval based on zoom level with progressive decluttering."""
    if view_range_seconds <= 15:  # Reduced from 20 to start simplifying earlier
        return 1  # Every 1 second
    elif view_range_seconds <= 80:  # Reduced from 100
        return 5  # Every 5 seconds
    elif view_range_seconds <= 250:  # Reduced from 300
        return 15  # Every 15 seconds
    elif view_range_seconds <= 500:  # Reduced from 600
        return 30  # Every 30 seconds
    elif view_range_seconds <= 1000:  # Reduced from 1200
        return 60  # Every 1 minute
    elif view_range_seconds <= 5000:  # Reduced from 6000
        return 300  # Every 5 minutes
    elif view_range_seconds <= 15000:  # Reduced from 18000
        return 900  # Every 15 minutes
    elif view_range_seconds <= 30000:  # Reduced from 36000
        return 1800  # Every 30 minutes
    elif view_range_seconds <= 60000:  # Reduced from 72000
        return 3600  # Every 1 hour
    else:
        # For very large ranges, use progressive doubling from 2 hours
        hours = max(2, int(view_range_seconds / 3600 / 6))  # Start from 2 hours, increase by factor of view size
        # Round to nearest power of 2
        hours = 2 ** math.ceil(math.log2(hours))
        return hours * 3600


def format_time_with_units(seconds):
    """Format time value with appropriate unit suffix and time notation.
    Always returns positive values - negative indication is handled by color.

    Format rules:
    - Under 60s: "30s"
    - 60s to 59:59: "1m 30s"
    - 1h+: "1h", "1h 05m", "1h 05m 45s" depending on precision needed
    """
    abs_seconds = abs(seconds)

    if abs_seconds < 60:
        # Display in seconds only: "30s"
        if abs(abs_seconds - round(abs_seconds)) < 0.001:  # Essentially a whole number
            return f"{int(round(abs_seconds))}s"
        else:
            return f"{abs_seconds:.1f}s"
    elif abs_seconds < 3600:
        # Display as "Xm Ys": "1m 30s" or "4m 00s"
        total_seconds = int(round(abs_seconds))
        minutes = total_seconds // 60
        remaining_seconds = total_seconds % 60

        # Always show both minutes and seconds for consistency
        return f"{minutes}m {remaining_seconds:02d}s"
    else:
        # For hours, we need to be smart about what to display
        total_seconds = int(round(abs_seconds))
        hours = total_seconds // 3600
        remaining_minutes = (total_seconds % 3600) // 60
        remaining_seconds = total_seconds % 60

        # Start with hours
        result = f"{hours}h"

        # Always show minutes when hours are present
        result += f" {remaining_minutes:02d}m"

        # Add seconds if present (only if minutes are 0 to avoid clutter)
        if remaining_seconds > 0 and remaining_minutes == 0:
            result += f" {remaining_seconds:02d}s"

        return result


def draw_circle_vertices(center_x, center_y, radius, segments=16):
    """Generate vertices for a filled circle."""
    vertices = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        vertices.append((x, y))
    return vertices


def draw_square_vertices(center_x, center_y, size):
    """Generate vertices for a filled square."""
    half_size = size / 2
    return [
        (center_x - half_size, center_y - half_size),
        (center_x + half_size, center_y - half_size),
        (center_x + half_size, center_y + half_size),
        (center_x - half_size, center_y + half_size),
    ]


def draw_diamond_vertices(center_x, center_y, size):
    """Generate vertices for a filled diamond (rotated square)."""
    half_size = size / 2
    return [
        (center_x, center_y - half_size),  # Top
        (center_x + half_size, center_y),  # Right
        (center_x, center_y + half_size),  # Bottom
        (center_x - half_size, center_y),  # Left
    ]


def draw_rectangle_vertices(x1, y1, x2, y2):
    """Generate vertices for a filled rectangle."""
    return [
        (x1, y1),
        (x2, y1),
        (x2, y2),
        (x1, y2),
    ]


def draw_capsule_vertices(center_x, center_y, width, height):
    """Generate vertices for a capsule shape (rectangle with half-circles on ends)."""
    vertices = []
    radius = height // 2

    # If width is smaller than height, just draw a circle
    if width <= height:
        return draw_circle_vertices(center_x, center_y, radius)

    # Rectangle width (excluding the rounded ends)
    rect_width = width - height
    left_center = center_x - rect_width // 2
    right_center = center_x + rect_width // 2

    # Left half-circle (from top to bottom, clockwise)
    segments = 8  # Half circle segments
    for i in range(segments + 1):
        angle = math.pi / 2 + (math.pi * i / segments)  # From 90° to 270°
        x = left_center + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        vertices.append((x, y))

    # Right half-circle (from bottom to top, clockwise)
    for i in range(segments + 1):
        angle = 3 * math.pi / 2 + (math.pi * i / segments)  # From 270° to 90° (opposite direction)
        x = right_center + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        vertices.append((x, y))

    return vertices


def draw_elongated_diamond_vertices(center_x, center_y, width, height):
    """Generate vertices for an elongated diamond shape."""
    half_width = width // 2
    half_height = height // 2

    # If width is smaller than height, just draw a normal diamond
    if width <= height:
        return draw_diamond_vertices(center_x, center_y, height)

    # Calculate the diamond shape with extended middle
    diamond_tip_width = height // 2  # Width of the diamond tips
    rect_width = width - height

    vertices = [
        # Left diamond tip
        (center_x - half_width, center_y),  # Far left point
        (center_x - rect_width // 2, center_y - half_height),  # Top left of rectangle
        (center_x + rect_width // 2, center_y - half_height),  # Top right of rectangle
        # Right diamond tip
        (center_x + half_width, center_y),  # Far right point
        (center_x + rect_width // 2, center_y + half_height),  # Bottom right of rectangle
        (center_x - rect_width // 2, center_y + half_height),  # Bottom left of rectangle
    ]

    return vertices


def draw_visual_aids_overlay():
    """Main draw function for visual aids overlay."""
    try:
        # Get the current context
        context = bpy.context

        # Check if we're in a supported editor
        if not context.space_data or context.space_data.type not in [
            "GRAPH_EDITOR",
            "DOPESHEET_EDITOR",
            "NLA_EDITOR",
            "SEQUENCE_EDITOR",
        ]:
            return

        # Get preferences to check if visual aids are enabled
        prefs = utils.get_prefs()
        if not hasattr(prefs, "visualaid_anim_editors") or not prefs.visualaid_anim_editors:
            return

        # Check editor-specific toggles
        editor_type = context.space_data.type
        if editor_type == "GRAPH_EDITOR" and not prefs.visualaid_display_in_graph:
            return
        elif editor_type == "DOPESHEET_EDITOR" and not prefs.visualaid_display_in_dope:
            return
        elif editor_type == "NLA_EDITOR" and not prefs.visualaid_display_in_nla:
            return
        elif editor_type == "SEQUENCE_EDITOR" and not prefs.visualaid_display_in_sequencer:
            return

        # Check if we have a scene
        if not context.scene:
            return

        # Check if hidden during playback
        if prefs.visualaid_hide_during_playback and context.screen.is_animation_playing:
            return

        # Get view bounds and frame rate
        view_min_x, view_min_y, view_max_x, view_max_y = get_view_bounds(context)
        if view_min_x is None:
            return

        fps = context.scene.render.fps
        scale = get_dpi_scale()

        # Store original view bounds for decluttering calculation
        original_view_min_x = view_min_x
        original_view_max_x = view_max_x

        # Check scene range restriction for drawing bounds
        if prefs.visualaid_restrict_to_scene_range:
            scene_start = context.scene.frame_start
            scene_end = context.scene.frame_end
            # Clamp view bounds to scene range for drawing purposes
            view_min_x = max(view_min_x, scene_start)
            view_max_x = min(view_max_x, scene_end)

            # If no overlap with scene range, don't draw anything
            if view_min_x >= view_max_x:
                return

        # Determine the frame range to use based on preview range preference
        if prefs.visualaid_focus_preview_range and context.scene.use_preview_range:
            # Use preview range as the reference point
            reference_start_frame = context.scene.frame_preview_start
            reference_end_frame = context.scene.frame_preview_end
            use_range_restriction = True
        else:
            # Use scene frame range as the reference point instead of frame 0
            reference_start_frame = context.scene.frame_start
            reference_end_frame = context.scene.frame_end
            use_range_restriction = prefs.visualaid_restrict_to_scene_range

        reference_start_second = reference_start_frame / fps

        # Calculate decluttering interval based on ORIGINAL visible range, not restricted range
        # This ensures consistent decluttering regardless of range restriction
        original_view_range_seconds = (original_view_max_x - original_view_min_x) / fps
        second_interval = get_adaptive_second_interval(original_view_range_seconds)

        # Calculate start and end seconds based on reference start alignment
        # Use original view bounds to ensure we capture all intervals that might be visible
        first_visible_second = original_view_min_x / fps
        last_visible_second = original_view_max_x / fps

        # Align to interval relative to reference start, ensuring we capture all visible intervals
        # Calculate how many intervals from reference start to the first visible second
        intervals_from_reference_start = math.floor((first_visible_second - reference_start_second) / second_interval)

        # Start from one interval before to ensure we don't miss partially visible intervals
        start_second = reference_start_second + ((intervals_from_reference_start - 1) * second_interval)

        # End one interval after to ensure we capture all partially visible intervals
        end_second = last_visible_second + second_interval

        # Enable blending for transparency for all drawing operations
        gpu.state.blend_set("ALPHA")

        # Draw header bar (if enabled)
        if prefs.visualaid_display_header_bar:
            draw_header_bar(context, prefs, scale)

        # Draw checker pattern (if enabled)
        if prefs.visualaid_display_checkers:
            draw_checker_pattern(
                context,
                prefs,
                scale,
                start_second,
                end_second,
                second_interval,
                fps,
                original_view_min_x,
                original_view_max_x,
                reference_start_second,
                reference_start_frame,
                reference_end_frame,
                use_range_restriction,
            )

        # Draw second markers (if enabled)
        if prefs.visualaid_display_time_markers:
            draw_second_markers(
                context,
                prefs,
                scale,
                start_second,
                end_second,
                second_interval,
                fps,
                original_view_min_x,
                original_view_max_x,
                reference_start_second,
                reference_start_frame,
                reference_end_frame,
                use_range_restriction,
            )

        # Reset blend state
        gpu.state.blend_set("NONE")

    except Exception as e:
        # Silently handle errors to prevent Blender crashes
        dprint(f"Error in visual aids overlay: {e}")
        import traceback

        traceback.print_exc()
        pass


def draw_header_bar(context, prefs, scale):
    """Draw the header bar at the top of the editor."""
    region = context.region

    # Header dimensions
    header_height = int(25 * scale)

    # Create rectangle vertices for header
    vertices = draw_rectangle_vertices(0, region.height - header_height, region.width, region.height)

    # Draw header background
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})

    shader.bind()
    header_color = ensure_alpha(prefs.visualaid_header_color)
    shader.uniform_float("color", header_color)
    batch.draw(shader)


def draw_checker_pattern(
    context,
    prefs,
    scale,
    start_second,
    end_second,
    second_interval,
    fps,
    original_view_min_x,
    original_view_max_x,
    reference_start_second,
    reference_start_frame,
    reference_end_frame,
    use_range_restriction,
):
    """Draw alternating transparent rectangles between seconds."""
    view_min_x, view_min_y, view_max_x, view_max_y = get_view_bounds(context)

    # Generate all potential second values in the range, ensuring we don't miss any
    current_second = start_second
    while current_second <= end_second:
        next_second = current_second + second_interval

        # Check if we should skip negative time markers
        if not prefs.visualaid_display_negative_time and current_second < 0:
            current_second += second_interval
            continue

        # Determine if this interval should have a dark overlay
        # Calculate the interval index relative to reference start
        # We want: reference_start to reference_start+1 (no overlay), reference_start+1 to reference_start+2 (overlay), etc.
        intervals_from_reference_start = round((current_second - reference_start_second) / second_interval)

        # Only draw overlay for odd-numbered intervals relative to reference start
        if intervals_from_reference_start % 2 != 0:  # Draw only odd intervals (1-2, 3-4, 5-6, etc.)
            # Convert seconds to frames
            start_frame = current_second * fps
            end_frame = next_second * fps

            # Apply range restriction if enabled
            if use_range_restriction:
                # Only draw if the interval overlaps with both the original visible range and reference range
                if (
                    end_frame < original_view_min_x
                    or start_frame > original_view_max_x
                    or end_frame < reference_start_frame
                    or start_frame > reference_end_frame
                ):
                    current_second += second_interval
                    continue
                # Clamp to both original visible range and reference range
                visible_start_frame = max(start_frame, original_view_min_x, reference_start_frame)
                visible_end_frame = min(end_frame, original_view_max_x, reference_end_frame)
            else:
                # Only draw if the interval overlaps with the original visible range
                if end_frame < original_view_min_x or start_frame > original_view_max_x:
                    current_second += second_interval
                    continue
                # Clamp to original visible range to ensure rectangles extend to screen edges
                visible_start_frame = max(start_frame, original_view_min_x)
                visible_end_frame = min(end_frame, original_view_max_x)

            # Get screen coordinates
            start_screen_x, start_screen_y = graph_to_screen(context, visible_start_frame, view_min_y)
            end_screen_x, end_screen_y = graph_to_screen(context, visible_end_frame, view_max_y)

            if start_screen_x is not None and end_screen_x is not None:
                # Create rectangle vertices that extend to screen edges
                vertices = draw_rectangle_vertices(start_screen_x, 0, end_screen_x, context.region.height)

                # Draw checker rectangle
                shader = gpu.shader.from_builtin("UNIFORM_COLOR")
                batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})

                shader.bind()
                checker_color = ensure_alpha(prefs.visualaid_checker_color)
                shader.uniform_float("color", checker_color)
                batch.draw(shader)

        # Move to next interval
        current_second += second_interval


def draw_second_markers(
    context,
    prefs,
    scale,
    start_second,
    end_second,
    second_interval,
    fps,
    original_view_min_x,
    original_view_max_x,
    reference_start_second,
    reference_start_frame,
    reference_end_frame,
    use_range_restriction,
):
    """Draw second markers with shapes and text."""
    region = context.region
    view_min_x, view_min_y, view_max_x, view_max_y = get_view_bounds(context)

    # Marker properties
    marker_size = int(20 * scale * prefs.visualaid_scale_factor)

    # Calculate marker Y position based on text position preference
    vertical_offset = int(prefs.visualaid_vertical_offset * scale)

    # Get text position preference
    text_position = prefs.visualaid_text_position

    # Calculate base Y position based on text position with proper offset behavior
    if text_position == "TOP":
        # TOP: Only positive offsets (push down), negatives ignored
        effective_offset = max(0, vertical_offset)
        marker_y = region.height - int(12 * scale) - effective_offset
    elif text_position == "MIDDLE":
        # MIDDLE: Both positive (up) and negative (down) offsets allowed
        marker_y = region.height // 2 - vertical_offset
    elif text_position == "BOTTOM":
        # BOTTOM: Only positive offsets (push up), negatives ignored
        effective_offset = max(0, vertical_offset)
        marker_y = int(12 * scale) + effective_offset
    else:
        # Fallback to top
        effective_offset = max(0, vertical_offset)
        marker_y = region.height - int(12 * scale) - effective_offset

    # Generate all potential second values in the range, ensuring we don't miss any
    current_second = start_second
    while current_second <= end_second:
        # Convert second to frame
        frame = current_second * fps

        # Check if we should skip negative time markers
        if not prefs.visualaid_display_negative_time and current_second < 0:
            current_second += second_interval
            continue

        # Apply range restriction if enabled
        if use_range_restriction and (frame < reference_start_frame or frame > reference_end_frame):
            current_second += second_interval
            continue

        # Only draw markers that are within a reasonable range of the original visible area
        # Include some padding to ensure markers are visible even when partially off-screen
        marker_padding = marker_size / 2  # Padding in screen pixels

        # Convert padding to graph space using original view bounds
        padding_in_graph_space = marker_padding * (original_view_max_x - original_view_min_x) / region.width

        # Only draw if the marker overlaps with the original visible range (with padding)
        if not (
            frame < (original_view_min_x - padding_in_graph_space)
            or frame > (original_view_max_x + padding_in_graph_space)
        ):
            # Get screen coordinates
            screen_x, screen_y = graph_to_screen(context, frame, 0)
            if screen_x is not None:
                # Only draw if the marker center is reasonably positioned
                if not (screen_x < -marker_size or screen_x > (region.width + marker_size)):
                    # Calculate the second number relative to reference start (reference start = 0)
                    actual_second = (frame - reference_start_frame) / fps

                    # Draw shape container with the reference-relative second number
                    draw_shape_container(context, prefs, screen_x, marker_y, marker_size, actual_second)

        # Move to next interval
        current_second += second_interval


def draw_shape_container(context, prefs, center_x, center_y, size, second_number):
    """Draw the shape container (circle, square, or diamond) with text."""
    scale = get_dpi_scale()

    # Setup text drawing to measure text dimensions first
    font_id = 0
    font_size = int(10 * scale * prefs.visualaid_scale_factor)
    blf.size(font_id, font_size)

    # Get text and measure its dimensions
    text = format_time_with_units(second_number)
    text_width, text_height = blf.dimensions(font_id, text)

    # Calculate minimum width needed for text with some padding
    text_padding = int(6 * scale)  # Padding around text
    min_width = text_width + (2 * text_padding)

    # Determine shape width (ensure it's at least the minimum size)
    base_width = size
    shape_width = max(base_width, min_width)

    # Generate vertices based on shape type with dynamic width
    if prefs.visualaid_shape_type == "CIRCLE":
        vertices = draw_capsule_vertices(center_x, center_y, shape_width, size)
    elif prefs.visualaid_shape_type == "SQUARE":
        vertices = draw_rectangle_vertices(
            center_x - shape_width // 2, center_y - size // 2, center_x + shape_width // 2, center_y + size // 2
        )
    elif prefs.visualaid_shape_type == "DIAMOND":
        vertices = draw_elongated_diamond_vertices(center_x, center_y, shape_width, size)

    # Ensure alpha blending is enabled for shape transparency
    gpu.state.blend_set("ALPHA")

    # Draw shape background only if enabled
    if prefs.visualaid_display_shape_background:
        # Draw shape
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})

        shader.bind()

        # Use slightly tinted shape color for negative times
        if second_number < -0.5:
            # Mix normal shape color with negative time color for subtle tinting
            base_color = list(ensure_alpha(prefs.visualaid_shape_color))
            negative_color = list(ensure_alpha(prefs.visualaid_negative_time_color))
            # Blend 80% base color with 20% negative color for subtle effect
            shape_color = [
                base_color[0] * 0.8 + negative_color[0] * 0.2,
                base_color[1] * 0.8 + negative_color[1] * 0.2,
                base_color[2] * 0.8 + negative_color[2] * 0.2,
                base_color[3],  # Keep original alpha
            ]
        else:
            shape_color = ensure_alpha(prefs.visualaid_shape_color)

        shader.uniform_float("color", shape_color)
        batch.draw(shader)

    # Draw text (reuse the already calculated text and dimensions)
    draw_second_text_with_dims(center_x, center_y, second_number, prefs, text, text_width, text_height)


def draw_second_text(center_x, center_y, second_number, prefs):
    """Draw the second number text inside the shape."""
    scale = get_dpi_scale()

    # Setup text drawing
    font_id = 0
    font_size = int(10 * scale * prefs.visualaid_scale_factor)
    blf.size(font_id, font_size)

    # Use the new format with units
    text = format_time_with_units(second_number)
    text_width, text_height = blf.dimensions(font_id, text)

    # Call the optimized version
    draw_second_text_with_dims(center_x, center_y, second_number, prefs, text, text_width, text_height)


def draw_second_text_with_dims(center_x, center_y, second_number, prefs, text, text_width, text_height):
    """Draw the second number text inside the shape using pre-calculated dimensions."""
    scale = get_dpi_scale()

    # Setup text drawing (font size should already be set, but ensure consistency)
    font_id = 0
    font_size = int(10 * scale * prefs.visualaid_scale_factor)
    blf.size(font_id, font_size)

    # Position text in center of shape
    text_x = center_x - text_width // 2
    text_y = center_y - text_height // 2

    # Check if text shadow is enabled
    display_shadow = prefs.visualaid_display_text_shadow

    # Draw text with shadow (if enabled)
    if display_shadow:
        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 5, 0, 0, 0, 1)
        blf.shadow_offset(0, int(1 * scale), int(-1 * scale))

    # Set text color based on whether time is negative or positive
    if second_number < -0.5:
        # Use negative time color for negative values
        text_color = ensure_alpha(prefs.visualaid_negative_time_color)
    else:
        # Use normal text color for positive values
        text_color = ensure_alpha(prefs.visualaid_text_color)

    blf.color(font_id, *text_color)

    blf.position(font_id, text_x, text_y, 0)
    blf.draw(font_id, text)

    if display_shadow:
        blf.disable(0, blf.SHADOW)


def update_visual_aids_toggle(self, context):
    """Update function for toggling visual aids on/off."""
    prefs = utils.get_prefs()

    # Always unregister first to avoid conflicts
    unregister_visual_aids_handler()

    if prefs.visualaid_anim_editors:
        register_visual_aids_handler()


def register_visual_aids_handler():
    """Register the visual aids draw handler for all animation editors."""
    global _draw_handlers, _is_handler_registered

    # Ensure we're not already registered
    if _is_handler_registered:
        dprint("Visual aids handlers already registered, skipping...")
        return

    try:
        # Register for Graph Editor
        _draw_handlers["GRAPH_EDITOR"] = bpy.types.SpaceGraphEditor.draw_handler_add(
            draw_visual_aids_overlay, (), "WINDOW", "POST_PIXEL"
        )

        # Register for Dope Sheet Editor
        _draw_handlers["DOPESHEET_EDITOR"] = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
            draw_visual_aids_overlay, (), "WINDOW", "POST_PIXEL"
        )

        # Register for NLA Editor
        _draw_handlers["NLA_EDITOR"] = bpy.types.SpaceNLA.draw_handler_add(
            draw_visual_aids_overlay, (), "WINDOW", "POST_PIXEL"
        )

        # Register for Video Sequencer Editor
        _draw_handlers["SEQUENCE_EDITOR"] = bpy.types.SpaceSequenceEditor.draw_handler_add(
            draw_visual_aids_overlay, (), "WINDOW", "POST_PIXEL"
        )

        _is_handler_registered = True
        dprint("Visual aids handlers registered for all animation and video sequencer editors")

    except Exception as e:
        dprint(f"Error registering visual aids handlers: {e}")
        _draw_handlers.clear()
        _is_handler_registered = False


def unregister_visual_aids_handler():
    """Unregister the visual aids draw handlers from all animation editors."""
    global _draw_handlers, _is_handler_registered

    if not _is_handler_registered and not _draw_handlers:
        return

    try:
        # Unregister Graph Editor handler
        if "GRAPH_EDITOR" in _draw_handlers and _draw_handlers["GRAPH_EDITOR"] is not None:
            try:
                bpy.types.SpaceGraphEditor.draw_handler_remove(_draw_handlers["GRAPH_EDITOR"], "WINDOW")
            except Exception as e:
                dprint(f"Error removing Graph Editor handler: {e}")

        # Unregister Dope Sheet Editor handler
        if "DOPESHEET_EDITOR" in _draw_handlers and _draw_handlers["DOPESHEET_EDITOR"] is not None:
            try:
                bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_draw_handlers["DOPESHEET_EDITOR"], "WINDOW")
            except Exception as e:
                dprint(f"Error removing Dope Sheet handler: {e}")

        # Unregister NLA Editor handler
        if "NLA_EDITOR" in _draw_handlers and _draw_handlers["NLA_EDITOR"] is not None:
            try:
                bpy.types.SpaceNLA.draw_handler_remove(_draw_handlers["NLA_EDITOR"], "WINDOW")
            except Exception as e:
                dprint(f"Error removing NLA Editor handler: {e}")

        # Unregister Video Sequencer Editor handler
        if "SEQUENCE_EDITOR" in _draw_handlers and _draw_handlers["SEQUENCE_EDITOR"] is not None:
            try:
                bpy.types.SpaceSequenceEditor.draw_handler_remove(_draw_handlers["SEQUENCE_EDITOR"], "WINDOW")
            except Exception as e:
                dprint(f"Error removing Video Sequencer handler: {e}")

        dprint("Visual aids handlers unregistered from all animation and video sequencer editors")

    except Exception as e:
        dprint(f"Error unregistering visual aids handlers: {e}")
    finally:
        # Always clear the state regardless of errors
        _draw_handlers.clear()
        _is_handler_registered = False


class AMP_OT_ToggleVisualAids(bpy.types.Operator):
    """Toggle Animation Visual Aids on/off."""

    bl_idname = "anim.amp_toggle_visual_aids"
    bl_label = "Toggle Visual Aids"
    bl_description = "Toggle animation visual aids in all animation and video sequencer editors"
    bl_options = {"REGISTER"}

    def execute(self, context):
        prefs = utils.get_prefs()
        prefs.visualaid_anim_editors = not prefs.visualaid_anim_editors

        status = "enabled" if prefs.visualaid_anim_editors else "disabled"
        self.report({"INFO"}, f"Animation visual aids {status}")

        return {"FINISHED"}


# Classes to register
classes = (AMP_OT_ToggleVisualAids,)


def register():
    """Register classes and properties."""
    # Register classes first
    for cls in classes:
        bpy.utils.register_class(cls)

    try:
        unregister_visual_aids_handler()
    except Exception as e:
        pass

    # Register handler if preference is already enabled
    # Use a timer to delay this check until after preferences are fully loaded
    bpy.app.timers.register(_delayed_handler_check, first_interval=0.1)


def _delayed_handler_check():
    """Delayed check for enabling visual aids handler if preference is set."""

    try:
        prefs = utils.get_prefs()
        if hasattr(prefs, "visualaid_anim_editors") and prefs.visualaid_anim_editors:
            register_visual_aids_handler()
    except Exception as e:
        dprint(f"Error checking visual aids preference: {e}")
    # Return None to unregister the timer (run only once)
    return None


def unregister():
    """Unregister classes and properties."""
    # Unregister handler
    try:
        unregister_visual_aids_handler()
    except Exception as e:
        pass

    # Unregister classes
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            dprint(f"Error unregistering class {cls}: {e}")
