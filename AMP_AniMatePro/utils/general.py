# licence
"""
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import bpy
import blf
import gpu
import json
from gpu_extras.batch import batch_for_shader
from .. import utils
from .api import dprint
from .. import __package__ as base_package

addon_keymaps = {}
_was_save_preferences_true = False


# -----------------------------------------------------------------------------
# centralized action management
# -----------------------------------------------------------------------------
def set_amp_timeline_tools_action():
    """Get or create the internal 'amp_action' used for anim offset blending masks"""
    action = bpy.data.actions.get("amp_action")
    if action is None:
        action = bpy.data.actions.new("amp_action")
    return action


# -----------------------------------------------------------------------------
# centralized getters
# -----------------------------------------------------------------------------
def set_operator_context(op, owner_obj):
    """Sets context properties on an operator based on the owner object."""
    prefs_instance = get_prefs()

    # Determine if the owner_obj is a PopupPanelGroup instance from prefs_instance.popup_panels
    is_popup_panel_owner = False
    popup_panel_owner_index = -1

    if owner_obj != prefs_instance and hasattr(owner_obj, "categories"):
        # Check if owner_obj is actually one of the popup_panels in prefs_instance
        # This requires knowing the type of PopupPanelGroup, assuming it's imported or defined
        # For now, we'll rely on it being present in the prefs_instance.popup_panels list
        try:
            # Attempt to find owner_obj in the list of popup panels
            idx = list(prefs_instance.popup_panels).index(owner_obj)
            is_popup_panel_owner = True
            popup_panel_owner_index = idx
        except ValueError:
            # owner_obj has 'categories' and is not prefs_instance, but isn't in prefs_instance.popup_panels
            # This case should ideally not happen if owner_obj is a valid popup panel context.
            # is_popup_panel_owner = False # Or True, and log an error that index is -1.
            # For safety, if not found in list, treat as not a popup panel from prefs.
            popup_panel_owner_index = -1

    if hasattr(op, "data_owner_is_popup_panel"):
        op.data_owner_is_popup_panel = is_popup_panel_owner
    if hasattr(op, "data_owner_popup_panel_index"):
        op.data_owner_popup_panel_index = popup_panel_owner_index


def get_contextual_owner_collection_indices(context, operator):
    """
    Determines the primary owner (prefs or a PopupPanelGroup),
    the relevant category collection, and the name of its active index property.
    """
    prefs = get_prefs()
    owner = prefs
    # Default to ui_categories for prefs
    category_collection_name = "ui_categories"
    active_category_idx_prop = "active_category_index"

    if getattr(operator, "data_owner_is_popup_panel", False):
        popup_panel_idx = getattr(operator, "data_owner_popup_panel_index", -1)
        if 0 <= popup_panel_idx < len(prefs.popup_panels):
            owner = prefs.popup_panels[popup_panel_idx]
            category_collection_name = "categories"  # Popup Panels use 'categories'
            # active_category_idx_prop remains "active_category_index" as PopupPanelGroup has it

    category_collection = getattr(owner, category_collection_name, None)
    return owner, category_collection, active_category_idx_prop


def get_contextual_category(context, operator, category_idx_prop_name=None):
    """
    Gets the current category based on the operator's context.
    Uses operator.<category_idx_prop_name> if provided (e.g., 'index' for delete, 'category_index' for others).
    Otherwise, uses the active_category_idx from the owner.
    """
    owner, cat_coll, active_cat_idx_prop = get_contextual_owner_collection_indices(context, operator)

    if not cat_coll:
        return None

    cat_idx = -1
    # Use specific index property from operator if provided and valid
    if category_idx_prop_name and hasattr(operator, category_idx_prop_name):
        cat_idx = getattr(operator, category_idx_prop_name)
    # Fallback to owner's active category index
    elif hasattr(owner, active_cat_idx_prop):
        cat_idx = getattr(owner, active_cat_idx_prop)
    else:  # Should not happen if owner is valid
        return None

    # Validate index against the collection
    if 0 <= cat_idx < len(cat_coll):
        return cat_coll[cat_idx]
    # If index is out of bounds but collection is not empty, try to clamp or use 0
    elif cat_coll:
        clamped_idx = min(max(0, cat_idx), len(cat_coll) - 1)
        return cat_coll[clamped_idx]
    return None


def get_contextual_row(context, operator, row_idx_prop_name=None):
    """
    Gets the current row based on the operator's context.
    Uses operator.<row_idx_prop_name> if provided.
    Otherwise, uses active_row_index from the contextual category.
    The `category_idx_prop_name` for `get_contextual_category` might be 'category_index' if the op has it.
    """
    category = get_contextual_category(context, operator, category_idx_prop_name="category_index")
    if not category or not hasattr(category, "rows") or not category.rows:
        return None

    row_idx = -1
    if row_idx_prop_name and hasattr(operator, row_idx_prop_name):
        row_idx = getattr(operator, row_idx_prop_name)
    elif hasattr(operator, "row_index"):  # Common case for ops targeting a specific row
        row_idx = operator.row_index
    elif hasattr(category, "active_row_index"):  # Fallback to category's active row
        row_idx = category.active_row_index
    else:  # Should not happen
        return None

    if 0 <= row_idx < len(category.rows):
        return category.rows[row_idx]
    elif category.rows:  # Clamp if out of bounds but rows exist
        clamped_idx = min(max(0, row_idx), len(category.rows) - 1)
        return category.rows[clamped_idx]
    return None


def get_contextual_button_entry(context, operator, entry_idx_prop_name="entry_index"):
    """
    Gets the current button entry based on the operator's context.
    Uses operator.<entry_idx_prop_name> if provided.
    Otherwise, uses active_button_index from the contextual row.
    """
    # `row_idx_prop_name` for `get_contextual_row` might be 'row_index' if op has it.
    row = get_contextual_row(context, operator, row_idx_prop_name="row_index")
    if not row or not hasattr(row, "buttons") or not row.buttons:
        return None

    entry_idx = -1
    if entry_idx_prop_name and hasattr(operator, entry_idx_prop_name):
        entry_idx = getattr(operator, entry_idx_prop_name)
    elif hasattr(row, "active_button_index"):  # Fallback to row's active button
        entry_idx = row.active_button_index
    else:  # Should not happen
        return None

    if 0 <= entry_idx < len(row.buttons):
        return row.buttons[entry_idx]
    elif row.buttons:  # Clamp if out of bounds but buttons exist
        clamped_idx = min(max(0, entry_idx), len(row.buttons) - 1)
        return row.buttons[clamped_idx]
    return None


def ptr_to_dict(ptr):
    data = {}
    for prop in ptr.bl_rna.properties:
        # skip readonly and pointer props
        if prop.is_readonly or prop.type == "POINTER":
            continue
        name = prop.identifier
        try:
            val = getattr(ptr, name)
        except Exception:
            continue

        # RNA-detected collection → recurse
        if prop.type == "COLLECTION":
            data[name] = [ptr_to_dict(item) for item in val]
        else:
            data[name] = val
    return data


def dict_to_ptr(ptr, data):
    """
    Assign scalar props and fully rebuild any COLLECTION props found in `data`.
    Works for CategoryGroup.rows → RowGroup.buttons → ButtonEntry, etc.
    """
    for key, value in data.items():
        if not hasattr(ptr, key):
            continue

        target = getattr(ptr, key)

        # Rebuild a collection if JSON gave us a list
        if isinstance(value, list) and hasattr(target, "clear") and hasattr(target, "add"):
            target.clear()
            for subdata in value:
                item = target.add()
                dict_to_ptr(item, subdata)

        # Otherwise, try to set it as a scalar
        else:
            try:
                setattr(ptr, key, value)
            except Exception:
                pass


def get_prefs():
    try:
        # Try to get preferences with error handling for fresh installs
        if base_package in bpy.context.preferences.addons:
            return bpy.context.preferences.addons[base_package].preferences
        else:
            # Addon not found in preferences, return None
            print(f"[AniMate Pro] Addon '{base_package}' not found in preferences")
            return None
    except Exception as e:
        print(f"[AniMate Pro] Error getting preferences: {e}")
        return None


def find_key_for_operator(operator_idname):
    wm = bpy.context.window_manager
    for keyconfig in [wm.keyconfigs.user, wm.keyconfigs.default]:
        for km in keyconfig.keymaps:
            for kmi in km.keymap_items:
                if kmi.idname == operator_idname:
                    return kmi.type  # Return the first found key type
    return None  # Return None if not found


def find_addon_keyconfig(operator_idname, keymaps_to_register, space_type, region_type, properties):
    """
    Find a specific keymap item in the addon key configurations based on operator_idname,
    space_type, region_type, and properties.

    Args:
    - operator_idname (str): The operator ID name used in the keymap item.
    - keymaps_to_register (list): The list of keymaps (as dictionaries) to search within.
    - space_type (str): The space type where the keymap is applicable.
    - region_type (str): The region type where the keymap is applicable.
    - properties (dict): The specific properties to match in the keymap item.

    Returns:
    - The found keymap item or None if not found.
    """
    wm = bpy.context.window_manager
    addon_keyconfigs = wm.keyconfigs.addon

    if not addon_keyconfigs:
        dprint("Addon keyconfig not available.")
        return None

    for keymap_dict in keymaps_to_register:
        if (
            keymap_dict["operator_idname"] == operator_idname
            and keymap_dict["space_type"] == space_type
            and keymap_dict["region_type"] == region_type
        ):
            # Extract details from the keymap definition
            km_name = keymap_dict["name"]
            km = addon_keyconfigs.keymaps.get(km_name, None)
            if km:
                for item in km.keymap_items:
                    if item.idname != operator_idname:
                        continue

                    # Check if the properties match
                    all_properties_match = True
                    for prop_name, prop_value in properties.items():
                        if not hasattr(item.properties, prop_name) or getattr(item.properties, prop_name) != prop_value:
                            all_properties_match = False
                            break

                    if all_properties_match:
                        # Found the matching keymap item
                        return item

    # If we get here, the keymap item was not found
    dprint(f"No matching keymap found for {operator_idname} in addon keyconfigs.")
    return None


def find_user_keyconfig(key):
    """Find a specific keymap item in the user key configurations."""
    # Function to find user keyconfig
    km, kmi = addon_keymaps[key]
    for item in bpy.context.window_manager.keyconfigs.user.keymaps[km.name].keymap_items:
        found_item = False
        if kmi.idname == item.idname:
            found_item = True
            for name in dir(kmi.properties):
                if not name in ["bl_rna", "rna_type"] and not name[0] == "_":
                    if (
                        name in kmi.properties
                        and name in item.properties
                        and not kmi.properties[name] == item.properties[name]
                    ):
                        found_item = False
        if found_item:
            return item
    return kmi


# def find_user_keyconfig(
#     operator_idname,
#     keymaps_to_register,
#     keymap_type,
#     keymap_event_value,
#     keymap_direction=None,
# ):
#     """
#     Find a specific keymap item in the user key configurations based on operator_idname and additional criteria.

