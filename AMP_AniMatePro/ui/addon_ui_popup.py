import json
import ast
import bpy
from bpy.types import Operator, UIList
from bpy.props import IntProperty, StringProperty
from types import SimpleNamespace
from ..utils import refresh_ui, get_prefs, ptr_to_dict, dict_to_ptr, set_operator_context
from ..utils.customIcons import get_icon
from .addon_ui import draw_config_ui, _draw_rows_for_category


# -----------------------------------------------------------------------------
# Operators: Add/Delete Popup Panel
# -----------------------------------------------------------------------------
class AMP_OT_popup_panel_add(Operator):
    bl_idname = "amp.popup_panel_add"
    bl_label = "Add Popup Panel"
    bl_description = "Add a new popup panel with default category and settings"

    def execute(self, context):
        prefs = get_prefs()
        idx = prefs.active_popup_panel_index + 1

        pm = prefs.popup_panels.add()
        pm.name = "Popup Panel"

        cats = pm.categories
        init_cat = cats.add()
        init_cat.name = "Category"
        init_cat.icon = "AniMateProContact"
        init_cat.style = "BOX_TITLE"
        pm.active_category_index = 0

        prefs.popup_panels.move(len(prefs.popup_panels) - 1, idx)
        prefs.active_popup_panel_index = idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_popup_panel_delete(Operator):
    bl_idname = "amp.popup_panel_delete"
    bl_label = "Delete Popup Panel"
    bl_description = "Delete the selected popup panel and unregister its hotkey"
    index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()
        if 0 <= self.index < len(prefs.popup_panels):
            # Unregister the hotkey before deleting the popup panel
            from .addon_ui_popup_utils import unregister_popup_panel_hotkey

            unregister_popup_panel_hotkey(self.index)

            prefs.popup_panels.remove(self.index)
            prefs.active_popup_panel_index = min(
                max(0, prefs.active_popup_panel_index - 1),
                len(prefs.popup_panels) - 1,
            )
        return {"FINISHED"}


class AMP_OT_popup_panel_move_up(Operator):
    bl_idname = "amp.popup_panel_move_up"
    bl_label = "Move Popup Panel Up"
    bl_description = "Move the selected popup panel one position up in the list"

    def execute(self, context):
        prefs = get_prefs()
        idx = prefs.active_popup_panel_index
        if idx > 0:
            prefs.popup_panels.move(idx, idx - 1)
            prefs.active_popup_panel_index = idx - 1
        return {"FINISHED"}


class AMP_OT_popup_panel_move_down(Operator):
    bl_idname = "amp.popup_panel_move_down"
    bl_label = "Move Popup Panel Down"
    bl_description = "Move the selected popup panel one position down in the list"

    def execute(self, context):
        prefs = get_prefs()
        idx = prefs.active_popup_panel_index
        if idx < len(prefs.popup_panels) - 1:
            prefs.popup_panels.move(idx, idx + 1)
            prefs.active_popup_panel_index = idx + 1
        return {"FINISHED"}


class AMP_OT_popup_panel_copy(Operator):
    bl_idname = "amp.popup_panel_copy"
    bl_label = "Copy Popup Panel"
    bl_description = "Copy the selected popup panel with all categories and content to clipboard"

    def execute(self, context):
        prefs = get_prefs()
        pm = prefs.popup_panels[prefs.active_popup_panel_index]
        data = ptr_to_dict(pm)

        # Include categories with full recursive content (rows and buttons)
        categories_data = []
        for cat in pm.categories:
            cat_data = ptr_to_dict(cat)
            # Ensure copied categories are not default
            cat_data["default_cat_id"] = ""
            # Include all rows with their buttons
            rows_data = []
            for row in cat.rows:
                row_data = ptr_to_dict(row)
                # Include all buttons in the row
                row_data["buttons"] = [ptr_to_dict(btn) for btn in row.buttons]
                rows_data.append(row_data)
            cat_data["rows"] = rows_data
            categories_data.append(cat_data)

        data["categories"] = categories_data
        # Only clear default_popup_id if this is a default popup panel being copied
        # This preserves the original default_popup_id for reference
        if not getattr(pm, "default_popup_id", ""):
            data["default_popup_id"] = ""

        # Clear keymap properties in copied data
        data["keymap_operator_properties"] = ""
        data["keymap_key"] = ""
        data["keymap_ctrl"] = False
        data["keymap_alt"] = False
        data["keymap_shift"] = False
        data["keymap_os"] = False
        data["hotkey_string"] = ""
        data["is_capturing_hotkey"] = False

        context.window_manager.clipboard = json.dumps(data)
        self.report({"INFO"}, "Popup Panel with complete content copied to clipboard")
        return {"FINISHED"}


