import bpy
from bpy.types import PropertyGroup
from bpy.props import IntProperty, BoolProperty, EnumProperty

class GPH_FlipFlopProps(PropertyGroup):
    """Properties for flip/flop tool"""

    stored_frame: IntProperty(
        name="Stored Frame",
        description="Frame to flip to when toggling",
        default=1,
        min=1
    )

    is_flopped: BoolProperty(
        name="Currently Flopped",
        description="True when showing the alternate frame",
        default=False
    )

    original_frame: IntProperty(
        name="Original Frame",
        description="Frame we flipped from",
        default=1,
        min=1
    )

    flip_mode: EnumProperty(
        name="Flip Mode",
        description="How to determine flip target",
        items=[
            ('STORED', "Stored Frame", "Flip to manually set frame"),
            ('PREVIOUS', "Previous Frame", "Always flip to frame - 1"),
            ('NEXT', "Next Frame", "Always flip to frame + 1"),
            ('PREVIOUS_KEY', "Previous Key", "Flip to previous keyframe"),
            ('NEXT_KEY', "Next Key", "Flip to next keyframe")
        ],
        default='PREVIOUS'
    )

    auto_update_stored: BoolProperty(
        name="Auto-Update Stored",
        description="Automatically update stored frame to current frame when setting",
        default=True
    )