#     Args:
#     - operator_idname (str): The operator ID name used in the keymap item.
#     - keymaps_to_register (list): The list of keymaps (as dictionaries) to search within.
#     - keymap_type (str): The type of event (e.g., 'SPACE', 'T', etc.).
#     - keymap_event_value (str): The value of the event ('PRESS', 'RELEASE').
#     - keymap_direction (str, optional): The direction of the mouse movement, if applicable.

#     Returns:
#     - The found keymap item or None if not found.
#     """
#     for keymap_dict in keymaps_to_register:
#         if keymap_dict["operator_idname"] == operator_idname:
#             # Extract details from the keymap definition
#             km_name = keymap_dict["name"]
#             km_space_type = keymap_dict["space_type"]
#             km_region_type = keymap_dict["region_type"]

#             # Find the keymap in user key configurations
#             km = bpy.context.window_manager.keyconfigs.user.keymaps.get(km_name, None)
#             if km:
#                 for item in km.keymap_items:
#                     if (
#                         item.idname == operator_idname
#                         and item.type == keymap_type
#                         and item.value == keymap_event_value
#                         and (keymap_direction is None or item.key_modifier == keymap_direction)
#                     ):
#                         # Found the matching keymap item
#                         return item
#     # If we get here, the keymap item was not found
#     return None


def find_blender_keyconfig(idname, properties=None):
    """Find a specific keymap item in Blender's key configurations."""
    wm = bpy.context.window_manager
    for keymap in wm.keyconfigs.user.keymaps:
        for item in keymap.keymap_items:
            if item.idname == idname:
                if properties:
                    if all(getattr(item.properties, k, None) == v for k, v in properties.items()):
                        return item
                else:
                    return item
    return None


# def update_spacebar_action(self, context):
#     # Map the addon's spacebar action to Blender's enum identifiers
#     spacebar_action_map = {
#         "PLAY": "PLAY",
#         "TOOLBAR": "TOOL",
#         "SEARCH": "SEARCH",
#         "NOTHING": "NOTHING",
#     }
#     # Get the mapped value for the current preference
#     mapped_action = spacebar_action_map.get(self.mode_options, "PLAY")  # Default to "PLAY" if not found

#     # Set Blender's spacebar action based on the mapped value
#     kc = bpy.context.window_manager.keyconfigs.active
#     if kc and kc.preferences:
#         kc.preferences.spacebar_action = mapped_action
#         dprint(f"Spacebar action changed to: {mapped_action}")


def ensure_alpha(color_tuple):
    """
    Ensures that a color tuple has an alpha value.
    If alpha is missing, it will add 1.0 (fully opaque).
    """
    if len(color_tuple) == 3:
        return (*color_tuple, 1.0)
    return color_tuple


# Update to calculate_3d_viewport_offset to return both x and y offsets
def calculate_3d_viewport_offset(context, mouse_x, mouse_y):
    """
    Calculates the offset based on the viewport that contains the mouse cursor.
    Returns the bottom left corner (x, y) of the viewport that contains the mouse.
    """
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            # Calculate the area's screen space bounds
            x1 = area.x
            y1 = area.y
            x2 = x1 + area.width
            y2 = y1 + area.height

            # Check if the mouse is within this area
            if (x1 < mouse_x < x2) and (y1 < mouse_y < y2):
                # Return the bottom left corner of the viewport
                return (x1, y1)
    # Return (0, 0) if no viewport under mouse
    return (0, 0)


