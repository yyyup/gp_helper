import bpy
from bpy.types import Operator

class GPH_OT_layer_solo(Operator):
    """Solo this layer (lock all others)"""
    bl_idname = "gph.layer_solo"
    bl_label = "Solo Layer"
    bl_description = "Lock all other layers, or unsolo to unlock all"
    bl_options = {'REGISTER', 'UNDO'}
    
    layer_name: bpy.props.StringProperty()
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            self.report({'ERROR'}, "No Grease Pencil object active")
            return {'CANCELLED'}
        
        gp_data = obj.data
        
        # Find the target layer
        target_layer = None
        for layer in gp_data.layers:
            if layer.name == self.layer_name:
                target_layer = layer
                break
        
        if not target_layer:
            self.report({'ERROR'}, f"Layer '{self.layer_name}' not found")
            return {'CANCELLED'}
        
        # Check if currently soloed
        is_soloed = self.is_layer_soloed(gp_data, target_layer)
        
        if is_soloed:
            # Unsolo: unlock all layers
            for layer in gp_data.layers:
                layer.lock = False
            self.report({'INFO'}, "Unsoloed all layers")
        else:
            # Solo: lock all except target
            for layer in gp_data.layers:
                if layer == target_layer:
                    layer.lock = False
                else:
                    layer.lock = True
            self.report({'INFO'}, f"Soloed layer '{self.layer_name}'")
        
        # Force UI refresh
        for area in context.screen.areas:
            area.tag_redraw()
        
        return {'FINISHED'}
    
    def is_layer_soloed(self, gp_data, layer):
        """Check if this layer is currently soloed"""
        if layer.lock:
            return False
        
        other_layers_locked = all(
            other.lock for other in gp_data.layers if other != layer
        )
        
        return other_layers_locked