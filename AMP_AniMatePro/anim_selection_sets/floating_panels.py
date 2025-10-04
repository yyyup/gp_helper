"""
FLOATING PANELS SYSTEM - Central Management for All Floating UI Panels
=====================================================================

PURPOSE:
This module provides a centralized system for managing floating panels in Blender.
It handles mouse tracking, panel positioning, modal operations, and shared GUI state
across all floating panels in the addon.

RESPONSIBILITIES:
1. **Mouse Tracking**: Global mouse position tracking across all Blender areas
2. **Panel Management**: Centralized positioning, alignment, and state management
3. **Modal Operations**: Panel behavior for all panels
4. **Draw Handler Management**: Ensuring proper draw handlers for all areas
5. **Region State Management**: Corner-based positioning system for panels
6. **Shared State**: Common GUI state that all panels can access

ARCHITECTURE:
- **Central State**: `gui_state` dictionary contains shared state for all panels
- **Tracker Data**: `tracker_data` tracks current mouse position and area information
- **Panel Registration**: Individual panels register with this system using panel_name
- **Decoupled Design**: Each panel handles its own drawing logic while using shared positioning

PANEL REQUIREMENTS:
Any panel that wants to use this system must:
1. Register with a unique panel_name (e.g., "selection_sets", "transforms", etc.)
2. Handle its own drawing logic in its own module
3. Use the shared positioning and state from this system
4. Not maintain duplicate state that conflicts with the central system

USAGE:
```python
# To show a panel:
bpy.ops.wm.amp_floating_panels_tracker('INVOKE_DEFAULT',
                                       panel_name="selection_sets")
```

STATE MANAGEMENT:
- **Global State**: Managed here for positioning, dragging, alignment
- **Panel-Specific State**: Managed in individual panel modules
- **No Duplication**: Each piece of state has a single source of truth

SUPPORTED PANEL TYPES:
- Selection Sets (selection_sets)
- Transforms (transforms) - planned
- Other floating panels as needed

MODAL BEHAVIOR:
- **Panel stays visible, can be dragged, remembers position**
- **Consistent**: All panels use the same modal behavior patterns
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from ..utils import dprint, get_prefs

from ..utils.gui_pins.gui_roundedbox import (
    simple_box_collision,
)

# Constants
SUPPORTED_AREA_TYPES = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
EXCLUDED_REGION_TYPES = {"HEADER", "TOOL_HEADER", "UI", "TOOLS", "PREVIEW"}

# Global state for mouse tracking - simplified like simple_global_tracker
default_tracker_data = {
    "window_pos": (0, 0),
    "region_pos": (0, 0),
    "area_type": "Unknown",
    "region_type": "Unknown",
    "area_id": "Unknown",
    "region_id": "Unknown",
    "screen": None,
    "debug_info": "",
    "show_debug": False,
    "last_valid_area_id": "Unknown",
}
tracker_data = default_tracker_data.copy()

# Store current draw handler per area: mapping area_id -> (area, space, handler)
_draw_handlers = {}

# Store active modal operator instance
_active_modal = None

# Global GUI state
gui_state = {
    "show_gui": False,
    "show_pinned_gui": False,  # Added for compatibility with selection sets
    "dragging_grabber": False,
    "drag_offset": (0, 0),
    "gui_position": (150, 50),
    "hovered_element": None,
    "drag_area_id": "",
    "collapsed": False,
    "alignment": "right",
    "drag_started": False,
}


# =============================================================================
# UTILITY FUNCTIONS - Area and region type validation
# =============================================================================


def is_supported_area_type(area_type):
    """Check if area type is supported for floating panels."""
    return area_type in SUPPORTED_AREA_TYPES


def is_valid_region_type(region_type):
    """Check if region type is valid (not excluded) for floating panels."""
    return region_type == "WINDOW" and region_type not in EXCLUDED_REGION_TYPES


def is_area_and_region_valid(area_type, region_type):
    """Check if both area type and region type are valid for floating panels."""
    return is_supported_area_type(area_type) and is_valid_region_type(region_type)


def is_mouse_in_valid_region():
    """Check if mouse is currently in a valid region for GUI operations."""
    region_type = tracker_data.get("region_type", "Unknown")
    area_type = tracker_data.get("area_type", "Unknown")
    return is_area_and_region_valid(area_type, region_type)


# =============================================================================
# CORNER POSITION FUNCTIONS - For region-based positioning
# =============================================================================


def get_corner_position(region, corner_type):
    """Get the absolute position of a corner in a region"""
    if not region:
        return (0, 0)

    if corner_type == "top_left":
        return (0, region.height)
    elif corner_type == "top_right":
        return (region.width, region.height)
    elif corner_type == "bottom_left":
        return (0, 0)
    elif corner_type == "bottom_right":
        return (region.width, 0)
    else:
        return (region.width, 0)  # Default to bottom_right


def find_closest_corner(region, x, y):
    """Find the closest corner to the given position and return corner type and distances"""
    if not region:
        return "bottom_right", 50, 50

    corners = {
        "top_left": (0, region.height),
        "top_right": (region.width, region.height),
        "bottom_left": (0, 0),
        "bottom_right": (region.width, 0),
    }

    closest_corner = None
    min_distance = float("inf")

    for corner_type, (cx, cy) in corners.items():
        distance = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            closest_corner = corner_type

    if closest_corner:
        cx, cy = corners[closest_corner]
        # Calculate distances based on corner type
        if closest_corner == "top_left":
            dist_x = x - cx  # Distance to the right
            dist_y = cy - y  # Distance down
        elif closest_corner == "top_right":
            dist_x = cx - x  # Distance to the left
            dist_y = cy - y  # Distance down
        elif closest_corner == "bottom_left":
            dist_x = x - cx  # Distance to the right
            dist_y = y - cy  # Distance up
        elif closest_corner == "bottom_right":
            dist_x = cx - x  # Distance to the left
            dist_y = y - cy  # Distance up
        else:
            dist_x = abs(x - cx)
            dist_y = abs(y - cy)

        return closest_corner, max(0, int(dist_x)), max(0, int(dist_y))

    return "bottom_right", 50, 50


def constrain_distances_to_quadrant(region, corner_type, dist_x, dist_y):
    """
    Constrain corner distances to ensure grabber stays within its quadrant.
    This prevents grabbers from appearing in wrong quadrants when restoring
    to smaller viewports.

    Args:
        region: The region to constrain within
        corner_type: The corner type (top_left, top_right, bottom_left, bottom_right)
        dist_x: Horizontal distance from corner
        dist_y: Vertical distance from corner

    Returns:
        tuple: (constrained_dist_x, constrained_dist_y)
    """
    if not region:
        return dist_x, dist_y

    # Limit distances to half the region dimensions to keep within quadrant
    max_dist_x = region.width // 2
    max_dist_y = region.height // 2

    # Clamp distances
    constrained_dist_x = min(dist_x, max_dist_x)
    constrained_dist_y = min(dist_y, max_dist_y)

    return constrained_dist_x, constrained_dist_y


def calculate_position_from_corner(region, corner_type, dist_x, dist_y):
    """Calculate absolute position from corner type and distances

    Constrains distances to ensure grabber stays within its quadrant:
    - X distance is limited to half the region width
    - Y distance is limited to half the region height
    This ensures the grabber remains in the correct quadrant when restoring to smaller windows.
    """
    if not region:
        return (50, 50)

    # Constrain distances to ensure grabber stays within its quadrant
    constrained_dist_x, constrained_dist_y = constrain_distances_to_quadrant(region, corner_type, dist_x, dist_y)

    corner_x, corner_y = get_corner_position(region, corner_type)

    if corner_type == "top_left":
        return (corner_x + constrained_dist_x, corner_y - constrained_dist_y)
    elif corner_type == "top_right":
        return (corner_x - constrained_dist_x, corner_y - constrained_dist_y)
    elif corner_type == "bottom_left":
        return (corner_x + constrained_dist_x, corner_y + constrained_dist_y)
    elif corner_type == "bottom_right":
        return (corner_x - constrained_dist_x, corner_y + constrained_dist_y)
    else:
        return (corner_x - constrained_dist_x, corner_y + constrained_dist_y)


def get_region_key(area, region):
    """Get a unique key for a specific region in an area - now uses WINDOW region ID only"""
    if not area or not region:
        return None

    # Find the WINDOW region in this area for stable identification
    window_region = get_window_region_from_area(area)
    if not window_region:
        return None

    # Use only the WINDOW region ID for stability across area changes
    return f"{area.type}_{str(window_region.as_pointer())}"


def handle_selection_set_click(context, set_index, event):
    """Handle clicks on selection sets"""
    scene_props = context.scene.amp_anim_set
    if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
        return

    preset = scene_props.presets[scene_props.active_preset_index]

    # Trigger selection set operator with appropriate modifiers
    selection_mode = "REPLACE"
    if event.shift and not event.ctrl:
        selection_mode = "ADD"
    elif event.ctrl and not event.shift:
        selection_mode = "TOGGLE"

    # Call the selection operator
    bpy.ops.anim.amp_anim_set_select(set_index=set_index, selection_mode=selection_mode)


# Selection Sets Event Callbacks
def selection_set_click_callback(context, element_id, event_data):
    """Handle clicks on selection sets"""
    try:
        import json

        # Parse element data
        element = get_ui_element(context, element_id)
        if not element or not element.data:
            return False

        data = json.loads(element.data)
        set_index = data.get("set_index")

        if set_index is None:
            return False

        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return False

        # Determine selection mode based on modifiers
        selection_mode = "REPLACE"
        if event_data.get("shift") and not event_data.get("ctrl"):
            selection_mode = "ADD"
        elif event_data.get("ctrl") and not event_data.get("shift"):
            selection_mode = "TOGGLE"

        # Call the selection operator
        bpy.ops.anim.amp_anim_set_select(set_index=set_index, selection_mode=selection_mode)
        return True

    except Exception as e:
        dprint(f"Error in selection set click callback: {e}")
        return False


def grabber_click_callback(context, element_id, event_data):
    """Handle clicks on grabber - just return False to allow dragging"""
    return False  # Don't consume the event, allow dragging


def grabber_drag_callback(context, element_id, event_data):
    """Handle dragging of grabber"""
    try:
        import json

        # Parse element data to get region key
        element = get_ui_element(context, element_id)
        if not element or not element.data:
            return False

        data = json.loads(element.data)
        region_key = data.get("region_key")

        if not region_key:
            return False

        # Update GUI position if this is a drag event (not drag end)
        if not event_data.get("drag_end", False):
            mouse_pos = event_data.get("mouse_pos", (0, 0))
            drag_delta = event_data.get("drag_delta", (0, 0))

            # Calculate new position
            tracker_data = get_tracker_data(context)
            if tracker_data:
                # Get current region state
                region_state = get_stored_region_state(context, context.area, context.region, "selection_sets")
                if region_state:
                    # Calculate new position based on drag
                    new_x = region_state.gui_position_x + drag_delta[0]
                    new_y = region_state.gui_position_y + drag_delta[1]

                    # Keep within region bounds (only grabber dimensions are considered)
                    dims = get_scaled_gui_dimensions()
                    new_x, new_y = keep_gui_in_region(
                        new_x, new_y, dims["grabber_width"], dims["height"], context.region
                    )

                    # Update stored position
                    create_or_update_region_state(
                        context, context.area, context.region, (new_x, new_y), None, "selection_sets"
                    )

                    # Force redraw
                    context.area.tag_redraw()

        return True

    except Exception as e:
        dprint(f"Error in grabber drag callback: {e}")
        return False


def selection_set_hover_callback(context, element_id, event_data):
    """Handle hover events on selection sets"""
    # Update hover state for visual feedback
    is_hovered = event_data.get("is_hovered", False)

    # Update global hover state for visual feedback
    if is_hovered:
        # Extract set index from element_id if needed
        try:
            parts = element_id.split("_")
            if len(parts) >= 3 and parts[1] == "set":
                set_index = int(parts[2])
                gui_state["hovered_element"] = f"set_{set_index}"
        except:
            pass
    else:
        if gui_state.get("hovered_element", "").startswith("set_"):
            gui_state["hovered_element"] = None

    # Force redraw to show hover state
    if context.area:
        context.area.tag_redraw()

    return True


def grabber_hover_callback(context, element_id, event_data):
    """Handle hover events on grabber"""
    is_hovered = event_data.get("is_hovered", False)

    # Update global hover state
    if is_hovered:
        gui_state["hovered_element"] = "grabber"
    else:
        if gui_state.get("hovered_element") == "grabber":
            gui_state["hovered_element"] = None

    # Force redraw to show hover state
    if context.area:
        context.area.tag_redraw()

    return True


def redraw_all_areas():
    """Redraw every area in all windows to clear any overlays."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def get_window_region_from_area(area):
    """Get the WINDOW region from an area"""
    if not area:
        return None

    for region in area.regions:
        if region.type == "WINDOW":
            return region
    return None


def get_region_under_mouse(context, x, y):
    """Return (area, region, local_coords) under mouse."""
    for area in context.screen.areas:
        if area.x <= x <= area.x + area.width and area.y <= y <= area.y + area.height:
            for region in area.regions:
                # Skip HEADER and TOOL_HEADER regions to avoid false positives
                # if region.type in {"HEADER", "TOOL_HEADER"}:
                #     continue

                abs_x, abs_y = region.x, region.y
                if abs_x <= x <= abs_x + region.width and abs_y <= y <= abs_y + region.height:
                    return area, region, (x - abs_x, y - abs_y)
    return None, None, (0, 0)


def get_stored_region_state(context, area, region, panel_name="selection_sets"):
    """
    Get stored region state from scene properties - consolidated function.
    This replaces both get_stored_region_state and get_region_state for consistency.
    """
    if not hasattr(context.scene, "amp_anim_set"):
        return None

    # Get the window region for stable identification
    window_region = get_window_region_from_area(area)
    if not window_region:
        return None

    # Use panel-specific region key based on WINDOW region ID
    region_key = f"{area.type}_{str(window_region.as_pointer())}_{panel_name}"
    if not region_key:
        return None

    scene_props = context.scene.amp_anim_set

    # Look for existing state
    for state in scene_props.region_states:
        if state.region_key == region_key:
            return state

    return None


def get_or_create_region_state(context, area, panel_name=None):
    """
    Get existing region state or create a new one using corner-based system.
    This consolidates the creation logic from multiple functions.
    """
    # Try to get existing state first
    existing_state = get_stored_region_state(context, area, None, panel_name or "selection_sets")
    if existing_state:
        return existing_state

    # Get window region for creation
    window_region = get_window_region_from_area(area)
    if not window_region:
        return None

    # Create new state using the centralized function
    return create_or_update_region_state(context, area, window_region, None, None, panel_name or "selection_sets")