class AMP_OT_popup_panel_paste(Operator):
    bl_idname = "amp.popup_panel_paste"
    bl_label = "Paste Popup Panel"
    bl_description = "Paste a popup panel from clipboard with all categories and content"

    def validate_popup_panel_data(self, data):
        """Validate that the clipboard data is a valid popup panel"""
        if not isinstance(data, dict):
            return False, "Clipboard data is not a valid dictionary"

        # Check for required popup panel properties
        required_props = ["name"]
        for prop in required_props:
            if prop not in data:
                return False, f"Missing required property: {prop}"

        # Validate categories structure if present
        if "categories" in data:
            if not isinstance(data["categories"], list):
                return False, "Categories must be a list"

            for i, cat_data in enumerate(data["categories"]):
                if not isinstance(cat_data, dict):
                    return False, f"Category {i} is not a valid dictionary"

                # Check for required category properties
                if "name" not in cat_data:
                    return False, f"Category {i} missing required property: name"

                # Validate rows structure if present
                if "rows" in cat_data:
                    if not isinstance(cat_data["rows"], list):
                        return False, f"Category {i} rows must be a list"

                    for j, row_data in enumerate(cat_data["rows"]):
                        if not isinstance(row_data, dict):
                            return False, f"Category {i}, row {j} is not a valid dictionary"

                        # Validate buttons structure if present
                        if "buttons" in row_data:
                            if not isinstance(row_data["buttons"], list):
                                return False, f"Category {i}, row {j} buttons must be a list"

                            for k, btn_data in enumerate(row_data["buttons"]):
                                if not isinstance(btn_data, dict):
                                    return False, f"Category {i}, row {j}, button {k} is not a valid dictionary"

        return True, "Valid popup panel data"

    def execute(self, context):
        prefs = get_prefs()
        clip = context.window_manager.clipboard

        if not clip.strip():
            self.report({"WARNING"}, "Clipboard is empty")
            return {"CANCELLED"}

        try:
            data = json.loads(clip)
        except Exception:
            try:
                data = ast.literal_eval(clip)
            except Exception:
                self.report({"WARNING"}, "Clipboard does not contain valid JSON or Python literal")
                return {"CANCELLED"}

        # Validate the data structure
        is_valid, message = self.validate_popup_panel_data(data)
        if not is_valid:
            self.report({"WARNING"}, f"Invalid popup panel data: {message}")
            return {"CANCELLED"}

        idx = prefs.active_popup_panel_index + 1
        new = prefs.popup_panels.add()

        # Handle categories data separately to ensure proper reconstruction
        categories_data = data.pop("categories", [])
        dict_to_ptr(new, data)
        # Clear default_popup_id so pasted popup panel is always custom
        if hasattr(new, "default_popup_id"):
            new.default_popup_id = ""

        # Clear keymap properties for pasted popup panel
        # Temporarily disable update callbacks during bulk property setting
        new.is_capturing_hotkey = True  # This will prevent the update callback from firing
        new.keymap_operator_properties = ""
        new.keymap_key = ""
        new.keymap_ctrl = False
        new.keymap_alt = False
        new.keymap_shift = False
        new.keymap_os = False
        new.hotkey_string = ""
        new.is_capturing_hotkey = False  # Re-enable update callbacks

        # Reconstruct categories with full content
        new.categories.clear()
        for cat_data in categories_data:
            # Ensure pasted categories are not default
            cat_data["default_cat_id"] = ""
            new_cat = new.categories.add()
            # Handle rows data separately
            rows_data = cat_data.pop("rows", [])
            dict_to_ptr(new_cat, cat_data)

            # Reconstruct rows with buttons
            new_cat.rows.clear()
            for row_data in rows_data:
                new_row = new_cat.rows.add()
                # Handle buttons data separately
                buttons_data = row_data.pop("buttons", [])
                dict_to_ptr(new_row, row_data)

                # Reconstruct buttons
                new_row.buttons.clear()
                for btn_data in buttons_data:
                    new_btn = new_row.buttons.add()
                    dict_to_ptr(new_btn, btn_data)

                # Restore buttons data for potential other uses
                row_data["buttons"] = buttons_data

            # Restore rows data for potential other uses
            cat_data["rows"] = rows_data

        # Restore categories data for potential other uses
        data["categories"] = categories_data

        prefs.popup_panels.move(len(prefs.popup_panels) - 1, idx)
        prefs.active_popup_panel_index = idx
        refresh_ui(context)
        self.report({"INFO"}, "Popup Panel with complete content pasted")
        return {"FINISHED"}


