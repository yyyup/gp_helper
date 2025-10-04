# File ui/top_buttons_definitions.py

import bpy
from .. import utils
from ..utils.customIcons import get_icon
from .. import __package__ as base_package
from ..anim_swapper.anim_swapper import draw_active_action, draw_active_action_slots
from ..anim_offset.ui import draw_anim_offset_mask
from .addon_ui_utils import draw_button_in_context, draw_external_addon_panel_button


#############################
###         TOOLS         ###
#############################
# scrub, sculpt, lattice, timewarper, shifter, slicer, stepper, retimer, looper


def Tools_Sculpt(layout, context):
    def _draw(layout, context):
        layout.operator(
            "anim.amp_anim_sculpt",
            text="",
            **get_icon("AMP_anim_sculpt"),
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_sculpt",
        draw_fn=_draw,
    )


def Tools_LatticeBox(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "anim.amp_anim_lattice",
            text="",
            **get_icon("AMP_anim_lattice"),
        )
        op.mode = "NORMAL"

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_lattice",
        draw_fn=_draw,
    )


def Tools_LatticeWarp(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "anim.amp_anim_lattice",
            text="",
            **get_icon("AMP_anim_lattice"),
        )
        op.mode = "WARP"

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_lattice",
        draw_fn=_draw,
        experimental=True,  # Mark this as experimental for testing
    )


def Tools_TimeWarper(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_timewarper",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_anim_timewarper",
            text="",
            **get_icon("AMP_anim_timewarper"),
        ),
    )


def Tools_Shifter(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_shift",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_anim_shifter",
            text="",
            **get_icon("AMP_anim_shift"),
        ),
    )


def Tools_Looper(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_loop",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_anim_loop",
            text="",
            **get_icon("AMP_anim_loop"),
        ),
    )


def Tools_Slicer(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_slice",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_anim_slicer",
            text="",
            **get_icon("AMP_anim_slice"),
        ),
    )


def Tools_ToolsTimeBlocker(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_anim_timeblocker",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_anim_timeblocker",
            text="",
            **get_icon("AMP_anim_timeblocker"),
        ),
    )


#############################
###         VIEW          ###
#############################


def View_Scrub(layout, context):
    def _draw(layout, context):
        prefs = context.preferences.addons[base_package].preferences
        layout.prop(
            prefs,
            "scrub_timeline_keymap_kmi_active",
            text="",
            **get_icon("AMP_scrubber_on" if prefs.scrub_timeline_keymap_kmi_active else "AMP_scrubber"),
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_scrubber",
        draw_fn=_draw,
    )


def View_CurvesSolo(layout, context):
    def _draw(layout, context):
        prefs = context.preferences.addons[base_package].preferences
        row = layout.row(align=True)
        is_solo = prefs.solo_fcurve
        row.operator(
            "anim.amp_isolate_selected_fcurves",
            text="",
            **get_icon("AMP_solo_curve_on" if is_solo else "AMP_solo_curve_off"),
            depress=is_solo,
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_solo_curve_on",
        draw_fn=_draw,
    )


def View_CurvesFrameSelected(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_zoom_curve_selected",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_zoom_frame_editors",
            text="",
            **get_icon("AMP_zoom_curve_selected"),
        ),
    )


def View_CurvesFrameRange(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_frame_action",
        draw_fn=lambda l, c: setattr(
            l.operator(
                "anim.amp_timeline_tools_frame_action_range",
                text="",
                **get_icon("AMP_frame_action"),
            ),
            "scene_range_to_action",
            True,
        ),
    )


def View_SmartZoom(layout, context):
    def _draw(layout, context):
        prefs = context.preferences.addons[base_package].preferences
        row = layout.row(align=True)
        row.operator(
            "anim.amp_smart_zoom_frame_editors",
            text="",
            **get_icon("AMP_zoom_smart"),
            emboss=True,
        ).frame_range_smart_zoom = 0
        range_row = row.row(align=True)
        range_row.scale_x = 0.65
        range_row.prop(
            prefs,
            "frame_range_smart_zoom",
            text="",
            toggle=True,
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_zoom_smart",
        draw_fn=_draw,
    )


