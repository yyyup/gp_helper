"""
AniMate Pro Scope GUI - Modular GUI Pin System

This module provides a flexible GUI system for creating animated scope interfaces
with adjustable influence pins, intensity handlers, and blending options.

Features:
- 4 GPU pins for influence management (2 main at 100%, 2 secondary with gradient)
- Draggable intensity handler with percentage control (2x faster drag speed)
- Draggable multiplier handler for intensity amplification (2x faster drag speed)
- Blending option selectors with visual feedback (2x faster drag speed)
- Clickable operation selector with drag-to-change functionality (uses same system as blend selectors)
- Configurable colors and behavior
- Modular design for easy integration

Positioning System:
Elements are positioned using a dual-level system:

TOP (from top down):
- 2 empty margin units
- Level 1: Operation name box (clickable/draggable)
- Level 2: % intensity box (center) with multiplier box (beside % box)

BOTTOM (from bottom up):
- 2 empty margin units
- Level 1: Secondary pin handlers, secondary bars, outer bar, and blending selectors (beside secondary pins)
- Level 2: Main pin handlers and main pins bar

Interactive Features:
- Operation name box: Click and drag to change between operations (same behavior as blend selectors)
- % intensity handler: 2x faster drag speed for quicker adjustments
- Blend selectors: 2x faster drag speed for quicker blend type changes
- All elements highlight on hover to indicate interactivity
- Cursor is hidden during drag operations
- Central overlay displays available options during drag

Usage:
    Create a ScopeGUI instance with desired parameters and call update() in your modal operator.
    Pass operation_options as a list of (id, name, description) tuples to enable operation switching.
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from math import sin, cos, pi, sqrt
from .. import get_prefs
from ..general import ensure_alpha, get_dpi_scale
from ..curve import get_nla_strip_offset


# ============================================================================
# VERTICAL LEVEL SYSTEM CONSTANTS
# ============================================================================


class VerticalLevels:
    """Constants defining the vertical level system for all GUI elements."""

    # Base system
    TOP_MARGIN_UNITS = 2  # 2 empty units at top
    BOTTOM_MARGIN_UNITS = 2  # 2 empty units at bottom
    PADDING_PERCENT = 0.2  # 20% padding between levels

    # Top levels (from top down, after 2-unit margin)
    OPERATION_BOX = 1  # Level 1: Operation name box (draggable)
    FACTOR_BOX = 2  # Level 2: Factor box (beside operation box)
    PROPERTY_BOXES_START = 3  # Level 2+: Property boxes (one per level)
    PERCENT_BOX = 1  # Level after properties: % intensity box (center)

    # Bottom levels (from bottom up, after 2-unit margin)
    BLEND_SELECTORS = 1  # Level 1: Blend option boxes (beside secondary pins)
    SECONDARY_PINS = 1  # Level 1: Secondary handlers (from bottom)
    SECONDARY_BARS = 1  # Level 1: Secondary bars and outer bar (from bottom)
    OUTER_BAR = 1  # Level 1: Outer bar (from bottom)
    MAIN_PINS = 2  # Level 2: Main handlers (from bottom)
    MAIN_BAR = 2  # Level 2: Main pins bar (from bottom)


def get_unit_height():
    """Get the standard unit height for all elements."""
    return 16.0 * get_dpi_scale()


def get_unit_padding():
    """Get the standard padding between levels."""
    return get_unit_height() * VerticalLevels.PADDING_PERCENT


def get_level_y_position_from_top(level, context):
    """
    Get the Y position for a given vertical level positioned from the top.

    Args:
        level (float): Vertical level number
        context: Blender context for region height

    Returns:
        float: Y position in screen coordinates
    """
    unit_height = get_unit_height()
    unit_padding = get_unit_padding()
    top_margin = VerticalLevels.TOP_MARGIN_UNITS * unit_height

    # Calculate from top of editor
    region_height = context.region.height if context.region else 800

    # Each level includes its height plus padding
    level_with_padding = level * (unit_height + unit_padding)

    return region_height - top_margin - level_with_padding


def get_level_y_position_from_bottom(level, context):
    """
    Get the Y position for a given vertical level positioned from the bottom.

    Args:
        level (float): Vertical level number
        context: Blender context for region height

    Returns:
        float: Y position in screen coordinates
    """
    unit_height = get_unit_height()
    unit_padding = get_unit_padding()
    bottom_margin = VerticalLevels.BOTTOM_MARGIN_UNITS * unit_height

    # Each level includes its height plus padding
    level_with_padding = level * (unit_height + unit_padding)

    return bottom_margin + level_with_padding


def get_level_y_position(level, context):
    """
    Get the Y position for a given vertical level with padding.
    Legacy function - now delegates to top positioning.

    Args:
        level (float): Vertical level number (can be fractional for bars)
        context: Blender context for region height

    Returns:
        float: Y position in screen coordinates
    """
    return get_level_y_position_from_top(level, context)


def get_element_center_y(level, context, from_bottom=False):
    """
    Get the center Y position for drawing an element at a given level.
    All elements are drawn from their center.

    Args:
        level (float): Vertical level number
        context: Blender context for region height
        from_bottom (bool): Whether to position from bottom or top

    Returns:
        float: Center Y position for drawing
    """
    if from_bottom:
        return get_level_y_position_from_bottom(level, context)
    else:
        return get_level_y_position_from_top(level, context)


# ============================================================================
# BLENDING TYPE DEFINITIONS
# ============================================================================


class BlendType:
    """Enumeration for blending types with visual representations."""

    LINEAR = "linear"
    QUADRATIC_IN = "quadratic_in"
    QUADRATIC_OUT = "quadratic_out"
    QUADRATIC_IN_OUT = "quadratic_in_out"
    CUBIC_IN = "cubic_in"
    CUBIC_OUT = "cubic_out"
    CUBIC_IN_OUT = "cubic_in_out"
    EXPONENTIAL_IN = "exponential_in"
    EXPONENTIAL_OUT = "exponential_out"
    EXPONENTIAL_IN_OUT = "exponential_in_out"

    @classmethod
    def get_all(cls):
        """Get all blending types ordered by intensity from in to out with linear in the middle."""
        return [
            cls.EXPONENTIAL_IN,
            cls.CUBIC_IN,
            cls.QUADRATIC_IN,
            cls.LINEAR,
            cls.QUADRATIC_IN_OUT,
            cls.CUBIC_IN_OUT,
            cls.EXPONENTIAL_IN_OUT,
            cls.QUADRATIC_OUT,
            cls.CUBIC_OUT,
            cls.EXPONENTIAL_OUT,
        ]

    @classmethod
    def get_display_name(cls, blend_type):
        """Get display name for blending type."""
        names = {
            cls.LINEAR: "Linear",
            cls.QUADRATIC_IN: "Quadratic In",
            cls.QUADRATIC_OUT: "Quadratic Out",
            cls.QUADRATIC_IN_OUT: "Quadratic In/Out",
            cls.CUBIC_IN: "Cubic In",
            cls.CUBIC_OUT: "Cubic Out",
            cls.CUBIC_IN_OUT: "Cubic In/Out",
            cls.EXPONENTIAL_IN: "Exponential In",
            cls.EXPONENTIAL_OUT: "Exponential Out",
            cls.EXPONENTIAL_IN_OUT: "Exponential In/Out",
        }
        return names.get(blend_type, "Unknown")


class ScopePin:
    """
    Individual pin component for the scope GUI.

    Represents a single pin with frame position, influence, and visual state.
    """

    def __init__(self, frame, influence=1.0, is_main=True, pin_index=0):
        """
        Initialize a scope pin.

        Args:
            frame (float): Frame position of the pin
            influence (float): Influence value (0.0 to 1.0)
            is_main (bool): Whether this is a main pin (100% influence) or secondary
            pin_index (int): Index of this pin (0=secondary_left, 1=main_left, 2=main_right, 3=secondary_right)
        """
        self.frame = frame
        self.influence = influence
        self.is_main = is_main
        self.pin_index = pin_index
        self.is_hovered = False
        self.is_dragging = False
        self.drag_offset = 0.0
        self.screen_x = 0.0
        self.screen_y = 0.0
        self.height = 16.0  # Fixed height for rectangle
        self.base_width = 16.0  # Minimum width (square)

    def get_screen_position(self, context):
        """Convert frame position to screen coordinates."""
        if not context.region or not context.region.view2d:
            return 0.0, 0.0

        region = context.region
        view2d = region.view2d

        # Convert frame (action-relative) to screen coordinates (scene frame) including NLA offset
        obj = getattr(context, "active_object", None)
        offset = get_nla_strip_offset(obj) if obj else 0.0
        screen_x, screen_y = view2d.view_to_region(self.frame + offset, 0.0, clip=False)

        # Vertical position based on pin type using level system from bottom
        if self.is_main:
            screen_y = get_element_center_y(VerticalLevels.MAIN_PINS, context, from_bottom=True)
        else:
            screen_y = get_element_center_y(VerticalLevels.SECONDARY_PINS, context, from_bottom=True)

        self.screen_x = screen_x
        self.screen_y = screen_y

        return screen_x, screen_y

    def check_hover(self, mouse_x, mouse_y, context):
        """Check if mouse is hovering over this pin's rectangle."""
        screen_x, screen_y = self.get_screen_position(context)
        scale = get_dpi_scale()

        # Calculate rectangle dimensions and position
        rect_x, rect_y, width, height = self._get_rectangle_bounds(context, scale)

        # Check if mouse is within rectangle bounds
        self.is_hovered = (
            abs(mouse_x - (rect_x + width * 0.5)) <= width * 0.5
            and abs(mouse_y - (rect_y + height * 0.5)) <= height * 0.5
        )
        return self.is_hovered

    def start_drag(self, mouse_x, mouse_y, context):
        """Start dragging this pin."""
        if not self.is_hovered:
            return False

        self.is_dragging = True
        screen_x, _ = self.get_screen_position(context)
        self.drag_offset = mouse_x - screen_x
        return True

    def update_drag(self, mouse_x, mouse_y, context):
        """Update pin position during drag."""
        if not self.is_dragging:
            return

        region = context.region
        view2d = region.view2d

        # Convert screen position back to frame
        adjusted_x = mouse_x - self.drag_offset
        scene_frame, _ = view2d.region_to_view(adjusted_x, 0)
        # Subtract NLA offset to get action-relative frame
        obj = getattr(context, "active_object", None)
        offset = get_nla_strip_offset(obj) if obj else 0.0
        action_frame = scene_frame - offset
        # Round to full frames only
        self.frame = round(action_frame)

    def end_drag(self):
        """End dragging this pin."""
        self.is_dragging = False
        self.drag_offset = 0.0

    def draw(self, context, main_color, accent_color):
        """Draw the pin with vertical line and rectangle handle."""
        screen_x, screen_y = self.get_screen_position(context)
        scale = get_dpi_scale()

        # Choose color based on state
        if self.is_hovered or self.is_dragging:
            color = accent_color
        else:
            color = main_color

        # Secondary pins have constant color (no influence-based alpha)
        # Influence visualization is handled by gradient fills

        # Draw vertical line
        self._draw_vertical_line(context, screen_x, color)

        # Draw rectangle handle
        self._draw_rectangle(context, scale, color)

        # Draw frame number
        self._draw_frame_number(context, scale)

    def _draw_vertical_line(self, context, x, color):
        """Draw a vertical line spanning the editor height."""
        region = context.region

        # Use text color when not hovered, accent color when hovered
        if self.is_hovered or self.is_dragging:
            line_color = (*color[:3], color[3] * 0.5)  # 50% alpha for subtle line
        else:
            # Use text color from preferences when not hovered
            prefs = get_prefs()
            text_color = prefs.guipins_accent_color
            line_color = (*text_color[:3], text_color[3] * 0.2)  # 30% alpha for subtle line

        vertices = [
            (x, 0),
            (x, region.height),
        ]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "LINES", {"pos": vertices})

        # Enable blending for transparency
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(line_color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _get_rectangle_bounds(self, context, scale):
        """Calculate rectangle position and dimensions based on frame digits and pin position."""
        screen_x, screen_y = self.get_screen_position(context)
        region = context.region

        # Calculate width based on frame number digits
        frame_text = str(int(self.frame))
        font_id = 0
        blf.size(font_id, int(10 * scale))
        text_width, text_height = blf.dimensions(font_id, frame_text)

        # Rectangle dimensions
        width = max(self.base_width * scale, text_width + 8 * scale)  # Padding for text
        height = self.height * scale

        # Determine positioning based on pin index
        if self.pin_index in [0, 1]:  # Left pins (secondary_left, main_left)
            # Draw to the left of the vertical line
            rect_x = screen_x - width
        else:  # Right pins (main_right, secondary_right)
            # Draw to the right of the vertical line
            rect_x = screen_x

        # Use the Y position from get_screen_position (already calculated correctly)
        rect_y = screen_y - height * 0.5  # Center the rectangle on the pin position

        return rect_x, rect_y, width, height

    def _draw_rectangle(self, context, scale, color):
        """Draw a rectangle handle at the calculated position."""
        rect_x, rect_y, width, height = self._get_rectangle_bounds(context, scale)

        vertices = [
            (rect_x, rect_y),
            (rect_x + width, rect_y),
            (rect_x + width, rect_y + height),
            (rect_x, rect_y + height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Enable blending for transparency
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_frame_number(self, context, scale):
        """Draw the frame number on the rectangle handle."""
        rect_x, rect_y, width, height = self._get_rectangle_bounds(context, scale)

        font_id = 0
        blf.size(font_id, int(10 * scale))

        # Get text color from preferences
        prefs = get_prefs()
        text_color = ensure_alpha(prefs.text_color)
        blf.color(font_id, *text_color)

        # Draw frame number centered in rectangle
        frame_text = str(int(self.frame))
        text_width, text_height = blf.dimensions(font_id, frame_text)

        text_x = rect_x + (width - text_width) * 0.5
        text_y = rect_y + (height - text_height) * 0.5

        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, frame_text)


class EnhancedDragHandler:
    """
    Enhanced drag handler that uses the new ValueBox system.

    This is a simplified wrapper that delegates to the new unified system.
    """

    def __init__(self, element_type, current_value, value_range, is_enum=False):
        """
        Initialize enhanced drag handler.

        Args:
            element_type (str): Type of element ("intensity", "blend_left", "blend_right")
            current_value: Current value (float for numeric, int index for enum)
            value_range: (min, max) for numeric or list of options for enum
            is_enum (bool): Whether this is an enum selector
        """
        self.element_type = element_type
        self.is_enum = is_enum

        # Create ValueBox with appropriate type
        value_type = "element" if is_enum else "value"
        display_formatter = None

        if element_type == "intensity":
            display_formatter = lambda x: f"{int(round(x))}%"
        elif is_enum:
            display_formatter = lambda x: (
                BlendType.get_display_name(value_range[int(x)]) if 0 <= int(x) < len(value_range) else "Unknown"
            )

        self.value_box = ValueBox(value_type, current_value, value_range, display_formatter)

        # Set appropriate order for element-based vs value-based
        if value_type == "element":
            # Element-based lists should use descending order (traditional behavior)
            self.value_box.ascending_order = False

        # Delegate properties
        self.is_hovered = False
        self.is_dragging = False

    def check_hover(self, mouse_x, mouse_y, element_bounds):
        """Check if mouse is hovering over the element."""
        x, y, width, height = element_bounds
        self.value_box.set_position(x, y)

        scale = get_dpi_scale()
        self.is_hovered = self.value_box.check_hover(mouse_x, mouse_y, scale)
        return self.is_hovered

    def start_drag(self, context, mouse_x, mouse_y):
        """Start drag operation."""
        if not self.is_hovered:
            return False

        self.is_dragging = True
        return self.value_box.start_drag(context, mouse_x, mouse_y)

    def update_drag(self, context, mouse_x, mouse_y):
        """Update drag operation."""
        if not self.is_dragging:
            return

        self.value_box.update_drag(context, mouse_x, mouse_y)

    def end_drag(self, context):
        """End drag operation."""
        if not self.is_dragging:
            return

        self.is_dragging = False
        self.value_box.end_drag(context)

    def get_current_value(self):
        """Get the current value."""
        return self.value_box.current_value

    def get_display_value(self):
        """Get the display value for the current selection."""
        return self.value_box.get_display_text()

    def should_hide_cursor(self):
        """Check if cursor should be hidden."""
        return self.is_dragging

    def draw_overlay(self, context, main_color, accent_color):
        """Draw the overlay (now handled by ValueBox)."""
        if self.is_dragging:
            self.value_box.draw(context, main_color, accent_color)


class IntensityHandler:
    """
    Intensity handler for controlling influence percentage.

    Appears as a draggable box between the main pins with percentage display.
    Uses the new enhanced drag system with ValueBox.

    The intensity handler stores a intensity value (0 to 100) as a simple percentage.
    """

    def __init__(self, intensity=100.0):
        """
        Initialize intensity handler.

        Args:
            intensity (float): Initial intensity percentage (0 to 100)
        """
        self.intensity = intensity  # Base intensity value (0 to 100)
        self.screen_x = 0.0
        self.screen_y = 0.0
        self.limit_bar_visible = False

        # Create ValueBox for intensity with fixed range
        self._setup_value_box()

    def _setup_value_box(self):
        """Setup the value box with fixed range."""
        # Fixed range from 0 to 100
        value_range = (0.0, 100.0)
        # Display formatter shows simple percentage
        display_formatter = lambda x: f"{int(round(x))}%"
        self.value_box = ValueBox("value", self.intensity, value_range, display_formatter)
        # Set reduced width for intensity handler
        self.value_box.box_width = 40.0  # Half the normal width
        # Set ascending order (0% at top, 100% at bottom)
        self.value_box.ascending_order = True

    def get_screen_position(self, context, main_pins, operation_selector=None):
        """Calculate screen position to the left of the operation selector with proper padding."""
        if len(main_pins) < 2:
            return 0.0, 0.0

        # Position horizontally between main pins
        pin1_x, _ = main_pins[0].get_screen_position(context)
        pin2_x, _ = main_pins[1].get_screen_position(context)
        center_x = (pin1_x + pin2_x) * 0.5

        # Calculate operation box width if available
        operation_box_width = 0.0
        if operation_selector and operation_selector.value_box:
            scale = get_dpi_scale()
            operation_box_width, _ = operation_selector.value_box.get_box_dimensions(scale)

        # Base spacing from center plus half the operation box width plus padding
        scale = get_dpi_scale()
        base_spacing = operation_box_width * 0.5 + 20 * scale  # 20px padding
        self.screen_x = center_x - base_spacing

        # Vertical position: same level as % box (from top)
        self.screen_y = get_element_center_y(VerticalLevels.PERCENT_BOX, context, from_bottom=False)

        # Set ValueBox position
        self.value_box.set_position(self.screen_x, self.screen_y)

        return self.screen_x, self.screen_y

    def check_hover(self, mouse_x, mouse_y, context, main_pins, operation_selector=None):
        """Check if mouse is hovering over the intensity handler."""
        screen_x, screen_y = self.get_screen_position(context, main_pins, operation_selector)
        scale = get_dpi_scale()

        # Use ValueBox for hover detection
        is_hovered = self.value_box.check_hover(mouse_x, mouse_y, scale)

        # Don't show limit bar when hovering (removed for cleaner look)
        self.limit_bar_visible = False

        return is_hovered

    def start_drag(self, mouse_x, mouse_y, context, main_pins, operation_selector=None):
        """Start dragging the intensity handler."""
        return self.value_box.start_drag(context, mouse_x, mouse_y)

    def update_drag(self, mouse_x, mouse_y, context, main_pins, operation_selector=None, shift_held=False):
        """Update intensity during drag."""
        self.value_box.update_drag(context, mouse_x, mouse_y, shift_held)
        self.intensity = self.value_box.current_value

    def end_drag(self, context):
        """End dragging the intensity handler."""
        self.value_box.end_drag(context)
        self.limit_bar_visible = False

    def draw(self, context, main_pins, main_color, accent_color, operation_selector=None):
        """Draw the intensity handler."""
        screen_x, screen_y = self.get_screen_position(context, main_pins, operation_selector)
        scale = get_dpi_scale()

        # Draw the ValueBox (handles its own overlay) - removed limit bar for cleaner look
        self.value_box.draw(context, main_color, accent_color)

    def _draw_limit_bar(self, context, main_pins, main_color):
        """Draw the vertical limit bar showing movement range."""
        if len(main_pins) < 2:
            return

        region = context.region
        scale = get_dpi_scale()

        # Calculate bar position and size
        pin1_x, _ = main_pins[0].get_screen_position(context)
        pin2_x, _ = main_pins[1].get_screen_position(context)

        bar_x = (pin1_x + pin2_x) * 0.5
        bar_width = 4.0 * scale

        # Bar height is 2/3 of editor height
        editor_height = region.height
        bar_height = editor_height * (2.0 / 3.0)
        bar_y = editor_height * (1.0 / 6.0)

        # Draw bar with proper alpha transparency
        bar_color = ensure_alpha((*main_color[:3], main_color[3] * 0.3))

        vertices = [
            (bar_x - bar_width * 0.5, bar_y),
            (bar_x + bar_width * 0.5, bar_y),
            (bar_x + bar_width * 0.5, bar_y + bar_height),
            (bar_x - bar_width * 0.5, bar_y + bar_height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Enable blending for transparency
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", bar_color)
        batch.draw(shader)
        gpu.state.blend_set("NONE")


class BlendSelector:
    """
    Blend option selector with visual feedback.

    Allows users to select from different blend types with drag interaction.
    Uses the new ValueBox system.
    """

    def __init__(self, side="left", blend_type=BlendType.LINEAR):
        """
        Initialize blend selector.

        Args:
            side (str): "left" or "right" side of the interface
            blend_type (str): Initial blend type
        """
        self.side = side
        self.blend_type = blend_type
        self.screen_x = 0.0
        self.screen_y = 0.0

        # All blend options
        self.blend_options = BlendType.get_all()
        self.selection_index = self.blend_options.index(blend_type)

        # Create ValueBox for blend selection
        display_formatter = lambda x: (
            BlendType.get_display_name(self.blend_options[int(x)])
            if 0 <= int(x) < len(self.blend_options)
            else "Unknown"
        )
        self.value_box = ValueBox("element", self.selection_index, self.blend_options, display_formatter)
        # Element-based lists should use descending order (traditional behavior)
        self.value_box.ascending_order = False

    def get_screen_position(self, context, main_pins, secondary_pins):
        """Calculate screen position beside the secondary pins at the bottom, aligned OUTSIDE handler boxes."""
        if len(secondary_pins) < 2:
            return 0.0, 0.0

        scale = get_dpi_scale()

        # Get the secondary pin positions and their handler box dimensions
        if self.side == "left":
            # Position to the left of the left secondary pin handler box (completely outside)
            pin_x, pin_y = secondary_pins[0].get_screen_position(context)
            # Calculate handler box bounds (same logic as in ScopePin._get_rectangle_bounds)
            frame_text = str(int(secondary_pins[0].frame))
            font_id = 0
            blf.size(font_id, int(10 * scale))
            text_width, text_height = blf.dimensions(font_id, frame_text)
            handler_width = max(secondary_pins[0].base_width * scale, text_width + 8 * scale)

            # For left pin (index 0), handler box is to the left of the vertical line
            handler_left_edge = pin_x - handler_width

            # Position our blend selector to the left of the handler box with padding
            blend_selector_width, _ = self.value_box.get_box_dimensions(scale)
            self.screen_x = handler_left_edge - get_unit_padding() - blend_selector_width * 0.5
        else:
            # Position to the right of the right secondary pin handler box (completely outside)
            pin_x, pin_y = secondary_pins[1].get_screen_position(context)
            # Calculate handler box bounds
            frame_text = str(int(secondary_pins[1].frame))
            font_id = 0
            blf.size(font_id, int(10 * scale))
            text_width, text_height = blf.dimensions(font_id, frame_text)
            handler_width = max(secondary_pins[1].base_width * scale, text_width + 8 * scale)

            # For right pin (index 3), handler box is to the right of the vertical line
            handler_right_edge = pin_x + handler_width

            # Position our blend selector to the right of the handler box with padding
            blend_selector_width, _ = self.value_box.get_box_dimensions(scale)
            self.screen_x = handler_right_edge + get_unit_padding() + blend_selector_width * 0.5

        # Vertical position: same level as blend selectors (from bottom), aligned with handler boxes
        self.screen_y = get_element_center_y(VerticalLevels.BLEND_SELECTORS, context, from_bottom=True)

        # Set ValueBox position
        self.value_box.set_position(self.screen_x, self.screen_y)

        return self.screen_x, self.screen_y

    def check_hover(self, mouse_x, mouse_y, context, main_pins, secondary_pins):
        """Check if mouse is hovering over the blend selector."""
        screen_x, screen_y = self.get_screen_position(context, main_pins, secondary_pins)
        scale = get_dpi_scale()

        # Use ValueBox for hover detection
        return self.value_box.check_hover(mouse_x, mouse_y, scale)

    def start_drag(self, mouse_x, mouse_y, context, main_pins, secondary_pins):
        """Start dragging the blend selector."""
        return self.value_box.start_drag(context, mouse_x, mouse_y)

    def update_drag(self, mouse_x, mouse_y, context, main_pins, secondary_pins):
        """Update blend selection during drag."""
        self.value_box.update_drag(context, mouse_x, mouse_y)

        # Update selection index and blend type
        self.selection_index = self.value_box.current_value
        self.blend_type = self.blend_options[int(self.selection_index)]

    def end_drag(self, context):
        """End dragging the blend selector."""
        self.value_box.end_drag(context)

    def draw(self, context, main_pins, secondary_pins, main_color, accent_color):
        """Draw the blend selector."""
        screen_x, screen_y = self.get_screen_position(context, main_pins, secondary_pins)

        # Draw the ValueBox (handles its own overlay)
        self.value_box.draw(context, main_color, accent_color)


class CursorManager:
    """
    Manages cursor visibility during drag operations.

    Hides the cursor when dragging starts and restores it when dragging ends.
    """

    def __init__(self):
        self.cursor_hidden = False
        self.stored_cursor_position = None

    def hide_cursor(self, context, mouse_x, mouse_y):
        """Hide the cursor and store its position."""
        if not self.cursor_hidden and context and context.window:
            self.stored_cursor_position = (mouse_x, mouse_y)
            try:
                # Hide cursor by setting it to NONE
                context.window.cursor_modal_set("NONE")
                self.cursor_hidden = True
            except:
                # Fallback - cursor hiding might not be supported
                self.cursor_hidden = False

    def restore_cursor(self, context):
        """Restore the cursor to its normal state."""
        if self.cursor_hidden and context and context.window:
            try:
                # Restore default cursor
                context.window.cursor_modal_restore()
                self.cursor_hidden = False
                self.stored_cursor_position = None
            except:
                # Ensure we reset the state even if restoration fails
                self.cursor_hidden = False
                self.stored_cursor_position = None


class StandaloneFactor:
    """
    Standalone factor handler for "on the fly" mode operations.

    This is a simplified version of the Factor class that can be used
    independently without requiring main pins or other GUI components.
    It displays only the factor slider and handles mouse interactions
    in the same way as the full Factor handler.
    """

    def __init__(self, factor=0.0, multiplier=1.0):
        """
        Initialize standalone factor handler.

        Args:
            factor (float): Initial factor value (range depends on guipins_overshoot preference)
            multiplier (float): Multiplier for the factor value
        """
        self.factor = factor
        self.multiplier = multiplier
        self.screen_x = 0.0
        self.screen_y = 0.0
        self.background_width = 200.0  # Fixed width for standalone mode
        self.background_height = 0.0

        # Handler properties
        self.handler_width = 0.0
        self.handler_height = 0.0
        self.handler_x = 0.0
        self.handler_y = 0.0

        # Interaction state
        self.is_hovered = False
        self.is_dragging = False
        self.drag_offset = 0.0
        self.drag_start_x = 0.0

        # Draw handler for modal operation
        self._draw_handler = None

        # Cursor management
        self.cursor_manager = CursorManager()

    def get_effective_factor(self):
        """Get the effective factor value (factor * multiplier)."""
        return self.factor * self.multiplier

    def _get_max_factor(self):
        """Get the maximum factor range based on overshoot preference."""
        prefs = get_prefs()
        return 2.0 if prefs.guipins_overshoot else 1.0

    def get_screen_position(self, context, screen_x=None, screen_y=None):
        """Calculate screen position and dimensions for the standalone factor handler."""
        # Use provided position or calculate positioned above mouse
        if screen_x is not None:
            self.screen_x = screen_x
        else:
            # Center horizontally in the viewport
            region = context.region
            self.screen_x = region.width * 0.5 if region else 400

        if screen_y is not None:
            self.screen_y = screen_y
        else:
            # Position in the upper portion of the viewport
            region = context.region
            self.screen_y = region.height * 0.8 if region else 600

        # Set background dimensions
        scale = get_dpi_scale()
        self.background_width = 200.0 * scale  # Fixed width
        self.background_height = get_unit_height()

        # Handler dimensions (2x height as width)
        self.handler_height = self.background_height
        self.handler_width = self.handler_height * 2.0

        # Calculate handler position based on factor value
        max_travel = (self.background_width - self.handler_width) * 0.5
        max_factor = self._get_max_factor()
        if max_factor > 0:
            self.handler_x = self.screen_x + (self.factor / max_factor * max_travel)
        else:
            self.handler_x = self.screen_x
        self.handler_y = self.screen_y

        return self.screen_x, self.screen_y

    def check_hover(self, mouse_x, mouse_y, context):
        """Check if mouse is hovering over the factor handler."""
        # Check if mouse is within the handler bounds
        self.is_hovered = (
            abs(mouse_x - self.handler_x) <= self.handler_width * 0.5
            and abs(mouse_y - self.handler_y) <= self.handler_height * 0.5
        )

        return self.is_hovered

    def start_drag(self, mouse_x, mouse_y, context):
        """Start dragging the factor handler."""
        # Always allow dragging in standalone mode (like quick_drag)
        self.is_dragging = True
        self.drag_start_x = mouse_x
        self.drag_offset = 0.0  # No offset - track mouse directly

        # Hide cursor during drag
        self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)

        # Start from center position (factor = 0.0) since mouse should be warped there
        # This ensures smooth dragging from the center
        self.factor = 0.0
        self.handler_x = self.screen_x  # Center the handler

        return True

    def update_drag(self, mouse_x, mouse_y, context, shift_held=False):
        """Update factor during drag."""
        if not self.is_dragging:
            return

        # Calculate new handler position
        new_handler_x = mouse_x - self.drag_offset

        # Constrain to background rectangle bounds
        max_travel = (self.background_width - self.handler_width) * 0.5
        min_x = self.screen_x - max_travel
        max_x = self.screen_x + max_travel

        new_handler_x = max(min_x, min(max_x, new_handler_x))

        # Convert position to factor value (range depends on overshoot preference)
        relative_pos = new_handler_x - self.screen_x
        max_factor = self._get_max_factor()
        # Scale the factor calculation to match the overshoot range
        self.factor = (relative_pos / max_travel * max_factor) if max_travel > 0 else 0.0

        # Apply shift snapping to 0.1 increments
        if shift_held:
            self.factor = round(self.factor * 10.0) / 10.0

        # Ensure factor stays within bounds
        self.factor = max(-max_factor, min(max_factor, self.factor))

        # Update handler position based on constrained factor
        if max_factor > 0:
            self.handler_x = self.screen_x + (self.factor / max_factor * max_travel)
        else:
            self.handler_x = self.screen_x

    def end_drag(self, context):
        """End dragging the factor handler."""
        self.is_dragging = False
        self.drag_offset = 0.0

    def activate(self, context):
        """Activate the standalone factor handler with draw callback."""
        # Register draw handler
        if context.space_data and hasattr(context.space_data, "draw_handler_add"):
            self._draw_handler = context.space_data.draw_handler_add(
                self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
            )

    def deactivate(self, context):
        """Deactivate the standalone factor handler and remove draw callback."""
        # End any active dragging and restore cursor
        if self.is_dragging:
            self.end_drag(context)

        # Always try to restore cursor when deactivating
        self.cursor_manager.restore_cursor(context)

        if self._draw_handler and context.space_data and hasattr(context.space_data, "draw_handler_remove"):
            try:
                context.space_data.draw_handler_remove(self._draw_handler, "WINDOW")
            except:
                pass  # Handle case where draw handler is already removed
            self._draw_handler = None

    def _draw_callback(self, context):
        """Draw callback function for the standalone factor handler."""
        self.draw(context)

    def draw(self, context):
        """Draw the standalone factor handler with background rectangle and draggable box."""
        # Update screen position
        self.get_screen_position(context)

        # Get colors from preferences
        prefs = get_prefs()
        main_color = prefs.guipins_main_color
        accent_color = prefs.guipins_accent_color

        # Draw background rectangle
        self._draw_background(context, main_color)

        # Draw handler box
        self._draw_handler_box(context, main_color, accent_color)

        # Draw factor value text
        self._draw_factor_text(context)

    def _draw_background(self, context, main_color):
        """Draw the background rectangle."""
        # Background rectangle vertices
        half_width = self.background_width * 0.5
        half_height = self.background_height * 0.5

        vertices = [
            (self.screen_x - half_width, self.screen_y - half_height),
            (self.screen_x + half_width, self.screen_y - half_height),
            (self.screen_x + half_width, self.screen_y + half_height),
            (self.screen_x - half_width, self.screen_y + half_height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Use main color with slight transparency
        bg_color = ensure_alpha((*main_color[:3], main_color[3] * 0.5))

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", bg_color)
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_handler_box(self, context, main_color, accent_color):
        """Draw the draggable handler box."""
        # Handler rectangle vertices
        half_width = self.handler_width * 0.5
        half_height = self.handler_height * 0.5

        vertices = [
            (self.handler_x - half_width, self.handler_y - half_height),
            (self.handler_x + half_width, self.handler_y - half_height),
            (self.handler_x + half_width, self.handler_y + half_height),
            (self.handler_x - half_width, self.handler_y + half_height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Choose color based on state
        if self.is_hovered or self.is_dragging:
            color = accent_color
        else:
            color = main_color

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_factor_text(self, context):
        """Draw the factor value text on the handler."""
        scale = get_dpi_scale()
        font_id = 0
        blf.size(font_id, int(8 * scale))

        # Get text color from preferences
        prefs = get_prefs()
        text_color = ensure_alpha(prefs.text_color)
        blf.color(font_id, *text_color)

        # Format factor value with 2 decimal places
        factor_text = f"{self.factor:.2f}"
        text_width, text_height = blf.dimensions(font_id, factor_text)

        # Center text on handler
        text_x = self.handler_x - text_width * 0.5
        text_y = self.handler_y - text_height * 0.5

        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, factor_text)


class Factor:
    """
    Factor handler for controlling a draggable factor value.

    Appears as a background rectangle with a draggable box that moves horizontally
    from -max_factor to +max_factor with 0.00 precision. The handler starts in the middle at 0.00.
    When shift is held, it snaps to 0.1 increments. Range depends on guipins_overshoot preference.
    """

    def __init__(self, factor=0.0, multiplier=1.0, quick_drag=False):
        """
        Initialize factor handler.

        Args:
            factor (float): Initial factor value (range depends on guipins_overshoot preference)
            multiplier (float): Multiplier for the factor value
            quick_drag (bool): Whether to start in quick drag mode
        """
        self.factor = factor
        self.multiplier = multiplier
        self.screen_x = 0.0
        self.screen_y = 0.0
        self.background_width = 0.0
        self.background_height = 0.0

        # Handler properties
        self.handler_width = 0.0
        self.handler_height = 0.0
        self.handler_x = 0.0
        self.handler_y = 0.0

        # Interaction state
        self.is_hovered = False
        self.is_dragging = False
        self.drag_offset = 0.0
        self.drag_start_x = 0.0

        # Quick drag state
        self.in_quick_drag = quick_drag

    def get_effective_factor(self):
        """Get the effective factor value (factor * multiplier)."""
        return self.factor * self.multiplier

    def _get_max_factor(self):
        """Get the maximum factor range based on overshoot preference."""
        prefs = get_prefs()
        return 2.0 if prefs.guipins_overshoot else 1.0

    def get_screen_position(self, context, main_pins, operation_selector=None, intensity_handler=None):
        """Calculate screen position and dimensions for the factor handler."""
        if len(main_pins) < 2:
            return 0.0, 0.0

        # Get the center position between main pins
        pin1_x, _ = main_pins[0].get_screen_position(context)
        pin2_x, _ = main_pins[1].get_screen_position(context)
        center_x = (pin1_x + pin2_x) * 0.5

        # Calculate the total width needed (operation + percent boxes)
        scale = get_dpi_scale()
        total_width = 0.0

        # Add operation box width
        if operation_selector and operation_selector.value_box:
            op_width, _ = operation_selector.value_box.get_box_dimensions(scale)
            total_width += op_width

        # Add intensity handler width
        if intensity_handler and intensity_handler.value_box:
            intensity_width, _ = intensity_handler.value_box.get_box_dimensions(scale)
            total_width += intensity_width

        # Add padding between elements (20px for spacing)
        total_width += 20 * scale

        # Set background dimensions
        self.background_width = total_width
        self.background_height = get_unit_height()

        # Handler dimensions (2x height as width)
        self.handler_height = self.background_height
        self.handler_width = self.handler_height * 2.0

        # Position at center horizontally
        self.screen_x = center_x

        # Vertical position: level 2 from top (FACTOR_BOX level)
        self.screen_y = get_element_center_y(VerticalLevels.FACTOR_BOX, context, from_bottom=False)

        # Calculate handler position based on factor value
        # Factor ranges based on overshoot preference
        # Map to position within background rectangle
        max_travel = (self.background_width - self.handler_width) * 0.5
        max_factor = self._get_max_factor()
        self.handler_x = self.screen_x + (self.factor / max_factor * max_travel)
        self.handler_y = self.screen_y

        return self.screen_x, self.screen_y

    def check_hover(
        self,
        mouse_x,
        mouse_y,
        context,
        main_pins,
        operation_selector=None,
        intensity_handler=None,
    ):
        """Check if mouse is hovering over the factor handler."""
        screen_x, screen_y = self.get_screen_position(context, main_pins, operation_selector, intensity_handler)

        # Check if mouse is within the handler bounds
        self.is_hovered = (
            abs(mouse_x - self.handler_x) <= self.handler_width * 0.5
            and abs(mouse_y - self.handler_y) <= self.handler_height * 0.5
        )

        return self.is_hovered

    def start_drag(
        self,
        mouse_x,
        mouse_y,
        context,
        main_pins,
        operation_selector=None,
        intensity_handler=None,
    ):
        """Start dragging the factor handler."""
        if not self.is_hovered and not self.in_quick_drag:
            return False

        # In quick_drag mode, we need to update the screen position first
        if self.in_quick_drag:
            self.get_screen_position(context, main_pins, operation_selector, intensity_handler)

        self.is_dragging = True
        self.drag_start_x = mouse_x

        # For quick_drag, center the handler on the mouse position
        if self.in_quick_drag:
            self.drag_offset = 0.0  # No offset - track mouse directly
            # Update the factor based on the current mouse position
            max_travel = (self.background_width - self.handler_width) * 0.5
            relative_pos = mouse_x - self.screen_x
            max_factor = self._get_max_factor()
            # Scale the factor calculation to match the overshoot range
            self.factor = (relative_pos / max_travel * max_factor) if max_travel > 0 else 0.0
            self.factor = max(-max_factor, min(max_factor, self.factor))  # Clamp to bounds
            self.handler_x = self.screen_x + (self.factor / max_factor * max_travel)
        else:
            self.drag_offset = mouse_x - self.handler_x

        return True

    def update_drag(
        self,
        mouse_x,
        mouse_y,
        context,
        main_pins,
        operation_selector=None,
        intensity_handler=None,
        shift_held=False,
    ):
        """Update factor during drag."""
        if not self.is_dragging:
            return

        # Calculate new handler position
        new_handler_x = mouse_x - self.drag_offset

        # Constrain to background rectangle bounds
        max_travel = (self.background_width - self.handler_width) * 0.5
        min_x = self.screen_x - max_travel
        max_x = self.screen_x + max_travel

        new_handler_x = max(min_x, min(max_x, new_handler_x))

        # Convert position to factor value (range depends on overshoot preference)
        relative_pos = new_handler_x - self.screen_x
        max_factor = self._get_max_factor()
        # Scale the factor calculation to match the overshoot range
        self.factor = (relative_pos / max_travel * max_factor) if max_travel > 0 else 0.0

        # Apply shift snapping to 0.1 increments
        if shift_held:
            self.factor = round(self.factor * 10.0) / 10.0

        # Ensure factor stays within bounds
        self.factor = max(-max_factor, min(max_factor, self.factor))

        # Update handler position based on constrained factor
        self.handler_x = self.screen_x + (self.factor / max_factor * max_travel)

    def end_drag(self, context):
        """End dragging the factor handler."""
        self.is_dragging = False
        self.drag_offset = 0.0
        self.in_quick_drag = False  # Exit quick drag mode

    def draw(
        self,
        context,
        main_pins,
        main_color,
        accent_color,
        operation_selector=None,
        intensity_handler=None,
    ):
        """Draw the factor handler with background rectangle and draggable box."""
        screen_x, screen_y = self.get_screen_position(context, main_pins, operation_selector, intensity_handler)

        # Draw background rectangle
        self._draw_background(context, main_color)

        # Draw handler box
        self._draw_handler_box(context, main_color, accent_color)

        # Draw factor value text
        self._draw_factor_text(context)

    def _draw_background(self, context, main_color):
        """Draw the background rectangle."""
        # Background rectangle vertices
        half_width = self.background_width * 0.5
        half_height = self.background_height * 0.5

        vertices = [
            (self.screen_x - half_width, self.screen_y - half_height),
            (self.screen_x + half_width, self.screen_y - half_height),
            (self.screen_x + half_width, self.screen_y + half_height),
            (self.screen_x - half_width, self.screen_y + half_height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Use main color with slight transparency
        bg_color = ensure_alpha((*main_color[:3], main_color[3] * 0.5))

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", bg_color)
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_handler_box(self, context, main_color, accent_color):
        """Draw the draggable handler box."""
        # Handler rectangle vertices
        half_width = self.handler_width * 0.5
        half_height = self.handler_height * 0.5

        vertices = [
            (self.handler_x - half_width, self.handler_y - half_height),
            (self.handler_x + half_width, self.handler_y - half_height),
            (self.handler_x + half_width, self.handler_y + half_height),
            (self.handler_x - half_width, self.handler_y + half_height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Choose color based on state
        if self.is_hovered or self.is_dragging:
            color = accent_color
        else:
            color = main_color

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_factor_text(self, context):
        """Draw the factor value text on the handler."""
        scale = get_dpi_scale()
        font_id = 0
        blf.size(font_id, int(8 * scale))

        # Get text color from preferences
        prefs = get_prefs()
        text_color = ensure_alpha(prefs.text_color)
        blf.color(font_id, *text_color)

        # Format factor value with 2 decimal places
        factor_text = f"{self.factor:.2f}"
        text_width, text_height = blf.dimensions(font_id, factor_text)

        # Center text on handler
        text_x = self.handler_x - text_width * 0.5
        text_y = self.handler_y - text_height * 0.5

        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, factor_text)


# ============================================================================
# NEW REFACTORED SYSTEM - VALUEBOX AND SCROLLLIST
# ============================================================================


class ValueBox:
    """
    A clickable box that displays a value and spawns a scrollable list when dragged.

    This is the parent element that users interact with. It can contain either:
    - Value-based data (floats, percentages) - smooth incremental changes
    - Element-based data (enums, discrete options) - jumpy selection changes

    Terminology:
    - ValueBox: The main clickable element that shows current value
    - ScrollList: The list that appears behind the ValueBox during dragging
    """

    def __init__(self, value_type, initial_value, value_range, display_formatter=None):
        """
        Initialize a value box.

        Args:
            value_type (str): "value" for continuous values, "element" for discrete options
            initial_value: Current value (float for value type, int index for element type)
            value_range: (min, max) tuple for values, or list of options for elements
            display_formatter: Optional function to format display text
        """
        self.value_type = value_type  # "value" or "element"
        self.current_value = initial_value
        self.value_range = value_range
        self.display_formatter = display_formatter

        # Visual properties
        self.box_width = 80.0
        self.box_height = 16.0
        self.screen_x = 0.0
        self.screen_y = 0.0

        # Scroll properties
        self.ascending_order = True  # When True, low values at top, high at bottom

        # Interaction state
        self.is_hovered = False
        self.is_dragging = False

        # Drag system
        self.drag_handler = None
        self.scroll_list = None

        # Initialize components
        self._setup_components()

    def _setup_components(self):
        """Set up drag handler and scroll list for this value box."""
        # Create unified drag handler (no more inverted scroll)
        self.drag_handler = UnifiedDragHandler(self.value_type, self.current_value, self.value_range, parent_box=self)

        # Create scroll list with ascending order support
        self.scroll_list = ScrollList(self.value_type, self.value_range, self.display_formatter, self.ascending_order)

    def set_position(self, x, y):
        """Set the screen position of this value box."""
        self.screen_x = x
        self.screen_y = y

    def get_box_dimensions(self, scale):
        """Get the dimensions of the value box."""
        # Calculate width based on current display text
        display_text = self.get_display_text()

        font_id = 0
        blf.size(font_id, int(9 * scale))
        text_width, text_height = blf.dimensions(font_id, display_text)

        # Box dimensions with padding
        width = max(self.box_width * scale, text_width + 16 * scale)
        height = self.box_height * scale

        return width, height

    def get_display_text(self):
        """Get the text to display in the box."""
        if self.display_formatter:
            return self.display_formatter(self.current_value)

        if self.value_type == "value":
            return f"{int(round(self.current_value))}%"
        else:  # element type
            if isinstance(self.value_range, list) and 0 <= self.current_value < len(self.value_range):
                return BlendType.get_display_name(self.value_range[int(self.current_value)])
            return "Unknown"

    def check_hover(self, mouse_x, mouse_y, scale):
        """Check if mouse is hovering over this value box."""
        width, height = self.get_box_dimensions(scale)

        self.is_hovered = abs(mouse_x - self.screen_x) <= width * 0.5 and abs(mouse_y - self.screen_y) <= height * 0.5

        return self.is_hovered

    def start_drag(self, context, mouse_x, mouse_y):
        """Start dragging this value box."""
        if not self.is_hovered:
            return False

        self.is_dragging = True

        # Start the drag handler
        self.drag_handler.start_drag(context, mouse_x, mouse_y, self.current_value)

        # Activate scroll list aligned with this box
        self.scroll_list.activate(context, self.screen_x, self.screen_y, self.current_value)

        return True

    def update_drag(self, context, mouse_x, mouse_y, shift_held=False):
        """Update drag operation."""
        if not self.is_dragging:
            return

        # Update drag handler
        new_value = self.drag_handler.update_drag(context, mouse_x, mouse_y, shift_held)

        if new_value is not None:
            self.current_value = new_value

            # Update scroll list
            self.scroll_list.update_value(self.current_value)

    def end_drag(self, context):
        """End drag operation."""
        if not self.is_dragging:
            return

        self.is_dragging = False

        # End drag handler
        self.drag_handler.end_drag(context)

        # Deactivate scroll list
        self.scroll_list.deactivate()

    def draw(self, context, main_color, accent_color):
        """Draw the value box and scroll list."""
        scale = get_dpi_scale()

        # Draw scroll list FIRST (behind the box)
        if self.scroll_list.is_active:
            self.scroll_list.draw(context, main_color, accent_color)

        # Choose color based on state
        if self.is_hovered or self.is_dragging:
            color = (*accent_color[:3], 1.0)  # Full opacity when active
        else:
            color = main_color

        # Draw the value box
        self._draw_box(context, scale, color)

        # Draw the text
        self._draw_text(context, scale)

    def _draw_box(self, context, scale, color):
        """Draw the value box rectangle."""
        width, height = self.get_box_dimensions(scale)

        vertices = [
            (self.screen_x - width * 0.5, self.screen_y - height * 0.5),
            (self.screen_x + width * 0.5, self.screen_y - height * 0.5),
            (self.screen_x + width * 0.5, self.screen_y + height * 0.5),
            (self.screen_x - width * 0.5, self.screen_y + height * 0.5),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_text(self, context, scale):
        """Draw the text inside the value box."""
        font_id = 0
        blf.size(font_id, int(9 * scale))

        # Get text color from preferences
        prefs = get_prefs()
        text_color = ensure_alpha(prefs.text_color)
        blf.color(font_id, *text_color)

        # Draw text centered in box
        display_text = self.get_display_text()
        text_width, text_height = blf.dimensions(font_id, display_text)

        blf.position(font_id, self.screen_x - text_width * 0.5, self.screen_y - text_height * 0.5, 0)
        blf.draw(font_id, display_text)


class ScrollList:
    """
    The scrollable list that appears behind a ValueBox during dragging.

    This list shows available options/values and is always horizontally aligned
    with the parent ValueBox. The current selection is positioned to coincide
    exactly with the parent box.
    """

    def __init__(self, value_type, value_range, display_formatter=None, ascending_order=True):
        """
        Initialize a scroll list.

        Args:
            value_type (str): "value" for continuous values, "element" for discrete options
            value_range: (min, max) tuple for values, or list of options for elements
            display_formatter: Optional function to format display text
            ascending_order (bool): When True, low values at top, high values at bottom
        """
        self.value_type = value_type
        self.value_range = value_range
        self.display_formatter = display_formatter
        self.ascending_order = ascending_order

        # State
        self.is_active = False
        self.current_value = 0.0

        # Position (aligned with parent ValueBox)
        self.parent_x = 0.0
        self.parent_y = 0.0
        self.parent_width = 0.0

        # Visual properties
        self.item_height = 16.0  # Same as ValueBox height
        self.visible_items = 7  # Always show 7 items

        # Scroll offset for smooth movement
        self.scroll_offset = 0.0

    def activate(self, context, parent_x, parent_y, current_value):
        """
        Activate the scroll list aligned with parent ValueBox.

        Args:
            context: Blender context
            parent_x, parent_y: Position of parent ValueBox
            current_value: Current value to center on
        """
        self.is_active = True
        self.parent_x = parent_x
        self.parent_y = parent_y
        self.current_value = current_value
        self.scroll_offset = 0.0

        # Calculate parent width to match exactly
        scale = get_dpi_scale()
        if self.display_formatter:
            display_text = self.display_formatter(current_value)
        else:
            display_text = f"{int(round(current_value))}%" if self.value_type == "value" else "Sample"

        font_id = 0
        blf.size(font_id, int(9 * scale))
        text_width, text_height = blf.dimensions(font_id, display_text)
        self.parent_width = max(80.0 * scale, text_width + 16 * scale)

    def update_value(self, new_value):
        """Update the current value and scroll position."""
        self.current_value = new_value

    def set_scroll_offset(self, offset):
        """Set the scroll offset for smooth visual movement."""
        self.scroll_offset = offset

    def deactivate(self):
        """Deactivate the scroll list."""
        self.is_active = False
        self.scroll_offset = 0.0

    def draw(self, context, main_color, accent_color):
        """Draw the scroll list behind the parent ValueBox."""
        if not self.is_active:
            return

        scale = get_dpi_scale()
        item_height = self.item_height * scale

        # Draw items based on type (removed background for cleaner look)
        if self.value_type == "value":
            self._draw_value_items(context, scale, item_height, main_color, accent_color)
        else:  # element type
            self._draw_element_items(context, scale, item_height, main_color, accent_color)

    def _draw_value_items(self, context, scale, item_height, main_color, accent_color):
        """Draw value-based items (continuous values)."""
        # Generate values around current value
        current_val = self.current_value

        # Determine step size based on value type
        if "%" in str(self.display_formatter) if self.display_formatter else True:
            # For percentages, show 10% increments
            step = 10.0
            center_val = current_val
        elif "x" in str(self.display_formatter) if self.display_formatter else False:
            # For multiplier values, show 1x increments
            step = 1.0
            center_val = current_val
        else:
            # For other values, determine appropriate step
            val_range = self.value_range[1] - self.value_range[0]
            step = val_range / 20.0  # 20 steps across range
            center_val = current_val  # Draw items around center
        half_items = self.visible_items // 2
        for i in range(-half_items, half_items + 1):
            # Calculate display value and position
            # Note: In this coordinate system, negative y_offset moves up, positive y_offset moves down
            if self.ascending_order:
                # For ascending order (low at top, high at bottom):
                # We want negative i to produce smaller values at negative y_offset (top)
                # We want positive i to produce larger values at positive y_offset (bottom)
                display_value = center_val - (i * step)  # negative i = larger, positive i = smaller
                y_offset = i  # negative i = up, positive i = down
            else:
                # For descending order: larger values at top, smaller at bottom
                display_value = center_val + (i * step)  # negative i = smaller, positive i = larger
                y_offset = i  # negative i = up, positive i = down

            # Round to step increments to avoid duplicates
            if "%" in str(self.display_formatter) if self.display_formatter else True:
                display_value = round(display_value / step) * step
            elif "x" in str(self.display_formatter) if self.display_formatter else False:
                display_value = round(display_value)  # Round to whole numbers for multiplier

            y_pos = self.parent_y + (y_offset * item_height) + self.scroll_offset

            # Skip if out of range
            if display_value < self.value_range[0] or display_value > self.value_range[1]:
                continue

            # Check if this is the current/selected value
            is_current = abs(display_value - current_val) < step * 0.5

            # Draw item
            self._draw_item(context, scale, display_value, y_pos, is_current, main_color, accent_color)

    def _draw_element_items(self, context, scale, item_height, main_color, accent_color):
        """Draw element-based items (discrete options)."""
        if not isinstance(self.value_range, list):
            return

        current_index = int(self.current_value)
        half_items = self.visible_items // 2

        # Calculate visible range
        start_index = max(0, current_index - half_items)
        end_index = min(len(self.value_range), start_index + self.visible_items)

        # Adjust start if at end
        if end_index - start_index < self.visible_items:
            start_index = max(0, end_index - self.visible_items)

        # Draw items
        for i in range(start_index, end_index):
            # Calculate position relative to current selection
            relative_pos = i - current_index

            # Apply ascending_order for element-based lists too
            if self.ascending_order:
                # Ascending order: lower indices at top, higher indices at bottom
                y_offset = relative_pos
            else:
                # Descending order: higher indices at top, lower indices at bottom
                y_offset = -relative_pos

            y_pos = self.parent_y + (y_offset * item_height) + self.scroll_offset

            # Check if this is current selection
            is_current = i == current_index

            # Draw item
            self._draw_item(context, scale, i, y_pos, is_current, main_color, accent_color)

    def _draw_item(self, context, scale, value, y_pos, is_current, main_color, accent_color):
        """Draw a single item in the scroll list."""
        item_height = self.item_height * scale

        # Highlight current item subtly
        if is_current:
            highlight_color = (*accent_color[:3], 0.15)

            vertices = [
                (self.parent_x - self.parent_width * 0.4, y_pos - item_height * 0.4),
                (self.parent_x + self.parent_width * 0.4, y_pos - item_height * 0.4),
                (self.parent_x + self.parent_width * 0.4, y_pos + item_height * 0.4),
                (self.parent_x - self.parent_width * 0.4, y_pos + item_height * 0.4),
            ]

            indices = [(0, 1, 2), (0, 2, 3)]

            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

            gpu.state.blend_set("ALPHA")
            shader.bind()
            shader.uniform_float("color", ensure_alpha(highlight_color))
            batch.draw(shader)
            gpu.state.blend_set("NONE")

        # Draw item text
        font_id = 0
        font_size = int(10 * scale) if is_current else int(9 * scale)
        blf.size(font_id, font_size)

        # Get text color - more subtle for scroll list
        prefs = get_prefs()
        text_color = ensure_alpha((*prefs.text_color[:3], 0.6))
        blf.color(font_id, *text_color)

        # Format text
        if self.value_type == "value":
            if self.display_formatter:
                item_text = self.display_formatter(value)
            else:
                item_text = f"{int(round(value))}%"
        else:  # element type
            if self.display_formatter:
                item_text = self.display_formatter(value)
            elif isinstance(self.value_range, list) and 0 <= value < len(self.value_range):
                item_text = str(self.value_range[value])
            else:
                item_text = "Unknown"

        # Center text
        text_width, text_height = blf.dimensions(font_id, item_text)
        text_x = self.parent_x - text_width * 0.5
        text_y = y_pos - text_height * 0.5

        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, item_text)


class UnifiedDragHandler:
    """
    Unified drag handler for both value-based and element-based dragging.

    Handles the mechanics of dragging and calculates new values based on
    mouse movement. Provides different feel for different data types:
    - Value type: Smooth incremental changes
    - Element type: Jumpy selection with elasticity
    """

    def __init__(self, value_type, initial_value, value_range, parent_box=None):
        """
        Initialize unified drag handler.

        Args:
            value_type (str): "value" for continuous, "element" for discrete
            initial_value: Starting value
            value_range: (min, max) tuple for values, or list for elements
            parent_box: Reference to the parent ValueBox for accessing properties
        """
        self.value_type = value_type
        self.initial_value = initial_value
        self.value_range = value_range
        self.parent_box = parent_box

        # Drag state
        self.is_dragging = False
        self.drag_start_y = 0.0
        self.current_value = initial_value

        # Sensitivity settings - different speeds for different types
        if self.value_type == "value":
            self.pixels_per_unit = 2.5  # 4x speed for values (% and multiplier)
        else:
            self.pixels_per_unit = (
                20.0  # 0.5x speed for elements (operation and blend modes) - slower for better control
            )

        # Elasticity for element type (visual feedback before jumping)
        self.elasticity_threshold = 0.3  # Fraction of unit before jumping
        self.elastic_offset = 0.0  # Current elastic visual offset

    def start_drag(self, context, mouse_x, mouse_y, current_value):
        """Start drag operation."""
        self.is_dragging = True
        self.drag_start_y = mouse_y
        self.current_value = current_value
        self.initial_value = current_value
        self.elastic_offset = 0.0

    def update_drag(self, context, mouse_x, mouse_y, shift_held=False):
        """
        Update drag operation and return new value.

        Always calculates from initial drag position for responsiveness.

        Args:
            shift_held (bool): Whether the Shift key is held for stepped dragging
        """
        if not self.is_dragging:
            return None

        # Calculate total offset from drag start
        # Inverted: drag down (toward bottom of list) = increase value, drag up (toward top) = decrease value
        total_offset = mouse_y - self.drag_start_y

        # Convert to units
        units_moved = total_offset / self.pixels_per_unit

        if self.value_type == "value":
            # Smooth value changes
            return self._handle_value_drag(units_moved, shift_held)
        else:
            # Discrete element changes with elasticity
            return self._handle_element_drag(units_moved)

    def _handle_value_drag(self, units_moved, shift_held=False):
        """Handle dragging for continuous values."""
        # Standard drag behavior: drag up = increase value, drag down = decrease value

        # Determine step size based on value range and shift modifier
        if isinstance(self.value_range, tuple):
            val_range = self.value_range[1] - self.value_range[0]

            # For multiplier values (range 1.0-10.0), use 1.0 steps
            if self.value_range[0] == 1.0 and self.value_range[1] == 10.0:
                base_step = 1.0
                shift_step = 1.0  # Already in full steps for multiplier
            # For percentages, use 1% steps normally, 10% steps with shift
            elif val_range <= 100:
                base_step = 1.0
                shift_step = 10.0  # 10% steps when shift is held
            else:
                base_step = val_range / 100.0  # 100 steps across range
                shift_step = val_range / 10.0  # 10 steps across range with shift
        else:
            base_step = 1.0
            shift_step = 10.0

        # Choose step size based on shift modifier
        step = shift_step if shift_held else base_step

        # Calculate new value
        new_value = self.initial_value + (units_moved * step)

        # For shift mode, snap to step increments
        if shift_held:
            # Round to nearest step increment from the starting value
            steps_from_initial = round((new_value - self.initial_value) / step)
            new_value = self.initial_value + (steps_from_initial * step)

        # Clamp to range
        if isinstance(self.value_range, tuple):
            new_value = max(self.value_range[0], min(self.value_range[1], new_value))

        # Round to appropriate precision
        if self.value_range[0] == 1.0 and self.value_range[1] == 10.0:
            # For multiplier values, round to whole numbers
            new_value = round(new_value)
        else:
            # For other values, round to 2 decimal places
            new_value = round(new_value, 2)

        old_value = self.current_value
        self.current_value = new_value

        return new_value if new_value != old_value else None

    def _handle_element_drag(self, units_moved):
        """Handle dragging for discrete elements with elasticity."""
        if not isinstance(self.value_range, list):
            return None

        # For element-based lists with ascending_order = False (traditional order),
        # we need to invert the drag direction so that dragging down increases the value
        # (moves down in the visual list)
        if hasattr(self, "parent_box") and hasattr(self.parent_box, "ascending_order"):
            if not self.parent_box.ascending_order:
                # Invert the units_moved for traditional order lists
                units_moved = -units_moved

        # Calculate which element we should be at
        target_index = int(self.initial_value) + int(units_moved)

        # Calculate elasticity within current "cell"
        fractional_part = units_moved - int(units_moved)

        # Only jump when we've moved past the elasticity threshold
        if abs(fractional_part) > self.elasticity_threshold:
            # Jump to next/previous element
            if fractional_part > 0:
                target_index = int(self.initial_value) + int(units_moved) + 1
            else:
                target_index = int(self.initial_value) + int(units_moved)
        else:
            # Stay at current element but show elastic visual feedback
            target_index = int(self.initial_value) + int(units_moved)
            self.elastic_offset = fractional_part * self.pixels_per_unit

        # Clamp to valid range
        target_index = max(0, min(len(self.value_range) - 1, target_index))

        old_value = self.current_value
        self.current_value = target_index

        return target_index if target_index != old_value else None

    def get_elastic_offset(self):
        """Get the current elastic offset for visual feedback."""
        return self.elastic_offset

    def end_drag(self, context):
        """End drag operation."""
        self.is_dragging = False
        self.elastic_offset = 0.0


# ============================================================================
# ENHANCED DRAG HANDLER WITH UNIFIED SYSTEM
# ============================================================================


class ScopeBar:
    """
    Draggable bar for moving multiple pins simultaneously.

    Different bar types:
    - main_bar: Between main pins (level 7), moves both main pins together
    - left_secondary_bar: From left secondary to left main (level 6), moves both together
    - right_secondary_bar: From right main to right secondary (level 6), moves both together
    - outer_bar: Between main pins only (level 6), moves all 4 pins together

    Enhanced Features:
    - Hover highlighting to indicate interactivity
    - Enhanced opacity control for better visual feedback
    """

    def __init__(self, bar_type="main_bar"):
        """
        Initialize scope bar.

        Args:
            bar_type (str): Type of bar - "main_bar", "left_secondary_bar", "right_secondary_bar", "outer_bar"
        """
        self.bar_type = bar_type
        self.is_hovered = False
        self.is_dragging = False
        self.drag_offset = 0.0
        self.screen_x = 0.0
        self.screen_y = 0.0
        self.width = 0.0
        self.height = 16.0  # Same height as other elements

        # Enhanced opacity settings for better visual feedback
        self.normal_opacity = 0.1  # Very subtle when not interacting
        self.hover_opacity = 0.4  # More visible when hovering
        self.drag_opacity = 0.8  # Most visible when dragging

    def get_screen_position(self, context, pins):
        """Calculate screen position and dimensions based on bar type."""
        if len(pins) < 4:
            return 0.0, 0.0, 0.0

        # Get pin positions
        sec_left_x, _ = pins[0].get_screen_position(context)
        main_left_x, _ = pins[1].get_screen_position(context)
        main_right_x, _ = pins[2].get_screen_position(context)
        sec_right_x, _ = pins[3].get_screen_position(context)

        if self.bar_type == "main_bar":
            # Between main pins, positioned at main level (from bottom)
            self.screen_x = (main_left_x + main_right_x) * 0.5
            self.width = abs(main_right_x - main_left_x)
            self.screen_y = get_element_center_y(VerticalLevels.MAIN_BAR, context, from_bottom=True)

        elif self.bar_type == "left_secondary_bar":
            # From left secondary to left main, at secondary level (from bottom)
            self.screen_x = (sec_left_x + main_left_x) * 0.5
            self.width = abs(main_left_x - sec_left_x)
            self.screen_y = get_element_center_y(VerticalLevels.SECONDARY_BARS, context, from_bottom=True)

        elif self.bar_type == "right_secondary_bar":
            # From right main to right secondary, at secondary level (from bottom)
            self.screen_x = (main_right_x + sec_right_x) * 0.5
            self.width = abs(sec_right_x - main_right_x)
            self.screen_y = get_element_center_y(VerticalLevels.SECONDARY_BARS, context, from_bottom=True)

        elif self.bar_type == "outer_bar":
            # Only between main pins, moves all pins but drawn at secondary level (from bottom)
            self.screen_x = (main_left_x + main_right_x) * 0.5
            self.width = abs(main_right_x - main_left_x)
            self.screen_y = get_element_center_y(VerticalLevels.OUTER_BAR, context, from_bottom=True)

        return self.screen_x, self.screen_y, self.width

    def check_hover(self, mouse_x, mouse_y, context, pins):
        """Check if mouse is hovering over this bar."""
        screen_x, screen_y, width = self.get_screen_position(context, pins)
        scale = get_dpi_scale()
        height = self.height * scale

        # Check if mouse is within bar bounds
        self.is_hovered = abs(mouse_x - screen_x) <= width * 0.5 and abs(mouse_y - screen_y) <= height * 0.5
        return self.is_hovered

    def start_drag(self, mouse_x, mouse_y, context, pins):
        """Start dragging this bar."""
        if not self.is_hovered:
            return False

        self.is_dragging = True
        screen_x, _, _ = self.get_screen_position(context, pins)
        self.drag_offset = mouse_x - screen_x
        return True

    def update_drag(self, mouse_x, mouse_y, context, pins, scope_gui=None):
        """Update pin positions during bar drag with constraint logic."""
        if not self.is_dragging:
            return

        region = context.region
        view2d = region.view2d

        # Convert screen position back to frame
        adjusted_x = mouse_x - self.drag_offset
        target_frame, _ = view2d.region_to_view(adjusted_x, 0)

        # Round to full frames only
        target_frame = round(target_frame)

        # Store original positions to check for changes
        original_positions = [pin.frame for pin in pins]

        # Calculate offset from current center and move pins
        if self.bar_type == "main_bar":
            current_center = (pins[1].frame + pins[2].frame) * 0.5
            offset = target_frame - current_center
            # Move both main pins and round to full frames
            pins[1].frame = round(pins[1].frame + offset)
            pins[2].frame = round(pins[2].frame + offset)

        elif self.bar_type == "left_secondary_bar":
            current_center = (pins[0].frame + pins[1].frame) * 0.5
            offset = target_frame - current_center
            # Move left secondary and left main and round to full frames
            pins[0].frame = round(pins[0].frame + offset)
            pins[1].frame = round(pins[1].frame + offset)

        elif self.bar_type == "right_secondary_bar":
            current_center = (pins[2].frame + pins[3].frame) * 0.5
            offset = target_frame - current_center
            # Move right main and right secondary and round to full frames
            pins[2].frame = round(pins[2].frame + offset)
            pins[3].frame = round(pins[3].frame + offset)

        elif self.bar_type == "outer_bar":
            # For outer bar, use the actual center between all pins, not just main pins
            current_center = (pins[1].frame + pins[2].frame) * 0.5  # Use main pins center for positioning
            offset = target_frame - current_center
            # Move all pins and round to full frames
            for pin in pins:
                pin.frame = round(pin.frame + offset)

        # Apply constraint logic for each moved pin if scope_gui is provided
        if scope_gui:
            for i, pin in enumerate(pins):
                if pin.frame != original_positions[i]:
                    # Apply constraints for this pin
                    scope_gui._apply_pin_constraints(i, original_positions[i])

    def end_drag(self):
        """End dragging this bar."""
        self.is_dragging = False
        self.drag_offset = 0.0

    def should_highlight(self, scope_gui):
        """
        Check if this bar should be highlighted based on outer bar state.

        Args:
            scope_gui: Reference to ScopeGUI instance

        Returns:
            bool: True if this bar should be highlighted
        """
        # Get the outer bar from scope_gui
        outer_bar = None
        for bar in scope_gui.bars:
            if bar.bar_type == "outer_bar":
                outer_bar = bar
                break

        if outer_bar is None:
            return self.is_hovered or self.is_dragging

        # If this is the outer bar, use normal logic
        if self.bar_type == "outer_bar":
            return self.is_hovered or self.is_dragging

        # For other bars, highlight if outer bar is hovered/dragged OR this bar is hovered/dragged
        return outer_bar.is_hovered or outer_bar.is_dragging or self.is_hovered or self.is_dragging

    def draw(self, context, pins, main_color, accent_color, scope_gui=None):
        """Draw the bar with enhanced visual feedback."""
        screen_x, screen_y, width = self.get_screen_position(context, pins)
        scale = get_dpi_scale()
        height = self.height * scale

        # Don't draw if width is too small
        if width < 10 * scale:
            return

        # Choose base color based on state (similar to pins)
        should_highlight = (scope_gui and self.should_highlight(scope_gui)) or self.is_hovered or self.is_dragging

        if should_highlight:
            base_color = accent_color
        else:
            base_color = main_color

        # Choose opacity based on state with enhanced feedback
        if self.is_dragging:
            opacity = self.drag_opacity
        elif should_highlight:
            opacity = self.hover_opacity
        else:
            opacity = self.normal_opacity

        # Create bar color with appropriate opacity
        bar_color = (*base_color[:3], opacity)

        vertices = [
            (screen_x - width * 0.5, screen_y - height * 0.5),
            (screen_x + width * 0.5, screen_y - height * 0.5),
            (screen_x + width * 0.5, screen_y + height * 0.5),
            (screen_x - width * 0.5, screen_y + height * 0.5),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        # Enable blending for transparency
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(bar_color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")


class ScopeGUI:
    """
    Main scope GUI system.

    Manages all GUI components and provides a unified interface for scope operations.
    """

    def __init__(
        self,
        frame_range,
        operation_name,
        blend_range=None,
        start_blend=BlendType.LINEAR,
        end_blend=BlendType.LINEAR,
        operation_options=None,
        property_definitions=None,
        factor_value=None,
        factor_multiplier=1.0,
        quick_drag=False,
        show_intensity=True,
        show_blend_selectors=True,
    ):
        """
        Initialize the scope GUI.

        Args:
            frame_range (tuple): (start_frame, end_frame) for main pins
            operation_name (str): Name of the operation to display
            blend_range (int, optional): Outwards distance for secondary pins
            start_blend (str): Initial blend type for start
            end_blend (str): Initial blend type for end
            operation_options (list, optional): List of (id, name, description) tuples for menu options
            property_definitions (list, optional): List of property definitions for PropertyBoxes
                Each definition is a dict with keys: 'path', 'display_name', 'type', 'range', 'initial_value', 'decimal_speed'
            factor_value (float, optional): Initial factor value (range depends on guipins_overshoot preference). If None, factor handler is disabled.
            factor_multiplier (float): Multiplier for factor value
            quick_drag (bool): Whether to start factor dragging immediately
            show_intensity (bool): Whether to show the intensity (%) handler. Default True.
            show_blend_selectors (bool): Whether to show the blend mode selector boxes. Default True.
        """
        self.frame_range = frame_range
        self.operation_name = operation_name

        # Initialize operation selector
        self.operation_selector = OperationSelector(operation_name, operation_options)

        # Initialize property boxes
        self.property_boxes = []
        if property_definitions:
            for prop_def in property_definitions:
                property_box = PropertyBox(
                    property_path=prop_def.get("path", ""),
                    display_name=prop_def.get("display_name", "Property"),
                    property_type=prop_def.get("type", "float"),
                    value_range=prop_def.get("range", (0, 100)),
                    initial_value=prop_def.get("initial_value", None),
                    decimal_speed=prop_def.get("decimal_speed", 1.0),
                )
                self.property_boxes.append(property_box)

        # Calculate blend range if not provided
        if blend_range is None:
            frame_span = abs(frame_range[1] - frame_range[0])
            blend_range = max(1, int(frame_span / 3))

        self.blend_range = blend_range

        # Initialize pins
        self.pins = []
        self._create_pins()

        # Initialize intensity handler if enabled
        self.intensity_handler = None
        if show_intensity:
            self.intensity_handler = IntensityHandler(100.0)

        # Initialize factor handler if enabled
        self.factor_handler = None
        if factor_value is not None:
            self.factor_handler = Factor(factor_value, factor_multiplier, quick_drag)

        # Initialize blend selectors if enabled
        self.blend_selectors = []
        if show_blend_selectors:
            self.blend_selectors = [BlendSelector("left", start_blend), BlendSelector("right", end_blend)]

        # Initialize bars for multi-pin dragging
        self.bars = [
            ScopeBar("main_bar"),
            ScopeBar("left_secondary_bar"),
            ScopeBar("right_secondary_bar"),
            ScopeBar("outer_bar"),
        ]

        # State tracking
        self.is_active = False
        self.dragging_element = None

        # Cursor management
        self.cursor_manager = CursorManager()

        # Colors (configurable)
        prefs = get_prefs()
        self.main_color = prefs.guipins_main_color
        self.accent_color = prefs.guipins_accent_color
        self.text_color = prefs.guipins_text_color

    def _create_pins(self):
        """Create the four scope pins in proper order: secondary1, main1, main2, secondary2."""
        start_frame, end_frame = self.frame_range

        # Create pins in order: secondary1, main1, main2, secondary2
        self.pins.append(ScopePin(start_frame - self.blend_range, 0.0, False, 0))  # Secondary left
        self.pins.append(ScopePin(start_frame, 1.0, True, 1))  # Main left
        self.pins.append(ScopePin(end_frame, 1.0, True, 2))  # Main right
        self.pins.append(ScopePin(end_frame + self.blend_range, 0.0, False, 3))  # Secondary right

        # Update secondary pin influences
        self._update_secondary_influences()

    def _update_secondary_influences(self):
        """Update influence values for secondary pins."""
        if len(self.pins) < 4:
            return

        # Pin order: secondary1, main1, main2, secondary2
        secondary_left = self.pins[0]
        main_left = self.pins[1]
        main_right = self.pins[2]
        secondary_right = self.pins[3]

        # Left secondary pin - gradient from 0 to 1 approaching main left
        left_distance = abs(main_left.frame - secondary_left.frame)
        if left_distance > 0:
            secondary_left.influence = max(0.0, 1.0 - (left_distance / self.blend_range))
        else:
            secondary_left.influence = 1.0

        # Right secondary pin - gradient from 1 to 0 moving away from main right
        right_distance = abs(secondary_right.frame - main_right.frame)
        if right_distance > 0:
            secondary_right.influence = max(0.0, 1.0 - (right_distance / self.blend_range))
        else:
            secondary_right.influence = 1.0

    def update(self, context, event):
        """
        Update the GUI state based on input events.

        Args:
            context: Blender context
            event: Input event

        Returns:
            dict: Updated values including pin positions, intensity, and blending settings
        """
        if not self.is_active:
            return None

        mouse_x, mouse_y = event.mouse_region_x, event.mouse_region_y

        # Check if shift key is held
        shift_held = event.shift

        # Handle events
        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                self._handle_mouse_press(context, mouse_x, mouse_y)
            elif event.value == "RELEASE":
                self._handle_mouse_release(context, mouse_x, mouse_y)

        elif event.type == "MOUSEMOVE":
            self._handle_mouse_move(context, mouse_x, mouse_y, shift_held)

        # Update hover states
        self._update_hover_states(context, mouse_x, mouse_y)

        # Return current values
        return self.get_values()

    def _handle_mouse_press(self, context, mouse_x, mouse_y):
        """Handle mouse press events with enhanced drag system."""
        # Check bars first (higher priority)
        for bar in self.bars:
            if bar.start_drag(mouse_x, mouse_y, context, self.pins):
                self.dragging_element = bar
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                return

        # Check pins
        for pin in self.pins:
            if pin.start_drag(mouse_x, mouse_y, context):
                self.dragging_element = pin
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                return

        # Check intensity handler (use main pins at indices 1 and 2) if enabled
        if self.intensity_handler:
            main_pins = [self.pins[1], self.pins[2]]
            if self.intensity_handler.start_drag(mouse_x, mouse_y, context, main_pins, self.operation_selector):
                self.dragging_element = self.intensity_handler
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                return

        # Check factor handler if enabled
        if self.factor_handler:
            main_pins = [self.pins[1], self.pins[2]]
            if self.factor_handler.start_drag(
                mouse_x,
                mouse_y,
                context,
                main_pins,
                self.operation_selector,
                self.intensity_handler,
            ):
                self.dragging_element = self.factor_handler
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                return

        # Check blend selectors (use main pins at indices 1 and 2, secondary pins at indices 0 and 3)
        main_pins = [self.pins[1], self.pins[2]]
        secondary_pins = [self.pins[0], self.pins[3]]
        for selector in self.blend_selectors:
            if selector.start_drag(mouse_x, mouse_y, context, main_pins, secondary_pins):
                self.dragging_element = selector
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                return

        # Check operation selector
        if hasattr(self, "operation_selector") and self.operation_selector:
            main_pins = [self.pins[1], self.pins[2]]
            if self.operation_selector.check_hover(mouse_x, mouse_y, context, main_pins):
                if self.operation_selector.start_drag(mouse_x, mouse_y, context):
                    self.dragging_element = self.operation_selector
                    self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                    return

        # Check property boxes
        for property_box in self.property_boxes:
            if property_box.start_drag(mouse_x, mouse_y, context):
                self.dragging_element = property_box
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)
                return

    def _handle_mouse_release(self, context, mouse_x, mouse_y):
        """Handle mouse release events with enhanced drag system."""
        if self.dragging_element:
            # Update secondary pin influences after pin or bar movement
            if isinstance(self.dragging_element, (ScopePin, ScopeBar)):
                self._update_secondary_influences()

            # End drag on the element (enhanced handlers handle cursor restoration)
            if isinstance(
                self.dragging_element,
                (IntensityHandler, BlendSelector, OperationSelector, PropertyBox, Factor),
            ):
                self.dragging_element.end_drag(context)
            elif hasattr(self.dragging_element, "end_drag"):
                self.dragging_element.end_drag()

            # Always restore cursor when drag ends
            self.cursor_manager.restore_cursor(context)

            # Reset dragging element
            self.dragging_element = None

    def _handle_mouse_move(self, context, mouse_x, mouse_y, shift_held=False):
        """Handle mouse move events."""
        # Handle quick drag mode - automatically start factor dragging on mouse movement
        if not self.dragging_element and self.factor_handler and self.factor_handler.in_quick_drag:
            main_pins = [self.pins[1], self.pins[2]]
            # Start dragging the factor handler without requiring mouse press
            if self.factor_handler.start_drag(
                mouse_x,
                mouse_y,
                context,
                main_pins,
                self.operation_selector,
                self.intensity_handler,
            ):
                self.dragging_element = self.factor_handler
                self.cursor_manager.hide_cursor(context, mouse_x, mouse_y)

        if not self.dragging_element:
            return

        if isinstance(self.dragging_element, ScopePin):
            self._handle_pin_drag(context, mouse_x, mouse_y)
        elif isinstance(self.dragging_element, ScopeBar):
            self.dragging_element.update_drag(mouse_x, mouse_y, context, self.pins, self)
            # Update secondary influences after bar movement
            self._update_secondary_influences()
        elif isinstance(self.dragging_element, IntensityHandler):
            main_pins = [self.pins[1], self.pins[2]]
            self.dragging_element.update_drag(mouse_x, mouse_y, context, main_pins, self.operation_selector, shift_held)
        elif isinstance(self.dragging_element, Factor):
            main_pins = [self.pins[1], self.pins[2]]
            self.dragging_element.update_drag(
                mouse_x,
                mouse_y,
                context,
                main_pins,
                self.operation_selector,
                self.intensity_handler,
                shift_held,
            )
        elif isinstance(self.dragging_element, BlendSelector):
            main_pins = [self.pins[1], self.pins[2]]
            secondary_pins = [self.pins[0], self.pins[3]]
            self.dragging_element.update_drag(mouse_x, mouse_y, context, main_pins, secondary_pins)
        elif isinstance(self.dragging_element, OperationSelector):
            self.dragging_element.update_drag(mouse_x, mouse_y, context)
        elif isinstance(self.dragging_element, PropertyBox):
            self.dragging_element.update_drag(mouse_x, mouse_y, context, shift_held)

    def _handle_pin_drag(self, context, mouse_x, mouse_y):
        """Handle pin dragging with constraint logic."""
        if not isinstance(self.dragging_element, ScopePin):
            return

        # Store original position
        original_frame = self.dragging_element.frame

        # Update drag position
        self.dragging_element.update_drag(mouse_x, mouse_y, context)

        # Find dragging pin index
        drag_index = self.pins.index(self.dragging_element)

        # Apply constraints and modifier behaviors
        self._apply_pin_constraints(drag_index, original_frame)

        # Update secondary influences
        self._update_secondary_influences()

    def _apply_pin_constraints(self, drag_index, original_frame):
        """Apply constraints with automatic pushing behavior."""
        dragging_pin = self.pins[drag_index]

        # Apply automatic pushing behavior
        self._apply_pushing_constraints(drag_index)

        # Ensure secondary pins stay outside main pins
        self._enforce_secondary_pin_ordering()

    def _apply_pushing_constraints(self, drag_index):
        """Apply pushing constraints to maintain relative positions."""
        if len(self.pins) < 4:
            return

        dragging_pin = self.pins[drag_index]

        # Pin order: secondary_left(0), main_left(1), main_right(2), secondary_right(3)

        if drag_index == 0:  # Secondary left
            # Push main left if we get too close (allow same frame)
            if dragging_pin.frame > self.pins[1].frame:
                self.pins[1].frame = dragging_pin.frame
                # Push main right if main left pushes into it
                if self.pins[1].frame > self.pins[2].frame:
                    self.pins[2].frame = self.pins[1].frame
                    # Push secondary right if main right pushes into it
                    if self.pins[2].frame > self.pins[3].frame:
                        self.pins[3].frame = self.pins[2].frame

        elif drag_index == 1:  # Main left
            # Push secondary left if we get too close (allow same frame)
            if dragging_pin.frame < self.pins[0].frame:
                self.pins[0].frame = dragging_pin.frame
            # Push main right if we overlap (main pins can share frame)
            if dragging_pin.frame > self.pins[2].frame:
                self.pins[2].frame = dragging_pin.frame
                # Push secondary right if main right pushes into it
                if self.pins[2].frame > self.pins[3].frame:
                    self.pins[3].frame = self.pins[2].frame

        elif drag_index == 2:  # Main right
            # Push main left if we overlap (main pins can share frame)
            if dragging_pin.frame < self.pins[1].frame:
                self.pins[1].frame = dragging_pin.frame
                # Push secondary left if main left pushes into it
                if self.pins[1].frame < self.pins[0].frame:
                    self.pins[0].frame = self.pins[1].frame
            # Push secondary right if we get too close (allow same frame)
            if dragging_pin.frame > self.pins[3].frame:
                self.pins[3].frame = dragging_pin.frame

        elif drag_index == 3:  # Secondary right
            # Push main right if we get too close (allow same frame)
            if dragging_pin.frame < self.pins[2].frame:
                self.pins[2].frame = dragging_pin.frame
                # Push main left if main right pushes into it
                if self.pins[2].frame < self.pins[1].frame:
                    self.pins[1].frame = self.pins[2].frame
                    # Push secondary left if main left pushes into it
                    if self.pins[1].frame < self.pins[0].frame:
                        self.pins[0].frame = self.pins[1].frame

    def _enforce_secondary_pin_ordering(self):
        """Ensure secondary pins stay outside main pins in proper order."""
        if len(self.pins) < 4:
            return

        # Pin order: secondary1, main1, main2, secondary2
        secondary_left = self.pins[0]
        main_left = self.pins[1]
        main_right = self.pins[2]
        secondary_right = self.pins[3]

        # Secondary left must be <= main left (allow same frame)
        if secondary_left.frame > main_left.frame:
            secondary_left.frame = main_left.frame

        # Secondary right must be >= main right (allow same frame)
        if secondary_right.frame < main_right.frame:
            secondary_right.frame = main_right.frame

    def _update_hover_states(self, context, mouse_x, mouse_y):
        """Update hover states for all elements."""
        if self.dragging_element:
            return  # Don't update hover

        # Check bars
        for bar in self.bars:
            bar.check_hover(mouse_x, mouse_y, context, self.pins)

        # Check pins
        for pin in self.pins:
            pin.check_hover(mouse_x, mouse_y, context)

        # Check intensity handler (use main pins at indices 1 and 2) if enabled
        if self.intensity_handler:
            main_pins = [self.pins[1], self.pins[2]]
            self.intensity_handler.check_hover(mouse_x, mouse_y, context, main_pins, self.operation_selector)

        # Check factor handler if enabled
        if self.factor_handler:
            main_pins = [self.pins[1], self.pins[2]]
            self.factor_handler.check_hover(
                mouse_x,
                mouse_y,
                context,
                main_pins,
                self.operation_selector,
                self.intensity_handler,
            )

        # Check blend selectors (use main pins at indices 1 and 2, secondary pins at indices 0 and 3)
        main_pins = [self.pins[1], self.pins[2]]
        secondary_pins = [self.pins[0], self.pins[3]]
        for selector in self.blend_selectors:
            selector.check_hover(mouse_x, mouse_y, context, main_pins, secondary_pins)

        # Check operation selector
        if hasattr(self, "operation_selector") and self.operation_selector:
            # Pass main pins for proper position calculation
            main_pins = [self.pins[1], self.pins[2]]
            self.operation_selector.check_hover(mouse_x, mouse_y, context, main_pins)

        # Check property boxes
        scale = get_dpi_scale()
        for property_box in self.property_boxes:
            property_box.check_hover(mouse_x, mouse_y, scale, self.operation_selector, self.intensity_handler)
            property_box.check_proximity(mouse_x, mouse_y, scale, self.operation_selector, self.intensity_handler)

    def draw(self, context):
        """Draw the complete scope GUI in proper vertical level order."""
        if not self.is_active:
            return

        # Draw gradient fills first (background)
        self._draw_gradient_fills(context)

        # Draw from top level to bottom level (proper z-order)

        # Top Level 1: Operation name box (now handled by OperationSelector)
        # Draw operation selector (same level as operation name box)
        if self.operation_selector:
            main_pins = [self.pins[1], self.pins[2]]
            self.operation_selector.draw(context, main_pins, self.main_color, self.accent_color)

        # Top Level 2+: Property boxes (one per level after operation box)
        self._draw_property_boxes(context)

        # Top Level (after properties): % box (center) and multiplier box (beside % box)
        main_pins = [self.pins[1], self.pins[2]]
        secondary_pins = [self.pins[0], self.pins[3]]

        # Draw % box (handles its own overlay) if enabled
        if self.intensity_handler:
            self.intensity_handler.draw(context, main_pins, self.main_color, self.accent_color, self.operation_selector)

        # Draw factor handler if enabled
        if self.factor_handler:
            self.factor_handler.draw(
                context,
                main_pins,
                self.main_color,
                self.accent_color,
                self.operation_selector,
                self.intensity_handler,
            )

        # Bottom Level 1: Secondary pins, secondary-to-main bars, outer bar, and blend selectors
        for i, pin in enumerate(self.pins):
            if not pin.is_main:  # Draw secondary pins
                pin.draw(context, self.main_color, self.accent_color)

        # Draw blend selectors (now at bottom level, beside secondary pins)
        for selector in self.blend_selectors:
            selector.draw(context, main_pins, secondary_pins, self.main_color, self.accent_color)

        # Draw secondary-to-main bars and outer bar (all at level 1)
        for bar in self.bars:
            if bar.bar_type in ["left_secondary_bar", "right_secondary_bar", "outer_bar"]:
                bar.draw(context, self.pins, self.main_color, self.accent_color, self)

        # Bottom Level 2: Main pins and main pins bar
        for i, pin in enumerate(self.pins):
            if pin.is_main:  # Draw main pins
                pin.draw(context, self.main_color, self.accent_color)

        # Draw main pins bar (at main pins level)
        for bar in self.bars:
            if bar.bar_type == "main_bar":
                bar.draw(context, self.pins, self.main_color, self.accent_color, self)

    def _draw_property_boxes(self, context):
        """Draw property boxes positioned below operation box."""
        if not self.property_boxes:
            return

        # Calculate centered X position between main pins
        main_pins = [self.pins[1], self.pins[2]]
        pin1_x, _ = main_pins[0].get_screen_position(context)
        pin2_x, _ = main_pins[1].get_screen_position(context)
        center_x = (pin1_x + pin2_x) * 0.5

        # Draw each property box on its own level
        for i, property_box in enumerate(self.property_boxes):
            # Calculate Y position: start after operation box, then one level per property
            level = VerticalLevels.PROPERTY_BOXES_START + i
            center_y = get_element_center_y(level, context, from_bottom=False)

            # Set position and draw
            property_box.set_position(center_x, center_y)
            property_box.draw(
                context, self.main_color, self.accent_color, self.operation_selector, self.intensity_handler
            )

    def _draw_gradient_fills(self, context):
        """Draw gradient fills to show influence areas."""
        if len(self.pins) < 4:
            return

        region = context.region
        prefs = get_prefs()

        # Pin positions
        secondary_left = self.pins[0]
        main_left = self.pins[1]
        main_right = self.pins[2]
        secondary_right = self.pins[3]

        # Get screen positions
        sec_left_x, _ = secondary_left.get_screen_position(context)
        main_left_x, _ = main_left.get_screen_position(context)
        main_right_x, _ = main_right.get_screen_position(context)
        sec_right_x, _ = secondary_right.get_screen_position(context)
        # Color constants for influence visualization
        influence_color = prefs.guipins_mask_color[:3]  # RGB only
        max_influence_opacity = prefs.guipins_mask_color[3]  # Use alpha from mask color

        # Color for no influence areas
        no_influence_color = (*influence_color, max_influence_opacity)

        # Draw left no-influence area (left of secondary left pin)
        if sec_left_x > 0:
            self._draw_solid_fill(context, 0, sec_left_x, no_influence_color)

        # Draw right no-influence area (right of secondary right pin)
        if sec_right_x < region.width:
            self._draw_solid_fill(context, sec_right_x, region.width, no_influence_color)

        # Draw left gradient area (secondary left to main left)
        if sec_left_x < main_left_x:
            self._draw_gradient_fill(
                context,
                sec_left_x,
                main_left_x,
                self.blend_selectors[0].blend_type if self.blend_selectors else BlendType.LINEAR,
                "left",
                influence_color,
                max_influence_opacity,
            )

        # Draw right gradient area (main right to secondary right)
        if main_right_x < sec_right_x:
            self._draw_gradient_fill(
                context,
                main_right_x,
                sec_right_x,
                self.blend_selectors[1].blend_type if len(self.blend_selectors) > 1 else BlendType.LINEAR,
                "right",
                influence_color,
                max_influence_opacity,
            )

    def _draw_solid_fill(self, context, start_x, end_x, color):
        """Draw a solid color fill area."""
        region = context.region

        vertices = [
            (start_x, 0),
            (end_x, 0),
            (end_x, region.height),
            (start_x, region.height),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_gradient_fill(self, context, start_x, end_x, blend_type, side, influence_color, max_influence_opacity):
        """Draw a gradient fill area based on blend type."""
        region = context.region

        # Create gradient by drawing multiple thin vertical strips
        strips = 50  # Number of gradient strips
        strip_width = (end_x - start_x) / strips

        for i in range(strips):
            strip_start = start_x + (i * strip_width)
            strip_end = start_x + ((i + 1) * strip_width)

            # Calculate influence based on position and blending type
            if side == "left":
                # From secondary (0% influence) to main (100% influence)
                ratio = i / (strips - 1)

            else:
                # From main (100% influence) to secondary (0% influence)
                ratio = 1.0 - (i / (strips - 1))

            # Apply blend curve
            influence = self._apply_blend_curve(ratio, blend_type)

            # Color: transparent at main pins (100% influence), colored at secondary pins (0% influence)
            alpha = (1.0 - influence) * max_influence_opacity  # 0 to max_influence_opacity alpha
            color = (*influence_color, alpha)

            # Draw strip
            vertices = [
                (strip_start, 0),
                (strip_end, 0),
                (strip_end, region.height),
                (strip_start, region.height),
            ]

            indices = [(0, 1, 2), (0, 2, 3)]

            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

            gpu.state.blend_set("ALPHA")
            shader.bind()
            shader.uniform_float("color", ensure_alpha(color))
            batch.draw(shader)

        gpu.state.blend_set("NONE")

    def _apply_blend_curve(self, ratio, blend_type):
        """Apply blend curve to influence ratio."""
        from math import pow

        if blend_type == BlendType.LINEAR:
            return ratio
        elif blend_type == BlendType.QUADRATIC_IN:
            return ratio * ratio
        elif blend_type == BlendType.QUADRATIC_OUT:
            return 1.0 - (1.0 - ratio) * (1.0 - ratio)
        elif blend_type == BlendType.QUADRATIC_IN_OUT:
            if ratio < 0.5:
                return 2.0 * ratio * ratio
            else:
                return 1.0 - 2.0 * (1.0 - ratio) * (1.0 - ratio)
        elif blend_type == BlendType.CUBIC_IN:
            return ratio * ratio * ratio
        elif blend_type == BlendType.CUBIC_OUT:
            return 1.0 - (1.0 - ratio) * (1.0 - ratio) * (1.0 - ratio)
        elif blend_type == BlendType.CUBIC_IN_OUT:
            if ratio < 0.5:
                return 4.0 * ratio * ratio * ratio
            else:
                return 1.0 - 4.0 * (1.0 - ratio) * (1.0 - ratio) * (1.0 - ratio)
        elif blend_type == BlendType.EXPONENTIAL_IN:
            return pow(ratio, 3)
        elif blend_type == BlendType.EXPONENTIAL_OUT:
            return 1.0 - pow(1.0 - ratio, 3)
        elif blend_type == BlendType.EXPONENTIAL_IN_OUT:
            if ratio < 0.5:
                return 4.0 * pow(ratio, 3)
            else:
                return 1.0 - 4.0 * pow(1.0 - ratio, 3)

        return ratio  # Default to linear

    def get_values(self):
        """
        Get current values from the GUI.

        Returns:
            dict: Dictionary containing all current values
        """
        # Get property values
        property_values = {}
        for property_box in self.property_boxes:
            property_values[property_box.property_path] = property_box.current_value

        values = {
            "pin_positions": [pin.frame for pin in self.pins],
            "pin_influences": [pin.influence for pin in self.pins],
            "intensity": (
                self.intensity_handler.intensity if self.intensity_handler else 100.0
            ),  # Default to 100% when disabled
            "effective_intensity": (
                self.intensity_handler.intensity if self.intensity_handler else 100.0
            ),  # Same as intensity, no multiplier
            "start_blend": self.blend_selectors[0].blend_type if self.blend_selectors else BlendType.LINEAR,
            "end_blend": self.blend_selectors[1].blend_type if len(self.blend_selectors) > 1 else BlendType.LINEAR,
            "main_pins": [self.pins[1].frame, self.pins[2].frame],  # Main pins at indices 1 and 2
            "secondary_pins": [self.pins[0].frame, self.pins[3].frame],  # Secondary pins at indices 0 and 3
            "current_operation": self.operation_selector.get_current_operation() if self.operation_selector else None,
            "properties": property_values,
        }

        # Add property values at top level for backward compatibility
        values.update(property_values)

        # Add factor values if factor handler is enabled
        if self.factor_handler:
            values.update(
                {
                    "factor": self.factor_handler.factor,
                    "effective_factor": self.factor_handler.get_effective_factor(),
                    "factor_multiplier": self.factor_handler.multiplier,
                }
            )

        return values

    def set_colors(self, main_color, accent_color):
        """
        Set custom colors for the GUI.

        Args:
            main_color (tuple): RGBA color for main elements
            accent_color (tuple): RGBA color for accented elements
        """
        self.main_color = main_color
        self.accent_color = accent_color

    def activate(self):
        """Activate the scope GUI."""
        self.is_active = True

    def deactivate(self, context=None):
        """Deactivate the scope GUI and ensure cursor is restored."""
        self.is_active = False

        # Always restore cursor when deactivating to catch any errors
        if hasattr(self, "cursor_manager") and self.cursor_manager.cursor_hidden:
            self.cursor_manager.restore_cursor(context)

        # Clear any dragging state
        self.dragging_element = None

    def set_intensity(self, intensity):
        """Set the intensity value."""
        if self.intensity_handler:
            self.intensity_handler.intensity = intensity
            self.intensity_handler.value_box.current_value = intensity
        # If intensity handler is disabled, we ignore the set operation
        # since the intensity is effectively always 100%

    def get_factor_handler_screen_position(self, context):
        """
        Get the screen position of the factor handler for mouse warping.

        Returns:
            tuple: (x, y) screen coordinates of the factor handler, or None if no factor handler
        """
        if not self.factor_handler or len(self.pins) < 3:
            return None

        # Get main pins (pins[1] and pins[2])
        main_pins = [self.pins[1], self.pins[2]]

        # Calculate screen position using the factor handler's method
        screen_x, screen_y = self.factor_handler.get_screen_position(
            context, main_pins, self.operation_selector, self.intensity_handler
        )

        # Return the actual handler position (not background center)
        return (self.factor_handler.handler_x, self.factor_handler.handler_y)

    def update_property_definitions(self, property_definitions):
        """Update property definitions and recreate property boxes."""
        # Clear existing property boxes
        self.property_boxes = []

        # Create new property boxes from definitions
        if property_definitions:
            for prop_def in property_definitions:
                property_box = PropertyBox(
                    property_path=prop_def["path"],
                    display_name=prop_def["display_name"],
                    property_type=prop_def["type"],
                    value_range=prop_def["range"],
                    initial_value=prop_def["initial_value"],
                    decimal_speed=prop_def["decimal_speed"],
                )
                self.property_boxes.append(property_box)


class OperationSelector:
    """
    Operation selector for the scope GUI.

    Provides a clickable operation name that can show a menu of available operations
    and allows dragging to change between them. Uses the same ValueBox system as BlendSelector.
    """

    def __init__(self, operation_name, operation_options=None):
        """
        Initialize the operation selector.

        Args:
            operation_name (str): Current operation name
            operation_options (list, optional): List of (id, name, description) tuples for menu options
        """
        self.operation_name = operation_name
        self.operation_options = operation_options or []
        self.screen_x = 0.0
        self.screen_y = 0.0

        # Find current option index
        self.current_option_index = 0
        if self.operation_options:
            for i, (op_id, op_name, op_desc) in enumerate(self.operation_options):
                if op_name == operation_name:
                    self.current_option_index = i
                    break

        # Create ValueBox for operation selection (only if we have options)
        if self.operation_options:
            # Extract just the names for the options list
            operation_names = [op_name for op_id, op_name, op_desc in self.operation_options]
            display_formatter = lambda x: (
                operation_names[int(round(float(x)))] if 0 <= int(round(float(x))) < len(operation_names) else "Unknown"
            )
            self.value_box = ValueBox("element", self.current_option_index, operation_names, display_formatter)
            # Element-based lists should use descending order (traditional behavior)
            self.value_box.ascending_order = False
        else:
            self.value_box = None

    def get_screen_position(self, context, main_pins):
        """Calculate screen position centered between main pins."""
        if len(main_pins) < 2:
            return 0.0, 0.0

        # Position horizontally between main pins
        pin1_x, _ = main_pins[0].get_screen_position(context)
        pin2_x, _ = main_pins[1].get_screen_position(context)

        # Calculate center position
        self.screen_x = (pin1_x + pin2_x) * 0.5

        # Vertical position: operation box level (from top)
        self.screen_y = get_element_center_y(VerticalLevels.OPERATION_BOX, context, from_bottom=False)

        # Set ValueBox position if available
        if self.value_box:
            self.value_box.set_position(self.screen_x, self.screen_y)

        return self.screen_x, self.screen_y

    def check_hover(self, mouse_x, mouse_y, context, main_pins=None):
        """Check if mouse is hovering over the operation box."""
        if not self.operation_options or not self.value_box:
            return False

        screen_x, screen_y = self.get_screen_position(context, main_pins)
        scale = get_dpi_scale()

        # Use ValueBox for hover detection (same as BlendSelector)
        return self.value_box.check_hover(mouse_x, mouse_y, scale)

    def start_drag(self, mouse_x, mouse_y, context):
        """Start dragging the operation selector."""
        if not self.value_box or not self.operation_options:
            return False

        return self.value_box.start_drag(context, mouse_x, mouse_y)

    def update_drag(self, mouse_x, mouse_y, context):
        """Update operation selection during drag."""
        if not self.value_box:
            return

        self.value_box.update_drag(context, mouse_x, mouse_y)

        # Update selection index and operation name
        self.current_option_index = int(round(float(self.value_box.current_value)))
        if 0 <= self.current_option_index < len(self.operation_options):
            self.operation_name = self.operation_options[self.current_option_index][1]

    def end_drag(self, context):
        """End dragging the operation selector."""
        if not self.value_box:
            return

        self.value_box.end_drag(context)

    def get_current_operation(self):
        """Get the current operation ID."""
        if not self.operation_options or self.current_option_index >= len(self.operation_options):
            return None
        return self.operation_options[self.current_option_index][0]

    def set_operation(self, operation_id):
        """Set the current operation by ID."""
        if not self.operation_options:
            return

        for i, (op_id, op_name, op_desc) in enumerate(self.operation_options):
            if op_id == operation_id:
                self.current_option_index = i
                self.operation_name = op_name
                if self.value_box:
                    self.value_box.current_value = i
                break

    def draw(self, context, main_pins, main_color, accent_color):
        """Draw the operation selector."""
        screen_x, screen_y = self.get_screen_position(context, main_pins)

        # Draw the ValueBox if available (handles its own overlay, same as BlendSelector)
        if self.value_box:
            self.value_box.draw(context, main_color, accent_color)


class PropertyBox:
    """
    Property box for displaying and editing properties.

    Shows a split box with display name on the left and value on the right.
    Supports int, float, and bool types with appropriate interaction methods.
    Features instant opacity change based on mouse proximity.
    """

    # Opacity behavior constants
    FADE_MIN_OPACITY = 0.1  # 10% minimum opacity when not in proximity
    FADE_MAX_OPACITY = 1.0  # 100% maximum opacity when in proximity
    PROXIMITY_MULTIPLIER = 2.0  # 2x bounding box for proximity detection

    def __init__(
        self, property_path, display_name, property_type, value_range=None, initial_value=None, decimal_speed=1.0
    ):
        """
        Initialize property box.

        Args:
            property_path (str): Path to the property for referencing
            display_name (str): Display name shown in left box
            property_type (str): "int", "float", or "bool"
            value_range (tuple, optional): (min, max) for int/float types
            initial_value: Initial value (if None, will use current property value)
            decimal_speed (float): Speed multiplier for decimal adjustments
        """
        self.property_path = property_path
        self.display_name = display_name
        self.property_type = property_type
        self.value_range = value_range or (0, 100)  # Default range
        self.decimal_speed = decimal_speed

        # Get initial value from property or use provided value
        if initial_value is not None:
            self.current_value = initial_value
        else:
            # In real usage, this would get the actual property value
            # For now, use type-appropriate defaults
            if property_type == "bool":
                self.current_value = False
            elif property_type == "int":
                self.current_value = int(self.value_range[0])
            else:  # float
                self.current_value = float(self.value_range[0])

        # Visual properties - width now calculated dynamically like Factor handler
        self.screen_x = 0.0
        self.screen_y = 0.0

        # Interaction state
        self.is_hovered = False
        self.is_dragging = False
        self.drag_start_x = 0.0
        self.drag_start_value = 0.0

        # Proximity opacity state
        self.is_in_proximity = False
        self.current_opacity = self.FADE_MIN_OPACITY

    def get_box_dimensions(self, scale, operation_selector=None, intensity_handler=None):
        """Get the dimensions of the property boxes using the same approach as Factor handler."""
        # Calculate total width the same way as Factor handler
        total_width = 0.0

        # Add operation box width
        if operation_selector and operation_selector.value_box:
            op_width, _ = operation_selector.value_box.get_box_dimensions(scale)
            total_width += op_width

        # Add intensity handler width
        if intensity_handler and intensity_handler.value_box:
            intensity_width, _ = intensity_handler.value_box.get_box_dimensions(scale)
            total_width += intensity_width

        # Add padding between elements (20px for spacing)
        total_width += 20 * scale

        # Use the calculated total width (same as Factor background width)
        height = get_unit_height()  # Use standard unit height like Factor

        if self.property_type == "bool":
            # For bool: name takes most width, value is square on the right
            name_width = total_width - height  # Value box is square (height x height)
            value_width = height
        else:
            # For int/float: name takes 2/3, value takes 1/3
            name_width = total_width * (2.0 / 3.0)
            value_width = total_width * (1.0 / 3.0)

        return total_width, height, name_width, value_width

    def get_display_text(self):
        """Get the text to display in the value box."""
        if self.property_type == "bool":
            return ""  # Bool shows as filled/unfilled square
        elif self.property_type == "int":
            return str(int(self.current_value))
        else:  # float
            return f"{self.current_value:.2f}"

    def set_position(self, x, y):
        """Set the screen position of this property box."""
        self.screen_x = x
        self.screen_y = y

    def check_proximity(self, mouse_x, mouse_y, scale, operation_selector=None, intensity_handler=None):
        """Check if mouse is in proximity area (2x bounding box) and update opacity instantly."""
        total_width, height, name_width, value_width = self.get_box_dimensions(
            scale, operation_selector, intensity_handler
        )

        # Calculate the full property box bounds (name + padding + value)
        padding = 8.0 * scale
        full_width = name_width + padding + value_width

        # Expand bounds by proximity multiplier
        proximity_width = full_width * self.PROXIMITY_MULTIPLIER
        proximity_height = height * self.PROXIMITY_MULTIPLIER

        # Check if mouse is within proximity area
        self.is_in_proximity = (
            abs(mouse_x - self.screen_x) <= proximity_width * 0.5
            and abs(mouse_y - self.screen_y) <= proximity_height * 0.5
        )

        # Instantly update opacity based on proximity
        if self.is_in_proximity:
            self.current_opacity = self.FADE_MAX_OPACITY
        else:
            self.current_opacity = self.FADE_MIN_OPACITY

    def check_hover(self, mouse_x, mouse_y, scale, operation_selector=None, intensity_handler=None):
        """Check if mouse is hovering over the value box (only value box is interactive)."""
        total_width, height, name_width, value_width = self.get_box_dimensions(
            scale, operation_selector, intensity_handler
        )

        # Add padding between name and value boxes (same as in draw method)
        padding = 8.0 * scale  # 8px padding

        # Calculate value box position (same logic as in draw method)
        name_box_center_x = self.screen_x - (total_width - name_width) * 0.5
        name_box_right_edge = name_box_center_x + name_width * 0.5
        value_box_center_x = name_box_right_edge + padding + value_width * 0.5

        if self.property_type == "bool":
            # For boolean: check against the actual checkbox area (square, positioned half its width to the left)
            checkbox_size = height * 0.8  # Same size calculation as in draw method
            checkbox_center_x = value_box_center_x - (checkbox_size * 0.5)  # Half width to the left
            self.is_hovered = (
                abs(mouse_x - checkbox_center_x) <= checkbox_size * 0.5
                and abs(mouse_y - self.screen_y) <= checkbox_size * 0.5
            )
        else:
            # For numeric: check against the full value box area
            self.is_hovered = (
                abs(mouse_x - value_box_center_x) <= value_width * 0.5 and abs(mouse_y - self.screen_y) <= height * 0.5
            )

        return self.is_hovered

    def start_drag(self, mouse_x, mouse_y, context):
        """Start dragging the property value."""
        if not self.is_hovered:
            return False

        if self.property_type == "bool":
            # For bool, toggle on click
            old_value = self.current_value
            self.current_value = not self.current_value
            return False  # No continuous drag for bool
        else:
            # For int/float, start drag operation
            self.is_dragging = True
            self.drag_start_x = mouse_x
            self.drag_start_value = self.current_value
            return True

    def update_drag(self, mouse_x, mouse_y, context, shift_held=False):
        """Update property value during drag."""
        if not self.is_dragging or self.property_type == "bool":
            return

        # Calculate drag distance
        drag_distance = mouse_x - self.drag_start_x

        # Apply shift modifier for finer control
        speed_multiplier = 0.1 if shift_held else 1.0

        # Convert to value change based on type and decimal speed
        if self.property_type == "int":
            # For int: each 10 pixels = 1 unit
            value_change = (drag_distance / 10.0) * self.decimal_speed * speed_multiplier
            new_value = self.drag_start_value + value_change
            # Clamp to range and round to integer
            old_value = self.current_value
            self.current_value = max(self.value_range[0], min(self.value_range[1], int(round(new_value))))
        else:  # float
            # For float: each 20 pixels = 1.0 unit
            value_change = (drag_distance / 20.0) * self.decimal_speed * speed_multiplier
            new_value = self.drag_start_value + value_change
            # Clamp to range
            old_value = self.current_value
            self.current_value = max(self.value_range[0], min(self.value_range[1], new_value))

    def end_drag(self, context):
        """End dragging the property value."""
        self.is_dragging = False

    def draw(self, context, main_color, accent_color, operation_selector=None, intensity_handler=None):
        """Draw the property box (name on left, value on right)."""
        scale = get_dpi_scale()
        total_width, height, name_width, value_width = self.get_box_dimensions(
            scale, operation_selector, intensity_handler
        )

        # Add padding between name and value boxes
        padding = 8.0 * scale  # 8px padding

        # Calculate positions for both boxes
        # Name box: left aligned from property box center
        name_box_center_x = self.screen_x - (total_width - name_width) * 0.5

        # Value box: positioned to the right of name box with padding
        name_box_right_edge = name_box_center_x + name_width * 0.5
        value_box_center_x = name_box_right_edge + padding + value_width * 0.5

        # Draw name box (left side, non-interactive)
        self._draw_name_box(context, scale, name_box_center_x, self.screen_y, name_width, height, main_color)

        # Draw value box (right side, interactive)
        if self.property_type == "bool":
            self._draw_bool_value_box(
                context, scale, value_box_center_x, self.screen_y, value_width, height, main_color, accent_color
            )
        else:
            self._draw_numeric_value_box(
                context, scale, value_box_center_x, self.screen_y, value_width, height, main_color, accent_color
            )

    def _draw_name_box(self, context, scale, center_x, center_y, width, height, main_color):
        """Draw the name box (left side)."""
        # Apply current opacity to main color
        faded_color = (*main_color[:3], main_color[3] * self.current_opacity)

        # Draw box background
        vertices = [
            (center_x - width * 0.5, center_y - height * 0.5),
            (center_x + width * 0.5, center_y - height * 0.5),
            (center_x + width * 0.5, center_y + height * 0.5),
            (center_x - width * 0.5, center_y + height * 0.5),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(faded_color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

        # Draw text with faded opacity
        font_id = 0
        blf.size(font_id, int(9 * scale))
        text_width, text_height = blf.dimensions(font_id, self.display_name)

        # Center the text
        text_x = center_x - text_width * 0.5
        text_y = center_y - text_height * 0.5

        blf.position(font_id, text_x, text_y, 0)
        blf.color(font_id, 1.0, 1.0, 1.0, self.current_opacity)  # Apply opacity to text
        blf.draw(font_id, self.display_name)

    def _draw_bool_value_box(self, context, scale, center_x, center_y, width, height, main_color, accent_color):
        """Draw the boolean value box (square checkbox positioned half its width to the left of center)."""
        # Calculate checkbox size and position
        # Checkbox should be square (height x height) and positioned half its width to the left of center
        checkbox_size = height * 0.8  # Make it slightly smaller than the full height for padding
        checkbox_half_size = checkbox_size * 0.5

        # Position the checkbox half its width to the left of the center
        checkbox_center_x = center_x - checkbox_half_size

        # Choose colors based on state
        if self.is_hovered:
            if self.current_value:
                fill_color = (*accent_color[:3], accent_color[3] * self.current_opacity)
                border_color = (*accent_color[:3], accent_color[3] * self.current_opacity)
            else:
                fill_color = (*main_color[:3], 0.0)  # Transparent fill when false and hovered
                border_color = (*accent_color[:3], accent_color[3] * self.current_opacity)
        else:
            if self.current_value:
                fill_color = (
                    *accent_color[:3],
                    0.7 * self.current_opacity,
                )  # Slightly transparent when not hovered but true
                border_color = (*accent_color[:3], accent_color[3] * self.current_opacity)
            else:
                fill_color = (*main_color[:3], 0.0)  # Transparent fill when false
                border_color = (*accent_color[:3], accent_color[3] * self.current_opacity)

        # Draw fill if needed
        if fill_color[3] > 0.0:
            vertices = [
                (checkbox_center_x - checkbox_half_size, center_y - checkbox_half_size),
                (checkbox_center_x + checkbox_half_size, center_y - checkbox_half_size),
                (checkbox_center_x + checkbox_half_size, center_y + checkbox_half_size),
                (checkbox_center_x - checkbox_half_size, center_y + checkbox_half_size),
            ]

            indices = [(0, 1, 2), (0, 2, 3)]

            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

            gpu.state.blend_set("ALPHA")
            shader.bind()
            shader.uniform_float("color", ensure_alpha(fill_color))
            batch.draw(shader)
            gpu.state.blend_set("NONE")

        # Draw border
        border_vertices = [
            (checkbox_center_x - checkbox_half_size, center_y - checkbox_half_size),
            (checkbox_center_x + checkbox_half_size, center_y - checkbox_half_size),
            (checkbox_center_x + checkbox_half_size, center_y + checkbox_half_size),
            (checkbox_center_x - checkbox_half_size, center_y + checkbox_half_size),
            (checkbox_center_x - checkbox_half_size, center_y - checkbox_half_size),  # Close the loop
        ]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": border_vertices})

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(border_color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    def _draw_numeric_value_box(self, context, scale, center_x, center_y, width, height, main_color, accent_color):
        """Draw the numeric value box (int/float with text)."""
        # Choose color based on hover state and apply fade opacity
        if self.is_hovered or self.is_dragging:
            color = (*accent_color[:3], accent_color[3] * self.current_opacity)  # Apply opacity to accent color
        else:
            color = (*main_color[:3], main_color[3] * self.current_opacity)  # Apply opacity to main color

        # Draw box background
        vertices = [
            (center_x - width * 0.5, center_y - height * 0.5),
            (center_x + width * 0.5, center_y - height * 0.5),
            (center_x + width * 0.5, center_y + height * 0.5),
            (center_x - width * 0.5, center_y + height * 0.5),
        ]

        indices = [(0, 1, 2), (0, 2, 3)]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", ensure_alpha(color))
        batch.draw(shader)
        gpu.state.blend_set("NONE")

        # Draw text with faded opacity
        display_text = self.get_display_text()
        font_id = 0
        blf.size(font_id, int(9 * scale))
        text_width, text_height = blf.dimensions(font_id, display_text)

        # Center the text
        text_x = center_x - text_width * 0.5
        text_y = center_y - text_height * 0.5

        blf.position(font_id, text_x, text_y, 0)
        blf.color(font_id, 1.0, 1.0, 1.0, self.current_opacity)  # Apply opacity to text
        blf.draw(font_id, display_text)
