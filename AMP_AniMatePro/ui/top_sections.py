# File ui/top_sections.py

import bpy
from .top_sections_definitions import section_definitions as section_definitions
from .. import utils
from ..utils.customIcons import get_icon

from .. import __package__ as base_package


def default_draw_function(layout, context):
    layout.operator(
        "timeline.reset_sections_and_buttons",
        text="Refresh Top Bar",
        icon="LOOP_BACK",
    )


button_draw_funcs = {}


def get_button_function(draw_function):
    if callable(draw_function):
        return draw_function
    else:
        return default_draw_function


def remove_duplicate_sections_and_buttons(prefs):
    # Remove duplicate sections
    section_names = set()
    if prefs.sections is not None:
        for i in reversed(range(len(prefs.sections))):
            sec = prefs.sections[i]
            if sec.name in section_names:
                prefs.sections.remove(i)
            else:
                section_names.add(sec.name)
                # Now, remove duplicate buttons in this section
                btn_names = set()
                for j in reversed(range(len(sec.buttons))):
                    btn = sec.buttons[j]
                    if btn.name in btn_names:
                        sec.buttons.remove(j)
                    else:
                        btn_names.add(btn.name)


def add_external_addon_section_and_button(
    prefs,
    existing_sections,
    section_name,
    button_name,
    button_draw_func,
    visible_graph=True,
    visible_dope=True,
    enable_graph=True,
    enable_dope=True,
    btn_visible_graph=True,
    btn_visible_dope=True,
    btn_enable_graph=True,
    btn_enable_dope=True,
):
    if button_draw_func == default_draw_function:
        return

    if section_name in existing_sections:
        sec = existing_sections[section_name]
    else:
        sec = prefs.sections.add()
        sec.name = section_name
        sec.visible_graph = visible_graph
        sec.visible_dope = visible_dope
        sec.enable_graph = enable_graph
        sec.enable_dope = enable_dope
        existing_sections[section_name] = sec

    existing_buttons = {btn.name: btn for btn in sec.buttons}

    if button_name in existing_buttons:
        btn = existing_buttons[button_name]
    else:
        btn = sec.buttons.add()
        btn.name = button_name
        btn.visible_graph = btn_visible_graph
        btn.visible_dope = btn_visible_dope
        btn.enable_graph = btn_enable_graph
        btn.enable_dope = btn_enable_dope
        existing_buttons[btn.name] = btn

    button_draw_funcs[button_name] = button_draw_func


def init_sections_and_buttons(section_definitions):
    prefs = bpy.context.preferences.addons[base_package].preferences
    remove_duplicate_sections_and_buttons(prefs)

    existing_sections = {sec.name: sec for sec in prefs.sections}

    for section_info in section_definitions:
        sec_name = section_info["sec_name"]

        if sec_name in existing_sections:
            sec = existing_sections[sec_name]
        else:
            sec = prefs.sections.add()
            sec.name = sec_name
            sec.visible_graph = section_info["sec_vis_graph"]
            sec.visible_dope = section_info["sec_vis_dope"]
            sec.enable_graph = section_info["sec_enabled_graph"]
            sec.enable_dope = section_info["sec_enabled_dope"]
            existing_sections[sec_name] = sec

        existing_buttons = {btn.name: btn for btn in sec.buttons}

        for btn_info in section_info["buttons"]:
            btn_name = btn_info["btn_name"]
            button_draw_funcs[btn_name] = btn_info["btn_draw"]

            if btn_name in existing_buttons:
                btn = existing_buttons[btn_name]
            else:
                btn = sec.buttons.add()
                btn.name = btn_name
                btn.visible_graph = btn_info["btn_vis_graph"]
                btn.visible_dope = btn_info["btn_vis_dope"]
                btn.enable_graph = btn_info["btn_enabled_graph"]
                btn.enable_dope = btn_info["btn_enabled_dope"]

                if not btn.visible_graph and not btn_info["btn_enabled_graph"]:
                    btn.enable_graph = False
                if not btn.visible_dope and not btn_info["btn_enabled_dope"]:
                    btn.enable_dope = False

    add_external_addon_section_and_button(
        prefs=prefs,
        existing_sections=existing_sections,
        section_name="Copy Transforms",
        button_name="Copy Transforms",
        button_draw_func=AmpCopyTransformsButton,
        visible_graph=True,
        visible_dope=True,
        enable_graph=False,
        enable_dope=False,
        btn_visible_graph=False,
        btn_visible_dope=False,
        btn_enable_graph=True,
        btn_enable_dope=True,
    )

    add_external_addon_section_and_button(
        prefs=prefs,
        existing_sections=existing_sections,
        section_name="Temp Pivot",
        button_name="Temp Pivot",
        button_draw_func=AmpTempPivotButton,
        visible_graph=True,
        visible_dope=True,
        enable_graph=False,
        enable_dope=False,
        btn_visible_graph=False,
        btn_visible_dope=False,
        btn_enable_graph=True,
        btn_enable_dope=True,
    )

    add_external_addon_section_and_button(
        prefs=prefs,
        existing_sections=existing_sections,
        section_name="Pin Transforms",
        button_name="Pin Transforms",
        button_draw_func=AmpPinTransformsButton,
        visible_graph=True,
        visible_dope=True,
        enable_graph=False,
        enable_dope=False,
        btn_visible_graph=False,
        btn_visible_dope=False,
        btn_enable_graph=True,
        btn_enable_dope=True,
    )