def draw_debug_info(self, context):
    """Draw debug overlay in the area where the mouse is currently located, or last known area."""
    area = context.area
    prefs = get_prefs()

    # Only draw debug info if enabled
    if not area or not tracker_data["show_debug"] or not prefs.debug:
        return

    current_area_id = tracker_data.get("area_id", "Unknown")
    last_valid_area_id = tracker_data.get("last_valid_area_id", "Unknown")

    # If mouse is currently over an area, only draw debug in that area
    if current_area_id != "Unknown":
        if str(area.as_pointer()) != current_area_id:
            return
    else:
        # If mouse is outside areas, show debug in the last valid area
        if last_valid_area_id == "Unknown" or str(area.as_pointer()) != last_valid_area_id:
            return

    # Get detailed region info for debugging
    region_info = get_detailed_region_info(context)
    if isinstance(region_info, str):
        drag_info = [region_info]
    else:
        drag_info = [
            f"Drag Valid: {region_info['is_valid_drag_region']}",
            f"Supported Area: {region_info['is_supported_area']}",
            f"Window Region: {region_info['is_window_region']}",
            f"Area Matches: {region_info['area_matches_drag']}",
            f"Dragging: {region_info['drag_state']['dragging_grabber']}",
            f"Drag Area ID: {region_info['drag_state']['drag_area_id'][-8:] if region_info['drag_state']['drag_area_id'] else 'None'}",
        ]

    # Get handler statistics for debugging
    handler_stats = get_handler_statistics()

    info_lines = [
        f"Window: {tracker_data['window_pos']}",
        f"Region: {tracker_data['region_pos']}",
        f"Area: {tracker_data['area_type']} ({tracker_data['area_id']})",
        f"Region: {tracker_data['region_type']} ({tracker_data['region_id']})",
        f"Debug: {tracker_data['debug_info']}",
        f"GUI: {gui_state['show_gui']}",
        f"Hovered: {gui_state['hovered_element']}",
        f"Region Valid: {tracker_data['region_type'] == 'WINDOW' and tracker_data['region_type'] not in {'HEADER', 'TOOL_HEADER'}}",
        f"Handlers: {handler_stats['total_handlers']}",
    ] + drag_info

    font_id = 0
    blf.size(font_id, 12)
    padding = 8
    line_height = 16

    # compute box size
    box_width = max(blf.dimensions(font_id, line)[0] for line in info_lines) + padding * 2
    box_height = len(info_lines) * line_height + padding * 2
    x0, y0 = 10, 10

    # draw background
    verts = [(x0, y0), (x0 + box_width, y0), (x0 + box_width, y0 + box_height), (x0, y0 + box_height)]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", (0, 0, 0, 0.75))
    batch.draw(shader)
    gpu.state.blend_set("NONE")

    # draw text
    gpu.state.blend_set("ALPHA")  # Enable alpha blending for text
    blf.color(font_id, 1, 1, 1, 1)
    for i, text in enumerate(info_lines):
        blf.position(font_id, x0 + padding, y0 + padding + i * line_height, 0)
        blf.draw(font_id, text)
    gpu.state.blend_set("NONE")  # Disable alpha blending


def draw_selection_sets_gui(self, context):
    """Draw selection sets GUI only in the tracked area."""
    area = context.area
    if not area or str(area.as_pointer()) != tracker_data["area_id"]:
        return

    # Check both GUI state and scene property
    if not gui_state["show_gui"]:
        return

    # Check scene property for display_gui
    if hasattr(context.scene, "amp_anim_set") and not context.scene.amp_anim_set.display_gui:
        return

    # Only draw in supported area types
    if not is_supported_area_type(area.type):
        return

    # Draw the actual selection sets GUI
    try:
        # Import the GUI draw function
        from .anim_selection_sets_gui import pinned_sets_draw_callback

        pinned_sets_draw_callback()
    except ImportError:
        pass  # Selection sets GUI module should handle its own fallback


def add_draw_handler(area):
    """Add centralized draw handler to an area only if it doesn't already exist."""
    aid = str(area.as_pointer())

    # Check if area is valid before proceeding
    if not is_area_valid(area):
        dprint(f"[HANDLER] Cannot add handler to invalid area {aid}")
        return

    # Check if handler already exists for this area
    if aid in _draw_handlers:
        # Verify the handler is still valid
        stored_area, stored_space, stored_handler = _draw_handlers[aid]
        if stored_area == area and stored_handler and is_area_valid(stored_area):
            return  # Handler already exists and is valid
        else:
            # Handler is stale, remove it
            dprint(f"[HANDLER] Removing stale handler for area {aid}")
            remove_draw_handler(aid)

    try:
        space = area.spaces.active
        # Use the centralized draw handler for all areas
        handler = space.draw_handler_add(centralized_draw_handler, (None, bpy.context), "WINDOW", "POST_PIXEL")
        _draw_handlers[aid] = (area, space, handler)
        dprint(f"[HANDLER] Added centralized draw handler for area {area.type} ({aid})")
    except Exception as e:
        dprint(f"[HANDLER] Failed to add centralized draw handler: {e}")


def is_area_valid(area):
    """Check if an area is valid for handler operations."""
    return (
        area
        and hasattr(area, "spaces")
        and area.spaces
        and area.spaces.active
        and hasattr(area.spaces.active, "draw_handler_add")
    )


def remove_draw_handler(aid):
    """Remove draw handler from an area using stored space instance."""
    data = _draw_handlers.get(aid)
    if data:
        area, space, handler = data
        try:
            space.draw_handler_remove(handler, "WINDOW")
            dprint(f"[HANDLER] Removed draw handler for area {area.type} ({aid})")
        except Exception as e:
            dprint(f"[HANDLER] Failed to remove draw handler: {e}")
        finally:
            _draw_handlers.pop(aid, None)


def validate_draw_handlers(context):
    """Validate existing draw handlers and remove stale ones."""
    stale_handlers = []

    # Get current valid area IDs
    valid_area_ids = set()
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            valid_area_ids.add(str(area.as_pointer()))

    for aid, (area, space, handler) in list(_draw_handlers.items()):
        is_stale = False

        # Check if area ID still exists in current context
        if aid not in valid_area_ids:
            is_stale = True
            dprint(f"[HANDLER] Found stale handler for non-existent area {aid}")

        # Check if space object is still valid and handler exists
        elif not hasattr(space, "draw_handler_remove") or not handler:
            is_stale = True
            dprint(f"[HANDLER] Found stale handler for area {aid} (invalid space or handler)")

        if is_stale:
            stale_handlers.append(aid)

    # Remove stale handlers
    for aid in stale_handlers:
        remove_draw_handler(aid)

    if stale_handlers:
        dprint(f"[HANDLER] Cleaned up {len(stale_handlers)} stale draw handlers")

    return len(stale_handlers) > 0


def ensure_draw_handler_for_area(area):
    """Ensure a draw handler exists for the given area, only if needed."""
    aid = str(area.as_pointer())

    # Check if area is valid
    if not is_area_valid(area):
        dprint(f"[HANDLER] Cannot ensure handler for invalid area {aid}")
        return

    # Check if handler already exists and is valid
    if aid in _draw_handlers:
        stored_area, stored_space, stored_handler = _draw_handlers[aid]
        if stored_area == area and stored_handler and is_area_valid(stored_area):
            return  # Handler already exists and is valid
        else:
            # Handler is stale, remove it and add a new one
            dprint(f"[HANDLER] Replacing stale handler for area {aid}")
            remove_draw_handler(aid)

    # Add new handler
    add_draw_handler(area)


def draw_combined_overlay(self, context):
    """Combined draw function for both debug and GUI."""
    # Always draw debug info if enabled
    draw_debug_info(self, context)

    # Draw selection sets GUI if enabled
    draw_selection_sets_gui(self, context)


def global_mouse_handler(context, event):
    """Handle mouse movement, adding/removing draw handlers and redrawing on area/region change."""
    global tracker_data
    mx, my = event.mouse_x, event.mouse_y
    prev_area = tracker_data["area_id"]
    prev_region = tracker_data["region_id"]

    # update window info
    tracker_data["window_pos"] = (mx, my)
    tracker_data["screen"] = context.screen

    # detect under-mouse area/region
    area, region, local_pos = get_region_under_mouse(context, mx, my)
    aid = str(area.as_pointer()) if area else "Unknown"
    rid = str(region.as_pointer()) if region else "Unknown"

    # Only redraw if there's an actual change and only the affected areas
    if aid != prev_area or rid != prev_region:
        # Mark only the previous and current areas as changed instead of redrawing all
        if prev_area != "Unknown":
            mark_area_changed(prev_area)
        if aid != "Unknown":
            mark_area_changed(aid)

        # Redraw only changed areas instead of all areas
        redraw_changed_areas_only(context)

    # update state and handlers
    if area and region:
        # Always update tracker data - don't exclude any region types
        tracker_data.update(
            {
                "area_type": area.type,
                "area_id": aid,
                "region_type": region.type,
                "region_pos": local_pos,
                "region_id": rid,
                "debug_info": f"reg({region.x},{region.y}) size({region.width}x{region.height})",
                "last_valid_area_id": aid,  # Track last valid area for debug display
            }
        )

        # Only add handler if we've moved to a new area: clean up stale first then ensure new
        if aid != prev_area:
            # Remove any stale handlers immediately to avoid accumulation
            validate_draw_handlers(context)
            ensure_draw_handler_for_area(area)

        # Only clear hover state when in non-WINDOW regions (to disable interactions)
        if region.type in {"HEADER", "TOOL_HEADER", "UI", "TOOLS", "PREVIEW"}:
            gui_state["hovered_element"] = None
    else:
        # Keep tracker alive even when mouse is outside areas (title bar, outside Blender, etc.)
        # Only update window position and set debug info to indicate we're outside areas
        tracker_data["window_pos"] = (mx, my)
        tracker_data["area_id"] = "Unknown"
        tracker_data["region_id"] = "Unknown"
        tracker_data["area_type"] = "Unknown"
        tracker_data["region_type"] = "Unknown"
        tracker_data["region_pos"] = (0, 0)
        tracker_data["debug_info"] = "Outside Blender areas (title bar, external, etc.)"
        # Keep last_valid_area_id for debug display

        # Clear hover state when mouse leaves areas entirely
        gui_state["hovered_element"] = None

    # remove stale handlers
    if prev_area != aid and prev_area in _draw_handlers:
        # Validate the handler exists before trying to remove it
        stored_area, stored_space, stored_handler = _draw_handlers[prev_area]
        if is_area_valid(stored_area):
            remove_draw_handler(prev_area)
        else:
            # Just remove from dict if area is already invalid
            _draw_handlers.pop(prev_area, None)
            dprint(f"[HANDLER] Cleaned up invalid handler reference for area {prev_area}")

    # Only redraw current area instead of all areas
    if area:
        area.tag_redraw()

    return {"PASS_THROUGH"}


def check_regions_when_needed(context):
    """Check regions only when we actually need to - during drags or window events."""
    if check_all_regions_for_changes(context):
        redraw_changed_areas_only(context)
        dprint("[TRACKER] Regions checked due to critical event")


# =============================================================================
# PANEL REGISTRY SYSTEM - Central management for all floating panels
# =============================================================================

# Registry of all panels that can be displayed
_panel_registry = {}


class PanelInfo:
    """Information about a registered panel"""

    def __init__(self, panel_name, draw_callback, event_handler, get_visibility_func, panel_specific_state=None):
        self.panel_name = panel_name
        self.draw_callback = draw_callback
        self.event_handler = event_handler
        self.get_visibility_func = get_visibility_func
        self.panel_specific_state = panel_specific_state or {}
        self.is_active = False


def register_panel(panel_name, draw_callback, event_handler, get_visibility_func, panel_specific_state=None):
    """
    Register a panel with the floating panels system.

    Args:
        panel_name: Unique identifier for the panel (e.g., "selection_sets")
        draw_callback: Function to call for drawing the panel
        event_handler: Function to call for handling events
        get_visibility_func: Function that returns True if panel should be visible
        panel_specific_state: Dictionary of panel-specific state (optional)
    """
    _panel_registry[panel_name] = PanelInfo(
        panel_name, draw_callback, event_handler, get_visibility_func, panel_specific_state
    )
    dprint(f"[REGISTRY] Registered panel: {panel_name}")


def unregister_panel(panel_name):
    """Unregister a panel from the system"""
    if panel_name in _panel_registry:
        del _panel_registry[panel_name]
        dprint(f"[REGISTRY] Unregistered panel: {panel_name}")


def get_panel_info(panel_name):
    """Get panel information by name"""
    return _panel_registry.get(panel_name)


def get_registered_panels():
    """Get all registered panels"""
    return list(_panel_registry.keys())


def is_panel_visible(panel_name):
    """Check if a specific panel should be visible"""
    panel_info = _panel_registry.get(panel_name)
    if not panel_info:
        return False

    try:
        return panel_info.get_visibility_func()
    except Exception as e:
        dprint(f"[REGISTRY] Error checking visibility for {panel_name}: {e}")
        return False


def get_active_panels():
    """Get list of currently active/visible panels"""
    active_panels = []
    for panel_name, panel_info in _panel_registry.items():
        if is_panel_visible(panel_name):
            active_panels.append(panel_name)
    return active_panels


def set_panel_active(panel_name, active=True):
    """Set a panel as active/inactive"""
    panel_info = _panel_registry.get(panel_name)
    if panel_info:
        panel_info.is_active = active
        dprint(f"[REGISTRY] Set panel {panel_name} active: {active}")


# =============================================================================
# TRACKER DATA FUNCTIONS - Central management for tracker state
# =============================================================================


def get_tracker_data(context):
    """Get tracker data from the modal operator"""
    global tracker_data
    return tracker_data


def ensure_tracker_running(context):
    """Ensure the tracker modal operator is running"""
    if not is_tracker_active(context):
        # Start the tracker
        try:
            bpy.ops.wm.amp_floating_panels_tracker("INVOKE_DEFAULT")
        except Exception as e:
            dprint(f"[TRACKER] Error starting tracker: {e}")


def is_tracker_active(context):
    """Check if the tracker modal operator is active"""
    global _active_modal
    return _active_modal is not None


# =============================================================================
# CENTRALIZED DRAW HANDLER - Calls all registered panels
# =============================================================================


