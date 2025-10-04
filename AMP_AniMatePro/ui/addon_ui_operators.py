import bpy
import json
import os
import random
import ast
import inspect
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
from . import addon_ui_definitions_button


def poll_contextual_operation(
    context, operator_class, require_section_or_panel=False, require_clipboard_data=None, clipboard_data_type=None
):
    """
    Centralized poll helper for UI operators that need contextual access.

    Args:
        context: Blender context
        operator_class: The operator class to get properties from
        require_section_or_panel: If True, current row must be a section or panel
        require_clipboard_data: If True, checks for valid clipboard data
        clipboard_data_type: Type of clipboard data required (e.g., "section_block", "button_entry")

    Returns:
        bool: True if operation should be enabled
    """
    try:
        # Get all available contexts - both main UI and popup panels
        prefs = get_prefs()
        if not prefs:
            return False

        contexts_to_check = []

        # Add main UI context
        contexts_to_check.append(
            {"owner": prefs, "cat_coll": prefs.ui_categories, "active_idx_prop": "active_category_index"}
        )

        # Add popup panel contexts
        for popup_panel in prefs.popup_panels:
            contexts_to_check.append(
                {"owner": popup_panel, "cat_coll": popup_panel.categories, "active_idx_prop": "active_category_index"}
            )

        # Check each context to see if any has a valid section/panel selection
        for ctx_info in contexts_to_check:
            owner = ctx_info["owner"]
            cat_coll = ctx_info["cat_coll"]
            active_idx_prop = ctx_info["active_idx_prop"]

            if not owner or not cat_coll:
                continue

            active_cat_idx = getattr(owner, active_idx_prop, -1)
            if not (0 <= active_cat_idx < len(cat_coll)):
                continue

            category = cat_coll[active_cat_idx]
            if not category:
                continue

            # Check if we need rows for section/panel operations
            if require_section_or_panel:
                if not category.rows:
                    continue

                if 0 <= category.active_row_index < len(category.rows):
                    current_row = category.rows[category.active_row_index]
                    if current_row.row_type in ("SECTION", "PANEL"):
                        # Found a valid section/panel in this context
                        break
                else:
                    continue
            else:
                # No specific section/panel requirement, any valid context is fine
                break
        else:
            # No valid context found
            if require_section_or_panel:
                return False

        # Check clipboard data if required
        if require_clipboard_data:
            clip = context.window_manager.clipboard
            if not clip:
                return False

            # Try to parse as JSON first
            try:
                data = __import__("json").loads(clip)
            except:
                try:
                    data = __import__("ast").literal_eval(clip)
                except:
                    return False

            # Check clipboard data type if specified
            if clipboard_data_type:
                if not isinstance(data, dict):
                    return False

                if clipboard_data_type == "section_block":
                    if (
                        data.get("type") != "section_block"
                        or not isinstance(data.get("content"), list)
                        or len(data.get("content", [])) == 0
                    ):
                        return False

                elif clipboard_data_type == "button_entry":
                    if (
                        data.get("type") != "button_entry"
                        or not isinstance(data.get("content"), dict)
                        or not data.get("content", {}).get("button_id")
                    ):
                        return False

        return True

    except Exception:
        return False


class AMP_OT_category_add(Operator):
    """Add a new UI category at the current position.

    Creates a new category with default settings and adds it after the
    currently active category. For pie menus, enforces the 8-category limit.
    """

    bl_idname = "amp.category_add"
    bl_label = "Add Category"
    bl_description = "Add a new UI category at the current position"

    data_owner_is_popup_panel: BoolProperty(
        name="Owner is Popup Panel", description="Indicates if the category owner is a Popup Panel", default=False
    )
    data_owner_popup_panel_index: IntProperty(
        name="Popup Panel Index",
        description="Index of the Popup Panel in prefs.popup_panels if owner is a Popup Panel",
        default=-1,
    )

    def execute(self, context):
        owner, coll, active_idx_prop_name = get_contextual_owner_collection_indices(context, self)

        if owner is None or coll is None:
            self.report({"ERROR"}, "Could not determine category owner or collection.")
            return {"CANCELLED"}

        if self.data_owner_is_popup_panel and len(coll) >= 8:
            self.report({"WARNING"}, "Popup panels support a maximum of 8 categories.")
            return {"CANCELLED"}

        current_active_idx = getattr(owner, active_idx_prop_name)
        insert_at_idx = current_active_idx + 1

        new_cat = coll.add()
        new_cat.name = "Category"
        new_cat.icon = f"AMP_COLORS_{random.randint(1,9):02d}"

        if self.data_owner_is_popup_panel:
            if hasattr(new_cat, "style"):
                new_cat.style = "BOX_TITLE"
            if hasattr(new_cat, "show"):
                new_cat.show = "ALWAYS"
            new_cat.properties = False

        coll.move(len(coll) - 1, insert_at_idx)
        setattr(owner, active_idx_prop_name, insert_at_idx)

        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_category_move_up(Operator):
    """Move the selected category one position up in the list.

    Swaps the currently selected category with the one above it,
    if not already at the top of the list.
    """

    bl_idname = "amp.category_move_up"
    bl_label = "Move Category Up"
    bl_description = "Move the selected category one position up"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        owner, coll, active_idx_prop = get_contextual_owner_collection_indices(context, self)
        if not owner or not coll:
            self.report({"WARNING"}, "Contextual owner or collection not found.")
            return {"CANCELLED"}

        idx = getattr(owner, active_idx_prop)
        if idx > 0:
            coll.move(idx, idx - 1)
            setattr(owner, active_idx_prop, idx - 1)
            refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_category_move_down(Operator):
    """Move the selected category one position down in the list.

    Swaps the currently selected category with the one below it,
    if not already at the bottom of the list.
    """

    bl_idname = "amp.category_move_down"
    bl_label = "Move Category Down"
    bl_description = "Move the selected category one position down"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        owner, coll, active_idx_prop = get_contextual_owner_collection_indices(context, self)
        if not owner or not coll:
            self.report({"WARNING"}, "Contextual owner or collection not found.")
            return {"CANCELLED"}

        idx = getattr(owner, active_idx_prop)
        if idx < len(coll) - 1:
            coll.move(idx, idx + 1)
            setattr(owner, active_idx_prop, idx + 1)
            refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_category_copy(Operator):
    """Copy the selected category to clipboard as JSON.

    Copies the currently selected category including all its rows
    and buttons to the system clipboard in JSON format.
    """

    bl_idname = "amp.category_copy"
    bl_label = "Copy Category"
    bl_description = "Copy the selected category to clipboard as JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        cat_to_copy = get_contextual_category(context, self)
        if not cat_to_copy:
            self.report({"WARNING"}, "No category selected to copy.")
            return {"CANCELLED"}

        data = ptr_to_dict(cat_to_copy)
        rows = []
        for row_item in cat_to_copy.rows:
            rd = ptr_to_dict(row_item)
            rd["buttons"] = [ptr_to_dict(btn) for btn in row_item.buttons]
            rows.append(rd)
        data["rows"] = rows

        context.window_manager.clipboard = json.dumps(data)
        self.report({"INFO"}, "Category JSON (with rows & buttons) copied")
        return {"FINISHED"}


class AMP_OT_category_paste(Operator):
    """Paste a category from clipboard JSON.

    Creates a new category from JSON data in the clipboard and converts
    it to a custom category with global pinning enabled.
    """

    bl_idname = "amp.category_paste"
    bl_label = "Paste Category"
    bl_description = "Paste a category from clipboard JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        owner, coll, active_idx_prop = get_contextual_owner_collection_indices(context, self)
        if not owner or coll is None:
            self.report({"WARNING"}, "Contextual owner or collection not found.")
            return {"CANCELLED"}

        clip = context.window_manager.clipboard
        try:
            data = json.loads(clip)
        except Exception:
            try:
                data = ast.literal_eval(clip)
            except Exception:
                self.report({"WARNING"}, "Clipboard does not contain valid JSON or Python literal")
                return {"CANCELLED"}

        current_active_idx = getattr(owner, active_idx_prop, -1)
        insert_at_idx = current_active_idx + 1

        new_cat = coll.add()
        dict_to_ptr(new_cat, data)

        new_cat.default_cat_id = ""
        new_cat.pin_global = True

        if self.data_owner_is_popup_panel:
            if hasattr(new_cat, "style") and "style" not in data:
                new_cat.style = "DEFAULT"
            if hasattr(new_cat, "show") and "show" not in data:
                new_cat.show = "NEVER"
            if hasattr(new_cat, "properties"):
                new_cat.properties = data.get("properties", False)

        coll.move(len(coll) - 1, insert_at_idx)
        setattr(owner, active_idx_prop, insert_at_idx)
        refresh_ui(context)
        self.report({"INFO"}, "Category pasted with all rows & buttons")
        return {"FINISHED"}


class AMP_OT_category_duplicate(Operator):
    """Duplicate the selected category.

    Creates an exact copy of the currently selected category and places it
    after the original. The duplicated category becomes a custom category.
    """

    bl_idname = "amp.category_duplicate"
    bl_label = "Duplicate Category"
    bl_description = "Duplicate the selected category"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        owner, coll, active_idx_prop = get_contextual_owner_collection_indices(context, self)
        cat_to_duplicate = get_contextual_category(context, self)

        if not owner or not coll or not cat_to_duplicate:
            self.report({"WARNING"}, "Contextual data or category to duplicate not found.")
            return {"CANCELLED"}

        data = ptr_to_dict(cat_to_duplicate)
        data["rows"] = [
            {**ptr_to_dict(row), "buttons": [ptr_to_dict(btn) for btn in row.buttons]} for row in cat_to_duplicate.rows
        ]

        current_active_idx = getattr(owner, active_idx_prop)
        insert_at_idx = current_active_idx + 1
        # set pin global to false to the old category
        cat_to_duplicate.pin_global = False

        new_cat = coll.add()
        dict_to_ptr(new_cat, data)
        new_cat.name += " Copy"

        new_cat.default_cat_id = ""
        new_cat.pin_global = True

        coll.move(len(coll) - 1, insert_at_idx)
        setattr(owner, active_idx_prop, insert_at_idx)
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_category_restore_default(Operator):
    """Restore all default categories to their original state.

    Removes all existing default categories and reloads them from
    the stored default category definitions folder.
    """

    bl_idname = "amp.restore_default_ui_categories"
    bl_label = "Restore All Default Categories"
    bl_description = "Remove all default categories and reload them from definitions"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    skip_confirmation: BoolProperty(
        name="Skip Confirmation", description="Skip the confirmation dialog", default=False, options={"SKIP_SAVE"}
    )

    def invoke(self, context, event):
        """Show confirmation dialog before restoring defaults (unless skipped)"""
        if self.skip_confirmation:
            return self.execute(context)
        return context.window_manager.invoke_confirm(self, event)

    def draw(self, context):
        """Draw confirmation dialog"""
        layout = self.layout
        layout.label(text="Restore all default categories and pie menus?")
        layout.label(text="This will remove all existing default categories", icon="INFO")
        layout.label(text="and pie menus, then reload them from the addon definitions.")
        layout.separator()
        layout.label(text="Custom categories and pie menus will not be affected.", icon="CHECKMARK")

    def execute(self, context):
        owner, coll, active_idx_prop = get_contextual_owner_collection_indices(context, self)

        # Fallback for startup scenarios where contextual access might fail
        if not owner or not coll:
            print("[AMP_AniMatePro] Contextual access failed, using direct preferences access")
            prefs = get_prefs()
            if not prefs:
                error_msg = "Cannot access addon preferences."
                if not self.skip_confirmation:
                    self.report({"ERROR"}, error_msg)
                else:
                    print(f"[AMP_AniMatePro] ERROR: {error_msg}")
                return {"CANCELLED"}

            # Use main UI categories as fallback
            owner = prefs
            coll = prefs.ui_categories
            active_idx_prop = "active_category_index"

        try:
            # Store previous pin_global flags for default categories
            old_pins = {cat.default_cat_id: cat.pin_global for cat in coll if cat.default_cat_id}

            # Count default categories before removal
            default_categories = [cat for cat in coll if cat.default_cat_id]
            default_count = len(default_categories)

            # Remove all existing default categories in reverse order to maintain indices
            categories_to_remove = [i for i, cat in enumerate(coll) if cat.default_cat_id]
            for i in reversed(categories_to_remove):
                coll.remove(i)

            # Adjust active index if needed
            current_active = getattr(owner, active_idx_prop)
            if current_active >= len(coll):
                setattr(owner, active_idx_prop, max(0, len(coll) - 1))  # Reload default categories from definitions
            from ..ui.addon_ui import _ensure_default_categories_loaded

            _ensure_default_categories_loaded(force_fresh_install=True)

            # Reapply previous pin_global flags where possible
            for cat in coll:
                if hasattr(cat, "default_cat_id") and cat.default_cat_id in old_pins:
                    cat.pin_global = old_pins[cat.default_cat_id]

            # Count new default categories
            new_default_categories = [cat for cat in coll if cat.default_cat_id]
            new_count = len(new_default_categories)

            refresh_ui(context)

            if not self.skip_confirmation:
                self.report(
                    {"INFO"}, f"Restored {new_count} default categories (removed {default_count} existing defaults)"
                )
            else:
                print(
                    f"[AMP_AniMatePro] Restored {new_count} default categories (removed {default_count} existing defaults)"
                )

            return {"FINISHED"}

        except Exception as e:
            error_msg = f"Failed to restore default categories: {str(e)}"
            if not self.skip_confirmation:
                self.report({"ERROR"}, error_msg)
            else:
                print(f"[AMP_AniMatePro] ERROR: {error_msg}")
            return {"CANCELLED"}