################################
###        SELECTIONS        ###
################################


def Selections_CurvesAll(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_all",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_all",
            text="",
            **get_icon("AMP_select_curves_all"),
        ),
    )


def Selections_CurvesLoc(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_loc",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_loc",
            text="",
            **get_icon("AMP_select_curves_loc"),
        ),
    )


def Selections_CurvesRot(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_rot",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_rot",
            text="",
            **get_icon("AMP_select_curves_rot"),
        ),
    )


def Selections_CurvesScale(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_scale",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_scale",
            text="",
            **get_icon("AMP_select_curves_scale"),
        ),
    )


def Selections_CurvesOthers(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_others",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_custom_props",
            text="",
            **get_icon("AMP_select_curves_others"),
        ),
    )


def Selections_CurvesShapes(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_shapes",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_shapes",
            text="",
            **get_icon("AMP_select_curves_shapes"),
        ),
    )


def Selections_CurvesConstraints(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"},
        icon_id="AMP_select_curves_const",
        draw_fn=lambda l, c: l.operator(
            "anim.view_anim_curves_constraints",
            text="",
            **get_icon("AMP_select_curves_const"),
        ),
    )


def Selections_ShowHandles(layout, context):
    def _draw(layout, context):
        sd = context.space_data
        layout.prop(
            sd,
            "show_handles",
            text="",
            **get_icon("AMP_handles_on" if sd.show_handles else "AMP_handles_off"),
            toggle=True,
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR"},
        icon_id="AMP_handles_on",
        draw_fn=_draw,
    )


def Selections_OnlySelectedHandles(layout, context):
    def _draw(layout, context):
        sd = context.space_data
        row = layout.row(align=True)
        row.active = sd.show_handles
        row.prop(
            sd,
            "use_only_selected_keyframe_handles",
            text="",
            **get_icon("AMP_handles_selected" if sd.use_only_selected_keyframe_handles else "AMP_handles_all"),
            toggle=True,
            invert_checkbox=True,
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR"},
        icon_id="AMP_handles_all",
        draw_fn=_draw,
    )


def Selections_SelectionSets(layout, context):
    layout.popover(
        "AMP_PT_AnimSetsPanelPop",
        text="",
        **get_icon("AMP_select_sets"),
    )


def Selections_SelectionsOptions(layout, context):
    layout.popover(
        "AMP_PT_anim_curves_properties",
        text="",
        **get_icon("SETTINGS"),
    )


#############################
###        TOGGLES        ###
#############################


def Toggles_IsolateCharacter(layout, context):
    props = context.scene.anim_poser_props
    row = layout.row(align=True)
    row.active = props.isolate_character
    row.prop(
        props,
        "isolate_character",
        text="",
        **get_icon("AMP_isolate_char_on" if props.isolate_character else "AMP_isolate_char_off"),
    )