def centralized_draw_handler(dummy, context):
    """
    Centralized draw handler that calls all registered and active panels.
    This replaces individual draw handlers for each panel.
    """
    if not context.area or not context.region:
        return

    # Only draw in supported area types with WINDOW regions
    supported_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
    if context.area.type not in supported_types or context.region.type != "WINDOW":
        return

    # Only draw in the area that's currently being tracked
    area_id = str(context.area.as_pointer()) if context.area else "Unknown"
    if area_id != tracker_data.get("area_id", "Unknown"):
        return

    # Get all active panels and call their draw callbacks
    try:
        active_panels = get_active_panels()
        for panel_name in active_panels:
            panel_info = get_panel_info(panel_name)
            if panel_info and panel_info.draw_callback:
                try:
                    panel_info.draw_callback()
                except Exception as e:
                    dprint(f"[DRAW_HANDLER] Error drawing panel '{panel_name}': {e}")
    except Exception as e:
        dprint(f"[DRAW_HANDLER] Error in centralized draw handler: {e}")


def centralized_event_handler(context, event):
    """
    Centralized event handler that forwards events to all registered and active panels.
    """
    if not context.area or not context.region:
        return False

    # Only handle events in supported area types with WINDOW regions
    supported_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
    if context.area.type not in supported_types or context.region.type != "WINDOW":
        return False

    # Forward event to all active panels
    try:
        active_panels = get_active_panels()
        for panel_name in active_panels:
            panel_info = get_panel_info(panel_name)
            if panel_info and panel_info.event_handler:
                try:
                    if panel_info.event_handler(context, event):
                        return True  # Event was handled by this panel
                except Exception as e:
                    dprint(f"[EVENT_HANDLER] Error handling event for panel '{panel_name}': {e}")
    except Exception as e:
        dprint(f"[EVENT_HANDLER] Error in centralized event handler: {e}")

    return False


# =============================================================================


def toggle_gui(context):
    """Toggle the GUI visibility."""
    gui_state["show_gui"] = not gui_state["show_gui"]

    if gui_state["show_gui"]:
        # Start tracker when GUI is enabled
        ensure_tracker_running(context)
        # Register draw handlers (with validation)
        register_all_draw_handlers()
        # Print handler statistics for debugging
        debug_print_handler_stats()
    else:
        # Unregister draw handlers
        unregister_all_draw_handlers()

    # Only redraw areas that have GUI elements instead of all areas
    redraw_gui_areas_only(context)
    dprint(f"[GUI] GUI toggled: {gui_state['show_gui']}")
    return gui_state["show_gui"]


def get_gui_drag_state():
    """Get the current global drag state."""
    return {
        "dragging_grabber": gui_state["dragging_grabber"],
        "hovered_element": gui_state["hovered_element"],
        "drag_area_id": gui_state["drag_area_id"],
        "drag_started": gui_state["drag_started"],
    }


def get_detailed_region_info(context):
    """Get detailed region information for debugging."""
    tracker_info = get_tracker_data(context)
    if not tracker_info:
        return "No tracker data available"

    supported_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
    is_supported_area = tracker_info["area_type"] in supported_types
    is_window_region = tracker_info["region_type"] == "WINDOW"

    drag_state = get_gui_drag_state()
    area_matches = not drag_state["drag_area_id"] or tracker_info["area_id"] == drag_state["drag_area_id"]

    return {
        "area_type": tracker_info["area_type"],
        "region_type": tracker_info["region_type"],
        "area_id": tracker_info["area_id"],
        "is_supported_area": is_supported_area,
        "is_window_region": is_window_region,
        "area_matches_drag": area_matches,
        "is_valid_drag_region": is_supported_area and is_window_region and area_matches,
        "drag_state": drag_state,
    }


def ensure_drag_area_set(context):
    """Ensure the drag area is set to the current tracker area."""
    if gui_state["dragging_grabber"] and not gui_state["drag_area_id"]:
        tracker_info = get_tracker_data(context)
        if tracker_info:
            gui_state["drag_area_id"] = tracker_info["area_id"]
            dprint(f"[DRAG] Set missing drag area to current tracker area: {tracker_info['area_id']}")


def handle_global_mouse_event(context, event):
    """Handle global mouse events for dragging, returns True if event was handled."""
    if event.type == "MOUSEMOVE" and gui_state["dragging_grabber"]:
        # Ensure drag area is set
        ensure_drag_area_set(context)

        # Check if dragging should stop
        if should_stop_dragging(context, event):
            stop_dragging_globally()
            return True

        # Continue with constrained movement
        return False

    elif event.type == "LEFTMOUSE" and event.value == "RELEASE" and gui_state["dragging_grabber"]:
        # Global LMB release to stop dragging
        stop_dragging_globally()
        return True

    return False


def compute_window_region_bounds(area, width, height):
    """Compute constraint bounds for a window region."""
    window_region = get_window_region_from_area(area)
    if not window_region:
        return None

    margin = 10
    return {
        "min_x": margin,
        "max_x": window_region.width - width - margin,
        "min_y": margin,
        "max_y": window_region.height - height - margin,
        "window_region": window_region,
    }


def clamp_position(x, y, bounds):
    """Clamp position to bounds."""
    if not bounds:
        return x, y

    clamped_x = max(bounds["min_x"], min(bounds["max_x"], x))
    clamped_y = max(bounds["min_y"], min(bounds["max_y"], y))

    return clamped_x, clamped_y


def constrain_to_window_region(context, area, x, y, width, height):
    """Constrain grabber position to stay within the WINDOW region of an area."""
    bounds = compute_window_region_bounds(area, width, height)
    constrained_x, constrained_y = clamp_position(x, y, bounds)

    # Debug print when constraints are applied
    if constrained_x != x or constrained_y != y:
        dprint(f"[CONSTRAINT] Clamped position from ({x}, {y}) to ({constrained_x}, {constrained_y})")
        if bounds:
            dprint(
                f"[CONSTRAINT] Window region bounds: x({bounds['min_x']}-{bounds['max_x']}), y({bounds['min_y']}-{bounds['max_y']})"
            )

    return constrained_x, constrained_y


def get_region_state_key(area, panel_name=None):
    """Get a unique key for storing region state - simplified to use only WINDOW region ID."""
    # Find the WINDOW region for this area
    window_region = None
    for region in area.regions:
        if region.type == "WINDOW":
            window_region = region
            break

    if window_region:
        # Use only the WINDOW region ID for the key
        base_key = f"WINDOW_{str(window_region.as_pointer())}"
        if panel_name:
            return f"{base_key}_{panel_name}"
        return base_key

    # Fallback if no WINDOW region found
    base_key = f"{area.type}_{str(area.as_pointer())}"
    if panel_name:
        return f"{base_key}_{panel_name}"
    return base_key


def get_panel_grabber_dimensions(panel_name):
    """Get grabber dimensions for a specific panel type."""
    if panel_name == "selection_sets":
        try:
            from .anim_selection_sets_gui import get_scaled_gui_dimensions

            dims = get_scaled_gui_dimensions()
            return dims["grabber_width"], dims["height"]
        except ImportError:
            return 10, 15
    else:
        # Default dimensions for other panels
        return 10, 15


# =============================================================================
# COLOR UTILITY FUNCTIONS - Centralized color calculations
# =============================================================================


def get_base_colors_and_alpha(prefs, is_hovered=False, is_dragging=False):
    """
    Get base colors and alpha values from preferences.
    Returns (base_bg_color, alpha) tuple.
    """
    if prefs:
        base_bg_color = prefs.fp_background_color
        # Use hover alpha if hovered or dragging, otherwise default
        alpha = prefs.fp_hoover_alpha if is_hovered or is_dragging else prefs.fp_default_alpha
    else:
        base_bg_color = (0.1, 0.1, 0.1)
        alpha = 1.0 if is_hovered or is_dragging else 0.8

    return base_bg_color, alpha


def get_grabber_color(prefs, is_hovered=False, is_dragging=False):
    """
    Get grabber color based on state and preferences.
    Returns RGBA color tuple.
    """
    base_bg_color, base_alpha = get_base_colors_and_alpha(prefs, is_hovered, is_dragging)

    # Scale alpha for grabber to be more visible (multiply by 1.5 but cap at 1.0)
    grabber_alpha = min(1.0, base_alpha * 1.5)

    # Choose color based on state using background color preference
    if is_dragging:
        # Brighter when dragging
        color = (base_bg_color[0] + 0.2, base_bg_color[1] + 0.2, base_bg_color[2] + 0.2, grabber_alpha)
    elif is_hovered:
        # Slightly brighter when hovered
        color = (base_bg_color[0] + 0.1, base_bg_color[1] + 0.1, base_bg_color[2] + 0.1, grabber_alpha)
    else:
        # Default state - use calculated alpha
        color = (base_bg_color[0], base_bg_color[1], base_bg_color[2], grabber_alpha)

    # Clamp color values
    return (min(1.0, color[0]), min(1.0, color[1]), min(1.0, color[2]), color[3])


def get_button_background_color(prefs, is_hovered=False):
    """
    Get button background color based on hover state and preferences.
    Returns RGBA color tuple.
    """
    if not prefs:
        return (0.1, 0.1, 0.1, 0.8)

    # Determine alpha based on hover state
    alpha = prefs.fp_hoover_alpha if is_hovered else prefs.fp_default_alpha

    # Use background color preference
    base_color = prefs.fp_background_color
    return (base_color[0], base_color[1], base_color[2], alpha)


def get_offset_color(base_color, alpha=0.5, offset=0.3):
    """
    Calculate offset color for better contrast against background

    Args:
        base_color: RGB tuple (r, g, b)
        alpha: Alpha value for the inverted color
        offset: Offset value for inversion (default 0.3)

    Returns:
        tuple: Offset RGBA color
    """
    r, g, b = base_color[:3]
    # Invert the color
    inverted_r = offset - r
    inverted_g = offset - g
    inverted_b = offset - b
    return (inverted_r, inverted_g, inverted_b, alpha)


# Color manipulation functions
def darken_color(color, alpha=1.0, factor=0.7):
    """
    Darken a color by the given factor

    Args:
        color (tuple): RGB color (r, g, b)
        factor (float): Darkening factor (0.0 = black, 1.0 = original)

    Returns:
        tuple: Darkened RGBA color
    """
    r, g, b = color[:3]
    # Simply multiply by the factor to darken
    new_r = r * factor
    new_g = g * factor
    new_b = b * factor
    return (new_r, new_g, new_b, alpha)


def desaturate_color(color, alpha=1.0, factor=0.5):
    """
    Desaturate a color by the given factor

    Args:
        color (tuple): RGB color (r, g, b)
        factor (float): Desaturation factor (0.0 = grayscale, 1.0 = original)

    Returns:
        tuple: Desaturated RGBA color
    """
    r, g, b = color[:3]
    # Convert to grayscale
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    # Mix with original color
    new_r = gray + factor * (r - gray)
    new_g = gray + factor * (g - gray)
    new_b = gray + factor * (b - gray)
    return (new_r, new_g, new_b, alpha)


def saturate_color(color, factor=0.75):
    """
    Increase saturation of a color (opposite of desaturate)

    Args:
        color (tuple): RGB color (r, g, b)
        factor (float): Saturation factor (0.0 = grayscale, 1.0 = original, >1.0 = more saturated)

    Returns:
        tuple: Saturated RGBA color
    """
    r, g, b = color[:3]
    # Convert to grayscale
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    # Mix with original color for more saturation
    new_r = gray + factor * (r - gray)
    new_g = gray + factor * (g - gray)
    new_b = gray + factor * (b - gray)
    # Clamp values
    new_r = max(0.0, min(1.0, new_r))
    new_g = max(0.0, min(1.0, new_g))
    new_b = max(0.0, min(1.0, new_b))
    return (new_r, new_g, new_b, 1.0)


def keep_gui_in_region(gui_x, gui_y, gui_width, gui_height, region):
    """
    Ensure the grabber will always be inside of the region where it is drawn.
    Only the grabber dimensions are considered for collision - not the selection sets.
    This function respects the GUI scale preference.

    Args:
        gui_x (float): GUI X position
        gui_y (float): GUI Y position
        gui_width (float): GUI width (ignored - only grabber width is used)
        gui_height (float): GUI height
        region: Blender region object

    Returns:
        tuple: (adjusted_x, adjusted_y)
    """
    # Get scaled dimensions
    dims = get_scaled_gui_dimensions()

    # Get GUI scale for margin calculations
    prefs = get_prefs()
    gui_scale = prefs.fp_scale if prefs else 1.0

    # Scale the margin with GUI scale to maintain consistent spacing
    margin = int(10 * gui_scale)

    # Keep grabber within region bounds - only consider grabber dimensions
    min_x = margin  # margin from left
    max_x = region.width - dims["grabber_width"] - margin  # margin from right, only consider grabber width
    min_y = margin  # margin from bottom
    max_y = region.height - gui_height - margin  # margin from top

    # Clamp values to ensure grabber stays in region
    adjusted_x = max(min_x, min(max_x, gui_x))
    adjusted_y = max(min_y, min(max_y, gui_y))

    # Debug dprint when boundaries are hit
    if adjusted_x != gui_x or adjusted_y != gui_y:
        dprint(f"[DRAG_BOUNDARY] Clamped grabber position from ({gui_x}, {gui_y}) to ({adjusted_x}, {adjusted_y})")
        dprint(f"[DRAG_BOUNDARY] Grabber bounds: x({min_x}-{max_x}), y({min_y}-{max_y})")

    return adjusted_x, adjusted_y


def calculate_gui_width(preset, region_state=None):
    """
    Calculate the total width needed for the GUI with DPI scaling

    Args:
        preset: The active preset with sets
        region_state: Optional region state to check collapse status

    Returns:
        float: Total width needed
    """
    dims = get_scaled_gui_dimensions()

    # Check collapse state from region or fall back to global state
    collapsed = False
    if region_state:
        collapsed = region_state.get("collapsed", False)
    else:
        collapsed = gui_state["collapsed"]

    if collapsed:
        return dims["grabber_width"]

    # Get pinned sets
    pinned = [s for s in preset.sets if s.pinned]
    if not pinned:
        return dims["grabber_width"]

    # Calculate total width: grabber + padding + panel width
    total_width = dims["grabber_width"] + dims["horizontal_padding"] + dims["panel_width"]

    return total_width


def get_ui_element(context, element_id):
    return None


def get_dpi_scale():
    """Get DPI and UI scale factor"""
    try:
        # Get system DPI and UI scale
        prefs = bpy.context.preferences.system
        dpi = prefs.dpi
        ui_scale = prefs.ui_scale
        # Calculate combined scale factor
        scale_factor = (dpi / 72.0) * ui_scale
        return max(1.0, scale_factor)  # Ensure minimum scale of 1.0
    except:
        return 1.0