# -----------------------------------------------------------------------------
# Operators: Select Category
# -----------------------------------------------------------------------------
class AMP_OT_category_select(Operator):
    """Select a category by index.

    Sets the active category index for the current context.
    Usually called from UIList interactions.
    """

    bl_idname = "amp.category_select"
    bl_label = "Select Category"
    bl_description = "Select a category by index"

    index: IntProperty(name="Index", description="Index of the category to select")

    def execute(self, context):
        prefs = get_prefs()
        prefs.active_category_index = self.index
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Operators: Row management
# -----------------------------------------------------------------------------
class AMP_OT_row_add_section(Operator):
    """Add a section row to the current category.

    Creates a new section row with default styling and adds it
    after the currently active row.
    """

    bl_idname = "amp.row_add_section"
    bl_label = "Add Section Row"
    bl_description = "Add a section row to the current category"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        category = get_contextual_category(context, self)
        if not category:
            owner_for_cat_add, coll_for_cat_add, _ = get_contextual_owner_collection_indices(context, self)
            if owner_for_cat_add and not coll_for_cat_add:
                bpy.ops.amp.category_add(
                    "EXEC_DEFAULT",
                    data_owner_is_popup_panel=self.data_owner_is_popup_panel,
                    data_owner_popup_panel_index=self.data_owner_popup_panel_index,
                )
                category = get_contextual_category(context, self)

            if not category:
                self.report({"WARNING"}, "No category to add row to.")
                return {"CANCELLED"}

        idx = category.active_row_index + 1
        row = category.rows.add()
        row.row_type = "SECTION"
        row.name = "Section"
        row.style = "BOX"
        category.rows.move(len(category.rows) - 1, idx)
        category.active_row_index = idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_add_button(Operator):
    """Add a button row to the current category.

    Creates a new button row and adds it after the currently active row.
    """

    bl_idname = "amp.row_add_button"
    bl_label = "Add Button Row"
    bl_description = "Add a button row to the current category"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        category = get_contextual_category(context, self)
        if not category:
            owner_for_cat_add, coll_for_cat_add, _ = get_contextual_owner_collection_indices(context, self)
            if owner_for_cat_add and not coll_for_cat_add:
                bpy.ops.amp.category_add(
                    "EXEC_DEFAULT",
                    data_owner_is_popup_panel=self.data_owner_is_popup_panel,
                    data_owner_popup_panel_index=self.data_owner_popup_panel_index,
                )
                category = get_contextual_category(context, self)
            if not category:
                self.report({"WARNING"}, "No category to add row to.")
                return {"CANCELLED"}

        idx = category.active_row_index + 1
        row = category.rows.add()
        row.row_type = "BUTTON"
        # row.name = "Button Row" # Button rows usually don't have names, sections do
        category.rows.move(len(category.rows) - 1, idx)
        category.active_row_index = idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_add_panel(Operator):
    """Add a panel row to the current category.

    Creates a new panel row and adds it after the currently active row.
    """

    bl_idname = "amp.row_add_panel"
    bl_label = "Add Panel Row"
    bl_description = "Add a panel row to the current category"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        category = get_contextual_category(context, self)
        if not category:
            owner_for_cat_add, coll_for_cat_add, _ = get_contextual_owner_collection_indices(context, self)
            if owner_for_cat_add and not coll_for_cat_add:
                bpy.ops.amp.category_add(
                    "EXEC_DEFAULT",
                    data_owner_is_popup_panel=self.data_owner_is_popup_panel,
                    data_owner_popup_panel_index=self.data_owner_popup_panel_index,
                )
                category = get_contextual_category(context, self)
            if not category:
                self.report({"WARNING"}, "No category to add row to.")
                return {"CANCELLED"}

        idx = category.active_row_index + 1
        row = category.rows.add()
        row.row_type = "PANEL"
        row.name = "Panel"
        category.rows.move(len(category.rows) - 1, idx)
        category.active_row_index = idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_move_up(Operator):
    """Move the selected row one position up.

    Swaps the currently selected row with the one above it,
    if not already at the top.
    """

    bl_idname = "amp.row_move_up"
    bl_label = "Move Row Up"
    bl_description = "Move the selected row one position up"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # category = get_contextual_category(context, self, category_idx_prop_name="category_index")
        category = get_contextual_category(context, self)
        if not category:
            return {"CANCELLED"}

        idx = category.active_row_index
        if idx > 0:
            category.rows.move(idx, idx - 1)
            category.active_row_index = idx - 1
            refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_move_down(Operator):
    """Move the selected row one position down.

    Swaps the currently selected row with the one below it,
    if not already at the bottom.
    """

    bl_idname = "amp.row_move_down"
    bl_label = "Move Row Down"
    bl_description = "Move the selected row one position down"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # category = get_contextual_category(context, self, category_idx_prop_name="category_index")
        category = get_contextual_category(context, self)
        if not category:
            return {"CANCELLED"}

        idx = category.active_row_index
        if idx < len(category.rows) - 1:
            category.rows.move(idx, idx + 1)
            category.active_row_index = idx + 1
            refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_copy(Operator):
    """Copy the selected row to clipboard as JSON.

    Copies the currently selected row including all its buttons
    to the system clipboard in JSON format.
    """

    bl_idname = "amp.row_copy"
    bl_label = "Copy Row"
    bl_description = "Copy the selected row to clipboard as JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # row_to_copy = get_contextual_row(context, self, row_idx_prop_name="row_index")
        # If row_index is not on op, get_contextual_row uses active_row_index from category
        row_to_copy = get_contextual_row(context, self)
        if not row_to_copy:
            self.report({"WARNING"}, "No row selected to copy.")
            return {"CANCELLED"}

        data = ptr_to_dict(row_to_copy)
        data["buttons"] = [ptr_to_dict(btn) for btn in row_to_copy.buttons]
        context.window_manager.clipboard = json.dumps(data)
        self.report({"INFO"}, "Row JSON (with buttons) copied")
        return {"FINISHED"}


class AMP_OT_row_paste(Operator):
    """Paste a row from clipboard JSON.

    Creates a new row from JSON data in the clipboard and adds it
    after the currently active row.
    """

    bl_idname = "amp.row_paste"
    bl_label = "Paste Row"
    bl_description = "Paste a row from clipboard JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # category = get_contextual_category(context, self, category_idx_prop_name="category_index")
        category = get_contextual_category(context, self)
        if not category:
            self.report({"WARNING"}, "No category to paste row into.")
            return {"CANCELLED"}

        clip = context.window_manager.clipboard
        try:
            data = json.loads(clip)
        except Exception:
            try:
                data = ast.literal_eval(clip)
            except Exception:
                self.report({"WARNING"}, "Clipboard does not contain valid JSON or Python literal")
                return {"CANCELLED"}

        insert_row_idx = category.active_row_index + 1
        new_row = category.rows.add()
        dict_to_ptr(new_row, data)  # Needs to handle new_row.buttons correctly

        category.rows.move(len(category.rows) - 1, insert_row_idx)
        category.active_row_index = insert_row_idx
        refresh_ui(context)
        self.report({"INFO"}, "Row pasted with all buttons")
        return {"FINISHED"}