def Toggles_RealtimeMopaths(layout, context):
    row = layout.row(align=True)
    row.alignment = "LEFT"
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        prefs = context.preferences.addons[base_package].preferences

        row.operator(
            "anim.amp_realtime_motion_paths",
            text="",
            **get_icon("AMP_anim_mopaths_on" if prefs.is_mopaths_active else "AMP_anim_mopaths_off"),
            depress=False,
        )
        row.popover(
            "AMP_PT_AnimMopathsPop",
            text="",
            ##*get_icon("AMP_anim_mopaths"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        row.label(text="", **get_icon("AMP_anim_mopaths_on"))


def Toggles_OffsetMopaths(layout, context):
    props = context.scene.mp_props
    row = layout.row(align=True)
    row.alignment = "LEFT"
    row.operator(
        "anim.amp_fmp_toggle_show_motion_paths",
        text="",
        **get_icon("AMP_flexmopaths_on" if props.show_motion_paths else "AMP_flexmopaths_off"),
        emboss=True,
    )
    row.popover("AMP_FMP_PT_OffsetMoPathsPanel", text="")


def Toggles_RealtimeLooper(layout, context):
    # if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
    row = layout.row(align=True)
    row.operator(
        "anim.amp_toggle_anim_looper_handler",
        text="",
        **get_icon(
            "AMP_realtimelooper_on" if context.scene.realtime_looper_handler_active else "AMP_realtimelooper_off"
        ),
        depress=True if context.scene.realtime_looper_handler_active else False,
    )
    # elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
    #     layout.label(text="", **get_icon("CHECKMARK"))


################################
###         MARKERS          ###
################################


def Markers_Insert(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_markers_tools",
        draw_fn=lambda l, c: l.operator("anim.amp_markers_tools", text="", **get_icon("AMP_markers_tools")),
    )


def Markers_Delete(layout, context):
    layout.operator(
        "anim.amp_delete_markers",
        text="",
        **get_icon("AMP_markers_delete_all"),
        # emboss=False,
    )


def Markers_Lock(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_markers_lock",
        draw_fn=lambda l, c: l.prop(
            c.scene.tool_settings,
            "lock_markers",
            text="",
            **get_icon("AMP_markers_lock" if c.scene.tool_settings.lock_markers else "AMP_markers_unlock"),
        ),
    )


###############################
###        PLAYBACK         ###
###############################


def Playback_AutoKey(layout, context):

    def _draw(layout, context):
        ts = context.tool_settings
        row = layout.row(align=True)
        row.prop(ts, "use_keyframe_insert_auto", text="", toggle=True)

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"},
        icon_id="RADIOBUT_ON",
        draw_fn=lambda l, c: _draw(l, c),
    )


