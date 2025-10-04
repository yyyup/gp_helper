import bpy
from bpy.types import Panel, UIList

class GPH_UL_layer_list(UIList):
    """Custom UIList for GP layers that mimics native behavior"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layer = item
        gp_data = data
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Solo button
            is_soloed = self.is_layer_soloed(gp_data, layer)
            solo_icon = 'SOLO_ON' if is_soloed else 'SOLO_OFF'
            op = row.operator("gph.layer_solo", text="", icon=solo_icon, emboss=True)
            op.layer_name = layer.name
            
            # Duplicate button
            op = row.operator("gph.layer_duplicate", text="", icon='DUPLICATE', emboss=True)
            op.layer_name = layer.name
            
            # Layer icon
            row.label(text="", icon='OUTLINER_DATA_GP_LAYER')
            
            # Layer name (editable)
            row.prop(layer, "name", text="", emboss=False)
            
            # Right side controls
            row.separator()
            
            # Visibility
            hide_icon = 'HIDE_OFF' if not layer.hide else 'HIDE_ON'
            row.prop(layer, "hide", text="", icon=hide_icon, emboss=False)
            
            # Onion skinning
            if hasattr(layer, "use_onion_skinning"):
                row.prop(layer, "use_onion_skinning", text="", icon='ONIONSKIN_ON', emboss=False)
            
            # Lock
            lock_icon = 'UNLOCKED' if not layer.lock else 'LOCKED'
            row.prop(layer, "lock", text="", icon=lock_icon, emboss=False)
        
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='OUTLINER_DATA_GP_LAYER')
    
    def filter_items(self, context, data, propname):
        """Reverse order to match dope sheet and native layer panel"""
        layers = getattr(data, propname)
        
        # Create filter flags (all visible)
        flt_flags = [self.bitflag_filter_item] * len(layers)
        
        # Reverse the order to match dope sheet display
        flt_neworder = list(reversed(range(len(layers))))
        
        return flt_flags, flt_neworder
    
    def is_layer_soloed(self, gp_data, layer):
        """Check if this layer is currently soloed"""
        if layer.lock:
            return False
        
        other_layers = [l for l in gp_data.layers if l != layer]
        if not other_layers:
            return False
        
        return all(other.lock for other in other_layers)


class GPH_PT_layer_manager_panel(Panel):
    """Enhanced layer manager with quick access buttons"""
    bl_label = "Layer Manager"
    bl_idname = "GPH_PT_layer_manager_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 10

    def draw(self, context):
        layout = self.layout
        
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            layout.label(text="No Grease Pencil object active", icon='ERROR')
            return
        
        gp_data = obj.data
        
        if not gp_data.layers:
            layout.label(text="No layers found", icon='INFO')
            return
        
        props = context.scene.gph_layer_manager_props
        
        row = layout.row()
        
        row.template_list(
            "GPH_UL_layer_list",
            "",
            gp_data,
            "layers",
            props,
            "active_layer_index",
            rows=6
        )
        
        # Sidebar with reorder buttons
        col = row.column(align=True)
        col.operator("gph.layer_move_up", text="", icon='TRIA_UP')
        col.operator("gph.layer_move_down", text="", icon='TRIA_DOWN')
        col.separator()
        col.operator("gph.layer_add", text="", icon='ADD')
        col.operator("gph.layer_remove", text="", icon='REMOVE')