###########
## ui.py ##
###########

import bpy
import bpy.utils.previews
import os
import gpu
from bpy.app.handlers import persistent
from ..anim_offset.ui import draw_anim_offset, draw_anim_offset_mask
from ..anim_slicer.anim_slicer import AnimSlicerButton
from ..markers_tools.markers import MarkersToolsButton
from ..anim_poser.anim_poser import AnimPoserButtons
from ..anim_sculpt.anim_sculpt import AnimSculptButton
from ..anim_shifter.anim_shifter import AnimShifterButton
from ..anim_curves.anim_curves import AnimCurvesButtons, AnimViewButtons
from ..anim_looper.anim_looper import AnimLoopButton
from ..anim_baker.anim_baker import AnimBakerButton

# from ..anim_curves.anim_curves import AMP_OT_isolate_selected_fcurves
from .. import utils
from ..utils.customIcons import get_icon


from .. import __package__ as base_package


addon_keymaps = {}


def amp_limits_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences
    layout_function.separator(factor=2.0)
    row_09003 = layout_function.row(heading="", align=False)
    row_09003.alert = False
    row_09003.enabled = True
    row_09003.active = True
    row_09003.use_property_split = False
    row_09003.use_property_decorate = False

    row_09003.label(text="Scrubbing Limits", icon_value=0)
    row_2C1EF = row_09003.row(heading="", align=False)
    row_2C1EF.alert = False
    row_2C1EF.enabled = True
    row_2C1EF.active = False
    row_2C1EF.use_property_split = False
    row_2C1EF.use_property_decorate = False

    op = row_2C1EF.operator(
        "anim.amp_call_help_panel",
        text="",
        icon_value=1,
        emboss=False,
        depress=False,
    )
    op.panel_name = "AMP_PT_Timeline_Scrubbing_Limits_Help"

    box_173D8 = layout_function.box()
    box_173D8.alert = False
    box_173D8.enabled = True
    box_173D8.active = True
    box_173D8.use_property_split = False
    box_173D8.use_property_decorate = False

    row_3475A = box_173D8.row(heading="", align=True)
    row_3475A.alert = False
    row_3475A.enabled = True
    row_3475A.active = True
    row_3475A.use_property_split = False
    row_3475A.use_property_decorate = False

    row_3475A.separator(factor=2.0)
    row_3475A.label(text="Limit to range", **get_icon("ACTION"))
    row_3475A.prop(
        prefs,
        "limit_to_active_range",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
            if prefs.limit_to_active_range
            else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
        ),
        emboss=True,
        toggle=True,
    )
    row_41FE4 = box_173D8.row(heading="", align=True)
    row_41FE4.alert = False
    row_41FE4.enabled = True
    row_41FE4.active = True
    row_41FE4.use_property_split = False
    row_41FE4.use_property_decorate = False

    row_41FE4.separator(factor=2.0)
    row_41FE4.prop(
        bpy.context.scene,
        "use_preview_range",
        text="",
        icon_value=0,
        emboss=True,
    )
    if bpy.context.scene.use_preview_range:
        row_AABA9 = row_41FE4.row(heading="", align=True)
        row_AABA9.alert = True
        row_AABA9.enabled = True
        row_AABA9.active = True
        row_AABA9.use_property_split = False
        row_AABA9.use_property_decorate = False

        row_AABA9.prop(
            bpy.context.scene,
            "frame_preview_start",
            text="Start",
            icon_value=0,
            emboss=True,
        )
        row_AABA9.prop(
            bpy.context.scene,
            "frame_preview_end",
            text="End",
            icon_value=0,
            emboss=True,
        )
    else:
        row_92B93 = row_41FE4.row(heading="", align=True)
        row_92B93.alert = False
        row_92B93.enabled = True
        row_92B93.active = True
        row_92B93.use_property_split = False
        row_92B93.use_property_decorate = False

        row_92B93.prop(
            bpy.context.scene,
            "frame_start",
            text="Start",
            icon_value=0,
            emboss=True,
        )
        row_92B93.prop(bpy.context.scene, "frame_end", text="End", icon_value=0, emboss=True)


