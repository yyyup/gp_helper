"""
ANIMATION SELECTION SETS GUI - Floating Panel Implementation
============================================================

PURPOSE:
This module implements the floating GUI for animation selection sets. It provides
a visual interface for creating, managing, and using selection sets in Blender's
animation workflow.

RESPONSIBILITIES:
1. **Drawing Logic**: Renders the selection sets buttons, grabber, and UI elements
2. **Event Handling**: Processes mouse interactions specific to selection sets
3. **Panel-Specific State**: Manages collapse state, set colors, and GUI dimensions
4. **Set Operations**: Handles selection, creation, and management of animation sets
5. **Visual Feedback**: Provides hover states, button highlighting, and visual cues

ARCHITECTURE:
- **Decoupled Design**: Uses floating_panels.py for positioning and modal behavior
- **Draw Callbacks**: Registers draw callbacks for rendering in Blender viewports
- **State Management**: Maintains only selection sets-specific state
- **Event Processing**: Handles mouse events for selection sets interactions

INTEGRATION WITH FLOATING PANELS:
- **Panel Name**: Registers as "selection_sets" with the floating panels system
- **Shared State**: Uses floating_panels.gui_state for positioning and dragging
- **Independent Logic**: Maintains its own drawing and interaction logic
- **No Conflicts**: Avoids duplicating state managed by floating_panels

PANEL-SPECIFIC STATE:
```python
gui_state = {
    "collapsed": False,          # Whether the panel is collapsed
    "set_colors": {},           # Color assignments for sets
    "hovered_element": None,    # Which UI element is hovered
    # ... other selection sets specific state
}
```

SHARED STATE (from floating_panels):
```python
fp.gui_state = {
    "show_gui": False,          # Whether panel is visible
    "dragging_grabber": False,  # Whether grabber is being dragged
    "gui_position": (x, y),     # Current panel position
    # ... other shared positioning state
}
```

DRAWING PROCESS:
1. Check if panel should be drawn (fp.gui_state["show_gui"])
2. Get position from floating_panels region state system
3. Draw selection sets specific UI elements
4. Handle hover states and interactions
5. Update only selection sets specific state

EVENT HANDLING:
1. Receive mouse events from floating_panels modal operator
2. Process selection sets specific interactions (button clicks, etc.)
3. Use shared dragging state for grabber movement
4. Return True if event was handled, False otherwise

USAGE:
This module should not be called directly. Instead, use the floating_panels system:
```python
bpy.ops.wm.amp_floating_panels_tracker('INVOKE_DEFAULT',
                                       panel_name="selection_sets")
```
"""

import bpy
import gpu
import blf
import time
import traceback
import math
import json
from gpu_extras.batch import batch_for_shader

from ..utils.customIcons import get_icon
from ..utils import refresh_ui, dprint, get_prefs
from .. import __package__ as base_package

from . import floating_panels as fp

from ..utils.gui_pins.gui_roundedbox import (
    draw_rounded_box_xy,
    simple_box_collision,
)

# Constants - imported from floating_panels to maintain consistency
SUPPORTED_AREA_TYPES = fp.SUPPORTED_AREA_TYPES

# Panel-specific state for selection sets - only contains data unique to this panel
# All positioning, dragging, and modal state is managed by floating_panels
gui_state = {
    # Visual state specific to selection sets
    "set_colors": {},  # Color assignments for individual sets
    "last_hover_time": 0,  # For hover timing effects
    "mouse_over_gui": False,  # Whether mouse is over this panel's GUI
    # UI state specific to selection sets
    "current_region": None,  # Current region being drawn in
    "active_area_type": None,  # Type of area this panel is active in
    "target_area": None,  # Target area for operations
    "target_window": None,  # Target window for operations
    "has_dragged": False,  # Whether a drag operation has occurred
    "drag_start_pos": None,  # Starting position of drag (for selection sets specific logic)
    # Panel-specific collapse state (independent of other panels)
    "collapsed": False,  # Whether THIS panel is collapsed
}


# Debug state for tracking GUI system
debug_state = {
    "show_debug": True,  # Start with debug enabled by default
    "mouse_pos": (0, 0),
    "region_pos": (0, 0),
    "area_type": "Unknown",
    "region_type": "Unknown",
    "tracker_active": False,
    "gui_enabled": False,
    "preset_count": 0,
    "pinned_sets_count": 0,
    "draw_handlers_count": 0,
    "last_draw_time": 0,
}


# Global reference to the draw handler
draw_handler = None


