import bpy
from bpy.types import PropertyGroup
from bpy.props import EnumProperty, FloatProperty, IntProperty, BoolProperty

class GPH_marker_spacing_properties(PropertyGroup):
    spacing_method: EnumProperty(
        name="Spacing Method",
        description="How to calculate the spacing to add at each marker",
        items=[
            ('MULTIPLIER', "Multiplier", "Multiply existing spacing by a factor"),
            ('FIXED', "Fixed Amount", "Add a fixed number of frames"),
        ],
        default='MULTIPLIER'
    )

    spacing_multiplier: FloatProperty(
        name="Multiplier",
        description="Factor to multiply existing spacing (2.0 = double spacing)",
        default=2.0,
        min=1.1,
        max=10.0,
        step=0.1,
        precision=1
    )

    fixed_spacing: IntProperty(
        name="Fixed Frames",
        description="Number of frames to add at each marker",
        default=20,
        min=1,
        max=500
    )

    target_selected_only: BoolProperty(
        name="Selected GP Objects Only",
        description="Only affect keyframes from selected Grease Pencil objects",
        default=True
    )


    auto_detect_spacing: BoolProperty(
        name="Auto-Detect Spacing",
        description="Automatically detect existing spacing pattern around markers",
        default=True
    )

    auto_cleanup_markers: BoolProperty(
        name="Auto-Cleanup GP Spacing Markers",
        description="Automatically remove GP spacing markers after applying",
        default=True
    )