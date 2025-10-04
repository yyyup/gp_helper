import bpy
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

# Import necessary utilities for pie menu hotkey management
from ..utils import get_prefs, ptr_to_dict, dict_to_ptr


def update_popup_panel_hotkey_space(self, context):
    """Update callback for popup panel hotkey space changes"""
    # Skip update if we're in the middle of capturing a hotkey or other operations
    if getattr(self, "is_capturing_hotkey", False):
        return

    # Import here to avoid circular imports
    try:
        from ..ui.addon_ui_popup_utils import update_popup_panel_hotkey

        # Find the index of this popup panel in the preferences
        prefs = get_prefs()
        popup_panel_index = -1
        for i, popup_panel in enumerate(prefs.popup_panels):
            if popup_panel == self:
                popup_panel_index = i
                break

        if popup_panel_index >= 0:
            if self.hotkey_string.strip():
                # Re-register the hotkey with the new space
                # This will automatically handle conflict checking and deregistration
                update_popup_panel_hotkey(self, popup_panel_index)
            # If no hotkey is set, no action needed
    except Exception as e:
        print(f"[AMP] Error updating popup panel hotkey space: {e}")


def update_popup_panel_hotkey_string(self, context):
    """Update callback for popup panel hotkey string changes"""
    # Skip update if we're in the middle of capturing a hotkey or other operations
    if getattr(self, "is_capturing_hotkey", False):
        return

    # Import here to avoid circular imports
    try:
        from ..ui.addon_ui_popup_utils import update_popup_panel_hotkey

        # Find the index of this popup panel in the preferences
        prefs = get_prefs()
        popup_panel_index = -1
        for i, popup_panel in enumerate(prefs.popup_panels):
            if popup_panel == self:
                popup_panel_index = i
                break

        if popup_panel_index >= 0:
            if self.hotkey_string.strip():
                # Register/update the hotkey
                update_popup_panel_hotkey(self, popup_panel_index)
            else:
                # Clear the hotkey if string is empty
                from ..ui.addon_ui_popup_utils import unregister_popup_panel_hotkey

                unregister_popup_panel_hotkey(popup_panel_index)
    except Exception as e:
        print(f"[AMP] Error updating popup panel hotkey: {e}")


# Global flags to prevent recursive updates
_updating_from_global = False
_updating_from_individual = False


def update_pin_global(self, context):
    """Update all individual pins based on the global pin state"""
    global _updating_from_global, _updating_from_individual

    # Prevent recursion - don't update if we're already in an individual pin update
    if _updating_from_individual:
        return

    _updating_from_global = True
    try:
        if self.pin_global:
            # If turning on global pin, turn on all individual pins if none were on
            all_pins = [
                self.top_nla_pin,
                self.top_graph_pin,
                self.top_dope_pin,
                self.side_nla_pin,
                self.side_graph_pin,
                self.side_dope_pin,
                self.side_view_pin,
            ]

            if not any(all_pins):
                # No pins were on, turn them all on
                self.top_nla_pin = True
                self.top_graph_pin = True
                self.top_dope_pin = True
                self.side_nla_pin = True
                self.side_graph_pin = True
                self.side_dope_pin = True
                self.side_view_pin = True
        # else:
        #     # If turning off global pin, turn off all individual pins
        #     self.top_nla_pin = False
        #     self.top_graph_pin = False
        #     self.top_dope_pin = False
        #     self.side_nla_pin = False
        #     self.side_graph_pin = False
        #     self.side_dope_pin = False
        #     self.side_view_pin = False
    finally:
        _updating_from_global = False


def update_individual_pin(self, context):
    """Update global pin state based on individual pin changes"""
    global _updating_from_global, _updating_from_individual

    # Prevent recursion - don't update if we're already in a global pin update
    if _updating_from_global:
        return

    _updating_from_individual = True
    try:
        all_pins = [
            self.top_nla_pin,
            self.top_graph_pin,
            self.top_dope_pin,
            self.side_nla_pin,
            self.side_graph_pin,
            self.side_dope_pin,
            self.side_view_pin,
        ]

        if any(all_pins):
            # If any pin is on, ensure global pin is on
            self.pin_global = True
        else:
            # If all pins are off, turn off global pin
            self.pin_global = False
    finally:
        _updating_from_individual = False