def get_text_dimensions(text, font_size=10):
    """Get text dimensions with specified font size"""
    try:
        # Set font size
        blf.size(0, font_size)
        # Get dimensions
        return blf.dimensions(0, text)
    except:
        # Fallback dimensions if blf fails
        return (len(text) * 6, font_size)  # Rough estimate


def get_scaled_gui_dimensions():
    """Get GUI dimensions scaled for DPI, UI scale, and GUI scale preference"""
    prefs = get_prefs()
    if not prefs:
        # Fallback to hardcoded values if preferences are not available
        return {
            "height": 20,
            "grabber_width": 10,
            "padding": 5,
            "min_set_width": 20,
            "text_padding": 10,
            "panel_width": 400,
            "horizontal_padding": 10,
            "vertical_padding": 5,
            "corner_radius": 5,
            "corner_segments": 8,
            "box_padding": 5,
        }

    dpi_scale = get_dpi_scale()
    gui_scale = prefs.fp_scale  # Get GUI scale preference

    # Combine both scales
    combined_scale = dpi_scale * gui_scale

    # Get values from preferences
    row_height = prefs.fp_row_height
    panel_width = prefs.fp_floating_panel_width
    horizontal_padding = prefs.fp_horizontal_padding
    vertical_padding = prefs.fp_vertical_padding
    corner_radius = prefs.fp_rounded_corners
    box_padding = prefs.fp_box_padding

    # Calculate corner segments based on radius (more segments for larger radius)
    # But cap at reasonable values to avoid performance issues
    corner_segments = max(16, min(4, int(corner_radius / 3) + 4)) if corner_radius > 0 else 4

    # Limit corner radius to half the height to ensure perfect semicircles and prevent drawing issues
    # This prevents corners from overlapping and keeps the box dimensions consistent
    max_corner_radius = min(row_height / 2.2, 50 * combined_scale)  # Limit to half height and reasonable max size
    corner_radius = min(corner_radius, max_corner_radius)

    return {
        "height": int(row_height * combined_scale),
        "grabber_width": int(10 * combined_scale),
        "padding": max(5, int(vertical_padding * combined_scale)),
        "min_set_width": int(20 * combined_scale),
        "text_padding": int(10 * combined_scale),
        "panel_width": int(panel_width * combined_scale),
        "horizontal_padding": int(horizontal_padding * combined_scale),
        "vertical_padding": int(vertical_padding * combined_scale),
        "corner_radius": corner_radius * combined_scale,
        "corner_segments": corner_segments,
        "grabber_corner_radius": 2.5 * combined_scale,
        "box_padding": box_padding * combined_scale,
    }


def import_corner_functions():
    """Import corner-based positioning functions from GUI module"""
    try:
        from .anim_selection_sets_gui import (
            get_window_region_from_area,
            find_closest_corner,
            calculate_position_from_corner,
            get_grabber_position_from_region_state,
            create_or_update_region_state,
            constrain_distances_to_quadrant,
        )

        return {
            "get_window_region_from_area": get_window_region_from_area,
            "find_closest_corner": find_closest_corner,
            "calculate_position_from_corner": calculate_position_from_corner,
            "get_grabber_position_from_region_state": get_grabber_position_from_region_state,
            "create_or_update_region_state": create_or_update_region_state,
            "constrain_distances_to_quadrant": constrain_distances_to_quadrant,
        }
    except ImportError as e:
        dprint(f"Warning: Could not import corner functions: {e}")
        return None


def create_or_update_region_state(
    context, area, region, position=None, collapsed=None, hidden=None, panel_name="selection_sets"
):
    """Create or update region state in scene properties - now uses corner-based positioning"""
    if not hasattr(context.scene, "amp_anim_set"):
        return None

    # Get the window region for stable identification
    window_region = get_window_region_from_area(area)
    if not window_region:
        return None

    # Use panel-specific region key based on WINDOW region ID
    region_key = f"{area.type}_{str(window_region.as_pointer())}_{panel_name}"
    if not region_key:
        return None

    scene_props = context.scene.amp_anim_set

    # Look for existing state
    existing_state = None
    for state in scene_props.region_states:
        if state.region_key == region_key:
            existing_state = state
            break

    # Create new state if it doesn't exist
    if not existing_state:
        new_state = scene_props.region_states.add()
        new_state.region_key = region_key
        new_state.window_region_id = str(window_region.as_pointer())
        new_state.area_type = area.type

        # Set default corner-based position (bottom-right corner, 50px from edges)
        new_state.corner_type = "bottom_right"
        new_state.corner_distance_x = 50
        new_state.corner_distance_y = 50

        # Set legacy properties for backward compatibility
        new_state.gui_position_x = 20
        new_state.gui_position_y = 20
        new_state.collapsed = False
        # Add hidden property - defaults to False (not hidden)
        if hasattr(new_state, "hidden"):
            new_state.hidden = False
        existing_state = new_state

    # Update state if values provided
    if position is not None:
        x, y = position
        # Find the closest corner and store distances
        corner_type, dist_x, dist_y = find_closest_corner(window_region, x, y)
        existing_state.corner_type = corner_type
        existing_state.corner_distance_x = dist_x
        existing_state.corner_distance_y = dist_y

        # Also update legacy properties for backward compatibility
        existing_state.gui_position_x = int(x)
        existing_state.gui_position_y = int(y)

    if collapsed is not None:
        existing_state.collapsed = collapsed

    if hidden is not None:
        if hasattr(existing_state, "hidden"):
            existing_state.hidden = hidden

    return existing_state


def get_current_mouse_region(context):
    """Get the region currently under the mouse cursor"""
    # Get tracker data from floating panels tracker
    tracker_data = get_tracker_data(context)
    if not tracker_data or not context.window:
        return None, None

    # Only return if it's a supported area type
    supported_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
    if tracker_data["area_type"] in supported_types and tracker_data.get("region_type") == "WINDOW":
        # For now, we return the current area and region since we don't have direct access
        # The floating panels tracker gives us the information we need
        return context.area, context.region if context.region.type == "WINDOW" else None

    return None, None


def should_display_gui_in_region(context, area, region):
    """Check if GUI should be displayed in the given region"""
    # Global visibility check
    if not gui_state["show_pinned_gui"]:
        return False

    # Check if display_gui is enabled
    if hasattr(context.scene, "amp_anim_set"):
        if not context.scene.amp_anim_set.display_gui:
            return False

    # Only draw in supported area types with main window regions
    # Exclude HEADER and TOOL_HEADER regions to avoid false positives
    if not is_supported_area_type(area.type) or not is_valid_region_type(region.type):
        return False

    # Always display in supported areas when GUI is enabled
    # We don't need to restrict to mouse-over areas
    return True


def region_to_gui(context, mouse_x, mouse_y):
    """Convert screen coordinates to GUI coordinates"""
    # Get tracker data from floating panels tracker
    tracker_data = get_tracker_data(context)
    if tracker_data:
        return tracker_data["region_pos"]
    # Fallback to provided coordinates
    return (mouse_x, mouse_y)


def get_gui_position_for_region(main_region):
    """Calculate GUI position for a specific region"""
    # Place GUI in the center-right of the region, using region coordinates
    # Make sure we're within the actual drawable area
    region_x = max(10, main_region.width - 250)  # 250 pixels from right edge, but at least 10px from left
    region_y = max(100, main_region.height - 100)  # 100 pixels from top, but at least 100px from bottom
    return region_x, region_y


def get_region_key_legacy(area):
    """Get a unique key for a region (legacy function)"""
    if not area:
        return None
    # Use area memory address as unique identifier
    return str(area.as_pointer())


def cleanup_region_states(context):
    """Clean up invalid region states from scene properties"""
    if not hasattr(context.scene, "amp_anim_set"):
        return

    scene_props = context.scene.amp_anim_set
    to_remove = []

    for i, state in enumerate(scene_props.region_states):
        # For now, we'll keep all states since we don't have a reliable way to check validity
        # In the future, we could implement region validity checking
        pass

    # Remove in reverse order to maintain indices
    for i in reversed(to_remove):
        scene_props.region_states.remove(i)


def register_all_draw_handlers():
    """Register centralized draw handlers for all current areas, avoiding duplicates."""
    # First validate existing handlers
    validate_draw_handlers(bpy.context)

    # Only add handlers for areas that don't already have them
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            ensure_draw_handler_for_area(area)

    dprint(f"[TRACKER] Centralized draw handlers ensured for all areas (total: {len(_draw_handlers)})")


def get_handler_statistics():
    """Get statistics about current draw handlers for debugging."""
    stats = {"total_handlers": len(_draw_handlers), "handlers_by_area_type": {}, "handler_details": []}

    for aid, (area, space, handler) in _draw_handlers.items():
        area_type = area.type
        if area_type not in stats["handlers_by_area_type"]:
            stats["handlers_by_area_type"][area_type] = 0
        stats["handlers_by_area_type"][area_type] += 1

        stats["handler_details"].append({"area_id": aid, "area_type": area_type, "handler_valid": handler is not None})

    return stats


def debug_print_handler_stats():
    """Print handler statistics for debugging."""
    stats = get_handler_statistics()
    dprint(f"[HANDLER STATS] Total handlers: {stats['total_handlers']}")
    for area_type, count in stats["handlers_by_area_type"].items():
        dprint(f"[HANDLER STATS] {area_type}: {count} handlers")


def unregister_all_draw_handlers():
    """Unregister all draw handlers safely."""
    handler_count = len(_draw_handlers)
    for aid in list(_draw_handlers.keys()):
        remove_draw_handler(aid)
    dprint(f"[TRACKER] Unregistered {handler_count} draw handlers")


def update_gui_state(context, display_gui_enabled):
    """Update GUI state and draw handlers based on display_gui property."""
    if display_gui_enabled:
        # Ensure tracker is running
        ensure_tracker_running(context)
        # Register draw handlers
        register_all_draw_handlers()
        # Enable GUI drawing
        gui_state["show_gui"] = True
        dprint("[TRACKER] GUI enabled - tracker started, handlers registered")
    else:
        # Disable GUI drawing
        gui_state["show_gui"] = False
        # Unregister draw handlers
        unregister_all_draw_handlers()
        dprint("[TRACKER] GUI disabled - handlers unregistered, tracker kept running")

    # Only redraw GUI areas instead of all areas
    redraw_gui_areas_only(context)


def cancel_tracker(context):
    """Cancel the tracker with the cancel mechanism."""
    global _active_modal
    if _active_modal:
        # Set the cancel flag and invoke the operator to trigger cancellation
        AMP_OT_FloatingPanelsTracker._cancel_requested = True
        bpy.ops.wm.amp_floating_panels_tracker("INVOKE_DEFAULT", panel_name="selection_sets")
        return True
    return False


def stop_dragging_globally():
    """Stop dragging globally and update all areas."""
    if gui_state["dragging_grabber"]:
        gui_state["dragging_grabber"] = False
        gui_state["drag_started"] = False
        gui_state["hovered_element"] = None

        # Only redraw the area where dragging was happening instead of all areas
        if gui_state["drag_area_id"]:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if str(area.as_pointer()) == gui_state["drag_area_id"]:
                        area.tag_redraw()
                        break

        gui_state["drag_area_id"] = ""
        dprint("[DRAG] Stopped dragging globally")


# Region tracking system for detecting changes and managing grabber positions
region_cache = {}  # Cache of region dimensions: area_id -> {width, height, x, y}
last_window_dimensions = {}  # Cache of window dimensions: window_id -> {width, height}


def get_region_dimensions(area, region):
    """Get region dimensions and position relative to area."""
    return {
        "width": region.width,
        "height": region.height,
        "x": region.x,
        "y": region.y,
        "area_x": area.x,
        "area_y": area.y,
        "area_width": area.width,
        "area_height": area.height,
    }


def has_region_changed(area, region):
    """Check if a region has changed size or position."""
    area_id = str(area.as_pointer())
    current_dims = get_region_dimensions(area, region)

    if area_id not in region_cache:
        region_cache[area_id] = current_dims
        return True

    cached_dims = region_cache[area_id]

    # Check if any dimension has changed
    for key in current_dims:
        if current_dims[key] != cached_dims[key]:
            region_cache[area_id] = current_dims
            return True

    return False


def has_window_changed(window):
    """Check if window dimensions have changed."""
    window_id = str(window.as_pointer())
    current_dims = {"width": window.width, "height": window.height}

    if window_id not in last_window_dimensions:
        last_window_dimensions[window_id] = current_dims
        return True

    cached_dims = last_window_dimensions[window_id]

    if current_dims["width"] != cached_dims["width"] or current_dims["height"] != cached_dims["height"]:
        last_window_dimensions[window_id] = current_dims
        return True

    return False


def check_all_regions_for_changes(context):
    """Check all regions in all windows for changes and update grabber positions - only called when needed."""
    changes_detected = False

    # Clean up stale cache entries every 100 calls to prevent indefinite growth
    if not hasattr(check_all_regions_for_changes, "_cleanup_counter"):
        check_all_regions_for_changes._cleanup_counter = 0
    check_all_regions_for_changes._cleanup_counter += 1

    if check_all_regions_for_changes._cleanup_counter % 100 == 0:
        cleanup_stale_cache_entries(context)

    for window in context.window_manager.windows:
        # Check if window itself changed
        if has_window_changed(window):
            changes_detected = True
            dprint(f"[RESIZE] Window {window.as_pointer()} changed size")

        # Check each area's WINDOW region
        for area in window.screen.areas:
            window_region = get_window_region_from_area(area)
            if window_region and has_region_changed(area, window_region):
                changes_detected = True
                dprint(f"[RESIZE] Area {area.type} ({area.as_pointer()}) WINDOW region changed")

                # Mark this area as changed for optimized redrawing
                mark_area_changed(str(area.as_pointer()))

                # Update grabber position for this area if it has a region state
                update_grabber_position_for_area(context, area, window_region)

    return changes_detected