def Playback_PlaybackButtons(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"}:
        scene = context.scene
        screen = context.screen

        row = layout.row(align=True)
        row.scale_x = 1
        row.operator("screen.frame_jump", text="", icon="REW").end = False
        if context.area.type == "GRAPH_EDITOR":
            row.operator("graph.keyframe_jump", text="", icon="PREV_KEYFRAME").next = False
        else:
            row.operator("screen.keyframe_jump", text="", icon="PREV_KEYFRAME").next = False
        if not screen.is_animation_playing:
            if scene.sync_mode == "AUDIO_SYNC" and context.preferences.system.audio_device == "JACK":
                row.scale_x = 1
                row.operator("screen.animation_play", text="", icon="PLAY")
                row.scale_x = 1
            else:
                row.operator("screen.animation_play", text="", icon="PLAY_REVERSE").reverse = True
                row.operator("screen.animation_play", text="", icon="PLAY")
        else:
            row_pause = row.row()
            row_pause.scale_x = 2
            row_pause.operator("screen.animation_play", text="", icon="PAUSE")
            row_pause.scale_x = 1
        if context.area.type == "GRAPH_EDITOR":
            row.scale_x = 1
            row.operator("graph.keyframe_jump", text="", icon="NEXT_KEYFRAME").next = True
        else:
            row.operator("screen.keyframe_jump", text="", icon="NEXT_KEYFRAME").next = True
        row.operator("screen.frame_jump", text="", icon="FF").end = True
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"}:
        layout.label(text="", icon="PLAY")


def Playback_SceneCurrentFrame(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"}:
        scene = context.scene

        row = layout.row()
        if scene.show_subframe:
            row.scale_x = 0.8
            row.prop(scene, "frame_float", text="")
        else:
            row.scale_x = 0.8
            row.prop(scene, "frame_current", text="")

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"}:
        layout.label(text="", icon="PREVIEW_RANGE")


def Playback_SceneRange(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"}:
        scene = context.scene

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

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"}:
        layout.label(text="", icon="SCENE")


##############################
###        CLEANUP         ###
##############################


def Cleanup_EulerFilter(layout, context):
    def _draw(layout, context):
        layout.operator(
            "anim.amp_euler_filter",
            text="",
            **get_icon("AMP_curves_euler"),
            emboss=True,
        )

    draw_button_in_context(
        layout, context, supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"}, icon_id="AMP_curves_euler", draw_fn=_draw
    )


def Cleanup_EulerGimbal(layout, context):
    def _draw(layout, context):
        layout.operator(
            "anim.amp_euler_rotation_recommendations",
            text="",
            **get_icon("AMP_curves_gimbal"),
            emboss=True,
        )

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_curves_gimbal",
        draw_fn=_draw,
    )


def Cleanup_SmartKeyframesCleanup(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="AMP_curves_cleanup",
        draw_fn=lambda l, c: l.operator(
            "anim.amp_cleanup_keyframes_from_locked_transforms", text="", **get_icon("AMP_curves_cleanup"), emboss=True
        ),
    )


################################
###        KEYFRAMES         ###
################################


def Keyframes_InBetween(layout, context):
    row = layout.row(align=True)
    row.operator("anim.anim_pusher", text="", **get_icon("AMP_inbetween_remove")).operation = "REMOVE"
    row.operator("anim.anim_pusher", text="", **get_icon("AMP_inbetween_add")).operation = "ADD"


def Keyframes_Nudger(layout, context):
    settings = context.scene.anim_nudger_settings

    row = layout.row(align=True)
    row.operator("anim.timeline_anim_nudger", text="", **get_icon("AMP_anim_nudge_L")).direction = "LEFT"
    row.operator("anim.timeline_anim_nudger", text="", **get_icon("AMP_anim_nudge_R")).direction = "RIGHT"
    sub_row = row.row(align=True)
    sub_row.scale_x = 0.65
    sub_row.prop(settings, "frames_to_nudge", text="")


def Keyframes_NextPrevKeyframe(layout, context):
    kf_row = layout.row(align=True)

    op_prev = kf_row.operator(
        "anim.amp_jump_to_keyframe",
        text="",
        **get_icon("AMP_prev_keyframe"),
        emboss=True,
    )
    op_prev.direction = "PREVIOUS"
    op_prev.select_keyframes = True

    op_next = kf_row.operator(
        "anim.amp_jump_to_keyframe",
        text="",
        **get_icon("AMP_next_keyframe"),
        emboss=True,
    )
    op_next.direction = "NEXT"
    op_next.select_keyframes = True


def Keyframes_InBetween(layout, context):
    row = layout.row(align=True)
    row.operator("anim.anim_pusher", text="", **get_icon("AMP_inbetween_remove")).operation = "REMOVE"
    row.operator("anim.anim_pusher", text="", **get_icon("AMP_inbetween_add")).operation = "ADD"


def Keyframes_MatchKeyframes(layout, context):
    row = layout.row(align=True)
    row.operator(
        "anim.amp_match_selected_keyframe_values",
        text="",
        **get_icon("AMP_match_keys_L"),
        # emboss=False,
    ).to_right = False
    row.operator(
        "anim.amp_match_selected_keyframe_values",
        text="",
        **get_icon("AMP_match_keys_R"),
        # emboss=False,
    ).to_right = True


def Keyframes_ShareKeyframes(layout, context):
    layout.operator(
        "anim.amp_share_keyframes",
        text="",
        **get_icon("AMP_share_keyframes"),
        emboss=True,
    )


#############################
###          UI           ###
#############################


def UI_NormalizeGraph(layout, context):
    def _draw(layout, context):
        st = context.space_data
        row = layout.row(align=True)
        row.prop(st, "use_normalization", icon="NORMALIZE_FCURVES", text="", toggle=True)
        sub = row.row(align=True)
        sub.active = st.use_normalization
        sub.prop(st, "use_auto_normalization", icon="FILE_REFRESH", text="", toggle=True)

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR"},
        icon_id="NORMALIZE_FCURVES",
        draw_fn=_draw,
    )


def UI_PlayOptions(layout, context):
    layout.popover(panel="TIME_PT_playback", text="", icon="PLAY")


def UI_KeyframingSettings(layout, context):
    layout.popover(
        panel="AMP_PT_keyframing_settings",
        text="",
        icon="KEY_HLT",
    )


#############################
###         EDITORS       ###
#############################

# All possible Blender editor areas for universal editor switching
all_editor_areas = {
    "VIEW_3D",
    "IMAGE_EDITOR",
    "NODE_EDITOR",
    "SEQUENCE_EDITOR",
    "CLIP_EDITOR",
    "DOPESHEET_EDITOR",
    "GRAPH_EDITOR",
    "NLA_EDITOR",
    "TEXT_EDITOR",
    "CONSOLE",
    "INFO",
    "TOPBAR",
    "STATUSBAR",
    "OUTLINER",
    "PROPERTIES",
    "FILE_BROWSER",
    "SPREADSHEET",
    "PREFERENCES",
}

# Original editor areas for animation-specific tools
editor_areas = {
    "GRAPH_EDITOR",
    "DOPESHEET_EDITOR",
    "NLA_EDITOR",
}


def Editors_NLA(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="NLA",
            depress=context.area.ui_type == "NLA_EDITOR",
        )
        op.space_type = "NLA_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="NLA", draw_fn=_draw)


def Editors_Graph(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="GRAPH",
            depress=context.area.ui_type == "FCURVES",
        )
        op.space_type = "GRAPH_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="GRAPH", draw_fn=_draw)


def Editors_DopeSheet(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="ACTION",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "DOPESHEET",
        )
        op.subspace_type = "DOPESHEET"
        op.space_type = "DOPESHEET_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="ACTION", draw_fn=_draw)


def Editors_Action(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="OBJECT_DATA",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "ACTION",
        )
        op.subspace_type = "ACTION"
        op.space_type = "DOPESHEET_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="OBJECT_DATA", draw_fn=_draw)


def Editors_ShapeKey(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="SHAPEKEY_DATA",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "SHAPEKEY",
        )
        op.subspace_type = "SHAPEKEY"
        op.space_type = "DOPESHEET_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="SHAPEKEY_DATA", draw_fn=_draw)


def Editors_GreasePencil(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="OUTLINER_OB_GREASEPENCIL",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "GPENCIL",
        )
        op.subspace_type = "GPENCIL"
        op.space_type = "DOPESHEET_EDITOR"

    draw_button_in_context(
        layout,
        context,
        supported_areas=all_editor_areas,
        icon_id="OUTLINER_OB_GREASEPENCIL",
        draw_fn=_draw,
    )


def Editors_Mask(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="MOD_MASK",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "MASK",
        )
        op.subspace_type = "MASK"
        op.space_type = "DOPESHEET_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="MOD_MASK", draw_fn=_draw)


def Editors_CacheFile(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="FILE",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "CACHEFILE",
        )
        op.subspace_type = "CACHEFILE"
        op.space_type = "DOPESHEET_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="FILE", draw_fn=_draw)


def Editors_Timeline(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="TIME",
            depress=context.area.ui_type == "TIMELINE",
        )
        op.space_type = "TIMELINE"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="TIME", draw_fn=_draw)