# --------------------------------------------------------------

# -----------------------------------------------------------------------------
# Property Groups
# -----------------------------------------------------------------------------


# class SectionRow(PropertyGroup):
#     is_subsection: BoolProperty(name="Subsection", default=False)
#     name: StringProperty(name="Section Name", default="Section")
#     icon: StringProperty(name="Icon", default="")
#     style: EnumProperty(
#         name="Style",
#         items=[("PLAIN", "Plain", ""), ("BOX", "Box", ""), ("BOX_TITLE", "Box Title", "")],
#         default="PLAIN",
#     )
#     height: FloatProperty(name="Height", default=1.0, min=1.0, max=2.0)

#     # Open/closed state for each context
#     top_nla_open: BoolProperty(default=False)
#     top_graph_open: BoolProperty(default=False)
#     top_dope_open: BoolProperty(default=False)
#     side_nla_open: BoolProperty(default=False)
#     side_graph_open: BoolProperty(default=False)
#     side_dope_open: BoolProperty(default=False)
#     side_view_open: BoolProperty(default=False)
#     popup_open: BoolProperty(default=False)
#     prefs_open: BoolProperty(default=False)

#     def to_dict(self):
#         return {
#             prop.identifier: getattr(self, prop.identifier)
#             for prop in self.bl_rna.properties
#             if not prop.is_readonly and prop.identifier != "rna_type"
#         }

#     def from_dict(self, data):
#         for k, v in data.items():
#             if hasattr(self, k):
#                 setattr(self, k, v)


# class ButtonRow(PropertyGroup):
#     amp_button: StringProperty(name="Button ID", default="")
#     name: StringProperty(name="Display Name", default="")

#     def to_dict(self):
#         return {
#             prop.identifier: getattr(self, prop.identifier)
#             for prop in self.bl_rna.properties
#             if not prop.is_readonly and prop.identifier != "rna_type"
#         }

#     def from_dict(self, data):
#         for k, v in data.items():
#             if hasattr(self, k):
#                 setattr(self, k, v)


class ButtonEntry(PropertyGroup):
    name: StringProperty(name="Name", default="Button")
    button_id: StringProperty(name="Button ID", default="operator")
    icon: StringProperty(name="Icon", default="NONE")
    operator_context: StringProperty(name="Operator Context", default="INVOKE_DEFAULT")
    operator_idname: StringProperty(name="Operator ID Name", default="")
    custom: BoolProperty(name="Is Custom", default=False)
    script: StringProperty(name="Script Name", default="")
    text_block_name: StringProperty(name="Text Block Name", default="")
    spacer_width: FloatProperty(name="Spacer Width", default=0.5, min=0.1, max=10.0)
    display_name: StringProperty(name="Display Name", default="")

    button_path: StringProperty(
        name="Button Path",
        default="",
        description="Path of the button to the opoerator or property deppending on the type of button",
    )
    property_slider: BoolProperty(
        name="Show as Slider", default=False, description="Display property as a slider instead of regular input"
    )

    operator_properties: StringProperty(
        name="Operator Properties",
        default="",
        description="JSON string of operator properties (e.g., {'linked': False, 'mode': 'TRANSLATION'})",
    )

    def to_dict(self):
        """Converts this ButtonEntry to a dictionary."""
        return ptr_to_dict(self)

    def from_dict(self, data):
        """Populates this ButtonEntry from a dictionary."""
        dict_to_ptr(self, data)