def amp_spacebaraction_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences
    row_E4CEF = layout_function.row(heading="", align=False)
    row_E4CEF.alert = False
    row_E4CEF.enabled = True
    row_E4CEF.active = True
    row_E4CEF.use_property_split = False
    row_E4CEF.use_property_decorate = False

    row_E4CEF.label(text="Scrubbing Tap Action", icon="ACTION_TWEAK")
    row_9AA59 = row_E4CEF.row(heading="", align=False)
    row_9AA59.alert = False
    row_9AA59.enabled = True
    row_9AA59.active = False
    row_9AA59.use_property_split = False
    row_9AA59.use_property_decorate = False

    op = row_9AA59.operator(
        "anim.amp_call_help_panel",
        text="",
        icon_value=1,
        emboss=False,
        depress=False,
    )
    op.panel_name = "AMP_PT_Timeline_Spacebar_Action_Help"

    # op = row_9AA59.operator(
    #     "sna.timeline_spacebar_action_help",
    #     text="",
    #     icon_value=1,
    #     emboss=False,
    #     depress=False,
    # )
    box_3E7E9 = layout_function.box()
    box_3E7E9.alert = False
    box_3E7E9.enabled = True
    box_3E7E9.active = True
    box_3E7E9.use_property_split = False
    box_3E7E9.use_property_decorate = False

    row_05094 = box_3E7E9.row(heading="", align=True)
    row_05094.alert = False
    row_05094.enabled = True
    row_05094.active = True
    row_05094.use_property_split = False
    row_05094.use_property_decorate = False

    row_05094.operator(
        "wm.deactivate_other_keymaps_for_operator",
        text="",
        icon="FILE_REFRESH",
    ).operator_idname = "anim.amp_timeline_scrub"
    row_05094.separator(factor=0.25)
    row_05094.prop(
        prefs,
        "mode",
        text="Tap Action",
        icon_value=0,
        emboss=True,
        expand=True,
    )


