import bpy
from bpy.types import Menu, Panel
from ..utils import get_prefs
from ..utils.customIcons import get_icon

# Global storage for registered popup panel keymaps
amp_popup_keymaps = {}

# Global storage for registered popup panel classes
amp_popup_classes = {}

# Space type mapping for keymap registration
SPACE_TYPE_ITEMS = [
    ("ALL_SPACES", "All Spaces", "Register hotkey in all spaces"),
    ("VIEW_3D", "View 3D", "Register hotkey in View 3D"),
    ("IMAGE_EDITOR", "Image Editor", "Register hotkey in Image Editor"),
    ("NODE_EDITOR", "Node Editor", "Register hotkey in Node Editor"),
    ("SEQUENCE_EDITOR", "Sequence Editor", "Register hotkey in Sequence Editor"),
    ("CLIP_EDITOR", "Clip Editor", "Register hotkey in Clip Editor"),
    ("DOPESHEET_EDITOR", "Dopesheet Editor", "Register hotkey in Dopesheet Editor"),
    ("GRAPH_EDITOR", "Graph Editor", "Register hotkey in Graph Editor"),
    ("NLA_EDITOR", "Nla Editor", "Register hotkey in Nla Editor"),
    ("TEXT_EDITOR", "Text Editor", "Register hotkey in Text Editor"),
    ("CONSOLE", "Console", "Register hotkey in Console"),
    ("INFO", "Info", "Register hotkey in Info"),
    ("OUTLINER", "Outliner", "Register hotkey in Outliner"),
    ("PROPERTIES", "Properties", "Register hotkey in Properties"),
    ("FILE_BROWSER", "File Browser", "Register hotkey in File Browser"),
]

# Space type to keymap name mapping
SPACE_TYPE_TO_KEYMAP = {
    "ALL_SPACES": "Window",
    "VIEW_3D": "3D View",
    "IMAGE_EDITOR": "Image",
    "NODE_EDITOR": "Node Editor",
    "SEQUENCE_EDITOR": "Sequencer",
    "CLIP_EDITOR": "Clip",
    "DOPESHEET_EDITOR": "Dopesheet",
    "GRAPH_EDITOR": "Graph Editor",
    "NLA_EDITOR": "NLA Editor",
    "TEXT_EDITOR": "Text",
    "CONSOLE": "Console",
    "INFO": "Info",
    "OUTLINER": "Outliner",
    "PROPERTIES": "Property Editor",
    "FILE_BROWSER": "File Browser",
}


def get_popup_panel_class_name(popup_panel_index):
    """Generate a unique class name for a popup panel"""
    return f"AMP_OT_PopupPanel_{popup_panel_index}"


def get_popup_panel_idname(popup_panel_index):
    """Generate a unique bl_idname for a popup panel"""
    return f"amp.popup_panel_{popup_panel_index}"


