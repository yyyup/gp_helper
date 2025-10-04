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


class GPH_OT_layer_move_up(Operator):
    """Move layer up in the stack"""
    bl_idname = "gph.layer_move_up"
    bl_label = "Move Layer Up"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        gp_data = obj.data
        active_layer = gp_data.layers.active
        props = context.scene.gph_layer_manager_props
        
        if not active_layer:
            self.report({'WARNING'}, "No active layer")
            return {'CANCELLED'}
        
        print("\n=== MOVE UP DEBUG ===")
        print(f"Active layer: {active_layer.name}")
        print(f"UI list active_layer_index: {props.active_layer_index}")
        
        # Show storage order
        print("\nStorage order (internal):")
        for i, layer in enumerate(gp_data.layers):
            marker = " <-- ACTIVE" if layer == active_layer else ""
            print(f"  [{i}] {layer.name}{marker}")
        
        # Show display order (reversed)
        print("\nDisplay order (what user sees):")
        reversed_layers = list(reversed(gp_data.layers))
        for i, layer in enumerate(reversed_layers):
            marker = " <-- ACTIVE" if layer == active_layer else ""
            print(f"  [{i}] {layer.name}{marker}")
        
        # Find current storage index
        storage_index = -1
        for i, layer in enumerate(gp_data.layers):
            if layer == active_layer:
                storage_index = i
                break
        
        print(f"\nStorage index: {storage_index}")
        print(f"Display index (reversed): {len(gp_data.layers) - 1 - storage_index}")
        
        try:
            # Moving UP in display means moving towards index 0 in display
            # Since display is reversed, that means moving towards higher index in storage
            gp_data.layers.move(active_layer, 'UP')
            print(f"Called: gp_data.layers.move(active_layer, 'UP')")
            
            # Show result
            print("\nAfter move - Storage order:")
            new_storage_index = -1
            for i, layer in enumerate(gp_data.layers):
                marker = " <-- ACTIVE" if layer == active_layer else ""
                if layer == active_layer:
                    new_storage_index = i
                print(f"  [{i}] {layer.name}{marker}")
            
            # Calculate new display index
            new_display_index = len(gp_data.layers) - 1 - new_storage_index
            print(f"\nNew storage index: {new_storage_index}")
            print(f"New display index: {new_display_index}")
            print(f"Should update UI list to index: {new_display_index}")
            
            # Update UI selection
            props.active_layer_index = new_display_index
            
            self.report({'INFO'}, f"Moved layer '{active_layer.name}' up")
            print("=== END DEBUG ===\n")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to move layer: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class GPH_OT_layer_move_up(Operator):
    """Move layer up in the stack"""
    bl_idname = "gph.layer_move_up"
    bl_label = "Move Layer Up"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        gp_data = obj.data
        active_layer = gp_data.layers.active
        props = context.scene.gph_layer_manager_props
        
        if not active_layer:
            self.report({'WARNING'}, "No active layer")
            return {'CANCELLED'}
        
        print(f"\n=== UP PRESSED - Layer: {active_layer.name} ===")
        print(f"UI active_layer_index: {props.active_layer_index}")
        
        # Show what user sees
        print("Display order:")
        for i, layer in enumerate(reversed(list(gp_data.layers))):
            marker = " <-- SELECTED" if layer == active_layer else ""
            print(f"  [{i}] {layer.name}{marker}")
        
        # Find current storage index
        storage_index = -1
        for i, layer in enumerate(gp_data.layers):
            if layer == active_layer:
                storage_index = i
                break
        
        display_index = len(gp_data.layers) - 1 - storage_index
        print(f"Storage index: {storage_index}, Display index: {display_index}")
        print(f"Total layers: {len(gp_data.layers)}")
        print(f"Check: storage_index ({storage_index}) >= len-1 ({len(gp_data.layers)-1})? {storage_index >= len(gp_data.layers) - 1}")
        
        # Check if already at top of display (highest storage index)
        if storage_index >= len(gp_data.layers) - 1:
            print("BLOCKED: Already at top")
            self.report({'INFO'}, "Layer is already at the top")
            return {'CANCELLED'}
        
        print(f"Calling: gp_data.layers.move({active_layer.name}, 'UP')")
        
        try:
            gp_data.layers.move(active_layer, 'UP')
            new_storage_index = storage_index + 1
            new_display_index = len(gp_data.layers) - 1 - new_storage_index
            props.active_layer_index = new_display_index
            
            print(f"New storage: {new_storage_index}, New display: {new_display_index}")
            self.report({'INFO'}, f"Moved layer '{active_layer.name}' up")
            
        except Exception as e:
            print(f"ERROR: {e}")
            self.report({'ERROR'}, f"Failed to move layer: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class GPH_OT_layer_move_up(Operator):
    """Move layer up in the stack"""
    bl_idname = "gph.layer_move_up"
    bl_label = "Move Layer Up"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        gp_data = obj.data
        if not gp_data.layers.active:
            self.report({'WARNING'}, "No active layer")
            return {'CANCELLED'}
        
        try:
            # Use Blender's native layer_move operator
            bpy.ops.grease_pencil.layer_move(direction='UP')
            self.report({'INFO'}, "Moved layer up")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to move layer: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class GPH_OT_layer_move_down(Operator):
    """Move layer down in the stack"""
    bl_idname = "gph.layer_move_down"
    bl_label = "Move Layer Down"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        gp_data = obj.data
        if not gp_data.layers.active:
            self.report({'WARNING'}, "No active layer")
            return {'CANCELLED'}
        
        try:
            # Use Blender's native layer_move operator
            bpy.ops.grease_pencil.layer_move(direction='DOWN')
            self.report({'INFO'}, "Moved layer down")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to move layer: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class GPH_OT_layer_add(Operator):
    """Add new layer"""
    bl_idname = "gph.layer_add"
    bl_label = "Add Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        try:
            bpy.ops.grease_pencil.layer_add()
            self.report({'INFO'}, "Added new layer")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add layer: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class GPH_OT_layer_remove(Operator):
    """Remove active layer"""
    bl_idname = "gph.layer_remove"
    bl_label = "Remove Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return {'CANCELLED'}
        
        gp_data = obj.data
        active_layer = gp_data.layers.active
        
        if not active_layer:
            self.report({'WARNING'}, "No active layer to remove")
            return {'CANCELLED'}
        
        try:
            bpy.ops.grease_pencil.layer_remove()
            self.report({'INFO'}, "Removed layer")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to remove layer: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}