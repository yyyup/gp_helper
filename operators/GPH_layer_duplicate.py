import bpy
from bpy.types import Operator

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