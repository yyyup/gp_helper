import bpy
import os
import inspect
import json
import re
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
from .addon_ui_operators import parse_button_path, parse_operator_call
from .addon_ui_helpers import (
    get_collapse_icon,
)
from .addon_ui_helpers import (
    get_collapse_icon,
    draw_ui_section,
)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _evaluate_row_conditional(row_item, context, cat):
    """Safely evaluate a row's conditional expression.

    Args:
        row_item: The RowGroup item to check
        context: The Blender context
        cat: The category containing the row (for error reporting)

    Returns:
        bool: True if the row should be shown, False if hidden
    """
    if not row_item.conditional or not row_item.conditional.strip():
        return True

    try:
        # First, let's try to validate the syntax before evaluation
        conditional_expr = row_item.conditional.strip()

        # Try to compile the expression first to catch syntax errors early
        try:
            compile(conditional_expr, "<conditional>", "eval")
        except SyntaxError as syntax_err:
            error_msg = f"[AMP] Conditional syntax error in category '{cat.name}', row '{row_item.name}': {syntax_err}"
            print(error_msg)
            print(f"[AMP] Expression: {conditional_expr}")
            return True  # Show on syntax error to avoid breaking UI

        # Create a comprehensive safe evaluation environment
        safe_builtins = {
            "getattr": getattr,
            "hasattr": hasattr,
            "isinstance": isinstance,
            "len": len,
            "bool": bool,
            "str": str,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "None": None,
            "True": True,
            "False": False,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "any": any,
            "all": all,
        }

        # Create comprehensive evaluation globals
        eval_globals = {"bpy": bpy, "context": context, "__builtins__": safe_builtins}

        # If the conditional contains 'prefs.', inject the addon preferences
        if "prefs." in conditional_expr:
            eval_globals["prefs"] = get_prefs()

        # Add panel validation function for use in conditionals
        try:
            from . import addon_ui_definitions_panels

            eval_globals["validate_external_panel_exists"] = addon_ui_definitions_panels.validate_external_panel_exists
        except ImportError:
            pass

        # Add some commonly used helper functions for conditionals
        def safe_get_nested_attr(obj, attr_path, default=None):
            """Safely get nested attributes using dot notation, returning default if any step fails."""
            if obj is None:
                return default
            try:
                for attr in attr_path.split("."):
                    obj = getattr(obj, attr, None)
                    if obj is None:
                        return default
                return obj
            except (AttributeError, TypeError):
                return default

        def has_addon(addon_name):
            """Check if an addon is enabled."""
            try:
                return addon_name in bpy.context.preferences.addons
            except:
                return False

        def object_has_attr_chain(obj, *attr_names):
            """Check if object has a chain of attributes (e.g., obj.als.turn_on)"""
            if obj is None:
                return False
            current = obj
            for attr_name in attr_names:
                if not hasattr(current, attr_name):
                    return False
                current = getattr(current, attr_name)
                if current is None:
                    return False
            return True

        # Add helper functions to evaluation environment
        eval_globals.update(
            {
                "safe_get_nested_attr": safe_get_nested_attr,
                "has_addon": has_addon,
                "object_has_attr_chain": object_has_attr_chain,
            }
        )

        # Evaluate the expression
        result = eval(conditional_expr, eval_globals)
        return bool(result)

    except Exception as e:
        # Enhanced error reporting with more context
        error_msg = f"[AMP] Conditional evaluation error in category '{cat.name}', row '{row_item.name}': {e}"
        print(error_msg)
        print(f"[AMP] Expression: {row_item.conditional}")
        print(f"[AMP] Error type: {type(e).__name__}")

        # Return True (show) on error to avoid breaking the UI
        return True


def _is_row_visible(row_item, context, cat, top_panel=False):
    """Check if a row would be visible considering all display conditions.

    Args:
        row_item: The RowGroup item to check
        context: The Blender context
        cat: The category containing the row
        top_panel: Whether this is for a top panel (affects display_top check)

    Returns:
        bool: True if the row would be visible, False otherwise
    """
    # Check conditional expression first
    # if not _evaluate_row_conditional(row_item, context, cat):
    #     return False

    # Panels that don’t exist should never be visible
    if row_item.row_type == "PANEL" and not _validate_panel_exists(row_item):
        return False

    # Check conditional expression first
    if not _evaluate_row_conditional(row_item, context, cat):
        return False

    # Check display settings based on panel type
    if top_panel and not row_item.display_top:
        return False
    if not top_panel and not row_item.display_side:
        return False

    return True


# -----------------------------------------------------------------------------
# UILists
# -----------------------------------------------------------------------------


class AMP_UL_Categories(UIList):
    def draw_item(self, context, layout, _data, item, _icon, active_data, active_propname, index):
        item_container = layout.column()
        is_default = False if item.default_cat_id != "" else True
        # Check if all pins are False to determine if category should appear inactive
        all_pins_false = not any(
            [
                item.top_nla_pin,
                item.top_graph_pin,
                item.top_dope_pin,
                item.side_nla_pin,
                item.side_graph_pin,
                item.side_dope_pin,
                item.side_view_pin,
            ]
        )

        # Set inactive appearance if all pins are false
        if all_pins_false:
            item_container.active = False

        row_split = item_container.split(factor=0.66, align=True)
        row_cat = row_split.row(align=True)

        # radio selector
        active_idx = getattr(active_data, active_propname)
        row_cat.label(text="", icon="LAYER_ACTIVE" if index == active_idx else "LAYER_USED")

        # display pins properties
        row_cat.prop(item, "properties", text="", icon="TRIA_DOWN" if item.properties else "SETTINGS", emboss=True)

        # icon-picker for category
        icon_args = get_icon(item.icon) if item.icon else {"icon": "RADIOBUT_OFF"}

        op_icon = row_cat.row().operator("amp.icon_selector", text="", **icon_args, emboss=True)
        # 'active_data' is the owner (prefs or PieMenuGroup)
        # 'index' is the category_index within that owner's collection
        set_operator_context(op_icon, active_data)  # Sets data_owner_is_popup_panel and data_owner_popup_panel_index
        op_icon.prop_name = "icon"
        op_icon.category_index = index
        op_icon.row_index = -1  # Explicitly set for category icon
        op_icon.entry_index = -1  # Explicitly set for category icon

        # name & delete - make name non-embeded for default categories
        name_emboss = not bool(item.default_cat_id)  # False for default categories, True for custom
        row_cat.row().prop(item, "name", text="", emboss=name_emboss)

        row_props = row_split.row(align=True)

        # Check if we're in popup panel context - if so, hide global pin control
        # We can determine this by checking if the active_data has a 'categories' attribute (popup panel)
        # vs 'ui_categories' attribute (main preferences)
        is_pie_menu_context = hasattr(active_data, "categories")

        # Global pin control - only show for normal categories, not popup panels
        if not is_pie_menu_context:
            row_props.row().prop(
                item, "pin_global", text="", icon="PINNED" if item.pin_global else "UNPINNED", emboss=True
            )

        cat_title_row = row_props.row(align=True)
        cat_title_row.enabled = is_default
        cat_title_row.row().prop(item, "show", text="")

        # row_props.separator(factor=0.5)

        delete_row = row_props.row().row(align=True)
        # delete_row.alert = True

        # Delete button for custom categories only
        if not item.default_cat_id:
            op = delete_row.row().operator("amp.category_delete", text="", icon="TRASH", emboss=True)
            set_operator_context(op, active_data)  # <— ensure delete applies to popup panel too
            op.index = index

        # only show the pin extra row if there is more than one category
        if item.properties:
            properties_col = item_container.column()
            properties_col.enabled = is_default

            properties_row = properties_col.row(align=True)
            properties_row.label(text="", icon="BLANK1")
            properties_row.label(text="", icon="BLANK1")

            properties_container = properties_row.box()
            properties_container.use_property_split = True
            properties_container.use_property_decorate = False

            # Check if we're in popup panel context - if so, hide the individual pin controls
            # We can determine this by checking if the active_data has a 'categories' attribute (popup panel)
            # vs 'ui_categories' attribute (main preferences)
            is_pie_menu_context = hasattr(active_data, "categories")

            if not is_pie_menu_context:
                pin_container = properties_container.column()

                pin_split = pin_container.split(factor=0.4, align=True)

                pins_label = pin_split.row(align=True)
                pins_label.alignment = "RIGHT"
                pins_label.label(text="Pins")

                pins_subrow = pin_split.row(align=True)

                pins_subrow.label(text="", icon="TOPBAR")
                pins_subrow.row().prop(item, "top_nla_pin", text="", **get_icon("NLA"), emboss=True)
                pins_subrow.row().prop(item, "top_graph_pin", text="", **get_icon("GRAPH"), emboss=True)
                pins_subrow.row().prop(item, "top_dope_pin", text="", **get_icon("ACTION"), emboss=True)

                pins_subrow.separator()

                pins_subrow.label(text="", icon="MENU_PANEL")
                pins_subrow.row().prop(item, "side_nla_pin", text="", **get_icon("NLA"), emboss=True)
                pins_subrow.row().prop(item, "side_graph_pin", text="", **get_icon("GRAPH"), emboss=True)
                pins_subrow.row().prop(item, "side_dope_pin", text="", **get_icon("ACTION"), emboss=True)
                pins_subrow.row().prop(item, "side_view_pin", text="", **get_icon("VIEW3D"), emboss=True)

            style_row = properties_container.row(align=True)

            style_row.prop(item, "style", text="Category Style", emboss=True)

            properties_container.row().prop(item, "indent", text="Items Indent", slider=True, emboss=True)

            properties_container.row().prop(
                item, "section_separator", text="Section Separator", slider=True, emboss=True
            )

            properties_container.row().prop(item, "cat_sections_collapse_style", text="Collapse Style")
            properties_container.row().prop(item, "cat_sections_icon_as_toggle", text="Icon as Toggle")

            properties_container.separator()

        item_container.separator(factor=0.25)