class AMP_OT_row_duplicate(Operator):
    """Duplicate the selected row.

    Creates an exact copy of the currently selected row and places it
    after the original. For sections, duplicates all section content.
    """

    bl_idname = "amp.row_duplicate"
    bl_label = "Duplicate Row"
    bl_description = "Duplicate the selected row"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        category = get_contextual_category(context, self)
        row_to_duplicate = get_contextual_row(context, self)
        if not category or not row_to_duplicate:
            self.report({"WARNING"}, "Contextual data or row to duplicate not found.")
            return {"CANCELLED"}

        # If duplicating a section or panel, use smart duplication
        if row_to_duplicate.row_type in ("SECTION", "PANEL"):
            return self._duplicate_section_with_content(context, category, row_to_duplicate)

        # Regular row duplication for button rows
        data = ptr_to_dict(row_to_duplicate)
        data["buttons"] = [ptr_to_dict(btn) for btn in row_to_duplicate.buttons]

        insert_row_idx = category.active_row_index + 1
        new_row = category.rows.add()
        dict_to_ptr(new_row, data)
        new_row.row_type = row_to_duplicate.row_type
        if new_row.row_type in ("SECTION", "PANEL"):
            new_row.name += " Copy"

        category.rows.move(len(category.rows) - 1, insert_row_idx)
        category.active_row_index = insert_row_idx
        refresh_ui(context)
        return {"FINISHED"}

    def _duplicate_section_with_content(self, context, category, section_row):
        """Duplicate a section/panel and all its content (subsections, panels, and button rows)"""
        section_idx = category.active_row_index

        # Collect all rows that belong to this section
        section_content = []

        # Add the section itself
        section_data = ptr_to_dict(section_row)
        section_data["buttons"] = [ptr_to_dict(btn) for btn in section_row.buttons]
        section_content.append(section_data)

        # Find all content belonging to this section
        current_idx = section_idx + 1
        while current_idx < len(category.rows):
            row = category.rows[current_idx]

            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break

            # Include subsections and all content until next main section or panel
            row_data = ptr_to_dict(row)
            row_data["buttons"] = [ptr_to_dict(btn) for btn in row.buttons]
            section_content.append(row_data)
            current_idx += 1

        # Insert all collected content after the original section
        insert_idx = section_idx + (current_idx - section_idx)  # After all original content

        for i, content_data in enumerate(section_content):
            new_row = category.rows.add()
            dict_to_ptr(new_row, content_data)

            # Add "Copy" to the main section name
            if i == 0:  # First item is the main section or panel
                new_row.name += " Copy"

            # Move to correct position
            category.rows.move(len(category.rows) - 1, insert_idx + i)
        # Set active to the duplicated section
        category.active_row_index = insert_idx
        refresh_ui(context)

        section_count = len(section_content)
        self.report({"INFO"}, f"Duplicated {section_row.row_type.lower()} with {section_count - 1} content items")
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Smart Section Operators
# -----------------------------------------------------------------------------
class AMP_OT_section_move_up(Operator):
    """Move the selected section/panel and all its content one position up.

    Moves a section or panel along with all its subsections, panels, and button rows
    as a complete unit.
    """

    bl_idname = "amp.section_move_up"
    bl_label = "Move Section/Panel Up"
    bl_description = "Move the selected section/panel and its content one position up"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        """Only enable if current row is a section or panel"""
        return poll_contextual_operation(context, cls, require_section_or_panel=True)

    def execute(self, context):
        category = get_contextual_category(context, self)
        current_row = get_contextual_row(context, self)

        if not category or not current_row:
            self.report({"WARNING"}, "No section or panel selected.")
            return {"CANCELLED"}

        if current_row.row_type not in ("SECTION", "PANEL"):
            self.report({"WARNING"}, "Selected row is not a section or panel.")
            return {"CANCELLED"}

        section_idx = category.active_row_index

        # Find the start of the current section and all its content
        section_content_indices = self._get_section_content_indices(category, section_idx)

        if section_idx == 0:
            self.report({"INFO"}, f"{current_row.row_type.title()} is already at the top.")
            return {"FINISHED"}

        # Find where to move the section (after the previous section/row)
        move_to_idx = self._find_move_target_up(category, section_idx)

        if move_to_idx >= section_idx:
            self.report({"INFO"}, f"Cannot move {current_row.row_type.lower()} up.")
            return {"FINISHED"}

        # Move all section content as a block
        self._move_section_block(category, section_content_indices, move_to_idx)

        # Update active index to the new position of the section
        category.active_row_index = move_to_idx
        refresh_ui(context)
        return {"FINISHED"}

    def _get_section_content_indices(self, category, section_idx):
        """Get all indices that belong to this section"""
        indices = [section_idx]

        # Find all content after the section until next main section
        current_idx = section_idx + 1
        while current_idx < len(category.rows):
            row = category.rows[current_idx]

            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break

            indices.append(current_idx)
            current_idx += 1

        return indices

    def _find_move_target_up(self, category, section_idx):
        """Find where to move the section when moving up"""
        # Look backwards to find the previous main section or panel
        previous_section_start = None
        current_idx = section_idx - 1

        # Find the start of the previous section/panel
        while current_idx >= 0:
            row = category.rows[current_idx]
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                previous_section_start = current_idx
                break
            current_idx -= 1

        # If no previous section found, move to the beginning
        if previous_section_start is None:
            return 0

        # Find if there's a section before the previous section
        before_previous_section_end = None
        current_idx = previous_section_start - 1

        while current_idx >= 0:
            row = category.rows[current_idx]
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                # Found a section before the previous section
                # Need to find where this section's content ends
                before_previous_section_end = self._find_section_end(category, current_idx) + 1
                break
            current_idx -= 1

        # If there's a section before the previous section, move after its content
        if before_previous_section_end is not None:
            return before_previous_section_end

        # Otherwise, move to the beginning
        return 0

    def _find_section_end(self, category, section_start_idx):
        """Find the last index of content belonging to the section starting at section_start_idx"""
        current_idx = section_start_idx + 1

        while current_idx < len(category.rows):
            row = category.rows[current_idx]
            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break
            current_idx += 1

        # Return the last index that belongs to this section
        return current_idx - 1

    def _move_section_block(self, category, indices, target_idx):
        """Move a block of rows to a new position"""
        # Store the rows data
        rows_data = []
        for idx in indices:
            row_data = ptr_to_dict(category.rows[idx])
            row_data["buttons"] = [ptr_to_dict(btn) for btn in category.rows[idx].buttons]
            rows_data.append(row_data)

        # Remove rows in reverse order
        for idx in reversed(indices):
            category.rows.remove(idx)

        # Add rows at new position
        for i, row_data in enumerate(rows_data):
            new_row = category.rows.add()
            dict_to_ptr(new_row, row_data)
            category.rows.move(len(category.rows) - 1, target_idx + i)


class AMP_OT_section_move_down(Operator):
    """Move the selected section/panel and all its content one position down.

    Moves a section or panel along with all its subsections, panels, and button rows
    as a complete unit.
    """

    bl_idname = "amp.section_move_down"
    bl_label = "Move Section/Panel Down"
    bl_description = "Move the selected section/panel and its content one position down"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        """Only enable if current row is a section or panel"""
        return poll_contextual_operation(context, cls, require_section_or_panel=True)

    def execute(self, context):
        category = get_contextual_category(context, self)
        current_row = get_contextual_row(context, self)

        if not category or not current_row:
            self.report({"WARNING"}, "No section or panel selected.")
            return {"CANCELLED"}

        if current_row.row_type not in ("SECTION", "PANEL"):
            self.report({"WARNING"}, "Selected row is not a section or panel.")
            return {"CANCELLED"}

        section_idx = category.active_row_index

        # Find the start of the current section and all its content
        section_content_indices = self._get_section_content_indices(
            category, section_idx
        )  # Check if this is the last section
        last_content_idx = section_content_indices[-1]
        if last_content_idx >= len(category.rows) - 1:
            self.report({"INFO"}, f"{current_row.row_type.title()} is already at the bottom.")
            return {"FINISHED"}

        # Find where to move the section (after the next section)
        move_to_idx = self._find_move_target_down(category, last_content_idx)

        # Move all section content as a block
        self._move_section_block(category, section_content_indices, move_to_idx)

        # Update active index to the new position of the section
        # Adjust for the fact that we removed items before inserting
        new_section_position = move_to_idx
        if move_to_idx > section_content_indices[-1]:
            new_section_position = move_to_idx - len(section_content_indices)

        category.active_row_index = new_section_position
        refresh_ui(context)
        return {"FINISHED"}

    def _get_section_content_indices(self, category, section_idx):
        """Get all indices that belong to this section"""
        indices = [section_idx]

        # Find all content after the section until next main section
        current_idx = section_idx + 1
        while current_idx < len(category.rows):
            row = category.rows[current_idx]

            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break

            indices.append(current_idx)
            current_idx += 1

        return indices

    def _find_move_target_down(self, category, last_content_idx):
        """Find where to move the section when moving down"""
        # Look forward to find the end of the next section
        current_idx = last_content_idx + 1

        if current_idx >= len(category.rows):
            return current_idx

        # Skip the next section and its content
        row = category.rows[current_idx]
        if (row.row_type == "SECTION" and not row.is_subsection) or (row.row_type == "PANEL" and not row.is_subsection):
            # This is a main section or panel, find its end
            current_idx += 1
            while current_idx < len(category.rows):
                row = category.rows[current_idx]
                if (row.row_type == "SECTION" and not row.is_subsection) or (
                    row.row_type == "PANEL" and not row.is_subsection
                ):
                    break
                current_idx += 1

        return current_idx

    def _find_section_end(self, category, section_start_idx):
        """Find the last index of content belonging to the section starting at section_start_idx"""
        current_idx = section_start_idx + 1

        while current_idx < len(category.rows):
            row = category.rows[current_idx]
            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break
            current_idx += 1

        # Return the last index that belongs to this section
        return current_idx - 1

    def _move_section_block(self, category, indices, target_idx):
        """Move a block of rows to a new position"""
        # Store the rows data
        rows_data = []
        for idx in indices:
            row_data = ptr_to_dict(category.rows[idx])
            row_data["buttons"] = [ptr_to_dict(btn) for btn in category.rows[idx].buttons]
            rows_data.append(row_data)

        # Adjust target index if it's after the removed content
        if target_idx > indices[-1]:
            target_idx -= len(indices)

        # Remove rows in reverse order
        for idx in reversed(indices):
            category.rows.remove(idx)

        # Add rows at new position
        for i, row_data in enumerate(rows_data):
            new_row = category.rows.add()
            dict_to_ptr(new_row, row_data)
            category.rows.move(len(category.rows) - 1, target_idx + i)