class AMP_OT_popup_panel_duplicate(Operator):
    bl_idname = "amp.popup_panel_duplicate"
    bl_label = "Duplicate Popup Panel"
    bl_description = "Create an exact copy of the selected popup panel with all content"

    def execute(self, context):
        prefs = get_prefs()
        src = prefs.popup_panels[prefs.active_popup_panel_index]
        data = ptr_to_dict(src)

        # Include categories with full recursive content (rows and buttons)
        categories_data = []
        for cat in src.categories:
            cat_data = ptr_to_dict(cat)
            # Ensure duplicated categories are not default
            cat_data["default_cat_id"] = ""
            # Include all rows with their buttons
            rows_data = []
            for row in cat.rows:
                row_data = ptr_to_dict(row)
                # Include all buttons in the row
                row_data["buttons"] = [ptr_to_dict(btn) for btn in row.buttons]
                rows_data.append(row_data)
            cat_data["rows"] = rows_data
            categories_data.append(cat_data)
        data["categories"] = categories_data

        # Clear keymap properties in the data before creating the new popup panel
        data["keymap_operator_properties"] = ""
        data["keymap_key"] = ""
        data["keymap_ctrl"] = False
        data["keymap_alt"] = False
        data["keymap_shift"] = False
        data["keymap_os"] = False
        data["hotkey_string"] = ""
        data["is_capturing_hotkey"] = False

        idx = prefs.active_popup_panel_index + 1
        new = prefs.popup_panels.add()
        categories_data = data.pop("categories", [])
        dict_to_ptr(new, data)
        new.name += " Copy"
        # Clear default_popup_id so duplicated popup panel is always custom
        if hasattr(new, "default_popup_id"):
            new.default_popup_id = ""
        new.categories.clear()

        # No need to clear keymap properties again since they're already cleared in data
        # Temporarily disable update callbacks during category reconstruction
        new.is_capturing_hotkey = True  # This will prevent the update callback from firing

        for cat_data in categories_data:
            # Ensure duplicated categories are not default
            cat_data["default_cat_id"] = ""
            new_cat = new.categories.add()
            rows_data = cat_data.pop("rows", [])
            dict_to_ptr(new_cat, cat_data)
            new_cat.rows.clear()
            for row_data in rows_data:
                new_row = new_cat.rows.add()
                buttons_data = row_data.pop("buttons", [])
                dict_to_ptr(new_row, row_data)
                new_row.buttons.clear()
                for btn_data in buttons_data:
                    new_btn = new_row.buttons.add()
                    dict_to_ptr(new_btn, btn_data)

        # Re-enable update callbacks
        new.is_capturing_hotkey = False

        prefs.popup_panels.move(len(prefs.popup_panels) - 1, idx)
        prefs.active_popup_panel_index = idx
        refresh_ui(context)
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Operators: Popup Panel Category Add
# -----------------------------------------------------------------------------
class AMP_OT_popup_panel_category_add(Operator):
    bl_idname = "amp.popup_panel_category_add"
    bl_label = "Add Category to Popup Panel"
    bl_description = "Add a new category to the selected popup panel (unlimited categories)"

    def execute(self, context):
        prefs = get_prefs()
        # clamp popup panel index
        prefs.active_popup_panel_index = min(prefs.active_popup_panel_index, len(prefs.popup_panels) - 1)
        pm = prefs.popup_panels[prefs.active_popup_panel_index]
        cats = pm.categories
        idx = len(cats)
        cat = cats.add()
        cat.name = "Category"
        pm.active_category_index = idx
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Operators: Clear Popup Panel Hotkey
# -----------------------------------------------------------------------------
class AMP_OT_popup_panel_clear_hotkey(Operator):
    """Clear the hotkey for a popup panel"""

    bl_idname = "amp.popup_panel_clear_hotkey"
    bl_label = "Clear Popup Panel Hotkey"
    bl_description = "Remove the assigned hotkey from the selected popup panel"

    popup_panel_index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()

        if 0 <= self.popup_panel_index < len(prefs.popup_panels):
            popup_panel = prefs.popup_panels[self.popup_panel_index]
            popup_panel.hotkey_string = ""
            popup_panel.is_capturing_hotkey = False

            from .addon_ui_popup_utils import unregister_popup_panel_hotkey

            # Unregister the hotkey
            unregister_popup_panel_hotkey(self.popup_panel_index)

            self.report({"INFO"}, "Hotkey cleared")

            # Refresh UI
            for area in context.screen.areas:
                area.tag_redraw()

        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Draw Helper