def amp_text_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences
    layout_function.separator(factor=2.0)
    row_D1BE4 = layout_function.row(heading="", align=False)
    row_D1BE4.alert = False
    row_D1BE4.enabled = True
    row_D1BE4.active = True
    row_D1BE4.use_property_split = False
    row_D1BE4.use_property_decorate = False
    row_D1BE4.scale_x = 1.0
    row_D1BE4.scale_y = 1.0

    row_D1BE4.label(text="Scrubbing Text", icon_value=0)
    row_3B991 = row_D1BE4.row(heading="", align=False)
    row_3B991.alert = False
    row_3B991.enabled = True
    row_3B991.active = False
    row_3B991.use_property_split = False
    row_3B991.use_property_decorate = False
    row_3B991.scale_x = 1.0
    row_3B991.scale_y = 1.0

    op = row_3B991.operator(
        "anim.amp_call_help_panel",
        text="",
        icon_value=1,
        emboss=False,
        depress=False,
    )
    op.panel_name = "AMP_PT_Timeline_Scrubbing_Text_Help"

    # op = row_3B991.operator(
    #     "sna.timeline_scrubbing_text_help",
    #     text="",
    #     icon_value=1,
    #     emboss=False,
    #     depress=False,
    # )
    col_599A2 = layout_function.column(heading="", align=True)

    box_AD740 = col_599A2.box()

    row_709A5 = box_AD740.row(heading="", align=True)

    row_709A5.separator(factor=2.0)
    row_709A5.label(text="Draw frame at cursor", **get_icon("RESTRICT_SELECT_OFF"))
    row_709A5.prop(
        prefs,
        "show_frame_number",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
            if prefs.show_frame_number
            else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
        ),
        emboss=True,
        toggle=True,
    )
    row_73A4B = box_AD740.row(heading="", align=True)
    row_73A4B.enabled = prefs.show_frame_number

    # row_9D71B = row_73A4B.row(heading="", align=True)
    # row_9D71B.alert = False
    # row_9D71B.enabled = not prefs.lock_text_in_place
    # row_9D71B.active = True
    # row_9D71B.use_property_split = False
    # row_9D71B.use_property_decorate = False
    # row_9D71B.scale_x = 1.0
    # row_9D71B.scale_y = 1.0

    # row_9D71B.separator(factor=2.0)
    # row_9D71B.label(text="lock vertical movement", **get_icon("DECORATE_LOCKED"))
    # row_9D71B.prop(
    #     prefs,
    #     "lock_vertical_movement",
    #     text="",
    #     icon_value=(41 if prefs.lock_vertical_movement else 224),
    #     emboss=True,
    # )
    # row_6DE73 = box_AD740.row(heading="", align=True)
    # row_6DE73.alert = False
    # row_6DE73.enabled = prefs.show_frame_number
    # row_6DE73.active = True
    # row_6DE73.use_property_split = False
    # row_6DE73.use_property_decorate = False
    # row_6DE73.scale_x = 1.0
    # row_6DE73.scale_y = 1.0

    # row_6DE73.separator(factor=2.0)
    # row_6DE73.label(text="Lock in place", **get_icon("DECORATE_LOCKED"))
    # row_6DE73.prop(
    #     prefs,
    #     "lock_text_in_place",
    #     text="",
    #     icon_value=(41 if prefs.lock_text_in_place else 224),
    #     emboss=True,
    # )
    row_9AD13 = box_AD740.row(heading="", align=True)

    row_9AD13.separator(factor=2.0)
    row_9AD13.label(text="GUI Help", **get_icon("HELP"))
    row_9AD13.prop(
        prefs,
        "timeline_gui_toggle",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_COL_eye_open_zoom")
            if prefs.timeline_gui_toggle
            else utils.customIcons.get_icon_id("AMP_COL_eye_closed_zoom_greyed")
        ),
        emboss=True,
        toggle=True,
    )
    col_599A2.separator(factor=2.0)
    box_0EB7A = col_599A2.box()

    row_7F2E6 = box_0EB7A.row(heading="", align=True)

    row_7F2E6.separator(factor=2.0)
    row_7F2E6.label(text="Size", **get_icon("CON_SIZELIKE"))
    row_7F2E6.prop(
        prefs,
        "timeline_gui_text_size",
        text="",
        icon_value=0,
        emboss=True,
        slider=True,
    )
    row_A2E10 = box_0EB7A.row(heading="", align=True)

    row_A2E10.separator(factor=2.0)
    row_A2E10.label(text="Accent", **get_icon("RESTRICT_COLOR_ON"))
    row_A2E10.prop(
        prefs,
        "accent_color",
        text="",
        icon_value=0,
        emboss=True,
    )
    row_B5BFD = box_0EB7A.row(heading="", align=True)

    row_B5BFD.separator(factor=2.0)
    row_B5BFD.label(text="Text", **get_icon("RESTRICT_COLOR_OFF"))
    row_B5BFD.prop(
        prefs,
        "text_color",
        text="",
        icon_value=0,
        emboss=True,
    )


class AMP_PT_Timeline_Scrubbing_Settings_Help(bpy.types.Panel):
    bl_idname = "AMP_PT_Timeline_Scrubbing_Settings_Help"
    bl_label = "Timeline Scrubbing Settings Help"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_description = "Information related with the Scrubbing settings"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 18

    @classmethod
    def poll(cls, context):
        return True

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

        box_4B1AD = layout.box()
        box_4B1AD.alert = False
        box_4B1AD.enabled = True
        box_4B1AD.active = True
        box_4B1AD.use_property_split = False
        box_4B1AD.use_property_decorate = False

        box_4B1AD.scale_x = 1.0
        box_4B1AD.scale_y = 1.5

        box_4B1AD.separator(factor=0.5)
        box_4B1AD.label(text="Distance to drag the mouse before Scrubbing starts", **get_icon("TRANSFORM_ORIGINS"))
        box_4B1AD.label(text="Sensitivity of the Scrubbing", **get_icon("SEQ_LUMA_WAVEFORM"))
        box_4B1AD.separator(factor=0.5)


