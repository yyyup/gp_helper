# File ui/top_buttons_definitions.py

import bpy
from .. import utils
from ..utils.customIcons import get_icon
from .. import __package__ as base_package
from ..anim_swapper.anim_swapper import draw_active_action, draw_active_action_slots
from ..anim_offset.ui import draw_anim_offset_mask
from .addon_ui_utils import draw_button_in_context, draw_external_addon_panel_button

####################################
###            FORGE             ###
####################################


def Tools_Stepper(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas="ANY",
        icon_id="AMP_anim_cam_step",
        draw_fn=lambda l, c: l.popover(
            "AMP_PT_CameraStepperPop",
            text="",
            **get_icon("AMP_anim_cam_step"),
        ),
        experimental=True,
        requires_forge=True,
    )


def Tools_Keyposer(layout, context):
    draw_button_in_context(
        layout,
        context,
        supported_areas="ANY",
        icon_id="AMP_anim_keyposer",
        draw_fn=lambda l, c: l.popover(
            "AMP_PT_AnimKeyPoserPop",
            text="",
            **get_icon("AMP_anim_keyposer"),
        ),
        requires_forge=True,
        experimental=True,
    )


