import bpy
import bpy.utils.previews
import os
from bpy.app.handlers import persistent
import importlib.util
from ..utils.general import (
    # find_user_keyconfig,
    find_addon_keyconfig,
    reboot_theme_colors,
    reset_autokeying_theme_colors,
    set_autokeying_theme_colors,
)
from ..keymaps.key_all_autokeying import (
    keymaps_to_register as autokey_keymaps_to_register,
)
from ..anim_offset import support
from .. import utils
from ..utils.customIcons import get_icon

addon_keymaps = {}

from .. import __package__ as base_package

# def load_icon(icon_name):
#     global custom_icons
#     if not icon_name.lower().endswith(".png"):
#         icon_name += ".png"  # Ensure the icon name ends with .png

#     if custom_icons is None:
#         custom_icons = bpy.utils.previews.new()

#     # Navigate one level up from the current file's directory, then to 'assets/icons'
#     icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons")
#     icon_path = os.path.join(icons_dir, icon_name)

#     if icon_name not in custom_icons:
#         custom_icons.load(icon_name, icon_path, "IMAGE")

#     return custom_icons[icon_name].icon_id


# def load_preview_icon(icon_name):
#     # Assuming this function is defined to simplify the icon loading
#     icon_id = load_icon(icon_name)
#     return icon_id


def amp_AutoKeying_text_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences

    box_4F8C0 = layout_function.box()

    col_0B164 = box_4F8C0.column(heading="", align=False)

    row_B76F3 = col_0B164.row(heading="", align=False)

    row_B76F3.prop(
        prefs,
        "autoKeying_viewport_text_options_expand",
        text="",
        icon="DOWNARROW_HLT" if prefs.autoKeying_viewport_text_options_expand else "RIGHTARROW",
        emboss=False,
    )
    row_0AC83 = row_B76F3.row(heading="", align=False)

    row_0AC83.enabled = bpy.context.preferences.addons[base_package].preferences.viewport_text

    row_0AC83.label(text="TEXT", icon_value=13)
    row_B76F3.prop(
        prefs,
        "viewport_text",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
            if prefs.viewport_text
            else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
        ),
        emboss=True,
        toggle=True,
    )
    if prefs.autoKeying_viewport_text_options_expand:
        col_0B164.separator(factor=0.5)
        row_A25EE = col_0B164.row(heading="", align=False)

        row_A25EE.separator(factor=1.0)
        col_03570 = row_A25EE.column(heading="", align=False)

        col_03570.enabled = prefs.viewport_text

        col_03570.separator(factor=0.5)
        row_C93C5 = col_03570.row(heading="", align=False)

        row_C93C5.prop(
            prefs,
            "rec_text_color",
            text="",
            icon_value=49,
            emboss=True,
        )
        row_C93C5.label(text="Color", icon_value=0)
        col_03570.separator(factor=0.5)
        col_03570.prop(
            prefs,
            "text_position",
            text="Position",
            icon_value=0,
            emboss=True,
        )
        col_03570.separator(factor=0.5)
        col_03570.prop(
            prefs,
            "text_content",
            text="Text",
            icon_value=0,
            emboss=True,
        )
        col_03570.separator(factor=0.5)
        col_03570.prop(
            prefs,
            "text_size",
            text="Size",
            icon_value=0,
            emboss=True,
            slider=True,
        )
        col_03570.separator(factor=0.5)
        col_03570.prop(
            prefs,
            "text_offset",
            text="Offset",
            icon_value=0,
            emboss=True,
            slider=True,
        )
        col_03570.separator(factor=1.0)
        row_A25EE.separator(factor=1.0)


