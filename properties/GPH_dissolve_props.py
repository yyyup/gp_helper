import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, IntProperty

class GPH_dissolve_properties(PropertyGroup):
    layer1_name: StringProperty(
        name="Dissolve Layer",
        description="Layer that fades out during dissolve effect",
        default="GP_Layer"
    )

    layer2_name: StringProperty(
        name="Base Layer",
        description="Layer that fades in during dissolve effect",
        default="GP_Layer.001"
    )

    total_frames: IntProperty(
        name="Total Frames",
        description="Total number of frames in timeline",
        default=90,
        min=1,
        max=10000
    )

    cycle_length: IntProperty(
        name="Cycle Length",
        description="Length of each dissolve cycle in frames",
        default=10,
        min=1,
        max=100
    )