def AmpCopyTransformsButton(layout, context):
    panel_class = getattr(bpy.types, "AMP_CT_PT_CopyPasteTransforms", None)

    if panel_class:
        panel_class.draw_compact_labels(layout, context)
    else:
        row = layout.row()
        row.label(text="Get/Update Transformator", icon="URL")
        row.operator("wm.url_open", text="", **get_icon("BlenderMarket")).url = (
            "https://blendermarket.com/products/amp-transformator"
        )
        row.operator("wm.url_open", text="", **get_icon("Gumroad")).url = "https://nda.gumroad.com/l/amp_transformator"


def AmpTempPivotButton(layout, context):
    panel_class = getattr(bpy.types, "AMP_TEMP_CONTROLS_PT_Panel_Compact", None)

    if panel_class:
        panel_class.draw_compact(layout, context)
    else:
        row = layout.row()
        row.label(text="Get/Update Transformator", icon="URL")
        row.operator("wm.url_open", text="", **get_icon("BlenderMarket")).url = (
            "https://blendermarket.com/products/amp-transformator"
        )
        row.operator("wm.url_open", text="", **get_icon("Gumroad")).url = "https://nda.gumroad.com/l/amp_transformator"


def AmpPinTransformsButton(layout, context):
    panel_class = getattr(bpy.types, "PIN_CT_PT_PinTransforms", None)

    if panel_class:
        panel_class.draw_compact(layout, context)
    else:
        row = layout.row()
        row.label(text="Get/Update Transformator", icon="URL")
        row.operator("wm.url_open", text="", **get_icon("BlenderMarket")).url = (
            "https://blendermarket.com/products/amp-transformator"
        )
        row.operator("wm.url_open", text="", **get_icon("Gumroad")).url = "https://nda.gumroad.com/l/amp_transformator"


def draw_graph_dope_side_panel(self, context):
    layout = self.layout
    prefs = bpy.context.preferences.addons[base_package].preferences
    box = layout.box()
    for section in prefs.sections:
        col = box.column()
        col.alignment = "LEFT"
        row = col.row(align=True)
        row.alignment = "LEFT"
        for button in section.buttons:
            draw_func = button_draw_funcs.get(button.name, default_draw_function)
            draw_func(row, context)


def draw_reload_theme_button(self, context):
    layout = self.layout
    prefs = bpy.context.preferences.addons[base_package].preferences
    if not prefs.icons_loaded:
        layout.operator("anim.amp_reload_icons", text="Load Icons", icon="FILE_REFRESH")


def draw_graph_editor_top_bar(self, context):
    layout = self.layout
    prefs = bpy.context.preferences.addons[base_package].preferences

    for section in prefs.sections:
        if section.visible_graph and section.enable_graph:
            row = layout.row(align=True)
            # row.label(text=section.name)
            for button in section.buttons:
                if button.enable_graph:
                    button_row = row.row(align=False)
                    button_row.alignment = "LEFT"
                    draw_func = button_draw_funcs.get(button.name, default_draw_function)
                    draw_func(button_row, context)
            layout.separator()


def draw_dopesheet_top_bar(self, context):
    layout = self.layout
    prefs = bpy.context.preferences.addons[base_package].preferences
    for section in prefs.sections:
        if section.visible_dope and section.enable_dope:
            row = layout.row(align=True)
            # row.label(text=section.name)
            for button in section.buttons:
                if button.enable_dope:  # and button.visible_dope:
                    button_row = row.row(align=False)
                    button_row.alignment = "LEFT"
                    draw_func = button_draw_funcs.get(button.name, default_draw_function)
                    draw_func(button_row, context)
            layout.separator()