class AMP_OT_section_copy(Operator):
    """Copy the selected section/panel and all its content to clipboard as JSON.

    Copies the section or panel along with all its subsections and button rows
    to the system clipboard in JSON format.
    """

    bl_idname = "amp.section_copy"
    bl_label = "Copy Section/Panel"
    bl_description = "Copy the selected section/panel and its content to clipboard as JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        """Only enable if current row is a section or panel"""
        return poll_contextual_operation(context, cls, require_section_or_panel=True)

    def execute(self, context):
        category = get_contextual_category(context, self)
        current_row = get_contextual_row(context, self)

        if not category or not current_row:
            self.report({"WARNING"}, "No section or panel selected.")
            return {"CANCELLED"}

        if current_row.row_type not in ("SECTION", "PANEL"):
            self.report({"WARNING"}, "Selected row is not a section or panel.")
            return {"CANCELLED"}

        section_idx = category.active_row_index

        # Collect section and all its content
        section_content = []

        # Add the section itself
        section_data = ptr_to_dict(current_row)
        section_data["buttons"] = [ptr_to_dict(btn) for btn in current_row.buttons]
        section_content.append(section_data)

        # Find all content belonging to this section
        current_idx = section_idx + 1
        while current_idx < len(category.rows):
            row = category.rows[current_idx]

            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break

            row_data = ptr_to_dict(row)
            row_data["buttons"] = [ptr_to_dict(btn) for btn in row.buttons]
            section_content.append(row_data)
            current_idx += 1

        # Wrap in a container to identify it as a section block
        data = {"type": "section_block", "content": section_content}

        context.window_manager.clipboard = json.dumps(data)
        content_count = len(section_content) - 1  # Subtract 1 for the section itself
        self.report({"INFO"}, f"{current_row.row_type.title()} with {content_count} content items copied")
        return {"FINISHED"}


class AMP_OT_section_paste(Operator):
    """Paste a section and its content from clipboard JSON.

    Creates a new section from JSON data in the clipboard and adds it
    after the currently active row.
    """

    bl_idname = "amp.section_paste"
    bl_label = "Paste Section/Panel"
    bl_description = "Paste a section/panel and its content from clipboard JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        """Only enable if clipboard contains valid section data and we have valid context"""
        return poll_contextual_operation(context, cls, require_clipboard_data=True, clipboard_data_type="section_block")

    def execute(self, context):
        category = get_contextual_category(context, self)
        if not category:
            self.report({"WARNING"}, "No category to paste section into.")
            return {"CANCELLED"}

        clip = context.window_manager.clipboard
        try:
            data = json.loads(clip)
        except Exception:
            try:
                data = ast.literal_eval(clip)
            except Exception:
                self.report({"WARNING"}, "Clipboard does not contain valid JSON or Python literal")
                return {"CANCELLED"}  # Check if this is a section block
        if not isinstance(data, dict) or data.get("type") != "section_block":
            self.report({"WARNING"}, "Clipboard does not contain section data")
            return {"CANCELLED"}

        section_content = data.get("content", [])
        if not section_content:
            self.report({"WARNING"}, "No section content found in clipboard")
            return {"CANCELLED"}

        insert_row_idx = category.active_row_index  # Paste above current selection

        # Add all section content
        for i, content_data in enumerate(section_content):
            new_row = category.rows.add()
            dict_to_ptr(new_row, content_data)

            # Add "Copy" to the main section name
            if i == 0 and new_row.row_type in ("SECTION", "PANEL"):
                new_row.name += " Copy"

            category.rows.move(len(category.rows) - 1, insert_row_idx + i)  # Set active to the pasted section
        category.active_row_index = insert_row_idx
        refresh_ui(context)
        content_count = len(section_content) - 1
        self.report({"INFO"}, f"Section with {content_count} content items pasted")
        return {"FINISHED"}


class AMP_OT_section_delete(Operator):
    """Delete the selected section/panel and all its content.

    Removes a section or panel along with all its subsections and button rows
    as a complete unit.
    """

    bl_idname = "amp.section_delete"
    bl_label = "Delete Section/Panel"
    bl_description = "Delete the selected section/panel and all its content"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        """Only enable if current row is a section or panel"""
        return poll_contextual_operation(context, cls, require_section_or_panel=True)

    def invoke(self, context, event):
        """Show confirmation dialog before deletion"""
        category = get_contextual_category(context, self)
        current_row = get_contextual_row(context, self)

        if not category or not current_row or current_row.row_type not in ("SECTION", "PANEL"):
            return {"CANCELLED"}

        # Count content that will be deleted
        section_content_indices = self._get_section_content_indices(category, category.active_row_index)
        content_count = len(section_content_indices) - 1  # Subtract 1 for the section itself

        if content_count > 0:
            return context.window_manager.invoke_confirm(self, event)
        else:
            return self.execute(context)

    def draw(self, context):
        """Draw confirmation dialog"""
        category = get_contextual_category(context, self)
        current_row = get_contextual_row(context, self)

        if category and current_row:
            section_content_indices = self._get_section_content_indices(category, category.active_row_index)
            content_count = len(section_content_indices) - 1

            layout = self.layout
            layout.label(text=f"Delete {current_row.row_type.lower()} '{current_row.name}'?")
            if content_count > 0:
                layout.label(text=f"This will also delete {content_count} content item(s).", icon="INFO")

    def execute(self, context):
        category = get_contextual_category(context, self)
        current_row = get_contextual_row(context, self)

        if not category or not current_row:
            self.report({"WARNING"}, "No section or panel selected.")
            return {"CANCELLED"}

        if current_row.row_type not in ("SECTION", "PANEL"):
            self.report({"WARNING"}, "Selected row is not a section or panel.")
            return {"CANCELLED"}

        section_idx = category.active_row_index

        # Find all content that belongs to this section
        section_content_indices = self._get_section_content_indices(category, section_idx)

        # Store section name for report
        section_name = current_row.name
        content_count = len(section_content_indices) - 1

        # Remove all section content in reverse order to maintain indices
        for idx in reversed(section_content_indices):
            category.rows.remove(idx)

        # Adjust active index
        if len(category.rows) == 0:
            category.active_row_index = 0
        elif section_idx >= len(category.rows):
            category.active_row_index = len(category.rows) - 1
        else:
            category.active_row_index = section_idx

        refresh_ui(context)

        if content_count > 0:
            self.report(
                {"INFO"}, f"Deleted {current_row.row_type.lower()} '{section_name}' with {content_count} content items"
            )
        else:
            self.report({"INFO"}, f"Deleted {current_row.row_type.lower()} '{section_name}'")

        return {"FINISHED"}

    def _get_section_content_indices(self, category, section_idx):
        """Get all indices that belong to this section"""
        indices = [section_idx]

        # Find all content after the section until next main section
        current_idx = section_idx + 1
        while current_idx < len(category.rows):
            row = category.rows[current_idx]

            # Stop if we hit another main section or non-indented panel
            if (row.row_type == "SECTION" and not row.is_subsection) or (
                row.row_type == "PANEL" and not row.is_subsection
            ):
                break

            indices.append(current_idx)
            current_idx += 1

        return indices


# -----------------------------------------------------------------------------
# Button Copy/Paste Operators
# -----------------------------------------------------------------------------
class AMP_OT_row_button_copy(Operator):
    """Copy a button entry to clipboard as JSON.

    Copies the button entry with all its properties to the clipboard.
    """

    bl_idname = "amp.row_button_copy"
    bl_label = "Copy Button"
    bl_description = "Copy button to clipboard as JSON"

    entry_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)
    category_index: IntProperty()
    row_index: IntProperty()

    def execute(self, context):
        row = get_contextual_row(context, self)
        if not row:
            self.report({"WARNING"}, "Target row not found.")
            return {"CANCELLED"}

        if not (0 <= self.entry_index < len(row.buttons)):
            self.report({"WARNING"}, "Invalid button entry index.")
            return {"CANCELLED"}

        button_to_copy = row.buttons[self.entry_index]
        data = ptr_to_dict(button_to_copy)

        # Wrap in a container to identify it as a button
        button_data = {"type": "button_entry", "content": data}

        context.window_manager.clipboard = json.dumps(button_data)
        self.report({"INFO"}, f"Button '{button_to_copy.name or button_to_copy.button_id}' copied")
        return {"FINISHED"}


class AMP_OT_row_button_paste(Operator):
    """Paste a button entry from clipboard JSON.

    Creates a new button entry from JSON data in the clipboard.
    """

    bl_idname = "amp.row_button_paste"
    bl_label = "Paste Button"
    bl_description = "Paste button from clipboard JSON"

    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)
    category_index: IntProperty()
    row_index: IntProperty()

    @classmethod
    def poll(cls, context):
        """Only enable if clipboard contains valid button data and we have valid context"""
        return poll_contextual_operation(context, cls, require_clipboard_data=True, clipboard_data_type="button_entry")

    def execute(self, context):
        row = get_contextual_row(context, self)
        if not row:
            self.report({"WARNING"}, "Target row not found.")
            return {"CANCELLED"}

        clip = context.window_manager.clipboard
        try:
            data = json.loads(clip)
        except Exception:
            try:
                data = ast.literal_eval(clip)
            except Exception:
                self.report({"WARNING"}, "Clipboard does not contain valid JSON or Python literal")
                return {"CANCELLED"}

        # Check if this is a button entry
        if not isinstance(data, dict) or data.get("type") != "button_entry":
            self.report({"WARNING"}, "Clipboard does not contain button data")
            return {"CANCELLED"}

        button_content = data.get("content", {})
        if not button_content:
            self.report({"WARNING"}, "No button content found in clipboard")
            return {"CANCELLED"}

        insert_idx = row.active_button_index + 1
        new_entry = row.buttons.add()
        dict_to_ptr(new_entry, button_content)

        # Add "Copy" to button name if it's a custom script
        if new_entry.button_id == "custom_script" and new_entry.display_name:
            new_entry.display_name += " Copy"

        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        self.report({"INFO"}, f"Button '{new_entry.name or new_entry.button_id}' pasted")
        return {"FINISHED"}


class AMP_OT_row_panel_add(Operator):
    """Display panel selection popup.

    Shows a popup with available panels organized by category,
    allowing the user to select and add a panel to the row.
    """

    bl_idname = "amp.row_panel_add"
    bl_label = "Add Panel to Row"
    bl_description = "Add a panel to the current row"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=300)

    def draw(self, context):
        import re
        from collections import defaultdict

        groups = defaultdict(list)
        # collect functions by "Section_Panel" naming
        try:
            from . import addon_ui_definitions_panels

            # Safely get all functions without calling them
            for name, func in inspect.getmembers(addon_ui_definitions_panels, inspect.isfunction):
                try:
                    if name.startswith("_"):
                        continue
                    if func.__module__ != addon_ui_definitions_panels.__name__:
                        continue
                    if not name.startswith("Panels_"):
                        continue
                    # Extract section and panel name from "Panels_SectionName" format
                    panel_name = name[7:]  # Remove "Panels_" prefix
                    if "_" in panel_name:
                        section, panel = panel_name.split("_", 1)
                    else:
                        section = "General"
                        panel = panel_name
                    groups[section].append((panel, func, name))
                except Exception:
                    # Skip problematic functions silently
                    continue

        except ImportError:
            self.layout.label(text="No panel definitions found", icon="ERROR")
            return
        except Exception:
            self.layout.label(text="Error loading panel definitions", icon="ERROR")
            return

        # If forge version is enabled, also collect forge panel definitions
        if is_forge_version():
            try:
                from . import addon_ui_definitions_panels_forge

                for name, func in inspect.getmembers(addon_ui_definitions_panels_forge, inspect.isfunction):
                    try:
                        if name.startswith("_"):
                            continue
                        if func.__module__ != addon_ui_definitions_panels_forge.__name__:
                            continue
                        if not name.startswith("Panels_"):
                            continue
                        # Extract section and panel name from "Panels_SectionName" format
                        panel_name = name[7:]  # Remove "Panels_" prefix
                        if "_" in panel_name:
                            section, panel = panel_name.split("_", 1)
                        else:
                            section = "General"
                            panel = panel_name
                        groups[section].append((panel, func, name))
                    except Exception:
                        # Skip problematic functions silently
                        continue
            except ImportError:
                # Forge panel definitions not available
                pass

        if not groups:
            self.layout.label(text="No panels available", icon="INFO")
            return

        # build UI: one box per section
        for section in sorted(groups):
            try:
                box = self.layout.box()
                box.label(text=section)
                for panel, func, full_name in sorted(groups[section], key=lambda x: x[0]):
                    row = self.layout.row(align=True)
                    row.label(text="", icon="BLANK1")
                    op = row.operator("amp.row_panel_add_exec", text="", icon="ADD")
                    # Pass context to the execution operator
                    op.data_owner_is_popup_panel = self.data_owner_is_popup_panel
                    op.data_owner_popup_panel_index = self.data_owner_popup_panel_index
                    op.category_index = self.category_index
                    op.row_index = self.row_index
                    op.panel_id = full_name
                    row.separator()
                    # Show panel icon instead of trying to call the function
                    row.label(text="", icon="PLUGIN")
                    # split CamelCase panel into words
                    display = re.sub(r"(.)([A-Z][a-z]+)", r"\1 \2", panel)
                    display = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", display)
                    row.label(text=display)
                self.layout.separator()
            except Exception:
                # Skip problematic sections
                continue

    def execute(self, context):
        return {"FINISHED"}


class AMP_OT_row_panel_add_exec(Operator):
    """Execute panel addition to row.

    Assigns the selected panel ID to the target row and updates
    the row name with a readable display name.
    """

    bl_idname = "amp.row_panel_add_exec"
    bl_label = "Execute Add Panel"
    bl_description = "Execute adding a panel to the row"

    category_index: IntProperty()
    row_index: IntProperty()
    panel_id: StringProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # Use category_index and row_index directly with get_contextual_row
        row = get_contextual_row(context, self)  # Relies on self.category_index and self.row_index
        if not row:
            self.report({"WARNING"}, f"Target row not found.")
            return {"CANCELLED"}

        if row.row_type != "PANEL":
            self.report({"WARNING"}, "Target row is not a panel row.")
            return {"CANCELLED"}

        # Set the panel_id on the row
        row.panel_id = self.panel_id
        # Extract display name from panel_id
        if self.panel_id.startswith("Panels_"):
            display_name = self.panel_id[7:]  # Remove "Panels_" prefix
            # Convert CamelCase to readable name
            import re

            display_name = re.sub(r"(.)([A-Z][a-z]+)", r"\1 \2", display_name)
            display_name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", display_name)
            row.name = display_name
        else:
            row.name = self.panel_id

        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_button_add(Operator):
    """Display button selection popup.

    Shows a popup with available buttons organized by category,
    allowing the user to select and add a button to the row.
    """

    bl_idname = "amp.row_button_add"
    bl_label = "Add Button to Row"
    bl_description = "Add a button to the current row"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    # Search filter property
    search_filter: StringProperty(
        name="Search", description="Filter buttons by name", default="", options={"TEXTEDIT_UPDATE"}
    )

    def invoke(self, context, event):
        # Single column layout now, so we can make it wider
        popup_width = 500  # Increased width for better usability

        # The properties category_index, row_index, data_owner_is_popup_panel, data_owner_popup_panel_index
        # are passed to AMP_OT_row_button_add_exec by the draw method.
        return context.window_manager.invoke_popup(self, width=popup_width)

    def draw(self, context):
        import re
        from collections import defaultdict

        layout = self.layout

        # Search field at the top
        search_box = layout.box()
        search_row = search_box.row()
        search_row.prop(self, "search_filter", text="", icon="VIEWZOOM")

        layout.separator()

        groups = defaultdict(list)

        # Get preferences to check forge version
        prefs = get_prefs()

        # Collect functions from regular button definitions
        for name, func in inspect.getmembers(addon_ui_definitions_button, inspect.isfunction):
            if name.startswith("_"):
                continue
            if func.__module__ != addon_ui_definitions_button.__name__:
                continue
            parts = name.split("_", 1)
            if len(parts) != 2:
                continue
            section, btn = parts
            groups[section].append((btn, func))

        # If forge version is enabled, also collect forge button definitions
        if prefs.forge_version:
            try:
                from . import addon_ui_definitions_button_forge

                for name, func in inspect.getmembers(addon_ui_definitions_button_forge, inspect.isfunction):
                    if name.startswith("_"):
                        continue
                    if func.__module__ != addon_ui_definitions_button_forge.__name__:
                        continue
                    parts = name.split("_", 1)
                    if len(parts) != 2:
                        continue
                    section, btn = parts
                    groups[section].append((btn, func))
            except ImportError:
                # Forge definitions not available
                pass

        # Filter logic
        search_text = self.search_filter.lower().strip()
        filtered_groups = {}

        if search_text:
            # When searching, show all matching buttons and their categories
            for section, buttons in groups.items():
                matching_buttons = []
                for btn, func in buttons:
                    # Check if button name matches search
                    btn_display = re.sub(r"(.)([A-Z][a-z]+)", r"\1 \2", btn)
                    btn_display = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", btn_display)
                    if (
                        search_text in btn.lower()
                        or search_text in btn_display.lower()
                        or search_text in section.lower()
                    ):
                        matching_buttons.append((btn, func))

                if matching_buttons:
                    filtered_groups[section] = matching_buttons
        else:
            # No search, show all groups
            filtered_groups = groups

        if not filtered_groups:
            layout.label(text="No buttons found matching your search", icon="INFO")
            return

        # Organize sections - put Experimental at the end
        all_sections = list(filtered_groups.keys())
        experimental_section = None
        if "Experimental" in all_sections:
            experimental_section = "Experimental"
            all_sections.remove("Experimental")

        # Sort non-experimental sections alphabetically, then add Experimental at the end
        sorted_sections = sorted(all_sections)
        if experimental_section:
            sorted_sections.append(experimental_section)

        # Single column layout for all sections
        for section in sorted_sections:
            section_buttons = filtered_groups[section]

            # Create toggle identifier for this section
            toggle_name = f"button_add_section_{section}"

            # Determine if section should be expanded
            # Always expand if searching, otherwise use toggle state
            if search_text:
                section_expanded = True
            else:
                # Import the toggles from operators.py
                from ..operators import toggles

                section_expanded = toggles.get(toggle_name, False)

            header_box = layout.box()
            # Create section header with toggle button
            header_row = header_box.row(align=True)

            if not search_text:  # Only show toggle when not searching
                # Make the section name itself clickable to toggle
                name_row = header_row.row(align=True)
                name_row.alignment = "LEFT"
                toggle_op = name_row.operator(
                    "ui.amp_toggle_panel_visibility",
                    text=section,
                    icon="TRIA_DOWN" if section_expanded else "TRIA_RIGHT",
                    emboss=False,
                )
                toggle_op.panel_name = toggle_name
                toggle_op.default_open = False

                toggle_op_blank = header_row.operator(
                    "ui.amp_toggle_panel_visibility", text=" ", icon="NONE", emboss=False
                )
                toggle_op_blank.panel_name = toggle_name
                toggle_op_blank.default_open = False

            else:
                # When searching, just show the section name as a label since toggles are disabled
                header_row.label(text=section)

            # Draw buttons if section is expanded or we're searching
            if section_expanded:
                # Create section box for buttons
                section_box = layout.box()

                # Add buttons for this section
                for btn, func in sorted(section_buttons, key=lambda x: x[0]):
                    row = section_box.row(align=True)
                    row.label(text="", icon="BLANK1")
                    op = row.operator("amp.row_button_add_exec", text="", icon="ADD")
                    # Pass context to the execution operator
                    op.data_owner_is_popup_panel = self.data_owner_is_popup_panel
                    op.data_owner_popup_panel_index = self.data_owner_popup_panel_index
                    op.category_index = self.category_index  # Index of category in owner's collection
                    op.row_index = self.row_index  # Index of row in category's collection
                    op.button_id = f"{section}_{btn}"
                    row.separator()

                    # Create a sub-layout that's always active for the button preview
                    button_preview_layout = row.column()
                    button_preview_layout.active = True
                    func(button_preview_layout, context)

                    # split CamelCase btn into words
                    display = re.sub(r"(.)([A-Z][a-z]+)", r"\1 \2", btn)
                    display = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", display)
                    row.label(text=display)

            # Add separator between sections
            layout.separator()

    def execute(self, context):
        return {"FINISHED"}


class AMP_OT_row_button_add_exec(Operator):
    """Execute button addition to row.

    Adds the selected button to the target row and positions it
    after the currently active button.
    """

    bl_idname = "amp.row_button_add_exec"
    bl_label = "Execute Add Button"
    bl_description = "Execute adding a button to the row"

    category_index: IntProperty()
    row_index: IntProperty()
    button_id: StringProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # Use category_index and row_index directly with get_contextual_row
        # get_contextual_row needs category_index on `self` to find the category first.
        row = get_contextual_row(context, self)  # Relies on self.category_index and self.row_index
        if not row:
            self.report({"WARNING"}, f"Target row not found.")
            return {"CANCELLED"}

        insert_idx = row.active_button_index + 1
        entry = row.buttons.add()
        entry.button_id = self.button_id
        entry.name = self.button_id

        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_button_add_spacer(Operator):
    """Add a spacer to the specified row.

    Creates a spacer element with configurable width for layout spacing.
    """

    bl_idname = "amp.row_button_add_spacer"
    bl_label = "Add Spacer"
    bl_description = "Add a spacer to the row"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        row = get_contextual_row(context, self)  # Relies on self.category_index and self.row_index
        if not row:
            self.report({"WARNING"}, "Target row not found.")
            return {"CANCELLED"}

        insert_idx = row.active_button_index + 1
        entry = row.buttons.add()
        entry.button_id = "spacer"
        entry.spacer_width = 1.0
        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_button_add_property(Operator):
    """Insert a new property element into the specified row.

    Creates a property element that can display Blender properties.
    """

    bl_idname = "amp.row_button_add_property"
    bl_label = "Add Property"
    bl_description = "Add a property element to the row"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        row = get_contextual_row(context, self)  # Relies on self.category_index and self.row_index
        if not row:
            self.report({"WARNING"}, "Target row not found.")
            return {"CANCELLED"}

        insert_idx = row.active_button_index + 1
        entry = row.buttons.add()
        entry.button_id = "property"
        entry.name = "Property"
        entry.icon = "PROPERTIES"
        entry.display_name = "Property"
        entry.button_path = ""
        entry.property_slider = False
        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_button_add_operator(Operator):
    """Insert a new operator element into the specified row.

    Creates an operator element that can execute Blender operators with properties.
    """

    bl_idname = "amp.row_button_add_operator"
    bl_label = "Add Operator"
    bl_description = "Add an operator element to the row"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        row = get_contextual_row(context, self)  # Relies on self.category_index and self.row_index
        if not row:
            self.report({"WARNING"}, "Target row not found.")
            return {"CANCELLED"}

        insert_idx = row.active_button_index + 1
        entry = row.buttons.add()
        entry.button_id = "operator"
        entry.name = "Operator"
        entry.icon = "PLAY"
        entry.display_name = "Operator"
        entry.button_path = ""
        entry.operator_properties = ""
        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_button_add_script(Operator):
    """Insert a new custom-script button into the specified row.

    Creates a custom script button that can execute user-defined Python code.
    """

    bl_idname = "amp.row_button_add_script"
    bl_label = "Add Custom Script"
    bl_description = "Add a custom script button to the row"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        row = get_contextual_row(context, self)  # Relies on self.category_index and self.row_index
        if not row:
            self.report({"WARNING"}, "Target row not found.")
            return {"CANCELLED"}

        insert_idx = row.active_button_index + 1
        entry = row.buttons.add()
        entry.button_id = "custom_script"
        entry.name = ""  # Default name for custom script button
        entry.icon = "USER"
        entry.script = ""
        entry.custom = True
        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Operators: Delete
# -----------------------------------------------------------------------------
class AMP_OT_category_delete(Operator):
    """Delete a category by index.

    Removes the specified category and adjusts the active index accordingly.
    """

    bl_idname = "amp.category_delete"
    bl_label = "Delete Category"
    bl_description = "Delete the specified category"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        owner, coll, active_idx_prop = get_contextual_owner_collection_indices(context, self)
        if not owner or not coll:
            self.report({"WARNING"}, "Contextual owner or collection not found.")
            return {"CANCELLED"}

        if 0 <= self.index < len(coll):
            coll.remove(self.index)
            current_active = getattr(owner, active_idx_prop)
            if len(coll) == 0:
                setattr(owner, active_idx_prop, 0)  # Or -1 if appropriate for no selection
            elif current_active >= self.index:
                setattr(owner, active_idx_prop, max(0, current_active - 1))
            else:  # Active index was before removed, or collection still has items
                setattr(owner, active_idx_prop, min(current_active, len(coll) - 1))
            refresh_ui(context)
        else:
            self.report({"WARNING"}, f"Index {self.index} out of range for category deletion.")
            return {"CANCELLED"}
        return {"FINISHED"}


class AMP_OT_row_delete(Operator):
    """Delete a row by index.

    Removes the specified row and adjusts the active row index accordingly.
    """

    bl_idname = "amp.row_delete"
    bl_label = "Delete Row"
    bl_description = "Delete the specified row"

    index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)
    category_index: IntProperty()
    row_index: IntProperty()

    def execute(self, context):
        # use the operator’s own category_index to pick the right category
        category = get_contextual_category(context, self, category_idx_prop_name="category_index")
        if not category:
            self.report({"WARNING"}, "Contextual category not found for row deletion.")
            return {"CANCELLED"}

        if 0 <= self.index < len(category.rows):
            category.rows.remove(self.index)
            current_active_row = category.active_row_index
            if len(category.rows) == 0:
                category.active_row_index = 0
            elif current_active_row >= self.index:
                category.active_row_index = max(0, current_active_row - 1)
            else:
                category.active_row_index = min(current_active_row, len(category.rows) - 1)
            refresh_ui(context)
        else:
            self.report({"WARNING"}, f"Index {self.index} out of range for row deletion.")
            return {"CANCELLED"}
        return {"FINISHED"}


class AMP_OT_row_edit_conditional(Operator):
    """Edit the conditional expression for a row.

    Opens a popup dialog where users can enter Python expressions
    that control when the row is displayed in the UI.
    """

    bl_idname = "amp.row_edit_conditional"
    bl_label = "Edit Row Conditional"
    bl_description = "Edit the Python expression that controls when this row is displayed"

    category_index: IntProperty()
    row_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    conditional_text: StringProperty(
        name="Conditional Expression",
        default="",
        description="Python expression (e.g., 'bpy.context.active_object' or 'context.area.type == \"GRAPH_EDITOR\"')",
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        # Get the current row and load its conditional
        row = get_contextual_row(context, self, row_idx_prop_name="row_index")
        if not row:
            self.report({"ERROR"}, "Could not find row")
            return {"CANCELLED"}

        self.conditional_text = row.conditional
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False

        # Instructions
        box = layout.box()
        col = box.column()
        col.label(text="Enter a Python expression to control when this row is displayed:")
        col.label(text="Examples:", icon="INFO")
        col.label(text="  • bpy.context.active_object")
        col.label(text="  • context.area.type == 'GRAPH_EDITOR'")
        col.label(text="  • bpy.context.active_object and context.mode == 'POSE'")
        col.label(text="Leave empty to always show the row.")

        layout.separator()

        # Text input
        col = layout.column()
        col.prop(self, "conditional_text", text="Expression")

    def execute(self, context):
        row = get_contextual_row(context, self, row_idx_prop_name="row_index")
        if not row:
            self.report({"ERROR"}, "Could not find row")
            return {"CANCELLED"}

        # Update the row's conditional
        row.conditional = self.conditional_text.strip()

        # Test the expression if it's not empty

        if row.conditional:
            try:
                # Try to compile the expression to check for syntax errors
                compile(row.conditional, "<conditional>", "eval")
                self.report({"INFO"}, f"Conditional expression set: {row.conditional}")
            except SyntaxError as e:
                self.report({"WARNING"}, f"Syntax error in expression: {e}")
            except Exception as e:
                self.report({"WARNING"}, f"Error in expression: {e}")
        else:
            self.report({"INFO"}, "Conditional expression cleared - row will always be shown")

        refresh_ui(context)
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# Operators: delete a button entry from a row
# -----------------------------------------------------------------------------
class AMP_OT_row_button_entry_delete(Operator):
    """Delete a button entry from a row.

    Removes the specified button entry and adjusts the active button index.
    """

    bl_idname = "amp.row_button_entry_delete"
    bl_label = "Delete Button Entry"
    bl_description = "Delete the specified button entry"

    entry_index: IntProperty()
    category_index: IntProperty(default=-1)
    row_index: IntProperty(default=-1)
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # Use operator.row_index rather than category.active_row_index
        row = get_contextual_row(context, self, row_idx_prop_name="row_index")

        if not row:
            self.report({"WARNING"}, "Contextual row not found for button entry deletion.")
            return {"CANCELLED"}

        if 0 <= self.entry_index < len(row.buttons):
            row.buttons.remove(self.entry_index)
            current_active_btn = row.active_button_index
            if len(row.buttons) == 0:
                row.active_button_index = 0
            elif current_active_btn >= self.entry_index:
                row.active_button_index = max(0, current_active_btn - 1)
            else:
                row.active_button_index = min(current_active_btn, len(row.buttons) - 1)
            refresh_ui(context)
        else:
            self.report({"WARNING"}, f"Index {self.entry_index} out of range for button entry deletion.")
            return {"CANCELLED"}
        return {"FINISHED"}


class AMP_OT_row_button_entry_duplicate(Operator):
    """Duplicate a button entry.

    Creates an exact copy of the specified button entry and places it
    after the original.
    """

    bl_idname = "amp.row_button_entry_duplicate"
    bl_label = "Duplicate Button Entry"
    bl_description = "Duplicate the specified button entry"

    entry_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)
    category_index: IntProperty()
    row_index: IntProperty()

    def execute(self, context):
        row = get_contextual_row(context, self)
        if not row:
            return {"CANCELLED"}

        if not (0 <= self.entry_index < len(row.buttons)):
            self.report({"WARNING"}, "Invalid button entry index for duplication.")
            return {"CANCELLED"}

        entry_to_duplicate = row.buttons[self.entry_index]
        data = ptr_to_dict(entry_to_duplicate)

        insert_idx = self.entry_index + 1  # row.active_button_index + 1
        new_entry = row.buttons.add()
        dict_to_ptr(new_entry, data)

        if new_entry.button_id == "custom_script":
            if new_entry.display_name:
                new_entry.display_name += " Copy"
            else:  # Should have a name from ptr_to_dict if original had one
                new_entry.display_name = (new_entry.name or "Script") + " Copy"

        row.buttons.move(len(row.buttons) - 1, insert_idx)
        row.active_button_index = insert_idx
        refresh_ui(context)
        return {"FINISHED"}


# new: move up/down for button entries
class AMP_OT_row_button_entry_move_up(Operator):
    """Move a button entry one position up.

    Swaps the button entry with the one above it, if not already at the top.
    """

    bl_idname = "amp.row_button_entry_move_up"
    bl_label = "Move Button Entry Up"
    bl_description = "Move the button entry one position up"

    entry_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)
    category_index: IntProperty()
    row_index: IntProperty()

    def execute(self, context):
        row = get_contextual_row(context, self)
        if not row:
            return {"CANCELLED"}

        # self.entry_index is the one to move, usually set to row.active_button_index by UI
        idx_to_move = self.entry_index
        if idx_to_move > 0 and idx_to_move < len(row.buttons):
            row.buttons.move(idx_to_move, idx_to_move - 1)
            row.active_button_index = idx_to_move - 1
            refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_row_button_entry_move_down(Operator):
    """Move a button entry one position down.

    Swaps the button entry with the one below it, if not already at the bottom.
    """

    bl_idname = "amp.row_button_entry_move_down"
    bl_label = "Move Button Entry Down"
    bl_description = "Move the button entry one position down"

    entry_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)
    category_index: IntProperty()
    row_index: IntProperty()

    def execute(self, context):
        row = get_contextual_row(context, self)
        if not row:
            return {"CANCELLED"}

        idx_to_move = self.entry_index
        if idx_to_move < len(row.buttons) - 1 and idx_to_move >= 0:
            row.buttons.move(idx_to_move, idx_to_move + 1)
            row.active_button_index = idx_to_move + 1
            refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_execute_operator_string(Operator):
    """Execute an operator string directly as if run in Python console.

    This operator takes a string containing a Blender operator call
    and executes it directly, allowing for complex operator calls
    with nested parameters. The operator is executed in the current
    space/context where the button was called from.
    """

    bl_idname = "amp.execute_operator_string"
    bl_label = "Execute Operator"
    bl_description = "Execute the operator assigned to this button"

    operator_string: StringProperty(
        name="Operator String",
        description="The operator string to execute (e.g., bpy.ops.object.duplicate_move(...))",
        default="",
    )

    def execute(self, context):
        if not self.operator_string.strip():
            self.report({"ERROR"}, "No operator string provided")
            return {"CANCELLED"}

        try:
            # Setup namespace for exec
            namespace = {
                "bpy": bpy,
                "context": context,
                "C": context,
                "__name__": "__main__",
            }

            # Build call string so it invokes the operator in modal/invoke context
            op_str = self.operator_string.strip()
            if op_str.startswith("bpy.ops."):
                idx = op_str.find("(")
                if idx != -1:
                    # insert 'INVOKE_DEFAULT' as first arg
                    call_str = op_str[:idx] + "('INVOKE_DEFAULT'," + op_str[idx + 1 :]
                else:
                    call_str = op_str + "('INVOKE_DEFAULT')"
            else:
                call_str = op_str

            # Execute the adjusted call
            exec(call_str, namespace)

        except Exception as e:
            self.report({"ERROR"}, f"Error executing operator: {str(e)}")
            return {"CANCELLED"}

        return {"FINISHED"}


class AMP_OT_execute_custom_script(Operator):
    """Execute the Python script assigned to a custom-script button.

    Runs the custom Python script either from a text datablock or
    from a file in the custom scripts directory.
    """

    bl_idname = "amp.execute_custom_script"
    bl_label = "Execute Custom Script"
    bl_description = "Execute the Python script assigned to this button"

    # These indices are relative to the contextual owner/category/row
    category_index: IntProperty()
    row_index: IntProperty()
    button_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # The operator itself has category_index, row_index, button_index.
        # We need to use these to navigate from the contextual owner.

        # First, try to validate the current context
        owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)

        # Check if the current context is valid
        context_is_valid = (
            owner
            and cat_coll
            and 0 <= self.category_index < len(cat_coll)
            and hasattr(cat_coll[self.category_index], "rows")
            and 0 <= self.row_index < len(cat_coll[self.category_index].rows)
            and hasattr(cat_coll[self.category_index].rows[self.row_index], "buttons")
            and 0 <= self.button_index < len(cat_coll[self.category_index].rows[self.row_index].buttons)
        )

        # If current context is invalid, try to auto-detect the correct context
        if not context_is_valid:
            # First, try to find in regular UI categories (reset popup context)
            self.data_owner_is_popup_panel = False
            self.data_owner_popup_panel_index = -1
            owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)

            # Check if regular UI context is valid
            regular_ui_valid = (
                owner
                and cat_coll
                and 0 <= self.category_index < len(cat_coll)
                and hasattr(cat_coll[self.category_index], "rows")
                and 0 <= self.row_index < len(cat_coll[self.category_index].rows)
                and hasattr(cat_coll[self.category_index].rows[self.row_index], "buttons")
                and 0 <= self.button_index < len(cat_coll[self.category_index].rows[self.row_index].buttons)
            )

            # If regular UI is not valid, try popup panels
            if not regular_ui_valid:
                popup_panel_idx, adjusted_cat_idx = find_popup_panel_context_for_button(
                    self.category_index, self.row_index, self.button_index
                )

                if popup_panel_idx is not None:
                    # Set popup panel context
                    self.data_owner_is_popup_panel = True
                    self.data_owner_popup_panel_index = popup_panel_idx
                    # Re-get the owner and category collection with corrected context
                    owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)

        if not owner or not cat_coll:
            self.report({"ERROR"}, "Contextual owner or category collection not found.")
            return {"CANCELLED"}

        # 2. Get the specific category using self.category_index
        if not (0 <= self.category_index < len(cat_coll)):
            # Provide detailed error info for debugging
            context_info = "popup panel" if getattr(self, "data_owner_is_popup_panel", False) else "regular UI"
            panel_idx = getattr(self, "data_owner_popup_panel_index", -1)
            if getattr(self, "data_owner_is_popup_panel", False):
                self.report(
                    {"ERROR"},
                    f"Category index {self.category_index} out of range for {context_info} (popup panel {panel_idx}). Available categories: {len(cat_coll)}",
                )
            else:
                self.report(
                    {"ERROR"},
                    f"Category index {self.category_index} out of range for {context_info}. Available categories: {len(cat_coll)}",
                )
            return {"CANCELLED"}
        category = cat_coll[self.category_index]

        # 3. Get the specific row using self.row_index
        if not (hasattr(category, "rows") and 0 <= self.row_index < len(category.rows)):
            self.report(
                {"ERROR"},
                f"Row index {self.row_index} out of range for category '{category.name}'. Available rows: {len(category.rows) if hasattr(category, 'rows') else 0}",
            )
            return {"CANCELLED"}
        row = category.rows[self.row_index]

        # 4. Get the specific button entry using self.button_index
        if not (hasattr(row, "buttons") and 0 <= self.button_index < len(row.buttons)):
            context_info = "popup panel" if getattr(self, "data_owner_is_popup_panel", False) else "regular UI"
            self.report(
                {"ERROR"},
                f"Button index {self.button_index} out of range for row in {context_info}. Available buttons: {len(row.buttons) if hasattr(row, 'buttons') else 0}",
            )
            return {"CANCELLED"}
        entry = row.buttons[self.button_index]

        prefs = get_prefs()  # Still need prefs for custom_scripts_path

        source = None

        # Try to get source from text datablock first
        if entry.text_block_name:
            text = bpy.data.texts.get(entry.text_block_name)
            if text:
                source = text.as_string()
            else:
                # Text datablock not found, try to reload from script file if available
                if entry.script:
                    script_path = entry.script
                    if not os.path.isabs(script_path):
                        script_path = os.path.join(prefs.custom_scripts_path, script_path)

                    if os.path.isfile(script_path):
                        try:
                            # Reload the text datablock from file
                            text = bpy.data.texts.load(script_path)
                            entry.text_block_name = text.name  # Update the reference
                            source = text.as_string()
                            # self.report({"INFO"}, f"Reloaded text datablock: {text.name}")
                        except Exception as e:
                            # If reloading text datablock fails, read directly from file
                            try:
                                with open(script_path, "r") as f:
                                    source = f.read()
                                # self.report({"INFO"}, f"Loaded script from file: {script_path}")
                            except Exception as file_error:
                                self.report({"ERROR"}, f"Failed to load script: {file_error}")
                                return {"CANCELLED"}
                    else:
                        self.report({"ERROR"}, f"Script file not found: {script_path}")
                        return {"CANCELLED"}
                else:
                    self.report({"ERROR"}, "Text datablock not found and no script file specified")
                    return {"CANCELLED"}

        # If no text_block_name, try to load directly from script file
        if source is None and entry.script:
            script_path = entry.script
            if not os.path.isabs(script_path):
                script_path = os.path.join(prefs.custom_scripts_path, script_path)

            if os.path.isfile(script_path):
                with open(script_path, "r") as f:
                    source = f.read()
            else:
                self.report({"ERROR"}, f"Script file not found: {script_path}")
                return {"CANCELLED"}

        # If we still don't have source, report error
        if source is None:
            self.report({"ERROR"}, "No script source available")
            return {"CANCELLED"}
        try:
            namespace = {"bpy": bpy, "__name__": "__main__"}
            exec(source, namespace)
        except Exception as e:
            self.report({"ERROR"}, f"Error in custom script:\n{e}")
        return {"FINISHED"}


# Operators for custom script assignment, creation, and editing
# These operators (assign, create, edit, unassign script) are called from _draw_custom_script_buttons.
# As noted there, that function currently assumes a `prefs` context for simplicity.
# To make these fully contextual, _draw_custom_script_buttons would need to pass the correct
# owner, and these operators would use get_contextual_button_entry.
# For now, they will inherit the `prefs` assumption from _draw_custom_script_buttons.
# If `set_operator_context` is called correctly in `_draw_custom_script_buttons`
# then these operators can use `get_contextual_button_entry`.


class AMP_OT_row_button_assign_script(Operator):
    """Display a file selector and assign a chosen script to the button.

    Shows available Python scripts from the custom scripts folder
    and assigns the selected one to the button.
    """

    bl_idname = "amp.row_button_assign_script"
    bl_label = "Assign Script to Custom Button"
    bl_description = "Assign a script file to this custom button"

    category_index: IntProperty()
    row_index: IntProperty()
    entry_index: IntProperty()
    file_name: StringProperty(default="", options={"SKIP_SAVE"})
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    # Filter property for searching scripts
    filter_text: StringProperty(
        name="Filter", description="Filter scripts by name (case insensitive)", default="", options={"SKIP_SAVE"}
    )

    def invoke(self, context, event):
        # if a filename was provided, skip popup and assign immediately
        if self.file_name:
            return self.execute(context)
        prefs = get_prefs()
        path = prefs.custom_scripts_path
        if not path or not os.path.isdir(path):
            self.report({"WARNING"}, "Custom scripts folder not set or invalid")
            return {"CANCELLED"}
        self.files = sorted([f for f in os.listdir(path) if f.endswith(".py")], key=str.lower)
        return context.window_manager.invoke_popup(self, width=300)

    def draw(self, context):
        layout = self.layout
        if not self.file_name:
            # Add filter field at the top
            layout.prop(self, "filter_text", text="", icon="VIEWZOOM")
            layout.separator()

            # Filter files based on search text (case insensitive)
            filtered_files = []
            for f_name in self.files:
                if not self.filter_text or self.filter_text.lower() in f_name.lower():
                    filtered_files.append(f_name)

            # Always sort the filtered files (case-insensitive)
            filtered_files.sort(key=str.lower)

            if not filtered_files:
                layout.label(text="No scripts match the filter", icon="INFO")
                return

            for f_name in filtered_files:
                op = layout.operator("amp.row_button_assign_script", text=f_name)
                # Pass context along
                op.data_owner_is_popup_panel = self.data_owner_is_popup_panel
                op.data_owner_popup_panel_index = self.data_owner_popup_panel_index
                op.category_index = self.category_index
                op.row_index = self.row_index
                op.entry_index = self.entry_index
                op.file_name = f_name

    def execute(self, context):
        # Use explicit indices to navigate to the button entry
        # 1. Get the owner and its category collection
        owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)
        if not owner or not cat_coll:
            self.report({"ERROR"}, "Contextual owner or category collection not found.")
            return {"CANCELLED"}

        # 2. Get the specific category using self.category_index
        if not (0 <= self.category_index < len(cat_coll)):
            self.report({"ERROR"}, f"Category index {self.category_index} out of range.")
            return {"CANCELLED"}
        category = cat_coll[self.category_index]

        # 3. Get the specific row using self.row_index
        if not (hasattr(category, "rows") and 0 <= self.row_index < len(category.rows)):
            self.report({"ERROR"}, f"Row index {self.row_index} out of range for category '{category.name}'.")
            return {"CANCELLED"}
        row = category.rows[self.row_index]

        # 4. Get the specific button entry using self.entry_index
        if not (hasattr(row, "buttons") and 0 <= self.entry_index < len(row.buttons)):
            self.report({"ERROR"}, f"Button index {self.entry_index} out of range for row.")
            return {"CANCELLED"}
        entry = row.buttons[self.entry_index]

        prefs = get_prefs()  # For custom_scripts_path
        base = prefs.custom_scripts_path
        full_path = os.path.join(base, self.file_name)
        text = bpy.data.texts.get(self.file_name) or bpy.data.texts.load(full_path)
        entry.script = self.file_name
        entry.text_block_name = text.name
        refresh_ui(context)
        self.report({"INFO"}, f"Script '{self.file_name}' assigned")
        return {"FINISHED"}


class AMP_OT_row_button_create_script(Operator):
    """Create a new Python script file and assign it to the button.

    Creates a new script file in the custom scripts directory with
    a basic template and assigns it to the button.
    """

    bl_idname = "amp.row_button_create_script"
    bl_label = "Create Script for Custom Button"
    bl_description = "Create a new script file for this custom button"

    category_index: IntProperty()
    row_index: IntProperty()
    entry_index: IntProperty()
    script_name: StringProperty(name="Script Name", default="", options={"SKIP_SAVE"})
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "script_name")

    def execute(self, context):
        # Use explicit indices to navigate to the button entry
        # 1. Get the owner and its category collection
        owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)
        if not owner or not cat_coll:
            self.report({"ERROR"}, "Contextual owner or category collection not found.")
            return {"CANCELLED"}

        # 2. Get the specific category using self.category_index
        if not (0 <= self.category_index < len(cat_coll)):
            self.report({"ERROR"}, f"Category index {self.category_index} out of range.")
            return {"CANCELLED"}
        category = cat_coll[self.category_index]

        # 3. Get the specific row using self.row_index
        if not (hasattr(category, "rows") and 0 <= self.row_index < len(category.rows)):
            self.report({"ERROR"}, f"Row index {self.row_index} out of range for category '{category.name}'.")
            return {"CANCELLED"}
        row = category.rows[self.row_index]

        # 4. Get the specific button entry using self.entry_index
        if not (hasattr(row, "buttons") and 0 <= self.entry_index < len(row.buttons)):
            self.report({"ERROR"}, f"Button index {self.entry_index} out of range for row.")
            return {"CANCELLED"}
        entry = row.buttons[self.entry_index]

        prefs = get_prefs()  # For custom_scripts_path
        name = self.script_name.strip()
        if not name:
            self.report({"WARNING"}, "Script name cannot be empty")
            return {"CANCELLED"}
        if not name.endswith(".py"):
            name += ".py"
        full_path = os.path.join(prefs.custom_scripts_path, name)
        if os.path.exists(full_path):
            self.report({"WARNING"}, "File already exists")
            return {"CANCELLED"}
        with open(full_path, "w") as f:
            f.write("# AniMate Pro Custom Script\nimport bpy\n\n")
        text = bpy.data.texts.load(full_path)
        entry.script = name
        entry.text_block_name = text.name
        refresh_ui(context)
        self.report({"INFO"}, f"Created script {name}")
        return {"FINISHED"}


class AMP_OT_row_button_edit_script(Operator):
    """Open the assigned script in the Text Editor for editing.

    Finds an open Text Editor and loads the assigned script for editing.
    """

    bl_idname = "amp.row_button_edit_script"
    bl_label = "Edit Custom Script"
    bl_description = "Open the assigned script for editing"

    category_index: IntProperty()
    row_index: IntProperty()
    entry_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # Use explicit indices to navigate to the button entry
        # 1. Get the owner and its category collection
        owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)
        if not owner or not cat_coll:
            self.report({"ERROR"}, "Contextual owner or category collection not found.")
            return {"CANCELLED"}

        # 2. Get the specific category using self.category_index
        if not (0 <= self.category_index < len(cat_coll)):
            self.report({"ERROR"}, f"Category index {self.category_index} out of range.")
            return {"CANCELLED"}
        category = cat_coll[self.category_index]

        # 3. Get the specific row using self.row_index
        if not (hasattr(category, "rows") and 0 <= self.row_index < len(category.rows)):
            self.report({"ERROR"}, f"Row index {self.row_index} out of range for category '{category.name}'.")
            return {"CANCELLED"}
        row = category.rows[self.row_index]

        # 4. Get the specific button entry using self.entry_index
        if not (hasattr(row, "buttons") and 0 <= self.entry_index < len(row.buttons)):
            self.report({"ERROR"}, f"Button index {self.entry_index} out of range for row.")
            return {"CANCELLED"}
        entry = row.buttons[self.entry_index]

        # Get the text datablock
        text = bpy.data.texts.get(entry.text_block_name)
        if not text:
            self.report({"WARNING"}, "Text datablock not found")
            return {"CANCELLED"}

        # Open a new window with Text Editor workspace
        bpy.ops.wm.window_new("INVOKE_DEFAULT")

        # Get the new window (it should be the last one created)
        new_window = bpy.context.window_manager.windows[-1]

        # Set the workspace to Text Editing if it exists, otherwise use the current workspace
        try:
            # Try to switch to Text Editing workspace
            with bpy.context.temp_override(window=new_window):
                if "Text Editing" in bpy.data.workspaces:
                    bpy.context.window.workspace = bpy.data.workspaces["Text Editing"]
                else:
                    # If Text Editing workspace doesn't exist, create a text editor area
                    # Find the first area and set it to TEXT_EDITOR
                    for area in new_window.screen.areas:
                        area.type = "TEXT_EDITOR"
                        area.spaces.active.text = text
                        break
        except Exception:
            # Fallback: just try to find a text editor area in the new window
            for area in new_window.screen.areas:
                if area.type == "TEXT_EDITOR":
                    area.spaces.active.text = text
                    break
                elif area.type in ["VIEW_3D", "OUTLINER", "PROPERTIES"]:
                    # Convert any of these area types to text editor
                    area.type = "TEXT_EDITOR"
                    area.spaces.active.text = text
                    break

        # If we still haven't set the text, try the original method in the current window
        if not any(area.type == "TEXT_EDITOR" and area.spaces.active.text == text for area in new_window.screen.areas):
            # Fallback to original behavior in current window
            for area in context.screen.areas:
                if area.type == "TEXT_EDITOR":
                    area.spaces.active.text = text
                    self.report({"INFO"}, f"Editing script {entry.script} in current window")
                    return {"FINISHED"}

            self.report({"INFO"}, f"New window opened - please switch to Text Editor to edit {entry.script}")
        else:
            self.report({"INFO"}, f"Editing script {entry.script} in new window")

        return {"FINISHED"}


class AMP_OT_row_button_unassign_script(Operator):
    """Remove any script assignment from the custom-script button.

    Clears the script and text datablock assignments from the button.
    """

    bl_idname = "amp.row_button_unassign_script"
    bl_label = "Unassign Custom Script"
    bl_description = "Remove script assignment from this custom button"

    category_index: IntProperty()
    row_index: IntProperty()
    entry_index: IntProperty()
    data_owner_is_popup_panel: BoolProperty(default=False)
    data_owner_popup_panel_index: IntProperty(default=-1)

    def execute(self, context):
        # Use explicit indices to navigate to the button entry
        # 1. Get the owner and its category collection
        owner, cat_coll, _ = get_contextual_owner_collection_indices(context, self)
        if not owner or not cat_coll:
            self.report({"ERROR"}, "Contextual owner or category collection not found.")
            return {"CANCELLED"}

        # 2. Get the specific category using self.category_index
        if not (0 <= self.category_index < len(cat_coll)):
            self.report({"ERROR"}, f"Category index {self.category_index} out of range.")
            return {"CANCELLED"}
        category = cat_coll[self.category_index]

        # 3. Get the specific row using self.row_index
        if not (hasattr(category, "rows") and 0 <= self.row_index < len(category.rows)):
            self.report({"ERROR"}, f"Row index {self.row_index} out of range for category '{category.name}'.")
            return {"CANCELLED"}
        row = category.rows[self.row_index]

        # 4. Get the specific button entry using self.entry_index
        if not (hasattr(row, "buttons") and 0 <= self.entry_index < len(row.buttons)):
            self.report({"ERROR"}, f"Button index {self.entry_index} out of range for row.")
            return {"CANCELLED"}
        entry = row.buttons[self.entry_index]

        entry.script = ""
        entry.text_block_name = ""
        refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_restore_default_ui_content(Operator):
    """Restore default UI content (categories and/or pie menus) based on context.

    When called from main preferences, restores both categories and pie menus.
    When called from pie menu context, restores only pie menus.
    """

    bl_idname = "amp.restore_default_ui_content"
    bl_label = "Restore Default Content"
    bl_description = "Restore default categories and/or pie menus"

    # data_owner_is_popup_panel: BoolProperty(default=False)
    # data_owner_popup_panel_index: IntProperty(default=-1)

    skip_confirmation: BoolProperty(
        name="Skip Confirmation", description="Skip the confirmation dialog", default=False, options={"SKIP_SAVE"}
    )

    def invoke(self, context, event):
        """Show confirmation dialog before restoring defaults (unless skipped)"""
        if self.skip_confirmation:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        """Draw confirmation dialog"""
        layout = self.layout

        # Determine what we're restoring based on context
        # if self.data_owner_is_popup_panel:
        #     layout.label(text="Restore all default pie menus?")
        #     layout.label(text="This will remove all existing default pie menus", icon="INFO")
        #     layout.label(text="and reload them from the addon definitions.")
        #     layout.separator()
        #     layout.label(text="Custom pie menus will not be affected.", icon="CHECKMARK")
        # else:
        layout.label(text="Restore default categories and pie menus?")
        layout.label(text="This will remove all existing default categories", icon="INFO")
        layout.label(text="and pie menus, then reload them from the addon definitions.")
        layout.separator()
        layout.label(text="Custom categories and pie menus will not be affected.", icon="CHECKMARK")

    def execute(self, context):
        prefs = get_prefs()

        try:
            # if self.data_owner_is_popup_panel:
            #     # Context is pie menu - restore only pie menus
            #     from .addon_ui_helpers import _restore_popup_panels_only
            #     _restore_popup_panels_only(prefs)
            #     self.report({"INFO"}, "Default pie menus restored")
            # else:
            # Context is main preferences - restore both categories and pie menus
            from .addon_ui_helpers import _ensure_default_content_loaded

            _ensure_default_content_loaded(force_fresh_install=True)
            self.report({"INFO"}, "Default categories and pie menus restored")

            refresh_ui(context)
            return {"FINISHED"}

        except Exception as e:
            error_msg = f"Failed to restore default content: {str(e)}"
            print(f"[AMP] {error_msg}")
            self.report({"ERROR"}, error_msg)
            return {"CANCELLED"}


# -----------------------------------------------------------------------------
# Property Path Parser
# -----------------------------------------------------------------------------


def parse_operator_call(operator_call):
    """
    Parse an operator call string and return the operator name for display purposes.

    Returns:
        str: operator_name for display purposes, or None if invalid
    """
    if not operator_call or not operator_call.strip():
        return None

    try:
        # Remove bpy.ops. prefix if present
        call_str = operator_call.strip()
        if call_str.startswith("bpy.ops."):
            call_str = call_str[8:]

        # Find the operator name (everything before the first parenthesis)
        paren_pos = call_str.find("(")
        if paren_pos == -1:
            # No parentheses, just the operator name
            return call_str

        operator_name = call_str[:paren_pos]
        return operator_name

    except Exception:
        return None


def parse_button_path(button_path):
    """
    Parse a complex property path and return the data object and property info.

    Handles paths like:
    - bpy.context.scene.frame_current
    - bpy.data.objects["Cube"].location[0]
    - bpy.context.object.modifiers["Subdivision"].levels
    - prefs.anim_editors_visual_aids

    Returns:
        tuple: (data_object, property_name, index) or (None, None, None) if invalid
    """
    if not button_path:
        return None, None, None

    try:
        # Handle array indexing at the end
        array_index = None
        if button_path.endswith("]"):
            # Find the last opening bracket
            bracket_start = button_path.rfind("[")
            if bracket_start != -1:
                index_str = button_path[bracket_start + 1 : -1]
                try:
                    array_index = int(index_str)
                    button_path = button_path[:bracket_start]
                except ValueError:
                    # Not a valid integer index
                    pass

        # Split the path into parts, handling dictionary-style access
        parts = []
        current_part = ""
        in_brackets = False
        i = 0

        while i < len(button_path):
            char = button_path[i]

            if char == "[":
                in_brackets = True
                current_part += char
            elif char == "]":
                in_brackets = False
                current_part += char
            elif char == "." and not in_brackets:
                if current_part:
                    parts.append(current_part)
                    current_part = ""
            else:
                current_part += char

            i += 1

        if current_part:
            parts.append(current_part)

        if len(parts) < 2:
            return None, None, None

        # The last part is the property name
        property_name = parts[-1]

        # Everything else forms the data path
        data_path_parts = parts[:-1]

        # Build and evaluate the data path
        data_obj = None
        for i, part in enumerate(data_path_parts):
            if i == 0:
                # First part should be a module or context
                if part == "bpy":
                    data_obj = bpy
                elif part == "prefs":
                    # Handle addon preferences access like conditional evaluation
                    data_obj = get_prefs()
                else:
                    # Try to evaluate as is
                    try:
                        data_obj = eval(part)
                    except:
                        return None, None, None
            else:
                # Subsequent parts
                if "[" in part and "]" in part:
                    # Handle dictionary/collection access like objects["Cube"]
                    attr_name = part[: part.find("[")]
                    key_part = part[part.find("[") + 1 : part.rfind("]")]

                    # Remove quotes if present
                    if (key_part.startswith('"') and key_part.endswith('"')) or (
                        key_part.startswith("'") and key_part.endswith("'")
                    ):
                        key = key_part[1:-1]
                    else:
                        try:
                            key = int(key_part)
                        except ValueError:
                            key = key_part

                    try:
                        collection = getattr(data_obj, attr_name)
                        data_obj = collection[key]
                    except (AttributeError, KeyError, IndexError, TypeError):
                        return None, None, None
                else:
                    # Regular attribute access
                    try:
                        data_obj = getattr(data_obj, part)
                    except AttributeError:
                        return None, None, None

        return data_obj, property_name, array_index

    except Exception:
        return None, None, None


def find_popup_panel_context_for_button(category_index, row_index, button_index):
    """
    Helper function to find the popup panel context for a button at the given indices.
    Returns (popup_panel_index, adjusted_category_index) or (None, None) if not found in popup panels.
    """
    prefs = get_prefs()

    # Search through all popup panels
    for pp_idx, popup_panel in enumerate(prefs.popup_panels):
        if 0 <= category_index < len(popup_panel.categories):
            category = popup_panel.categories[category_index]
            if hasattr(category, "rows") and 0 <= row_index < len(category.rows):
                row = category.rows[row_index]
                if hasattr(row, "buttons") and 0 <= button_index < len(row.buttons):
                    # Found the button in this popup panel
                    return pp_idx, category_index

    return None, None


class AMP_OT_show_panel_popup(Operator):
    """Show a panel in a popup window.

    Creates a popup window that displays the content of the specified panel
    using the panel registry system.
    """

    bl_idname = "amp.show_panel_popup"
    bl_label = "Show Panel Popup"
    bl_description = "Show a panel in a popup window"

    panel_id: StringProperty(name="Panel ID", description="ID of the panel to show in popup", default="")
    custom_panel: StringProperty(
        name="Custom Panel Class", description="Blender panel class name for custom panels", default=""
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=400)

    def draw(self, context):
        layout = self.layout

        # Handle custom panels first
        if self.custom_panel:
            if hasattr(bpy.types, self.custom_panel):
                panel_class = getattr(bpy.types, self.custom_panel)
                if hasattr(panel_class, "draw"):
                    # Create a mock panel object for compatibility
                    mock_panel = type("MockPanel", (), {"layout": layout})()
                    try:
                        panel_class.draw(mock_panel, context)
                    except Exception as e:
                        error_row = layout.row()
                        error_row.alert = True
                        error_row.label(text=f"Panel error: {str(e)[:50]}...", icon="ERROR")
                else:
                    error_row = layout.row()
                    error_row.alert = True
                    error_row.label(text=f"{self.custom_panel} has no draw method", icon="ERROR")
            else:
                error_row = layout.row()
                error_row.alert = True
                error_row.label(text=f"Panel '{self.custom_panel}' not found", icon="ERROR")
            return

        # Get panel function from panel registry for regular panels
        if self.panel_id:
            try:
                from . import addon_ui_definitions_panels

                panel_func = getattr(addon_ui_definitions_panels, self.panel_id, None)
                if panel_func and callable(panel_func):
                    try:
                        panel_func(layout, context)
                    except Exception as e:
                        error_row = layout.row()
                        error_row.alert = True
                        error_row.label(text=f"Panel error: {str(e)[:50]}...", icon="ERROR")
                else:
                    layout.label(text=f"Panel '{self.panel_id}' not found", icon="ERROR")
            except ImportError:
                layout.label(text="Panel definitions not available", icon="ERROR")
        else:
            layout.label(text="No panel specified", icon="INFO")

    def execute(self, context):
        return {"FINISHED"}


classes = (
    AMP_OT_category_add,
    AMP_OT_category_move_up,
    AMP_OT_category_move_down,
    AMP_OT_category_copy,
    AMP_OT_category_paste,
    AMP_OT_category_select,
    AMP_OT_row_add_section,
    AMP_OT_row_add_button,
    AMP_OT_row_add_panel,
    AMP_OT_row_move_up,
    AMP_OT_row_move_down,
    AMP_OT_row_copy,
    AMP_OT_row_paste,
    AMP_OT_section_move_up,
    AMP_OT_section_move_down,
    AMP_OT_section_copy,
    AMP_OT_section_paste,
    AMP_OT_section_delete,
    AMP_OT_row_button_copy,
    AMP_OT_row_button_paste,
    AMP_OT_category_delete,
    AMP_OT_row_delete,
    AMP_OT_row_panel_add,
    AMP_OT_row_panel_add_exec,
    AMP_OT_row_button_add,
    AMP_OT_row_button_add_exec,
    AMP_OT_row_button_entry_delete,
    AMP_OT_row_button_entry_move_up,
    AMP_OT_row_button_entry_move_down,
    AMP_OT_row_button_add_script,
    AMP_OT_execute_operator_string,
    AMP_OT_execute_custom_script,
    AMP_OT_row_button_assign_script,
    AMP_OT_row_button_create_script,
    AMP_OT_row_button_edit_script,
    AMP_OT_row_button_unassign_script,
    AMP_OT_row_button_add_spacer,
    AMP_OT_row_button_add_property,
    AMP_OT_row_button_add_operator,
    AMP_OT_category_duplicate,
    AMP_OT_row_duplicate,
    AMP_OT_row_button_entry_duplicate,
    AMP_OT_category_restore_default,
    AMP_OT_restore_default_ui_content,
    AMP_OT_row_edit_conditional,
    AMP_OT_show_panel_popup,
)


def register():

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass


def unregister():

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
