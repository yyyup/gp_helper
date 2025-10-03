import bpy
from bpy.types import Panel


class GPH_PT_onion_skin_panel(Panel):
    """Panel for onion skinning controls"""
    bl_label = "Onion Skinning"
    bl_idname = "GPH_PT_onion_skin_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 3

    def draw(self, context):
        layout = self.layout

        # Active layer check - try both context.object and context.active_object
        obj = context.active_object if context.active_object else context.object

        if not obj or obj.type not in ('GPENCIL', 'GREASEPENCIL'):
            layout.label(text="No Grease Pencil object active", icon='ERROR')
            return

        gp_data = obj.data
        layer = gp_data.layers.active

        if not layer:
            layout.label(text="No active layer", icon='ERROR')
            return

        # Layer info
        box = layout.box()
        box.label(text=f"Active Layer: {layer.name}", icon='OUTLINER_DATA_GP_LAYER')

        layout.separator()

        # Per-layer toggle
        layout.prop(layer, "use_onion_skinning", text="Enable for This Layer", toggle=True)

        layout.separator()

        # Object-level onion skin settings
        box = layout.box()
        box.label(text="Onion Skin Settings:", icon='ONIONSKIN')
        box.prop(gp_data, "onion_mode", text="Mode")
        box.prop(gp_data, "onion_keyframe_type", text="Keyframe Type")

        layout.separator()

        box = layout.box()
        box.label(text="Frame Range:", icon='SORTTIME')
        box.prop(gp_data, "ghost_before_range", text="Keyframes Before")
        box.prop(gp_data, "ghost_after_range", text="Keyframes After")

        layout.separator()

        box = layout.box()
        box.label(text="Display:", icon='HIDE_OFF')
        box.prop(gp_data, "onion_factor", text="Opacity", slider=True)
        box.prop(gp_data, "use_onion_fade", text="Fade")
        box.prop(gp_data, "use_onion_loop", text="Loop")