def amp_AutoKeying_offset_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences

    box_CD491 = layout_function.box()

    row_19EDC = box_CD491.row(heading="", align=False)

    row_19EDC.prop(
        prefs,
        "autoKeying_viewport_offsets_options_expand",
        text="",
        icon="DOWNARROW_HLT" if prefs.autoKeying_viewport_offsets_options_expand else "RIGHTARROW",
        emboss=False,
    )
    row_6EC8E = row_19EDC.row(heading="", align=False)

    row_6EC8E.label(text="OFFSETS", icon_value=76)
    if prefs.autoKeying_viewport_offsets_options_expand:
        box_2BE39 = box_CD491.box()

        col_1D164 = box_2BE39.column(heading="", align=False)

        row_938F3 = col_1D164.row(heading="", align=False)

        row_938F3.prop(
            prefs,
            "include_n_panel_width",
            text="N Panel Offset",
            icon_value=0,
            emboss=True,
        )
        col_1D164.separator(factor=0.5)
        row_B8A13 = col_1D164.row(heading="", align=True)

        row_B8A13.prop(
            prefs,
            "tool_settings_height",
            text="Top Offset",
            icon_value=0,
            emboss=True,
            slider=True,
        )
        col_1D164.separator(factor=0.5)
        col_1D164.prop(
            prefs,
            "n_panel_bar",
            text="Right Offset",
            icon_value=0,
            emboss=True,
            slider=True,
        )