# Function to handle setup and teardown
def setup_or_teardown(self, context):
    """
    Setup or teardown based on the context and self object.
    """
    if not hasattr(self, "_active_region") or not hasattr(self, "_handle"):
        return


def find_window_region(context):
    """
    Finds and returns the 'WINDOW' region in the context area.
    """
    for region in context.area.regions:
        if region.type == "WINDOW":
            return region
    return None


# Function to set up the text properties
def setup_text_properties(context):
    """
    Sets up text properties like color and size.
    """
    prefs = context.preferences.addons[base_package].preferences
    color = prefs.timeline_gui_color
    blf.color(0, color[0], color[1], color[2], 1)
    text_size = prefs.timeline_gui_text_size
    blf.size(0, text_size)


# Function to draw the frame number and shapes
def draw_frame_number(context, mouse_x, mouse_y, adjusted_mouse_y):
    """
    Draws the frame number and associated triangles.
    """
    prefs = context.preferences.addons[base_package].preferences
    if prefs.show_frame_number and not prefs.is_sensitivity_mode:
        # Set font size for big text
        big_text_size = int(prefs.timeline_gui_text_size * 1.5)
        blf.size(0, big_text_size)

        # Calculate text dimensions
        text_width, text_height = blf.dimensions(0, f"{context.scene.frame_current}")
        text_x = mouse_x - (text_width // 2)

        # Adjust y-coordinate to move text down
        text_y = adjusted_mouse_y

        # Draw the frame number
        blf.position(0, text_x, text_y, 0)
        blf.draw(0, f"{context.scene.frame_current}")
        # Enable shadow with level 3, and set shadow color to black with 50% alpha
        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 3, 0.0, 0.0, 0.0, 1)

        # Then set the text color, ensuring it has an alpha value
        safe_text_color = ensure_alpha(prefs.text_color)
        blf.color(0, *safe_text_color)

        # Draw the frame number with position set
        blf.position(0, text_x, text_y, 0)
        blf.draw(0, f"{context.scene.frame_current}")

        # Disable shadow for subsequent text
        blf.disable(0, blf.SHADOW)

        # Calculate the vertical center of the text
        text_center_y = text_y + (text_height // 2)

        scale_factor = 0.75

        # Calculating the center points for scaling
        left_center_x = text_x - 15  # Midpoint between -20 and -10
        left_center_y = text_center_y
        right_center_x = text_x + text_width + 15  # Midpoint between +10 and +20
        right_center_y = text_center_y

        # Position triangles left and right of the frame number, and center vertically
        left_triangle = [
            (left_center_x - 5 * scale_factor, left_center_y),
            (left_center_x + 5 * scale_factor, left_center_y - 10 * scale_factor),
            (left_center_x + 5 * scale_factor, left_center_y + 10 * scale_factor),
        ]
        right_triangle = [
            (right_center_x + 5 * scale_factor, right_center_y),
            (right_center_x - 5 * scale_factor, right_center_y - 10 * scale_factor),
            (right_center_x - 5 * scale_factor, right_center_y + 10 * scale_factor),
        ]

        # Drawing the triangles
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch_left = batch_for_shader(shader, "TRIS", {"pos": left_triangle})
        batch_right = batch_for_shader(shader, "TRIS", {"pos": right_triangle})

        safe_accent_color = ensure_alpha(prefs.accent_color)

        shader.bind()
        shader.uniform_float("color", safe_accent_color)
        batch_left.draw(shader)
        batch_right.draw(shader)


def draw_gui_text_lines(context, x, y, toggle_gui_key):
    """
    Draws the GUI text lines based on timeline_gui_toggle, growing upwards from the starting y position.
    Adjusts the help lines dynamically based on the current mode and conditions.
    """
    prefs = context.preferences.addons[base_package].preferences
    region = find_window_region(context)

    if prefs.timeline_gui_toggle and region:
        # Initialize the lines list
        lines = [
            "________________________",
            f"HIDE GUI ({prefs.gui_help_key})",
            "________________________",
            f" - CURRENT MODE: {prefs.current_mode}",
            f" - CURRENT FRAME: {context.scene.frame_current}",
            f" - TIMELINE SENSITIVITY (MWHEEL): {prefs.timeline_sensitivity:.2f}",
            f" - LIMIT TO RANGE ({prefs.limit_to_range_key}): {'ON' if prefs.limit_to_active_range else 'OFF'}",
            f" - QUICK ANIM OFFSET ({prefs.quick_anim_offset_key})",
            " ",
            "________________________",
            "SCRUBBING MODES:",
            "________________________",
            " - DEFAULT (No Modifier + Drag)",
            " - MARKERS (Ctrl + Drag)",
            " - KEYFRAMES (Shift + Drag)",
            "",
            "________________________",
            "SCRUBBING HOTKEYS:",
            "________________________",
            f" - SET/CLEAR PREVIEW RANGE ({prefs.set_preview_range_key})",
            f" - ADD MARKER ({prefs.add_marker_key})",
        ]

        # Conditionally add lines based on specific modes or conditions
        if prefs.current_mode == "MARKERS":
            lines.append(f" - REMOVE MARKER ({prefs.remove_marker_keyframe_key})")
        if prefs.current_mode == "KEYFRAMES":
            lines.append(f" - REMOVE KEYFRAME ({prefs.remove_marker_keyframe_key})")
        if prefs.scrubbing_error:
            lines.insert(0, prefs.scrubbing_error)

        # Add remaining hotkeys
        lines.extend(
            [
                f" - NEXT/PREV KEYFRAME ({prefs.next_keyframe_key}/{prefs.prev_keyframe_key})",
                f" - NUDGE LEFT/RIGHT ({prefs.scrub_nudge_key_L}/{prefs.scrub_nudge_key_R})",
                f" - NEXT/PREV FRAME ({prefs.next_frame_key}/{prefs.prev_frame_key})",
                f" - INSERT KEYFRAME ({prefs.insert_keyframe_key})",
                f" - FIRST/LAST FRAME ({prefs.first_frame_key}/{prefs.last_frame_key})",
                f" - PLAY/REVERSE ({prefs.play_animation_key}/{prefs.play_reverse_animation_key})",
                "",
                "________________________",
                "  POSE BREAKDOWN:",
                "________________________",
                f" - BREAKDOWNER ({prefs.breakdown_pose_key})",
                f" - BLEND TO NEIGHBOR ({prefs.blend_to_neighbor_key})",
                f" - RELAX TO BREAKDOWN({prefs.relax_to_breakdown_key})",
            ]
        )

        # Start drawing from the y position upwards
        y_position = y
        for line in reversed(lines):
            # Draw the current line
            draw_text_line(context, x, y_position, line)
            # Get the height of the current line to calculate the position of the next line
            line_height = blf.dimensions(0, line)[1]
            # Increment the y position for the next line
            y_position += line_height + 5

    else:
        draw_help_text(context, x, y, toggle_gui_key)


def draw_text_line(context, x, y, line):
    """
    Draws a single line of text at the specified position with shadow.
    """
    prefs = context.preferences.addons[base_package].preferences
    # Enable shadow with level 3, and set shadow color to black with 50% alpha
    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 3, 0.0, 0.0, 0.0, 0.5)

    # Ensure the color has an alpha value and set it
    safe_text_color = ensure_alpha(prefs.text_color)
    blf.color(0, *safe_text_color)

    # Draw the text
    blf.position(0, x, y, 0)
    blf.draw(0, line)

    # Disable shadow for subsequent text
    blf.disable(0, blf.SHADOW)