def pinned_sets_draw_callback():
    """Draw callback for the floating selection sets GUI - uses centralized floating_panels system"""
    context = bpy.context
    if not context.area or not context.region:
        return

    # Only draw in the area that's currently being tracked
    area_id = str(context.area.as_pointer()) if context.area else "Unknown"
    if area_id != fp.tracker_data.get("area_id", "Unknown"):
        return

    # Only draw in supported area types with WINDOW regions
    if not fp.is_supported_area_type(context.area.type):
        return

    # Check if GUI should be displayed using the centralized system
    if not is_gui_visible():
        return

    try:
        # Get scene data
        scene = context.scene
        if not hasattr(scene, "amp_anim_set"):
            return

        scene_props = scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return

        preset = scene_props.presets[scene_props.active_preset_index]
        if not preset.sets:
            return

        # Get or create region state from the centralized system
        region_state = fp.get_stored_region_state(context, context.area, context.region, "selection_sets")
        if not region_state:
            # Create default state for new regions - initialize at 20,20
            region_state = fp.create_or_update_region_state(
                context, context.area, context.region, (20, 20), None, "selection_sets"
            )
            if not region_state:
                dprint("[DRAW_CALLBACK] Failed to create/get region state")
                return

        # Get GUI position from stored state using corner-based positioning
        gui_x, gui_y = fp.get_grabber_position_from_region_state(context, context.area, context.region, region_state)

        # Use region state's collapsed property (this is the actual collapse state)
        collapsed = region_state.collapsed if hasattr(region_state, "collapsed") else False

        # Calculate GUI dimensions
        dims = fp.get_scaled_gui_dimensions()
        gui_height = dims["height"]

        # Get pinned sets
        pinned_sets = [s for s in preset.sets if s.pinned]

        # Calculate total width needed
        total_width = fp.calculate_gui_width(preset, {"collapsed": collapsed})

        # Keep GUI within region bounds (only grabber dimensions are considered)
        gui_x, gui_y = fp.keep_gui_in_region(gui_x, gui_y, dims["grabber_width"], gui_height, context.region)

        # Update stored position if it was adjusted
        if gui_x != region_state.gui_position_x or gui_y != region_state.gui_position_y:
            fp.create_or_update_region_state(
                context, context.area, context.region, (gui_x, gui_y), None, "selection_sets"
            )

        # Draw grabber - always draw
        is_grabber_hovered = get_hovered_element() == "grabber"
        draw_grabber(
            gui_x,
            gui_y,
            dims["grabber_width"],
            gui_height,
            is_grabber_hovered,
            is_dragging_grabber(),
        )

        # Draw selection sets - show buttons when not collapsed
        should_draw_buttons = not collapsed and pinned_sets

        if should_draw_buttons and pinned_sets:
            # Determine horizontal and vertical alignment
            alignment = region_state.alignment if hasattr(region_state, "alignment") else "right"
            vert_align = getattr(region_state, "vertical_alignment", "bottom")

            # Get padding values from dimensions
            panel_width = dims["panel_width"]
            horizontal_pad = dims["horizontal_padding"]
            vertical_pad = dims["vertical_padding"]
            box_padding = dims["box_padding"]

            # Organize pinned sets by row
            rows = {}
            for idx, anim_set in enumerate(pinned_sets):
                row_idx = getattr(anim_set, "row", 1)
                rows.setdefault(row_idx, []).append((idx, anim_set))

            # Sort rows by row index (1 = top)
            sorted_rows = sorted(rows.items(), key=lambda x: x[0])
            # Number of rows and block height
            n_rows = len(sorted_rows)
            block_height = n_rows * gui_height + max(0, (n_rows - 1) * vertical_pad)

            # Compute block vertical positions relative to grabber with padding adjustment
            if vert_align == "bottom":
                # Panel above grabber: bottom aligns with grabber bottom, moved up by padding
                block_bottom = gui_y + box_padding
                block_top = block_bottom + block_height
            else:
                # Panel below grabber: top aligns with grabber top, moved down by padding
                block_top = gui_y + gui_height - box_padding
                block_bottom = block_top - block_height

            # Check if the overall button block is hovered (for opacity control)
            button_block_hovered = check_button_block_collision(
                context, gui_x, gui_y, dims, region_state, preset, collapsed
            )

            # Also check if grabber is hovered OR being dragged - if so, buttons should use hover alpha too
            is_grabber_hovered = fp.gui_state.get("hovered_element") == "grabber"
            is_grabber_dragging = fp.gui_state.get("dragging_grabber", False)
            button_block_hovered = button_block_hovered or is_grabber_hovered or is_grabber_dragging

            # Draw the button block background wrapper first
            draw_button_block_background(gui_x, gui_y, dims, region_state, preset, button_block_hovered)

            # Draw each row, row1 always at top of block
            for idx_row, (_, items) in enumerate(sorted_rows):
                items.sort(key=lambda tup: tup[1].priority)
                count = len(items)

                if count == 0:
                    continue

                # Width per button
                total_horizontal_pad = horizontal_pad * (count - 1)
                set_w = (panel_width - total_horizontal_pad) / count

                # Horizontal start based on alignment with padding adjustment
                if alignment == "left":
                    start_x = gui_x - panel_width - horizontal_pad - box_padding
                else:
                    start_x = gui_x + dims["grabber_width"] + horizontal_pad + box_padding

                # Compute Y for this row: from block_top downward
                row_y = block_top - gui_height - idx_row * (gui_height + vertical_pad)
                # Draw buttons in this row
                cur_x = start_x
                for idx, anim_set in items:
                    hov = fp.gui_state.get("hovered_element") == idx
                    # Use button_block_hovered to determine overall opacity
                    draw_selection_set(cur_x, row_y, set_w, gui_height, anim_set, hov, button_block_hovered)
                    cur_x += set_w + horizontal_pad

    except Exception as e:
        dprint(f"[DRAW_CALLBACK] Error in pinned_sets_draw_callback: {e}")
        import traceback

        traceback.print_exc()