class AMP_PT_Timeline_Spacebar_Action_Help(bpy.types.Panel):
    bl_idname = "AMP_PT_Timeline_Spacebar_Action_Help"
    bl_label = "Timeline Scrubbing Action help"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_description = "Information related with the Scrubbing Tap Action"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 18

    @classmethod
    def poll(cls, context):
        return True

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

        box_1E850 = layout.box()
        box_1E850.alert = False
        box_1E850.enabled = True
        box_1E850.active = True
        box_1E850.use_property_split = False
        box_1E850.use_property_decorate = False

        box_1E850.scale_x = 1.0
        box_1E850.scale_y = 1.5

        box_1E850.separator(factor=0.5)
        box_1E850.label(
            text="Hold Scrubbing Key and drag L or R to drag the timeline.",
            icon_value=936,
        )
        box_1E850.label(text="While Scrubbing hold CTRL for Markers.", icon_value=915)
        box_1E850.label(text="While Scrubbing hold SHHIFT for Keyframes of active.", icon_value=916)
        box_1E850.label(text="Press SPACE and release for Scrubbing Tap Action", icon_value=936)
        box_1E850.label(
            text="Change the Scrubbing Tap Action while not Scrubbing",
            icon="ACTION_TWEAK",
        )
        box_1E850.separator(factor=0.5)


class AMP_PT_Timeline_Scrubbing_Limits_Help(bpy.types.Panel):
    bl_idname = "AMP_PT_Timeline_Scrubbing_Limits_Help"
    bl_label = "Timeline Scrubbing Limits Help"
    bl_description = "Information related with the Scrubbing Limits"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 18

    @classmethod
    def poll(cls, context):
        return True

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

        box_7DFD4 = layout.box()
        box_7DFD4.alert = False
        box_7DFD4.enabled = True
        box_7DFD4.active = True
        box_7DFD4.use_property_split = False
        box_7DFD4.use_property_decorate = False

        box_7DFD4.scale_x = 1.0
        box_7DFD4.scale_y = 1.5

        box_7DFD4.separator(factor=0.5)
        box_7DFD4.label(text="Limit to active frame range", icon_value=115)
        box_7DFD4.label(text="Set frame and preview range", icon_value=503)
        box_7DFD4.separator(factor=0.5)


class AMP_PT_Timeline_Scrubbing_Text_Help(bpy.types.Panel):
    bl_idname = "AMP_PT_Timeline_Scrubbing_Text_Help"
    bl_label = "Timeline Scrubbing Text Help"
    bl_description = "Information related with the Scrubbing viewport text"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 18

    @classmethod
    def poll(cls, context):
        return True

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

        box_C084D = layout.box()
        box_C084D.alert = False
        box_C084D.enabled = True
        box_C084D.active = True
        box_C084D.use_property_split = False
        box_C084D.use_property_decorate = False

        box_C084D.scale_x = 1.0
        box_C084D.scale_y = 1.5

        box_C084D.separator(factor=0.5)
        box_C084D.label(text="At Cursor: display the frame number at the cursor", icon_value=256)
        box_C084D.label(text="Lock the vertical movement of the text with the mouse", icon_value=41)
        box_C084D.label(text="GUI Help: Expand the GUI help while scrubbing", icon_value=52)
        box_C084D.label(text="Size: Change the text size on screen", icon_value=421)
        box_C084D.label(text="Accent: Change the viewport text accent color", icon_value=252)
        box_C084D.label(text="Text: Change the viewport text color", icon_value=251)
        box_C084D.separator(factor=0.5)