def create_dynamic_popup_panel_class(popup_panel, popup_panel_index):
    """Create a dynamic popup panel class based on popup panel configuration"""

    class_name = get_popup_panel_class_name(popup_panel_index)
    idname = get_popup_panel_idname(popup_panel_index)

    def draw_popup_panel(self, context):
        """Draw the popup panel using the same layout system as side panels

        This ensures that popup panels respect the same category placement settings
        (TOP, LEFT, RIGHT) and styling options as the side panels, providing a
        consistent user experience across all UI areas.
        """
        layout = self.layout

        # Import necessary functions from addon_ui
        from .addon_ui import _draw_rows_for_category

        prefs = get_prefs()
        region_key = "popup"

        # Get pinned categories from popup panel (only respect pin_global)
        popup_categories = [cat for cat in popup_panel.categories if getattr(cat, "pin_global", False)]

        if not popup_categories:
            layout.label(text="No categories available", icon="INFO")
            return

        # Ensure popup_active properties exist and are properly set
        for i, cat in enumerate(popup_categories):
            if not hasattr(cat, "popup_active"):
                cat.popup_active = i == 0  # First category active by default
            # Add popup_pin property for compatibility with the layout system
            if not hasattr(cat, "popup_pin"):
                cat.popup_pin = True  # All globally pinned categories in popup are considered pinned for this region

        # Determine which categories are pinned for this region
        pinned = [
            cat
            for cat in popup_categories
            if getattr(cat, "pin_global", False) and getattr(cat, f"{region_key}_pin", True)
        ]

        # Show category toggles only if there are multiple categories
        show_category_icons = len(pinned) > 1

        # Open (active) categories
        open_cats = [cat for cat in pinned if getattr(cat, "popup_active", False)]

        # Build container according to prefs.cat_placement
        content_area = None
        if prefs.cat_placement in ("TOP"):
            # Categories at top: column layout with categories above content
            main_col = layout.column(align=prefs.sections_box_container)

            if show_category_icons:
                # Calculate how many categories can fit per row based on region width
                try:
                    region_width = context.region.width / max(0.001, context.preferences.view.ui_scale)
                except Exception:
                    # Fallback to popup width if region is unavailable
                    region_width = getattr(popup_panel, "popup_width", 400)
                scaled_button_width = 28 * getattr(prefs, "cat_scale", 1.0)
                categories_per_row = max(1, int(region_width // max(1, int(scaled_button_width))))

                # Create category icons container at the top
                cat_outer = main_col.box() if getattr(prefs, "cat_box_container", False) else main_col

                # For row layout, create multiple rows as needed
                for i in range(0, len(pinned), categories_per_row):
                    cat_pre_row = cat_outer.row()
                    cat_pre_row.alignment = "CENTER"
                    cat_row = cat_pre_row.row()
                    cat_row.scale_x = getattr(prefs, "cat_scale", 1.0)
                    cat_row.scale_y = getattr(prefs, "cat_scale", 1.0)

                    # Add categories to this row
                    row_categories = pinned[i : i + categories_per_row]
                    for cat in row_categories:
                        icon_args = get_icon(cat.icon) if getattr(cat, "icon", None) else {"icon": "RADIOBUT_OFF"}
                        if isinstance(icon_args, dict):
                            cat_row.prop(cat, "popup_active", text="", **icon_args, emboss=True)
                        else:
                            cat_row.prop(cat, "popup_active", text="", icon=icon_args, emboss=True)

            # Content area below categories
            if getattr(prefs, "sections_box_container", False) and open_cats:
                content_area = main_col.box().column()
            else:
                content_area = main_col.column()

        else:
            # LEFT or RIGHT placement: horizontal layout
            row = layout.row(align=getattr(prefs, "sections_box_container", False))

            if show_category_icons:
                if prefs.cat_placement == "LEFT":
                    # Category icons first
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

                    # Then content
                    if getattr(prefs, "sections_box_container", False) and open_cats:
                        category_box = row.box()
                        content_area = category_box.column()
                    else:
                        content_area = row.column()

                else:  # RIGHT placement
                    # Content first
                    if getattr(prefs, "sections_box_container", False) and open_cats:
                        category_box = row.box()
                        content_area = category_box.column()
                    else:
                        content_area = row.column()

                    # Then category icons
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
                # No category icons to show, just content area
                if getattr(prefs, "sections_box_container", False) and open_cats:
                    category_box = row.box()
                    content_area = category_box.column()
                else:
                    content_area = row.column()

        # Safety fallback
        if content_area is None:
            content_area = layout.column()

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

    def invoke_popup_panel(self, context, event):
        """Custom invoke function that uses the popup panel's width setting"""
        prefs = get_prefs()
        if popup_panel_index < len(prefs.popup_panels):
            popup_panel_data = prefs.popup_panels[popup_panel_index]
            width = getattr(popup_panel_data, "popup_width", 400)
        else:
            width = 400  # Fallback width
        return context.window_manager.invoke_popup(self, width=width)

    # Create the dynamic class - using Operator instead of Panel for proper popup behavior with invoke_popup
    popup_class = type(
        class_name,
        (bpy.types.Operator,),
        {
            "bl_idname": idname,
            "bl_label": popup_panel.name,
            "bl_options": {"REGISTER", "UNDO"},
            "popup_panel_index": popup_panel_index,  # Store the index for reference
            "invoke": invoke_popup_panel,
            "execute": lambda self, context: {"FINISHED"},
            "draw": draw_popup_panel,
            "__module__": __name__,
        },
    )

    return popup_class


def find_conflicting_popup_panel_hotkey(hotkey_string, space_type, exclude_index=None):
    """Find if any existing popup panel uses the same hotkey combination"""
    prefs = get_prefs()

    for i, popup_panel in enumerate(prefs.popup_panels):
        # Skip the popup panel we're currently setting (to allow re-setting the same hotkey)
        if exclude_index is not None and i == exclude_index:
            continue

        # Check if this popup panel has the same hotkey combination and space
        if popup_panel.hotkey_string == hotkey_string and popup_panel.hotkey_space == space_type:
            return i

    return None


def register_popup_panel_hotkey(popup_panel, popup_panel_index):
    """Register a hotkey for a popup panel using addon keyconfigs"""
    if not popup_panel.hotkey_string:
        return False

    try:
        # Check for conflicting hotkeys and unregister them first
        conflicting_index = find_conflicting_popup_panel_hotkey(
            popup_panel.hotkey_string, popup_panel.hotkey_space, exclude_index=popup_panel_index
        )

        if conflicting_index is not None:
            print(f"[AMP] Found conflicting popup panel hotkey at index {conflicting_index}, unregistering...")
            unregister_popup_panel_hotkey(conflicting_index)

            # Clear the hotkey string from the conflicting popup panel
            prefs = get_prefs()
            if 0 <= conflicting_index < len(prefs.popup_panels):
                conflicting_popup_panel = prefs.popup_panels[conflicting_index]
                conflicting_popup_panel.hotkey_string = ""
                conflicting_popup_panel.is_capturing_hotkey = False

        # Parse the hotkey string (e.g., "CTRL+SHIFT+T")
        hotkey_parts = popup_panel.hotkey_string.split("+")
        key = hotkey_parts[-1]  # Last part is the key

        # Check for modifiers
        ctrl = "CTRL" in hotkey_parts
        alt = "ALT" in hotkey_parts
        shift = "SHIFT" in hotkey_parts
        oskey = "OSKEY" in hotkey_parts

        # Unregister existing hotkey first for this popup panel
        unregister_popup_panel_hotkey(popup_panel_index)

        # Create and register the dynamic popup panel class
        popup_class = create_dynamic_popup_panel_class(popup_panel, popup_panel_index)

        # Unregister old class if it exists
        class_key = f"popup_{popup_panel_index}"
        if class_key in amp_popup_classes:
            try:
                bpy.utils.unregister_class(amp_popup_classes[class_key])
            except:
                pass

        bpy.utils.register_class(popup_class)
        amp_popup_classes[class_key] = popup_class

        # Get keymap configuration
        kc = bpy.context.window_manager.keyconfigs.addon
        if not kc:
            print(f"[AMP] No addon keyconfig available for popup panel {popup_panel_index}")
            return False

        space_type = popup_panel.hotkey_space
        keymap_name = SPACE_TYPE_TO_KEYMAP.get(space_type)

        # Create keymap like in example
        if space_type == "ALL_SPACES":
            # For all spaces, use Window keymap without space_type
            km = kc.keymaps.new(name=keymap_name)
        else:
            # For specific spaces, include space_type
            km = kc.keymaps.new(name=keymap_name, space_type=space_type)

        # Add keymap item - directly call the popup operator
        kmi = km.keymap_items.new(
            popup_class.bl_idname,
            key,
            "PRESS",
            ctrl=ctrl,
            alt=alt,
            shift=shift,
            oskey=oskey,
            repeat=False,
        )

        # Store like in example for later cleanup
        amp_popup_keymaps[class_key] = (km, kmi)

        print(f"[AMP] Registered popup panel hotkey: {popup_panel.hotkey_string} in {space_type}")
        return True

    except Exception as e:
        print(f"[AMP] Error registering popup panel hotkey {popup_panel_index}: {e}")
        return False


def unregister_popup_panel_hotkey(popup_panel_index):
    """Unregister a popup panel hotkey - simplified like example"""
    key = f"popup_{popup_panel_index}"
    if key in amp_popup_keymaps:
        try:
            km, kmi = amp_popup_keymaps[key]
            km.keymap_items.remove(kmi)
            del amp_popup_keymaps[key]
            print(f"[AMP] Unregistered popup panel hotkey for index {popup_panel_index}")
        except Exception as e:
            print(f"[AMP] Error unregistering popup panel hotkey {popup_panel_index}: {e}")

    # Also unregister the popup panel class
    if key in amp_popup_classes:
        try:
            bpy.utils.unregister_class(amp_popup_classes[key])
            del amp_popup_classes[key]
            print(f"[AMP] Unregistered popup panel class for index {popup_panel_index}")
        except Exception as e:
            print(f"[AMP] Error unregistering popup panel class {popup_panel_index}: {e}")


def update_popup_panel_hotkey(popup_panel, popup_panel_index):
    """Update a popup panel hotkey (unregister old, register new)"""
    unregister_popup_panel_hotkey(popup_panel_index)
    if popup_panel.hotkey_string:
        register_popup_panel_hotkey(popup_panel, popup_panel_index)


def refresh_all_popup_panel_hotkeys():
    """Refresh all popup panel hotkeys based on current preferences"""
    prefs = get_prefs()

    # Clear all existing hotkeys
    clear_all_popup_panel_hotkeys()

    # Register hotkeys for popup panels with hotkey strings
    for i, popup_panel in enumerate(prefs.popup_panels):
        if popup_panel.hotkey_string:
            register_popup_panel_hotkey(popup_panel, i)


def clear_all_popup_panel_hotkeys():
    """Clear all registered popup panel hotkeys - like example"""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # Remove any tracked items
        for km, kmi in amp_popup_keymaps.values():
            try:
                km.keymap_items.remove(kmi)
            except:
                pass
        # Also remove *any* stray popup panel items in addon keyconfig
        for km in kc.keymaps:
            for kmi in list(km.keymap_items):
                if kmi.idname.startswith("AMP_POPUP_PT_"):
                    km.keymap_items.remove(kmi)
    amp_popup_keymaps.clear()

    # Unregister all popup panel classes
    for popup_class in list(amp_popup_classes.values()):
        try:
            bpy.utils.unregister_class(popup_class)
        except:
            pass
    amp_popup_classes.clear()


def get_hotkey_display_string(popup_panel):
    """Get a display string for the popup panel hotkey"""
    if not popup_panel.hotkey_string:
        return "No Hotkey"

    return popup_panel.hotkey_string


def get_space_display_string(space_type):
    """Get a display string for the space type"""
    for item in SPACE_TYPE_ITEMS:
        if item[0] == space_type:
            return item[1]
    return "Unknown Space"


def find_user_keyconfig_for_popup(popup_panel_index):
    """Find the user keyconfig for a popup panel (for UI display)"""
    key = f"popup_{popup_panel_index}"
    if key not in amp_popup_keymaps:
        return None

    km, kmi = amp_popup_keymaps[key]

    try:
        # Try to find matching user keymap using the popup operator's bl_idname
        popup_class = amp_popup_classes.get(key)
        if not popup_class:
            return kmi

        operator_idname = popup_class.bl_idname

        # Try to find matching user keymap like in example
        for item in bpy.context.window_manager.keyconfigs.user.keymaps[km.name].keymap_items:
            found_item = False
            if operator_idname == item.idname:
                found_item = True
                # No need to check properties for our popup operators
            if found_item:
                return item
    except:
        pass

    print(f"[AMP] Using addon keymap for popup panel {popup_panel_index} (won't be saved)")
    return kmi