def register_top_sections():
    try:
        bpy.types.GRAPH_MT_editor_menus.remove(draw_graph_editor_top_bar)
        bpy.types.DOPESHEET_MT_editor_menus.remove(draw_dopesheet_top_bar)
    except:
        pass

    bpy.types.GRAPH_MT_editor_menus.append(draw_graph_editor_top_bar)
    bpy.types.DOPESHEET_MT_editor_menus.append(draw_dopesheet_top_bar)


def refresh_top_sections(self, context):
    try:
        bpy.types.GRAPH_MT_editor_menus.remove(draw_graph_editor_top_bar)
        bpy.types.DOPESHEET_MT_editor_menus.remove(draw_dopesheet_top_bar)
        # del bpy.types.TIME_MT_editor_menus.append(draw_timeline_tools_header_buttons)
        # del bpy.types.NLA_MT_editor_menus.append(draw_timeline_tools_header)
    except:
        pass

    bpy.types.GRAPH_MT_editor_menus.append(draw_graph_editor_top_bar)
    bpy.types.DOPESHEET_MT_editor_menus.append(draw_dopesheet_top_bar)
    # bpy.types.TIME_MT_editor_menus.append(draw_timeline_tools_header_buttons)
    # bpy.types.NLA_MT_editor_menus.append(draw_timeline_tools_header)