# Helper function to draw help text
def draw_help_text(context, x, y, toggle_gui_key):
    prefs = context.preferences.addons[base_package].preferences
    region = find_window_region(context)

    # Enable shadow and set its color
    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 3, 0.0, 0.0, 0.0, 0.5)

    # Ensure the color has an alpha value and set it
    safe_text_color = ensure_alpha(prefs.text_color)
    blf.color(0, *safe_text_color)

    if region:
        # Draw "GUI HELP" text
        blf.position(0, x, y, 0)
        blf.draw(0, f"GUI HELP ({prefs.gui_help_key})")

        # Disable shadow for subsequent text
        blf.disable(0, blf.SHADOW)


def draw_conditional_text(context, mouse_x, mouse_y, adjusted_mouse_y):
    prefs = context.preferences.addons[base_package].preferences
    text_size = prefs.timeline_gui_text_size
    blf.size(0, text_size)
    prefs = context.preferences.addons[base_package].preferences

    if prefs.current_mode in [
        "MARKERS",
        "KEYFRAMES",
        # "ANIMOFFSET",
    ]:
        # if prefs.current_mode == "ANIMOFFSET":
        #     text_to_display = f"QUICK ANIM OFFSET"
        #     sub_text_to_display = f"""({prefs.quick_anim_offset_key}) to exit."""  # ({prefs.quick_anim_offset_blend_key}) to edit mask blend. ({prefs.quick_anim_offset_mask_key}) to edit mask"""
        # else:
        text_to_display = prefs.current_mode
        sub_text_to_display = ""

        # Current mode text dimensions
        mode_text_width, mode_text_height = blf.dimensions(0, text_to_display)
        mode_sub_text_width, mode_sub_text_height = blf.dimensions(0, sub_text_to_display)

        # Position text below the frame number and arrows
        text_x = mouse_x - (mode_text_width // 2)
        text_y = adjusted_mouse_y - (2 * mode_text_height)
        sub_text_x = mouse_x - (mode_sub_text_width // 2)
        sub_text_y = adjusted_mouse_y - (3 * mode_sub_text_height)

        # Set the text color with alpha
        safe_text_color = ensure_alpha(prefs.text_color)
        blf.color(0, *safe_text_color)

        # Enable shadow
        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 5, 0, 0, 0, 0.8)
        blf.shadow_offset(0, 3, -3)

        # Draw the current mode text
        blf.position(0, text_x, text_y, 0)
        blf.draw(0, text_to_display)

        blf.position(0, sub_text_x, sub_text_y, 0)
        blf.draw(0, sub_text_to_display)

        # Draw the error message below if it's not empty
        error_message = prefs.scrubbing_error
        if error_message != "":
            # Error message text dimensions
            error_text_width, error_text_height = blf.dimensions(0, error_message)

            # Calculate the position for the error message, leaving a small gap between lines
            error_text_x = mouse_x - (error_text_width / 2)  # Center the error message
            error_text_y = text_y - mode_text_height - 10  # 10 is the gap, adjust as needed

            # Draw the error message text
            blf.position(0, error_text_x, error_text_y, 0)
            blf.draw(0, error_message)

        # Disable shadow for subsequent text
        blf.disable(0, blf.SHADOW)


is_cleaning_up = False


# Main draw callback function
def draw_callback_px(self, context, mouse_x=None, mouse_y=None, editor_type=None, remove=False):
    """
    Main draw callback function to draw text on screen, adjusted to active viewport.
    """
    if context.area is None or context.area.type != editor_type:
        return

    if editor_type not in ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"]:
        return

    # Check if the operator has been removed
    try:
        if not hasattr(self, "is_cleaning_up"):
            return
    except:
        return

    # Then check the flag
    if self.is_cleaning_up:
        return

    current_area = context.area
    current_region = context.region
    region = find_window_region(context)

    # Ensure drawing only occurs in the intended 'WINDOW' region

    if not (hasattr(self, "_active_area") and hasattr(self, "_active_region")):
        return

    if self._active_area != current_area or self._active_region != current_region:
        return

    setup_text_properties(context)

    # Get the settings
    prefs = context.preferences.addons[base_package].preferences

    # Use the initial mouse position if we are not moving the text with the mouse
    if prefs.lock_text_in_place:
        # Use initial mouse coordinates and adjust for the region's position
        adjusted_mouse_x = self.initial_mouse_position[0] - region.x
        adjusted_mouse_y = self.initial_mouse_position[1] - region.y
    else:
        # Get the offset for the active viewport
        viewport_offset = calculate_3d_viewport_offset(context, mouse_x, mouse_y)

        # Adjust mouse coordinates by viewport offset
        # adjusted_mouse_x = mouse_x - viewport_offset[0]
        # adjusted_mouse_y = mouse_y - viewport_offset[1]
        adjusted_mouse_x = mouse_x - region.x
        adjusted_mouse_y = mouse_y - region.y

    if prefs.lock_vertical_movement:
        # If vertical movement is not allowed, keep the Y coordinate fixed
        adjusted_mouse_y = self.initial_mouse_position[1] - region.y

    # if not settings.allow_horizontal_movement:
    #     # If horizontal movement is not allowed, keep the X coordinate fixed
    #     adjusted_mouse_x = self.initial_mouse_position[0] - region.x

    # Define constants for text drawing
    blf.size(0, 11)

    if region:
        # Now using the adjusted mouse coordinates for drawing
        draw_frame_number(context, adjusted_mouse_x, adjusted_mouse_y, adjusted_mouse_y)
        draw_conditional_text(context, adjusted_mouse_x, adjusted_mouse_y, adjusted_mouse_y)

        toggle_gui_key = self.toggle_gui_key.upper()

        # Define the starting X and Y positions for the GUI text
        gui_text_x = 20
        gui_text_y = 60

        # Use adjusted coordinates for drawing GUI text lines as well
        draw_gui_text_lines(context, gui_text_x, gui_text_y, toggle_gui_key)


# Helper function to update the current frame based on the scrub settings and delta X
def update_frame(context, delta_x):
    """Update the current frame based on the scrub settings and delta X."""
    prefs = context.preferences.addons[base_package].preferences
    sensitivity = prefs.timeline_sensitivity
    new_frame = prefs.initial_frame + (delta_x * sensitivity)
    context.scene.frame_current = round(new_frame)


# Helper function to set the scrubbing mode based on the pressed key
def set_mode_based_on_key(context, event, marker_key, keyframe_key):
    """Set the scrubbing mode based on the pressed key."""
    prefs = context.preferences.addons[base_package].preferences
    scene = context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset

    # if not anim_offset.mask_in_use:
    if event.ctrl and marker_key == "CTRL":
        prefs.current_mode = "MARKERS"
    elif event.shift and keyframe_key == "SHIFT":
        prefs.current_mode = "KEYFRAMES"
    else:
        # If no specific mode key is pressed, default to scrubbing
        prefs.current_mode = "SCRUBBING"
    # else:
    #     prefs.current_mode = "ANIMOFFSET"


# Helper function to toggle the GUI
def toggle_gui(context):
    """Toggle the visibility of the timeline GUI."""
    prefs = context.preferences.addons[base_package].preferences
    prefs.timeline_gui_toggle = not prefs.timeline_gui_toggle


def change_scrub_sensitivity(self, context, event):
    """Adjust timeline sensitivity based on mouse wheel scroll events, with finer adjustments when Shift is held."""
    prefs = context.preferences.addons[base_package].preferences
    # Define a smaller step size for adjustments when Shift is held
    small_step = self.timeline_sensitivity * 0.1  # Example: 10% of the current sensitivity

    # Determine the change in sensitivity, considering whether Shift is held
    if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
        if event.shift:  # If Shift key is held, use the smaller step size
            sensitivity_change = small_step if event.type == "WHEELUPMOUSE" else -small_step
        else:  # No Shift key, use the regular sensitivity change
            sensitivity_change = (
                self.timeline_sensitivity if event.type == "WHEELUPMOUSE" else -self.timeline_sensitivity
            )

        # Apply the sensitivity change and ensure it does not go below a minimum threshold
        new_sensitivity = prefs.timeline_sensitivity + sensitivity_change
        min_sensitivity = 0.01 if event.shift else 0.1  # Adjust the minimum sensitivity based on Shift key
        prefs.timeline_sensitivity = max(min_sensitivity, new_sensitivity)


# def quick_anim_offset_mask(self, context, event):
#     scene = context.scene
#     prefs = context.preferences.addons[base_package].preferences
#     anim_offset = scene.amp_timeline_tools.anim_offset

#     if anim_offset.mask_in_use:
#         if self.mask_mouse_offset_x is None:
#             self.mask_mouse_offset_x = event.mouse_x
#             self.acumulate_mask_mover = 0.0

#         current_mouse_x = event.mouse_x
#         mouse_move_difference = current_mouse_x - self.mask_mouse_offset_x

#         self.acumulate_mask_mover += mouse_move_difference * prefs.timeline_sensitivity

#         # if matches_key_combination(event, prefs.quick_anim_offset_blend_key):
#         #     if abs(self.acumulate_mask_mover) >= 1.0:
#         #         blending_change = int(self.acumulate_mask_mover)
#         #         anim_offset.ao_blend_range += blending_change
#         #         self.acumulate_mask_mover -= blending_change

#         # elif matches_key_combination(event, prefs.quick_anim_offset_mask_key):
#         #     if abs(self.acumulate_mask_mover) >= 1.0:
#         #         mask_change = int(self.acumulate_mask_mover)
#         #         anim_offset.ao_mask_range += mask_change
#         #         self.acumulate_mask_mover -= mask_change

#         self.mask_mouse_offset_x = current_mouse_x


def add_marker_scrubbing(context):
    # Add a marker at the current frame
    marker = context.scene.timeline_markers.new(
        name=f"F_{context.scene.frame_current}", frame=context.scene.frame_current
    )
    marker.select = True


def remove_marker_scrubbing(context):
    # Remove marker at the current frame
    markers = context.scene.timeline_markers
    current_frame = context.scene.frame_current
    for marker in markers:
        if marker.frame == current_frame:
            markers.remove(marker)
            break


def remove_keyframe_scrubbing(context):
    # Remove keyframes at the current frame for the selected bones or objects
    current_frame = context.scene.frame_current
    if context.mode == "POSE":
        # In pose mode, remove keyframes from selected bones
        bones = context.selected_pose_bones
        if bones:
            for bone in bones:
                if bone.bone.select:
                    # Remove keyframes for the bone's location, rotation, and scale
                    bone.keyframe_delete(data_path="location", frame=current_frame)
                    bone.keyframe_delete(data_path="rotation_quaternion", frame=current_frame)
                    bone.keyframe_delete(data_path="rotation_euler", frame=current_frame)
                    bone.keyframe_delete(data_path="scale", frame=current_frame)
                    # Remove keyframes for custom properties
                    for prop in bone.keys():
                        # Check if the property is animatable
                        if prop not in {"_RNA_UI", "id_data"} and isinstance(
                            getattr(bone, prop, None), (float, int, bool, str)
                        ):
                            bone.keyframe_delete(data_path=f'["{prop}"]', frame=current_frame)
    elif context.selected_objects:
        # In object mode, remove keyframes from selected objects
        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                # Remove keyframes for object-level properties
                obj.keyframe_delete(data_path="location", frame=current_frame)
                obj.keyframe_delete(data_path="rotation_quaternion", frame=current_frame)
                obj.keyframe_delete(data_path="rotation_euler", frame=current_frame)
                obj.keyframe_delete(data_path="scale", frame=current_frame)
                # Remove keyframes for custom properties
                for prop in obj.keys():
                    # Check if the property is animatable
                    if prop not in {"_RNA_UI", "id_data"} and isinstance(
                        getattr(obj, prop, None), (float, int, bool, str)
                    ):
                        obj.keyframe_delete(data_path=f'["{prop}"]', frame=current_frame)
    # Force a UI update
    for area in context.screen.areas:
        if area.type in {"DOPESHEET_EDITOR", "GRAPH_EDITOR", "NLA_EDITOR", "TIMELINE"}:
            area.tag_redraw()

    # Update the scene to reflect the changes
    context.scene.frame_current = context.scene.frame_current


def insert_keyframe(self, context, force_insert=False):
    area_type = context.area.type
    current_frame = context.scene.frame_current

    if area_type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"}:
        self.report({"WARNING"}, "This operation can only be performed in the Graph Editor, Dope Sheet, or 3D View.")
        return {"CANCELLED"}

    # Determine keyframe insertion options based on the editor context
    if area_type == "GRAPH_EDITOR":
        insert_options = {"INSERTKEY_NEEDED"}
        keyframe_curves(self, context, force_insert)
    else:
        insert_options = {"INSERTKEY_AVAILABLE"}

    # Handle keyframe insertion based on the type of the active object and selection
    objects = context.selected_objects if area_type == "VIEW_3D" else [context.active_object]
    for obj in objects:
        if obj.type == "ARMATURE" and obj.mode == "POSE":
            for bone in obj.pose.bones:
                if bone.bone.select:
                    keyframe_bone(self, bone, current_frame, insert_options, force_insert)
        else:
            keyframe_object(self, obj, current_frame, insert_options, force_insert)

    context.view_layer.update()

    return {"FINISHED"}


def keyframe_curves(self, context, force_insert=False):
    for fcurve in context.selected_visible_fcurves:
        if fcurve.lock or fcurve.hide:
            continue

        if not force_insert:
            try:
                fcurve.keyframe_points.insert(
                    frame=context.scene.frame_current,
                    value=fcurve.evaluate(context.scene.frame_current),
                    options={"NEEDED", "FAST"},
                )
            except Exception as e:
                self.report({"WARNING"}, f"Failed to insert keyframe: {str(e)}")
        else:
            try:
                fcurve.keyframe_points.insert(
                    frame=context.scene.frame_current,
                    value=fcurve.evaluate(context.scene.frame_current),
                    options={"NEEDED", "FAST"},
                )
            except Exception as e:
                self.report({"WARNING"}, f"Failed to insert keyframe: {str(e)}")
    pass


def keyframe_object(self, obj, frame, insert_options, force_insert):
    # Determine the rotation mode and adjust properties accordingly
    rotation_mode = obj.rotation_mode
    if rotation_mode == "QUATERNION":
        rotation_prop = "rotation_quaternion"
    elif rotation_mode == "AXIS_ANGLE":
        rotation_prop = "rotation_axis_angle"
    else:
        rotation_prop = "rotation_euler"

    properties = ["location", rotation_prop, "scale"]

    for prop in properties:
        lock_attr = f"lock_{prop}"
        lock_status = getattr(
            obj, lock_attr, [False] * len(getattr(obj, prop, [0]))
        )  # Default to unlocked if attribute missing

        if all(lock_status):
            continue  # Skip keyframing if all channels are locked

        if force_insert or not any(lock_status):
            try:
                obj.keyframe_insert(
                    data_path=prop, frame=frame, options={"INSERTKEY_NEEDED" if force_insert else "INSERTKEY_AVAILABLE"}
                )
            except RuntimeError as e:
                self.report({"WARNING"}, f"Failed to insert keyframe for {prop} on {obj.name}: {str(e)}")


def keyframe_bone(self, bone, frame, insert_options, force_insert):
    # Determine the rotation mode and adjust properties accordingly
    rotation_mode = bone.rotation_mode
    if rotation_mode == "QUATERNION":
        rotation_prop = "rotation_quaternion"
    elif rotation_mode == "AXIS_ANGLE":
        rotation_prop = "rotation_axis_angle"
    else:
        rotation_prop = "rotation_euler"

    properties = {"location": bone.lock_location, rotation_prop: bone.lock_rotation, "scale": bone.lock_scale}

    for prop, lock_status in properties.items():
        if all(lock_status):
            continue  # Skip this property if all channels are locked

        if force_insert or not any(lock_status):
            try:
                bone.keyframe_insert(
                    data_path=prop, frame=frame, options={"INSERTKEY_NEEDED" if force_insert else "INSERTKEY_AVAILABLE"}
                )
            except RuntimeError as e:
                self.report({"WARNING"}, f"Failed to insert keyframe for {prop} on {bone.name}: {str(e)}")


def register_script(script, should_register):
    if should_register:
        script.register()
        dprint("Script components registered.")
    else:
        script.unregister()
        dprint("Script components unregistered.")


# Function to move playhead to the lowest selected keyframe
def move_playhead_to_lowest_keyframe(selected_keyframes):
    if selected_keyframes:
        lowest_frame = min(selected_keyframes)
        bpy.context.scene.frame_current = int(lowest_frame)


# Handles Pose Mode logic for armature objects
def select_keyframes(context):
    selected_keyframes = []

    for fcurve in context.selected_visible_fcurves:
        for keyframe in fcurve.keyframe_points:
            if keyframe.select_control_point:
                selected_keyframes.append(keyframe.co.x)
    return selected_keyframes


def set_amp_timeline_tools_action():
    """Creates an "action" called 'amp_action'"""

    action = bpy.data.actions.get("amp_action")

    if action is None:
        return bpy.data.actions.new("amp_action")
    else:
        return bpy.data.actions.get("amp_action")


def get_all_actions(obj):

    trans_action = getattr(obj.animation_data, "action", None)

    transform = {"type": "transform_action", "action": trans_action}

    sk = getattr(obj.data, "shape_keys", None)
    sk_animation_data = getattr(sk, "animation_data", None)
    sk_action = getattr(sk_animation_data, "action", None)

    shape_keys = {"type": "shape_keys", "action": sk_action}

    if transform or shape_keys:
        return [transform, shape_keys]
    else:
        return


def gradual(key_y, target_y, delta=1.0, factor=0.15):
    """Gradualy transition the value of key_y to target_y"""
    step = abs(key_y - target_y) * (delta * factor)

    if target_y > key_y:
        return key_y + step

    else:
        return key_y - step


def clamp(value, minimum, maximum, to_none=False):
    """Take a value and if it goes beyond the minimum and maximum it would replace it with those."""

    if value <= minimum:
        if to_none is True:
            return None
        else:
            return minimum

    if value >= maximum:
        if to_none is True:
            return None
        else:
            return maximum

    return value


def floor(value, minimum, to_none=False):
    """Take the value and if it goes lower than the minimum it would replace it with it"""
    if value < minimum:
        if to_none is True:
            return None
        else:
            return minimum

    return value


def ceiling(value, maximum, to_none=False):
    """Take the value and if it goes over the maximum it would replace it with it"""
    if value > maximum:
        if to_none is True:
            return None
        else:
            return maximum

    return value


def toggle(to_toggle, value_a, value_b):
    """Change 'to_toggle' to one of the tow values it doesn't have at the moment"""
    if to_toggle == value_a:
        return value_b
    elif to_toggle == value_b:
        return value_a


def add_marker(name, side, frame=0, overwrite=True):
    """add reference frames marker"""

    amp = bpy.context.scene.amp_timeline_tools
    use_markers = amp.tool.use_markers

    if not use_markers:
        return

    name = f"{side}{name}"

    markers = bpy.context.scene.timeline_markers
    if overwrite:
        remove_marker(side)
    marker = markers.new(name=name, frame=frame)
    marker["side"] = side
    return marker


def modify_marker(marker, name="SAME", frame="SAME"):
    if name != "SAME":
        marker.name = name

    if frame != "SAME":
        marker.frame = frame


def remove_marker(side):
    """Removes reference frame markers"""

    markers = bpy.context.scene.timeline_markers

    for marker in markers:
        if marker.get("side") == side:
            markers.remove(marker)
    return


def switch_aim(aim, factor):
    if factor < 0.5:
        aim = aim * -1
    return aim


def poll(context):
    """Poll used on all the slider operators"""

    selected = get_items(context, any_mode=True)

    area = context.area.type
    return bool((area == "GRAPH_EDITOR" or area == "DOPESHEET_EDITOR" or area == "VIEW_3D") and selected)


def get_items(context, any_mode=False):
    """returns objects"""
    if any_mode:
        if context.mode == "OBJECT":
            selected = context.selected_objects
        elif context.mode == "POSE":
            selected = context.selected_pose_bones
        else:
            selected = None
    else:
        selected = context.selected_objects

    if context.area.type == "VIEW_3D":
        return selected
    elif context.space_data.dopesheet.show_only_selected:
        return selected
    else:
        return bpy.data.objects


text_handle = None
# bar_color = None
# amp_pref_theme_colors_autosave = None
# dopesheet_color = None
# graph_color = None
# nla_color = None


# def set_bar_color():
#     global bar_color, dopesheet_color, graph_color, nla_color, amp_pref_theme_colors_autosave
#     if bar_color is None:
#         bar_color = True
#         amp_pref_theme_colors_autosave = bpy.context.preferences.use_preferences_save
#         dopesheet_color = bpy.context.preferences.themes[
#             0
#         ].dopesheet_editor.space.header[:]
#         graph_color = bpy.context.preferences.themes[0].graph_editor.space.header[:]
#         nla_color = bpy.context.preferences.themes[0].nla_editor.space.header[:]

#     h = bpy.context.preferences.themes[0].graph_editor.preview_range
#     highlight = (h[0] * 0.9, h[1] * 0.9, h[2] * 0.9, 1)
#     bpy.context.preferences.use_preferences_save = False
#     bpy.context.preferences.themes[0].dopesheet_editor.space.header = highlight
#     bpy.context.preferences.themes[0].nla_editor.space.header = highlight
#     bpy.context.preferences.themes[0].graph_editor.space.header = highlight


# def reset_bar_color():
#     if amp_pref_theme_colors_autosave is not None:
#         bpy.context.preferences.use_preferences_save = amp_pref_theme_colors_autosave
#     if dopesheet_color is not None:
#         bpy.context.preferences.themes[0].dopesheet_editor.space.header = (
#             dopesheet_color
#         )
#     if graph_color is not None:
#         bpy.context.preferences.themes[0].nla_editor.space.header = graph_color
#     if nla_color is not None:
#         bpy.context.preferences.themes[0].graph_editor.space.header = nla_color


def reboot_theme_colors(self, context):
    reset_autokeying_theme_colors()
    # set_bar_color()
    reset_bar_color()


def set_bar_color():
    prefs = bpy.context.preferences.addons[base_package].preferences
    theme = bpy.context.preferences.themes[0]
    autokeying_is_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    anim_offset = bpy.context.scene.amp_timeline_tools.anim_offset.mask_in_use

    prefs.original_theme_captured = False

    # Capture original theme colors if they haven't been captured yet
    capture_original_theme_colors(prefs)

    # Define the highlight color
    h = bpy.context.preferences.themes[0].graph_editor.preview_range
    highlight = (h[0] * 0.9, h[1] * 0.9, h[2] * 0.9, 1)

    # Apply the highlight color
    theme.dopesheet_editor.space.header = highlight
    theme.graph_editor.space.header = highlight
    theme.nla_editor.space.header = highlight

    # Check if use_preferences_save was enabled and track it so we can reenable it later
    _was_save_preferences_true = bpy.context.preferences.use_preferences_save

    # Disable preferences auto-saving to avoid saving these temporary changes
    if _was_save_preferences_true:
        bpy.context.preferences.use_preferences_save = False


def reset_bar_color():
    theme = bpy.context.preferences.themes[0]
    prefs = bpy.context.preferences.addons[base_package].preferences

    # restore dopesheet header
    if prefs.original_dopesheet_header:
        try:
            theme.dopesheet_editor.space.header = json.loads(prefs.original_dopesheet_header)
        except json.JSONDecodeError:
            pass

    # restore graph header
    if prefs.original_graph_header:
        try:
            theme.graph_editor.space.header = json.loads(prefs.original_graph_header)
        except json.JSONDecodeError:
            pass

    # restore nla header
    if prefs.original_nla_header:
        try:
            theme.nla_editor.space.header = json.loads(prefs.original_nla_header)
        except json.JSONDecodeError:
            pass

    if prefs.original_header:
        try:
            theme.view_3d.space.header = json.loads(prefs.original_header)
        except json.JSONDecodeError:
            pass

    if prefs.original_object_active:
        try:
            theme.view_3d.object_active = json.loads(prefs.original_object_active)
        except json.JSONDecodeError:
            pass

    if prefs.original_bone_pose_active:
        try:
            theme.view_3d.bone_pose_active = json.loads(prefs.original_bone_pose_active)
        except json.JSONDecodeError:
            pass

    if _was_save_preferences_true:
        bpy.context.preferences.use_preferences_save = True
        bpy.ops.wm.save_userpref()


def add_message(message):

    global text_handle

    def draw_text_callback(info):
        font_id = 0
        blf.position(font_id, 10, 80, 0)
        blf.size(font_id, 20)
        blf.color(font_id, 1, 1, 1, 0.5)
        blf.draw(font_id, info)

    if text_handle is None:
        # set_bar_color(0.5, 0.3, 0.2, 1)
        text_handle = bpy.types.SpaceView3D.draw_handler_add(draw_text_callback, (message,), "WINDOW", "POST_PIXEL")


def remove_message():
    global text_handle

    # reset_bar_color()
    if text_handle:
        bpy.types.SpaceView3D.draw_handler_remove(text_handle, "WINDOW")
    text_handle = None


def set_autokeying_theme_colors():
    prefs = bpy.context.preferences.addons[base_package].preferences
    theme = bpy.context.preferences.themes[0]
    autokeying_is_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    anim_offset = bpy.context.scene.amp_timeline_tools.anim_offset.mask_in_use

    prefs.original_theme_captured = False

    capture_original_theme_colors()

    if autokeying_is_on:
        if prefs.autokeying_selection_color_use:
            theme.view_3d.object_active = prefs.autokeying_selection_color_on

        if prefs.autokeying_posebone_color_use:
            theme.view_3d.bone_pose_active = prefs.autokeying_posebone_color_on

        if prefs.autokeying_header_color_use:
            if prefs.autokeying_header_3dview_color_use:
                theme.view_3d.space.header = prefs.autokeying_header_color_on
            else:
                theme.view_3d.space.header = json.loads(prefs.original_header)

            if prefs.autokeying_header_dopesheet_color_use:
                theme.dopesheet_editor.space.header = prefs.autokeying_header_color_on
            else:
                theme.dopesheet_editor.space.header = json.loads(prefs.original_dopesheet_header)

            if prefs.autokeying_header_graph_color_use:
                theme.graph_editor.space.header = prefs.autokeying_header_color_on
            else:
                theme.graph_editor.space.header = json.loads(prefs.original_graph_header)

            if prefs.autokeying_header_nla_color_use:
                theme.nla_editor.space.header = prefs.autokeying_header_color_on
            else:
                theme.nla_editor.space.header = json.loads(prefs.original_nla_header)

        if prefs.autokeying_playhead_color_use:
            theme.dopesheet_editor.frame_current = prefs.autokeying_playhead_color_on
            theme.graph_editor.frame_current = prefs.autokeying_playhead_color_on
            theme.nla_editor.frame_current = prefs.autokeying_playhead_color_on
        else:
            theme.dopesheet_editor.frame_current = json.loads(prefs.original_dopesheet_frame_current)
            theme.graph_editor.frame_current = json.loads(prefs.original_graph_frame_current)
            theme.nla_editor.frame_current = json.loads(prefs.original_nla_frame_current)


def reset_autokeying_theme_colors():
    prefs = bpy.context.preferences.addons[base_package].preferences
    theme = bpy.context.preferences.themes[0]
    autokeying_is_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    anim_offset = bpy.context.scene.amp_timeline_tools.anim_offset.mask_in_use

    # Restore original theme colors using JSON stored preferences
    if prefs.original_theme_captured and not autokeying_is_on and not anim_offset:
        theme.dopesheet_editor.space.header = json.loads(prefs.original_dopesheet_header)
        theme.graph_editor.space.header = json.loads(prefs.original_graph_header)
        theme.nla_editor.space.header = json.loads(prefs.original_nla_header)
        theme.view_3d.object_active = json.loads(prefs.original_object_active)
        theme.view_3d.bone_pose_active = json.loads(prefs.original_bone_pose_active)
        theme.view_3d.space.header = json.loads(prefs.original_header)
        theme.dopesheet_editor.frame_current = json.loads(prefs.original_dopesheet_frame_current)
        theme.graph_editor.frame_current = json.loads(prefs.original_graph_frame_current)
        theme.nla_editor.frame_current = json.loads(prefs.original_nla_frame_current)


def capture_original_theme_colors():
    prefs = bpy.context.preferences.addons[base_package].preferences
    theme = bpy.context.preferences.themes[0]
    autokeying_is_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    anim_offset = bpy.context.scene.amp_timeline_tools.anim_offset.mask_in_use
    if not prefs.original_theme_captured:
        # Convert theme colors and settings to JSON string for storage
        prefs.original_dopesheet_header = json.dumps(theme.dopesheet_editor.space.header[:])
        prefs.original_graph_header = json.dumps(theme.graph_editor.space.header[:])
        prefs.original_nla_header = json.dumps(theme.nla_editor.space.header[:])
        prefs.original_object_active = json.dumps(theme.view_3d.object_active[:])
        prefs.original_bone_pose_active = json.dumps(theme.view_3d.bone_pose_active[:])
        prefs.original_header = json.dumps(theme.view_3d.space.header[:])
        prefs.original_dopesheet_frame_current = json.dumps(theme.dopesheet_editor.frame_current[:])
        prefs.original_graph_frame_current = json.dumps(theme.graph_editor.frame_current[:])
        prefs.original_nla_frame_current = json.dumps(theme.nla_editor.frame_current[:])

    prefs.original_theme_captured = True


def refresh_ui(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


# def matches_key_combination(event, key_combination):
#     """
#     Check if the event matches the given key combination.
#     key_combination is a string like 'CTRL+SHIFT+Z'.
#     """
#     components = key_combination.split("+")
#     main_key = components[-1]  # The main key is always the last component
#     modifiers = set(components[:-1])  # All but the last component are modifiers

#     # Check if the main key matches
#     if event.type != main_key or event.value != "PRESS":
#         return False

#     # Check if the required modifiers are pressed
#     if "CTRL" in modifiers and not event.ctrl:
#         return False
#     if "SHIFT" in modifiers and not event.shift:
#         return False
#     if "ALT" in modifiers and not event.alt:
#         return False
#     if "OSKEY" in modifiers and not event.oskey:
#         return False

#     return True


def matches_key_combination(event, key_combination, event_type="PRESS", ignore_modifiers=False):
    """
    Check if the event matches the given key combination and type (e.g., "PRESS" or "RELEASE").
    key_combination is a string like 'CTRL+SHIFT+Z'.
    event_type specifies the type of keyboard event to match (default is "PRESS").
    ignore_modifiers: if True, only checks the main key, ignoring modifier states
    """
    # Split the key combination into components and normalize to uppercase
    components = key_combination.upper().split("+")
    main_key = components[-1]  # The main key is always the last component

    # Check if the main key matches and the event type matches
    if event.type.upper() != main_key or event.value.upper() != event_type.upper():
        return False

    # If ignore_modifiers is True, we only care about the main key match
    if ignore_modifiers:
        return True

    # Otherwise, proceed with normal modifier checking
    required_modifiers = set(components[:-1])  # All but the last component are modifiers

    # Collect currently pressed modifiers
    current_modifiers = set()
    if event.ctrl:
        current_modifiers.add("CTRL")
    if event.shift:
        current_modifiers.add("SHIFT")
    if event.alt:
        current_modifiers.add("ALT")
    if event.oskey:
        current_modifiers.add("OSKEY")

    # Ensure that the current modifiers exactly match the required modifiers
    return current_modifiers == required_modifiers


def get_dpi_scale():
    """
    Calculate scaling factor based on screen DPI or return 1.0 if DPI adaptation is disabled.

    Returns:
        float: DPI scaling factor.
    """
    try:
        prefs = bpy.context.preferences.addons[base_package].preferences
        overlay_adapt_dpi = prefs.overlay_adapt_dpi
    except (KeyError, AttributeError):
        overlay_adapt_dpi = True

    if overlay_adapt_dpi:
        screen_dpi = bpy.context.preferences.system.dpi
        base_dpi = 72
        return screen_dpi / base_dpi
    else:
        return 1.0


_draw_handlers = {
    "GRAPH_EDITOR": None,
    "DOPESHEET_EDITOR": None,
    "NLA_EDITOR": None,
}


def draw_callback(color, coords):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": coords})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def amp_draw_header_handler(action="ADD", color=None):
    def make_draw_callback(space_type, color=None):
        def callback():
            scale = get_dpi_scale()
            region = bpy.context.region
            width, height = region.width, region.height
            header_height = 24 * scale
            coords = [
                (0, height - header_height),
                (width, height - header_height),
                (width, height),
                (0, height),
            ]

            theme = bpy.context.preferences.themes[0]
            selected_object_color = theme.view_3d.object_selected
            if color is None:
                current_color = (
                    selected_object_color[0],
                    selected_object_color[1],
                    selected_object_color[2],
                    0.5,
                )
            else:
                current_color = color

            draw_callback(current_color, coords)

        return callback

    editors = {
        "GRAPH_EDITOR": bpy.types.SpaceGraphEditor,
        "DOPESHEET_EDITOR": bpy.types.SpaceDopeSheetEditor,
        "NLA_EDITOR": bpy.types.SpaceNLA,
    }

    for editor_key, editor_space in editors.items():
        if action == "ADD" and not _draw_handlers.get(editor_key):
            _draw_handlers[editor_key] = editor_space.draw_handler_add(
                make_draw_callback(editor_space, color), (), "WINDOW", "POST_PIXEL"
            )
        elif action == "REMOVE" and _draw_handlers.get(editor_key):
            editor_space.draw_handler_remove(_draw_handlers[editor_key], "WINDOW")
            _draw_handlers[editor_key] = None


def find_editor_override(context, area_types):
    """
    Find the first open area whose type is in `area_types`,
    and build a context override dict for it.
    """
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in area_types:
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region:
                    ov = context.copy()
                    ov.update(
                        {
                            "window": window,
                            "screen": window.screen,
                            "area": area,
                            "region": region,
                        }
                    )
                    return ov
    return None
