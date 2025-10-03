import bpy
from bpy.types import PropertyGroup
from bpy.props import IntProperty, CollectionProperty, StringProperty, BoolProperty

class GPH_LayerKeyframeSettings(PropertyGroup):
    layer_name: StringProperty(
        name="Layer Name",
        description="Name of the Grease Pencil layer"
    )
    is_enabled: BoolProperty(
        name="Enabled",
        description="Whether this layer is affected by individual operations",
        default=True
    )

class GPH_KeyframeProperties(PropertyGroup):
    frame_offset: IntProperty(
        name="Frame Offset",
        description="Number of frames to move keyframes by (master control)",
        default=1,
        min=1,
        max=100
    )

    layer_settings: CollectionProperty(
        type=GPH_LayerKeyframeSettings,
        name="Layer Settings"
    )

    show_layer_controls: BoolProperty(
        name="Show Layer Controls",
        description="Show individual layer controls",
        default=False
    )

# Registration is handled by the main properties __init__.py