def pinned_sets_event_handler(context, event):
    """Event handler for the floating selection sets GUI using floating panels tracker"""
    # Check if GUI should be displayed in this region
    if not context.area or not context.region:
        return False

    if not fp.should_display_gui_in_region(context, context.area, context.region):
        return False

    try:
        # Get tracker data from floating panels system
        tracker_data = fp.get_tracker_data(context)
        if not tracker_data:
            return False

        scene = bpy.context.scene
        scene_props = scene.amp_anim_set

        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return False

        preset = scene_props.presets[scene_props.active_preset_index]

        # Get region state from scene properties
        region_state = fp.get_stored_region_state(context, context.area, context.region, "selection_sets")
        if not region_state:
            return False

        # Use region mouse coordinates from tracker
        mouse_x = tracker_data["region_pos"][0]
        mouse_y = tracker_data["region_pos"][1]

        # Get GUI position from stored state using corner-based positioning
        gui_x, gui_y = fp.get_grabber_position_from_region_state(context, context.area, context.region, region_state)

        # Use region state's collapsed property (this is the actual collapse state)
        collapsed = region_state.collapsed if hasattr(region_state, "collapsed") else False

        # Calculate dimensions
        dims = fp.get_scaled_gui_dimensions()
        gui_height = dims["height"]
        total_width = fp.calculate_gui_width(preset, {"collapsed": collapsed})

        # Handle mouse events using tracker data
        if event.type == "MOUSEMOVE":
            # Store previous hover state for comparison
            prev_hovered = fp.gui_state.get("hovered_element")

            # Check hover states for all interactive elements
            set_hovered_element(None)

            # Check grabber hover
            grabber_hovered = simple_box_collision(gui_x, gui_y, dims["grabber_width"], gui_height, mouse_x, mouse_y)
            if grabber_hovered:
                set_hovered_element("grabber")

            # Check selection set button hovers if not collapsed
            elif not collapsed:
                pinned_sets = [s for s in preset.sets if s.pinned]
                if pinned_sets:
                    # Compute button boxes for collision detection
                    button_boxes = fp.compute_button_boxes(gui_x, gui_y, dims, region_state, preset)

                    # Check each button for hover
                    for idx, box_x, box_y, box_width, box_height in button_boxes:
                        if simple_box_collision(box_x, box_y, box_width, box_height, mouse_x, mouse_y):
                            set_hovered_element(idx)
                            break

            # Debug output when hover state changes
            current_hovered = fp.gui_state.get("hovered_element")
            if current_hovered != prev_hovered:
                dprint(f"[HOVER] State changed: {prev_hovered} -> {current_hovered}")

            # Force redraw to update hover state
            context.area.tag_redraw()

        elif event.type == "LEFTMOUSE" and event.value == "PRESS":
            # Check for clicks on UI elements

            # Check grabber click first
            grabber_hovered = simple_box_collision(gui_x, gui_y, dims["grabber_width"], gui_height, mouse_x, mouse_y)
            if grabber_hovered:
                # Handle grabber click (start dragging)
                fp.gui_state["dragging_grabber"] = True
                fp.gui_state["drag_offset"] = (mouse_x - gui_x, mouse_y - gui_y)
                return True

            # Check selection set clicks if not collapsed
            elif not collapsed:
                pinned_sets = [s for s in preset.sets if s.pinned]
                if pinned_sets:
                    # Compute button boxes for collision detection
                    button_boxes = fp.compute_button_boxes(gui_x, gui_y, dims, region_state, preset)

                    # Check each button for clicks
                    for idx, box_x, box_y, box_width, box_height in button_boxes:
                        if simple_box_collision(box_x, box_y, box_width, box_height, mouse_x, mouse_y):
                            # Handle selection set click
                            fp.handle_selection_set_click(context, idx, event)
                            return True

        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            # End dragging
            if fp.gui_state.get("dragging_grabber", False):
                fp.gui_state["dragging_grabber"] = False
                return True

        elif event.type == "MOUSEMOVE" and fp.gui_state.get("dragging_grabber", False):
            # Handle grabber dragging
            dims = fp.get_scaled_gui_dimensions()
            offset_x, offset_y = fp.gui_state.get("drag_offset", (0, 0))
            new_x = mouse_x - offset_x
            new_y = mouse_y - offset_y

            # Keep within region bounds (only grabber dimensions are considered)
            new_x, new_y = fp.keep_gui_in_region(new_x, new_y, dims["grabber_width"], gui_height, context.region)

            # Update stored position
            fp.create_or_update_region_state(
                context, context.area, context.region, (new_x, new_y), None, "selection_sets"
            )
            return True

        return False

    except Exception as e:
        dprint(f"[EVENT_HANDLER] Error in pinned_sets_event_handler: {e}")
        import traceback

        traceback.print_exc()
        return False