def amp_AutoKeying_theme_colors(layout, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    box = layout.box()

    row = box.row()

    row.prop(
        prefs,
        "autokeying_viewport_theme_options_expand",
        text="",
        icon="DOWNARROW_HLT" if prefs.autokeying_viewport_theme_options_expand else "RIGHTARROW",
        emboss=False,
    )

    row.label(text="THEME (Experimental)", icon="COLOR")

    if prefs.autokeying_viewport_theme_options_expand:
        row = box.row()
        row.active = prefs.autokeying_selection_color_use
        row.separator()
        row_color = row.row()
        row_color.prop(
            prefs,
            "autokeying_selection_color_on",
            text="",
            icon_value=1,
            emboss=True,
        )
        row.label(
            text="Change Selection Color",
            icon="RESTRICT_SELECT_OFF",
        )
        row.prop(
            prefs,
            "autokeying_selection_color_use",
            text="",
            **get_icon(
                "AMP_COL_eye_open_zoom" if prefs.autokeying_selection_color_use else "AMP_COL_eye_closed_zoom_greyed"
            ),
        )
        row.separator()

        row = box.row()
        row.active = prefs.autokeying_posebone_color_use
        row.separator()
        row.prop(
            prefs,
            "autokeying_posebone_color_on",
            text="",
            icon_value=1,
            emboss=True,
        )
        row.label(
            text="Highlight Pose Bone Outline",
            icon="BONE_DATA",
        )
        row.prop(
            prefs,
            "autokeying_posebone_color_use",
            text="",
            **get_icon(
                "AMP_COL_eye_open_zoom" if prefs.autokeying_posebone_color_use else "AMP_COL_eye_closed_zoom_greyed"
            ),
        )
        row.separator()

        row = box.row()
        row.active = prefs.autokeying_playhead_color_use
        row.separator()
        row.prop(
            prefs,
            "autokeying_playhead_color_on",
            text="",
            icon_value=1,
            emboss=True,
        )
        row.label(
            text="Highlight Playhead",
            icon="PLAY",
        )
        row.prop(
            prefs,
            "autokeying_playhead_color_use",
            text="",
            **get_icon(
                "AMP_COL_eye_open_zoom" if prefs.autokeying_playhead_color_use else "AMP_COL_eye_closed_zoom_greyed"
            ),
        )
        row.separator()

        container = box.column()
        row = container.row()
        row.active = prefs.autokeying_header_color_use
        row.separator()
        row.prop(
            prefs,
            "autokeying_header_color_on",
            text="",
            icon_value=1,
            emboss=True,
        )
        row.label(
            text="Highlight Header",
            icon="TOPBAR",
        )
        row.prop(
            prefs,
            "autokeying_header_color_use",
            text="",
            **get_icon(
                "AMP_COL_eye_open_zoom" if prefs.autokeying_header_color_use else "AMP_COL_eye_closed_zoom_greyed"
            ),
        )
        row.separator()

        # Include additional options for specific editor headers if needed
        if prefs.autokeying_header_color_use:
            split = container.split(factor=0.2)
            col1 = split.column()
            col1.separator()
            col2 = split.column()
            column_container = col2.column()
            column_container.separator()
            row = column_container.row()
            row.active = prefs.autokeying_header_3dview_color_use
            row.label(
                text="3D View",
                icon="VIEW3D",
            )
            row.prop(
                prefs,
                "autokeying_header_3dview_color_use",
                text="",
                **get_icon(
                    "AMP_COL_eye_open_zoom"
                    if prefs.autokeying_header_3dview_color_use
                    else "AMP_COL_eye_closed_zoom_greyed"
                ),
            )
            row.separator()

            row = column_container.row()
            row.active = prefs.autokeying_header_dopesheet_color_use
            row.label(
                text="Timeline",
                icon="ACTION",
            )
            row.prop(
                prefs,
                "autokeying_header_dopesheet_color_use",
                text="",
                **get_icon(
                    "AMP_COL_eye_open_zoom"
                    if prefs.autokeying_header_dopesheet_color_use
                    else "AMP_COL_eye_closed_zoom_greyed"
                ),
            )
            row.separator()

            row = column_container.row()
            row.active = prefs.autokeying_header_graph_color_use
            row.label(
                text="Graph Editor",
                icon="GRAPH",
            )
            row.prop(
                prefs,
                "autokeying_header_graph_color_use",
                text="",
                **get_icon(
                    "AMP_COL_eye_open_zoom"
                    if prefs.autokeying_header_graph_color_use
                    else "AMP_COL_eye_closed_zoom_greyed"
                ),
            )
            row.separator()

            row = column_container.row()
            row.active = prefs.autokeying_header_nla_color_use
            row.label(
                text="NLA Editor",
                icon="NLA",
            )
            row.prop(
                prefs,
                "autokeying_header_nla_color_use",
                text="",
                **get_icon(
                    "AMP_COL_eye_open_zoom"
                    if prefs.autokeying_header_nla_color_use
                    else "AMP_COL_eye_closed_zoom_greyed"
                ),
            )
            row.separator()


class AMP_PT_Auto_AutoKeying_Info(bpy.types.Panel):
    bl_idname = "AMP_PT_Auto_AutoKeying_Info"
    bl_label = "AutoKeying Help"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_description = "Information related with the Autokeying settings"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 18

    def draw(self, context):
        layout = self.layout

        # *####### HELP HEADER #########*#

        # *_________ INPUTS __________* #
        header_title = "  " + self.bl_label
        header_icon = "AniMateProContact"
        # *___________________________* #

        header_row = layout.row()
        headers_split = header_row.split(factor=0.1)

        # *_______ HEADER ICON ________* #
        headers_split.template_icon(icon_value=utils.customIcons.get_icon_id(header_icon), scale=2)

        # *_______ HEADER TEXT ________* #
        box = headers_split.box()
        header_text = box.row()
        header_container = header_text.column()
        header_container.scale_y = 1.5
        header_container.scale_x = 1.5
        header_container.alignment = "CENTER"
        header_container.label(text=header_title)

        # *####### HELP BODY #########*#

        box = layout.box()

        box.separator()

        box.label(
            text="Shortcut: Improved behaviour refreshing the UI on toggle",
            icon_value=13,
        )
        box.label(text="Frame: Adds a frame around the viewport", icon_value=624)
        box.label(
            text="         - The frame has a variable width frame and a border.",
            icon_value=0,
        )
        box.label(
            text="         - The timeline and editors have an independent frame.",
            icon_value=0,
        )
        box.label(text="Text: Displays a configurable text in the viewport", icon_value=742)
        box.label(text="Offsets: Centers the frame and text", icon_value=76)

        box.separator()


def amp_AutoKeying_frame_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences

    box_239FC = layout_function.box()

    col_45E4D = box_239FC.column(heading="", align=False)

    row_97D34 = col_45E4D.row(heading="", align=False)

    row_97D34.prop(
        prefs,
        "autoKeying_viewport_frame_options_expand",
        text="",
        icon="DOWNARROW_HLT" if prefs.autoKeying_viewport_frame_options_expand else "RIGHTARROW",
        emboss=False,
    )
    row_D84F4 = row_97D34.row(heading="", align=False)

    row_D84F4.enabled = prefs.viewport_frame

    row_D84F4.label(text="FRAME", icon_value=624)
    row_EBE27 = row_D84F4.row(heading="", align=False)

    row_8F2B6 = row_EBE27.row(heading="", align=False)

    row_8F2B6.scale_x = 0.33000001311302185
    row_8F2B6.scale_y = 1.0

    row_97D34.prop(
        prefs,
        "viewport_frame",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
            if prefs.viewport_frame
            else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
        ),
        emboss=True,
        toggle=True,
    )
    if prefs.autoKeying_viewport_frame_options_expand:
        col_D1021 = col_45E4D.column(heading="", align=False)

        col_D1021.enabled = prefs.viewport_frame

        col_D1021.separator(factor=2.0)
        box_FACE4 = col_D1021.box()

        row_1E9CE = box_FACE4.row(heading="", align=False)

        row_1E9CE.label(text="Inner frame", icon_value=48)
        row_1E9CE.prop(
            prefs,
            "frame_inner",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
                if prefs.frame_inner
                else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
            ),
            emboss=True,
        )
        row_1D190 = box_FACE4.row(heading="", align=False)

        row_1D190.separator(factor=1.0)
        col_04269 = row_1D190.column(heading="", align=False)

        col_04269.enabled = prefs.frame_inner

        col_04269.separator(factor=0.5)
        row_71CD0 = col_04269.row(heading="", align=False)

        row_71CD0.prop(
            prefs,
            "frame_color",
            text="",
            icon_value=14,
            emboss=True,
        )
        row_71CD0.label(text="Color", icon_value=0)
        col_04269.separator(factor=0.5)
        col_04269.prop(
            prefs,
            "frame_offset",
            text="Offset",
            icon_value=0,
            emboss=True,
            slider=True,
        )
        col_04269.separator(factor=0.5)
        col_04269.prop(
            prefs,
            "frame_width",
            text="Width",
            icon_value=14,
            emboss=True,
            slider=True,
        )
        col_04269.separator(factor=0.5)
        col_D1021.separator(factor=2.0)
        box_C262E = col_D1021.box()

        row_ABD11 = box_C262E.row(heading="", align=False)

        row_ABD11.label(text="Passepartout", icon_value=385)
        row_ABD11.prop(
            prefs,
            "frame_outter",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
                if prefs.frame_outter
                else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
            ),
            emboss=True,
        )
        row_6C665 = box_C262E.row(heading="", align=False)

        row_6C665.separator(factor=1.0)
        col_88601 = row_6C665.column(heading="", align=False)

        col_88601.enabled = prefs.frame_outter
        col_88601.separator(factor=0.5)
        row_BC21B = col_88601.row(heading="", align=False)

        row_BC21B.prop(
            prefs,
            "frame_outter_color",
            text="",
            icon_value=14,
            emboss=True,
            slider=True,
        )
        row_BC21B.label(text="Color", icon_value=0)
        col_88601.separator(factor=0.5)
        col_D1021.separator(factor=2.0)
        box_58D4A = col_D1021.box()
        box_58D4A.label(text="Editors", icon_value=404)
        row_C8D97 = box_58D4A.row(heading="", align=False)

        row_C8D97.separator(factor=1.0)
        col_CA096 = row_C8D97.column(heading="", align=False)

        if not True:
            col_CA096.operator_context = "EXEC_DEFAULT"
        row_ED73D = col_CA096.row(heading="", align=False)

        row_ED73D.label(text="Timeline", icon_value=utils.customIcons.get_icon_id("ACTION"))
        row_ED73D.prop(
            prefs,
            "frame_dopesheet",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
                if prefs.frame_dopesheet
                else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
            ),
            emboss=True,
        )
        row_9E59B = col_CA096.row(heading="", align=False)
        row_9E59B.label(text="Graph Editor", icon_value=utils.customIcons.get_icon_id("GRAPH"))
        row_9E59B.prop(
            prefs,
            "frame_grapheditor",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
                if prefs.frame_grapheditor
                else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
            ),
            emboss=True,
        )
        row_31AED = col_CA096.row(heading="", align=False)

        row_31AED.label(text="NLA Editor", icon_value=utils.customIcons.get_icon_id("NLA"))
        row_31AED.prop(
            prefs,
            "frame_nla",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
                if prefs.frame_nla
                else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
            ),
            emboss=True,
        )
        col_CA096.separator(factor=1.0)
        col_CA096.prop(
            prefs,
            "frame_width_editors",
            text="Width",
            emboss=True,
            slider=True,
        )
        col_CA096.prop(
            prefs,
            "frame_offset_editors",
            text="Offset",
            emboss=True,
            slider=True,
        )
        col_CA096.prop(
            prefs,
            "frame_top_offset_editors",
            text="Top Offset",
            emboss=True,
            slider=True,
        )
        col_CA096.separator(factor=1.0)
        row_C8D97.separator(factor=1.0)
        col_D1021.separator(factor=1.0)