class AMP_PT_keyframing_settings(bpy.types.Panel):
    bl_label = "AMP_PT_keyframing_settings"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_options = {"HIDE_HEADER"}
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        tool_settings = context.tool_settings

        col = layout.column(align=True)
        col.label(text="Active Keying Set")
        row = col.row(align=True)
        row.prop_search(scene.keying_sets_all, "active", scene, "keying_sets_all", text="")
        row.operator("anim.keyframe_insert", text="", icon="KEY_HLT")
        row.operator("anim.keyframe_delete", text="", icon="KEY_DEHLT")

        col = layout.column(align=True)
        col.label(text="New Keyframe Type")
        col.prop(tool_settings, "keyframe_type", text="")

        layout.prop(tool_settings, "use_keyframe_cycle_aware")


def amp_scrubbing_interface(
    layout_function,
):
    prefs = bpy.context.preferences.addons[base_package].preferences
    layout_function.separator(factor=2.0)
    row_0695A = layout_function.row(heading="", align=False)
    row_0695A.alert = False
    row_0695A.enabled = True
    row_0695A.active = True
    row_0695A.use_property_split = False
    row_0695A.use_property_decorate = False
    row_0695A.scale_x = 1.0
    row_0695A.scale_y = 1.0

    row_0695A.label(text="Scrubbing Settings", icon_value=0)
    row_A91DC = row_0695A.row(heading="", align=False)
    row_A91DC.alert = False
    row_A91DC.enabled = True
    row_A91DC.active = False
    row_A91DC.use_property_split = False
    row_A91DC.use_property_decorate = False
    row_A91DC.scale_x = 1.0
    row_A91DC.scale_y = 1.0

    op = row_A91DC.operator(
        "anim.amp_call_help_panel",
        text="",
        icon_value=1,
        emboss=False,
        depress=False,
    )
    op.panel_name = "AMP_PT_Timeline_Scrubbing_Settings_Help"

    # op = row_A91DC.operator(
    #     "sna.timeline_scrubbing_settings_help",
    #     text="",
    #     icon_value=1,
    #     emboss=False,
    #     depress=False,
    # )
    box_6BA4F = layout_function.box()
    box_6BA4F.alert = False
    box_6BA4F.enabled = True
    box_6BA4F.active = True
    box_6BA4F.use_property_split = False
    box_6BA4F.use_property_decorate = False

    box_6BA4F.scale_x = 1.0
    box_6BA4F.scale_y = 1.0

    row_2E003 = box_6BA4F.row(heading="", align=True)
    row_2E003.alert = False
    row_2E003.enabled = True
    row_2E003.active = True
    row_2E003.use_property_split = False
    row_2E003.use_property_decorate = False
    row_2E003.scale_x = 1.0
    row_2E003.scale_y = 1.0

    row_2E003.separator(factor=1.0)
    row_2E003.label(text="Distance drag", **get_icon("TRANSFORM_ORIGINS"))
    row_2E003.prop(
        prefs,
        "drag_threshold",
        text="",
        icon_value=0,
        emboss=True,
        slider=True,
    )
    row_0DDF7 = box_6BA4F.row(heading="", align=True)
    row_0DDF7.alert = False
    row_0DDF7.enabled = True
    row_0DDF7.active = True
    row_0DDF7.use_property_split = False
    row_0DDF7.use_property_decorate = False
    row_0DDF7.scale_x = 1.0
    row_0DDF7.scale_y = 1.0

    row_0DDF7.separator(factor=1.0)
    row_0DDF7.label(
        text="Sensitivity",
        **get_icon("SEQ_LUMA_WAVEFORM"),
    )
    row_0DDF7.prop(
        prefs,
        "timeline_sensitivity",
        text="",
        emboss=True,
        slider=True,
    )