def update_grabber_position_for_area(context, area, window_region):
    """Update grabber position for a specific area when its region changes - now uses corner-based positioning."""
    if not hasattr(context.scene, "amp_anim_set"):
        return

    # Validate draw handlers when we're restoring grabber positions
    validate_draw_handlers(context)

    corner_funcs = import_corner_functions()
    if not corner_funcs:
        # Fallback to legacy system - find region state with old key format
        region_state = None
        for state in context.scene.amp_anim_set.region_states:
            if state.area_type == area.type and state.region_key.startswith(f"{area.type}_{str(area.as_pointer())}_"):
                region_state = state
                break

        if not region_state:
            return

        # Get current grabber position
        current_x = region_state.gui_position_x
        current_y = region_state.gui_position_y

        # Get scaled dimensions for the grabber
        from .anim_selection_sets_gui import get_scaled_gui_dimensions

        dims = get_scaled_gui_dimensions()
        grabber_width = dims["grabber_width"]
        grabber_height = dims["height"]

        # Constrain to new region bounds
        constrained_x, constrained_y = constrain_to_window_region(
            context, area, current_x, current_y, grabber_width, grabber_height
        )

        # Update position if it changed
        if constrained_x != current_x or constrained_y != current_y:
            region_state.gui_position_x = constrained_x
            region_state.gui_position_y = constrained_y
            dprint(
                f"[RESIZE] Updated grabber position from ({current_x}, {current_y}) to ({constrained_x}, {constrained_y})"
            )
        return

    # Use corner-based system
    try:
        # Find region state using new key format (based on WINDOW region ID)
        window_region_id = str(window_region.as_pointer())
        region_state = None
        for state in context.scene.amp_anim_set.region_states:
            if (
                state.area_type == area.type
                and hasattr(state, "window_region_id")
                and state.window_region_id == window_region_id
            ):
                region_state = state
                break

        if not region_state:
            # Try to find with legacy key format as fallback
            for state in context.scene.amp_anim_set.region_states:
                if state.area_type == area.type and state.region_key.startswith(
                    f"{area.type}_{str(area.as_pointer())}_"
                ):
                    region_state = state
                    break

        if not region_state:
            return

        # Get current grabber position using corner-based system
        current_x, current_y = corner_funcs["get_grabber_position_from_region_state"](
            context, area, window_region, region_state
        )

        # Get scaled dimensions for the grabber
        from .anim_selection_sets_gui import get_scaled_gui_dimensions

        dims = get_scaled_gui_dimensions()
        grabber_width = dims["grabber_width"]
        grabber_height = dims["height"]

        # Constrain to new region bounds
        constrained_x, constrained_y = constrain_to_window_region(
            context, area, current_x, current_y, grabber_width, grabber_height
        )

        # Update position if it changed - use corner-based system
        if constrained_x != current_x or constrained_y != current_y:
            # Find closest corner and update distances
            corner_type, dist_x, dist_y = corner_funcs["find_closest_corner"](
                window_region, constrained_x, constrained_y
            )

            # Update region state with new corner-based data
            if hasattr(region_state, "corner_type"):
                region_state.corner_type = corner_type
                region_state.corner_distance_x = dist_x
                region_state.corner_distance_y = dist_y

            # Also update legacy properties for backward compatibility
            region_state.gui_position_x = constrained_x
            region_state.gui_position_y = constrained_y

            dprint(
                f"[RESIZE] Updated grabber position from ({current_x}, {current_y}) to ({constrained_x}, {constrained_y})"
            )
            dprint(f"[RESIZE] Corner: {corner_type}, distances: ({dist_x}, {dist_y})")

    except Exception as e:
        dprint(f"Error updating grabber position with corner-based system: {e}")
        # Fallback to legacy system if corner-based fails
        region_state = None
        for state in context.scene.amp_anim_set.region_states:
            if state.area_type == area.type and state.region_key.startswith(f"{area.type}_{str(area.as_pointer())}_"):
                region_state = state
                break

        if region_state:
            current_x = region_state.gui_position_x
            current_y = region_state.gui_position_y
            from .anim_selection_sets_gui import get_scaled_gui_dimensions

            dims = get_scaled_gui_dimensions()
            constrained_x, constrained_y = constrain_to_window_region(
                context, area, current_x, current_y, dims["grabber_width"], dims["height"]
            )
            if constrained_x != current_x or constrained_y != current_y:
                region_state.gui_position_x = constrained_x
                region_state.gui_position_y = constrained_y
                dprint(
                    f"[RESIZE] Updated grabber position from ({current_x}, {current_y}) to ({constrained_x}, {constrained_y})"
                )


def constrain_grabber_movement(context, proposed_x, proposed_y, drag_area_id):
    """Constrain grabber movement to valid regions, allowing movement in valid directions."""
    # Find the area where dragging started
    drag_area = None
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if str(area.as_pointer()) == drag_area_id:
                drag_area = area
                break
        if drag_area:
            break

    if not drag_area:
        dprint(f"[DRAG] Could not find drag area {drag_area_id}")
        return proposed_x, proposed_y

    # Get grabber dimensions
    try:
        from .anim_selection_sets_gui import get_scaled_gui_dimensions

        dims = get_scaled_gui_dimensions()
        grabber_width = dims["grabber_width"]
        grabber_height = dims["height"]
    except ImportError:
        grabber_width = 10
        grabber_height = 15

    # Use the consolidated constraint function
    constrained_x, constrained_y = constrain_to_window_region(
        context, drag_area, proposed_x, proposed_y, grabber_width, grabber_height
    )

    # Debug info when constraints are applied
    if constrained_x != proposed_x or constrained_y != proposed_y:
        dprint(f"[DRAG] Constrained grabber from ({proposed_x}, {proposed_y}) to ({constrained_x}, {constrained_y})")

    return constrained_x, constrained_y


def should_stop_dragging(context, event):
    """Check if dragging should stop based on mouse position using tracker data."""
    if not gui_state["dragging_grabber"]:
        return False

    # Use tracker data to determine if we're in a valid drag region
    tracker_info = get_tracker_data(context)
    if not tracker_info:
        dprint(f"[DRAG] Stopping drag - no tracker data")
        return True

    # Only stop dragging if we're in a completely invalid area type
    supported_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
    if tracker_info["area_type"] not in supported_types:
        dprint(f"[DRAG] Stopping drag - unsupported area type: {tracker_info['area_type']}")
        return True

    # Stop dragging if we switched to a different area
    if gui_state["drag_area_id"] and tracker_info["area_id"] != gui_state["drag_area_id"]:
        dprint(f"[DRAG] Stopping drag - area changed from {gui_state['drag_area_id']} to {tracker_info['area_id']}")
        return True

    # Don't stop for region type changes within the same area - just constrain movement
    # This allows dragging to continue even when mouse goes outside WINDOW region
    return False


def migrate_region_states_to_corner_based(context):
    """Migrate existing region states to use corner-based positioning system"""
    if not hasattr(context.scene, "amp_anim_set"):
        return

    corner_funcs = import_corner_functions()
    if not corner_funcs:
        return

    scene_props = context.scene.amp_anim_set
    migrated_count = 0

    for region_state in scene_props.region_states:
        # Skip if already migrated (has corner_type property)
        if hasattr(region_state, "corner_type") and region_state.corner_type:
            continue

        # Skip if no legacy position data
        if not hasattr(region_state, "gui_position_x") or not hasattr(region_state, "gui_position_y"):
            continue

        try:
            # Find the area this region state belongs to
            area = None
            for window in context.window_manager.windows:
                for a in window.screen.areas:
                    if a.type == region_state.area_type:
                        area = a
                        break
                if area:
                    break

            if not area:
                continue

            # Get the window region
            window_region = corner_funcs["get_window_region_from_area"](area)
            if not window_region:
                continue

            # Get current legacy position
            x = region_state.gui_position_x
            y = region_state.gui_position_y

            # Convert to corner-based positioning
            corner_type, dist_x, dist_y = corner_funcs["find_closest_corner"](window_region, x, y)

            # Update region state with corner-based data
            if hasattr(region_state, "corner_type"):
                region_state.corner_type = corner_type
                region_state.corner_distance_x = dist_x
                region_state.corner_distance_y = dist_y

                # Update window region ID for stable identification
                if hasattr(region_state, "window_region_id"):
                    region_state.window_region_id = str(window_region.as_pointer())

                # Update region key to use new format
                old_key = region_state.region_key
                new_key = f"{area.type}_{str(window_region.as_pointer())}_selection_sets"
                region_state.region_key = new_key

                migrated_count += 1
                dprint(f"[MIGRATE] Migrated region state: {old_key} -> {new_key}")
                dprint(f"[MIGRATE] Corner: {corner_type}, distances: ({dist_x}, {dist_y})")

        except Exception as e:
            dprint(f"Error migrating region state: {e}")
            continue

    if migrated_count > 0:
        dprint(f"[MIGRATE] Successfully migrated {migrated_count} region states to corner-based positioning")


def cleanup_legacy_region_states(context):
    """Clean up region states that use legacy key format"""
    if not hasattr(context.scene, "amp_anim_set"):
        return

    scene_props = context.scene.amp_anim_set
    corner_funcs = import_corner_functions()
    if not corner_funcs:
        return

    # First, migrate any remaining legacy states
    migrate_region_states_to_corner_based(context)

    # Build a set of current valid window region IDs
    valid_window_regions = set()
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            window_region = corner_funcs["get_window_region_from_area"](area)
            if window_region:
                valid_window_regions.add(str(window_region.as_pointer()))

    # Find states to remove
    states_to_remove = []
    for i, state in enumerate(scene_props.region_states):
        # Remove if it's using legacy key format (contains area pointer)
        if "_" in state.region_key:
            key_parts = state.region_key.split("_")
            if len(key_parts) >= 3:
                # Check if it's an old format with area pointer
                try:
                    # If the second part looks like an area pointer (long number), it's legacy
                    int(key_parts[1])
                    if len(key_parts) > 3 and key_parts[2] == "WINDOW":
                        # This is definitely legacy format: AREA_TYPE_AREA_PTR_WINDOW_REGION_PTR_PANEL
                        states_to_remove.append(i)
                        continue
                except ValueError:
                    pass

        # Remove if window region ID is no longer valid
        if (
            hasattr(state, "window_region_id")
            and state.window_region_id
            and state.window_region_id not in valid_window_regions
        ):
            states_to_remove.append(i)

    # Remove in reverse order to maintain indices
    for i in reversed(states_to_remove):
        dprint(f"[CLEANUP] Removing legacy region state: {scene_props.region_states[i].region_key}")
        scene_props.region_states.remove(i)

    if states_to_remove:
        dprint(f"[CLEANUP] Removed {len(states_to_remove)} legacy region states")


def cleanup_stale_cache_entries(context):
    """Clean up cache entries for areas/windows that no longer exist."""
    global region_cache, last_window_dimensions

    # Get current valid area IDs
    valid_area_ids = set()
    valid_window_ids = set()
    for window in context.window_manager.windows:
        valid_window_ids.add(str(window.as_pointer()))
        for area in window.screen.areas:
            valid_area_ids.add(str(area.as_pointer()))

    # Remove stale area cache entries
    stale_areas = [area_id for area_id in region_cache.keys() if area_id not in valid_area_ids]
    for area_id in stale_areas:
        del region_cache[area_id]

    # Remove stale window cache entries
    stale_windows = [window_id for window_id in last_window_dimensions.keys() if window_id not in valid_window_ids]
    for window_id in stale_windows:
        del last_window_dimensions[window_id]

    if stale_areas or stale_windows:
        dprint(f"[CACHE] Cleaned {len(stale_areas)} stale area entries and {len(stale_windows)} stale window entries")


def ensure_single_region_state_per_window(context):
    """Ensure only one region state exists per WINDOW region - cleanup duplicates."""
    if not hasattr(context.scene, "amp_anim_set"):
        return

    scene_props = context.scene.amp_anim_set

    # Build a map of window_region_id -> region_state
    window_states = {}
    states_to_remove = []

    for i, state in enumerate(scene_props.region_states):
        if hasattr(state, "window_region_id") and state.window_region_id:
            window_id = state.window_region_id
            if window_id in window_states:
                # Duplicate found - keep the first one, mark others for removal
                states_to_remove.append(i)
                dprint(f"[CLEANUP] Found duplicate region state for window {window_id}")
            else:
                window_states[window_id] = state
        elif state.region_key.startswith("WINDOW_"):
            # Extract window ID from key for new format
            parts = state.region_key.split("_")
            if len(parts) >= 2:
                window_id = parts[1]
                if window_id in window_states:
                    states_to_remove.append(i)
                else:
                    window_states[window_id] = state

    # Remove duplicates in reverse order to maintain indices
    for i in reversed(states_to_remove):
        scene_props.region_states.remove(i)

    if states_to_remove:
        dprint(f"[CLEANUP] Removed {len(states_to_remove)} duplicate region states")


# Performance optimization: track which areas have changed
_changed_areas = set()


def redraw_changed_areas_only(context):
    """Redraw only areas that have actually changed instead of all areas."""
    global _changed_areas
    if not _changed_areas:
        return

    # Only redraw areas that actually changed
    redrawn_count = 0
    for area_id in _changed_areas:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if str(area.as_pointer()) == area_id:
                    area.tag_redraw()
                    redrawn_count += 1
                    break

    # Clear the changed areas set
    _changed_areas.clear()

    if redrawn_count > 0:
        dprint(f"[PERF] Redrawn {redrawn_count} changed areas instead of all areas")


def mark_area_changed(area_id):
    """Mark an area as changed for optimized redrawing."""
    global _changed_areas
    _changed_areas.add(area_id)


def redraw_gui_areas_only(context):
    """Redraw only areas that have GUI elements (supported area types)."""
    redrawn_count = 0

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if is_supported_area_type(area.type):
                area.tag_redraw()
                redrawn_count += 1

    dprint(f"[PERF] Redrawn GUI areas instead of all areas")


def update_debug_state(context):
    """Update debug state with current information"""
    global debug_state

    # Get tracker data
    tracker_data = get_tracker_data(context)
    debug_state["tracker_active"] = is_tracker_active(context)
    debug_state["gui_enabled"] = gui_state.get("show_pinned_gui", False)

    if tracker_data:
        debug_state["mouse_pos"] = tracker_data.get("window_pos", (0, 0))
        debug_state["region_pos"] = tracker_data.get("region_pos", (0, 0))
        debug_state["area_type"] = tracker_data.get("area_type", "Unknown")
        debug_state["region_type"] = tracker_data.get("region_type", "Unknown")

    # Get preset info
    if hasattr(context.scene, "amp_anim_set"):
        scene_props = context.scene.amp_anim_set
        debug_state["preset_count"] = len(scene_props.presets)

        if scene_props.active_preset_index >= 0 and scene_props.active_preset_index < len(scene_props.presets):
            preset = scene_props.presets[scene_props.active_preset_index]
            debug_state["pinned_sets_count"] = len([s for s in preset.sets if s.pinned])
        else:
            debug_state["pinned_sets_count"] = 0
    else:
        debug_state["preset_count"] = 0
        debug_state["pinned_sets_count"] = 0

    # Get draw handlers count
    from .floating_panels import _draw_handlers

    debug_state["draw_handlers_count"] = len(_draw_handlers)

    import time

    debug_state["last_draw_time"] = time.time()