def view3d_draw_handler(dummy, context):
    """Draw handler for 3D viewport"""
    pinned_sets_draw_callback()


def view3d_event_handler(context, event):
    """Event handler for 3D viewport"""
    return pinned_sets_event_handler(context, event)


def register_gui():
    """Register GUI components with the centralized floating panels system"""
    global draw_handler

    # Register with the floating panels system
    register_selection_sets_panel()

    dprint("Selection sets GUI registered with centralized floating panels system")


def unregister_gui():
    """Unregister GUI components from the centralized floating panels system"""
    global draw_handler

    # Unregister from the floating panels system
    unregister_selection_sets_panel()

    # Stop the GUI
    gui_state["collapsed"] = False  # Reset panel-specific state

    draw_handler = None
    dprint("Selection sets GUI unregistered from centralized floating panels system")


def update_display_gui(scene_props, context):
    """Update the display GUI state using centralized floating panels system"""
    dprint(f"[UPDATE_GUI] Called with display_gui={scene_props.display_gui}")

    # Set global visibility state in floating panels
    fp.gui_state["show_gui"] = scene_props.display_gui

    # Start or ensure tracker is running if GUI is enabled
    if scene_props.display_gui:
        if not fp.is_tracker_active(context):
            fp.ensure_tracker_running(context)
            dprint("[UPDATE_GUI] Started floating panels tracker")
        else:
            dprint("[UPDATE_GUI] Floating panels tracker already active")

    # Force redraw of all areas to show/hide GUI
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if fp.is_supported_area_type(area.type):
                area.tag_redraw()

    dprint(f"[UPDATE_GUI] Updated GUI visibility: {fp.gui_state['show_gui']}")


def toggle_region_gui(context):
    """Toggle GUI for the current region and start mouse tracking"""
    if not context.area:
        dprint("[TOGGLE] No active area")
        return

    # Check if the area type is supported
    if not fp.is_supported_area_type(context.area.type):
        dprint(f"[TOGGLE] Unsupported area type: {context.area.type}")
        return

    # Enable global GUI state in floating panels
    fp.gui_state["show_gui"] = True

    # Enable scene property
    scene = bpy.context.scene
    if hasattr(scene, "amp_anim_set"):
        scene.amp_anim_set.display_gui = True

    # Start floating panels tracker if not already running
    if not fp.is_tracker_active(context):
        fp.ensure_tracker_running(context)
        dprint("[TOGGLE] Started floating panels tracker")

    context.area.tag_redraw()
    dprint("[TOGGLE] GUI enabled for region")


