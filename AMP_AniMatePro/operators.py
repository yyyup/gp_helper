##################
## operators.py ##
##################
from . import __package__ as base_package
import bpy
import os
import json
import inspect
from pathlib import Path
from bpy.props import (
    EnumProperty,
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    FloatVectorProperty,
    CollectionProperty,
)
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .utils.insert_keyframes import (
    get_3d_view_items,
    get_graph_editor_items,
    get_timeline_dopesheet_items,
)
from .utils import refresh_ui


class AMP_OT_deactivate_other_keymaps_for_operator(bpy.types.Operator):
    """Deactivate all other keymaps that match the key and modifiers of the specified operator"""

    bl_idname = "wm.deactivate_other_keymaps_for_operator"
    bl_label = "Deactivate Other Keymaps for Operator"

    operator_idname: bpy.props.StringProperty(
        name="Operator ID Name",
        description="ID name of the operator to match keymaps for",
    )

    def find_keymap_items(self, operator_idname):
        """Find all keymap items for a specific operator across all keymaps"""
        wm = bpy.context.window_manager
        found_items = []

        for km in wm.keyconfigs.user.keymaps.values():
            for kmi in km.keymap_items:
                if kmi.idname == operator_idname:
                    # Append both the keymap and the keymap item for later use
                    found_items.append((km, kmi))
        return found_items

    def execute(self, context):
        wm = bpy.context.window_manager
        target_kmis = self.find_keymap_items(self.operator_idname)

        if not target_kmis:
            self.report({"INFO"}, "No keymap items found for the specified operator.")
            return {"CANCELLED"}

        # Deactivate conflicting keymaps
        deactivated_count = 0
        for km, target_kmi in target_kmis:
            target_key = target_kmi.type
            target_modifiers = (
                target_kmi.shift,
                target_kmi.ctrl,
                target_kmi.alt,
                target_kmi.oskey,
            )
            target_space_type = km.space_type
            target_region_type = km.region_type

            for other_km in wm.keyconfigs.user.keymaps.values():
                if other_km.space_type == target_space_type and other_km.region_type == target_region_type:
                    for kmi in other_km.keymap_items:
                        if (
                            kmi.type == target_key
                            and (kmi.shift, kmi.ctrl, kmi.alt, kmi.oskey) == target_modifiers
                            and kmi.idname != self.operator_idname
                        ):
                            kmi.active = False
                            deactivated_count += 1

        self.report(
            {"INFO"},
            f"Deactivated {deactivated_count} conflicting keymaps for the specified operator.",
        )
        return {"FINISHED"}


