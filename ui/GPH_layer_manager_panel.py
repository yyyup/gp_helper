import bpy
from bpy.types import Panel

class GPH_PT_layer_manager_panel(Panel):
    """Layer manager with solo and duplicate buttons"""
    bl_label = "Layer Manager"
    bl_idname = "GPH_PT_layer_manager_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 10

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'GREASEPENCIL'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        gpd = obj.data

        # Use Blender's native GP v3 layer tree (like Storytools does)
        row = layout.row()
        row.template_grease_pencil_layer_tree()

        col = row.column()
        sub = col.column(align=True)
        sub.operator("grease_pencil.layer_add", icon='ADD', text="")
        sub.operator("grease_pencil.layer_remove", icon='REMOVE', text="")

        col.separator()
        sub = col.column(align=True)
        sub.operator("grease_pencil.layer_move", icon='TRIA_UP', text="").direction = 'UP'
        sub.operator("grease_pencil.layer_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

        # Add solo and duplicate buttons for active layer
        active_layer = gpd.layers.active
        if active_layer:
            layout.separator()
            box = layout.box()
            box.label(text="Quick Actions:")
            row = box.row(align=True)

            # Solo button
            is_soloed = self.is_layer_soloed(gpd, active_layer)
            solo_icon = 'SOLO_ON' if is_soloed else 'SOLO_OFF'
            solo_text = "Unsolo" if is_soloed else "Solo"
            op = row.operator("gph.layer_solo", text=solo_text, icon=solo_icon)
            op.layer_name = active_layer.name

            # Duplicate button
            op = row.operator("gph.layer_duplicate", text="Duplicate", icon='DUPLICATE')
            op.layer_name = active_layer.name

    def is_layer_soloed(self, gp_data, layer):
        """Check if this layer is currently soloed"""
        if layer.lock:
            return False

        other_layers = [l for l in gp_data.layers if l != layer]
        if not other_layers:
            return False

        return all(other.lock for other in other_layers)