def draw_grabber(x, y, width, height, is_hovered, is_dragging):
    """
    Draw the grabber handle using rounded box with square grip indicators

    Args:
        x, y: Position
        width, height: Dimensions
        is_hovered: Whether mouse is over grabber
        is_dragging: Whether grabber is being dragged
    """

    dims = fp.get_scaled_gui_dimensions()
    grabber_corner_radius = dims["grabber_corner_radius"]  # Fixed radius for grabber
    corner_segments = dims["corner_segments"]

    # Get preference colors using centralized color function
    prefs = get_prefs()
    color = fp.get_grabber_color(prefs, is_hovered, is_dragging)

    # Calculate inverted border color for contrast with same alpha as fill
    border_color = fp.get_offset_color(color, color[3], 0.3)

    # Draw rounded box for grabber or simple rectangle if corner_radius is 0
    if grabber_corner_radius > 0:
        # Adjust box dimensions to account for corner radius to keep overall size consistent
        # The corner centers need to be inset by the radius to keep the box within bounds
        adjusted_x = x + grabber_corner_radius
        adjusted_y = y + grabber_corner_radius
        adjusted_width = width - 2 * grabber_corner_radius
        adjusted_height = height - 2 * grabber_corner_radius

        # Only draw rounded corners if we have enough space
        if adjusted_width > 0 and adjusted_height > 0:
            # Calculate border width based on show_border preference and GUI scale
            prefs = get_prefs()

            border_width = 1.0

            success = draw_rounded_box_xy(
                adjusted_x,
                adjusted_y,
                adjusted_width,
                adjusted_height,
                border_color,
                color,
                border_width,
                grabber_corner_radius,
                corner_segments,
            )
        else:
            success = False  # Fall back to rectangle if too small for corners
    else:
        success = False  # Force fallback to rectangle

    if not success:
        # Fallback: draw simple rectangle with border using helper
        # Get border scaling for consistent appearance
        prefs = get_prefs()
        border_width = 1.0
        draw_simple_rectangle(x, y, width, height, color, border_color, border_width)

    # Draw three small square grip indicators with shadows
    # Calculate square positions (vertically centered, evenly spaced)
    # Get DPI and GUI scale for proper scaling
    dpi_scale = fp.get_dpi_scale()
    prefs = get_prefs()
    gui_scale = prefs.fp_scale if prefs else 1.0
    combined_scale = dpi_scale * gui_scale

    # Scale the square size and shadow offset with DPI and GUI scale
    base_square_size = 2.0  # Base size in pixels
    max_square_size = width * 0.25  # Maximum size relative to grabber width
    square_size = min(base_square_size * combined_scale, max_square_size)

    # Scale shadow offset with combined scale, but ensure minimum visibility
    shadow_offset = max(0.5, 0.5 * combined_scale)

    center_x = x + width / 2
    spacing = height / 4
    start_y = y + spacing

    # Shadow color (black)
    shadow_color = (0.0, 0.0, 0.0, 0.8)

    # Use border color for squares
    square_color = border_color

    for i in range(3):
        square_y = start_y + i * spacing

        # Draw shadow first (scaled offset to right and down)
        draw_square(center_x + shadow_offset, square_y - shadow_offset, square_size, shadow_color)

        # Draw main square above shadow
        draw_square(center_x, square_y, square_size, square_color)


def draw_square(center_x, center_y, size, color):
    """
    Draw a simple square

    Args:
        center_x, center_y: Square center
        size: Square size (width and height)
        color: RGBA color tuple
    """
    try:
        half_size = size * 0.5
        coords = [
            (center_x - half_size, center_y - half_size),
            (center_x + half_size, center_y - half_size),
            (center_x + half_size, center_y + half_size),
            (center_x - half_size, center_y + half_size),
        ]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": coords})
        shader.bind()
        shader.uniform_float("color", color)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)
        gpu.state.blend_set("NONE")

    except Exception as e:
        dprint(f"[DRAW_SQUARE] Error drawing square: {e}")


def check_button_block_collision(context, gui_x, gui_y, dims, region_state, preset, collapsed=False):
    """
    Check if mouse is over the entire button block area.
    This is used for overall hover detection to control opacity.
    """

    # Skip collision detection when grabber is collapsed (buttons are not visible)
    if collapsed:
        return False
    # Only process hover states when mouse is in a valid region
    if not fp.is_mouse_in_valid_region():
        return False

    # Get mouse position in region coordinates
    mouse_x, mouse_y = fp.tracker_data.get("region_pos", (0, 0))

    # Calculate button block bounds using centralized function
    block_bounds = fp.calculate_button_block_bounds(gui_x, gui_y, dims, region_state, preset)
    if not block_bounds:
        return False

    block_x, block_y, block_width, block_height = block_bounds

    # Simple box collision for the entire block
    return simple_box_collision(block_x, block_y, block_width, block_height, mouse_x, mouse_y)