class AMP_PT_Timeline_Tools(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_Timeline_Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    # bl_category = "AMP"
    bl_ui_units_x = 0

    def draw_header(self, context):
        layout = self.layout
        layout.label(
            text="Timeline Tools",
            icon_value=utils.customIcons.get_icon_id("AMP_COL_blue_light"),
        )

    def draw(self, context):
        layout = self.layout


class AMP_PT_Timeline_Scrub(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_Timeline_Scrub"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "AMP_PT_Timeline_Tools"
    # bl_category = "AMP"
    bl_ui_units_x = 0

    @classmethod
    def poll(cls, context):
        return not (False)

    def draw_header(self, context):
        layout = self.layout
        layout.label(
            text="Timeline Scrubbing",
            icon_value=utils.customIcons.get_icon_id("AMP_COL_blue_light"),
        )

    def draw(self, context):
        layout = self.layout
        layout_function = layout
        amp_spacebaraction_interface(
            layout_function,
        )
        layout_function = layout
        amp_scrubbing_interface(
            layout_function,
        )
        layout_function = layout
        amp_limits_interface(
            layout_function,
        )
        layout_function = layout
        amp_text_interface(
            layout_function,
        )
        layout.separator(factor=1.0)


def draw_playbuttons_header(self, context):
    layout = self.layout
    scene = context.scene
    tool_settings = context.tool_settings
    screen = context.screen

    row = layout.row(align=True)
    row.prop(tool_settings, "use_keyframe_insert_auto", text="", toggle=True)
    sub = row.row(align=True)
    sub.active = tool_settings.use_keyframe_insert_auto
    if context.area.type == "TIMELINE":
        sub.popover(
            panel="TIME_PT_auto_keyframing",
            text="",
        )

    row = layout.row(align=True)
    row.operator("screen.frame_jump", text="", icon="REW").end = False
    if context.area.type == "GRAPH_EDITOR":
        row.operator("graph.keyframe_jump", text="", icon="PREV_KEYFRAME").next = False
    else:
        row.operator("screen.keyframe_jump", text="", icon="PREV_KEYFRAME").next = False
    if not screen.is_animation_playing:
        # if using JACK and A/V sync:
        #   hide the play-reversed button
        #   since JACK transport doesn't support reversed playback
        if scene.sync_mode == "AUDIO_SYNC" and context.preferences.system.audio_device == "JACK":
            row.scale_x = 1
            row.operator("screen.animation_play", text="", icon="PLAY")
            row.scale_x = 1
        else:
            row.operator("screen.animation_play", text="", icon="PLAY_REVERSE").reverse = True
            row.operator("screen.animation_play", text="", icon="PLAY")
    else:
        row.scale_x = 1
        row.operator("screen.animation_play", text="", icon="PAUSE")
        row.scale_x = 1
    if context.area.type == "GRAPH_EDITOR":
        row.operator("graph.keyframe_jump", text="", icon="NEXT_KEYFRAME").next = True
    else:
        row.operator("screen.keyframe_jump", text="", icon="NEXT_KEYFRAME").next = True
    row.operator("screen.frame_jump", text="", icon="FF").end = True


def draw_frame_ranges_header(self, context):
    layout = self.layout
    scene = context.scene

    row = layout.row()
    if scene.show_subframe:
        row.scale_x = 0.8
        row.prop(scene, "frame_float", text="")
    else:
        row.scale_x = 0.8
        row.prop(scene, "frame_current", text="")

    row.separator(factor=1)

    row = layout.row(align=True)
    row.prop(scene, "use_preview_range", text="", toggle=True)
    sub = row.row(align=True)
    sub.scale_x = 0.8
    if not scene.use_preview_range:
        sub.prop(scene, "frame_start", text="")
        sub.prop(scene, "frame_end", text="")
    else:
        sub.prop(scene, "frame_preview_start", text="")
        sub.prop(scene, "frame_preview_end", text="")


def draw_timeline_tools_header(self, context):
    layout = self.layout
    # layout.separator_spacer()

    layout.separator(factor=2)

    draw_playbuttons_header(self, context)

    layout.separator(factor=2)

    draw_frame_ranges_header(self, context)


def draw_timeline_tools_header_buttons(self, context):
    prefs = context.preferences.addons[base_package].preferences
    layout = self.layout

    sep_factor = 0.4
    big_sep_factor = sep_factor * 2

    layout.separator()

    scrub_row = layout.row(align=True)

    scrub_row.prop(
        prefs,
        "scrub_timeline_keymap_kmi_active",
        text="",
        icon_value=(
            utils.customIcons.get_icon_id("AMP_scrubber_on")
            if prefs.scrub_timeline_keymap_kmi_active
            else utils.customIcons.get_icon_id("AMP_scrubber")
        ),
        emboss=False,
    )

    layout.separator(factor=big_sep_factor)

    view_row = layout.row()

    AnimViewButtons(view_row, context)

    layout.separator(factor=big_sep_factor)

    select_row = layout.row(align=True)

    AnimCurvesButtons(select_row, context)

    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:

        # if context.area.type == "GRAPH_EDITOR":

        KeyframesButtons_Graph(layout, context, sep_factor, big_sep_factor)

        ActionButtons_Graph_Dope(layout, context, sep_factor, big_sep_factor)


def ActionButtons_Graph_Dope(layout, context, sep_factor=0.4, big_sep_factor=0.8):

    action_row = layout.row(align=True)

    AnimSculptButton(action_row, context, "", utils.customIcons.get_icon_id("AMP_anim_sculpt"))

    AnimShifterButton(action_row, context, "", utils.customIcons.get_icon_id("AMP_anim_shift"))

    AnimLoopButton(action_row, context, "", utils.customIcons.get_icon_id("AMP_anim_loop"))

    AnimSlicerButton(action_row, context, "", utils.customIcons.get_icon_id("AMP_anim_slice"))

    AnimBakerButton(action_row, context, "", utils.customIcons.get_icon_id("AMP_anim_baker"))

    action_row.popover(
        "AMP_PT_AnimStepper",
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_anim_step"),
    )

    action_row.popover(
        "AMP_PT_CameraStepperPop",
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_anim_cam_step"),
    )

    action_row.popover(
        "AMP_PT_AnimKeyPoserPop",
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_anim_keyposer"),
    )


def KeyframesButtons_Graph(layout, context, sep_factor=0.4, big_sep_factor=0.8):
    layout.separator(factor=big_sep_factor)

    kf_row = layout.row(align=True)

    AnimPoserButtons(kf_row, context)

    kf_row.separator(factor=sep_factor)

    # markers_row = layout.row(align=True)
    MarkersToolsButton(kf_row, context, "", utils.customIcons.get_icon_id("AMP_markers_tools"))

    kf_row.separator(factor=sep_factor)

    kf_row.popover(
        "AMP_PT_AnimKeyframerPopover",
        text="",
        icon_value=utils.customIcons.get_icon_id("AMP_keyframer"),
    )

    kf_row.separator(factor=sep_factor)

    draw_anim_offset_mask(kf_row, context)

    layout.separator(factor=big_sep_factor)


def refresh_button_icons(context, layout):

    # reload_icons
    layout.operator("amp.reload_icons", text="", **get_icon("AniMateProContact"), emboss=False)


class AMP_PT_AniMateProGraph(bpy.types.Panel):
    bl_label = "AniMatePro"
    bl_idname = "AMP_PT_AniMateProGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        refresh_button_icons(context, layout)

    def draw(self, context):
        layout = self.layout


class AMP_PT_AniMateProDope(bpy.types.Panel):
    bl_label = "AniMatePro"
    bl_idname = "AMP_PT_AniMateProDope"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        refresh_button_icons(context, layout)

    def draw(self, context):
        layout = self.layout


class AMP_PT_AniMateProView(bpy.types.Panel):
    bl_label = "AniMatePro"
    bl_idname = "AMP_PT_AniMateProView"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        refresh_button_icons(context, layout)

    def draw(self, context):
        layout = self.layout


class AMP_PT_AniMateProNLA(bpy.types.Panel):
    bl_label = "AniMatePro"
    bl_idname = "AMP_PT_AniMateProNLA"
    bl_space_type = "NLA_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        refresh_button_icons(context, layout)

    def draw(self, context):
        layout = self.layout


from bl_ui.space_dopesheet import dopesheet_filter


class GRAPH_HT_header(bpy.types.Header):
    bl_space_type = "GRAPH_EDITOR"

    def draw(self, context):
        layout = self.layout
        tool_settings = context.tool_settings

        st = context.space_data

        layout.template_header()

        # Now a exposed as a sub-space type
        # layout.prop(st, "mode", text="")

        GRAPH_MT_editor_menus.draw_collapsible(context, layout)

        row = layout.row(align=True)
        row.prop(st, "use_normalization", icon="NORMALIZE_FCURVES", text="Normalize", toggle=True)
        sub = row.row(align=True)
        sub.active = st.use_normalization
        sub.prop(st, "use_auto_normalization", icon="FILE_REFRESH", text="", toggle=True)

        layout.separator_spacer()

        dopesheet_filter(layout, context)

        row = layout.row(align=True)
        if st.has_ghost_curves:
            row.operator("graph.ghost_curves_clear", text="", icon="X")
        else:
            row.operator("graph.ghost_curves_create", text="", icon="FCURVE_SNAPSHOT")

        layout.popover(
            panel="GRAPH_PT_filters",
            text="",
            icon="FILTER",
        )

        layout.prop(st, "pivot_point", icon_only=True)

        row = layout.row(align=True)
        row.prop(tool_settings, "use_snap_anim", text="")
        sub = row.row(align=True)
        sub.popover(
            panel="GRAPH_PT_snapping",
            text="",
        )

        row = layout.row(align=True)
        row.prop(tool_settings, "use_proportional_fcurve", text="", icon_only=True)
        sub = row.row(align=True)
        sub.active = tool_settings.use_proportional_fcurve
        sub.prop_with_popover(
            tool_settings,
            "proportional_edit_falloff",
            text="",
            icon_only=True,
            panel="GRAPH_PT_proportional_edit",
        )


class GRAPH_MT_editor_menus(bpy.types.Menu):
    bl_idname = "GRAPH_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        st = context.space_data
        layout = self.layout
        layout.menu("GRAPH_MT_view")
        layout.menu("GRAPH_MT_select")
        if st.mode != "DRIVERS" and st.show_markers:
            layout.menu("GRAPH_MT_marker")
        layout.menu("GRAPH_MT_channel")
        layout.menu("GRAPH_MT_key")


classes = (
    AMP_PT_AniMateProGraph,
    AMP_PT_AniMateProDope,
    AMP_PT_AniMateProView,
    AMP_PT_AniMateProNLA,
    AMP_PT_Timeline_Scrubbing_Settings_Help,
    AMP_PT_Timeline_Spacebar_Action_Help,
    AMP_PT_Timeline_Scrubbing_Limits_Help,
    AMP_PT_Timeline_Scrubbing_Text_Help,
    AMP_PT_Timeline_Tools,
    AMP_PT_Timeline_Scrub,
    AMP_PT_keyframing_settings,
)


def register():
    # global custom_icons
    # custom_icons = bpy.utils.previews.new()

    for cls in classes:
        # try:
        bpy.utils.register_class(cls)
        # except ValueError as e:
        #     utils.dprint(f"Class {cls.__name__} already registered. Skipping...")


def unregister():
    # global custom_icons
    # bpy.utils.previews.remove(custom_icons)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError as e:
            utils.dprint(f"Class {cls.__name__} not found. Skipping...")


###########
## ui.py ##
###########
