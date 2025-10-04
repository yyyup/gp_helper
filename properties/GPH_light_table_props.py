import bpy
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, IntProperty, FloatProperty, FloatVectorProperty, EnumProperty

class GPH_LightTableProps(PropertyGroup):
    """Properties for light table / reference frame"""

    enabled: BoolProperty(
        name="Show Reference",
        description="Show reference frame as light table",
        default=False
    )

    reference_frame: IntProperty(
        name="Reference Frame",
        description="Frame number to display as reference",
        default=1,
        min=1
    )

    opacity: FloatProperty(
        name="Opacity",
        description="Opacity of reference frame",
        default=0.3,
        min=0.0,
        max=1.0,
        subtype='FACTOR'
    )

    tint_color: FloatVectorProperty(
        name="Tint Color",
        description="Color tint for reference frame",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 1.0)  # Light blue tint by default
    )

    use_tint: BoolProperty(
        name="Use Tint",
        description="Apply color tint to reference frame",
        default=True
    )

    lock_to_current: BoolProperty(
        name="Lock to Current",
        description="Always use current frame as reference (updates when you change frames)",
        default=False
    )

    reference_mode: EnumProperty(
        name="Reference Mode",
        description="How to display the reference",
        items=[
            ('DUPLICATE', "Duplicate Object", "Create duplicate GP object (recommended)"),
            ('OVERLAY', "Viewport Overlay", "Draw in viewport (experimental)")
        ],
        default='DUPLICATE'
    )

    show_in_front: BoolProperty(
        name="Show in Front",
        description="Display reference in front of current drawing",
        default=False
    )
