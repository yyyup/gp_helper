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


class GPH_OT_layer_duplicate(Operator):
    """Duplicate layer with all keyframes"""
    bl_idname = "gph.layer_duplicate"
    bl_label = "Duplicate Layer"
    bl_description = "Duplicate this layer including all keyframes and drawings"
    bl_options = {'REGISTER', 'UNDO'}
    
    layer_name: bpy.props.StringProperty()
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            self.report({'ERROR'}, "No Grease Pencil object active")
            return {'CANCELLED'}
        
        gp_data = obj.data
        
        # Find the source layer
        source_layer = None
        for layer in gp_data.layers:
            if layer.name == self.layer_name:
                source_layer = layer
                break
        
        if not source_layer:
            self.report({'ERROR'}, f"Layer '{self.layer_name}' not found")
            return {'CANCELLED'}
        
        # Make source layer active (required for duplication)
        gp_data.layers.active = source_layer
        
        try:
            # Use Blender's built-in duplicate operator
            bpy.ops.grease_pencil.layer_duplicate()
            
            # The new layer is now active
            new_layer = gp_data.layers.active
            
            self.report({'INFO'}, f"Duplicated layer '{self.layer_name}' as '{new_layer.name}'")
            
            # Force UI refresh
            for area in context.screen.areas:
                area.tag_redraw()
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to duplicate layer: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class GPH_OT_layer_make_active(Operator):
    """Make this layer active"""
    bl_idname = "gph.layer_make_active"
    bl_label = "Activate Layer"
    bl_description = "Click to make active"
    bl_options = {'REGISTER', 'UNDO'}
    
    layer_name: bpy.props.StringProperty()
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        gp_data = obj.data
        
        # Find and activate the layer
        for layer in gp_data.layers:
            if layer.name == self.layer_name:
                gp_data.layers.active = layer
                
                # Force UI refresh
                for area in context.screen.areas:
                    area.tag_redraw()
                
                return {'FINISHED'}
        
        return {'CANCELLED'}