def draw_button_block_background(gui_x, gui_y, dims, region_state, preset, is_hovered):
    """
    Draw the background wrapper for all selection set buttons.
    This provides a unified background that can be controlled by preferences.
    """
    prefs = get_prefs()
    if not prefs:
        return

    # Calculate button block bounds using centralized function
    block_bounds = fp.calculate_button_block_bounds(gui_x, gui_y, dims, region_state, preset)
    if not block_bounds:
        return

    block_x, block_y, block_width, block_height = block_bounds

    # Get preference values
    show_background = prefs.fp_show_background if prefs else True
    box_padding = dims["box_padding"]

    # Only draw background if enabled
    if not show_background:
        return

    # Use same corner radius as buttons, but add padding since padding is now outward
    corner_radius = dims["corner_radius"] + box_padding
    corner_segments = dims["corner_segments"]

    # Get background color using centralized color function
    fill_color = fp.get_button_background_color(prefs, is_hovered)

    # Border color using inverted color for contrast
    border_color = fp.get_offset_color(fill_color, fill_color[3], 0.3)

    # Draw rounded box for background
    if corner_radius > 0:
        # Clamp corner radius to half the minimum dimension
        min_dimension = min(block_width, block_height)
        clamped_corner_radius = min(corner_radius, min_dimension / 2)

        # Adjust box dimensions to account for corner radius
        adjusted_x = block_x + clamped_corner_radius
        adjusted_y = block_y + clamped_corner_radius
        adjusted_width = block_width - 2 * clamped_corner_radius
        adjusted_height = block_height - 2 * clamped_corner_radius

        # Only draw rounded corners if we have enough space
        if adjusted_width > 0 and adjusted_height > 0:

            border_width = 1.0

            success = draw_rounded_box_xy(
                adjusted_x,
                adjusted_y,
                adjusted_width,
                adjusted_height,
                border_color,
                fill_color,
                border_width,
                clamped_corner_radius,
                corner_segments,
            )
        else:
            success = False  # Fall back to rectangle if too small for corners
    else:
        success = False  # Force fallback to rectangle

    if not success:
        # Fallback: draw simple rectangle using helper
        # Get border scaling for consistent appearance
        prefs = get_prefs()
        border_width = 1.0
        draw_simple_rectangle(block_x, block_y, block_width, block_height, fill_color, border_color, border_width)


