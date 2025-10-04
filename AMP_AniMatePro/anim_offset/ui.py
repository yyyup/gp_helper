import bpy
from . import support
from bpy.types import Panel, Menu
from .. import utils

from .. import __package__ as base_package


def draw_anim_offset(layout, context):
    row = layout.row(align=True)
    row.separator()

    if support.magnet_handlers in bpy.app.handlers.depsgraph_update_post:
        row.operator(
            "anim.amp_deactivate_anim_offset",
            text="",
            depress=False,
            emboss=False,
            icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_start"),
        )
    else:
        row.operator(
            "anim.amp_activate_anim_offset",
            text="",
            icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_start"),
            depress=False,
            emboss=False,
        )


def draw_anim_offset_mask(layout, context):
    if context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        row = layout.row(align=True)
        # row.separator()

        if support.magnet_handlers in bpy.app.handlers.depsgraph_update_post:
            row.operator(
                "anim.amp_deactivate_anim_offset",
                text="",
                depress=False,
                # emboss=False,
                icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_start_on"),
            )
        else:
            row.operator(
                "anim.amp_activate_anim_offset",
                text="",
                icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_start"),
                # emboss=False,
            )

        scene = context.scene
        if scene.amp_timeline_tools.anim_offset:
            anim_offset = scene.amp_timeline_tools.anim_offset
            mask_in_use = anim_offset.mask_in_use

        row.operator(
            "anim.amp_toggle_anim_offset_mask",
            text="",
            icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_mask"),
            depress=False,
            # emboss=False,
        )

    elif context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
        layout.label(text="", icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_start_on"))
        layout.label(text="", icon_value=utils.customIcons.get_icon_id("AMP_anim_offset_mask_on"))
