import bpy
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, IntProperty, FloatProperty, FloatVectorProperty, EnumProperty

class GPH_LightTableProps(PropertyGroup):
    """Properties for light table / reference frame"""

    enabled: BoolProperty(
        name="Show Reference",
        description="Show reference frame as light table",
        default=False,
        update=lambda self, context: update_light_table(self, context)
    )

    reference_frame: IntProperty(
        name="Reference Frame",
        description="Frame number to display as reference",
        default=1,
        min=1,
        update=lambda self, context: update_light_table(self, context)
    )

    opacity: FloatProperty(
        name="Opacity",
        description="Opacity of reference frame",
        default=0.3,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=lambda self, context: update_light_table(self, context)
    )

    tint_color: FloatVectorProperty(
        name="Tint Color",
        description="Color tint for reference frame",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 1.0),  # Light blue tint by default
        update=lambda self, context: update_light_table(self, context)
    )

    use_tint: BoolProperty(
        name="Use Tint",
        description="Apply color tint to reference frame",
        default=True,
        update=lambda self, context: update_light_table(self, context)
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
        default=False,
        update=lambda self, context: update_light_table(self, context)
    )

    is_updating_internal: BoolProperty(
        name="Internal Update Flag",
        description="Internal flag to prevent recursion",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

def update_light_table(self, context):
    """Update callback for light table properties"""
    # Only update if enabled and not already updating
    if not self.enabled:
        return

    # Prevent infinite recursion
    if self.is_updating_internal:
        return

    try:
        self.is_updating_internal = True

        # Directly update the reference object properties without recreating
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return

        ref_obj_name = obj.get("gph_light_table_ref")
        if not ref_obj_name or ref_obj_name not in bpy.data.objects:
            return

        ref_obj = bpy.data.objects[ref_obj_name]

        # Update properties directly
        ref_obj.color[3] = self.opacity
        ref_obj.show_in_front = self.show_in_front

        # Update modifiers
        for mod in ref_obj.modifiers:
            if mod.type == 'GREASE_PENCIL_TIME' and mod.name == "Light Table Lock":
                mod.frame_start = self.reference_frame

            if mod.type == 'GREASE_PENCIL_TINT' and mod.name == "Light Table Tint":
                if self.use_tint:
                    mod.color = self.tint_color
                    mod.show_viewport = True
                else:
                    mod.show_viewport = False

        # Force viewport redraw
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    finally:
        self.is_updating_internal = False
