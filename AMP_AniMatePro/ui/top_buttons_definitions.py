# File ui/top_buttons_definitions.py

import bpy
from .. import utils
from ..utils.customIcons import get_icon
from .. import __package__ as base_package
from bpy.app.translations import contexts as i18n_contexts


def AnimScrubButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        prefs = context.preferences.addons[base_package].preferences
        layout.prop(
            prefs,
            "scrub_timeline_keymap_kmi_active",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_scrubber_on")
                if prefs.scrub_timeline_keymap_kmi_active
                else utils.customIcons.get_icon_id("AMP_scrubber")
            ),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_scrubber_on"))


def AnimCurvesSoloButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        context = bpy.context
        prefs = context.preferences.addons[base_package].preferences
        row_solo = layout.row(align=True)
        has_selected_keyframes = True if bpy.context.selected_editable_keyframes else False
        is_solo = True if prefs.solo_fcurve else False
        row_solo.active = has_selected_keyframes or is_solo
        icon_value = (
            utils.customIcons.get_icon_id("AMP_solo_curve_on")
            if is_solo
            else utils.customIcons.get_icon_id("AMP_solo_curve_off")
        )
        row_solo.operator(
            "anim.amp_isolate_selected_fcurves",
            text="",
            icon_value=icon_value,
            depress=is_solo,
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_solo_curve_on"))


def AnimCurvesFrameSelectedButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        has_selected_keyframes = True if bpy.context.selected_editable_keyframes else False
        layout.operator(
            "anim.amp_zoom_frame_editors",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_zoom_curve_selected")
                if has_selected_keyframes
                else utils.customIcons.get_icon_id("AMP_zoom_curve_all")
            ),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_zoom_curve_selected"))


def AnimSmartZoomButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
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

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_zoom_smart"))


def IsolateCharacterButton(layout, context):
    props = context.scene.anim_poser_props
    row = layout.row(align=True)
    row.active = props.isolate_character
    row.prop(
        props,
        "isolate_character",
        text="",
        **get_icon("AMP_isolate_char_on" if props.isolate_character else "AMP_isolate_char_off"),
    )


def AnimCurvesFrameRange(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_timeline_tools_frame_action_range",
            text="",
            **get_icon("AMP_frame_action"),
        ).scene_range_to_action = True
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_frame_action"))


def MatchKeyframesButtons(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
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
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_match_keys_L"))
        layout.label(text="", **get_icon("AMP_match_keys_R"))


def CopyPastePose(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        row = layout.row(align=True)
        row.operator(
            "pose.copy",
            text="",
            **get_icon("AMP_pose_range_copy"),
            # emboss=False,
        )
        row.operator(
            "anim.amp_propagate_pose_to_range",
            text="",
            **get_icon("AMP_pose_range_paste"),
            # emboss=False,
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_pose_range_copy"))
        layout.label(text="", **get_icon("AMP_pose_range_paste"))


def AnimKeyframer(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover(
            "AMP_PT_AnimKeyframerPopover",
            text="",
            **get_icon("AMP_keyframer"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_keyframer"))


def MarkersToolsButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_markers_tools",
            text="",
            **get_icon("AMP_markers_tools"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_markers_tools"))


def MarkersDelete(layout, context):
    layout.operator(
        "anim.amp_delete_markers",
        text="",
        **get_icon("AMP_markers_delete_all"),
        # emboss=False,
    )


def MarkersLock(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.prop(
            context.scene.tool_settings,
            "lock_markers",
            text="",
            icon_value=(
                utils.customIcons.get_icon_id("AMP_markers_lock")
                if context.scene.tool_settings.lock_markers
                else utils.customIcons.get_icon_id("AMP_markers_unlock")
            ),
            # emboss=False,
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_markers_lock"))


def AnimSculptButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_sculpt",
            text="",
            **get_icon("AMP_anim_sculpt"),
        )
    if context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_sculpt"))


def AnimLatticeButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_lattice",
            text="",
            **get_icon("AMP_anim_lattice"),
        )
    if context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_lattice"))


def AnimTimeWarper(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_timewarper",
            text="",
            **get_icon("AMP_anim_timewarper"),
        )
    if context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_timewarper"))


def AnimShifterButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_shifter",
            text="",
            **get_icon("AMP_anim_shift"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_shift"))


def AnimLoopButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_loop",
            text="",
            **get_icon("AMP_anim_loop"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_loop"))


def AnimSlicerButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_slicer",
            text="",
            **get_icon("AMP_anim_slice"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_slice"))


def AnimBakerButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_anim_baker",
            text="",
            **get_icon("AMP_anim_baker"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_baker"))


def AnimStepperButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover(
            "AMP_PT_AnimStepper",
            text="",
            **get_icon("AMP_anim_step"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_step"))


def CameraStepperButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover(
            "AMP_PT_CameraStepperPop",
            text="",
            **get_icon("AMP_anim_cam_step"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_cam_step"))


def AnimKeyposerButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover(
            "AMP_PT_AnimKeyPoserPop",
            text="",
            **get_icon("AMP_anim_keyposer"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_anim_keyposer"))


def AnimCurvesAllButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_all",
            text="",
            **get_icon("AMP_select_curves_all"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_select_curves_all"))


def AnimCurvesLocButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_loc",
            text="",
            **get_icon("AMP_select_curves_loc"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_select_curves_loc"))


def AnimCurvesRotButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_rot",
            text="",
            **get_icon("AMP_select_curves_rot"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_select_curves_rot"))


def AnimCurvesScaleButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_scale",
            text="",
            **get_icon("AMP_select_curves_scale"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_select_curves_scale"))


def AnimCurvesOthersButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_custom_props",
            text="",
            **get_icon("AMP_select_curves_others"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_select_curves_others"))


def AnimCurvesShapesButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_shapes",
            text="",
            **get_icon("AMP_select_curves_shapes"),
        )

    else:
        layout.label(text="Shapes", **get_icon("AMP_select_curves_shapes"))


def AnimCurvesConstraintsButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.view_anim_curves_constraints",
            text="",
            **get_icon("AMP_select_curves_const"),
        )

    else:
        layout.label(
            text="",
            **get_icon("AMP_select_curves_const"),
        )


def AnimCurvesOptions(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover("AMP_PT_anim_curves_properties", text="")

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover("AMP_PT_anim_curves_properties", text="", icon="SETTINGS")


def ShowHandlesButton(layout, context):
    if context.area.type == "GRAPH_EDITOR":
        if context.space_data.show_handles:
            show_handles_icon = utils.customIcons.get_icon_id("AMP_handles_on")

        elif not context.space_data.show_handles:
            show_handles_icon = utils.customIcons.get_icon_id("AMP_handles_off")
        layout.prop(
            context.space_data,
            "show_handles",
            text="",
            icon_value=show_handles_icon,
            toggle=True,
        )
    elif context.area.type != "GRAPH_EDITOR":
        layout.label(text="", **get_icon("AMP_handles_on"))


def OnlySelectedHandlesButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR"}:
        sub_row = layout.row(align=True)
        sub_row.active = context.space_data.show_handles
        if context.space_data.use_only_selected_keyframe_handles:
            only_sel_handles_icon = utils.customIcons.get_icon_id("AMP_handles_selected")
        elif not context.space_data.use_only_selected_keyframe_handles:
            only_sel_handles_icon = utils.customIcons.get_icon_id("AMP_handles_all")
        sub_row.prop(
            context.space_data,
            "use_only_selected_keyframe_handles",
            text="",
            icon_value=only_sel_handles_icon,
            toggle=True,
            invert_checkbox=True,
        )
    elif context.area.type not in {"GRAPH_EDITOR"}:
        layout.label(text="", **get_icon("AMP_handles_all"))


def AutoKeyButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        tool_settings = context.tool_settings

        row = layout.row(align=True)
        row.prop(tool_settings, "use_keyframe_insert_auto", text="", toggle=True)
        sub = row.row(align=True)
        sub.active = tool_settings.use_keyframe_insert_auto
        if context.area.type == "TIMELINE":
            sub.popover(
                panel="TIME_PT_auto_keyframing",
                text="",
            )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", icon="RADIOBUT_ON")


def PlayButtons(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
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
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", icon="PLAY")


def SceneCurrentFrameButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        scene = context.scene

        row = layout.row()
        if scene.show_subframe:
            row.scale_x = 0.8
            row.prop(scene, "frame_float", text="")
        else:
            row.scale_x = 0.8
            row.prop(scene, "frame_current", text="")

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", icon="PREVIEW_RANGE")


def SceneRangeButtons(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
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

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", icon="SCENE")


def AnimMopaths(layout, context):
    row = layout.row(align=True)
    row.alignment = "LEFT"
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        prefs = context.preferences.addons[base_package].preferences
        if prefs.is_mopaths_active:
            layout.alert = True
            icon_value = utils.customIcons.get_icon_id("AMP_anim_mopaths_on")
        elif not prefs.is_mopaths_active:
            icon_value = utils.customIcons.get_icon_id("AMP_anim_mopaths_off")

        row.operator(
            "anim.amp_realtime_motion_paths",
            text="",
            icon_value=icon_value,
            depress=False,
        )
        row.popover(
            "AMP_PT_AnimMopathsPop",
            text="",
            # **get_icon("AMP_anim_mopaths"),
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        row.label(text="", **get_icon("AMP_anim_mopaths_on"))


def AnimEulerFilterButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_euler_filter",
            text="",
            **get_icon("AMP_curves_euler"),
            emboss=True,
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_curves_euler"))


def AnimEulerGimbalButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_euler_rotation_recommendations",
            text="",
            **get_icon("AMP_curves_gimbal"),
            emboss=True,
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_curves_gimbal"))


def AnimSmartKeyframesCleanupButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.operator(
            "anim.amp_cleanup_keyframes_from_locked_transforms",
            text="",
            **get_icon("AMP_curves_cleanup"),
            emboss=True,
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_curves_cleanup"))


def AnimNudgerButton(layout, context):
    settings = context.scene.anim_nudger_settings

    row = layout.row(align=True)
    row.operator("anim.timeline_anim_nudger", text="", **get_icon("AMP_anim_nudge_L")).direction = "LEFT"
    row.operator("anim.timeline_anim_nudger", text="", **get_icon("AMP_anim_nudge_R")).direction = "RIGHT"
    row = row.row(align=True)
    row.scale_x = 0.65
    row.prop(settings, "frames_to_nudge", text="")


def AnimInBetweenButton(layout, context):
    row = layout.row(align=True)
    row.operator("anim.anim_pusher", text="", **get_icon("AMP_inbetween_remove")).operation = "REMOVE"
    row.operator("anim.anim_pusher", text="", **get_icon("AMP_inbetween_add")).operation = "ADD"


def AnimNextPrevKeyframeButton(layout, context):
    kf_row = layout.row(align=True)

    op_prev = kf_row.operator(
        "anim.amp_jump_to_keyframe",
        text="",
        **get_icon("AMP_prev_keyframe"),
        emboss=True,
    )
    op_prev.direction = "PREVIOUS"
    # op_prev.select_keyframes = True

    op_next = kf_row.operator(
        "anim.amp_jump_to_keyframe",
        text="",
        **get_icon("AMP_next_keyframe"),
        emboss=True,
    )
    op_next.direction = "NEXT"
    # op_next.select_keyframes = True


def AnimShareKeyframesButton(layout, context):
    layout.operator(
        "anim.amp_share_keyframes",
        text="",
        **get_icon("AMP_share_keyframes"),
        emboss=True,
    )


def AnimPlayOptionsButton(layout, context):
    layout.popover(panel="TIME_PT_playback", text="", icon="PLAY")


def AnimKeyframingSettingsButton(layout, context):
    layout.popover(
        panel="AMP_PT_keyframing_settings",
        text="",
        icon="KEY_HLT",
    )


def NormalizeGraphButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR"}:
        st = context.space_data
        row = layout.row(align=True)
        row.prop(st, "use_normalization", icon="NORMALIZE_FCURVES", text="", toggle=True)
        sub = row.row(align=True)
        sub.active = st.use_normalization
        sub.prop(st, "use_auto_normalization", icon="FILE_REFRESH", text="", toggle=True)
    elif context.area.type not in {"GRAPH_EDITOR"}:
        layout.label(text="", icon="NORMALIZE_FCURVES")
        layout.label(text="", icon="FILE_REFRESH")


def AnimOffsetMoPathsButton(layout, context):
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


def AnimNLAButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="NLA",
            depress=context.area.ui_type == "NLA_EDITOR",
        )
        op.space_type = "NLA_EDITOR"
    else:
        layout.label(text="", icon="NLA")


def AnimEditorGraphButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="GRAPH",
            depress=context.area.ui_type == "FCURVES",
        )
        op.space_type = "GRAPH_EDITOR"
    else:
        layout.label(text="", icon="GRAPH")


def AnimEditorDopeSheetButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="ACTION",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "DOPESHEET",
        )
        op.subspace_type = "DOPESHEET"
        op.space_type = "DOPESHEET_EDITOR"
    else:
        layout.label(text="", icon="ACTION")


def AnimEditorActionButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="OBJECT_DATA",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "ACTION",
        )
        op.subspace_type = "ACTION"
        op.space_type = "DOPESHEET_EDITOR"
    else:
        layout.label(text="", icon="OBJECT_DATA")


def AnimEditorShapeKeyButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="SHAPEKEY_DATA",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "SHAPEKEY",
        )
        op.subspace_type = "SHAPEKEY"
        op.space_type = "DOPESHEET_EDITOR"
    else:
        layout.label(text="", icon="SHAPEKEY_DATA")


def AnimEditorGreasePencilButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="OUTLINER_OB_GREASEPENCIL",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "GPENCIL",
        )
        op.subspace_type = "GPENCIL"
        op.space_type = "DOPESHEET_EDITOR"
    else:
        layout.label(text="", icon="OUTLINER_OB_GREASEPENCIL")


def AnimEditorMaskButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="MOD_MASK",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "MASK",
        )
        op.subspace_type = "MASK"
        op.space_type = "DOPESHEET_EDITOR"
    else:
        layout.label(text="", icon="MOD_MASK")


def AnimEditorCacheFileButton(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        op = layout.operator(
            "space.amp_animation_editors",
            text="",
            icon="FILE",
            depress=context.area.ui_type == "DOPESHEET" and context.space_data.ui_mode == "CACHEFILE",
        )
        op.subspace_type = "CACHEFILE"
        op.space_type = "DOPESHEET_EDITOR"
    else:
        layout.label(text="", icon="FILE")


def AnimSelectionSets(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.popover(
            "AMP_PT_AnimSetsPanelPop",
            text="",
            **get_icon("AMP_select_sets"),
        )
    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", **get_icon("AMP_select_sets"))


def AnimRealtimeLooper(layout, context):
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
