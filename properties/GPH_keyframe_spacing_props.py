import bpy
from bpy.types import PropertyGroup
from bpy.props import IntProperty, BoolProperty

class GPH_KeyframeSpacingProps(PropertyGroup):
    spacing_frames: IntProperty(
        name="Frame Interval",
        description="Frame interval between keyframes (e.g., 10 = frames at 0, 10, 20, 30...)",
        default=10,
        min=1,
        max=100
    )
    
    ripple_edit: BoolProperty(
        name="Ripple Edit",
        description="Move subsequent keyframes proportionally to preserve all frames",
        default=True
    )