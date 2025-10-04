# filepath: g:\My Drive\Dev\Blender Addons\@in_dev\GitLab\animatepro\AMP_AniMatePro\ui\addon_ui_definitions_panels.py

import bpy
from ..utils.customIcons import get_icon
from ..utils import get_prefs
from .addon_ui_utils import (
    draw_panel_as_section,
    create_external_panel_function,
)


def validate_external_panel_exists(panel_class_name):
    """
    Check if an external panel class exists in bpy.types.

    Args:
        panel_class_name (str): The name of the panel class to check

    Returns:
        bool: True if the panel class exists in bpy.types, False otherwise
    """
    try:
        return hasattr(bpy.types, panel_class_name)
    except Exception:
        return False


#############################
###     CUSTOM PANEL      ###
#############################


def Panels_CustomPanel(layout, context):
    """Custom Panel - placeholder for custom panel selection"""
    # This function is just a placeholder - it should not be used directly
    # The actual custom panel drawing is handled in _handle_panel_row
    # in addon_ui.py based on the custom_panel property
    box = layout.box()
    col = box.column(align=True)
    col.label(text="Custom Panel", icon="PLUGIN")
    col.label(text="Select 'Custom Panel' and enter")
    col.label(text="a Blender panel class name")
    col.separator()
    col.label(text="Tip: Use conditional expressions like:", icon="INFO")
    col.label(text="validate_external_panel_exists('ANIMLAYERS_PT_VIEW_3D_List')")
    col.label(text="to hide panels when external addons aren't available")


#############################
###      RETIMER PANEL    ###
#############################


def Panels_AnimRetimer(layout, context):
    """Animation Retimer Panel"""
    from ..anim_retimer.anim_retimer import draw_animretimer_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Anim Retimer",
        icon_name="AMP_anim_retimer",
        draw_function=draw_animretimer_panel,
        panel_id="anim_retimer",
    )


#############################
###    KEYFRAMER PANEL    ###
#############################


def Panels_AnimKeyframer(layout, context):
    """Animation Keyframer Panel"""
    from ..anim_keyframer.anim_keyframer import draw_keyframer_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Anim Keyframer",
        icon_name="AMP_keyframer",
        draw_function=draw_keyframer_panel,
        panel_id="anim_keyframer",
    )


#############################
###    MOPATHS PANEL      ###
#############################


def Panels_AnimMopaths(layout, context):
    """Animation Motion Paths Panel"""
    from ..anim_mopaths.anim_mopaths import AnimMopathsButtons

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Anim Mopaths",
        icon_name="AMP_anim_mopaths",
        draw_function=lambda panel, ctx: AnimMopathsButtons(panel.layout, ctx),
        panel_id="anim_mopaths",
    )


#############################
###  OFFSET MOPATHS PANEL ###
#############################


def Panels_OffsetMopaths(layout, context):
    """Offset Motion Paths Panel"""
    from ..anim_mopaths.anim_offset_mopaths import draw_offsetmopaths_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Offset MoPaths",
        icon_name="AMP_flexmopaths",
        draw_function=draw_offsetmopaths_panel,
        panel_id="offset_mopaths",
    )


#############################
###  SELECTION SETS PANEL ###
#############################


def Panels_SelectionSets(layout, context):
    """Selection Sets Panel"""
    from ..anim_selection_sets.anim_selection_sets import draw_main_panel as draw_selection_sets_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Selection Sets",
        icon_name="AMP_select_sets",
        draw_function=draw_selection_sets_panel,
        panel_id="selection_sets",
    )


#############################
###  ACTION SWAPPER PANEL ###
#############################


def Panels_ActionSwapper(layout, context):
    """Action Swapper Panel"""
    from ..anim_swapper.anim_swapper import draw_action_swapper

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Action Swapper",
        icon_name="ACTION",
        draw_function=draw_action_swapper,
        panel_id="action_swapper",
    )


#############################
###    ANIM MODIFIERS     ###
#############################


def Panels_AnimModifiers(layout, context):
    """Anim Modifiers Panel"""
    from ..anim_modifiers.anim_modifiers_ui import draw_anim_modifiers_panel

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Anim Modifiers (Experimental)",
        icon_name="Experimental",
        draw_function=draw_anim_modifiers_panel,
        panel_id="anim_modifiers",
        experimental=True,
    )


#############################
###        RIG UI         ###
#############################


def Panels_RigUI(layout, context):

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Rig UI",
        icon_name="Experimental",
        draw_function=create_external_panel_function(
            panel_class_name="RIG_UI_PT_RigUIPopOver",
            fallback_message="Install AMP Rig UI addon to enable this panel",
        ),
        panel_id="rig_ui",
        experimental=True,
    )


#############################
###      TRANSFORMATOR    ###
#############################


def Panels_Transformator(layout, context):

    draw_panel_as_section(
        layout=layout,
        context=context,
        panel_name="Transformator",
        icon_name="Experimental",
        draw_function=create_external_panel_function(
            panel_class_name="AMP_CT_PT_Transformator",
            fallback_message="Install Transformator addon to enable this panel",
        ),
        panel_id="transformator",
        experimental=True,
    )
