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

        # Get active GP object
        obj = context.active_object if context.active_object else context.object

        if not obj or obj.type not in ('GPENCIL', 'GREASEPENCIL'):
            layout.label(text="No Grease Pencil object active", icon='ERROR')
            return

        gp_data = obj.data
        
        # Check if layers exist
        if not gp_data.layers:
            layout.label(text="No layers found", icon='ERROR')
            return
            
        layer = gp_data.layers.active

        if not layer:
            layout.label(text="No active layer", icon='ERROR')
            return

        # Main onion skin overlay toggle
        # Try to get overlay from different contexts
        overlay = None
        
        # First try from space_data (Dope Sheet)
        if hasattr(context.space_data, 'overlay'):
            overlay = context.space_data.overlay
        # Also try from all 3D viewports in case user wants to control it from here
        elif hasattr(context, 'screen'):
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    overlay = area.spaces.active.overlay
                    break
        
        if overlay and hasattr(overlay, 'use_gpencil_onion_skin'):
            icon = 'ONIONSKIN_ON' if overlay.use_gpencil_onion_skin else 'ONIONSKIN_OFF'
            layout.prop(overlay, "use_gpencil_onion_skin", text="Show Onion Skin", toggle=True, icon=icon)
        else:
            # Fallback: show a note if overlay can't be found
            box = layout.box()
            box.label(text="Onion Skin toggle in 3D View Overlay", icon='INFO')

        # Layer info and per-layer toggle
        box = layout.box()
        box.label(text=f"Active Layer: {layer.name}", icon='OUTLINER_DATA_GP_LAYER')
        
        # Per-layer toggle
        if hasattr(layer, "use_onion_skinning"):
            box.prop(layer, "use_onion_skinning", text="Enable for This Layer", toggle=True)

        # Frame range settings
        box = layout.box()
        box.label(text="Frame Range:", icon='SORTTIME')
        col = box.column(align=True)
        col.prop(gp_data, "ghost_before_range", text="Before")
        col.prop(gp_data, "ghost_after_range", text="After")

        # Display settings
        box = layout.box()
        box.label(text="Display:", icon='HIDE_OFF')
        col = box.column(align=True)
        col.prop(gp_data, "onion_factor", text="Opacity", slider=True)
        
        if hasattr(gp_data, "use_onion_fade"):
            col.prop(gp_data, "use_onion_fade", text="Fade")
        
        if hasattr(gp_data, "use_onion_loop"):
            col.prop(gp_data, "use_onion_loop", text="Loop")

        # Custom colors - compact with shield toggle
        box = layout.box()
        
        # Header row with label and shield toggle
        row = box.row(align=True)
        row.label(text="Custom Colors:", icon='COLOR')
        # Shield toggle on the same row - matches the blue icon from properties panel
        shield_icon = 'LOCKED' if gp_data.use_fake_user else 'UNLOCKED'
        row.prop(gp_data, "use_fake_user", text="", icon=shield_icon, emboss=True)
        
        # Try different possible property names for custom color toggle
        custom_color_prop = None
        for prop_name in ["onion_use_custom_color", "use_ghost_custom_colors", "use_onion_custom_colors"]:
            if hasattr(gp_data, prop_name):
                custom_color_prop = prop_name
                break
        
        if custom_color_prop:
            box.prop(gp_data, custom_color_prop, text="Use Custom Colors")
            
            if getattr(gp_data, custom_color_prop):
                # These property names are confirmed from API docs
                if hasattr(gp_data, "before_color"):
                    box.prop(gp_data, "before_color", text="Before")
                if hasattr(gp_data, "after_color"):
                    box.prop(gp_data, "after_color", text="After")