class AMP_OT_Autokeying(bpy.types.Operator):
    bl_idname = "anim.amp_autokeying_toggle"
    bl_label = "AMP_AutoKeying"
    bl_description = "Toggle Auto Keying on / off"
    # bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if bpy.app.version >= (3, 0, 0) and True:
            cls.poll_message_set("")
        return not False

    def execute(self, context):
        if context.scene.tool_settings.use_keyframe_insert_auto:
            context.scene.tool_settings.use_keyframe_insert_auto = False
            reset_autokeying_theme_colors()
        else:
            context.scene.tool_settings.use_keyframe_insert_auto = True
            bpy.ops.anim.amp_deactivate_anim_offset
            set_autokeying_theme_colors()
        if bpy.context and bpy.context.screen:
            for a in bpy.context.screen.areas:
                a.tag_redraw()

        return {"FINISHED"}

    def invoke(self, context, event):
        # reboot_theme_colors(self, context)
        return self.execute(context)


def amp_AutoKeying_header_interface(
    layout_function,
):
    row_7D229 = layout_function.row(heading="", align=False)

    row_7D229.alignment = "Expand".upper()
    row_7D229.prop(
        bpy.context.scene.tool_settings,
        "use_keyframe_insert_auto",
        text="",
        icon_value=0,
        emboss=True,
    )
    row_7D229.label(text="Auto-Keying Options", icon_value=0)
    row_D1F59 = row_7D229.row(heading="", align=False)

    row_D1F59.alignment = "Expand".upper()
    row_D1F59.active = False
    op = row_D1F59.operator(
        "anim.amp_call_help_panel",
        text="",
        icon_value=1,
        emboss=False,
        depress=False,
    )
    op.panel_name = "AMP_PT_Auto_AutoKeying_Info"


class AMP_PT_AutoKeying_Settings(bpy.types.Panel):
    bl_label = ""
    bl_idname = "ANIMATEPRO_PT_AutoKeying_Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"DEFAULT_CLOSED"}
    bl_ui_units_x = 0
    # bl_category = "AMP"

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="AutoKeying", icon_value=utils.customIcons.get_icon_id("AMP_COL_red"))

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        amp_AutoKeying_header_interface(
            layout_function,
        )
        layout_function = layout
        amp_AutoKeying_frame_interface(
            layout_function,
        )
        layout_function = layout
        amp_AutoKeying_text_interface(
            layout_function,
        )
        layout_function = layout
        amp_AutoKeying_offset_interface(
            layout_function,
        )


classes = (
    AMP_PT_Auto_AutoKeying_Info,
    AMP_OT_Autokeying,
    AMP_PT_AutoKeying_Settings,
)


def register():
    global _icons
    _icons = bpy.utils.previews.new()

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    global _icons
    bpy.utils.previews.remove(_icons)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
