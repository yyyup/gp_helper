# ------------------------------------------------------------------------ #
# Start of Rig_UI_customIcons.py
# This module contains the code for adding custom icons

import bpy
import os
import time
from bpy.utils import previews
from .general import refresh_ui
from .. import __package__ as base_package
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

amp_custom_icons = None

# Global instance for popup management
amp_icon_selector_instance = None
protected_icon_reload = False


def close_popup():
    """Close popup using simple screen reassignment"""
    bpy.context.window.screen = bpy.context.window.screen


def get_addon_path():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))


def load_icons(icons_folders=["icons", "icons_grey"]):
    global amp_custom_icons
    prefs = bpy.context.preferences.addons[base_package].preferences
    addon_dir = get_addon_path()

    unload_icons()


    amp_custom_icons = previews.new()

    # Load icons from addon assets folders
    for folder in icons_folders:
        folder_path = os.path.join(addon_dir, "assets", folder)
        if os.path.exists(folder_path):
            for icon_file in os.listdir(folder_path):
                if icon_file.endswith(".png"):
                    icon_path = os.path.join(folder_path, icon_file)
                    icon_name = os.path.splitext(icon_file)[0]
                    amp_custom_icons.load(icon_name, icon_path, "IMAGE")

    # Load icons from custom user icons path if set
    if prefs.custom_user_icons_path and os.path.exists(prefs.custom_user_icons_path):
        custom_path = prefs.custom_user_icons_path
        if os.path.isdir(custom_path):
            for icon_file in os.listdir(custom_path):
                if icon_file.endswith(".png"):
                    icon_path = os.path.join(custom_path, icon_file)
                    icon_name = os.path.splitext(icon_file)[0]
                    # Prefix custom user icons with "USER_" to avoid naming conflicts
                    custom_icon_name = f"USER_{icon_name}"
                    amp_custom_icons.load(custom_icon_name, icon_path, "IMAGE")

    # Update previous_icons_set to current value after loading
    prefs.previous_icons_set = prefs.icons_set


def refresh_icons(self, context):
    global amp_custom_icons

    prefs = bpy.context.preferences.addons[base_package].preferences

    # Check if icons_set has actually changed
    if prefs.icons_set == prefs.previous_icons_set:
        return

    reload_icons()


def reload_icons():
    """
    Reload custom icons. Protection mechanism prevents rapid successive calls.
    """
    global amp_custom_icons, protected_icon_reload

    prefs = bpy.context.preferences.addons[base_package].preferences

    # Prevent rapid successive refreshes
    if protected_icon_reload:
        return

    protected_icon_reload = True

    load_icons(["icons", prefs.icons_set])

    # Schedule protected_icon_reload reset after 0.5 seconds
    def _reset_protected():
        global protected_icon_reload
        protected_icon_reload = False
        return None

    bpy.app.timers.register(_reset_protected, first_interval=0.5)


def unload_icons():
    global amp_custom_icons

    try:
        bpy.utils.previews.remove(amp_custom_icons)
        amp_custom_icons = None
    except Exception as e:
        pass


def get_icon_id(icon_name):

    if icon_name in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys():
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items[icon_name].value
    elif amp_custom_icons is not None and icon_name in amp_custom_icons:
        return amp_custom_icons[icon_name].icon_id
    else:
        return bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items["ERROR"].value


def get_icon(icon_name):
    """Get the appropriate icon parameters for a UI element."""
    if isinstance(icon_name, int):
        return {"icon_value": icon_name}

    if isinstance(icon_name, str) and amp_custom_icons is not None and icon_name in amp_custom_icons:
        return {"icon_value": amp_custom_icons[icon_name].icon_id}

    if (
        isinstance(icon_name, str)
        and icon_name in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items
    ):
        return {"icon": icon_name}

    return {"icon": "BLANK1"}



# -----------------------------------------------------------------------------
# Operators: Icon selector moved in here from icon_selector.py
# -----------------------------------------------------------------------------

ALL_ICONS = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys()