def Editors_AssetBrowser(layout, context):
    def _draw(layout, context):
        # Check if we're in a FILE_BROWSER with ASSETS browse_mode
        is_asset_browser = (
            context.area.type == "FILE_BROWSER"
            and hasattr(context.space_data, "browse_mode")
            and context.space_data.browse_mode == "ASSETS"
        )
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="ASSET_MANAGER",
            depress=is_asset_browser,
        )
        op.space_type = "FILE_BROWSER"
        op.subspace_type = "ASSETS"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="ASSET_MANAGER", draw_fn=_draw)


def Editors_AllEditors(layout, context):
    def _draw(layout, context):
        row = layout.row(align=True)
        row.alignment = "LEFT"
        row.template_header()

    draw_button_in_context(
        layout,
        context,
        supported_areas={context.area.type},
        icon_id="",
        draw_fn=_draw,
    )


####################################
###         EXPERIMENTAL         ###
####################################


# def Experimental_ToolsBaker(layout, context):
#     draw_button_in_context(
#         layout,
#         context,
#         supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
#         icon_id="AMP_anim_baker",
#         draw_fn=lambda l, c: l.operator(
#             "anim.amp_anim_baker",
#             text="",
#             **get_icon("AMP_anim_baker"),
#         ),
#     )


####################################
###        ANIM OFFSET           ###
####################################