# -----------------------------------------------------------------------------
def draw_popup_panels_config_ui(context, layout, _region_key=None, data=None):
    prefs = get_prefs()
    obj = data or prefs

    header = layout.column()

    header_split = header.split(factor=0.5)

    header_name = header_split.row(align=True)
    header_name.scale_y = 0.65
    header_name.box().label(text="Popup Panels")

    butons_row = header_split.row()
    butons_row.operator("amp.popup_panel_add", icon="ADD", text="Add")

    # Set proper context for the restore operator
    op = butons_row.operator("amp.restore_default_ui_content", icon="FILE_REFRESH", text="")
    # When called from popup panel context, we're dealing with popup panels specifically
    # op.data_owner_is_popup_panel = True

    layout.separator(factor=0.25)

    row = layout.row()

    col = row.column()
    col.template_list("AMP_UL_PopupPanels", "", prefs, "popup_panels", prefs, "active_popup_panel_index")

    ops2 = row.column(align=True)
    ops2.operator("amp.popup_panel_move_up", icon="TRIA_UP", text="")
    ops2.operator("amp.popup_panel_move_down", icon="TRIA_DOWN", text="")
    ops2.separator(factor=0.5)
    ops2.operator("amp.popup_panel_copy", icon="COPYDOWN", text="")
    ops2.operator("amp.popup_panel_paste", icon="PASTEDOWN", text="")
    ops2.separator(factor=0.5)
    ops2.operator("amp.popup_panel_duplicate", icon="DUPLICATE", text="")