def check_grabber_collision(context, gui_x, gui_y, width, height):
    """Check if mouse is over the grabber using tracker data"""

    # Only process hover states when mouse is in a valid region
    if not is_mouse_in_valid_region():
        return False

    # Get mouse position in region coordinates
    mouse_x, mouse_y = tracker_data.get("region_pos", (0, 0))

    # Simple box collision
    return simple_box_collision(gui_x, gui_y, width, height, mouse_x, mouse_y)


def check_set_collision(context, gui_x, gui_y, width, height, set_index):
    """Check if mouse is over a selection set using tracker data"""

    # Only process hover states when mouse is in a valid region
    if not is_mouse_in_valid_region():
        return False

    # Get mouse position in region coordinates
    mouse_x, mouse_y = tracker_data.get("region_pos", (0, 0))

    # Simple box collision
    return simple_box_collision(gui_x, gui_y, width, height, mouse_x, mouse_y)


def compute_button_boxes(gui_x, gui_y, dims, region_state, preset):
    """
    Compute bounding boxes for each selection set button (idx, x, y, width, height)
    """
    vertical_pad = dims["vertical_padding"]
    horizontal_pad = dims["horizontal_padding"]
    gui_height = dims["height"]
    panel_width = dims["panel_width"]
    box_padding = dims["box_padding"]

    # Organize by row
    rows = {}
    pinned_sets = [s for s in preset.sets if s.pinned]
    for idx, anim_set in enumerate(pinned_sets):
        row_idx = getattr(anim_set, "row", 1)
        rows.setdefault(row_idx, []).append((idx, anim_set))
    sorted_rows = sorted(rows.items(), key=lambda x: x[0])
    n_rows = len(sorted_rows)

    # Block height using vertical padding
    block_height = n_rows * gui_height + max(0, (n_rows - 1) * vertical_pad)

    # Determine block top and bottom with padding adjustment
    if region_state.vertical_alignment == "bottom":
        block_bottom = gui_y + box_padding
        block_top = block_bottom + block_height
    else:
        block_top = gui_y + dims["height"] - box_padding
        block_bottom = block_top - block_height
    boxes = []

    # Iterate rows
    for row_i, (_, items) in enumerate(sorted_rows):
        items.sort(key=lambda tup: tup[1].priority)
        count = len(items)
        if count == 0:
            continue

        # Calculate button width using horizontal padding
        total_horizontal_pad = horizontal_pad * (count - 1)
        set_w = (panel_width - total_horizontal_pad) / count

        # Horizontal start with padding adjustment
        if region_state.alignment == "left":
            start_x = gui_x - panel_width - horizontal_pad - box_padding
        else:
            start_x = gui_x + dims["grabber_width"] + horizontal_pad + box_padding

        # Row Y position using vertical padding
        row_y = block_top - gui_height - row_i * (gui_height + vertical_pad)
        cur_x = start_x

        for idx, anim_set in items:
            boxes.append((idx, cur_x, row_y, set_w, gui_height))
            cur_x += set_w + horizontal_pad
    return boxes


def calculate_button_block_bounds(gui_x, gui_y, dims, region_state, preset):
    """
    Calculate the bounding box for all selection set buttons combined.
    Returns (x, y, width, height) for the entire button block.
    This is a wrapper around compute_button_boxes to get the overall bounds.
    """
    # Get pinned sets
    pinned_sets = [s for s in preset.sets if s.pinned]
    if not pinned_sets:
        return None

    # Get padding values
    panel_width = dims["panel_width"]
    horizontal_pad = dims["horizontal_padding"]
    vertical_pad = dims["vertical_padding"]
    gui_height = dims["height"]
    box_padding = dims["box_padding"]

    # Organize pinned sets by row (same logic as compute_button_boxes)
    rows = {}
    for idx, anim_set in enumerate(pinned_sets):
        row_idx = getattr(anim_set, "row", 1)
        rows.setdefault(row_idx, []).append((idx, anim_set))

    # Sort rows by row index (1 = top)
    sorted_rows = sorted(rows.items(), key=lambda x: x[0])
    n_rows = len(sorted_rows)
    block_height = n_rows * gui_height + max(0, (n_rows - 1) * vertical_pad)

    # Compute block vertical positions relative to grabber with padding adjustment
    if region_state.vertical_alignment == "bottom":
        # Panel above grabber: bottom aligns with grabber bottom, moved up by padding
        block_bottom = gui_y + box_padding
        block_top = block_bottom + block_height
    else:
        # Panel below grabber: top aligns with grabber top, moved down by padding
        block_top = gui_y + gui_height - box_padding
        block_bottom = block_top - block_height

    # Calculate horizontal position with padding adjustment
    if region_state.alignment == "left":
        block_x = gui_x - panel_width - horizontal_pad - box_padding
    else:
        block_x = gui_x + dims["grabber_width"] + horizontal_pad + box_padding

    # Apply padding to the block bounds (outward padding)
    block_x -= box_padding
    block_bottom -= box_padding
    block_width = panel_width + (2 * box_padding)
    block_height = block_height + (2 * box_padding)

    return (block_x, block_bottom, block_width, block_height)


def get_grabber_position_from_region_state(context, area, region, region_state):
    """Get grabber position from region state using corner-based positioning"""
    if not region_state:
        return (50, 50)  # Default position

    # Get the window region for coordinate calculation
    window_region = get_window_region_from_area(area)
    if not window_region:
        # Fallback to legacy position if window region not available
        return (region_state.gui_position_x, region_state.gui_position_y)

    # Calculate position from corner-based data
    try:
        corner_type = region_state.corner_type if hasattr(region_state, "corner_type") else "bottom_right"
        dist_x = region_state.corner_distance_x if hasattr(region_state, "corner_distance_x") else 50
        dist_y = region_state.corner_distance_y if hasattr(region_state, "corner_distance_y") else 50

        # Additional safety: constrain distances to ensure quadrant positioning
        # This handles cases where saved distances are from larger windows
        clamped_dist_x, clamped_dist_y = constrain_distances_to_quadrant(window_region, corner_type, dist_x, dist_y)

        position = calculate_position_from_corner(window_region, corner_type, clamped_dist_x, clamped_dist_y)

        # Ensure position is within bounds
        x, y = position
        x = max(0, min(x, window_region.width - 10))  # Keep 10px margin
        y = max(0, min(y, window_region.height - 10))

        return (x, y)

    except Exception as e:
        dprint(f"Error calculating corner-based position: {e}")
        # Fallback to legacy position
        return (region_state.gui_position_x, region_state.gui_position_y)


def get_optimal_alignment_from_position(grabber_x, grabber_y, window_width, window_height):
    """
    Determine the optimal alignment based on the grabber's position in the window.
    Makes the panel point towards the center of the window.

    Args:
        grabber_x: X position of the grabber in the window region
        grabber_y: Y position of the grabber in the window region
        window_width: Width of the window region
        window_height: Height of the window region

    Returns:
        tuple: (horizontal_alignment, vertical_alignment)
    """
    # Calculate normalized position (0.0 to 1.0)
    norm_x = grabber_x / window_width if window_width > 0 else 0.5
    norm_y = grabber_y / window_height if window_height > 0 else 0.5

    # Determine horizontal alignment (panel goes opposite direction)
    # If grabber is in left half, panel goes right; if in right half, panel goes left
    horizontal_alignment = "right" if norm_x < 0.5 else "left"

    # Determine vertical alignment (panel goes opposite direction)
    # If grabber is in lower half, panel goes up; if in upper half, panel goes down
    vertical_alignment = "bottom" if norm_y < 0.5 else "top"

    return horizontal_alignment, vertical_alignment


def update_alignment_during_drag(context, tracked_area, tracked_region, region_state, new_x, new_y):
    """
    Update the alignment during dragging based on the grabber's position.
    Only updates the specific region state for the area being dragged, not all areas of the same type.

    Args:
        context: Blender context
        tracked_area: The area being tracked
        tracked_region: The region being tracked
        region_state: The region state object
        new_x: New X position of the grabber
        new_y: New Y position of the grabber
    """
    # Get window region dimensions
    window_region = None
    for region in tracked_area.regions:
        if region.type == "WINDOW":
            window_region = region
            break

    if not window_region:
        return  # Can't determine alignment without window region

    # Get optimal alignment based on position
    new_horizontal, new_vertical = get_optimal_alignment_from_position(
        new_x, new_y, window_region.width, window_region.height
    )

    # Only update if alignment changed to avoid unnecessary updates
    if region_state.alignment != new_horizontal or region_state.vertical_alignment != new_vertical:
        
        # Update ONLY the specific region state for this area, not all areas of the same type
        region_state.alignment = new_horizontal
        region_state.vertical_alignment = new_vertical

        dprint(f"[DRAG_ALIGN] Auto-updated alignment for area {tracked_area.as_pointer()} to: {new_horizontal}, vertical: {new_vertical}")


def handle_mouse_event(context, event):
    """Handle mouse events for the selection sets GUI - works across all areas"""
    try:
        from .floating_panels import tracker_data, gui_state

        # Only handle events when mouse is in a WINDOW region
        region_type = tracker_data.get("region_type", "Unknown")
        if region_type != "WINDOW" or region_type in {"HEADER", "TOOL_HEADER", "UI", "TOOLS", "PREVIEW"}:
            return False

        # Get the area that's currently being tracked (where the mouse is)
        current_area_id = tracker_data.get("area_id", "Unknown")
        if current_area_id == "Unknown":
            return False

        # Find the area being tracked
        tracked_area = None
        tracked_region = None
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if str(area.as_pointer()) == current_area_id:
                    tracked_area = area
                    # Find the WINDOW region in this area
                    for region in area.regions:
                        if region.type == "WINDOW":
                            tracked_region = region
                            break
                    break
            if tracked_area:
                break

        if not tracked_area or not tracked_region:
            return False

        # Only handle events in supported areas with WINDOW regions
        # Exclude HEADER and TOOL_HEADER regions to avoid false positives
        supported_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
        if (
            tracked_area.type not in supported_types
            or tracked_region.type != "WINDOW"
            or tracked_region.type in {"HEADER", "TOOL_HEADER", "UI", "TOOLS", "PREVIEW"}
        ):
            return False

        # Check if GUI should be displayed
        if not gui_state.get("show_gui", False):
            return False

        # Get scene data
        scene = bpy.context.scene
        if not hasattr(scene, "amp_anim_set"):
            return False

        scene_props = scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return False

        preset = scene_props.presets[scene_props.active_preset_index]

        # Get region state for the tracked area
        region_state = get_stored_region_state(context, tracked_area, tracked_region, "selection_sets")
        if not region_state:
            return False

        # Get GUI position from stored state using corner-based positioning
        gui_x, gui_y = get_grabber_position_from_region_state(context, tracked_area, tracked_region, region_state)
        collapsed = region_state.collapsed
        # Get hidden state - if hidden property doesn't exist, default to False (not hidden)
        hidden = getattr(region_state, "hidden", False)

        # Calculate GUI dimensions
        dims = get_scaled_gui_dimensions()
        gui_height = dims["height"]
        # Compute vertical offset for selection sets based on vertical_alignment
        pad = dims["padding"]
        v_align = region_state.vertical_alignment if hasattr(region_state, "vertical_alignment") else "bottom"
        if v_align == "bottom":
            set_y = gui_y + gui_height + pad
        else:
            set_y = gui_y - gui_height - pad

        # Get mouse position in region coordinates
        mouse_x, mouse_y = tracker_data.get("region_pos", (0, 0))

        # Additional safety check - only process mouse events in WINDOW regions
        current_region_type = tracker_data.get("region_type", "Unknown")
        if current_region_type != "WINDOW" or current_region_type in {
            "HEADER",
            "TOOL_HEADER",
            "UI",
            "TOOLS",
            "PREVIEW",
        }:
            return False

        # Handle left mouse button press
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            # Check grabber collision
            if check_grabber_collision(context, gui_x, gui_y, dims["grabber_width"], gui_height):
                # Start dragging
                gui_state["dragging_grabber"] = True
                gui_state["drag_offset"] = (mouse_x - gui_x, mouse_y - gui_y)
                gui_state["drag_area_id"] = current_area_id
                gui_state["drag_started"] = False  # Reset drag started flag
                dprint(f"[LMB_CLICK] Started grabber drag at ({mouse_x}, {mouse_y})")
                return True

            # Check selection set clicks if not hidden and not collapsed
            if not hidden and not collapsed:
                # Block-based click detection for selection sets
                boxes = compute_button_boxes(gui_x, gui_y, dims, region_state, preset)
                for idx, bx, by, bw, bh in boxes:
                    if simple_box_collision(bx, by, bw, bh, mouse_x, mouse_y):
                        handle_selection_set_click(context, idx, event)
                        return True

        elif event.type == "RIGHTMOUSE" and event.value == "PRESS":
            # Check grabber collision
            if check_grabber_collision(context, gui_x, gui_y, dims["grabber_width"], gui_height):
                # If hidden, first RMB click should unhide
                if hidden:
                    create_or_update_region_state(
                        context, tracked_area, tracked_region, None, None, False, "selection_sets"
                    )
                    dprint("[RMB_CLICK] Unhid grabber from hidden state")
                    # Redraw all areas
                    from .floating_panels import redraw_all_areas

                    redraw_all_areas()
                    return True  # Event consumed
                else:
                    # Right-click on visible grabber - for now, just redraw
                    # (Alignment is now handled automatically during dragging)
                    from .floating_panels import redraw_all_areas

                    redraw_all_areas()
                    return True  # Event consumed

            # Block-based right-click detection for selection sets
            if not hidden and not collapsed:
                boxes = compute_button_boxes(gui_x, gui_y, dims, region_state, preset)
                for idx, bx, by, bw, bh in boxes:
                    if simple_box_collision(bx, by, bw, bh, mouse_x, mouse_y):
                        handle_selection_set_click(context, idx, event)
                        return True

        elif event.type == "MOUSEMOVE":
            # Update hover states for grabber and selection sets using block alignment
            is_grabber_hovered = check_grabber_collision(context, gui_x, gui_y, dims["grabber_width"], gui_height)
            hovered_element = None
            if is_grabber_hovered:
                hovered_element = "grabber"
            elif not collapsed:
                # Block-based hover detection using helper
                boxes = compute_button_boxes(gui_x, gui_y, dims, region_state, preset)
                for idx, bx, by, bw, bh in boxes:
                    if simple_box_collision(bx, by, bw, bh, mouse_x, mouse_y):
                        hovered_element = idx

                        break

            # Update hover state
            prev_hovered = gui_state.get("hovered_element")
            gui_state["hovered_element"] = hovered_element

            # Redraw if hover state changed
            if prev_hovered != hovered_element:
                tracked_area.tag_redraw()

            # Handle dragging
            if gui_state.get("dragging_grabber", False):
                # Only allow dragging if we're in the same area where dragging started
                if current_area_id == gui_state.get("drag_area_id", ""):
                    drag_offset = gui_state.get("drag_offset", (0, 0))

                    # Calculate new position
                    new_x = mouse_x - drag_offset[0]
                    new_y = mouse_y - drag_offset[1]

                    # Find the window region specifically for constraint
                    window_region = None
                    for region in tracked_area.regions:
                        if region.type == "WINDOW":
                            window_region = region
                            break

                    if window_region:
                        # Apply constraint BEFORE checking drag threshold
                        try:
                            from .floating_panels import constrain_to_window_region

                            new_x, new_y = constrain_to_window_region(
                                context, tracked_area, new_x, new_y, dims["grabber_width"], gui_height
                            )
                        except ImportError:
                            # Fallback to old method (only grabber dimensions are considered)
                            new_x, new_y = keep_gui_in_region(
                                new_x, new_y, dims["grabber_width"], gui_height, tracked_region
                            )

                        # Mark that we've started dragging (for distinguishing from click)
                        if not gui_state.get("drag_started", False):
                            # Check if we've moved enough to consider this a drag
                            initial_pos = (gui_x, gui_y)
                            current_pos = (new_x, new_y)
                            distance = (
                                (current_pos[0] - initial_pos[0]) ** 2 + (current_pos[1] - initial_pos[1]) ** 2
                            ) ** 0.5
                            if distance > 0:  # 5 pixel threshold
                                gui_state["drag_started"] = True
                                dprint(f"[DRAG] Started dragging grabber at ({new_x}, {new_y})")

                        # Auto-update alignment based on grabber position during drag
                        if gui_state.get("drag_started", False):
                            update_alignment_during_drag(
                                context, tracked_area, tracked_region, region_state, new_x, new_y
                            )

                        # Update stored position
                        create_or_update_region_state(
                            context, tracked_area, tracked_region, (new_x, new_y), None, "selection_sets"
                        )

                        # Redraw
                        tracked_area.tag_redraw()
                        return True  # Event consumed

        # Handle mouse release
        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            if gui_state.get("dragging_grabber", False):
                # Check if we actually dragged or just clicked
                drag_started = gui_state.get("drag_started", False)

                if not drag_started:
                    # This was a click, not a drag - toggle collapse state
                    current_collapsed = getattr(region_state, "collapsed", False)
                    new_collapsed = not current_collapsed
                    create_or_update_region_state(
                        context, tracked_area, tracked_region, None, new_collapsed, None, "selection_sets"
                    )
                    dprint(f"[CLICK] Toggled collapse state to: {new_collapsed}")
                else:
                    dprint("[DRAG] Finished dragging grabber")

                # Clean up dragging state
                gui_state["dragging_grabber"] = False
                gui_state["drag_offset"] = (0, 0)
                gui_state["drag_area_id"] = ""
                gui_state["drag_started"] = False

                # Redraw all areas
                from .floating_panels import redraw_all_areas

                redraw_all_areas()

                return True  # Event consumed

    except Exception as e:
        dprint(f"[MOUSE] Error handling mouse event: {e}")
        import traceback

        traceback.print_exc()
        return False

    return False  # Event not consumed