class AMP_OT_icon_selector(bpy.types.Operator):
    """Select an icon for a UI element
    - LMB: open the icon selector dialog
    - Shift+LMB: apply the icon from the clipboard
    - Ctrl+LMB: copy the current icon name to the clipboard
    - Alt+LMB: clear the icon"""

    bl_idname = "amp.icon_selector"
    bl_label = "Select Icon"
    bl_options = {"REGISTER", "UNDO"}

    prop_name: bpy.props.StringProperty()
    category_index: bpy.props.IntProperty(default=-1)
    row_index: bpy.props.IntProperty(default=-1)
    entry_index: bpy.props.IntProperty(default=-1)
    # Context properties
    data_owner_is_popup_panel: bpy.props.BoolProperty(default=False)
    data_owner_popup_panel_index: bpy.props.IntProperty(default=-1)

    filter_text: bpy.props.StringProperty(name="Filter", default="")

    # Property to store the selected icon (like your selected_button)
    selected_icon: bpy.props.StringProperty(name="Selected Icon", default="")

    # Properties to store the mouse position (like your example)
    mouse_x: bpy.props.IntProperty(default=0)
    mouse_y: bpy.props.IntProperty(default=0)

    def invoke(self, context, event):
        global amp_icon_selector_instance
        amp_icon_selector_instance = self

        # Store mouse position like in your example
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        # Alt: clear icon
        if event.alt:
            self.set_icon_directly(context, "BLANK1")
            return {"FINISHED"}
        # Shift: apply icon from clipboard if valid
        elif event.shift:
            clipboard_icon = context.window_manager.clipboard
            valid = set(amp_custom_icons.keys()) if amp_custom_icons else set()
            valid |= set(ALL_ICONS)
            if isinstance(clipboard_icon, str) and clipboard_icon in valid:
                self.set_icon_directly(context, clipboard_icon)
                return {"FINISHED"}
            return {"CANCELLED"}
        # Ctrl: copy current icon name
        elif event.ctrl:
            context.window_manager.clipboard = self.get_current_icon_name(context)
            return {"FINISHED"}

        # If an icon was selected, execute the action (like your example)
        if self.selected_icon:
            return self.execute(context)

        # Default: open the popup (using invoke_popup like your example)
        return context.window_manager.invoke_popup(self, width=1200)

    def get_current_icon_name(self, context):
        prefs = get_prefs()

        owner = prefs
        category_collection = owner.ui_categories

        if self.data_owner_is_popup_panel and 0 <= self.data_owner_popup_panel_index < len(prefs.popup_panels):
            owner = prefs.popup_panels[self.data_owner_popup_panel_index]
            category_collection = owner.categories

        if not (0 <= self.category_index < len(category_collection)):
            return ""

        cat = category_collection[self.category_index]

        if self.row_index >= 0:
            if not (cat.rows and 0 <= self.row_index < len(cat.rows)):
                return ""
            row = cat.rows[self.row_index]
            if self.entry_index >= 0:
                if not (row.buttons and 0 <= self.entry_index < len(row.buttons)):
                    return ""
                return getattr(row.buttons[self.entry_index], self.prop_name, "")
            else:
                return getattr(row, self.prop_name, "")
        else:
            return getattr(cat, self.prop_name, "")

    def set_icon_directly(self, context, icon_name):
        prefs = get_prefs()

        owner = prefs
        category_collection = owner.ui_categories

        if self.data_owner_is_popup_panel and 0 <= self.data_owner_popup_panel_index < len(prefs.popup_panels):
            owner = prefs.popup_panels[self.data_owner_popup_panel_index]
            category_collection = owner.categories

        target_object = None
        if not (0 <= self.category_index < len(category_collection)):
            return  # Invalid category_index

        cat = category_collection[self.category_index]

        if self.row_index >= 0:
            if not (cat.rows and 0 <= self.row_index < len(cat.rows)):
                return  # Invalid row_index
            row = cat.rows[self.row_index]
            if self.entry_index >= 0:
                if not (row.buttons and 0 <= self.entry_index < len(row.buttons)):
                    return  # Invalid entry_index
                target_object = row.buttons[self.entry_index]
            else:
                target_object = row
        else:
            target_object = cat

        if target_object:
            setattr(target_object, self.prop_name, icon_name)
            refresh_ui(context)
            self.close_panel(context)

    def close_panel(self, context):
        """Closes the panel with a workaround (moving the cursor away and restoring its position later)"""
        window = context.window
        offset = 1210  # Greater than the popup size (1200 + 10)
        x, y = self.mouse_x, self.mouse_y

        # Move the cursor away from the popup
        window.cursor_warp(x + offset, y + offset)

        # Register a timer to move the cursor back after a short interval
        def restore_mouse_position():
            window.cursor_warp(x, y)

        bpy.app.timers.register(restore_mouse_position, first_interval=0.001)
        self.selected_icon = ""  # Reset the icon selection

    def draw(self, context):
        layout = self.layout

        if not self.selected_icon:
            # Display the icon selector if no icon has been selected
            layout.prop(self, "filter_text", text="", icon="VIEWZOOM")

            # custom icons
            if amp_custom_icons:
                box_custom = layout.box()
                box_custom.label(text="Custom Icons")
                grid = box_custom.grid_flow(row_major=True, columns=35, even_columns=True, align=True)
                for name in amp_custom_icons.keys():
                    if self.filter_text.lower() not in name.lower():
                        continue
                    btn = grid.operator(self.bl_idname, text="", **get_icon(name), emboss=False)
                    btn.selected_icon = name
                    btn.prop_name = self.prop_name
                    btn.category_index = self.category_index
                    btn.row_index = self.row_index
                    btn.entry_index = self.entry_index
                    btn.data_owner_is_popup_panel = self.data_owner_is_popup_panel
                    btn.data_owner_popup_panel_index = self.data_owner_popup_panel_index
                    btn.mouse_x = self.mouse_x  # Pass the mouse X position
                    btn.mouse_y = self.mouse_y  # Pass the mouse Y position

            # built-in icons
            box_builtin = layout.box()
            box_builtin.label(text="Built-in Icons")
            icons = [i for i in ALL_ICONS if self.filter_text.lower() in i.lower()]
            grid = box_builtin.grid_flow(row_major=True, columns=35, even_columns=True, align=True)
            for name in icons:
                btn = grid.operator(self.bl_idname, text="", **get_icon(name), emboss=False)
                btn.selected_icon = name
                btn.prop_name = self.prop_name
                btn.category_index = self.category_index
                btn.row_index = self.row_index
                btn.entry_index = self.entry_index
                btn.data_owner_is_popup_panel = self.data_owner_is_popup_panel
                btn.data_owner_popup_panel_index = self.data_owner_popup_panel_index
                btn.mouse_x = self.mouse_x  # Pass the mouse X position
                btn.mouse_y = self.mouse_y  # Pass the mouse Y position

    def execute(self, context):
        # If an icon was selected, apply it and close the popup
        if self.selected_icon:
            prefs = get_prefs()

            owner = prefs
            category_collection = owner.ui_categories

            if self.data_owner_is_popup_panel and 0 <= self.data_owner_popup_panel_index < len(prefs.popup_panels):
                owner = prefs.popup_panels[self.data_owner_popup_panel_index]
                category_collection = owner.categories

            target_object = None
            if not (0 <= self.category_index < len(category_collection)):
                return {"CANCELLED"}

            cat = category_collection[self.category_index]

            if self.row_index >= 0:
                if not (cat.rows and 0 <= self.row_index < len(cat.rows)):
                    return {"CANCELLED"}
                row = cat.rows[self.row_index]
                if self.entry_index >= 0:
                    if not (row.buttons and 0 <= self.entry_index < len(row.buttons)):
                        return {"CANCELLED"}
                    target_object = row.buttons[self.entry_index]
                else:
                    target_object = row
            else:
                target_object = cat

            if target_object:
                setattr(target_object, self.prop_name, self.selected_icon)

                # Close the popup using the same method as your example
                self.close_panel(context)

                # Reset global instance
                global amp_icon_selector_instance
                amp_icon_selector_instance = None

                # Refresh UI after closing
                refresh_ui(context)
                return {"FINISHED"}

        return {"FINISHED"}