def draw_config_popup_ui(context, layout, _unused=None):
    prefs = get_prefs()
    split = layout.split(factor=0.5)

    config_col = split.column()

    draw_popup_panels_config_ui(context, config_col)
    layout.separator()

    if not prefs.popup_panels:
        return

    pm = prefs.popup_panels[min(prefs.active_popup_panel_index, len(prefs.popup_panels) - 1)]

    content_col = config_col.column()
    content_col.enabled = True if getattr(pm, "default_popup_id", "") == "" else False

    draw_config_ui(context, content_col, None, data=pm)

    popup_preview = split.column()
    popup_preview.box().label(text="Preview")

    draw_popup_preview(context, popup_preview, pm)


# -----------------------------------------------------------------------------
# Operators: Clear Popup Panel Hotkey
# -----------------------------------------------------------------------------
class AMP_OT_popup_panel_clear_hotkey(Operator):
    """Clear the hotkey for a popup panel"""

    bl_idname = "amp.popup_panel_clear_hotkey"
    bl_label = "Clear Popup Panel Hotkey"
    bl_description = "Remove the assigned hotkey from the selected popup panel"

    popup_panel_index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()

        if 0 <= self.popup_panel_index < len(prefs.popup_panels):
            popup_panel = prefs.popup_panels[self.popup_panel_index]
            popup_panel.hotkey_string = ""
            popup_panel.is_capturing_hotkey = False

            from .addon_ui_popup_utils import unregister_popup_panel_hotkey

            # Unregister the hotkey
            unregister_popup_panel_hotkey(self.popup_panel_index)

            self.report({"INFO"}, "Hotkey cleared")

            # Refresh UI
            for area in context.screen.areas:
                area.tag_redraw()

        return {"FINISHED"}