def AnimOffset_AnimOffset(layout, context):

    def _draw(layout, context):
        draw_anim_offset_mask(layout, context)

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR"},
        icon_id="TEMP",
        draw_fn=_draw,
    )


####################################
###      ACTION SWAPPER          ###
####################################


def ActionSwapper_ActiveAction(layout, context):
    """Active Action management UI from Action Swapper"""

    def _draw(layout, context):
        draw_active_action(layout, context)

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR", "VIEW_3D"},
        icon_id="ACTION",
        draw_fn=_draw,
    )


def ActionSwapper_ActionSlots(layout, context):
    """Action Slots UI for Blender 4.4+ layered actions"""

    def _draw(layout, context):
        if bpy.app.version >= (4, 4):
            if context.object and context.object.animation_data and context.object.animation_data.action:
                draw_active_action_slots(layout, context)

    draw_button_in_context(
        layout,
        context,
        supported_areas={"GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR", "VIEW_3D"},
        icon_id="NLA_PUSHDOWN",
        draw_fn=_draw,
    )


####################################
###      EXTERNAL ADDONS         ###
####################################


def ExternalAddons_TransformatorCopyTransforms(layout, context):
    """Copy Transforms panel from Transformator addon"""
    draw_external_addon_panel_button(
        layout,
        context,
        panel_class_name="AMP_CT_PT_CopyPasteTransforms",
        method_name="draw_compact_labels",
        fallback_label="Get Transformator",
        fallback_urls={
            "super_hive": "https://blendermarket.com/products/amp-transformator",
            "gumroad": "https://nda.gumroad.com/l/amp_transformator",
        },
        icon_id="AMP_transformator",
    )


def ExternalAddons_TransformatorTempPivot(layout, context):
    """Temp Pivot panel from Transformator addon"""
    draw_external_addon_panel_button(
        layout,
        context,
        panel_class_name="AMP_TEMP_CONTROLS_PT_Panel_Compact",
        method_name="draw_compact",
        fallback_label="Get Transformator",
        fallback_urls={
            "super_hive": "https://blendermarket.com/products/amp-transformator",
            "gumroad": "https://nda.gumroad.com/l/amp_transformator",
        },
        icon_id="AMP_transformator",
    )


def ExternalAddons_TransformatorPinTransforms(layout, context):
    """Pin Transforms panel from Transformator addon"""
    draw_external_addon_panel_button(
        layout,
        context,
        panel_class_name="PIN_CT_PT_PinTransforms",
        method_name="draw_compact",
        fallback_label="Get Transformator",
        fallback_urls={
            "super_hive": "https://blendermarket.com/products/amp-transformator",
            "gumroad": "https://nda.gumroad.com/l/amp_transformator",
        },
        icon_id="AMP_transformator",
    )


# def ExternalAddons_RigUI(layout, context):
#     """Rig UI panel from Rig UI addon"""
#     draw_external_addon_panel_button(
#         layout,
#         context,
#         panel_class_name="AMP_PT_RigUI",
#         method_name="draw",
#         fallback_label="Get Rig UI",
#         fallback_urls={
#             "super_hive": "https://blendermarket.com/products/rig-ui",
#             "gumroad": "https://gumroad.com/l/rig-ui",
#         },
#         icon_id="AMP_rig_ui",
#     )
def Editors_Drivers(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="DRIVER",
            depress=context.area.ui_type == "DRIVERS",
        )
        op.space_type = "DRIVERS_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="DRIVER", draw_fn=_draw)


def Editors_3DViewport(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="VIEW3D",
            depress=context.area.ui_type == "VIEW_3D",
        )
        op.space_type = "VIEW_3D"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="VIEW3D", draw_fn=_draw)


def Editors_ImageEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="IMAGE",
            depress=context.area.ui_type == "IMAGE_EDITOR",
        )
        op.space_type = "IMAGE_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="IMAGE", draw_fn=_draw)


