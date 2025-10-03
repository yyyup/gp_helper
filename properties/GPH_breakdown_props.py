import bpy
from bpy.types import PropertyGroup
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty

class GPH_BreakdownProps(PropertyGroup):
    """Properties for breakdown frame creation"""

    position: FloatProperty(
        name="Position",
        description="Position of breakdown between selected frames (0.0 = first frame, 1.0 = last frame)",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )

    copy_mode: EnumProperty(
        name="Copy Mode",
        description="How to create the breakdown frame",
        items=[
            ('FIRST', "Copy First", "Duplicate the first keyframe (traditional approach)"),
            ('LAST', "Copy Last", "Duplicate the last keyframe"),
            ('BLANK', "Blank Frame", "Create an empty frame for drawing from scratch"),
            ('INTERPOLATE', "Interpolate", "Attempt to interpolate between frames (experimental)")
        ],
        default='FIRST'
    )

    shift_subsequent: BoolProperty(
        name="Shift Subsequent Frames",
        description="Move frames after the breakdown forward by 1 to make room",
        default=False
    )

    apply_to_all_layers: BoolProperty(
        name="All Layers",
        description="Create breakdown on all layers (ignores layer settings)",
        default=False
    )

    custom_offset: IntProperty(
        name="Frame Offset",
        description="Custom frame offset from first keyframe (overrides position slider)",
        default=0,
        min=0,
        max=1000
    )

    use_custom_offset: BoolProperty(
        name="Use Custom Offset",
        description="Use frame offset instead of position slider",
        default=False
    )