class AMP_OT_FloatingPanelsTracker(Operator):
    """Simplified modal operator for mouse tracking and GUI display."""

    bl_idname = "wm.amp_floating_panels_tracker"
    bl_label = "Floating Panels Tracker"

    # Property to specify which panel to move grabber for
    panel_name: StringProperty(
        name="Panel Name",
        description="Name of the panel to move grabber for (e.g., 'selection_sets')",
        default="selection_sets",
    )

    popup: BoolProperty(
        name="Popup Mode",
        description="Enable popup mode for the tracker",
        default=False,
    )

    _cancel_requested = False

    def _handle_existing_modal(self, context, event):
        """Handle logic when a modal is already active."""
        if AMP_OT_FloatingPanelsTracker._cancel_requested:
            # Cancel the existing tracker
            global _active_modal
            _active_modal.cancel(context)
            _active_modal = None
            AMP_OT_FloatingPanelsTracker._cancel_requested = False
            return {"CANCELLED"}
        else:
            # Normal behavior when tracker is already running
            # Always move grabber to mouse cursor when tracker is running
            mx, my = event.mouse_x, event.mouse_y
            area, region, local_pos = get_region_under_mouse(context, mx, my)

            if area and region:
                aid = str(area.as_pointer())
                rid = str(region.as_pointer())

                # Update tracker data with current mouse position
                tracker_data.update(
                    {
                        "window_pos": (mx, my),
                        "region_pos": local_pos,
                        "area_type": area.type,
                        "region_type": region.type,
                        "area_id": aid,
                        "region_id": rid,
                        "debug_info": f"reg({region.x},{region.y}) size({region.width}x{region.height})",
                        "last_valid_area_id": aid,
                    }
                )

                # Check if mouse is in a valid area and move grabber to mouse cursor
                if self._should_move_grabber_to_mouse(context, tracker_data):
                    # Ensure GUI is enabled
                    gui_state["show_gui"] = True
                    if hasattr(context.scene, "amp_anim_set"):
                        context.scene.amp_anim_set.display_gui = True

                    # Ensure draw handler exists in current area
                    ensure_draw_handler_for_area(area)

                    # Handle popup mode vs normal mode
                    if self.popup:
                        # Popup mode: center the entire panel on the mouse cursor
                        self._position_panel_at_mouse(context, tracker_data, self.panel_name, center_entire_panel=True)
                        dprint(f"[TRACKER_POPUP] Centered panel on mouse cursor for '{self.panel_name}'")
                    else:
                        # Normal mode: move grabber to mouse cursor with same validation as dragging
                        # Get current mouse position in region coordinates
                        mouse_x, mouse_y = local_pos

                        # Find the window region for constraint validation
                        window_region = None
                        for reg in area.regions:
                            if reg.type == "WINDOW":
                                window_region = reg
                                break

                        if window_region:
                            # Get dimensions for constraint validation
                            dims = get_scaled_gui_dimensions()
                            gui_height = dims["height"]
                            grabber_width = dims["grabber_width"]

                            # Apply the same constraint validation as in dragging
                            try:
                                new_x, new_y = constrain_to_window_region(
                                    context, area, mouse_x, mouse_y, grabber_width, gui_height
                                )
                            except:
                                # Fallback to keeping GUI in region bounds
                                new_x, new_y = keep_gui_in_region(
                                    mouse_x, mouse_y, grabber_width, gui_height, window_region
                                )

                            # Center the grabber at the constrained position
                            centered_x = new_x - (grabber_width // 2)
                            centered_y = new_y - (gui_height // 2)

                            # Apply constraint again to the centered position
                            try:
                                final_x, final_y = constrain_to_window_region(
                                    context, area, centered_x, centered_y, grabber_width, gui_height
                                )
                            except:
                                final_x, final_y = keep_gui_in_region(
                                    centered_x, centered_y, grabber_width, gui_height, window_region
                                )

                            # Update the position using the same system as dragging
                            create_or_update_region_state(
                                context, area, window_region, (int(final_x), int(final_y)), None, self.panel_name
                            )

                            # Auto-update alignment like during dragging
                            region_state = get_stored_region_state(context, area, window_region, self.panel_name)
                            if region_state:
                                update_alignment_during_drag(
                                    context, area, window_region, region_state, final_x, final_y
                                )

                            dprint(
                                f"[TRACKER] Moved grabber to mouse cursor for '{self.panel_name}' at ({final_x}, {final_y})"
                            )
                        else:
                            dprint(f"[TRACKER] No WINDOW region found in area {area.type}")
                            return {"CANCELLED"}

                    # Force redraw to show the new position
                    redraw_all_areas()
                    return {"FINISHED"}
                else:
                    dprint(f"[TRACKER] Mouse not in valid area: {area.type} {region.type}")
                    return {"CANCELLED"}
            else:
                dprint("[TRACKER] Could not find area/region under mouse")
                return {"CANCELLED"}

    def invoke(self, context, event):
        global _active_modal
        if _active_modal:
            return self._handle_existing_modal(context, event)

        _active_modal = self
        wm = context.window_manager
        # No timer needed - we respond to actual mouse events
        wm.modal_handler_add(self)

        # Check if the specified panel is registered
        if self.panel_name not in _panel_registry:
            dprint(f"[TRACKER] Panel '{self.panel_name}' not registered in panel registry")
            return {"CANCELLED"}

        # Activate the specific panel
        set_panel_active(self.panel_name, True)
        dprint(f"[TRACKER] Activated panel: {self.panel_name}")

        # Enable GUI and scene property
        gui_state["show_gui"] = True
        if hasattr(context.scene, "amp_anim_set"):
            context.scene.amp_anim_set.display_gui = True

        # Position the panel at mouse cursor
        mx, my = event.mouse_x, event.mouse_y
        area, region, local_pos = get_region_under_mouse(context, mx, my)
        if area and region:
            aid = str(area.as_pointer())
            rid = str(region.as_pointer())

            # Update tracker data with current mouse position
            tracker_data.update(
                {
                    "window_pos": (mx, my),
                    "region_pos": local_pos,
                    "area_type": area.type,
                    "region_type": region.type,
                    "area_id": aid,
                    "region_id": rid,
                    "debug_info": f"reg({region.x},{region.y}) size({region.width}x{region.height})",
                    "last_valid_area_id": aid,
                }
            )

            # Check if we're in a valid area
            if self._should_move_grabber_to_mouse(context, tracker_data):
                # Handle popup mode differently from normal mode
                if self.popup:
                    # Popup mode: center the entire panel on the mouse cursor
                    self._position_panel_at_mouse(context, tracker_data, self.panel_name, center_entire_panel=True)
                    dprint(f"[POPUP] Centered panel on mouse cursor for '{self.panel_name}'")
                else:
                    # Normal mode: restore saved position or position grabber at mouse
                    # First, restore visibility and alignment for normal mode
                    self._restore_normal_mode_visibility_and_alignment(context, area, self.panel_name)

                    # Then try to restore saved position or position at mouse
                    if not self._restore_saved_position_for_area(context, area, self.panel_name):
                        # No saved position found, position at mouse
                        self._position_panel_at_mouse(context, tracker_data, self.panel_name, center_entire_panel=False)
                        # Evaluate corner alignment after positioning
                        self._evaluate_corner_alignment_for_area(context, area, self.panel_name)
                        dprint(
                            f"[NORMAL] No saved position found, positioned panel at mouse cursor for '{self.panel_name}'"
                        )
                    else:
                        # Successfully restored saved position, but still ensure alignment is optimal
                        self._evaluate_corner_alignment_for_area(context, area, self.panel_name)
                        dprint(f"[NORMAL] Restored saved position for '{self.panel_name}'")
            else:
                dprint(f"[NORMAL] Mouse not in valid area for positioning: {area.type} {region.type}")
        else:
            dprint("[NORMAL] Could not find area/region under mouse for positioning")

        # Refresh UI state immediately after positioning to update hover states
        self._refresh_ui_state_after_invoke(context, event)

        # Initialize region cache on startup
        check_all_regions_for_changes(context)

        # Ensure only one region state per window
        ensure_single_region_state_per_window(context)

        # Validate existing draw handlers on startup
        validate_draw_handlers(context)
        # Ensure draw handlers are registered for all areas so GUI will draw
        register_all_draw_handlers()

        dprint(f"[TRACKER] Started floating panels tracker for panel '{self.panel_name}' and enabled GUI")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        # Periodic validation of draw handlers to prevent accumulation
        if not hasattr(self, "_validation_counter"):
            self._validation_counter = 0

        # Only validate on specific events to reduce overhead
        should_validate = False

        if event.type in {"WINDOW_DEACTIVATE", "WINDOW_ACTIVATE"}:
            should_validate = True
        elif event.type == "MOUSEMOVE":
            self._validation_counter += 1
            # Validate handlers every 100 mouse moves instead of 50
            if self._validation_counter % 100 == 0:
                should_validate = True

        if should_validate:
            validate_draw_handlers(context)

        # Only respond to actual mouse events - no timer needed
        if event.type == "MOUSEMOVE":
            global_mouse_handler(context, event)  # Handle global mouse events for dragging
            if handle_global_mouse_event(context, event):
                return {"RUNNING_MODAL"}  # Event was handled by global handler

            # Also forward to selection sets GUI for dragging
            try:
                if handle_mouse_event(context, event):
                    return {"RUNNING_MODAL"}  # Event was handled
            except ImportError:
                pass

        elif event.type in {"D"} and event.value == "PRESS":
            # Toggle debug with Ctrl+Alt+D
            if event.ctrl and event.alt:
                tracker_data["show_debug"] = not tracker_data["show_debug"]

                redraw_all_areas()
                dprint(f"[TRACKER] Debug toggled: {tracker_data['show_debug']}")
                # Also update GUI debug state
                try:
                    from .anim_selection_sets_gui import debug_state

                    debug_state["show_debug"] = tracker_data["show_debug"]
                except ImportError:
                    pass

        elif event.type in {"H"} and event.value == "PRESS":
            # Print handler statistics with Ctrl+Alt+H
            if event.ctrl and event.alt:
                debug_print_handler_stats()
                validate_draw_handlers(context)
                dprint("[TRACKER] Handler validation completed")

        # Handle mouse events for selection sets GUI
        elif event.type in {"LEFTMOUSE", "RIGHTMOUSE"} and event.value in {"PRESS", "RELEASE"}:
            # Forward mouse events to selection sets GUI first
            try:
                if handle_mouse_event(context, event):
                    return {"RUNNING_MODAL"}  # Event was handled by GUI

            except ImportError:
                pass

            # Global LMB release detection to stop dragging anywhere in Blender (fallback)
            if event.type == "LEFTMOUSE" and event.value == "RELEASE":
                if gui_state["dragging_grabber"]:
                    dprint("[DRAG] Stopped drag on global LMB release (fallback)")
                    gui_state["dragging_grabber"] = False
                    gui_state["drag_started"] = False
                    gui_state["hovered_element"] = None
                    gui_state["drag_area_id"] = ""
                    redraw_all_areas()
                    return {"RUNNING_MODAL"}

        # Check for window/region changes only when dragging or during critical window events
        elif event.type in {"WINDOW_DEACTIVATE", "WINDOW_ACTIVATE"}:
            # Validate handlers on window events to catch area destruction
            validate_draw_handlers(context)
            check_regions_when_needed(context)
        elif event.type == "MOUSEMOVE" and gui_state["dragging_grabber"]:
            # Check for region changes during drag to handle window resizing
            check_regions_when_needed(context)

        return {"PASS_THROUGH"}

    def _should_move_grabber_to_mouse(self, context, tracker_info):
        """Check if the button box should be moved to the mouse position."""
        # Check if mouse is in a valid area type
        if not is_supported_area_type(tracker_info["area_type"]):
            dprint(f"[GRAB_MOVE] Area type {tracker_info['area_type']} not supported for grabber movement")
            return False

        # Check if mouse is in a WINDOW region
        if not is_valid_region_type(tracker_info["region_type"]):
            dprint(f"[GRAB_MOVE] Region type {tracker_info['region_type']} not WINDOW for grabber movement")
            return False

        # For normal mode, always allow movement when tracker is running
        # (the caller handles enabling GUI state)
        dprint(f"[GRAB_MOVE] Valid area for grabber movement: {tracker_info['area_type']} WINDOW")
        return True

    def _position_panel_at_mouse(self, context, tracker_info, panel_name="selection_sets", center_entire_panel=False):
        """
        Universal panel positioning function.

        Args:
            center_entire_panel: If True, centers the entire panel (popup mode).
                                If False, centers only the grabber (normal mode).
        """
        # Find the area where the mouse is located
        area = None
        for window in context.window_manager.windows:
            for a in window.screen.areas:
                if str(a.as_pointer()) == tracker_info["area_id"]:
                    area = a
                    break
            if area:
                break

        if not area:
            dprint(f"[PANEL_POS] Could not find area with ID {tracker_info['area_id']}")
            return

        # Find the WINDOW region
        window_region = get_window_region_from_area(area)
        if not window_region:
            dprint(f"[PANEL_POS] Could not find WINDOW region in area {area.type}")
            return

        # Get current mouse position in region coordinates
        mouse_x, mouse_y = tracker_info["region_pos"]

        try:
            # Get scene data for panel calculations
            scene = context.scene
            if not hasattr(scene, "amp_anim_set"):
                dprint("[PANEL_POS] No amp_anim_set in scene")
                return

            scene_props = scene.amp_anim_set
            if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
                dprint("[PANEL_POS] No active preset")
                return

            preset = scene_props.presets[scene_props.active_preset_index]
            pinned_sets = [s for s in preset.sets if s.pinned]

            if not pinned_sets:
                dprint("[PANEL_POS] No pinned sets to position")
                return

            # Get or create region state
            region_state = get_stored_region_state(context, area, window_region, panel_name)
            if not region_state:
                region_state = create_or_update_region_state(context, area, window_region, (150, 50), None, panel_name)

            # Get GUI dimensions
            dims = get_scaled_gui_dimensions()
            grabber_width = dims["grabber_width"]
            grabber_height = dims["height"]

            if center_entire_panel:
                # POPUP MODE: Center entire panel on mouse cursor

                # Ensure panel is not collapsed for popup mode
                region_state.collapsed = False

                # Calculate panel dimensions
                panel_width = dims["panel_width"]
                horizontal_padding = dims["horizontal_padding"]
                vertical_padding = dims["vertical_padding"]
                box_padding = dims["box_padding"]

                # Calculate total panel dimensions including buttons
                total_panel_width = panel_width + (2 * box_padding)

                # Calculate panel height based on number of rows
                rows = {}
                for idx, anim_set in enumerate(pinned_sets):
                    row_idx = getattr(anim_set, "row", 1)
                    rows.setdefault(row_idx, []).append((idx, anim_set))

                n_rows = len(rows)
                total_panel_height = (
                    n_rows * grabber_height + max(0, (n_rows - 1) * vertical_padding) + (2 * box_padding)
                )

                # Calculate total dimensions: grabber + spacing + panel
                total_width = grabber_width + horizontal_padding + total_panel_width
                total_height = max(grabber_height, total_panel_height)

                # Calculate where the grabber should be positioned to center the panel on the mouse
                panel_center_x = total_width / 2
                panel_center_y = total_height / 2
                grabber_target_x = mouse_x - panel_center_x
                grabber_target_y = mouse_y - panel_center_y

                # Determine optimal alignment and adjust position
                alignment, vert_align = get_optimal_alignment_from_position(
                    mouse_x, mouse_y, window_region.width, window_region.height
                )

                # Adjust grabber position based on alignment
                if alignment == "left":
                    grabber_target_x = mouse_x - total_width + grabber_width
                else:
                    grabber_target_x = mouse_x - grabber_width

                if vert_align == "top":
                    grabber_target_y = mouse_y - total_height + grabber_height
                else:
                    grabber_target_y = mouse_y - grabber_height

                final_x, final_y = grabber_target_x, grabber_target_y

                # Update region state with calculated alignment
                region_state.alignment = alignment
                region_state.vertical_alignment = vert_align

                mode_text = "popup (entire panel centered)"
            else:
                # NORMAL MODE: Center grabber on mouse cursor
                collapsed = region_state.collapsed if region_state else False

                centered_x = mouse_x - (grabber_width // 2)
                centered_y = mouse_y - (grabber_height // 2)
                final_x, final_y = centered_x, centered_y

                # Update alignment based on position
                alignment, vert_align = get_optimal_alignment_from_position(
                    final_x, final_y, window_region.width, window_region.height
                )
                region_state.alignment = alignment
                region_state.vertical_alignment = vert_align

                mode_text = "normal (grabber centered)"

            # Constrain the position to window bounds
            try:
                final_x, final_y = constrain_to_window_region(
                    context, area, final_x, final_y, grabber_width, grabber_height
                )
            except:
                final_x, final_y = keep_gui_in_region(final_x, final_y, grabber_width, grabber_height, window_region)

            # Store the position permanently
            create_or_update_region_state(
                context,
                area,
                window_region,
                (int(final_x), int(final_y)),
                False if center_entire_panel else None,
                panel_name,
            )

            dprint(
                f"[PANEL_POS] Positioned at ({final_x}, {final_y}) in {area.type} for panel '{panel_name}' ({mode_text})"
            )

        except Exception as e:
            dprint(f"[PANEL_POS] Error positioning panel: {e}")
            return

        # Force a redraw to show the new position
        redraw_all_areas()

    def cancel(self, context):
        global _active_modal, region_cache, last_window_dimensions, _changed_areas
        wm = context.window_manager
        # No timer to remove since we eliminated it

        # Validate handlers before cleanup to catch any stale ones
        validate_draw_handlers(context)

        # Clean up all draw handlers
        unregister_all_draw_handlers()

        # Clear all caches to prevent memory leaks
        region_cache.clear()
        last_window_dimensions.clear()
        _changed_areas.clear()

        # Clean up region states to ensure single state per window
        try:
            ensure_single_region_state_per_window(bpy.context)
        except:
            pass

        # Stop any ongoing drag operations
        stop_dragging_globally()

        redraw_all_areas()
        _active_modal = None
        dprint("[TRACKER] Stopped floating panels tracker and cleared all caches")

    def _evaluate_corner_alignment_for_area(self, context, area, panel_name):
        """Evaluate and update corner alignment for a specific area after positioning (like during dragging)."""
        try:
            from .anim_selection_sets_gui import (
                get_stored_region_state,
                get_optimal_alignment_from_position,
            )

            # Get the window region for this area
            window_region = get_window_region_from_area(area)
            if not window_region:
                dprint(f"[ALIGNMENT] No WINDOW region found for area {area.type}")
                return

            # Get the region state for this panel in this area
            region_state = get_stored_region_state(context, area, window_region, panel_name)
            if not region_state:
                dprint(f"[ALIGNMENT] No region state found for panel '{panel_name}' in area {area.type}")
                return

            # Get current grabber position
            current_x = region_state.gui_position_x
            current_y = region_state.gui_position_y

            # Calculate optimal alignment based on current position
            alignment, vert_align = get_optimal_alignment_from_position(
                current_x, current_y, window_region.width, window_region.height
            )

            # Update region state with new alignment if it changed
            if region_state.alignment != alignment or region_state.vertical_alignment != vert_align:
                region_state.alignment = alignment
                region_state.vertical_alignment = vert_align
                dprint(f"[ALIGNMENT] Updated alignment for '{panel_name}' in {area.type}: {alignment}/{vert_align}")
                # Force redraw to reflect alignment changes
                area.tag_redraw()
            else:
                dprint(
                    f"[ALIGNMENT] Alignment already optimal for '{panel_name}' in {area.type}: {alignment}/{vert_align}"
                )

        except ImportError as e:
            dprint(f"[ALIGNMENT] Could not import GUI functions for alignment evaluation: {e}")
        except Exception as e:
            dprint(f"[ALIGNMENT] Error evaluating corner alignment: {e}")

    def _refresh_ui_state_after_invoke(self, context, event):
        """Refresh UI state immediately after invoke to update hover states before requiring mouse movement."""
        try:
            # Create a fake MOUSEMOVE event at the current position to trigger hover state updates
            # This ensures the UI responds immediately without requiring the user to move the mouse
            fake_event = type(
                "Event",
                (),
                {
                    "type": "MOUSEMOVE",
                    "value": "NOTHING",
                    "mouse_x": event.mouse_x,
                    "mouse_y": event.mouse_y,
                    "mouse_region_x": getattr(event, "mouse_region_x", 0),
                    "mouse_region_y": getattr(event, "mouse_region_y", 0),
                },
            )()

            # Process the fake mouse event to update hover states
            handle_mouse_event(context, fake_event)

            # Also update the global mouse handler to ensure tracker state is current
            global_mouse_handler(context, fake_event)

            dprint("[REFRESH] UI state refreshed after invoke - hover states should be current")

        except ImportError:
            # If GUI module isn't available, just update tracker state
            global_mouse_handler(context, event)
            dprint("[REFRESH] Basic tracker state refreshed (GUI module not available)")
        except Exception as e:
            dprint(f"[REFRESH] Error refreshing UI state: {e}")

    def _restore_normal_mode_visibility_and_alignment(self, context, area, panel_name):
        """
        Restore grabber visibility and recalculate corner alignment for normal mode.
        This ensures the grabber comes back from being invisible and is properly aligned.
        """
        try:
            from .anim_selection_sets_gui import (
                get_stored_region_state,
                get_optimal_alignment_from_position,
                create_or_update_region_state,
            )

            # Get the window region for this area
            window_region = get_window_region_from_area(area)
            if not window_region:
                dprint(f"[RESTORE] No window region found for area {area.type}")
                return False

            # Get or create region state for this panel
            region_state = get_stored_region_state(context, area, window_region, panel_name)
            if not region_state:
                # Create a default region state if none exists
                # Position at center of window region
                center_x = window_region.width // 2
                center_y = window_region.height // 2
                region_state = create_or_update_region_state(
                    context, area, window_region, (center_x, center_y), None, panel_name
                )
                if not region_state:
                    dprint(f"[RESTORE] Failed to create region state for panel '{panel_name}'")
                    return False

            # Ensure grabber visibility is restored at both levels
            # 1. Global floating panels state
            gui_state["show_gui"] = True

            # 2. Scene property state
            if hasattr(context.scene, "amp_anim_set"):
                context.scene.amp_anim_set.display_gui = True

            # 3. Panel-specific state (if accessible)
            try:
                from .anim_selection_sets_gui import gui_state as panel_gui_state

                panel_gui_state["show_gui"] = True
            except ImportError:
                pass  # Panel module not available

            # Recalculate corner alignment using existing mechanisms
            current_x = region_state.gui_position_x
            current_y = region_state.gui_position_y

            # Calculate optimal alignment based on current position
            alignment, vert_align = get_optimal_alignment_from_position(
                current_x, current_y, window_region.width, window_region.height
            )

            # Update region state with recalculated alignment
            region_state.alignment = alignment
            region_state.vertical_alignment = vert_align

            # Ensure draw handler exists for this area
            ensure_draw_handler_for_area(area)

            dprint(f"[RESTORE] Restored normal mode visibility and alignment for '{panel_name}' in {area.type}")
            dprint(f"[RESTORE] Position: ({current_x}, {current_y}), Alignment: {alignment}/{vert_align}")

            return True

        except ImportError as e:
            dprint(f"[RESTORE] Could not import GUI functions for restoration: {e}")
            return False
        except Exception as e:
            dprint(f"[RESTORE] Error restoring normal mode visibility and alignment: {e}")
            return False

    def _restore_saved_position_for_area(self, context, area, panel_name):
        """Restore the saved position for the panel in the given area if it exists."""
        try:
            from .anim_selection_sets_gui import get_stored_region_state

            # Get the window region for this area
            window_region = get_window_region_from_area(area)
            if not window_region:
                dprint(f"[RESTORE] No window region found for area {area.type}")
                return False

            # Check if we have a saved region state for this area
            region_state = get_stored_region_state(context, area, window_region, panel_name)
            if region_state:
                # We have a saved state - position is already stored
                dprint(
                    f"[RESTORE] Found saved position for '{panel_name}' in {area.type}: ({region_state.gui_position_x}, {region_state.gui_position_y})"
                )
                # Evaluate corner alignment to ensure it's optimal for current window size
                self._evaluate_corner_alignment_for_area(context, area, panel_name)
                return True
            else:
                dprint(f"[RESTORE] No saved position found for '{panel_name}' in {area.type}")
                return False

        except ImportError as e:
            dprint(f"[RESTORE] Could not import GUI functions: {e}")
            return False
        except Exception as e:
            dprint(f"[RESTORE] Error restoring saved position: {e}")
            return False


# =============================================================================
# BLENDER REGISTRATION
# =============================================================================

classes = [
    AMP_OT_FloatingPanelsTracker,
]


def register():
    """Register the floating panels system with Blender."""
    for cls in classes:
        bpy.utils.register_class(cls)
    dprint("[FLOATING_PANELS] Registered floating panels system")


def unregister():
    """Unregister the floating panels system from Blender."""
    # Clean up any active modal operators
    global _active_modal
    if _active_modal:
        try:
            _active_modal.cancel(bpy.context)
        except:
            pass
        _active_modal = None

    # Clean up draw handlers
    unregister_all_draw_handlers()

    # Clear panel registry
    global _panel_registry
    _panel_registry.clear()

    # Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    dprint("[FLOATING_PANELS] Unregistered floating panels system")