def draw_selection_set(x, y, width, height, anim_set, is_hovered, any_hovered=False):
    """
    Draw a selection set button using rounded box

    Args:
        x, y: Position
        width, height: Dimensions
        anim_set: The animation set data
        is_hovered: Whether mouse is over this set
        any_hovered: Whether any button is being hovered in this area
    """
    prefs = get_prefs()
    dims = fp.get_scaled_gui_dimensions()
    corner_radius = dims["corner_radius"]
    corner_segments = dims["corner_segments"]

    # Get preference values
    show_background = prefs.fp_show_colors if prefs else True
    show_border = prefs.fp_show_border if prefs else True

    # Clamp corner radius to half the button height to prevent overlap
    button_corner_radius = min(corner_radius, height / 2)

    # Always draw background for collision detection (even if colors are hidden)
    if show_background:
        # Get set color
        base_color = anim_set.color if hasattr(anim_set, "color") else (0.5, 0.5, 0.5)
        saturation = prefs.fp_button_color_saturation if prefs else 0.5
        darkness = prefs.fp_button_color_darkness if prefs else 0.5

        # Determine alpha based on hover state
        if prefs:
            if any_hovered:
                alpha = prefs.fp_hoover_alpha
            else:
                alpha = prefs.fp_default_alpha
            text_color = prefs.fp_text_color
        else:
            # Fallback values
            alpha = 1.0 if any_hovered else 0.8
            text_color = (1.0, 1.0, 1.0, alpha)

        # Apply color processing based on hover state
        if is_hovered:
            # When hovering: brighter version of the color
            fill_color = fp.desaturate_color(fp.darken_color(base_color, alpha, darkness), alpha, saturation)
        else:
            # Default: moderate darkness with visible color
            fill_color = fp.desaturate_color(fp.darken_color(base_color, alpha, darkness * 0.8), alpha, saturation)

        # Apply alpha to the fill color
        fill_color = (fill_color[0], fill_color[1], fill_color[2], alpha)

        # Border color - always draw border but with different colors based on preference
        if show_border:
            # When border is enabled: use derived/offset color for contrast but preserve alpha
            border_color = fp.darken_color(fill_color, alpha, 0.4)
        else:
            # When border is disabled: use same color as background but preserve alpha for consistency
            border_color = (fill_color[0], fill_color[1], fill_color[2], alpha)

        # Draw rounded box for selection set or simple rectangle if corner_radius is 0
        if button_corner_radius > 0:
            # Adjust box dimensions to account for corner radius to keep overall size consistent
            # The corner centers need to be inset by the radius to keep the box within bounds
            adjusted_x = x + button_corner_radius
            adjusted_y = y + button_corner_radius
            adjusted_width = width - 2 * button_corner_radius
            adjusted_height = height - 2 * button_corner_radius

            # Only draw rounded corners if we have enough space
            if adjusted_width > 0 and adjusted_height > 0:
                border_width = 1.0
                success = draw_rounded_box_xy(
                    adjusted_x,
                    adjusted_y,
                    adjusted_width,
                    adjusted_height,
                    border_color,
                    fill_color,
                    border_width,
                    button_corner_radius,
                    corner_segments,
                )
            else:
                success = False  # Fall back to rectangle if too small for corners
        else:
            success = False  # Force fallback to rectangle

        if not success:

            border_width = 1.0
            draw_simple_rectangle(x, y, width, height, fill_color, border_color, border_width)
    else:
        # When colors are disabled, draw buttons in grey
        if prefs:
            if any_hovered:
                alpha = prefs.fp_hoover_alpha
            else:
                alpha = prefs.fp_default_alpha
            text_color = tuple(prefs.fp_text_color) + (alpha,)
        else:
            alpha = 1.0 if any_hovered else 0.8
            text_color = (1.0, 1.0, 1.0, alpha)

        # Grey background when colors are disabled
        if is_hovered:
            base_color = (0.3, 0.3, 0.3)  # Lighter grey when hovered
        else:
            base_color = (0.2, 0.2, 0.2)  # Default grey

        fill_color = (base_color[0], base_color[1], base_color[2], alpha)

        # Border color - always draw border but with different colors based on preference
        if show_border:
            # When border is enabled: use derived/offset color for contrast with proper alpha
            border_color = fp.get_offset_color(fill_color, alpha, 0.3)
        else:
            # When border is disabled: use same color as background but preserve alpha for consistency
            border_color = (fill_color[0], fill_color[1], fill_color[2], alpha)

        # Draw rounded box for selection set or simple rectangle if corner_radius is 0
        if button_corner_radius > 0:
            # Adjust box dimensions to account for corner radius to keep overall size consistent
            adjusted_x = x + button_corner_radius
            adjusted_y = y + button_corner_radius
            adjusted_width = width - 2 * button_corner_radius
            adjusted_height = height - 2 * button_corner_radius

            # Only draw rounded corners if we have enough space
            if adjusted_width > 0 and adjusted_height > 0:
                border_width = 1.0

                success = draw_rounded_box_xy(
                    adjusted_x,
                    adjusted_y,
                    adjusted_width,
                    adjusted_height,
                    border_color,
                    fill_color,
                    border_width,
                    button_corner_radius,
                    corner_segments,
                )
            else:
                success = False  # Fall back to rectangle if too small for corners
        else:
            success = False  # Force fallback to rectangle

        if not success:
            border_width = 1.0
            draw_simple_rectangle(x, y, width, height, fill_color, border_color, border_width)

    # Draw text if available
    if anim_set.name:
        try:
            # Set font size based on row height - scale from 60% to 80% of height
            font_size = max(8, min(24, int(height * 0.5)))

            # Calculate text position (centered)
            text_x = x + width / 2
            text_y = y + height / 2 - font_size / 2

            # Get text dimensions and center it
            text_width = fp.get_text_dimensions(anim_set.name, font_size)[0]
            text_x = x + (width - text_width) / 2

            # Draw text with shadow using helper function
            # text color should always premultiplied by the alpha value
            if len(text_color) == 4:
                text_color = (text_color[0], text_color[1], text_color[2], text_color[3] * alpha)
            draw_text_with_shadow(anim_set.name, text_x, text_y, font_size, text_color)

        except Exception as e:
            dprint(f"[DRAW_SET] Error drawing text: {e}")