class RowGroup(PropertyGroup):
    name: StringProperty(name="Name", default="Row")  # Used for SECTION type
    row_type: EnumProperty(
        name="Row Type",
        items=[("BUTTON", "Button Row", ""), ("SECTION", "Section", ""), ("PANEL", "Panel", "")],
        default="BUTTON",
    )
    buttons: CollectionProperty(type=ButtonEntry)
    active_button_index: IntProperty()
    alignment: EnumProperty(
        name="Alignment",
        items=[
            ("LEFT", "Left", "Align buttons to the left", "ALIGN_LEFT", 0),
            ("CENTER", "Center", "Align buttons to the center", "ALIGN_CENTER", 1),
            ("RIGHT", "Right", "Align buttons to the right", "ALIGN_RIGHT", 2),
            ("EXPAND", "Expand", "Expand buttons to fill the row", "ALIGN_JUSTIFY", 3),
            ("GRID", "Grid", "Arrange buttons in a grid", "VIEW_ORTHO", 4),
        ],
        default="EXPAND",
    )
    # Properties for SECTION type
    icon: StringProperty(name="Icon", default="NONE")  # For section icon

    panel_id: StringProperty(name="Panel ID", default="", description="ID of the panel function to call")
    custom_panel: StringProperty(
        name="Custom Panel Name",
        default="",
        description="Name of the Blender panel class to draw (e.g., VIEW3D_PT_context_properties)",
    )

    # Panel rows should have the same properties as sections
    style: EnumProperty(
        name="Panel Style",
        items=[
            ("DEFAULT", "Plain", "No box around title or content", "SELECT_SET", 0),
            ("BOX", "Box all", "Box around title and content", "MESH_PLANE", 1),
            ("BOX_TITLE", "Title Box", "Box around title only", "TOPBAR", 2),
            ("BOX_CONTENT", "Content Box", "Box around content only", "STICKY_UVS_LOC", 3),
        ],
        default="BOX",
    )
    is_subsection: BoolProperty(name="Is Subpanel", default=False)

    # Per-region open state for sections and panels
    side_view_open: BoolProperty(name="View3D Open", default=False)
    side_graph_open: BoolProperty(name="Graph Open", default=False)
    side_dope_open: BoolProperty(name="DopeSheet Open", default=False)
    side_nla_open: BoolProperty(name="NLA Open", default=False)
    top_graph_open: BoolProperty(name="Top Graph Open", default=False)
    top_dope_open: BoolProperty(name="Top DopeSheet Open", default=False)
    top_nla_open: BoolProperty(name="Top NLA Open", default=False)
    popup_open: BoolProperty(name="Pie Menu Open", default=False)

    # Display control for top panels
    display_top: BoolProperty(
        name="Display in Top Panels", default=True, description="Show this section/panel in top panels"
    )

    # Display control for side panels
    display_side: BoolProperty(
        name="Display in Side Panels", default=True, description="Show this section/panel in side panels"
    )

    # Conditional expression for when this row should be displayed
    conditional: StringProperty(
        name="Conditional Expression",
        default="",
        description="Python expression that determines if this row is displayed (e.g., 'bpy.context.active_object'). Leave empty to always show.",
    )

    def to_dict(self):
        """Converts this RowGroup to a dictionary."""
        data = ptr_to_dict(self)
        data["buttons"] = [btn.to_dict() for btn in self.buttons]
        return data

    def from_dict(self, data):
        """Populates this RowGroup from a dictionary."""
        # Handle non-collection properties first
        buttons_data = data.pop("buttons", [])
        dict_to_ptr(self, data)  # Apply remaining simple properties

        # Then repopulate the collection
        self.buttons.clear()
        for btn_data in buttons_data:
            new_btn = self.buttons.add()
            new_btn.from_dict(btn_data)
        # Restore popped data if necessary for other logic, though usually not needed
        data["buttons"] = buttons_data