class TIMELINE_UL_sections(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        # row.prop(item, "name", text="", emboss=False, icon="OUTLINER_OB_GROUP_INSTANCE")
        row.label(text=item.name, icon="OUTLINER_OB_GROUP_INSTANCE")
        if item.visible_graph:
            row.prop(item, "enable_graph", text="", toggle=True, icon="GRAPH")
        else:
            row.label(text="", icon="BLANK1")
        if item.visible_dope:
            row.prop(item, "enable_dope", text="", toggle=True, icon="ACTION")
        else:
            row.label(text="", icon="BLANK1")


class TIMELINE_UL_buttons(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        # Retrieve the draw function associated with the button
        draw_func = button_draw_funcs.get(item.name, default_draw_function)

        # Call the draw function to render the button's functionality in the list
        draw_func(row, context)

        # Additional UI controls for enabling/disabling visibility in the Graph Editor and Dope Sheet
        sub_row = row.row(align=True)

        sub_row.label(text=item.name)
        if item.visible_graph:
            sub_row.prop(item, "enable_graph", text="", toggle=True, icon="GRAPH")
        else:
            sub_row.label(text="", icon="BLANK1")
        if item.visible_dope:
            sub_row.prop(item, "enable_dope", text="", toggle=True, icon="ACTION")
        else:
            sub_row.label(text="", icon="BLANK1")


class AMP_OT_move_section(bpy.types.Operator):
    """Move a section up or down in the list"""

    bl_idname = "timeline.move_section"
    bl_label = "Move Section"

    direction: bpy.props.StringProperty()

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        index = prefs.active_section_index
        target_index = index + (-1 if self.direction == "UP" else 1)

        if 0 <= target_index < len(prefs.sections):
            prefs.sections.move(index, target_index)
            prefs.active_section_index = target_index

        # Refresh the UI
        utils.refresh_ui(context)

        return {"FINISHED"}


class AMP_OT_move_button(bpy.types.Operator):
    """Move a button up or down in the list within a section"""

    bl_idname = "timeline.move_button"
    bl_label = "Move Button"

    direction: bpy.props.StringProperty()

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        section = prefs.sections[prefs.active_section_index]
        index = section.active_button_index
        target_index = index + (-1 if self.direction == "UP" else 1)

        if 0 <= target_index < len(section.buttons):
            section.buttons.move(index, target_index)
            section.active_button_index = target_index

        utils.refresh_ui(context)
        return {"FINISHED"}


class AMP_OT_reset_sections_and_buttons(bpy.types.Operator):
    """Reset sections and buttons to default values"""

    bl_idname = "timeline.reset_sections_and_buttons"
    bl_label = "Reset to Default"

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        prefs.sections.clear()
        init_sections_and_buttons(section_definitions)

        # Refresh the UI
        utils.refresh_ui(context)

        return {"FINISHED"}


def draw_ui_sections_lists_preferences(self, layout, context):
    prefs = bpy.context.preferences.addons[base_package].preferences

    layout.label(text="Sections and Buttons")

    # Validate active_section_index
    if prefs.active_section_index >= len(prefs.sections):
        prefs.active_section_index = 0  # Reset to the first section or another appropriate value

    split = layout.split(factor=0.5)
    row_sections = split.row()
    col = row_sections.column()
    col.template_list("TIMELINE_UL_sections", "", prefs, "sections", prefs, "active_section_index")

    col2 = row_sections.column(align=True)
    col2.operator("timeline.move_section", text="", icon="TRIA_UP").direction = "UP"
    col2.operator("timeline.move_section", text="", icon="TRIA_DOWN").direction = "DOWN"
    col2.operator("timeline.reset_sections_and_buttons", text="", icon="LOOP_BACK")

    if prefs.sections:
        section = prefs.sections[prefs.active_section_index] if prefs.sections else None
        row_buttons = split.row()
        if section:
            col = row_buttons.column()
            col.template_list("TIMELINE_UL_buttons", "", section, "buttons", section, "active_button_index")

            col2 = row_buttons.column(align=True)
            col2.operator("timeline.move_button", text="", icon="TRIA_UP").direction = "UP"
            col2.operator("timeline.move_button", text="", icon="TRIA_DOWN").direction = "DOWN"
            col2.operator("timeline.reset_sections_and_buttons", text="", icon="LOOP_BACK")


def draw_ui_sections_lists_side_panel(self, layout, context):
    prefs = bpy.context.preferences.addons[base_package].preferences

    box = layout.box()

    row_icons_set = box.row()
    row_icons_set.label(text="Icons Theme:")
    row_icons_set.prop(prefs, "icons_set", text="")

    box.label(text="Sections and Buttons")

    # Validate active_section_index
    if prefs.active_section_index >= len(prefs.sections):
        prefs.active_section_index = 0

    row_sections = box.row(align=True)
    col = row_sections.column()
    col.template_list("TIMELINE_UL_sections", "", prefs, "sections", prefs, "active_section_index")

    col2 = row_sections.column(align=True)
    col2.operator("timeline.move_section", text="", icon="TRIA_UP").direction = "UP"
    col2.operator("timeline.move_section", text="", icon="TRIA_DOWN").direction = "DOWN"
    col2.operator("timeline.reset_sections_and_buttons", text="", icon="LOOP_BACK")

    if prefs.sections:
        row_buttons = box.row(align=True)
        section = prefs.sections[prefs.active_section_index] if prefs.sections else None
        if section:
            col = row_buttons.column()
            col.template_list("TIMELINE_UL_buttons", "", section, "buttons", section, "active_button_index")

            col2 = row_buttons.column(align=True)
            col2.operator("timeline.move_button", text="", icon="TRIA_UP").direction = "UP"
            col2.operator("timeline.move_button", text="", icon="TRIA_DOWN").direction = "DOWN"
            col2.operator("timeline.reset_sections_and_buttons", text="", icon="LOOP_BACK")


class side_panel_ui(bpy.types.Panel):
    bl_label = "Top Bar Buttons"
    bl_region_type = "UI"
    bl_category = "Animation"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        layout = self.layout
        layout.operator("amp.reload_icons", text="", **get_icon("TOPBAR"), emboss=False)

    def draw(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        layout = self.layout

        draw_graph_dope_side_panel(self, context)

        layout.separator()

        row = layout.row()
        row.prop(
            prefs,
            "config_top_panel",
            text="Configure",
            icon="TRIA_DOWN" if prefs.config_top_panel else "SETTINGS",
        )

        row.operator("amp.reload_icons", text="", **get_icon("FILE_REFRESH"), emboss=False)
        if prefs.config_top_panel:
            draw_ui_sections_lists_side_panel(self, layout, context)


class AMP_PT_SidePanelGraph(side_panel_ui):
    bl_idname = "AMP_PT_SidePanelGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_parent_id = "AMP_PT_AniMateProGraph"


class AMP_PT_SidePanelDope(side_panel_ui):
    bl_idname = "AMP_PT_SidePanelDope"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_parent_id = "AMP_PT_AniMateProDope"


classes = [
    # ButtonItem,
    # SectionItem,
    TIMELINE_UL_sections,
    TIMELINE_UL_buttons,
    AMP_OT_move_button,
    AMP_OT_move_section,
    AMP_OT_reset_sections_and_buttons,
    AMP_PT_SidePanelGraph,
    AMP_PT_SidePanelDope,
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    # register_properties()

    # init_sections_and_buttons(section_definitions)

    # bpy.types.GRAPH_MT_editor_menus.append(draw_graph_editor_top_bar)
    # bpy.types.DOPESHEET_MT_editor_menus.append(draw_dopesheet_top_bar)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    # unregister_properties()

    # bpy.types.GRAPH_MT_editor_menus.remove(draw_graph_editor_top_bar)
    # bpy.types.DOPESHEET_MT_editor_menus.remove(draw_dopesheet_top_bar)


if __name__ == "__main__":
    register()