def draw_simple_rectangle(x, y, width, height, fill_color, border_color=None, border_width=1.0):
    """
    Helper function to draw a simple rectangle with optional border.

    Args:
        x, y: Position
        width, height: Dimensions
        fill_color: RGBA color tuple for fill
        border_color: Optional RGBA color tuple for border
        border_width: Width of border (default 1.0)
    """
    try:
        # Draw fill
        coords = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": coords})
        shader.bind()
        shader.uniform_float("color", fill_color)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)
        gpu.state.blend_set("NONE")

        # Draw border if specified
        if border_color:
            # Set line width for the border
            if border_width > 1.0:
                gpu.state.line_width_set(border_width)

            border_coords = [(x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y)]
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(shader, "LINE_STRIP", {"pos": border_coords})
            shader.bind()
            shader.uniform_float("color", border_color)
            # Use inverted blending for better contrast
            gpu.state.blend_set("ALPHA_PREMULT")
            batch.draw(shader)
            gpu.state.blend_set("NONE")

            # Reset line width to default
            if border_width > 1.0:
                gpu.state.line_width_set(1.0)
    except Exception as e:
        dprint(f"[DRAW_RECT] Error drawing rectangle: {e}")


def draw_text_with_shadow(text, x, y, font_size, text_color, shadow_color=(0.0, 0.0, 0.0, 0.5)):
    """
    Helper function to draw text with shadow and proper alpha handling.

    Args:
        text: Text string to draw
        x, y: Position
        font_size: Font size
        text_color: RGBA color tuple for text
        shadow_color: RGBA color tuple for shadow (default black with 0.5 alpha)
    """
    try:
        # Enable alpha blending for text rendering
        gpu.state.blend_set("ALPHA")

        # Set font size
        blf.size(0, font_size)

        # Calculate shadow offset based on font size
        shadow_offset = max(1, int(font_size * 0.05))

        # Calculate shadow alpha as 0.8 of text alpha
        text_alpha = text_color[3] if len(text_color) == 4 else 1.0
        shadow_alpha = text_alpha * 0.8

        # Draw shadow first (offset by shadow_offset pixels)
        blf.position(0, x + shadow_offset, y - shadow_offset, 0)
        blf.color(0, shadow_color[0], shadow_color[1], shadow_color[2], shadow_alpha)
        blf.draw(0, text)

        # Draw main text
        blf.position(0, x, y, 0)
        if len(text_color) == 4:
            blf.color(0, text_color[0], text_color[1], text_color[2], text_color[3])
        else:
            blf.color(0, text_color[0], text_color[1], text_color[2], 1.0)
        blf.draw(0, text)

        # Disable alpha blending
        gpu.state.blend_set("NONE")

    except Exception as e:
        dprint(f"[DRAW_TEXT] Error drawing text with shadow: {e}")
        # Ensure blend state is reset even if there's an error
        try:
            gpu.state.blend_set("NONE")
        except:
            pass


# =============================================================================
# COMPATIBILITY FUNCTIONS - Interface with floating_panels system
# =============================================================================


def is_dragging_grabber():
    """Check if grabber is being dragged - delegates to floating_panels"""
    return fp.gui_state.get("dragging_grabber", False)


def get_hovered_element():
    """Get currently hovered element - delegates to floating_panels"""
    return fp.gui_state.get("hovered_element", None)


def set_hovered_element(element):
    """Set currently hovered element - delegates to floating_panels"""
    fp.gui_state["hovered_element"] = element


def get_drag_offset():
    """Get drag offset - delegates to floating_panels"""
    return fp.gui_state.get("drag_offset", (0, 0))


def is_gui_visible():
    """Check if GUI should be visible - uses panel registry"""
    return fp.is_panel_visible("selection_sets")


# =============================================================================
# PANEL REGISTRY INTEGRATION - Register with floating_panels system
# =============================================================================


def should_be_visible():
    """Check if selection sets panel should be visible"""
    # Check if GUI is enabled globally
    if not fp.gui_state.get("show_gui", False):
        return False

    # Check if we have valid scene data
    scene = bpy.context.scene
    if not hasattr(scene, "amp_anim_set"):
        return False

    scene_props = scene.amp_anim_set
    if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
        return False

    preset = scene_props.presets[scene_props.active_preset_index]
    if not preset.sets:
        return False

    # Check if we have pinned sets
    pinned_sets = [s for s in preset.sets if s.pinned]
    return len(pinned_sets) > 0


def register_selection_sets_panel():
    """Register selection sets panel with floating_panels system"""
    fp.register_panel(
        panel_name="selection_sets",
        draw_callback=pinned_sets_draw_callback,
        event_handler=pinned_sets_event_handler,
        get_visibility_func=should_be_visible,
        panel_specific_state=gui_state,
    )
    dprint("[SELECTION_SETS] Registered with floating panels system")


def unregister_selection_sets_panel():
    """Unregister selection sets panel from floating_panels system"""
    fp.unregister_panel("selection_sets")
    dprint("[SELECTION_SETS] Unregistered from floating panels system")