def draw_popup_panel_conflicts(layout, context, popup_panel, popup_panel_index):
    """Draw potential keymap conflicts for a popup panel hotkey"""
    if not popup_panel.hotkey_string:
        return

    try:
        # Parse the hotkey string (e.g., "CTRL+SHIFT+T")
        hotkey_parts = popup_panel.hotkey_string.split("+")
        key = hotkey_parts[-1]  # Last part is the key

        # Check for modifiers
        ctrl = "CTRL" in hotkey_parts
        alt = "ALT" in hotkey_parts
        shift = "SHIFT" in hotkey_parts
        oskey = "OSKEY" in hotkey_parts

        # Get space type for the popup panel
        space_type = popup_panel.hotkey_space

        # Import the conflict detection function from register_keymaps
        from ..register_keymaps import detect_conflicts_for_keymap_item
        from .addon_ui_popup_utils import SPACE_TYPE_TO_KEYMAP

        wm = context.window_manager
        kc = wm.keyconfigs.user

        if not kc:
            return

        # Create a mock KeyMapItem to use with the existing conflict detection
        class MockKeyMapItem:
            def __init__(self, key, ctrl, alt, shift, oskey):
                self.type = key
                self.value = "PRESS"
                self.ctrl = ctrl
                self.alt = alt
                self.shift = shift
                self.oskey = oskey
                self.key_modifier = "NONE"
                # Use the actual popup panel operator naming pattern
                self.idname = f"amp.popup_panel_{popup_panel_index}"

        # Create a mock KeyMap for the space type
        class MockKeyMap:
            def __init__(self, space_type):
                if space_type == "ALL_SPACES":
                    self.name = "Window"
                    self.space_type = "EMPTY"
                    self.region_type = "WINDOW"
                else:
                    keymap_name = SPACE_TYPE_TO_KEYMAP.get(space_type, "Window")
                    self.name = keymap_name
                    self.space_type = space_type
                    self.region_type = "WINDOW"
                self.is_modal = False

        mock_kmi = MockKeyMapItem(key, ctrl, alt, shift, oskey)
        mock_km = MockKeyMap(space_type)

        # Detect conflicts using the existing function
        conflicting_keymaps = detect_conflicts_for_keymap_item(wm, mock_km, mock_kmi)

        # Filter out conflicts with other popup panels and ensure exact key+modifier matches
        filtered_conflicts = []
        for conflict in conflicting_keymaps:
            # Skip conflicts with AMP popup panels (they use amp.popup_panel_X naming)
            if conflict["operator_name"].startswith("amp.popup_panel_"):
                continue
            # Skip conflicts with the same operator (though this should already be handled)
            if conflict["operator_name"] == mock_kmi.idname:
                continue
            # Verify exact key combination match (the detection function should already do this,
            # but we double-check to ensure exact modifier and key matching)
            conflict_kmi = conflict.get("keymap_item")
            if conflict_kmi:
                # Ensure exact match of all modifiers and key
                if (
                    conflict_kmi.type == key
                    and conflict_kmi.ctrl == ctrl
                    and conflict_kmi.alt == alt
                    and conflict_kmi.shift == shift
                    and conflict_kmi.oskey == oskey
                    and conflict_kmi.value == "PRESS"
                ):
                    # Only include conflicts that are actually active keymaps
                    if hasattr(conflict_kmi, "active") and not conflict_kmi.active:
                        continue
                    filtered_conflicts.append(conflict)

        if filtered_conflicts:
            # Import for the collapsible panel functionality
            from .. import changelog

            # Create a unique identifier for this popup panel's conflicts
            conflict_id = f"popup_panel_{popup_panel_index}_conflicts"

            conflict_container = layout.column()
            split_row = conflict_container.split(factor=0.5, align=True)
            row = split_row.row(align=True)
            row = split_row.row()

            # Show conflict icon and toggle button
            conflict_icon = "DOWNARROW_HLT" if changelog.panels_visibility.get(conflict_id, False) else "ERROR"

            op = row.operator(
                "ui.amp_toggle_panels_visibility",
                text=f"Potential keymap conflicts {len(filtered_conflicts)}",
                icon=conflict_icon,
            )
            op.version = conflict_id

            # Show number of conflicts in tooltip or as text
            # row.label(text=f"{len(filtered_conflicts)}", icon="ERROR")

            # If expanded, show the conflicts
            if changelog.panels_visibility.get(conflict_id, False):
                from ..register_keymaps import draw_rna_conflict

                for conflict in filtered_conflicts:
                    draw_rna_conflict(
                        conflict_container,
                        context,
                        keymap_name=conflict["keymap_name"],
                        operator_name=conflict["operator_name"],
                    )
    except Exception as e:
        # Fail silently if there are any issues with conflict detection
        print(f"[AMP] Error detecting popup panel conflicts: {e}")
        pass


