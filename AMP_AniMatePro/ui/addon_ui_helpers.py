import bpy
import json
import os
from bpy.types import AddonPreferences, Panel, PropertyGroup, UIList, Operator
from bpy.props import (
    BoolProperty,
    IntProperty,
    StringProperty,
    CollectionProperty,
    PointerProperty,
    EnumProperty,
    FloatProperty,
)

from ..utils.customIcons import get_icon, get_icon_id
from ..utils import (
    refresh_ui,
    get_prefs,
    ptr_to_dict,
    dict_to_ptr,
    get_contextual_row,
    get_contextual_button_entry,
    get_contextual_category,
    get_contextual_owner_collection_indices,
    set_operator_context,
)
from ..utils.version_manager import is_forge_version
from .. import __package__ as base_package


# Global flag to prevent redundant category loading
_default_categories_loaded = False


def _load_all_default_categories():
    """Load all default categories from the default_categories folder - single efficient load"""
    import os
    import json

    # Get the ui directory and construct path to default_categories folder
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    default_categories_path = os.path.join(ui_dir, "default_categories")

    if not os.path.exists(default_categories_path):
        print(f"[AMP] Default categories folder not found: {default_categories_path}")
        return []

    default_categories = []

    try:
        for file_name in sorted(os.listdir(default_categories_path)):
            if file_name.endswith(".json"):
                file_path = os.path.join(default_categories_path, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Store the file name as the default_cat_id (keep full filename with .json)
                    data["default_cat_id"] = file_name
                    default_categories.append(data)
                    print(f"[AMP] Found default category: {data.get('name', 'Unknown')} from {file_name}")
                except Exception as e:
                    print(f"[AMP] Error loading default category file '{file_name}': {e}")
                    continue

    except Exception as e:
        print(f"[AMP] Error reading default categories folder: {e}")

    print(f"[AMP] Loaded {len(default_categories)} default category definitions")
    return default_categories


def _load_all_default_popup_panels():
    """Load all default popup panels from the default_popup folder - single efficient load"""

    # Get the ui directory and construct path to default_popup folder
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    default_popup_path = os.path.join(ui_dir, "default_popup")

    if not os.path.exists(default_popup_path):
        print(f"[AMP] Default popup panels folder not found: {default_popup_path}")
        return []

    default_popup_panels = []

    try:
        for file_name in sorted(os.listdir(default_popup_path)):
            if file_name.endswith(".json"):
                file_path = os.path.join(default_popup_path, file_name)
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        popup_data = json.load(f)
                        # Validate that this is a popup panel definition
                        if isinstance(popup_data, dict):
                            # Set default_popup_id to filename (without .json extension) if not present
                            if "default_popup_id" not in popup_data or not popup_data["default_popup_id"]:
                                popup_data["default_popup_id"] = file_name[:-5]  # Remove .json extension
                                print(
                                    f"[AMP] Set default_popup_id to '{popup_data['default_popup_id']}' for {file_name}"
                                )
                            default_popup_panels.append(popup_data)
                        else:
                            print(f"[AMP] Invalid popup panel definition in {file_name} - not a dictionary")
                    except json.JSONDecodeError as e:
                        print(f"[AMP] JSON error in {file_name}: {e}")

    except Exception as e:
        print(f"[AMP] Error reading default popup panels folder: {e}")

    print(f"[AMP] Loaded {len(default_popup_panels)} default popup panel definitions")
    return default_popup_panels


def _ensure_default_content_loaded(force_fresh_install=False):
    """Efficiently load and sync default categories and pie menus - only when needed"""
    global _default_categories_loaded
    prefs = get_prefs()

    # Skip if content is already loaded and this isn't a forced refresh
    if _default_categories_loaded and not prefs.fresh_install and not force_fresh_install:
        print("[AMP] Default content already processed, skipping")
        return

    # Also skip if content exists and this isn't a fresh install or forced update
    if not prefs.fresh_install and not force_fresh_install:
        has_default_categories = any(cat.default_cat_id for cat in prefs.ui_categories)
        has_default_popup_panels = any(getattr(popup, "default_popup_id", "") for popup in prefs.popup_panels)
        if has_default_categories and has_default_popup_panels:
            print("[AMP] Default content exists, skipping incremental load")
            _default_categories_loaded = True
            return

    # Don't load content if fresh_install is True but force_fresh_install is False
    # This indicates we're waiting for user input via the version dialog
    if prefs.fresh_install and not force_fresh_install:
        print("[AMP] Fresh install detected but not forced - waiting for user action")
        return

    print(f"[AMP] Processing default content - fresh_install={prefs.fresh_install}, force={force_fresh_install}")

    # Load both categories and popup panels
    default_categories = _load_all_default_categories()
    default_popup_panels = _load_all_default_popup_panels()

    if not default_categories and not default_popup_panels:
        print("[AMP] No default content found in folders")
        _default_categories_loaded = True
        return

    # Track changes
    cat_loaded_count = 0
    cat_converted_count = 0
    cat_restored_count = 0
    popup_loaded_count = 0
    popup_converted_count = 0
    popup_restored_count = 0

    # === Process Categories ===
    if default_categories:
        # Create a lookup for default categories by ID
        default_cat_lookup = {data.get("default_cat_id", ""): data for data in default_categories}

        # Fresh install or version update - replace all default categories
        if prefs.fresh_install or force_fresh_install:
            operation_type = "Fresh install" if prefs.fresh_install else "Version update"
            print(f"[AMP] {operation_type} detected - updating default categories")

            # Remove existing default categories efficiently
            categories_to_remove = [i for i, cat in enumerate(prefs.ui_categories) if cat.default_cat_id]
            for i in reversed(categories_to_remove):
                prefs.ui_categories.remove(i)

            if categories_to_remove:
                print(f"[AMP] Removed {len(categories_to_remove)} existing default categories")

            # Add new default categories at the beginning
            for i, default_data in enumerate(default_categories):
                new_cat = prefs.ui_categories.add()
                dict_to_ptr(new_cat, default_data)
                new_cat.default_cat_id = default_data.get("default_cat_id", "")
                prefs.ui_categories.move(len(prefs.ui_categories) - 1, i)
                cat_loaded_count += 1

            print(f"[AMP] {operation_type} complete: {cat_loaded_count} default categories loaded")

        else:
            # Incremental update - only process changes
            existing_defaults = {cat.default_cat_id: cat for cat in prefs.ui_categories if cat.default_cat_id}

            # Convert orphaned categories (files no longer exist)
            for cat_id, cat in list(existing_defaults.items()):
                if cat_id not in default_cat_lookup:
                    cat.default_cat_id = ""  # Convert to custom category
                    cat_converted_count += 1
                    print(f"[AMP] Converted orphaned category '{cat.name}' to custom")

            # Update existing defaults and add missing ones
            for default_data in default_categories:
                cat_id = default_data.get("default_cat_id", "")
                if cat_id in existing_defaults:
                    # Update existing default category
                    _preserve_and_update_category(existing_defaults[cat_id], default_data)
                    cat_restored_count += 1
                else:
                    # Add missing default category
                    new_cat = prefs.ui_categories.add()
                    dict_to_ptr(new_cat, default_data)
                    new_cat.default_cat_id = cat_id
                    # Move to beginning with other defaults
                    default_count = len([c for c in prefs.ui_categories if c.default_cat_id])
                    prefs.ui_categories.move(len(prefs.ui_categories) - 1, default_count - 1)
                    cat_loaded_count += 1

            # Report incremental changes
            cat_changes = cat_loaded_count + cat_converted_count + cat_restored_count
            if cat_changes > 0:
                print(
                    f"[AMP] Categories updated: {cat_loaded_count} new, {cat_restored_count} updated, {cat_converted_count} converted"
                )

    # === Process Popup Panels ===
    if default_popup_panels:
        # Create a lookup for default popup panels by ID
        default_popup_lookup = {data.get("default_popup_id", ""): data for data in default_popup_panels}

        # Fresh install or version update - replace all default popup panels
        if prefs.fresh_install or force_fresh_install:
            operation_type = "Fresh install" if prefs.fresh_install else "Version update"
            print(f"[AMP] {operation_type} detected - updating default popup panels")

            # Remove existing default popup panels efficiently
            popup_panels_to_remove = [
                i for i, popup in enumerate(prefs.popup_panels) if getattr(popup, "default_popup_id", "")
            ]
            for i in reversed(popup_panels_to_remove):
                prefs.popup_panels.remove(i)

            if popup_panels_to_remove:
                print(f"[AMP] Removed {len(popup_panels_to_remove)} existing default popup panels")

            # Add new default popup panels at the beginning
            for i, default_data in enumerate(default_popup_panels):
                new_popup = prefs.popup_panels.add()
                dict_to_ptr(new_popup, default_data)
                # Ensure default_popup_id is properly set (should already be set by dict_to_ptr)
                expected_popup_id = default_data.get("default_popup_id", "")
                if (
                    not hasattr(new_popup, "default_popup_id")
                    or getattr(new_popup, "default_popup_id", "") != expected_popup_id
                ):
                    new_popup.default_popup_id = expected_popup_id
                # Ensure popup_width has a sensible default if not present in the data
                if not hasattr(new_popup, "popup_width") or getattr(new_popup, "popup_width", 0) <= 0:
                    new_popup.popup_width = 400
                prefs.popup_panels.move(len(prefs.popup_panels) - 1, i)
                popup_loaded_count += 1

            print(f"[AMP] {operation_type} complete: {popup_loaded_count} default popup panels loaded")

        else:
            # Incremental update - only process changes
            existing_default_popups = {
                getattr(popup, "default_popup_id", ""): popup
                for popup in prefs.popup_panels
                if getattr(popup, "default_popup_id", "")
            }

            # Convert orphaned popup panels (files no longer exist)
            for popup_id, popup in list(existing_default_popups.items()):
                if popup_id not in default_popup_lookup:
                    if hasattr(popup, "default_popup_id"):
                        popup.default_popup_id = ""  # Convert to custom popup panel
                    popup_converted_count += 1
                    print(f"[AMP] Converted orphaned popup panel '{popup.name}' to custom")

            # Update existing defaults and add missing ones
            for default_data in default_popup_panels:
                popup_id = default_data.get("default_popup_id", "")
                if popup_id in existing_default_popups:
                    # Update existing default popup panel
                    _preserve_and_update_popup_panel(existing_default_popups[popup_id], default_data)
                    popup_restored_count += 1
                else:
                    # Add missing default popup panel
                    new_popup = prefs.popup_panels.add()
                    dict_to_ptr(new_popup, default_data)
                    # Ensure default_popup_id is properly set (should already be set by dict_to_ptr)
                    if (
                        not hasattr(new_popup, "default_popup_id")
                        or getattr(new_popup, "default_popup_id", "") != popup_id
                    ):
                        new_popup.default_popup_id = popup_id
                    # Ensure popup_width has a sensible default if not present in the data
                    if not hasattr(new_popup, "popup_width") or getattr(new_popup, "popup_width", 0) <= 0:
                        new_popup.popup_width = 400
                    # Move to beginning with other defaults
                    default_count = len([p for p in prefs.popup_panels if getattr(p, "default_popup_id", "")])
                    prefs.popup_panels.move(len(prefs.popup_panels) - 1, default_count - 1)
                    popup_loaded_count += 1

            # Report incremental changes
            popup_changes = popup_loaded_count + popup_converted_count + popup_restored_count
            if popup_changes > 0:
                print(
                    f"[AMP] Popup panels updated: {popup_loaded_count} new, {popup_restored_count} updated, {popup_converted_count} converted"
                )

    # Mark fresh install as complete and set loaded flag
    if prefs.fresh_install:
        prefs.fresh_install = False
    _default_categories_loaded = True

    # Refresh UI only if changes were made
    total_changes = (
        cat_loaded_count
        + cat_converted_count
        + cat_restored_count
        + popup_loaded_count
        + popup_converted_count
        + popup_restored_count
    )
    if total_changes > 0:
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    area.tag_redraw()
        except:
            pass

    print(f"[AMP] Default content processing complete")


def _preserve_and_update_popup_panel(popup, default_data):
    """Update popup panel while preserving user-customized settings"""
    # Store user settings to preserve
    preserved_settings = {
        "name": popup.name,  # Preserve custom names
        "active_category_index": popup.active_category_index,
        "popup_width": getattr(popup, "popup_width", 400),  # Preserve custom width
        # Add any other popup panel specific settings that should be preserved
    }

    # Update with new default data
    dict_to_ptr(popup, default_data)
    if hasattr(popup, "default_popup_id"):
        popup.default_popup_id = default_data.get("default_popup_id", "")

    # Restore preserved settings
    for attr_name, value in preserved_settings.items():
        if hasattr(popup, attr_name):
            setattr(popup, attr_name, value)


def _preserve_and_update_category(cat, default_data):
    """Update category while preserving user-customized settings"""
    # Store user settings to preserve
    preserved_settings = {
        "top_nla_pin": cat.top_nla_pin,
        "top_graph_pin": cat.top_graph_pin,
        "top_dope_pin": cat.top_dope_pin,
        "side_nla_pin": cat.side_nla_pin,
        "side_graph_pin": cat.side_graph_pin,
        "side_dope_pin": cat.side_dope_pin,
        "side_view_pin": cat.side_view_pin,
        "pin_global": cat.pin_global,
        "show": cat.show,
        "properties": cat.properties,
        "style": cat.style,
        "indent": cat.indent,
        "cat_sections_collapse_style": cat.cat_sections_collapse_style,
        "cat_sections_icon_as_toggle": cat.cat_sections_icon_as_toggle,
        # Active states
        "top_nla_active": getattr(cat, "top_nla_active", False),
        "top_graph_active": getattr(cat, "top_graph_active", False),
        "top_dope_active": getattr(cat, "top_dope_active", False),
        "side_nla_active": getattr(cat, "side_nla_active", False),
        "side_graph_active": getattr(cat, "side_graph_active", False),
        "side_dope_active": getattr(cat, "side_dope_active", False),
        "side_view_active": getattr(cat, "side_view_active", False),
    }

    # Update with new default data
    dict_to_ptr(cat, default_data)
    cat.default_cat_id = default_data.get("default_cat_id", "")

    # Restore preserved settings
    for attr_name, value in preserved_settings.items():
        if hasattr(cat, attr_name):
            setattr(cat, attr_name, value)


def _restore_popup_panels_only(prefs):
    """Restore only default popup panels"""
    from .addon_ui_helpers import _load_all_default_popup_panels

    # Load default popup panels
    default_popup_panels = _load_all_default_popup_panels()
    if not default_popup_panels:
        print("[AMP] No default popup panels found in folder")
        return

    # Store previous settings for default popup panels
    old_settings = {}
    for popup in prefs.popup_panels:
        popup_id = getattr(popup, "default_popup_id", "")
        if popup_id:
            old_settings[popup_id] = {
                "name": popup.name,
                "active_category_index": popup.active_category_index,
                "hotkey_string": getattr(popup, "hotkey_string", ""),
                "hotkey_space": getattr(popup, "hotkey_space", "ALL_SPACES"),
            }

    # Remove existing default popup panels efficiently
    popup_panels_to_remove = [i for i, popup in enumerate(prefs.popup_panels) if getattr(popup, "default_popup_id", "")]
    for i in reversed(popup_panels_to_remove):
        prefs.popup_panels.remove(i)

    if popup_panels_to_remove:
        print(f"[AMP] Removed {len(popup_panels_to_remove)} existing default popup panels")

    loaded_count = 0

    for i, default_data in enumerate(default_popup_panels):
        new_popup = prefs.popup_panels.add()
        dict_to_ptr(new_popup, default_data)

        # Always ensure default_popup_id is set correctly from the data
        popup_id = default_data.get("default_popup_id", "")
        if hasattr(new_popup, "default_popup_id") and popup_id:
            new_popup.default_popup_id = popup_id
            print(f"[AMP] Set default_popup_id to '{popup_id}' for popup panel '{new_popup.name}'")

        # Restore user settings if they existed
        if popup_id in old_settings:
            for attr_name, value in old_settings[popup_id].items():
                if hasattr(new_popup, attr_name):
                    setattr(new_popup, attr_name, value)
                    print(f"[AMP] Restored {attr_name}='{value}' for popup panel '{popup_id}'")

        prefs.popup_panels.move(len(prefs.popup_panels) - 1, i)
        loaded_count += 1

    # Reset active popup panel index
    if prefs.popup_panels:
        prefs.active_popup_panel_index = 0

    print(f"[AMP] Restored {loaded_count} default popup panels")


def get_collapse_icon(is_open, collapse_style=None, category=None):
    """
    Returns the appropriate collapse icon based on the collapse style and open state.

    Args:
        is_open (bool): Whether the section is open/expanded
        collapse_style (str): The collapse style preference. If None, uses current preference.
        category (UI_CategoryGroup): Optional category to check for overrides.

    Returns:
        str: The icon name for the collapse state
    """
    if collapse_style is None:
        prefs = get_prefs()
        # Check for category override first
        if (
            category
            and hasattr(category, "cat_sections_collapse_style")
            and category.cat_sections_collapse_style != "GLOBAL"
        ):
            collapse_style = category.cat_sections_collapse_style
        else:
            collapse_style = prefs.sections_collapse_style

    if collapse_style == "THIN":
        return "DOWNARROW_HLT" if is_open else "RIGHTARROW_THIN"
    elif collapse_style == "THICK":
        return "TRIA_DOWN" if is_open else "TRIA_RIGHT"
    elif collapse_style == "EYE":
        return "HIDE_OFF" if is_open else "HIDE_ON"
    elif collapse_style == "RADIO":
        return "RADIOBUT_ON" if is_open else "RADIOBUT_OFF"
    else:
        # Default fallback to thin arrows
        return "DOWNARROW_HLT" if is_open else "RIGHTARROW_THIN"


from ..operators import toggles


def draw_ui_section(layout, context, zone, title, section_icon, fn, start_open=True):
    col = layout.column()
    title_box = col.box()
    # title row with toggle button
    title_row = title_box.row(align=True)
    title_row.label(text=title, icon=section_icon)

    # use start_open as default state
    toggle_icon = "TRIA_DOWN" if toggles.get(zone, start_open) else "TRIA_RIGHT"
    op = title_row.operator("ui.amp_toggle_panel_visibility", text="", emboss=False, icon=toggle_icon)
    op.panel_name = zone
    op.default_open = start_open

    # only draw body if expanded (default open) into the title_box:
    if toggles.get(zone, start_open):
        fn(context, title_box, zone)

    col.separator()

    return title_box