def Editors_UVEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="UV",
            depress=context.area.ui_type == "UV",
        )
        op.space_type = "IMAGE_EDITOR"
        op.subspace_type = "UV"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="UV", draw_fn=_draw)


def Editors_Compositor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="NODE_COMPOSITING",
            depress=context.area.ui_type == "CompositorNodeTree",
        )
        op.space_type = "NODE_EDITOR"
        op.subspace_type = "CompositorNodeTree"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="NODE_COMPOSITING", draw_fn=_draw)


def Editors_TextureNodeEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="NODE_TEXTURE",
            depress=context.area.ui_type == "TextureNodeTree",
        )
        op.space_type = "NODE_EDITOR"
        op.subspace_type = "TextureNodeTree"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="NODE_TEXTURE", draw_fn=_draw)


def Editors_GeometryNodeEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="GEOMETRY_NODES",
            depress=context.area.ui_type == "GeometryNodeTree",
        )
        op.space_type = "NODE_EDITOR"
        op.subspace_type = "GeometryNodeTree"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="GEOMETRY_NODES", draw_fn=_draw)


def Editors_ShaderEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="NODE_MATERIAL",
            depress=context.area.ui_type == "ShaderNodeTree",
        )
        op.space_type = "NODE_EDITOR"
        op.subspace_type = "ShaderNodeTree"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="NODE_MATERIAL", draw_fn=_draw)


def Editors_VideoSequencer(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="SEQUENCE",
            depress=context.area.ui_type == "SEQUENCE_EDITOR",
        )
        op.space_type = "SEQUENCE_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="SEQUENCE", draw_fn=_draw)


def Editors_MovieClipEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="TRACKER",
            depress=context.area.ui_type == "CLIP_EDITOR",
        )
        op.space_type = "CLIP_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="TRACKER", draw_fn=_draw)


def Editors_TextEditor(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="TEXT",
            depress=context.area.ui_type == "TEXT_EDITOR",
        )
        op.space_type = "TEXT_EDITOR"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="TEXT", draw_fn=_draw)


def Editors_PythonConsole(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="CONSOLE",
            depress=context.area.ui_type == "CONSOLE",
        )
        op.space_type = "CONSOLE"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="CONSOLE", draw_fn=_draw)


def Editors_Info(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="INFO",
            depress=context.area.ui_type == "INFO",
        )
        op.space_type = "INFO"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="INFO", draw_fn=_draw)


def Editors_Outliner(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="OUTLINER",
            depress=context.area.ui_type == "OUTLINER",
        )
        op.space_type = "OUTLINER"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="OUTLINER", draw_fn=_draw)


def Editors_Properties(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="PROPERTIES",
            depress=context.area.ui_type == "PROPERTIES",
        )
        op.space_type = "PROPERTIES"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="PROPERTIES", draw_fn=_draw)


def Editors_FileBrowser(layout, context):
    def _draw(layout, context):
        # Check if we're in a FILE_BROWSER that's NOT in ASSETS mode
        is_file_browser = context.area.type == "FILE_BROWSER" and (
            not hasattr(context.space_data, "browse_mode") or context.space_data.browse_mode != "ASSETS"
        )
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="FILEBROWSER",
            depress=is_file_browser,
        )
        op.space_type = "FILE_BROWSER"
        op.subspace_type = "FILES"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="FILEBROWSER", draw_fn=_draw)


def Editors_Spreadsheet(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="SPREADSHEET",
            depress=context.area.ui_type == "SPREADSHEET",
        )
        op.space_type = "SPREADSHEET"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="SPREADSHEET", draw_fn=_draw)


def Editors_Preferences(layout, context):
    def _draw(layout, context):
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="PREFERENCES",
            depress=context.area.ui_type == "PREFERENCES",
        )
        op.space_type = "PREFERENCES"

    draw_button_in_context(layout, context, supported_areas=all_editor_areas, icon_id="PREFERENCES", draw_fn=_draw)