class UI_CategoryGroup(PropertyGroup):
    name: StringProperty(name="Name", default="Category")
    icon: StringProperty(name="Icon", default="AniMateProContact")
    rows: CollectionProperty(type=RowGroup)
    active_row_index: IntProperty()

    section_separator: FloatProperty(
        name="Separator Height",
        default=0.5,
        min=0.1,
        max=2.0,
        description="Height of the separator line between sections",
    )

    # Pin properties
    pin_global: BoolProperty(
        name="Global Pin Control",
        default=True,
        update=update_pin_global,
        description="Control all pin settings at once",
    )
    top_nla_pin: BoolProperty(name="Pin to NLA Top Bar", default=True, update=update_individual_pin)
    top_graph_pin: BoolProperty(name="Pin to Graph Editor Top Bar", default=True, update=update_individual_pin)
    top_dope_pin: BoolProperty(name="Pin to Dope Sheet Top Bar", default=True, update=update_individual_pin)
    side_nla_pin: BoolProperty(name="Pin to NLA Side Panel", default=True, update=update_individual_pin)
    side_graph_pin: BoolProperty(name="Pin to Graph Editor Side Panel", default=True, update=update_individual_pin)
    side_dope_pin: BoolProperty(name="Pin to Dope Sheet Side Panel", default=True, update=update_individual_pin)
    side_view_pin: BoolProperty(name="Pin to 3D View Side Panel", default=True, update=update_individual_pin)

    top_nla_active: BoolProperty(name="Active in NLA Top", default=True)
    top_graph_active: BoolProperty(name="Active in Graph Top", default=True)
    top_dope_active: BoolProperty(name="Active in Dope Top", default=True)
    side_nla_active: BoolProperty(name="Active in NLA Side", default=True)
    side_graph_active: BoolProperty(name="Active in Graph Side", default=True)
    side_dope_active: BoolProperty(name="Active in Dope Side", default=True)
    side_view_active: BoolProperty(name="Active in View3D Side", default=True)
    popup_active: BoolProperty(name="Active in Popup", default=True)

    properties: BoolProperty(name="Show Properties", default=False)

    show: EnumProperty(
        name="Show Category Title",
        items=[
            ("ALWAYS", "Always", "Always show the category title", "HIDE_OFF", 0),
            ("GLOBAL", "Use Global", "Use global preference for category headers", "WORLD", 1),
            ("NEVER", "Never", "Never show the category title", "HIDE_ON", 2),
        ],
        default="GLOBAL",
    )
    style: EnumProperty(
        name="Category Style",
        items=[
            ("DEFAULT", "Default", "Default category style", "SELECT_SET", 0),
            ("BOX", "Box", "Boxed category style", "MESH_PLANE", 1),
            ("BOX_TITLE", "Box with Title", "Box style with a prominent title area", "TOPBAR", 2),
            ("BOX_CONTENT", "Box Content Only", "Content area is boxed, title is outside", "STICKY_UVS_LOC", 3),
        ],
        default="BOX_TITLE",
    )
    indent: FloatProperty(name="Indent Items", default=1.0, min=0.1, max=3.0)

    # Section collapse style overrides
    cat_sections_collapse_style: EnumProperty(
        name="Sections Collapse Style",
        items=[
            ("GLOBAL", "Use Global", "Use global preference setting"),
            ("THIN", "", "Thin arrow style", "DOWNARROW_HLT", 1),
            ("THICK", "", "Thick arrow style", "TRIA_DOWN", 2),
            ("EYE", "", "Eye icon style", "HIDE_OFF", 3),
            ("RADIO", "", "Radio button icon style", "RADIOBUT_ON", 4),
        ],
        default="GLOBAL",
        description="Override the global sections collapse style for this category",
    )

    cat_sections_icon_as_toggle: BoolProperty(
        name="Use Section Icon as Toggle",
        default=False,
        description="Override global setting: use section icons as toggle buttons instead of decorative labels",
    )

    # Hidden property to track default categories
    default_cat_id: StringProperty(
        name="Default Category ID",
        default="",
        description="ID of the default category file this category was loaded from",
        options={"HIDDEN"},
    )

    def to_dict(self):
        """Converts this UI_CategoryGroup to a dictionary."""
        data = ptr_to_dict(self)
        data["rows"] = [row.to_dict() for row in self.rows]
        return data

    def from_dict(self, data):
        """Populates this UI_CategoryGroup from a dictionary."""
        rows_data = data.pop("rows", [])
        dict_to_ptr(self, data)

        self.rows.clear()
        for row_data in rows_data:
            new_row = self.rows.add()
            new_row.from_dict(row_data)
        data["rows"] = rows_data