# -----------------------------------------------------------------------------
# UI Lists
# -----------------------------------------------------------------------------
class AMP_UL_PopupPanels(UIList):
    """Popup panel list with inline rename, hotkey setup, and per-item delete."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        prefs = get_prefs()

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            # Main row for popup panel name
            main_row = layout.split(align=True)

            # Name field (editable)
            main_row.prop(item, "name", text="", emboss=False)

            second_row = main_row.row(align=True)
            popup_panel_hotkey(item, index, second_row)

            # Delete button should only display if it is NOT a default popup panel
            default_popup_id = getattr(item, "default_popup_id", "")
            if default_popup_id == "":
                delete_op = second_row.operator("amp.popup_panel_delete", text="", icon="TRASH")
                delete_op.index = index

        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.name)


def popup_panel_hotkey(item, index, layout):
    # Hotkey capture button with dynamic text
    if item.is_capturing_hotkey:
        hotkey_display = "Press any key..."
        hotkey_icon = "TIME"
    else:
        hotkey_display = item.hotkey_string if item.hotkey_string else "Set Hotkey"
        hotkey_icon = "EVENT_RETURN"

    # Make the button look different when capturing
    hotkey_btn = layout.row(align=True)
    if item.is_capturing_hotkey:
        hotkey_btn.alert = True

    op = hotkey_btn.operator("anim.amp_capture_key_input_popup_panel", text=hotkey_display, icon=hotkey_icon)
    op.popup_panel_index = index

    # Space type selector (compact)
    space_row = hotkey_btn.row(align=True)
    space_row.prop(item, "hotkey_space", text="", icon_only=True)


class AMP_UL_PopupPanelBranches(UIList):
    """Minimal list for Popup Panel categories (branches)."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_args = get_icon(item.icon) if item.icon else {"icon": "RADIOBUT_OFF"}
        row = layout.row(align=True)
        if isinstance(icon_args, dict):
            row.prop(item, "name", text="", **icon_args, emboss=False)
        else:
            row.prop(item, "name", text="", icon=icon_args, emboss=False)


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------
classes = (
    AMP_UL_PopupPanels,
    AMP_UL_PopupPanelBranches,
    AMP_OT_popup_panel_add,
    AMP_OT_popup_panel_delete,
    AMP_OT_popup_panel_move_up,
    AMP_OT_popup_panel_move_down,
    AMP_OT_popup_panel_copy,
    AMP_OT_popup_panel_paste,
    AMP_OT_popup_panel_duplicate,
    AMP_OT_popup_panel_category_add,
    AMP_OT_popup_panel_clear_hotkey,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def draw_popup_preview(context, layout, popup_panel):
    """Draw popup panel preview using the same layout system as side panels

    This ensures that the preview accurately reflects how the actual popup panel
    will appear, respecting the same category placement settings and styling
    options as configured for side panels.
    """
    # Header with popup panel name and hotkey
    header_box = layout.box()
    header_row = header_box.split()

    # Popup panel name
    header_row.label(text=popup_panel.name, **get_icon("AniMateProContact"))

    # Hotkey display
    popup_index = list(get_prefs().popup_panels).index(popup_panel)
    popup_panel_hotkey(popup_panel, popup_index, header_row)

    # potential hotkey conflict warning
    if popup_panel.hotkey_string:
        conflict_row = header_box.row(align=True)
        draw_popup_panel_conflicts(conflict_row, context, popup_panel, popup_index)

    # Width property row below hotkey
    width_row = header_box.row()
    width_row.prop(popup_panel, "popup_width", text="Width")

    # Categories preview - display exactly like the actual popup panels using the same layout system
    content_box = layout.box()

    # Import necessary functions from addon_ui
    from .addon_ui import _setup_layout_for_normal_ui

    # Create a region key for popup panel preview
    region_key = "popup"
    prefs = get_prefs()

    # Get pinned categories from popup panel
    popup_categories = [cat for cat in popup_panel.categories if getattr(cat, "pin_global", False)]

    if not popup_categories:
        content_box.label(text="No categories available", icon="INFO")
        return

    # Ensure popup_active properties exist and are properly set
    for i, cat in enumerate(popup_categories):
        if not hasattr(cat, "popup_active"):
            cat.popup_active = i == 0  # First category active by default
        # Add popup_pin property for compatibility with the layout system
        if not hasattr(cat, "popup_pin"):
            cat.popup_pin = True  # All globally pinned categories in popup are considered pinned for this region

    # Respect category placement like side panels
    pinned = [
        cat for cat in popup_categories if getattr(cat, "pin_global", False) and getattr(cat, f"{region_key}_pin", True)
    ]

    show_category_icons = len(pinned) > 1
    open_cats = [cat for cat in pinned if getattr(cat, "popup_active", False)]

    content_area = None
    if prefs.cat_placement in ("TOP"):
        # Categories at top
        main_col = content_box.column(align=prefs.sections_box_container)

        if show_category_icons:
            # Calculate how many categories can fit per row based on region width
            try:
                region_width = context.region.width / max(0.001, context.preferences.view.ui_scale)
            except Exception:
                region_width = getattr(popup_panel, "popup_width", 400)
            scaled_button_width = 28 * getattr(prefs, "cat_scale", 1.0)
            categories_per_row = max(1, int(region_width // max(1, int(scaled_button_width))))

            cat_outer = main_col.box() if getattr(prefs, "cat_box_container", False) else main_col

            for i in range(0, len(pinned), categories_per_row):
                cat_pre_row = cat_outer.row()
                cat_pre_row.alignment = "CENTER"
                cat_row = cat_pre_row.row()
                cat_row.scale_x = getattr(prefs, "cat_scale", 1.0)
                cat_row.scale_y = getattr(prefs, "cat_scale", 1.0)

                row_categories = pinned[i : i + categories_per_row]
                for cat in row_categories:
                    icon_args = get_icon(cat.icon) if getattr(cat, "icon", None) else {"icon": "RADIOBUT_OFF"}
                    if isinstance(icon_args, dict):
                        cat_row.prop(cat, "popup_active", text="", **icon_args, emboss=True)
                    else:
                        cat_row.prop(cat, "popup_active", text="", icon=icon_args, emboss=True)

        if getattr(prefs, "sections_box_container", False) and open_cats:
            content_area = main_col.box().column()
        else:
            content_area = main_col.column()

    else:
        # LEFT or RIGHT placement
        row = content_box.row(align=getattr(prefs, "sections_box_container", False))

        if show_category_icons:
            if prefs.cat_placement == "LEFT":
                if getattr(prefs, "cat_box_container", False):
                    cat_outer = row.box()
                    col_pins = cat_outer.column()
                else:
                    col_pins = row.column()

                col_pins.scale_x = getattr(prefs, "cat_scale", 1.0)
                col_pins.scale_y = getattr(prefs, "cat_scale", 1.0)

                for cat in pinned:
                    icon_args = get_icon(cat.icon) if getattr(cat, "icon", None) else {"icon": "RADIOBUT_OFF"}
                    if isinstance(icon_args, dict):
                        col_pins.prop(cat, "popup_active", text="", **icon_args, emboss=True)
                    else:
                        col_pins.prop(cat, "popup_active", text="", icon=icon_args, emboss=True)

                if getattr(prefs, "sections_box_container", False) and open_cats:
                    category_box = row.box()
                    content_area = category_box.column()
                else:
                    content_area = row.column()

            else:  # RIGHT
                if getattr(prefs, "sections_box_container", False) and open_cats:
                    category_box = row.box()
                    content_area = category_box.column()
                else:
                    content_area = row.column()

                if getattr(prefs, "cat_box_container", False):
                    cat_outer = row.box()
                    col_pins = cat_outer.column()
                else:
                    col_pins = row.column()

                col_pins.scale_x = getattr(prefs, "cat_scale", 1.0)
                col_pins.scale_y = getattr(prefs, "cat_scale", 1.0)

                for cat in pinned:
                    icon_args = get_icon(cat.icon) if getattr(cat, "icon", None) else {"icon": "RADIOBUT_OFF"}
                    if isinstance(icon_args, dict):
                        col_pins.prop(cat, "popup_active", text="", **icon_args, emboss=True)
                    else:
                        col_pins.prop(cat, "popup_active", text="", icon=icon_args, emboss=True)
        else:
            if getattr(prefs, "sections_box_container", False) and open_cats:
                category_box = row.box()
                content_area = category_box.column()
            else:
                content_area = row.column()

    if content_area is None:
        content_area = content_box.column()

    # Get the separator value for inter-category spacing
    inter_category_separator = 1.0
    for cat in pinned:
        if hasattr(cat, "section_separator"):
            inter_category_separator = cat.section_separator
            break

    # Draw active categories into the content area
    first_visible_category = True
    for cat in pinned:
        if not getattr(cat, "popup_active", False):
            continue
        if not first_visible_category:
            content_area.separator(factor=inter_category_separator)
        first_visible_category = False
        _draw_rows_for_category(context, cat, content_area, region_key, prefs, top_panel=False)
