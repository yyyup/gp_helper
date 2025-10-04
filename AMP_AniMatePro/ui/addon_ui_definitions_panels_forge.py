# filepath: g:\My Drive\Dev\Blender Addons\@in_dev\GitLab\animatepro\AMP_AniMatePro\ui\addon_ui_definitions_panels_forge.py

import bpy
from ..utils.customIcons import get_icon
from ..utils import get_prefs
from .addon_ui_utils import (
    draw_panel_as_section,
    create_external_panel_function,
)


#############################
###   PLACEHOLDER FORGE   ###
#############################


def Panels_ForgeFeatures(layout, context):
    """General Forge Features Panel"""
    box = layout.box()
    col = box.column(align=True)
    col.label(text="Forge Features", icon="TOOL_SETTINGS")
    col.label(text="Additional features available in", icon="INFO")
    col.label(text="the Forge version of AniMatePro")

    row = col.row()
    row.operator("wm.url_open", text="Get Forge Version", **get_icon("AMP_Forge")).url = (
        "https://nda.gumroad.com/l/animate_forge"
    )


#############################
###    ANIM STEPPER      ###
#############################


def Panels_AnimStepper(layout, context):
    """Animation Stepper Panel - Forge exclusive"""
    from ..forge_modules.anim_stepper.anim_stepper import draw_stepper_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Anim Stepper",
        icon_name="AMP_anim_cam_step",
        draw_function=draw_stepper_panel,
        panel_id="anim_stepper",
        requires_forge=True,
        experimental=True,
    )


#############################
###        KEY POSER      ###
#############################


def Panels_Keyposer(layout, context):
    """Key Poser Panel"""
    from ..forge_modules.anim_key_poser.anim_key_poser import draw_anim_keyposer_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Key Poser (Experimental)",
        icon_name="Experimental",
        draw_function=draw_anim_keyposer_panel,
        panel_id="key_poser",
        requires_forge=True,
        experimental=True,
    )


#############################
###     POSE POLATOR      ###
#############################


def Panels_PosePolator(layout, context):
    """Pose Polator Panel"""
    from ..forge_modules.anim_pose_polator.anim_pose_polator import draw_posepolator_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Pose Polator (Experimental)",
        icon_name="Experimental",
        draw_function=draw_posepolator_panel,
        panel_id="pose_polator",
        requires_forge=True,
        experimental=True,
    )


#############################
###     POSE POLATOR      ###
#############################


def Panels_AnimLink(layout, context):
    """Anim Link Panel"""
    from ..forge_modules.anim_link.anim_link import draw_anim_link_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Anim Link (Experimental)",
        icon_name="Experimental",
        draw_function=draw_anim_link_panel,
        panel_id="anim_link",
        requires_forge=True,
        experimental=True,
    )