class AMP_OT_CaptureKeyInput(bpy.types.Operator):
    """Capture Key Input"""

    bl_idname = "anim.amp_capture_key_input"
    bl_label = "Capture Key Input"
    action_id: bpy.props.StringProperty()

    action_modifiers: bpy.props.BoolProperty(
        name="Include Modifiers",
        description="Include modifiers in the key combination",
        default=True,
    )

    @staticmethod
    def update_ui():
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == "TIMER":
            return {"PASS_THROUGH"}

        # Handle BACKSPACE to reset to default
        if event.type == "BACKSPACE" and event.value == "PRESS":
            prefs = bpy.context.preferences.addons[base_package].preferences
            default_value = getattr(prefs, f"default_{self.action_id}")
            setattr(prefs, self.action_id, default_value)
            self.report(
                {"INFO"},
                f"Key for {self.action_id.replace('_', ' ').title()} reset to default",
            )
            context.area.header_text_set(None)  # Clear the header text
            self.update_ui()
            return {"FINISHED"}

        if event.value == "PRESS" and event.type not in {"ESC", "TIMER", "MOUSEMOVE"}:
            modifiers = []
            if self.action_modifiers:
                if event.shift:
                    modifiers.append("SHIFT")
                if event.ctrl:
                    modifiers.append("CTRL")
                if event.alt:
                    modifiers.append("ALT")
                if event.oskey:
                    modifiers.append("OSKEY")

            # Combine modifiers with the key (if it's not a modifier key itself)
            if event.type not in {
                "LEFT_SHIFT",
                "RIGHT_SHIFT",
                "LEFT_CTRL",
                "RIGHT_CTRL",
                "LEFT_ALT",
                "RIGHT_ALT",
                "OSKEY",
            }:
                key_identifier = "+".join(modifiers + [event.type])
                prefs = bpy.context.preferences.addons[base_package].preferences
                setattr(prefs, self.action_id, key_identifier)
                self.report(
                    {"INFO"},
                    f"Key set to {key_identifier} for {self.action_id.replace('_', ' ').title()}",
                )
                context.area.header_text_set(None)  # Clear the header text
                self.finish_capture(context)
                self.update_ui()
                return {"FINISHED"}

        context.area.header_text_set("Press a key (ESC or BACKSPACE to cancel)")
        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.capturing_key = self.action_id
        wm = context.window_manager
        wm.modal_handler_add(self)
        context.area.header_text_set("Press a key (ESC or BACKSPACE to cancel)")
        return {"RUNNING_MODAL"}

    def finish_capture(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.capturing_key = ""
        self.update_ui()

    def cancel(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.capturing_key = ""
        context.area.header_text_set(None)  # Clear the header text
        self.update_ui()


class AMP_OT_CaptureKeyInputPopupPanel(bpy.types.Operator):
    """Capture Key Input for Popup Panel"""

    bl_idname = "anim.amp_capture_key_input_popup_panel"
    bl_label = "Capture Popup Panel Key"
    bl_description = """Capture a key input for a popup panel hotkey.
Press ESC or RMB to cancel, or BACKSPACE to clear the hotkey"""

    popup_panel_index: bpy.props.IntProperty(default=-1)

    @staticmethod
    def update_ui():
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

    def modal(self, context, event):
        if event.type == "TIMER":
            return {"PASS_THROUGH"}

        # Handle ESC or RMB to cancel
        if (event.type == "ESC" and event.value == "PRESS") or (event.type == "RIGHTMOUSE" and event.value == "PRESS"):
            self.report({"INFO"}, "Hotkey capture cancelled")
            context.area.header_text_set(None)
            self.finish_capture(context, cancelled=True)
            return {"CANCELLED"}

        # Handle BACKSPACE to clear hotkey
        if event.type == "BACK_SPACE" and event.value == "PRESS":
            prefs = bpy.context.preferences.addons[base_package].preferences
            if 0 <= self.popup_panel_index < len(prefs.popup_panels):
                popup_panel = prefs.popup_panels[self.popup_panel_index]
                old_hotkey = popup_panel.hotkey_string
                popup_panel.hotkey_string = ""

                # Deregister the old hotkey if it existed
                if old_hotkey:
                    from .ui.addon_ui_popup_utils import unregister_popup_panel_hotkey

                    unregister_popup_panel_hotkey(self.popup_panel_index)

                self.report({"INFO"}, f"Hotkey cleared for popup panel '{popup_panel.name}'")
            context.area.header_text_set(None)
            self.finish_capture(context, cancelled=True)
            self.update_ui()
            return {"FINISHED"}

        if event.value == "PRESS" and event.type not in {"ESC", "RIGHTMOUSE", "TIMER", "MOUSEMOVE", "BACKS_PACE"}:
            modifiers = []
            if event.shift:
                modifiers.append("SHIFT")
            if event.ctrl:
                modifiers.append("CTRL")
            if event.alt:
                modifiers.append("ALT")
            if event.oskey:
                modifiers.append("OSKEY")

            # Combine modifiers with the key (if it's not a modifier key itself)
            if event.type not in {
                "LEFT_SHIFT",
                "RIGHT_SHIFT",
                "LEFT_CTRL",
                "RIGHT_CTRL",
                "LEFT_ALT",
                "RIGHT_ALT",
                "OSKEY",
            }:
                key_identifier = "+".join(modifiers + [event.type])
                prefs = bpy.context.preferences.addons[base_package].preferences
                if 0 <= self.popup_panel_index < len(prefs.popup_panels):
                    popup_panel = prefs.popup_panels[self.popup_panel_index]
                    popup_panel.hotkey_string = key_identifier
                    self.report({"INFO"}, f"Hotkey '{key_identifier}' set for popup panel '{popup_panel.name}'")

                    # Update the hotkey registration
                    from .ui.addon_ui_popup_utils import update_popup_panel_hotkey

                    result = update_popup_panel_hotkey(popup_panel, self.popup_panel_index)

                    if result:
                        self.report({"INFO"}, f"Hotkey set: {key_identifier}")
                    else:
                        self.report({"WARNING"}, f"Failed to register hotkey: {key_identifier}")

                context.area.header_text_set(None)
                self.finish_capture(context)
                self.update_ui()
                return {"FINISHED"}

        context.area.header_text_set("Press a key (ESC, RMB, or BACKSPACE to cancel/clear)")
        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        wm = context.window_manager
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.capturing_key = f"popup_panel_{self.popup_panel_index}_hotkey"
        popup_panel = prefs.popup_panels[self.popup_panel_index]
        popup_panel.is_capturing_hotkey = True

        # Refresh UI to show "Press any key..." text
        for area in context.screen.areas:
            area.tag_redraw()

        wm.modal_handler_add(self)
        context.area.header_text_set("Press a key (ESC or BACKSPACE to clear)")
        return {"RUNNING_MODAL"}

    def finish_capture(self, context, cancelled=False):
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.capturing_key = ""

        if self.popup_panel_index >= 0 and self.popup_panel_index < len(prefs.popup_panels):
            popup_panel = prefs.popup_panels[self.popup_panel_index]
            popup_panel.is_capturing_hotkey = False

            # Refresh UI to restore normal text
            for area in context.screen.areas:
                area.tag_redraw()

        self.update_ui()

    def cancel(self, context):
        context.area.header_text_set(None)
        self.update_ui()


def draw_insert_menu(context, layout):
    prefs = bpy.context.preferences.addons[base_package].preferences

    # Determine context and set items accordingly
    if context.area.type == "VIEW_3D":
        method = prefs.default_3d_view_insert_keyframe
        items = get_3d_view_items(None, context)
    elif context.area.type == "GRAPH_EDITOR":
        method = prefs.default_graph_editor_insert_keyframe
        items = get_graph_editor_items(None, context)
    elif context.area.type in ["DOPESHEET_EDITOR", "TIMELINE"]:
        method = prefs.default_timeline_dopesheet_insert_keyframe
        items = get_timeline_dopesheet_items(None, context)
    else:
        # Default or unsupported context
        items = []
        method = ""

    row = layout.row(align=True)
    split = row.split(factor=0.4)
    column = split.column(align=True)
    column.alignment = "RIGHT"
    column.label(text="Default Keying")
    column2 = split.column(align=True)
    # Dynamically create menu items
    for item in items:
        row = column2.row(align=True)
        op = row.operator(
            "wm.context_set_enum",
            text=item[1],
            # icon="CHECKBOX_HLT" if (method == item[0]) else "CHECKBOX_DEHLT",
            depress=(method == item[0]),
        )
        if context.area.type == "VIEW_3D":
            op.data_path = f"preferences.addons['{base_package}'].preferences.default_3d_view_insert_keyframe"
        elif context.area.type == "GRAPH_EDITOR":
            op.data_path = f"preferences.addons['{base_package}'].preferences.default_graph_editor_insert_keyframe"
        elif context.area.type in ["DOPESHEET_EDITOR", "TIMELINE"]:
            op.data_path = (
                f"preferences.addons['{base_package}'].preferences.default_timeline_dopesheet_insert_keyframe"
            )
        op.value = item[0]


class AMP_OT_ResetPreferencesToDefaults(bpy.types.Operator):
    """Reset all AniMate Pro preferences to default values and clear auto-save path"""

    bl_idname = "amp.reset_preferences_to_defaults"
    bl_label = "Reset AniMate Pro Preferences"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        reset_addon()
        return {"FINISHED"}

    def invoke(self, context, event):
        # return context.window_manager.invoke_confirm(self, event)
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="This will reset ALL AniMate Pro preferences")
        layout.label(text="to their default values and clear the auto-save path.")
        # layout.label(text="The add-on will be disabled, enable it again to apply changes.")
        layout.separator()
        layout.label(text="This action cannot be undone.", icon="ERROR")


class AMP_PT_InsertKeyPreferencesVIEW(bpy.types.Panel):
    bl_idname = "AMP_PT_InsertKeyPreferencesVIEW"
    bl_label = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 20

    def draw(self, context):
        layout = self.layout
        width = context.region.width
        ui_scale = context.preferences.system.ui_scale
        is_wide = width > (350 * ui_scale)

        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row()
        if is_wide:
            row.label()

        col = row.column()
        col.ui_units_x = 100

        if is_wide:
            row.label()
        userpref_panel = bpy.types.USERPREF_PT_animation_keyframes
        userpref_panel.draw_centered(self, context, col)


class AMP_PT_InsertKeyPreferencesGraph(bpy.types.Panel):
    bl_idname = "AMP_PT_InsertKeyPreferencesGraph"
    bl_label = ""
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 20

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        row = layout.row()

        row.label()

        col = row.column()
        col.ui_units_x = 100

        row.label()
        col2 = col.column(heading="Default Keying:", align=True)
        draw_insert_menu(context, col2)
        userpref_panel = bpy.types.USERPREF_PT_animation_fcurves
        userpref_panel.draw_centered(self, context, col)


class AMP_PT_InsertKeyPreferencesDope(bpy.types.Panel):
    bl_idname = "AMP_PT_InsertKeyPreferencesDope"
    bl_label = ""
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 20

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row()
        row.label()

        col = row.column()
        col.ui_units_x = 100

        col2 = col.column(heading="Default Keying:", align=True)
        draw_insert_menu(context, col2)
        userpref_panel = bpy.types.USERPREF_PT_animation_timeline
        userpref_panel.draw_centered(self, context, col)


# Global dictionary to store toggle states.
toggles = {}


def draw_toggle_button(layout, toggle_name: str, symbol: str = "Triangle") -> None:
    """
    Draw a toggle button with a specific icon based on the toggle state.

    The button's appearance changes according to the toggle state stored in a
    global dictionary 'toggles'. Depending on the selected symbol, a different
    icon is shown when the toggle state is active or inactive.

    Parameters:
        layout (UILayout): The UI layout to draw the button on.
        toggle_name (str): Identifier for the toggle state.
        symbol (str, optional): The icon type used. Options include:
            "Triangle", "Arrow", "Plus", "Eye", "Ghost", "Settings".
            Defaults to "Triangle".

    Returns:
        None
    """
    expanded = toggles.get(toggle_name, False)
    if symbol == "Triangle":
        icon = "TRIA_DOWN" if expanded else "TRIA_RIGHT"
    if symbol == "Arrow":
        icon = "DOWNARROW_HLT" if expanded else "RIGHTARROW"
    if symbol == "Plus":
        icon = "REMOVE" if expanded else "ADD"
    if symbol == "Eye":
        icon = "HIDE_OFF" if expanded else "HIDE_ON"
    if symbol == "Ghost":
        icon = "GHOST_ENABLED" if expanded else "GHOST_DISABLED"
    if symbol == "Settings":
        icon = "DOWNARROW_HLT" if expanded else "SETTINGS"
    layout.operator("ui.amp_toggle_panel_visibility", text="", icon=icon, emboss=False).panel_name = toggle_name


class AMP_OT_TogglePanelVisibility(bpy.types.Operator):
    """
    Toggle the visibility of a UI panel.

    This operator flips the panel's expanded/collapsed state when executed.

    Attributes:
        panel_name (str): The name of the panel whose visibility is toggled.
    """

    bl_idname = "ui.amp_toggle_panel_visibility"
    bl_label = "Toggle Panel Visibility"
    bl_description = "Toggle a panel open or closed"

    panel_name: bpy.props.StringProperty()
    default_open: BoolProperty(
        name="Default State",
        description="Panel default open state when first toggled",
        default=True,
    )

    def execute(self, context):
        """
        Execute the toggle operation to update the panel's visibility.

        Returns:
            set: A set containing {'FINISHED'} if the operation was successful.
        """
        current = toggles.get(self.panel_name, self.default_open)
        toggles[self.panel_name] = not current
        return {"FINISHED"}


def draw_version_update_dialog(layout, context, mouse_x=0, mouse_y=0):
    """Draw the version update dialog in place of preferences"""
    import os
    import json

    # Get current addon version directly from __init__.py
    try:
        # Try to get bl_info from the addon module directly first
        try:
            import sys

            addon_module = sys.modules.get(base_package)
            if addon_module and hasattr(addon_module, "bl_info"):
                bl_info = addon_module.bl_info
                current_version = ".".join(str(v) for v in bl_info["version"])
            else:
                raise Exception("Module method failed")
        except Exception:
            # Fallback: read and parse the __init__.py file
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            init_file = os.path.join(addon_dir, "__init__.py")
            bl_info = None
            if os.path.exists(init_file):
                with open(init_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Look for bl_info dictionary using regex
                    import re

                    pattern = r'bl_info\s*=\s*\{[^}]*"version"\s*:\s*\([^)]*\)[^}]*\}'
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        # Execute just the bl_info assignment
                        local_vars = {}
                        exec(match.group(0), {}, local_vars)
                        bl_info = local_vars.get("bl_info")

            if bl_info and "version" in bl_info:
                current_version = ".".join(str(v) for v in bl_info["version"])
            else:
                current_version = "Unknown"
    except Exception:
        current_version = "Unknown"

    # Get stored version
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(addon_dir)
    pathfile = os.path.join(parent, "AniMateProUserPrefsPath.json")

    stored_version = "Unknown"
    stored_path = None

    if os.path.isfile(pathfile):
        try:
            with open(pathfile, "r") as f:
                data = json.load(f)
            stored_version = data.get("addon_version", "Unknown")
            stored_path = data.get("auto_save_path")
        except Exception:
            pass

    # Header
    header_box = layout.box()
    header_row = header_box.row()
    header_row.label(text=f"AniMate Pro Updated: {stored_version} → {current_version}", icon="INFO")

    layout.separator()

    # Show different options based on whether saved preferences exist
    if stored_path and os.path.isfile(os.path.abspath(os.path.expanduser(stored_path))):
        layout.label(text="Previous settings file found:")
        layout.label(text=f"  {stored_path}")
        layout.separator()

        layout.label(text="Choose an option:")

        op1 = layout.operator("amp.version_update_action", text="Load Saved Settings", icon="IMPORT", depress=True)
        op1.action_type = "load_saved"
        op1.saved_path = os.path.abspath(os.path.expanduser(stored_path))
        op1.mouse_x = mouse_x
        op1.mouse_y = mouse_y

        op2 = layout.operator("amp.version_update_action", text="Keep Current Settings", icon="CHECKMARK")
        op2.action_type = "keep_current"
        op2.mouse_x = mouse_x
        op2.mouse_y = mouse_y

    else:
        layout.label(text="No previous settings file found.")
        layout.separator()

        layout.label(text="Choose an option:")

        op1 = layout.operator("amp.version_update_action", text="Keep Current Settings", icon="CHECKMARK")
        op1.action_type = "keep_current"
        op1.mouse_x = mouse_x
        op1.mouse_y = mouse_y

    op_defaults = layout.operator("amp.version_update_action", text="Default Settings", icon="FILE_NEW")
    op_defaults.action_type = "restore_defaults"
    op_defaults.mouse_x = mouse_x
    op_defaults.mouse_y = mouse_y

    op_imp = layout.operator("amp.version_update_action", text="Import From Other File", icon="IMPORT")
    op_imp.action_type = "import_preferences"
    op_imp.mouse_x = mouse_x
    op_imp.mouse_y = mouse_y


class AMP_OT_VersionUpdateDialog(bpy.types.Operator):
    """Dialog shown when a version update is detected"""

    bl_idname = "amp.version_update_dialog"
    bl_label = "AniMate Pro Version Update"
    bl_options = {"REGISTER", "UNDO"}

    stored_version: bpy.props.StringProperty()
    current_version: bpy.props.StringProperty()
    saved_preferences_path: bpy.props.StringProperty()

    # Mouse position for popup closing
    mouse_x: bpy.props.IntProperty(default=0)
    mouse_y: bpy.props.IntProperty(default=0)

    def invoke(self, context, event):
        # Store mouse position for closing popup
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        wm = context.window_manager
        refresh_ui(context)
        return wm.invoke_popup(self, width=350)

    def draw(self, context):
        layout = self.layout
        draw_version_update_dialog(layout, context, self.mouse_x, self.mouse_y)

    def execute(self, context):
        return {"FINISHED"}


class AMP_OT_VersionUpdateAction(bpy.types.Operator):
    """Execute the chosen version update action"""

    bl_idname = "amp.version_update_action"
    bl_label = "Version Update Action"
    bl_options = {"UNDO"}

    action_type: bpy.props.StringProperty()
    saved_path: bpy.props.StringProperty()

    # Mouse position for popup closing
    mouse_x: bpy.props.IntProperty(default=0)
    mouse_y: bpy.props.IntProperty(default=0)

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences

        if self.action_type == "load_saved":
            if self.saved_path and os.path.isfile(self.saved_path):
                bpy.ops.amp.restore_default_ui_content(skip_confirmation=True)
                try:
                    result = _load_preferences(self.saved_path, prefs)
                    if result == {"FINISHED"}:
                        print(f"[AniMate Pro] Loaded preferences from {self.saved_path}")
                    else:
                        print(f"[AniMate Pro] Failed to load preferences from {self.saved_path}")
                except Exception as e:
                    print(f"[AniMate Pro] Error loading preferences: {e}")
                    # For now, just skip loading and continue
                    print(f"[AniMate Pro] Continuing without loading saved preferences")

        elif self.action_type == "keep_current":
            bpy.ops.amp.restore_default_ui_content(skip_confirmation=True)
            print(f"[AniMate Pro] Keeping current preferences")

        elif self.action_type == "restore_defaults":
            print(f"[AniMate Pro] Starting fresh with defaults")
            reset_addon()

        elif self.action_type == "import_preferences":
            # Close the current popup first, then open import dialog
            self.close_panel(context)

            # Use a timer to delay the import dialog opening until after popup closes
            def delayed_import():
                bpy.ops.amp.import_preferences("INVOKE_DEFAULT")
                return None  # Unregister timer

            bpy.app.timers.register(delayed_import, first_interval=0.1)
            print(f"[AniMate Pro] Opening import preferences dialog")

        # Always do these actions after any choice
        restore_defaults_and_update_version()

        # Save Blender preferences to disk
        bpy.ops.wm.save_userpref()
        print(f"[AniMate Pro] Blender preferences saved")

        # Close the popup
        self.close_panel(context)

        # Reset dialog flag
        global _version_dialog_shown
        _version_dialog_shown = False

        # Register a delayed reload for icons and UI refresh
        def delayed_icon_reload():
            try:
                from .utils.customIcons import reload_icons

                reload_icons()
                print(f"[AniMate Pro] Reloaded icons after version update")
                for screen in bpy.data.screens:
                    for area in screen.areas:
                        area.tag_redraw()

            except Exception as e:
                print(f"[AniMate Pro] Error during delayed reload: {e}")

            return None

        bpy.app.timers.register(delayed_icon_reload, first_interval=0.5)

        return {"FINISHED"}

    def close_panel(self, context):
        """Close the popup using cursor movement (same as icon selector)"""
        window = context.window
        offset = 510  # Greater than the popup size (500 + 10)
        x, y = self.mouse_x, self.mouse_y

        # Move the cursor away from the popup
        window.cursor_warp(x + offset, y + offset)

        # Register a timer to move the cursor back after a short interval
        def restore_mouse_position():
            window.cursor_warp(x, y)

        bpy.app.timers.register(restore_mouse_position, first_interval=0.001)


def reset_addon():
    # Create and register timer handler for toggle effect
    def timer_callback():

        try:
            # Disable then re-enable the addon
            bpy.ops.preferences.addon_disable(module=base_package)
            bpy.ops.preferences.addon_enable(module=base_package)

        except Exception as e:
            print(f"[AniMate Pro] Error resetting addon: {e}")

        return None  # Unregister the timer

    # Register the timer for toggle effect
    bpy.app.timers.register(timer_callback, first_interval=0.01)


def restore_defaults_and_update_version():
    """Restore default categories and pie menus and update version file"""
    try:
        prefs = bpy.context.preferences.addons[base_package].preferences
    except KeyError:
        # Addon might be disabled, skip this operation
        print(f"[AniMate Pro] Addon not available, skipping restore operation")
        return

    # Update version file and mark setup complete ONLY - do not mark fresh_install or addon_up_to_date here
    # Those should only be set when user makes a choice in the dialog
    _write_userprefs_path(prefs.auto_save_path)

    print(f"[AniMate Pro] Version file updated")


# Global flag to prevent version file writing during startup checks
_startup_version_check_in_progress = False
_version_dialog_shown = False  # Prevent double dialogs


def _write_userprefs_path(path):
    """Store the auto-save path and addon version into AniMateProUserPrefsPath.json in the addon parent folder."""
    global _startup_version_check_in_progress

    # Prevent writing during startup version checks
    if _startup_version_check_in_progress:
        print("[AniMate Pro] Version file write blocked during startup check")
        return

    addon_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(addon_dir)
    out = os.path.join(parent, "AniMateProUserPrefsPath.json")

    # Get current addon version from __init__.py
    try:
        # Try to get bl_info from the addon module directly first
        try:
            import sys

            addon_module = sys.modules.get(base_package)
            if addon_module and hasattr(addon_module, "bl_info"):
                bl_info = addon_module.bl_info
                current_version = ".".join(str(v) for v in bl_info["version"])
            else:
                raise Exception("Module method failed")
        except Exception:
            # Fallback: read and parse the __init__.py file
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            init_file = os.path.join(addon_dir, "__init__.py")
            bl_info = None
            if os.path.exists(init_file):
                with open(init_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Look for bl_info dictionary using regex
                    import re

                    pattern = r'bl_info\s*=\s*\{[^}]*"version"\s*:\s*\([^)]*\)[^}]*\}'
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        # Execute just the bl_info assignment
                        local_vars = {}
                        exec(match.group(0), {}, local_vars)
                        bl_info = local_vars.get("bl_info")

            if bl_info and "version" in bl_info:
                current_version = ".".join(str(v) for v in bl_info["version"])
            else:
                current_version = "Unknown"
    except Exception:
        current_version = "Unknown"

    try:
        # Read existing data if file exists
        existing_data = {}
        if os.path.exists(out):
            try:
                with open(out, "r") as f:
                    existing_data = json.load(f)
                if not isinstance(existing_data, dict):
                    existing_data = {}
            except (json.JSONDecodeError, FileNotFoundError):
                existing_data = {}

        # Update only the fields we care about
        existing_data["addon_version"] = current_version
        if path:  # Only update path if it's not empty
            existing_data["auto_save_path"] = path

        # Write the updated data back
        with open(out, "w") as f:
            json.dump(existing_data, f, indent=2)

        # Mark install done - but ONLY if not during startup check
        try:
            prefs = bpy.context.preferences.addons[base_package].preferences
            prefs.fresh_install = False
            prefs.addon_up_to_date = True
        except KeyError:
            # Addon might be disabled during shutdown, that's OK
            pass
        print(f"[AniMate Pro] Version {current_version} saved to tracking file")

    except Exception as e:
        print(f"[AniMate Pro] Error writing version file: {e}")


class AMP_OT_TryReloadUserPrefs(bpy.types.Operator):
    """Try to reload user preferences on startup"""

    bl_idname = "amp.try_reload_user_prefs"
    bl_label = "Try Reload User Prefs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return self._try_reload_userprefs()

    def _try_reload_userprefs(self):
        global _startup_version_check_in_progress, _version_dialog_shown

        # Prevent double execution
        if _version_dialog_shown:
            return {"FINISHED"}

        # Set flag to prevent version file writing during check
        _startup_version_check_in_progress = True

        try:
            prefs = bpy.context.preferences.addons[base_package].preferences

            # Get current addon version from __init__.py - use same logic as _write_userprefs_path
            try:
                # Try to get bl_info from the addon module directly first
                try:
                    import sys

                    addon_module = sys.modules.get(base_package)
                    if addon_module and hasattr(addon_module, "bl_info"):
                        bl_info = addon_module.bl_info
                        current_version = ".".join(str(v) for v in bl_info["version"])
                        print(f"[AniMate Pro] Got version from module: {current_version}")
                    else:
                        raise Exception("Module method failed")

                except Exception:
                    # Fallback: read and parse the __init__.py file
                    print(f"[AniMate Pro] Falling back to file parsing for version")
                    addon_dir = os.path.dirname(os.path.abspath(__file__))
                    init_file = os.path.join(addon_dir, "__init__.py")
                    bl_info = None
                    if os.path.exists(init_file):
                        with open(init_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Look for bl_info dictionary using regex
                            import re

                            pattern = r'bl_info\s*=\s*\{[^}]*"version"\s*:\s*\([^)]*\)[^}]*\}'
                            match = re.search(pattern, content, re.DOTALL)
                            if match:
                                # Execute just the bl_info assignment
                                local_vars = {}
                                exec(match.group(0), {}, local_vars)
                                bl_info = local_vars.get("bl_info")

                    if bl_info and "version" in bl_info:
                        current_version = ".".join(str(v) for v in bl_info["version"])
                        print(f"[AniMate Pro] Got version from file parsing: {current_version}")

                    else:
                        current_version = "Unknown"
                        print(f"[AniMate Pro] Failed to parse version from file")

            except Exception as e:
                current_version = "Unknown"
                print(f"[AniMate Pro] Version detection error: {e}")

            # Check for existing version tracking file
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            parent = os.path.dirname(addon_dir)
            pathfile = os.path.join(parent, "AniMateProUserPrefsPath.json")

            stored_version = None
            stored_path = None
            version_file_exists = os.path.isfile(pathfile)

            if version_file_exists:
                try:
                    with open(pathfile, "r") as f:
                        data = json.load(f)
                    stored_version = data.get("addon_version")
                    stored_path = data.get("auto_save_path")
                except Exception as e:
                    print(f"[AniMate Pro] Error reading version file: {e}")

            # Determine conditions
            is_first_install = not version_file_exists  # No version file = first install
            is_fresh_install = prefs.fresh_install  # Fresh install flag is set (regardless of version file)
            is_version_update = stored_version and stored_version != current_version
            has_default_categories = any(cat.default_cat_id for cat in prefs.ui_categories)

            # Debug logging
            print(f"[AniMate Pro] Version check:")
            print(f"  - Current version: {current_version}")
            print(f"  - Stored version: {stored_version}")
            print(f"  - Version file exists: {version_file_exists}")
            print(f"  - Fresh install flag: {prefs.fresh_install}")
            print(f"  - Addon up to date flag: {prefs.addon_up_to_date}")
            print(f"  - Is first install: {is_first_install}")
            print(f"  - Is fresh install: {is_fresh_install}")
            print(f"  - Is version update: {is_version_update}")
            print(f"  - Has default categories: {has_default_categories}")

            # Clear flag before any operations that might trigger dialogs
            _startup_version_check_in_progress = False

            # Condition 1: First install ever (no version file exists)
            if is_first_install:
                print(f"[AniMate Pro] First install detected - setting up defaults")
                restore_defaults_and_update_version()
                bpy.ops.amp.restore_default_ui_content(skip_confirmation=True)
                return {"FINISHED"}

            # Condition 2: Fresh install (fresh_install flag is True, regardless of version file)
            if is_fresh_install:
                print(f"[AniMate Pro] Fresh install detected")
                if version_file_exists:
                    _version_dialog_shown = True
                    prefs.addon_up_to_date = False
                    bpy.ops.amp.version_update_dialog(
                        "INVOKE_DEFAULT",
                        stored_version=stored_version or "",
                        current_version=current_version,
                        saved_preferences_path=os.path.abspath(os.path.expanduser(stored_path or "")),
                    )
                    return {"FINISHED"}
                else:
                    print(f"[AniMate Pro] No previous settings file, setting up defaults")
                    restore_defaults_and_update_version()
                    bpy.ops.amp.restore_default_ui_content(skip_confirmation=True)
                    return {"FINISHED"}

            # Condition 3 & 4: Version Update (check this BEFORE the "no action needed" check)
            if is_version_update:
                print(f"[AniMate Pro] Version update detected: {stored_version} → {current_version}")

                # Mark dialog as shown to prevent duplicates
                _version_dialog_shown = True

                if stored_path and os.path.isfile(os.path.abspath(os.path.expanduser(stored_path))):
                    # Condition 4: Version Update with saved preferences
                    prefs.addon_up_to_date = False
                    bpy.ops.amp.version_update_dialog(
                        "INVOKE_DEFAULT",
                        stored_version=stored_version,
                        current_version=current_version,
                        saved_preferences_path=os.path.abspath(os.path.expanduser(stored_path)),
                    )
                else:
                    # Condition 3: Version Update without saved preferences
                    prefs.addon_up_to_date = False
                    bpy.ops.amp.version_update_dialog(
                        "INVOKE_DEFAULT",
                        stored_version=stored_version,
                        current_version=current_version,
                        saved_preferences_path="",
                    )
                return {"FINISHED"}

            # Condition 5: No Action Needed - addon is up to date and has categories
            if not is_version_update and has_default_categories:
                print(f"[AniMate Pro] No action needed - addon is up to date")
                return {"FINISHED"}

            # Fallback: Missing default categories and pie menus
            if not has_default_categories:
                print(f"[AniMate Pro] Missing default content, restoring...")
                restore_defaults_and_update_version()
                bpy.ops.amp.restore_default_ui_content(skip_confirmation=True)

            # # Register a delayed reload for icons and UI refresh
            # def delayed_icon_reload():
            #     try:
            #         from .utils.customIcons import reload_icons

            #         reload_icons()
            #         print(f"[AniMate Pro] Reloaded icons after version update")
            #         for screen in bpy.data.screens:
            #             for area in screen.areas:
            #                 area.tag_redraw()

            #     except Exception as e:
            #         print(f"[AniMate Pro] Error during delayed reload: {e}")

            #     return None

            # bpy.app.timers.register(delayed_icon_reload, first_interval=0.5)

            return {"FINISHED"}

        finally:
            # Always clear the flag when done
            _startup_version_check_in_progress = False


def validate_auto_save_path(self, context):
    # Ensure the path ends with .json
    if self.auto_save_path and not self.auto_save_path.lower().endswith(".json"):
        self.auto_save_path += ".json"

    # Check if the path is valid
    if self.auto_save_path and not os.path.isdir(os.path.dirname(self.auto_save_path)):
        print(f"[AniMate Pro] Invalid auto-save path: {self.auto_save_path}")
        return  # must return None for update callback

    # Only write version info if not in fresh install mode AND not during startup checks
    global _startup_version_check_in_progress
    if not self.fresh_install and not _startup_version_check_in_progress:
        _write_userprefs_path(self.auto_save_path)


def _load_preferences(filepath, prefs):
    """Load preferences from a JSON file"""
    import json

    try:
        # Validate file exists and is readable
        if not os.path.isfile(filepath):
            print(f"[AniMate Pro] File not found: {filepath}")
            return {"CANCELLED"}

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate that data is a dictionary
        if not isinstance(data, dict):
            print(f"[AniMate Pro] Invalid preferences format - not a dictionary")
            return {"CANCELLED"}

        # Remove forge_version from imported data to let the script set it
        data.pop("forge_version", None)

        # Use the preferences object's from_dict method
        prefs.from_dict(data)

        print(f"[AniMate Pro] Successfully loaded preferences from {filepath}")

        return {"FINISHED"}

    except json.JSONDecodeError as e:
        print(f"[AniMate Pro] JSON decode error: {e}")
        return {"CANCELLED"}
    except FileNotFoundError as e:
        print(f"[AniMate Pro] File not found: {e}")
        return {"CANCELLED"}
    except PermissionError as e:
        print(f"[AniMate Pro] Permission error: {e}")
        return {"CANCELLED"}
    except Exception as e:
        print(f"[AniMate Pro] Unexpected error loading preferences: {e}")
        import traceback

        traceback.print_exc()
        return {"CANCELLED"}

    # def execute(self, context):
    #     bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
    #     bpy.ops.preferences.addon_show(module=base_package)

    #     return {"FINISHED"}


class AMP_OT_OpenPreferencesFullscreen(bpy.types.Operator):
    """Open AniMate Pro update popup"""

    bl_idname = "amp.open_preferences_fullscreen"
    bl_label = "Update AniMate Pro Preferences"
    bl_description = "Open AniMate Pro update popup to complete version update setup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Open the version update dialog instead of preferences
        bpy.ops.amp.version_update_dialog("INVOKE_DEFAULT")
        return {"FINISHED"}


class AMP_OT_ExportPreferences(bpy.types.Operator, ExportHelper):
    bl_idname = "amp.export_preferences"
    bl_label = "Export Preferences"
    bl_description = "Export add-on preferences to a JSON file"

    filename_ext = ".json"
    filter_glob: StringProperty(
        default="*.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    def invoke(self, context, event):
        if not self.filepath:
            user_home_dir = os.path.expanduser("~")
            os.makedirs(user_home_dir, exist_ok=True)
            default_filepath = os.path.join(user_home_dir, "AMP_preferences.json")
            self.filepath = default_filepath
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        prefs = context.preferences.addons[base_package].preferences
        return self.save_preferences(self.filepath, prefs)

    def save_preferences(self, filepath, prefs):
        try:
            pref_dict = prefs.to_dict()
            # do not export the fresh_install flag and forge_version
            pref_dict.pop("fresh_install", None)
            pref_dict.pop("forge_version", None)
            json_str = json.dumps(pref_dict, indent=4)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
            self.report({"INFO"}, f"Preferences successfully saved to {filepath}")
            return {"FINISHED"}
        except TypeError as e:
            print(f"Serialization failed: {e}")
            self.report({"ERROR"}, f"Failed to serialize preferences: {e}")
            return {"CANCELLED"}
        except Exception as e:
            print(f"Failed to save preferences: {e}")
            self.report({"ERROR"}, f"Failed to save preferences: {e}")
            return {"CANCELLED"}


class AMP_OT_ImportPreferences(bpy.types.Operator, ImportHelper):
    bl_idname = "amp.import_preferences"
    bl_label = "Import Preferences"

    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={"HIDDEN"},
        maxlen=255,
    )

    def execute(self, context):
        prefs = context.preferences.addons[base_package].preferences
        result = _load_preferences(self.filepath, prefs)

        if result == {"FINISHED"}:
            self.report({"INFO"}, f"Preferences successfully imported from {self.filepath}")

        else:
            self.report({"ERROR"}, f"Failed to import preferences from {self.filepath}")

        return result


class AMP_OT_AutoSavePreferences(bpy.types.Operator):
    bl_idname = "amp.auto_save_preferences"
    bl_label = "Auto Save Preferences"

    def execute(self, context):
        prefs = context.preferences.addons[base_package].preferences

        auto_save_path = prefs.auto_save_path
        if not auto_save_path:
            # Define default auto-save path, e.g., in the user's home directory
            user_home_dir = os.path.expanduser("~")
            auto_save_path = os.path.join(user_home_dir, "AMP_preferences.json")
            prefs.auto_save_path = auto_save_path

        return self.save_preferences_with_backup(auto_save_path, prefs)

    def save_preferences_with_backup(self, filepath, prefs):
        try:
            # Create backup if file exists
            if os.path.exists(filepath):
                backup_path = filepath.replace(".json", ".back")

                # Delete existing backup if it exists
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    print(f"[AMP_AniMatePro] Deleted existing backup: {backup_path}")

                # Create new backup
                os.rename(filepath, backup_path)
                print(f"[AMP_AniMatePro] Created backup: {backup_path}")

            # Save current preferences
            data = prefs.to_dict()
            # do not auto-save the fresh_install flag and forge_version
            data.pop("fresh_install", None)
            data.pop("forge_version", None)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            # Update the path file with version info when auto-saving
            _write_userprefs_path(filepath)

            self.report({"INFO"}, f"Preferences auto-saved to {filepath}")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Failed to auto-save preferences: {e}")
            return {"CANCELLED"}


# Add popup panel hotkey management functions
def initialize_popup_panel_hotkeys():
    """Initialize all popup panel hotkeys on addon startup"""
    try:
        from .ui.addon_ui_popup_utils import clear_all_popup_panel_hotkeys, refresh_all_popup_panel_hotkeys

        # first purge any leftovers (even those not in our amp_popup_keymaps dict)
        clear_all_popup_panel_hotkeys()
        # now re-register
        refresh_all_popup_panel_hotkeys()
        print("[AMP] Popup panel hotkeys initialized")
    except Exception as e:
        print(f"[AMP] Error initializing popup panel hotkeys: {e}")


def cleanup_popup_panel_hotkeys():
    """Clean up all popup panel hotkeys on addon shutdown"""
    try:
        from .ui.addon_ui_popup_utils import clear_all_popup_panel_hotkeys

        clear_all_popup_panel_hotkeys()
        print("[AMP] Popup panel hotkeys cleaned up")
    except Exception as e:
        print(f"[AMP] Error cleaning up popup panel hotkeys: {e}")


# Register classes
classes = (
    AMP_OT_deactivate_other_keymaps_for_operator,
    AMP_OT_CaptureKeyInput,
    AMP_OT_CaptureKeyInputPopupPanel,
    AMP_PT_InsertKeyPreferencesVIEW,
    AMP_PT_InsertKeyPreferencesGraph,
    AMP_PT_InsertKeyPreferencesDope,
    AMP_OT_TogglePanelVisibility,
    AMP_OT_ResetPreferencesToDefaults,
    AMP_OT_VersionUpdateDialog,
    AMP_OT_VersionUpdateAction,
    AMP_OT_TryReloadUserPrefs,
    AMP_OT_OpenPreferencesFullscreen,
    AMP_OT_ExportPreferences,
    AMP_OT_ImportPreferences,
    AMP_OT_AutoSavePreferences,
)


# Register classes and properties
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Initialize popup panel hotkeys after registration
    initialize_popup_panel_hotkeys()


# Unregister classes and properties
def unregister():
    # Clean up popup panel hotkeys before unregistration
    cleanup_popup_panel_hotkeys()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


##################
## operators.py ##
##################