class PopupPanelGroup(PropertyGroup):
    name: StringProperty(name="Popup Panel Name", default="New Popup Panel")

    categories: CollectionProperty(type=UI_CategoryGroup)
    active_category_index: IntProperty(default=0)

    invoke_type: EnumProperty(
        name="Invoke Type",
        items=[
            ("PRESS", "Press", "Invoke on key press"),
            ("RELEASE", "Release", "Invoke on key release"),
        ],
        default="PRESS",
    )
    keymap_operator_properties: StringProperty(
        name="Keymap Operator Properties",
        default='{"popup_panel_name": ""}',  # Store as JSON string, e.g., {"popup_panel_name": self.name}
        description="Properties for the popup panel invocation operator",
    )
    keymap_key: StringProperty(name="Key", default="NONE")
    keymap_ctrl: BoolProperty(name="Ctrl", default=False)
    keymap_alt: BoolProperty(name="Alt", default=False)
    keymap_shift: BoolProperty(name="Shift", default=False)
    keymap_os: BoolProperty(name="OS Key", default=False)

    default_popup_id: StringProperty(
        name="Default Popup Panel ID",
        default="",
        description="ID of the default popup panel file this popup panel was loaded from",
        options={"HIDDEN"},
    )

    hotkey_enabled: BoolProperty(name="Enable Hotkey", default=False, description="Enable hotkey for this popup panel")
    hotkey_key: StringProperty(name="Hotkey", default="", description="Key for popup panel hotkey")
    hotkey_ctrl: BoolProperty(name="Ctrl", default=False, description="Use Ctrl modifier")
    hotkey_alt: BoolProperty(name="Alt", default=False, description="Use Alt modifier")
    hotkey_shift: BoolProperty(name="Shift", default=False, description="Use Shift modifier")
    hotkey_string: StringProperty(
        name="Hotkey String",
        default="",
        description="Hotkey combination for this popup panel (e.g., 'CTRL+SHIFT+T')",
        update=update_popup_panel_hotkey_string,
    )
    hotkey_space: EnumProperty(
        name="Space",
        items=[
            ("ALL_SPACES", "All Spaces", "Register hotkey in all spaces", "WORLD", 0),
            ("VIEW_3D", "View 3D", "Register hotkey in View 3D", "VIEW3D", 1),
            ("IMAGE_EDITOR", "Image Editor", "Register hotkey in Image Editor", "IMAGE", 2),
            ("NODE_EDITOR", "Node Editor", "Register hotkey in Node Editor", "NODETREE", 3),
            ("SEQUENCE_EDITOR", "Sequence Editor", "Register hotkey in Sequence Editor", "SEQUENCE", 4),
            ("CLIP_EDITOR", "Clip Editor", "Register hotkey in Clip Editor", "TRACKER", 5),
            ("DOPESHEET_EDITOR", "Dopesheet Editor", "Register hotkey in Dopesheet Editor", "ACTION", 6),
            ("GRAPH_EDITOR", "Graph Editor", "Register hotkey in Graph Editor", "GRAPH", 7),
            ("NLA_EDITOR", "Nla Editor", "Register hotkey in Nla Editor", "NLA", 8),
            ("TEXT_EDITOR", "Text Editor", "Register hotkey in Text Editor", "TEXT", 9),
            ("CONSOLE", "Console", "Register hotkey in Console", "CONSOLE", 10),
            ("INFO", "Info", "Register hotkey in Info", "INFO", 11),
            ("OUTLINER", "Outliner", "Register hotkey in Outliner", "OUTLINER", 12),
            ("PROPERTIES", "Properties", "Register hotkey in Properties", "PROPERTIES", 13),
            ("FILE_BROWSER", "File Browser", "Register hotkey in File Browser", "FILEBROWSER", 14),
        ],
        default="ALL_SPACES",
        description="Space where the hotkey should be active",
        update=update_popup_panel_hotkey_space,
    )
    # Flag to track if we're currently capturing a hotkey
    is_capturing_hotkey: BoolProperty(
        name="Capturing Hotkey", default=False, description="Internal flag to track hotkey capture state"
    )

    # Popup panel width setting
    popup_width: IntProperty(
        name="Popup Width", default=400, min=50, max=1200, description="Width of the popup panel in pixels"
    )

    def to_dict(self):
        """Converts this PopupPanelGroup to a dictionary."""
        data = ptr_to_dict(self)
        data["categories"] = [cat.to_dict() for cat in self.categories]
        return data

    def from_dict(self, data):
        """Populates this PopupPanelGroup from a dictionary."""
        categories_data = data.pop("categories", [])
        dict_to_ptr(self, data)

        self.categories.clear()
        for cat_data in categories_data:
            new_cat = self.categories.add()
            new_cat.from_dict(cat_data)
        data["categories"] = categories_data