class AMP_OT_reload_icons(bpy.types.Operator):
    """Reload AniMate Pro and custom user icons."""

    bl_idname = "amp.reload_icons"
    bl_label = "Reload Icons"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        reload_icons()
        return {"FINISHED"}


# ------------------------------Registration------------------------------ #

classes = [
    AMP_OT_icon_selector,
    AMP_OT_reload_icons,

]


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)
    prefs = bpy.context.preferences.addons[base_package].preferences

    # unload_icons()

    reload_icons()
    # Register a delayed reload for icons and UI refresh

    # def delayed_reload():
    #     try:
    #         reload_icons()
    #         print(f"[AniMate Pro] Icons reloaded successfully at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    #         for screen in bpy.data.screens:
    #             for area in screen.areas:
    #                 area.tag_redraw()

    #     except Exception as e:
    #         print(f"[AniMate Pro] Error during delayed reload: {e}")

    #     return None

    # bpy.app.timers.register(delayed_reload, first_interval=0.5)


def unregister():
    from bpy.utils import unregister_class

    unload_icons()

    for cls in reversed(classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            # This can happen if the class was never registered or already unregistered
            pass  # You could add a print statement here for debugging if needed


if __name__ == "__main__":
    register()

# End of Rig_UI_customIcons.py
# ------------------------------------------------------------------------ #