class AMP_UL_Rows(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        item_container = layout.column()
        row_split = item_container.split(factor=0.66, align=True)
        row_first = row_split.row(align=True)

        # radio selector
        active_idx = getattr(active_data, active_propname)

        if item.row_type == "SECTION":
            if item.is_subsection:
                # Indent for subsection visual cue, if desired
                sub_indent = row_first.row(align=True)
                sub_indent.label(text="", icon="BLANK1")

            row_first.label(text="", icon="LAYER_ACTIVE" if index == active_idx else "LAYER_USED")

            # icon-picker for section/subsection
            default_icon = get_collapse_icon(False, category=None)  # Use collapsed state as default for sections
            icon_args = get_icon(item.icon) if item.icon not in {"NONE", "BLANK1", ""} else {"icon": default_icon}
            op_icon = row_first.operator("amp.icon_selector", text="", **icon_args, emboss=True)

            # Context setting for op_icon (section icon)
            # 'active_data' is the category (cat_obj). 'index' is the row_index.
            # We need to find the owner of 'active_data' and 'active_data's index within that owner.
            prefs_instance = get_prefs()
            owner_obj_for_icon_op = None
            cat_idx_for_icon_op = -1

            try:
                # Check if active_data (the category) is in prefs.ui_categories
                cat_idx_for_icon_op = list(prefs_instance.ui_categories).index(active_data)
                owner_obj_for_icon_op = prefs_instance
            except ValueError:
                # Not in prefs.ui_categories, check popup_panels
                for pm_idx, pm in enumerate(prefs_instance.popup_panels):
                    try:
                        cat_idx_for_icon_op = list(pm.categories).index(active_data)
                        owner_obj_for_icon_op = pm
                        break
                    except ValueError:
                        continue

            if owner_obj_for_icon_op and cat_idx_for_icon_op != -1:
                set_operator_context(op_icon, owner_obj_for_icon_op)
                op_icon.category_index = cat_idx_for_icon_op
            else:
                # Fallback: This case should ideally not be reached if UI is structured correctly.
                # Default to global active category if owner cannot be determined.
                set_operator_context(op_icon, prefs_instance)  # Fallback owner
                op_icon.category_index = prefs_instance.active_category_index  # Fallback category index

            op_icon.prop_name = "icon"
            op_icon.row_index = index  # 'index' is the current row's index in active_data.rows
            op_icon.entry_index = -1  # Explicitly set for section row icon

            row_first.row().prop(item, "name", text="", emboss=True)

            add_delete = row_split.row(align=True)

            add_delete.row().prop(item, "style", text="", emboss=True, icon_only=True)

            # Check if we're in popup panel context - if so, hide display_top and display_side controls
            # We determine this by checking the active_data (category) owner's attributes
            is_pie_menu_context = False
            try:
                # Try to find if this category belongs to a popup panel by checking its parent
                prefs_instance = get_prefs()
                for pm in prefs_instance.popup_panels:
                    if active_data in pm.categories:
                        is_pie_menu_context = True
                        break
            except:
                pass

            if not is_pie_menu_context:
                add_delete.row().prop(item, "display_top", text="", icon="TOPBAR", emboss=True)
                add_delete.row().prop(item, "display_side", text="", icon="MENU_PANEL", emboss=True)

            add_delete.row().prop(
                item,
                "is_subsection",
                text="",
                toggle=True,
                icon="ALIGN_RIGHT" if item.is_subsection else "ALIGN_JUSTIFY",
            )

        elif item.row_type == "PANEL":
            if item.is_subsection:
                # Indent for subsection visual cue, if desired
                sub_indent = row_first.row(align=True)
                sub_indent.label(text="", icon="BLANK1")

            row_first.label(text="", icon="LAYER_ACTIVE" if index == active_idx else "LAYER_USED")

            # icon-picker for panel (same as section)
            default_icon = "RIGHTARROW"  # Default icon for panels
            icon_args = get_icon(item.icon) if item.icon not in {"NONE", "BLANK1", ""} else {"icon": default_icon}
            op_icon = row_first.operator("amp.icon_selector", text="", **icon_args, emboss=True)

            # Context setting for op_icon (panel icon) - same as section
            prefs_instance = get_prefs()
            owner_obj_for_icon_op = None
            cat_idx_for_icon_op = -1

            try:
                cat_idx_for_icon_op = list(prefs_instance.ui_categories).index(active_data)
                owner_obj_for_icon_op = prefs_instance
            except ValueError:
                for pm_idx, pm in enumerate(prefs_instance.popup_panels):
                    try:
                        cat_idx_for_icon_op = list(pm.categories).index(active_data)
                        owner_obj_for_icon_op = pm
                        break
                    except ValueError:
                        continue

            if owner_obj_for_icon_op and cat_idx_for_icon_op != -1:
                set_operator_context(op_icon, owner_obj_for_icon_op)
                op_icon.category_index = cat_idx_for_icon_op
            else:
                set_operator_context(op_icon, prefs_instance)
                op_icon.category_index = prefs_instance.active_category_index

            op_icon.prop_name = "icon"
            op_icon.row_index = index
            op_icon.entry_index = -1

            row_first.row().prop(item, "name", text="", emboss=True)

            add_delete = row_split.row(align=True)

            # Show style dropdown like sections
            add_delete.row().prop(item, "style", text="", emboss=True, icon_only=True)

            # Check if we're in popup panel context - if so, hide display_top and display_side controls
            # We determine this by checking the active_data (category) owner's attributes
            is_pie_menu_context = False
            try:
                # Try to find if this category belongs to a popup panel by checking its parent
                prefs_instance = get_prefs()
                for pm in prefs_instance.popup_panels:
                    if active_data in pm.categories:
                        is_pie_menu_context = True
                        break
            except:
                pass

            if not is_pie_menu_context:
                add_delete.row().prop(item, "display_top", text="", icon="TOPBAR", emboss=True)
                add_delete.row().prop(item, "display_side", text="", icon="MENU_PANEL", emboss=True)

            # Show subsection toggle like sections
            add_delete.row().prop(
                item,
                "is_subsection",
                text="",
                toggle=True,
                icon="ALIGN_RIGHT" if item.is_subsection else "ALIGN_JUSTIFY",
            )

        else:
            # Check if this button row is under a section/subsection
            prev_section = None
            for i in range(index - 1, -1, -1):
                sec = data.rows[i]
                if sec.row_type == "SECTION":
                    prev_section = sec
                    break

            # Only add indent if there's a previous section
            if prev_section:
                if prev_section.is_subsection:
                    row_first.label(text="", icon="BLANK1")
                row_first.label(text="", icon="BLANK1")

            row_first.label(text="", icon="LAYER_ACTIVE" if index == active_idx else "LAYER_USED")

            if item.buttons:
                btn_row = row_first.row(align=True)
                for btn in item.buttons:
                    if btn.button_id == "spacer":
                        sp = btn_row.row(align=True)
                        sp.scale_x = btn.spacer_width
                        # Only use BLANK1 icon if there's no text, otherwise display as a normal label
                        if btn.display_name and btn.display_name.strip():
                            sp.label(text=btn.display_name)
                        else:
                            sp.label(text="", icon="BLANK1")
                    elif btn.button_id == "property":
                        _draw_property_button(btn_row, btn)
                    elif btn.button_id == "operator":
                        _draw_operator_button(btn_row, btn)
                    else:
                        fn = getattr(addon_ui_definitions_button, btn.button_id, None)

                        # Also try forge buttons if the function isn't found in regular buttons
                        if not fn:
                            try:
                                from . import addon_ui_definitions_button_forge

                                fn = getattr(addon_ui_definitions_button_forge, btn.button_id, None)
                            except ImportError:
                                pass

                        if fn and callable(fn):
                            try:
                                fn(btn_row, context)
                            except Exception:
                                btn_row.label(text=btn.button_id)
                        else:
                            btn_row.label(text=btn.button_id)
            else:
                row_first.row().label(text="No buttons")

            add_delete = row_split.row(align=True)

            add_delete.row().prop(item, "alignment", text="", emboss=True, icon_only=True)

            # Check if we're in popup panel context - hide display controls for popup panels
            is_pie_menu_context = False
            try:
                # Try to find if this category belongs to a popup panel by checking its parent
                prefs_instance = get_prefs()
                for pm in prefs_instance.popup_panels:
                    if active_data in pm.categories:
                        is_pie_menu_context = True
                        break
            except:
                pass

            # Display control buttons for button rows - only show for normal categories
            if not is_pie_menu_context:
                add_delete.row().prop(item, "display_top", text="", icon="TOPBAR", emboss=True)
                add_delete.row().prop(item, "display_side", text="", icon="MENU_PANEL", emboss=True)

            # op refers to amp.row_button_add
            op = add_delete.row().operator("amp.row_button_add", text="", icon="PLUS", emboss=True)
            # op.row_index = index # Original line, still correct for the operator's own row_index property.

            # Set full context for amp.row_button_add
            prefs_instance = get_prefs()
            owner_obj_for_op = None
            cat_idx_for_op = -1

            # 'active_data' is the category. Find its owner and its index within that owner.
            try:
                cat_idx_for_op = list(prefs_instance.ui_categories).index(active_data)
                owner_obj_for_op = prefs_instance
            except ValueError:
                for pm_candidate in prefs_instance.popup_panels:
                    try:
                        cat_idx_for_op = list(pm_candidate.categories).index(active_data)
                        owner_obj_for_op = pm_candidate
                        break
                    except ValueError:
                        continue

            if owner_obj_for_op and cat_idx_for_op != -1:
                set_operator_context(op, owner_obj_for_op)
                op.category_index = cat_idx_for_op
            else:
                # Fallback if owner/category context can't be established
                # print(f"AMP_UL_Rows (row_button_add): Could not find owner for category '{active_data.name}'. Falling back.") # Optional debug
                set_operator_context(op, prefs_instance)
                op.category_index = prefs_instance.active_category_index

            op.row_index = index  # This operator specifically needs the target row index within the category.

        # Add conditional button for all row types - just before delete button
        conditional_icon = "RADIOBUT_ON" if item.conditional else "RADIOBUT_OFF"
        op_conditional = add_delete.row().operator(
            "amp.row_edit_conditional", text="", icon=conditional_icon, emboss=True
        )

        # Set context for conditional operator - same pattern as delete operator
        prefs_instance = get_prefs()
        owner_obj_for_conditional = None
        cat_idx_for_conditional = -1

        try:
            cat_idx_for_conditional = list(prefs_instance.ui_categories).index(active_data)
            owner_obj_for_conditional = prefs_instance
        except ValueError:
            for pm_candidate in prefs_instance.popup_panels:
                try:
                    cat_idx_for_conditional = list(pm_candidate.categories).index(active_data)
                    owner_obj_for_conditional = pm_candidate
                    break
                except ValueError:
                    continue

        if owner_obj_for_conditional and cat_idx_for_conditional != -1:
            set_operator_context(op_conditional, owner_obj_for_conditional)
            op_conditional.category_index = cat_idx_for_conditional
        else:
            set_operator_context(op_conditional, prefs_instance)
            op_conditional.category_index = prefs_instance.active_category_index

        op_conditional.row_index = index

        delete_row = add_delete.row(align=True)
        # delete_row.alert = True
        # op is now reassigned to amp.row_delete
        op = delete_row.row().operator("amp.row_delete", text="", icon="TRASH", emboss=True)

        # Context setting for amp.row_delete (from previous successful patch)
        # 'active_data' is the CategoryGroup object (e.g., UI_CategoryGroup or UI_PieMenusGroup)
        # 'index' is the index of the current row_item (item) within active_data.rows.
        prefs = get_prefs()  # Renamed to avoid conflict with outer scope prefs_instance if any confusion
        owner_obj_for_delete = None
        cat_idx_for_delete_op = -1

        try:
            # 'active_data' is the category. Find its index in prefs.ui_categories
            cat_idx_for_delete_op = list(prefs.ui_categories).index(active_data)
            owner_obj_for_delete = prefs
        except ValueError:
            # Not in prefs.ui_categories, check popup_panels
            for pm in prefs.popup_panels:
                try:
                    cat_idx_for_delete_op = list(pm.categories).index(active_data)
                    owner_obj_for_delete = pm
                    break
                except ValueError:
                    continue

        if owner_obj_for_delete and cat_idx_for_delete_op != -1:
            set_operator_context(op, owner_obj_for_delete)
            op.category_index = cat_idx_for_delete_op  # This is the category index for amp.row_delete
        else:
            # Fallback for amp.row_delete
            # print(f"AMP_UL_Rows (row_delete): Could not find owner for category '{active_data.name}'. Falling back.") # Optional debug
            set_operator_context(op, prefs)
            op.category_index = prefs.active_category_index

        op.index = index  # This is the row_index for deletion, relative to `active_data.rows`.

        item_container.separator(factor=0.5)


class AMP_UL_ButtonEntries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        item_container = layout.column()
        split = item_container.row().split(factor=0.5, align=True)
        row = split.row(align=True)
        active_idx = getattr(active_data, active_propname)
        row.label(text="", icon="LAYER_ACTIVE" if index == active_idx else "LAYER_USED")

        prefs = bpy.context.preferences.addons[base_package].preferences

        # Spacer preview + width slider
        if item.button_id == "spacer":
            preview = row.row(align=True)
            # preview.label(text="Spacer", icon="BLANK1")
            preview.row().prop(item, "display_name", text="" if item.display_name else "Spacer", emboss=True)

        elif item.button_id == "custom_script":
            chose_icon_op = row.row().operator("amp.icon_selector", text="", **get_icon(item.icon), emboss=True)

            # `active_data` is the row_obj (RowGroup instance)
            # `index` is the entry_index of `item` (ButtonEntry) within `active_data.buttons`
            prefs_instance = get_prefs()
            owner_obj_for_op = None
            cat_idx_for_op = -1
            row_idx_for_op = -1
            found_owner_and_indices = False

            # Find owner of `active_data` (the row)
            for c_idx, cat_candidate in enumerate(prefs_instance.ui_categories):
                if not hasattr(cat_candidate, "rows"):
                    continue
                try:
                    r_idx = list(cat_candidate.rows).index(active_data)
                    owner_obj_for_op = prefs_instance
                    cat_idx_for_op = c_idx
                    row_idx_for_op = r_idx
                    found_owner_and_indices = True
                    break
                except ValueError:
                    continue

            if not found_owner_and_indices:
                for pm_candidate in prefs_instance.popup_panels:
                    for c_idx, cat_candidate in enumerate(pm_candidate.categories):
                        if not hasattr(cat_candidate, "rows"):
                            continue
                        try:
                            r_idx = list(cat_candidate.rows).index(active_data)
                            owner_obj_for_op = pm_candidate
                            cat_idx_for_op = c_idx
                            row_idx_for_op = r_idx
                            found_owner_and_indices = True
                            break
                        except ValueError:
                            continue
                    if found_owner_and_indices:
                        break

            if owner_obj_for_op and cat_idx_for_op != -1 and row_idx_for_op != -1:
                set_operator_context(chose_icon_op, owner_obj_for_op)
                chose_icon_op.category_index = cat_idx_for_op
                chose_icon_op.row_index = row_idx_for_op
            else:  # Fallback
                set_operator_context(chose_icon_op, prefs_instance)
                # This fallback logic for indices might be imperfect but aims to provide some values.
                chose_icon_op.category_index = prefs_instance.active_category_index
                if 0 <= prefs_instance.active_category_index < len(prefs_instance.ui_categories):
                    current_cat = prefs_instance.ui_categories[prefs_instance.active_category_index]
                    chose_icon_op.row_index = current_cat.active_row_index
                else:
                    chose_icon_op.row_index = 0

            chose_icon_op.prop_name = "icon"
            chose_icon_op.entry_index = index  # 'index' is the button entry index

            row.row().prop(item, "display_name", text="Text", emboss=True)

        elif item.button_id == "property":
            chose_icon_op = row.row().operator("amp.icon_selector", text="", **get_icon(item.icon), emboss=True)

            # Use same context finding logic as custom_script
            prefs_instance = get_prefs()
            owner_obj_for_op = None
            cat_idx_for_op = -1
            row_idx_for_op = -1
            found_owner_and_indices = False

            # Find owner of `active_data` (the row)
            for c_idx, cat_candidate in enumerate(prefs_instance.ui_categories):
                if not hasattr(cat_candidate, "rows"):
                    continue
                try:
                    r_idx = list(cat_candidate.rows).index(active_data)
                    owner_obj_for_op = prefs_instance
                    cat_idx_for_op = c_idx
                    row_idx_for_op = r_idx
                    found_owner_and_indices = True
                    break
                except ValueError:
                    continue

            if not found_owner_and_indices:
                for pm_candidate in prefs_instance.popup_panels:
                    for c_idx, cat_candidate in enumerate(pm_candidate.categories):
                        if not hasattr(cat_candidate, "rows"):
                            continue
                        try:
                            r_idx = list(cat_candidate.rows).index(active_data)
                            owner_obj_for_op = pm_candidate
                            cat_idx_for_op = c_idx
                            row_idx_for_op = r_idx
                            found_owner_and_indices = True
                            break
                        except ValueError:
                            continue
                    if found_owner_and_indices:
                        break

            if owner_obj_for_op and cat_idx_for_op != -1 and row_idx_for_op != -1:
                set_operator_context(chose_icon_op, owner_obj_for_op)
                chose_icon_op.category_index = cat_idx_for_op
                chose_icon_op.row_index = row_idx_for_op

            else:  # Fallback
                set_operator_context(chose_icon_op, prefs_instance)
                chose_icon_op.category_index = prefs_instance.active_category_index
                if 0 <= prefs_instance.active_category_index < len(prefs_instance.ui_categories):
                    current_cat = prefs_instance.ui_categories[prefs_instance.active_category_index]
                    chose_icon_op.row_index = current_cat.active_row_index
                else:
                    chose_icon_op.row_index = 0

            chose_icon_op.prop_name = "icon"
            chose_icon_op.entry_index = index

            row.row().prop(item, "display_name", text="Text", emboss=True)

        elif item.button_id == "operator":
            chose_icon_op = row.row().operator("amp.icon_selector", text="", **get_icon(item.icon), emboss=True)

            # Use same context finding logic as property
            prefs_instance = get_prefs()
            owner_obj_for_op = None
            cat_idx_for_op = -1
            row_idx_for_op = -1
            found_owner_and_indices = False

            # Find owner of `active_data` (the row)
            for c_idx, cat_candidate in enumerate(prefs_instance.ui_categories):
                if not hasattr(cat_candidate, "rows"):
                    continue
                try:
                    r_idx = list(cat_candidate.rows).index(active_data)
                    owner_obj_for_op = prefs_instance
                    cat_idx_for_op = c_idx
                    row_idx_for_op = r_idx
                    found_owner_and_indices = True
                    break
                except ValueError:
                    continue

            if not found_owner_and_indices:
                for pm_candidate in prefs_instance.popup_panels:
                    for c_idx, cat_candidate in enumerate(pm_candidate.categories):
                        if not hasattr(cat_candidate, "rows"):
                            continue
                        try:
                            r_idx = list(cat_candidate.rows).index(active_data)
                            owner_obj_for_op = pm_candidate
                            cat_idx_for_op = c_idx
                            row_idx_for_op = r_idx
                            found_owner_and_indices = True
                            break
                        except ValueError:
                            continue
                    if found_owner_and_indices:
                        break

            if owner_obj_for_op and cat_idx_for_op != -1 and row_idx_for_op != -1:
                set_operator_context(chose_icon_op, owner_obj_for_op)
                chose_icon_op.category_index = cat_idx_for_op
                chose_icon_op.row_index = row_idx_for_op
            else:  # Fallback
                set_operator_context(chose_icon_op, prefs_instance)
                chose_icon_op.category_index = prefs_instance.active_category_index
                if 0 <= prefs_instance.active_category_index < len(prefs_instance.ui_categories):
                    current_cat = prefs_instance.ui_categories[prefs_instance.active_category_index]
                    chose_icon_op.row_index = current_cat.active_row_index
                else:
                    chose_icon_op.row_index = 0

            chose_icon_op.prop_name = "icon"
            chose_icon_op.entry_index = index

            row.row().prop(item, "display_name", text="Text", emboss=True)

        second_row = split.row(align=True)

        fn = getattr(addon_ui_definitions_button, item.button_id, None)

        # Also try forge buttons if the function isn't found in regular buttons
        if not fn:
            try:
                from . import addon_ui_definitions_button_forge

                fn = getattr(addon_ui_definitions_button_forge, item.button_id, None)
            except ImportError:
                pass

        if fn and callable(fn) and len(inspect.signature(fn).parameters) == 2:
            btn_row = row.row(align=True)
            btn_row.alignment = "LEFT"

            fn(btn_row, context)
            second_row.label(text=item.name)

        elif item.button_id == "custom_script":
            # second_row.prop(item, "name", text="", emboss=True)
            _draw_custom_script_buttons(second_row, prefs, context, item, index, compact=True, active_data=active_data)

        elif item.button_id == "property":
            # Always show property configuration instead of preview
            path_row = second_row.row(align=True)
            path_row.prop(item, "button_path", text="")
            path_row.prop(item, "property_slider", text="", icon="DRIVER" if item.property_slider else "PROPERTIES")

        elif item.button_id == "operator":
            path_row = second_row.row(align=True)
            path_row.prop(item, "button_path", text="")

        else:
            second_row.row().prop(item, "spacer_width", text="Width", emboss=True, slider=True)

        # delete button entry
        del_col = second_row.row().row(align=True)
        # del_col.alert = True
        op_del = del_col.operator("amp.row_button_entry_delete", text="", icon="TRASH", emboss=True)

        # `active_data` is the row_obj (RowGroup instance, e.g., sel_row)
        # `index` is the index of `item` (ButtonEntry) within `active_data.buttons`

        prefs_instance = get_prefs()
        owner_obj_for_op = None
        cat_idx_for_op = -1
        row_idx_for_op = -1
        found_owner_and_indices = False

        # Try to find `active_data` (the row) in prefs.ui_categories' rows
        for c_idx, cat_candidate in enumerate(prefs_instance.ui_categories):
            if not hasattr(cat_candidate, "rows"):
                continue
            try:
                r_idx = list(cat_candidate.rows).index(active_data)
                owner_obj_for_op = prefs_instance
                cat_idx_for_op = c_idx
                row_idx_for_op = r_idx
                found_owner_and_indices = True
                break
            except ValueError:
                continue

        if not found_owner_and_indices:
            # Try to find `active_data` (the row) in popup_panels' categories' rows
            for pm_candidate in prefs_instance.popup_panels:
                for c_idx, cat_candidate in enumerate(pm_candidate.categories):
                    if not hasattr(cat_candidate, "rows"):
                        continue
                    try:
                        r_idx = list(cat_candidate.rows).index(active_data)
                        owner_obj_for_op = pm_candidate
                        cat_idx_for_op = c_idx
                        row_idx_for_op = r_idx
                        found_owner_and_indices = True
                        break
                    except ValueError:
                        continue
                if found_owner_and_indices:
                    break

        if owner_obj_for_op and cat_idx_for_op != -1 and row_idx_for_op != -1:
            set_operator_context(op_del, owner_obj_for_op)
            op_del.category_index = cat_idx_for_op
            op_del.row_index = row_idx_for_op
        else:
            # Fallback: This path being taken would explain data_owner_is_popup_panel=False
            # print(f"AMP_UL_ButtonEntries: Could not find owner/indices for row. Falling back.") # Optional debug
            set_operator_context(op_del, prefs_instance)
            current_prefs_cat_idx = prefs_instance.active_category_index
            op_del.category_index = current_prefs_cat_idx
            if 0 <= current_prefs_cat_idx < len(prefs_instance.ui_categories):
                current_cat = prefs_instance.ui_categories[current_prefs_cat_idx]
                op_del.row_index = current_cat.active_row_index
            else:
                op_del.row_index = 0

        op_del.entry_index = index  # This is the button_entry index for deletion

        item_container.separator(factor=0.25)


# -----------------------------------------------------------------------------
# UIList for Popup Panels
# -----------------------------------------------------------------------------


class AMP_UL_PopupPanelBranches(AMP_UL_Categories, UIList):
    """Pie-menu branches list—uses pie‐menu’s own active_category_index."""

    # inherits draw_item and styling from AMP_UL_Categories


def _get_all_categories(prefs):
    """Get all categories including forge categories if enabled"""
    categories = list(prefs.ui_categories)

    # Add forge categories at the beginning if forge_version is enabled
    if is_forge_version():
        try:
            # Import forge categories if available
            from . import addon_ui_definitions_panels_forge
            from . import addon_ui_definitions_button_forge

            # Create a special forge category if it doesn't exist
            # This would be handled by the preferences system in a real implementation
            # For now, just add the existing categories that are marked as forge
            pass
        except ImportError:
            # Forge modules not available
            pass

    return categories


def _category_should_draw(cat, prefs, region_key, top_panel=False):
    # use new pin flags per area

    # Check if category is globally pinned - if not, don't draw at all
    pin_global = getattr(cat, "pin_global", False)

    if not pin_global:
        return False

    pinned = [c for c in prefs.ui_categories if getattr(c, f"{region_key}_pin")]
    active = getattr(cat, f"{region_key}_active", False)

    if not prefs.top_bars_use_categories and top_panel:
        return True

    elif len(pinned) >= 1:
        return getattr(cat, f"{region_key}_pin") and active

    else:
        return False  # If no categories are pinned, don't draw any


def draw_top_panel_ui(context, layout, region_key):
    prefs = get_prefs()

    if not prefs.addon_up_to_date:
        layout.operator(
            "amp.open_preferences_fullscreen",
            text="Finish AniMatePro Update",
            icon="PREFERENCES",
        )
        return

    # Early return if UI should be hidden during playback
    if prefs.hide_ui_during_playback and (context.screen.is_animation_playing or prefs.is_scrubbing):
        return

    col_content = _setup_layout_for_normal_ui(prefs, layout, region_key, context, top_panel=True)

    for cat in _get_all_categories(prefs):
        if not _category_should_draw(cat, prefs, region_key, top_panel=True):
            continue

        _draw_rows_for_category(context, cat, col_content, region_key, prefs, top_panel=True)


def draw_side_panel_ui(context, layout, region_key):
    prefs = get_prefs()

    if not prefs.addon_up_to_date:
        layout.operator(
            "amp.open_preferences_fullscreen",
            text="Finish AniMatePro Update",
            icon="PREFERENCES",
        )
        return

    # Early return if UI should be hidden during playback
    if prefs.hide_ui_during_playback and context.screen.is_animation_playing:
        return

    col_content = _setup_layout_for_normal_ui(prefs, layout, region_key, context)

    # Get a consistent separator value for inter-category spacing
    # Use the first visible category's separator or a default value
    inter_category_separator = 1.0  # Default value
    for cat in _get_all_categories(prefs):
        if _category_should_draw(cat, prefs, region_key):
            inter_category_separator = cat.section_separator
            break

    first_visible_category = True
    for cat in _get_all_categories(prefs):
        if not _category_should_draw(cat, prefs, region_key):
            continue

        # Add spacer before category (except the first visible one)
        if not first_visible_category and col_content:
            col_content.separator(factor=inter_category_separator)
        first_visible_category = False

        _draw_rows_for_category(context, cat, col_content, region_key, prefs)


def _setup_layout_for_normal_ui(prefs, layout, region_key, context, top_panel=False):

    # Filter categories that are globally pinned AND have region-specific pins
    pinned = [
        cat
        for cat in _get_all_categories(prefs)
        if getattr(cat, "pin_global", False) and getattr(cat, f"{region_key}_pin")
    ]

    # For side panels, only show category icons if there are multiple pinned categories
    if not top_panel and len(pinned) <= 1:
        return layout

    # For top panels, always show category icons if categories are enabled and there are pinned categories
    # For side panels, only show if there are multiple pinned categories
    show_category_icons = (top_panel and pinned and prefs.top_bars_use_categories) or (
        not top_panel and len(pinned) > 1
    )

    open = [
        cat
        for cat in _get_all_categories(prefs)
        if getattr(cat, "pin_global", False)
        and getattr(cat, f"{region_key}_pin")
        and getattr(cat, f"{region_key}_active", False)
    ]

    # For top panels, use existing layout logic
    if top_panel:
        row = layout.row(align=False)

        if show_category_icons:
            col_pins = row.row(align=True)
            col_pins.scale_x = 1
            col_pins.scale_y = 1

            for cat in pinned:
                icon_args = get_icon(cat.icon) if cat.icon else {"icon": "RADIOBUT_OFF"}

                # Create the toggle button row
                btn_row = col_pins.row()
                btn_row.active = getattr(cat, f"{region_key}_active", False)

                if isinstance(icon_args, dict):
                    btn_row.prop(cat, f"{region_key}_active", text="", **icon_args, emboss=True)
                else:
                    btn_row.prop(cat, f"{region_key}_active", text="", icon=icon_args, emboss=True)

        if prefs.sections_box_container and open:
            category_box = row.row(align=True)
            category_container_box = category_box.row(align=True)
            return category_container_box
        else:
            category_container = row.row(align=True)
            return category_container

    # For side panels, handle different category placements
    else:
        # Determine the layout structure based on cat_placement
        if prefs.cat_placement in ("TOP"):
            # Categories at top: column layout with categories above content
            main_col = layout.column(align=prefs.sections_box_container)

            if show_category_icons:
                # Calculate how many categories can fit per row based on region width
                region_width = context.region.width / context.preferences.view.ui_scale
                # Base width of 38 pixels works well for scale 1.2, adjust proportionally
                scaled_button_width = 28 * prefs.cat_scale
                categories_per_row = max(1, int(region_width // scaled_button_width))

                # Create category icons container at the top
                if prefs.cat_box_container:
                    cat_outer = main_col.box()
                else:
                    cat_outer = main_col

                # For row layout, create multiple rows as needed
                for i in range(0, len(pinned), categories_per_row):
                    cat_pre_row = cat_outer.row()
                    cat_pre_row.alignment = "CENTER"
                    cat_row = cat_pre_row.row()
                    cat_row.scale_x = prefs.cat_scale
                    cat_row.scale_y = prefs.cat_scale

                    # Add categories to this row
                    row_categories = pinned[i : i + categories_per_row]
                    for cat in row_categories:
                        icon_args = get_icon(cat.icon) if cat.icon else {"icon": "RADIOBUT_OFF"}

                        if isinstance(icon_args, dict):
                            cat_row.prop(cat, f"{region_key}_active", text="", **icon_args, emboss=True)
                        else:
                            cat_row.prop(cat, f"{region_key}_active", text="", icon=icon_args, emboss=True)

            # Return content area below categories
            if prefs.sections_box_container and open:
                category_container_box = main_col.box().column()
                return category_container_box
            else:
                return main_col.column()

        else:
            # LEFT or RIGHT placement: horizontal layout
            row = layout.row(align=prefs.sections_box_container)

            if show_category_icons:
                # For LEFT: categories first, then content
                # For RIGHT: content first, then categories
                if prefs.cat_placement == "LEFT":
                    if prefs.cat_box_container:
                        cat_outer = row.box()
                        col_pins = cat_outer.column()
                    else:
                        col_pins = row.column()

                    col_pins.scale_x = prefs.cat_scale
                    col_pins.scale_y = prefs.cat_scale

                    for cat in pinned:
                        icon_args = get_icon(cat.icon) if cat.icon else {"icon": "RADIOBUT_OFF"}

                        if isinstance(icon_args, dict):
                            col_pins.prop(cat, f"{region_key}_active", text="", **icon_args, emboss=True)
                        else:
                            col_pins.prop(cat, f"{region_key}_active", text="", icon=icon_args, emboss=True)

                    # Content area after categories (for LEFT)
                    if prefs.sections_box_container and open:
                        category_box = row.box()
                        category_container_box = category_box.column()
                        return category_container_box
                    else:
                        category_container = row.column()
                        return category_container

                else:  # RIGHT placement
                    # Content area first (for RIGHT)
                    if prefs.sections_box_container and open:
                        category_box = row.box()
                        category_container_box = category_box.column()
                        content_area = category_container_box
                    else:
                        category_container = row.column()
                        content_area = category_container

                    # Categories after content (for RIGHT)
                    if prefs.cat_box_container:
                        cat_outer = row.box()
                        col_pins = cat_outer.column()
                    else:
                        col_pins = row.column()

                    col_pins.scale_x = prefs.cat_scale
                    col_pins.scale_y = prefs.cat_scale

                    for cat in pinned:
                        icon_args = get_icon(cat.icon) if cat.icon else {"icon": "RADIOBUT_OFF"}

                        if isinstance(icon_args, dict):
                            col_pins.prop(cat, f"{region_key}_active", text="", **icon_args, emboss=True)
                        else:
                            col_pins.prop(cat, f"{region_key}_active", text="", icon=icon_args, emboss=True)

                    return content_area

            else:
                # No category icons to show, just return content area
                if prefs.sections_box_container and open:
                    category_box = row.box()
                    category_container_box = category_box.column()
                    return category_container_box
                else:
                    category_container = row.column()
                    return category_container


def _draw_rows_for_category(context, cat, col_content, region_key, prefs, top_panel=False):
    section_state = {"open": True, "box": None}
    subsection_state = {"open": True, "box": None}
    col_content.alignment = "LEFT" if top_panel else "EXPAND"

    # skip if hidden
    show_title = not top_panel and ((cat.show == "ALWAYS") or (cat.show == "GLOBAL" and prefs.cat_headers))

    if region_key == "popup":
        col_content = col_content.box()

    if not prefs.top_bars_use_categories and top_panel:
        content_area = col_content.row(align=True)

    else:
        if cat.style == "BOX":
            container = col_content.box()
            if show_title:
                header_row = container.row(align=True)
            content_area = container.row(align=True) if top_panel else container.column()

        elif cat.style == "BOX_TITLE":
            if show_title:
                title_box = col_content.box()
                header_row = title_box.row(align=True)
            content_area = col_content.column()

            if not top_panel:
                content_area.separator(factor=0.5)

        elif cat.style == "BOX_CONTENT":
            if show_title:
                header_row = col_content.row(align=True)
            content_area = col_content.box()

        else:  # PLAIN
            if show_title:
                header_row = col_content.row(align=True)
            content_area = col_content.column()

    if show_title:
        # header_row.template_icon(**get_icon(cat.icon), scale=prefs.cat_scale)
        header_row.label(text=cat.name, **get_icon(cat.icon))

    # indent for content
    indent_col = None

    if content_area != col_content and not top_panel:
        row = content_area.row(align=True)
        if show_title:
            indent_col = row.column()
            indent_col.scale_x = cat.indent / 2
            indent_col.label(text="", icon="BLANK1")
        content_area = row.column()

    else:
        content_area = col_content.row(align=True)

    content_area.alignment = "LEFT" if top_panel else "EXPAND"

    # iterate rows inside content_area
    current_section = None
    current_subsection = None
    current_section_visible = True
    current_subsection_visible = True
    previous_section_or_panel_drawn = False
    previous_subsection_drawn = False  # Track subsections separately

    # Add initial spacer before the first element of the category (only for side panels with headers)
    if not top_panel and cat.rows and show_title:
        content_area.separator(factor=cat.section_separator)

    for i, row_item in enumerate(cat.rows):

        if row_item.row_type == "SECTION":
            # Check if section/subsection is visible considering all conditions
            section_visible = _is_row_visible(row_item, context, cat, top_panel)

            if row_item.is_subsection:
                # For subsections, add spacer within the parent section's container
                if not top_panel and previous_subsection_drawn and section_visible and section_state["box"]:
                    section_state["box"].separator(factor=cat.section_separator)
            else:
                # For main sections, add spacer at the main content level
                if not top_panel and previous_section_or_panel_drawn and section_visible:
                    content_area.separator(factor=cat.section_separator)
                # Reset subsection tracking when starting a new main section
                previous_subsection_drawn = False

            _handle_section_row(
                row_item, section_state, subsection_state, cat, content_area, region_key, prefs, top_panel
            )

            # Track if this section was actually drawn
            if section_visible:
                if row_item.is_subsection:
                    previous_subsection_drawn = True
                else:
                    previous_section_or_panel_drawn = True

            # Track current section for content filtering
            if row_item.is_subsection:
                current_subsection = row_item
                current_subsection_visible = section_visible
            else:
                current_section = row_item
                current_section_visible = section_visible
                current_subsection = None
                current_subsection_visible = True  # Reset subsection visibility
            continue
        elif row_item.row_type == "PANEL":
            # Check if panel is visible considering all conditions
            panel_visible = _is_row_visible(row_item, context, cat, top_panel)

            if row_item.is_subsection:
                # For subpanels, add spacer within the parent section's container
                if not top_panel and previous_subsection_drawn and panel_visible and section_state["box"]:
                    section_state["box"].separator(factor=cat.section_separator)
            else:
                # For main panels, add spacer at the main content level
                if not top_panel and previous_section_or_panel_drawn and panel_visible:
                    content_area.separator(factor=cat.section_separator)
                # Reset subsection tracking when starting a new main panel
                previous_subsection_drawn = False

            _handle_panel_row(
                row_item, section_state, subsection_state, cat, content_area, region_key, prefs, top_panel
            )

            # Track if this panel was actually drawn
            if panel_visible:
                if row_item.is_subsection:
                    previous_subsection_drawn = True
                else:
                    previous_section_or_panel_drawn = True

            # Track current section for content filtering (panels behave like sections)
            if row_item.is_subsection:
                current_subsection = row_item
                current_subsection_visible = panel_visible
            else:
                current_section = row_item
                current_section_visible = panel_visible
                current_subsection = None
                current_subsection_visible = True  # Reset subsection visibility
            continue

        # For button rows, check if we should skip due to row's own display settings
        if top_panel and not row_item.display_top:
            continue
        if not top_panel and not row_item.display_side:
            continue

        # Check if current section/subsection conditionals allow content to be shown
        if not current_section_visible:
            continue
        if current_subsection and not current_subsection_visible:
            continue

        # Check row conditional expression
        if not _evaluate_row_conditional(row_item, context, cat):
            continue

        # For button rows, check if we should skip due to section display_top setting
        if top_panel:
            # Check if current subsection should not display in top panels
            if current_subsection and not current_subsection.display_top:
                continue
            # Check if current section should not display in top panels (and no subsection override)
            elif current_section and not current_subsection and not current_section.display_top:
                continue

        # For button rows, check if we should skip due to section display_side setting
        if not top_panel:
            # Check if current subsection should not display in side panels
            if current_subsection and not current_subsection.display_side:
                continue
            # Check if current section should not display in side panels (and no subsection override)
            elif current_section and not current_subsection and not current_section.display_side:
                continue

        if not (section_state["open"] and subsection_state["open"]):
            continue
        # content_area.separator(factor=0.5)
        _draw_button_row(row_item, context, section_state, subsection_state, cat, content_area, region_key, top_panel)


def _handle_section_row(
    row_item, section_state, subsection_state, cat, col_content, region_key, prefs, top_panel=False
):
    is_subsec = row_item.is_subsection

    # Early return if section should not be displayed in top panels
    if top_panel and not row_item.display_top:
        return

    # Early return if section should not be displayed in side panels
    if not top_panel and not row_item.display_side:
        return

    # Early return if section's conditional expression evaluates to False
    if not _evaluate_row_conditional(row_item, bpy.context, cat):
        return

    # Early return if section is closed or sections are disabled in top panel
    if is_subsec:
        if not section_state["open"] or (top_panel and not prefs.top_bars_use_sections):
            return
        # Use section's box as content area for subsections
        target_content = section_state["box"]
    else:
        target_content = col_content
        subsection_state["box"] = None  # Reset subsection state for new section

    # Setup container and get box for this section or subsection
    container, new_box = _setup_section_container(
        row_item, is_subsec, section_state, cat, target_content, prefs, top_panel
    )

    # If setup failed (None content), skip this section
    if container is None:
        return

    # Draw header before any BOX_CONTENT styling, pass category for overrides
    is_open = _draw_section_header(container, row_item, region_key, top_panel, cat) or (
        not prefs.top_bars_use_sections and top_panel
    )

    # For BOX_CONTENT style, create the box after the header if section is open
    if row_item.style == "BOX_CONTENT" and is_open:
        box_container = container.box()
        new_box = box_container.row(align=True) if top_panel else box_container.column()

    # Update section/subsection states and store the correct box
    if is_subsec:
        subsection_state["box"] = new_box if is_open else None
        subsection_state["open"] = is_open or (
            not prefs.top_bars_use_categories and top_panel and not prefs.top_bars_use_sections
        )

    else:
        section_state["box"] = new_box if is_open else None
        section_state["open"] = is_open or (
            not prefs.top_bars_use_categories and top_panel and not prefs.top_bars_use_sections
        )
        subsection_state["open"] = True

    # Add initial spacer after section header if section is open (only for side panels)
    if not top_panel and is_open and new_box:
        new_box.separator(factor=cat.section_separator)


def _validate_panel_exists(row_item):
    """
    Validate that a panel exists before attempting to draw it.

    Args:
        row_item: The RowGroup item representing a panel row

    Returns:
        bool: True if the panel exists and can be drawn, False otherwise
    """
    if not row_item or row_item.row_type != "PANEL":
        return True  # Not a panel row, allow other row types to proceed

    # If no panel assignment, consider it valid (will show "no panel assigned" message)
    if not row_item.panel_id and not row_item.custom_panel:
        return True

    # For custom panels, check if the panel class exists in bpy.types
    if row_item.panel_id == "Panels_CustomPanel" and row_item.custom_panel:
        # First check if the panel class exists
        panel_class_exists = hasattr(bpy.types, row_item.custom_panel) and hasattr(
            getattr(bpy.types, row_item.custom_panel, None), "draw"
        )

        # If panel class doesn't exist, return False
        if not panel_class_exists:
            return False

        # If panel class exists but there's a conditional, evaluate it
        if row_item.conditional and row_item.conditional.strip():
            try:
                conditional_expr = row_item.conditional.strip()

                # Try to compile the expression first to catch syntax errors early
                try:
                    compile(conditional_expr, "<panel_conditional>", "eval")
                except SyntaxError as syntax_err:
                    print(f"[AMP] Panel conditional syntax error for '{row_item.custom_panel}': {syntax_err}")
                    print(f"[AMP] Expression: {conditional_expr}")
                    return True  # Show on syntax error to avoid breaking UI

                # Create a comprehensive safe evaluation environment (same as _evaluate_row_conditional)
                safe_builtins = {
                    "getattr": getattr,
                    "hasattr": hasattr,
                    "isinstance": isinstance,
                    "len": len,
                    "bool": bool,
                    "str": str,
                    "int": int,
                    "float": float,
                    "list": list,
                    "dict": dict,
                    "tuple": tuple,
                    "set": set,
                    "None": None,
                    "True": True,
                    "False": False,
                    "abs": abs,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "any": any,
                    "all": all,
                }

                eval_globals = {"bpy": bpy, "context": bpy.context, "__builtins__": safe_builtins}

                # If the conditional contains 'prefs.', inject the addon preferences
                if "prefs." in conditional_expr:
                    eval_globals["prefs"] = get_prefs()

                # Add helper functions (same as _evaluate_row_conditional)
                def safe_get_nested_attr(obj, attr_path, default=None):
                    """Safely get nested attributes using dot notation, returning default if any step fails."""
                    if obj is None:
                        return default
                    try:
                        for attr in attr_path.split("."):
                            obj = getattr(obj, attr, None)
                            if obj is None:
                                return default
                        return obj
                    except (AttributeError, TypeError):
                        return default

                def has_addon(addon_name):
                    """Check if an addon is enabled."""
                    try:
                        return addon_name in bpy.context.preferences.addons
                    except:
                        return False

                def object_has_attr_chain(obj, *attr_names):
                    """Check if object has a chain of attributes (e.g., obj.als.turn_on)"""
                    if obj is None:
                        return False
                    current = obj
                    for attr_name in attr_names:
                        if not hasattr(current, attr_name):
                            return False
                        current = getattr(current, attr_name)
                        if current is None:
                            return False
                    return True

                # Add helper functions to evaluation environment
                eval_globals.update(
                    {
                        "safe_get_nested_attr": safe_get_nested_attr,
                        "has_addon": has_addon,
                        "object_has_attr_chain": object_has_attr_chain,
                    }
                )

                # Evaluate the conditional expression
                conditional_result = eval(conditional_expr, eval_globals)
                return bool(conditional_result)
            except Exception as e:
                # Enhanced error reporting with more context
                print(f"[AMP] Panel conditional evaluation error for '{row_item.custom_panel}': {e}")
                print(f"[AMP] Expression: {conditional_expr}")
                print(f"[AMP] Error type: {type(e).__name__}")
                return True

        # Panel class exists and no conditional, so it's valid
        return True

    # For regular panel functions, check if the function exists in the definitions module
    if row_item.panel_id:
        try:
            from . import addon_ui_definitions_panels

            # Check if the panel function exists in regular panels
            if hasattr(addon_ui_definitions_panels, row_item.panel_id):
                # For external panels, do additional validation by checking if they use external panel classes
                panel_func = getattr(addon_ui_definitions_panels, row_item.panel_id)

                # Check if this is an external panel by looking for specific patterns in the function
                # This is a heuristic approach - external panels typically use create_external_panel_function
                import inspect

                try:
                    source = inspect.getsource(panel_func)
                    # If the function uses create_external_panel_function, extract the panel class name
                    if "create_external_panel_function" in source:
                        # Try to extract the panel_class_name from the source
                        # This is a simple pattern match - may need refinement
                        import re

                        match = re.search(r'panel_class_name="([^"]+)"', source)
                        if match:
                            panel_class_name = match.group(1)
                            # Use the validation function from the definitions module
                            return addon_ui_definitions_panels.validate_external_panel_exists(panel_class_name)
                except (OSError, TypeError):
                    # If we can't inspect the source, assume it's valid
                    pass

                return True  # Regular panel function found

            # If not found in regular panels and forge version is enabled, check forge panels
            if is_forge_version():
                try:
                    from . import addon_ui_definitions_panels_forge
                    
                    if hasattr(addon_ui_definitions_panels_forge, row_item.panel_id):
                        return True  # Forge panel function found
                except ImportError:
                    pass

            # Panel function not found in either regular or forge modules
            return False

            return True  # Regular panel function exists

        except ImportError:
            return False

    return True  # Default to true for any other cases


def _handle_panel_row(row_item, section_state, subsection_state, cat, col_content, region_key, prefs, top_panel=False):
    """Handle drawing a panel row using the panels definition system"""
    is_subsec = row_item.is_subsection
    context = bpy.context

    # Early return if panel should not be displayed in top panels
    if top_panel and not row_item.display_top:
        return

    # Early return if panel should not be displayed in side panels
    if not top_panel and not row_item.display_side:
        return

    # Early return if external panel doesn't exist
    if not _validate_panel_exists(row_item):
        return

    # Early return if panel's conditional expression evaluates to False
    if not _evaluate_row_conditional(row_item, context, cat):
        return

    # Early return if panel should not be drawn
    if is_subsec:
        if not section_state["open"] or (top_panel and not prefs.top_bars_use_sections):
            return
        # Use section's box as content area for subpanels
        target_content = section_state["box"]
    else:
        target_content = col_content
        subsection_state["box"] = None  # Reset subsection state for new panel

    # Safety check: if target_content is None, return early
    if target_content is None:
        return

    # Get panel function from panel_id or custom_panel
    has_panel_assignment = row_item.panel_id or row_item.custom_panel

    if not has_panel_assignment:
        # Show label and add button if no panel_id is set
        info_row = target_content.row(align=True)
        info_row.label(text=f"Panel '{row_item.name}' - No panel assigned", icon="INFO")

        # Add the panel picker button
        op_pick_panel = info_row.operator("amp.row_panel_add", text="Add Panel", icon="ADD")

        # Set context for panel picker (same logic as in the main function)
        prefs_instance = get_prefs()
        owner_obj_for_op = None
        cat_idx_for_op = -1

        try:
            cat_idx_for_op = list(prefs_instance.ui_categories).index(cat)
            owner_obj_for_op = prefs_instance
        except ValueError:
            for pm_candidate in prefs_instance.popup_panels:
                try:
                    cat_idx_for_op = list(pm_candidate.categories).index(cat)
                    owner_obj_for_op = pm_candidate
                    break
                except ValueError:
                    continue

        if owner_obj_for_op and cat_idx_for_op != -1:
            set_operator_context(op_pick_panel, owner_obj_for_op)
            op_pick_panel.category_index = cat_idx_for_op
        else:
            set_operator_context(op_pick_panel, prefs_instance)
            op_pick_panel.category_index = prefs_instance.active_category_index

        # Find the row index in the category
        op_pick_panel.row_index = next((i for i, r in enumerate(cat.rows) if r == row_item), 0)
        return

    # Setup container and get box for this panel or subpanel (same as sections)
    container, new_box = _setup_section_container(
        row_item, is_subsec, section_state, cat, target_content, prefs, top_panel
    )

    # If setup failed (None content), skip this panel
    if container is None:
        return

    # In top panels, show operator button instead of collapsible header
    if top_panel:
        # Show panel as operator button aligned to left
        button_row = container.row(align=True)
        button_row.alignment = "LEFT"

        # Only use icon if panel row has one defined
        if row_item.icon and row_item.icon not in {"NONE", "BLANK1", ""}:
            panel_icon = get_icon(row_item.icon)
            op = button_row.operator("amp.show_panel_popup", text=row_item.name, **panel_icon)
        else:
            op = button_row.operator("amp.show_panel_popup", text=row_item.name)

        # Set the panel info for the popup operator
        if row_item.panel_id == "Panels_CustomPanel":
            op.custom_panel = row_item.custom_panel
            op.panel_id = ""  # Clear regular panel_id for custom panels
        else:
            op.panel_id = row_item.panel_id
            op.custom_panel = ""  # Clear custom panel for regular panels

        # Update states to indicate panel is "open" for layout purposes
        if is_subsec:
            subsection_state["box"] = None
            subsection_state["open"] = True
        else:
            section_state["box"] = None
            section_state["open"] = True
            subsection_state["open"] = True
        return

    # For side panels, draw header exactly like sections
    is_open = _draw_section_header(container, row_item, region_key, top_panel, cat) or (
        not prefs.top_bars_use_sections and top_panel
    )

    # For BOX_CONTENT style, create the box after the header if panel is open
    if row_item.style == "BOX_CONTENT" and is_open:
        box_container = container.box()
        new_box = box_container.row(align=True) if top_panel else box_container.column()

    # Update section/subsection states and store the correct box
    if is_subsec:
        subsection_state["box"] = new_box if is_open else None
        subsection_state["open"] = is_open or (
            not prefs.top_bars_use_categories and top_panel and not prefs.top_bars_use_sections
        )
    else:
        section_state["box"] = new_box if is_open else None
        section_state["open"] = is_open or (
            not prefs.top_bars_use_categories and top_panel and not prefs.top_bars_use_sections
        )
        subsection_state["open"] = True

    # Draw panel content if open
    if is_open and new_box:
        content_area = new_box if top_panel else new_box.column()
        # Add initial spacer after panel header (only for side panels)
        if not top_panel:
            content_area.separator(factor=cat.section_separator)

        if top_panel:
            # show operator button to open popup
            if row_item.icon and row_item.icon not in {"NONE", "BLANK1", ""}:
                icon_args = get_icon(row_item.icon)
                op = content_area.operator("amp.show_panel_popup", text=row_item.name, **icon_args)
            else:
                op = content_area.operator("amp.show_panel_popup", text=row_item.name)

            # Set the panel info for the popup operator
            if row_item.panel_id == "Panels_CustomPanel":
                op.custom_panel = row_item.custom_panel
                op.panel_id = ""  # Clear regular panel_id for custom panels
            else:
                op.panel_id = row_item.panel_id
                op.custom_panel = ""  # Clear custom panel for regular panels
        else:
            # inline draw for side panels
            # Apply indentation logic consistent with button rows
            panel_content_row = content_area.row(align=True)

            # Add indentation if this panel is inside a section/subsection (same logic as _draw_button_row)
            if (new_box is not col_content) and not top_panel:
                indent_col = panel_content_row.row(align=True)
                indent_col.label(text="", icon="BLANK1")
                indent_col.scale_x = cat.indent / 2

            # Create the actual panel content area with proper indentation
            panel_layout = panel_content_row.column()

            if row_item.panel_id == "Panels_CustomPanel" and row_item.custom_panel:
                # Handle custom panel by class name
                if hasattr(bpy.types, row_item.custom_panel):
                    panel_class = getattr(bpy.types, row_item.custom_panel)
                    if hasattr(panel_class, "draw"):
                        # Create a mock panel object for compatibility
                        mock_panel = type("MockPanel", (), {"layout": panel_layout})()
                        try:
                            panel_class.draw(mock_panel, context)
                        except Exception as e:
                            error_row = panel_layout.row()
                            error_row.alert = True
                            error_row.label(text=f"Panel error: {str(e)[:50]}...", icon="ERROR")
                    else:
                        error_row = panel_layout.row()
                        error_row.alert = True
                        error_row.label(text=f"{row_item.custom_panel} has no draw method", icon="ERROR")
                else:
                    error_row = panel_layout.row()
                    error_row.alert = True
                    error_row.label(text=f"Panel '{row_item.custom_panel}' not found", icon="ERROR")
            elif row_item.panel_id:
                # Handle regular panel functions
                from . import addon_ui_definitions_panels

                # First try to get the panel from regular panels
                panel_func = getattr(addon_ui_definitions_panels, row_item.panel_id, None)

                # If not found in regular panels and forge version is enabled, try forge panels
                if not panel_func and is_forge_version():
                    try:
                        from . import addon_ui_definitions_panels_forge

                        panel_func = getattr(addon_ui_definitions_panels_forge, row_item.panel_id, None)
                    except ImportError:
                        pass

                if panel_func:
                    panel_func(panel_layout, context)
                else:
                    err = panel_layout.row()
                    err.alert = True
                    err.label(text=f"Panel '{row_item.panel_id}' missing", icon="ERROR")
            else:
                # This should not happen since we check has_panel_assignment earlier
                err = panel_layout.row()
                err.alert = True
                err.label(text="No panel assigned", icon="INFO")


def _setup_section_container(row_item, is_subsec, section_state, cat, col_content, prefs, top_panel=False):
    # Safety check: if col_content is None, return None containers
    if col_content is None:
        return None, None

    # Create an outer container to hold both indent and content
    if is_subsec and not top_panel:
        outer_row = col_content.row(align=True)
        indent_col = outer_row.column()
        indent_col.scale_x = cat.indent / 2
        indent_col.label(text="", icon="BLANK1")
        col_content = outer_row.column()

    style = row_item.style

    if top_panel:
        top_pannel_row = col_content.row().row(align=True)
        return top_pannel_row, top_pannel_row

    if style == "BOX":
        content_box = col_content.box().column()
        return content_box, content_box

    elif style == "BOX_TITLE":
        title_box = col_content.box()
        content_col = col_content.column()
        return title_box, content_col

    elif style == "BOX_CONTENT":
        # Just create and return the container - box will be added after header
        container = col_content.column()
        return container, container

    else:  # PLAIN
        container = col_content.column()
        return container, container


def _draw_section_header(container, row_item, region_key, top_panel=False, category=None):
    header = container.row(align=True)
    header.alignment = "LEFT" if top_panel else "EXPAND"
    prefs = get_prefs()

    title_row = header.row(align=True)
    title_row.alignment = "LEFT"

    blank_row = header.row(align=True)
    blank_row.alignment = "EXPAND"

    is_open = getattr(row_item, f"{region_key}_open") or not prefs.top_bars_use_sections and top_panel

    if not prefs.top_bars_use_sections and top_panel:
        return

    has_custom_icon = row_item.icon and row_item.icon.upper() not in {"NONE", "", "BLANK1"}

    # Determine if we should use icon as toggle (check category override first, then section-specific, then global)
    use_icon_as_toggle = prefs.sections_icon_as_toggle
    if category and hasattr(category, "cat_sections_icon_as_toggle") and category.cat_sections_icon_as_toggle:
        use_icon_as_toggle = True
    elif top_panel and prefs.top_sections_icon_as_toggle:
        use_icon_as_toggle = True
    elif not top_panel and prefs.side_panels_icon_as_toggle:
        use_icon_as_toggle = True

    # Determine collapse style (check category override first)
    collapse_style = prefs.sections_collapse_style
    if (
        category
        and hasattr(category, "cat_sections_collapse_style")
        and category.cat_sections_collapse_style != "GLOBAL"
    ):
        collapse_style = category.cat_sections_collapse_style

    if has_custom_icon and use_icon_as_toggle:
        title_row.prop(
            row_item,
            f"{region_key}_open",
            text=row_item.name if top_panel and not prefs.top_bars_sections_hide_names else row_item.name,
            **get_icon(row_item.icon),
            emboss=top_panel,
            toggle=True,
        )

    elif has_custom_icon and not use_icon_as_toggle:
        # Use collapse icon for toggle, section icon for label
        collapse_icon = get_collapse_icon(is_open, collapse_style=collapse_style)
        title_row.prop(
            row_item,
            f"{region_key}_open",
            text="",
            icon=collapse_icon,
            emboss=top_panel,
            toggle=True,
        )

        # Add section icon to the label
        if not top_panel or (top_panel and not prefs.top_bars_sections_hide_names):
            icon_args = get_icon(row_item.icon)
            # if isinstance(icon_args, dict):
            #     header.label(text=row_item.name, **icon_args)
            # else:
            #     header.label(text=row_item.name, icon=icon_args)
            title_row.prop(
                row_item,
                f"{region_key}_open",
                text=row_item.name,  # row_item.name,
                **get_icon(row_item.icon),
                emboss=top_panel,
                toggle=True,
            )
        else:
            title_row.prop(row_item, f"{region_key}_open", text=row_item.name, **get_icon(row_item.icon))

    else:
        # No custom icon, use collapse icon only
        collapse_icon = get_collapse_icon(is_open, collapse_style=collapse_style)
        title_row.prop(
            row_item,
            f"{region_key}_open",
            text=row_item.name,
            icon=collapse_icon,
            emboss=top_panel,
            toggle=True,
        )
        # header.active = getattr(row_item, f"{region_key}_open") if top_panel else True

    if not top_panel:

        blank_row.prop(
            row_item,
            f"{region_key}_open",
            text=" ",
            icon="NONE",
            emboss=top_panel,
            toggle=True,
        )

    return is_open


def _draw_property_button(row_layout, btn):
    """Draw a property button with proper error handling"""
    if btn.button_path:
        try:
            data_obj, prop_name, array_index = parse_button_path(btn.button_path)

            if data_obj is not None and prop_name:
                prop_row = row_layout.row()
                # Handle empty display_name - empty string means no text
                if btn.display_name == "":
                    display_text = ""
                else:
                    display_text = btn.display_name if btn.display_name else prop_name

                if array_index is not None:
                    # Handle array properties
                    if btn.property_slider:
                        prop_row.prop(data_obj, prop_name, text=display_text, slider=True, index=array_index)
                    else:
                        prop_row.prop(data_obj, prop_name, text=display_text, index=array_index)
                else:
                    # Handle regular properties
                    if btn.property_slider:
                        prop_row.prop(data_obj, prop_name, text=display_text, slider=True)
                    else:
                        prop_row.prop(data_obj, prop_name, text=display_text)
            else:
                prop_row = row_layout.row()
                prop_row.alert = True
                prop_row.label(text="Invalid property path", icon="ERROR")
        except Exception as e:
            prop_row = row_layout.row()
            prop_row.alert = True
            prop_row.label(text=f"Error: {str(e)[:20]}...", icon="ERROR")
    else:
        prop_row = row_layout.row()
        prop_row.alert = True
        prop_row.label(text="No property path set", icon="INFO")


def _draw_operator_button(row_layout, btn):
    """Draw an operator button with proper error handling"""
    if btn.button_path:
        try:
            operator_name = parse_operator_call(btn.button_path)

            op_row = row_layout.row()
            # Determine display text - empty string means no text at all
            if btn.display_name == "":
                display_text = ""
            elif btn.display_name:
                display_text = btn.display_name
            elif operator_name:
                display_text = operator_name.replace(".", " ").title()
            else:
                display_text = "Operator"

            # Create the generic operator button
            op = op_row.operator(
                "amp.execute_operator_string",
                text=display_text,
                **get_icon(btn.icon if btn.icon not in {"NONE", "BLANK1", ""} else "PLAY"),
            )

            # Set the operator string to execute
            op.operator_string = btn.button_path

        except Exception as e:
            op_row = row_layout.row()
            op_row.alert = True
            op_row.label(text=f"Error: {str(e)[:20]}...", icon="ERROR")
    else:
        op_row = row_layout.row()
        op_row.alert = True
        op_row.label(text="No operator path set", icon="INFO")


def _draw_button_row(row_item, context, section_state, subsection_state, cat, col_content, region_key, top_panel=False):
    prefs = get_prefs()

    # For popup panels, always use the passed container to keep content inside the box
    # if region_key == "popup":
    #     target = col_content
    # else:
    target = subsection_state["box"] or section_state["box"] or col_content

    # start from a row so alignment can be honored
    base_row = target.row(align=True)

    # indent if this is inside a subsection
    if (target is not col_content) and not top_panel:
        indent_col = base_row.row(align=True)
        indent_col.label(text="", icon="BLANK1")
        indent_col.scale_x = cat.indent / 2

    main_container = base_row

    # Create button container: grid or aligned row
    if row_item.alignment == "GRID":
        row_layout = main_container.grid_flow(row_major=True, columns=0, even_columns=False, align=True)

    else:
        row_layout = main_container.row(align=True)
        row_layout.alignment = "LEFT" if top_panel else row_item.alignment

    # Draw the buttons in order
    for idx, btn in enumerate(row_item.buttons):

        if btn.button_id == "spacer":
            sp = row_layout.row().row(align=True)
            sp.scale_x = btn.spacer_width
            # Only use BLANK1 icon if there's no text, otherwise display as a normal label
            if btn.display_name and btn.display_name.strip():
                sp.label(text=btn.display_name)
            else:
                sp.label(text=btn.display_name, icon="BLANK1")

        elif btn.button_id == "custom_script":
            # draw the custom‐script button
            prefs = get_prefs()
            op = row_layout.row().operator("amp.execute_custom_script", text=btn.display_name, **get_icon(btn.icon))

            # if region_key == "popup":
            #     popup_panel_index = -1
            #     category_index = 0
            #     for pp_idx, popup_panel in enumerate(prefs.popup_panels):
            #         for cat_idx, popup_cat in enumerate(popup_panel.categories):
            #             if popup_cat == cat:
            #                 popup_panel_index = pp_idx
            #                 category_index = cat_idx
            #                 break
            #         if popup_panel_index != -1:
            #             break

            #     # Set popup panel context
            #     op.data_owner_is_popup_panel = True
            #     op.data_owner_popup_panel_index = popup_panel_index
            # else:
            #     # For regular UI, find the category in prefs.ui_categories
            category_index = next((i for i, c in enumerate(prefs.ui_categories) if c == cat), 0)

            op.category_index = category_index

            # find this row’s index in the category
            row_index = next((i for i, r in enumerate(cat.rows) if r == row_item), 0)
            op.row_index = row_index
            op.button_index = idx

        elif btn.button_id == "property":
            _draw_property_button(row_layout, btn)

        elif btn.button_id == "operator":
            _draw_operator_button(row_layout, btn)

        else:
            fn = getattr(addon_ui_definitions_button, btn.button_id, None)

            # Also try forge buttons if the function isn't found in regular buttons
            if not fn:
                try:
                    from . import addon_ui_definitions_button_forge

                    fn = getattr(addon_ui_definitions_button_forge, btn.button_id, None)
                except ImportError:
                    pass

            if fn:
                fn(row_layout.row(), context)

    target.separator(factor=0.5)


def draw_preview_toggles_prefs(layout, prefs):

    main_row = layout.row()

    main_split = main_row.split(factor=0.5)

    col1 = main_split.column()

    col2 = main_split.column()

    preview_box = col1.box()

    row = preview_box.row(align=True)

    row.label(text="Preview Top Panels")

    row.separator()

    row.row().prop(prefs, "preview_top_graph", text="", icon="GRAPH")
    row.row().prop(prefs, "preview_top_dope", text="", icon="ACTION")
    row.row().prop(prefs, "preview_top_nla", text="", icon="NLA")

    draw_ui_section(col1, bpy.context, "side_conf", "Side Panels Configuration", "SETTINGS", draw_side_config_ui, False)

    preview_box = col2.box()
    row = preview_box.row(align=True)
    row.label(text="Preview Side Panels")

    row.separator()

    row.row().prop(prefs, "preview_side_3dview", text="", icon="VIEW3D")
    row.row().prop(prefs, "preview_side_graph", text="", icon="GRAPH")
    row.row().prop(prefs, "preview_side_dope", text="", icon="ACTION")
    row.row().prop(prefs, "preview_side_nla", text="", icon="NLA")
    draw_ui_section(col2, bpy.context, "top_conf", "Top Panels Configuration", "SETTINGS", draw_top_config_ui, False)


def draw_config_ui(context, layout, _region_key=None, data=None):
    prefs = get_prefs()
    obj = data or prefs  # obj is the owner: prefs or a PieMenuGroup

    # Determine the correct category collection name for checking emptiness
    category_collection_attr = "categories" if hasattr(obj, "categories") else "ui_categories"

    if not getattr(obj, category_collection_attr, []):
        box = layout.box()
        row = box.row(align=True)
        op = row.operator("amp.category_add", icon="ADD", text="Add Category")
        set_operator_context(op, obj)
        op = row.operator("amp.restore_default_ui_content", icon="FILE_REFRESH", text="")
        # set_operator_context(op, obj)
        op = row.operator("amp.category_paste", icon="PASTEDOWN", text="")
        set_operator_context(op, obj)
        return

    # layout.separator()

    is_default_category = _draw_category_list(layout, obj)

    layout.separator()

    # Check if current category is a default category
    if is_default_category:  # is_default_category returns True when category is NOT default
        # Show normal UI for custom categories
        col = layout.column(align=True)
        _draw_rows_list(col, obj)
        col.separator()
        _draw_row_content(col, obj, context)
    else:
        # Show informative message for default categories
        info_box = layout.box()
        # info_box.alert = True

        # Header with icon
        header_row = info_box.row(align=True)
        header_row.label(text="Default Category Selected", icon="INFO")

        # Explanation message
        info_box.separator()
        msg_col = info_box.column(align=True)
        msg_col.label(text="This is a default category that cannot be modified directly.")
        msg_col.label(text="To customize this category:")
        msg_col.separator(factor=0.5)

        # Instructions with bullet points
        steps_col = msg_col.column(align=True)
        steps_col.label(text="   • Use the duplicate button to create a copy")
        steps_col.label(text="   • Modify the duplicated category as needed")
        steps_col.label(text="   • Unpin the default category to hide it from the UI")

        # Helpful action buttons
        info_box.separator()
        action_row = info_box.row()
        action_row.scale_y = 1.2

        # Duplicate button with proper context
        duplicate_op = action_row.operator("amp.category_duplicate", text="Duplicate This Category", icon="DUPLICATE")
        set_operator_context(duplicate_op, obj)

        # Restore defaults button
        restore_op = action_row.operator(
            "amp.restore_default_ui_content", text="Restore All Defaults", icon="FILE_REFRESH"
        )
        # set_operator_context(restore_op, obj)


def draw_general_options_config_ui(context, layout, _region_key):
    prefs = get_prefs()

    # sections_collapse_style
    layout.use_property_split = True
    layout.use_property_decorate = False

    row = layout.row(align=True)
    row.prop(prefs, "icons_set", text="Icons Theme")
    row.separator(factor=0.5)

    row.operator("amp.reload_icons", text="", **get_icon("FILE_REFRESH"))
    layout.prop(prefs, "sections_collapse_style", text="Sections Collapse Style")
    layout.prop(prefs, "hide_ui_during_playback", text="Hide UI During Playback")
    layout.prop(
        prefs,
        "sections_icon_as_toggle",
        text="Use Section Icon as Toggle",
    )
    layout.prop(prefs, "custom_scripts_path", text="Custom Scripts Path")
    layout.prop(prefs, "custom_user_icons_path", text="Custom Icons Path")
    layout.separator()


def draw_top_config_ui(context, layout, _region_key):
    prefs = get_prefs()
    layout.use_property_split = True
    layout.use_property_decorate = False

    layout.prop(prefs, "top_bars_use_categories", text="Use Categories")
    layout.prop(prefs, "top_bars_use_sections", text="Use Sections")
    layout.prop(prefs, "top_bars_sections_hide_names", text="Hide Section Names")
    layout.prop(prefs, "top_sections_icon_as_toggle", text="Top Sections Icon as Toggle")
    layout.prop(prefs, "collapsible_vanilla_top_panels", text="Collapsible Default Top Panels")
    layout.prop(prefs, "top_bars_position", text="Top Bars Position")


def draw_side_config_ui(context, layout, _region_key):
    prefs = get_prefs()
    layout.use_property_split = True
    layout.use_property_decorate = False

    layout.prop(prefs, "cat_placement", text="Category Placement")
    layout.prop(prefs, "cat_scale", text="Category Scale")
    layout.prop(prefs, "cat_headers", text="Category Headers")
    layout.prop(prefs, "cat_box_container", text="Category Box Container")
    layout.prop(prefs, "sections_box_container", text="Section Box Container")
    layout.prop(prefs, "side_panels_icon_as_toggle", text="Side Panels Icon as Toggle")


def _draw_category_list(layout, obj):  # obj is the owner (prefs or PieMenuGroup)
    container = layout.column()

    title_box = container.box()
    title_split = title_box.split(factor=0.5)
    title_split.scale_y = 1.5

    buttons = title_split.row()
    buttons.label(text="Categories")
    buttons = title_split.row()
    op_add = buttons.operator("amp.category_add", icon="COLLECTION_NEW", text="Category")
    set_operator_context(op_add, obj)
    op_add = buttons.operator("amp.restore_default_ui_content", icon="FILE_REFRESH", text="")
    # set_operator_context(op_add, obj)

    row = container.row()

    col = row.column()
    cat_prop_name = "categories" if hasattr(obj, "categories") else "ui_categories"
    # Set rows based on context: 8 for popup panels (max 8 categories), 5 for normal categories
    list_rows = 8 if hasattr(obj, "categories") else 5
    col.template_list("AMP_UL_Categories", "", obj, cat_prop_name, obj, "active_category_index", rows=list_rows)

    ops_col = row.column(align=True)
    op_move_up = ops_col.operator("amp.category_move_up", icon="TRIA_UP", text="")
    set_operator_context(op_move_up, obj)
    op_move_down = ops_col.operator("amp.category_move_down", icon="TRIA_DOWN", text="")
    set_operator_context(op_move_down, obj)

    ops_col.separator(factor=0.5)

    op_copy = ops_col.operator("amp.category_copy", icon="COPYDOWN", text="")
    set_operator_context(op_copy, obj)
    op_paste = ops_col.operator("amp.category_paste", icon="PASTEDOWN", text="")
    set_operator_context(op_paste, obj)

    ops_col.separator(factor=0.5)

    op_duplicate = ops_col.operator("amp.category_duplicate", icon="DUPLICATE", text="")
    set_operator_context(op_duplicate, obj)

    # Check if the active category is a default category
    cat_coll_name = "categories" if hasattr(obj, "categories") else "ui_categories"
    cat_coll = getattr(obj, cat_coll_name, [])
    active_cat_idx = getattr(obj, "active_category_index", 0)

    if cat_coll and 0 <= active_cat_idx < len(cat_coll):
        active_cat = cat_coll[active_cat_idx]
        is_default_category = bool(getattr(active_cat, "default_cat_id", "") != "")
    else:
        is_default_category = False

    return not is_default_category  # Return True to enable UI when category is NOT default


def _draw_rows_list(layout, obj):  # obj is the owner (prefs or PieMenuGroup)
    # Get the current category based on obj's active_category_index
    cat_coll_name = "categories" if hasattr(obj, "categories") else "ui_categories"
    cat_coll = getattr(obj, cat_coll_name, [])
    active_cat_idx = getattr(obj, "active_category_index", 0)

    if not cat_coll or not (0 <= active_cat_idx < len(cat_coll)):
        layout.label(text="No category selected or available.")
        return
    cat = cat_coll[active_cat_idx]

    container = layout.column()

    title_box = container.box()
    title_split = title_box.split(factor=0.3)
    title_split.scale_y = 1.5

    header = title_split.row()
    header.label(text="Category content")
    buttons = title_split.row(align=True)

    op_add_section = buttons.row().operator("amp.row_add_section", icon="NEWFOLDER", text="Section")
    set_operator_context(op_add_section, obj)  # obj is the category owner

    op_add_button_row = buttons.row().operator("amp.row_add_button", icon="PRESET_NEW", text="Button Row")
    set_operator_context(op_add_button_row, obj)

    op_add_panel_row = buttons.row().operator("amp.row_add_panel", icon="PLUGIN", text="Panel")
    set_operator_context(op_add_panel_row, obj)

    row2 = container.row()
    col2 = row2.column()
    col2.template_list("AMP_UL_Rows", "", cat, "rows", cat, "active_row_index", rows=8)
    ops2 = row2.column(align=True)

    op_row_move_up = ops2.operator("amp.row_move_up", icon="TRIA_UP", text="")
    set_operator_context(op_row_move_up, obj)

    op_row_move_down = ops2.operator("amp.row_move_down", icon="TRIA_DOWN", text="")
    set_operator_context(op_row_move_down, obj)

    ops2.separator(factor=0.5)

    op_row_copy = ops2.operator("amp.row_copy", icon="COPYDOWN", text="")
    set_operator_context(op_row_copy, obj)

    op_row_paste = ops2.operator("amp.row_paste", icon="PASTEDOWN", text="")
    set_operator_context(op_row_paste, obj)

    ops2.separator(factor=0.5)

    op_row_duplicate = ops2.operator("amp.row_duplicate", icon="DUPLICATE", text="")
    set_operator_context(op_row_duplicate, obj)

    ops2.separator(factor=0.5)

    op_section_move_up = ops2.operator("amp.section_move_up", icon="TRIA_UP_BAR", text="")
    set_operator_context(op_section_move_up, obj)

    op_section_move_down = ops2.operator("amp.section_move_down", icon="TRIA_DOWN_BAR", text="")
    set_operator_context(op_section_move_down, obj)

    ops2.separator(factor=0.25)

    op_section_delete = ops2.operator("amp.section_delete", icon="TRASH", text="")
    set_operator_context(op_section_delete, obj)

    ops2.separator(factor=0.25)

    op_section_copy = ops2.operator("amp.section_copy", icon="COPYDOWN", text="")
    set_operator_context(op_section_copy, obj)

    op_section_paste = ops2.operator("amp.section_paste", icon="PASTEDOWN", text="")
    set_operator_context(op_section_paste, obj)


def _draw_row_content(layout, obj, context):  # obj is the owner (prefs or PieMenuGroup)
    cat_coll_name = "categories" if hasattr(obj, "categories") else "ui_categories"
    cat_coll = getattr(obj, cat_coll_name, [])
    active_cat_idx = getattr(obj, "active_category_index", 0)

    if not cat_coll or not (0 <= active_cat_idx < len(cat_coll)):
        layout.label(text="No category selected.")
        return
    cat = cat_coll[active_cat_idx]

    if not cat.rows:
        layout.label(text="No rows available")
        return

    active_row_idx = min(cat.active_row_index, len(cat.rows) - 1)
    if active_row_idx < 0:  # No rows, or active_row_index is invalid
        layout.label(text="No row selected.")
        return
    sel_row = cat.rows[active_row_idx]

    container = layout.column()

    if sel_row.row_type == "PANEL":
        title_box = container.box()
        title_split = title_box.split(factor=0.5)
        title_split.scale_y = 1.5

        header = title_split.row()
        header.label(text="Panel Configuration")

        buttons = title_split.row(align=True)
        # if not sel_row.panel_id and not sel_row.custom_panel:
        op_pick_panel = buttons.operator("amp.row_panel_add", text="Choose Panel", icon="MENU_PANEL")
        set_operator_context(op_pick_panel, obj)
        op_pick_panel.category_index = active_cat_idx
        op_pick_panel.row_index = active_row_idx

        # Panel picker button
        op_panel_picker = buttons.row().operator("amp.panel_picker_activate", text="Pick from UI", icon="EYEDROPPER")
        set_operator_context(op_panel_picker, obj)
        op_panel_picker.category_index = active_cat_idx
        op_panel_picker.row_index = active_row_idx

        # Show cancel button if panel picker is active
        if getattr(context.scene, "amp_panel_picker_active", False):
            cancel_row = buttons.row()
            cancel_row.alert = True
            cancel_row.operator("amp.panel_picker_cancel", text="Cancel Picker", icon="CANCEL")

        # Panel configuration area
        config_area = container.column()

        if sel_row.panel_id == "Panels_CustomPanel":
            # Custom panel configuration
            box = config_area.box()
            box.label(text="Custom Panel Settings", icon="PLUGIN")

            custom_panel_row = box.row()
            custom_panel_row.prop(sel_row, "custom_panel", text="Panel Class Name")

            # Show validation status
            if sel_row.custom_panel:
                validation_row = box.row()
                if hasattr(bpy.types, sel_row.custom_panel):
                    validation_row.label(text="Panel class found", icon="CHECKMARK")
                else:
                    validation_row.alert = True
                    validation_row.label(text="Panel class not found", icon="ERROR")
            else:
                help_row = box.row()
                help_row.label(text="Enter a Blender panel class name (e.g., VIEW3D_PT_context_properties)")

        elif sel_row.panel_id:
            # Regular panel configuration
            box = config_area.box()
            box.label(text=f"Panel: {sel_row.panel_id}", icon="PREFERENCES")
            info_row = box.row()
            info_row.label(text="This panel uses predefined content")
        else:
            # No panel assigned
            box = config_area.box()
            box.label(text="No Panel Assigned", icon="INFO")
            help_row = box.row()
            help_row.label(text="Click 'Add Panel' to assign a panel to this row")

    elif sel_row.row_type == "SECTION":
        title_box = container.box()
        title_split = title_box.split(factor=0.3)
        title_split.scale_y = 1.5

        header = title_split.row()
        section_type = "Subsection" if sel_row.is_subsection else "Section"
        header.label(text=f"{section_type} Configuration")

        # Section configuration area
        config_area = container.column()
        box = config_area.box()
        box.label(text=f"{section_type}: {sel_row.name}", icon="NEWFOLDER")
        info_row = box.row()
        info_row.label(text="Sections organize content and can be collapsed/expanded")

    elif sel_row.row_type == "BUTTON":
        title_box = container.box()
        title_split = title_box.split(factor=0.3)
        title_split.scale_y = 1.5

        header = title_split.row()

        title = "Button Row Content"

        header.label(text=title)
        buttons = title_split.row(align=True)

        op_add_btn = buttons.row().operator("amp.row_button_add", text="Button", icon="PLUS")
        set_operator_context(op_add_btn, obj)
        op_add_btn.category_index = active_cat_idx
        op_add_btn.row_index = active_row_idx

        op_add_spacer = buttons.row().operator("amp.row_button_add_spacer", text="Spacer", icon="DRIVER_DISTANCE")
        set_operator_context(op_add_spacer, obj)
        op_add_spacer.category_index = active_cat_idx
        op_add_spacer.row_index = active_row_idx

        op_add_script = buttons.row().operator("amp.row_button_add_script", text="Script", icon="FILE_NEW")
        set_operator_context(op_add_script, obj)
        op_add_script.category_index = active_cat_idx
        op_add_script.row_index = active_row_idx

        op_add_property = buttons.row().operator("amp.row_button_add_property", text="Property", icon="PROPERTIES")
        set_operator_context(op_add_property, obj)
        op_add_property.category_index = active_cat_idx
        op_add_property.row_index = active_row_idx

        op_add_operator = buttons.row().operator("amp.row_button_add_operator", text="Operator", icon="PLAY")
        set_operator_context(op_add_operator, obj)
        op_add_operator.category_index = active_cat_idx
        op_add_operator.row_index = active_row_idx

        row_ui = container.row(align=True)
        col1 = row_ui.column(align=True)
        col1.template_list("AMP_UL_ButtonEntries", "", sel_row, "buttons", sel_row, "active_button_index")
        col2 = row_ui.column().column(align=True)

        op_btn_move_up = col2.operator("amp.row_button_entry_move_up", icon="TRIA_UP", text="")
        set_operator_context(op_btn_move_up, obj)
        op_btn_move_up.category_index = active_cat_idx
        op_btn_move_up.row_index = active_row_idx
        op_btn_move_up.entry_index = sel_row.active_button_index  # entry_index is relative to current row's buttons

        op_btn_move_down = col2.operator("amp.row_button_entry_move_down", icon="TRIA_DOWN", text="")
        set_operator_context(op_btn_move_down, obj)
        op_btn_move_down.category_index = active_cat_idx
        op_btn_move_down.row_index = active_row_idx
        op_btn_move_down.entry_index = sel_row.active_button_index

        col2.separator(factor=0.5)

        op_btn_copy = col2.operator("amp.row_button_copy", icon="COPYDOWN", text="")
        set_operator_context(op_btn_copy, obj)
        op_btn_copy.category_index = active_cat_idx
        op_btn_copy.row_index = active_row_idx
        op_btn_copy.entry_index = sel_row.active_button_index

        op_btn_paste = col2.operator("amp.row_button_paste", icon="PASTEDOWN", text="")
        set_operator_context(op_btn_paste, obj)
        op_btn_paste.category_index = active_cat_idx
        op_btn_paste.row_index = active_row_idx

        col2.separator(factor=0.25)

        op_btn_duplicate = col2.operator("amp.row_button_entry_duplicate", icon="DUPLICATE", text="")
        set_operator_context(op_btn_duplicate, obj)
        op_btn_duplicate.category_index = active_cat_idx
        op_btn_duplicate.row_index = active_row_idx
        op_btn_duplicate.entry_index = sel_row.active_button_index


def _draw_custom_script_buttons(layout, prefs, context, entry, entry_index, compact=False, active_data=None):

    path = prefs.custom_scripts_path
    if not path or not os.path.isdir(path):
        layout.prop(prefs, "custom_scripts_path", text="" if compact else "Custom Scripts Folder")
        return

    files = [f for f in os.listdir(path) if f.endswith(".py")]
    row_ops = layout.row(align=True)
    row_ops.label(text=entry.text_block_name or "None")

    # Use the same contextual discovery logic as the UIList
    prefs_instance = get_prefs()
    owner_obj_for_op = None
    cat_idx_for_op = -1
    row_idx_for_op = -1
    found_owner_and_indices = False

    if active_data:
        # Try to find `active_data` (the row) in prefs.ui_categories' rows
        for c_idx, cat_candidate in enumerate(prefs_instance.ui_categories):
            if not hasattr(cat_candidate, "rows"):
                continue
            try:
                r_idx = list(cat_candidate.rows).index(active_data)
                owner_obj_for_op = prefs_instance
                cat_idx_for_op = c_idx
                row_idx_for_op = r_idx
                found_owner_and_indices = True
                break
            except ValueError:
                continue

        if not found_owner_and_indices:
            # Try to find `active_data` (the row) in popup_panels' categories' rows
            for pm_candidate in prefs_instance.popup_panels:
                for c_idx, cat_candidate in enumerate(pm_candidate.categories):
                    if not hasattr(cat_candidate, "rows"):
                        continue
                    try:
                        r_idx = list(cat_candidate.rows).index(active_data)
                        owner_obj_for_op = pm_candidate
                        cat_idx_for_op = c_idx
                        row_idx_for_op = r_idx
                        found_owner_and_indices = True
                        break
                    except ValueError:
                        continue
                if found_owner_and_indices:
                    break

    # Fallback to original logic if contextual discovery fails or active_data not provided
    if not found_owner_and_indices:
        owner_obj_for_op = prefs_instance
        cat_idx_for_op = prefs.active_category_index
        if 0 <= prefs.active_category_index < len(prefs.ui_categories):
            current_category_for_script_ops = prefs.ui_categories[cat_idx_for_op]
            row_idx_for_op = current_category_for_script_ops.active_row_index
        else:
            row_idx_for_op = 0

    if entry.script:
        op_edit = row_ops.row().operator(
            "amp.row_button_edit_script", text="" if compact else "Edit Script", icon="TEXT"
        )
        set_operator_context(op_edit, owner_obj_for_op)
        op_edit.category_index = cat_idx_for_op
        op_edit.row_index = row_idx_for_op
        op_edit.entry_index = entry_index

        op_change = row_ops.operator(
            "amp.row_button_assign_script", text="" if compact else "Change Script", icon="FILE_REFRESH"
        )
        set_operator_context(op_change, owner_obj_for_op)
        op_change.category_index = cat_idx_for_op
        op_change.row_index = row_idx_for_op
        op_change.entry_index = entry_index

        op_unassign = row_ops.row().operator(
            "amp.row_button_unassign_script", text="" if compact else "Unassign", icon="X"
        )
        set_operator_context(op_unassign, owner_obj_for_op)
        op_unassign.category_index = cat_idx_for_op
        op_unassign.row_index = row_idx_for_op
        op_unassign.entry_index = entry_index

    else:
        sub = row_ops.row(align=True)
        sub.enabled = bool(files)
        op_assign = sub.row().operator(
            "amp.row_button_assign_script", text="" if compact else "Assign Script", icon="RESTRICT_SELECT_OFF"
        )
        set_operator_context(op_assign, owner_obj_for_op)
        op_assign.category_index = cat_idx_for_op
        op_assign.row_index = row_idx_for_op
        op_assign.entry_index = entry_index

        op_create = row_ops.row().operator(
            "amp.row_button_create_script", text="" if compact else "Create Script", icon="FILE_NEW"
        )
        set_operator_context(op_create, owner_obj_for_op)
        op_create.category_index = cat_idx_for_op
        op_create.row_index = row_idx_for_op
        op_create.entry_index = entry_index


# -----------------------------------------------------------------------------
# Named UI draw callbacks (allow proper removal later)
# -----------------------------------------------------------------------------
def _draw_side_view(self, context):
    draw_side_panel_ui(context, self.layout, "side_view")


def _draw_side_graph(self, context):
    draw_side_panel_ui(context, self.layout, "side_graph")


def _draw_side_dope(self, context):
    draw_side_panel_ui(context, self.layout, "side_dope")


def _draw_side_nla(self, context):
    draw_side_panel_ui(context, self.layout, "side_nla")


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

classes = (
    AMP_UL_Categories,
    AMP_UL_Rows,
    AMP_UL_ButtonEntries,
)


def register_ui():

    try:
        unregister_ui()
    except Exception:
        pass

    bpy.types.AMP_PT_AniMateProView.prepend(_draw_side_view)
    bpy.types.AMP_PT_AniMateProGraph.prepend(_draw_side_graph)
    bpy.types.AMP_PT_AniMateProDope.prepend(_draw_side_dope)
    bpy.types.AMP_PT_AniMateProNLA.prepend(_draw_side_nla)


def unregister_ui():
    bpy.types.AMP_PT_AniMateProView.remove(_draw_side_view)
    bpy.types.AMP_PT_AniMateProGraph.remove(_draw_side_graph)
    bpy.types.AMP_PT_AniMateProDope.remove(_draw_side_dope)
    bpy.types.AMP_PT_AniMateProNLA.remove(_draw_side_nla)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    # Add property to WindowManager to store panel ID for popups
    bpy.types.WindowManager.amp_popup_panel_id = StringProperty(
        name="AMP Popup Panel ID", description="ID of the panel to show in popup", default=""
    )

    from . import addon_ui_popup
    from . import addon_ui_operators

    addon_ui_operators.register()
    addon_ui_popup.register()

    register_ui()


def unregister():

    from . import addon_ui_popup
    from . import addon_ui_operators

    addon_ui_operators.unregister()
    addon_ui_popup.unregister()

    unregister_ui()

    # Remove property from WindowManager
    if hasattr(bpy.types.WindowManager, "amp_popup_panel_id"):
        del bpy.types.WindowManager.amp_popup_panel_id

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