# # Update the PieMenuGroup class to include hotkey properties (no update callbacks needed)
# class PieMenuGroup(PropertyGroup):
#     name: StringProperty(name="Name", default="Pie Menu")
#     categories: CollectionProperty(type=UI_PieMenusGroup)
#     active_category_index: IntProperty(default=0)
#     # Hidden property to track default pie menus
#     default_pie_id: StringProperty(
#         name="Default Pie Menu ID",
#         default="",
#         description="ID of the default pie menu file this pie menu was loaded from",
#         options={"HIDDEN"},
#     )
#     # Simple hotkey properties - no complex registration needed
#     hotkey_string: StringProperty(
#         name="Hotkey String", default="", description="Hotkey combination for this pie menu (e.g., 'CTRL+SHIFT+T')"
#     )
#     hotkey_space: EnumProperty(
#         name="Hotkey Space",
#         items=[
#             ("ALL_SPACES", "All Spaces", "Register hotkey in all spaces"),
#             ("VIEW_3D", "View 3D", "Register hotkey in View 3D"),
#             ("IMAGE_EDITOR", "Image Editor", "Register hotkey in Image Editor"),
#             ("NODE_EDITOR", "Node Editor", "Register hotkey in Node Editor"),
#             ("SEQUENCE_EDITOR", "Sequence Editor", "Register hotkey in Sequence Editor"),
#             ("CLIP_EDITOR", "Clip Editor", "Register hotkey in Clip Editor"),
#             ("DOPESHEET_EDITOR", "Dopesheet Editor", "Register hotkey in Dopesheet Editor"),
#             ("GRAPH_EDITOR", "Graph Editor", "Register hotkey in Graph Editor"),
#             ("NLA_EDITOR", "Nla Editor", "Register hotkey in Nla Editor"),
#             ("TEXT_EDITOR", "Text Editor", "Register hotkey in Text Editor"),
#             ("CONSOLE", "Console", "Register hotkey in Console"),
#             ("INFO", "Info", "Register hotkey in Info"),
#             ("OUTLINER", "Outliner", "Register hotkey in Outliner"),
#             ("PROPERTIES", "Properties", "Register hotkey in Properties"),
#             ("FILE_BROWSER", "File Browser", "Register hotkey in File Browser"),
#         ],
#         default="ALL_SPACES",
#         description="Space where the hotkey should be active",
#     )

#     # Flag to track if we're currently capturing a hotkey
#     is_capturing_hotkey: BoolProperty(
#         name="Capturing Hotkey", default=False, description="Internal flag to track hotkey capture state"
#     )
