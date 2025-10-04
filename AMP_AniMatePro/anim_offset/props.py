# licence
"""
Copyright (C) 2018 Ares Deveaux


Created by Ares Deveaux

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import bpy
from . import support
from .. import utils
from bpy.props import BoolProperty, EnumProperty, IntProperty
from bpy.types import PropertyGroup
from .support import update_blend_range, update_mask_range


def interpolation_update(self, context):
    blends_action = bpy.data.actions.get("amp_action")
    blends_curves = list(utils.curve.all_fcurves(blends_action)) if blends_action else None
    if blends_curves:
        keys = blends_curves[0].keyframe_points
        support.mask_interpolation(keys, context)


class AMP_AnimOffset(PropertyGroup):

    user_preview_start: IntProperty()

    user_preview_end: IntProperty()

    user_preview_use: BoolProperty()

    user_scene_start: IntProperty()

    user_scene_end: IntProperty()

    user_scene_auto: BoolProperty()

    blends: BoolProperty(default=False)

    # end_on_release: BoolProperty(default=False)

    mask_in_use: BoolProperty(default=False)

    quick_anim_offset_in_use: BoolProperty(default=False)

    reference_frame: IntProperty(
        name="Reference Frame",
        description="Reference frame for the AnimOffset",
        default=0,
    )

    fast_mask: BoolProperty(default=False)

    insert_outside_keys: BoolProperty(default=False)

    interp: EnumProperty(
        items=[
            ("LINEAR", " ", "Linear transition", "IPO_LINEAR", 1),
            ("SINE", " ", "Curve slope 1", "IPO_SINE", 2),
            ("CUBIC", " ", "Curve slope 3", "IPO_CUBIC", 3),
            ("QUART", " ", "Curve Slope 4", "IPO_QUART", 4),
            ("QUINT", " ", "Curve Slope 5", "IPO_QUINT", 5),
        ],
        name="Mask Blend Interpolation",
        default="SINE",
        update=interpolation_update,
    )

    easing: EnumProperty(
        items=[
            ("EASE_IN", "Ease in", "Sets Mask transition type", "IPO_EASE_IN", 1),
            (
                "EASE_IN_OUT",
                "Ease in-out",
                "Sets Mask transition type",
                "IPO_EASE_IN_OUT",
                2,
            ),
            ("EASE_OUT", "Ease-out", "Sets Mask transition type", "IPO_EASE_OUT", 3),
        ],
        name="Mask Blend Easing",
        default="EASE_IN_OUT",
        update=interpolation_update,
    )

    ao_mask_range: IntProperty(
        name="Mask Range",
        description="Mask range in frames for the AnimOffset",
        default=0,
        min=0,
        update=update_mask_range,
    )

    ao_blend_range: IntProperty(
        name="Blend Range",
        description="Blend range in frames for the AnimOffset outside of the mask",
        default=0,
        min=0,
        update=update_blend_range,
    )


classes = (AMP_AnimOffset,)
