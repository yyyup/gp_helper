"""
GP Helper - Dope Sheet Header UI
Adds tools to the Dope Sheet top bar
"""

import bpy
from bpy.types import Header, Menu
from ..utils import get_icon


def draw_gp_helper_header(self, context):
    """Draw GP Helper tools in Dope Sheet header"""
    layout = self.layout
    
    # Only show for Grease Pencil objects
    obj = context.active_object
    if not obj or obj.type != 'GREASEPENCIL':
        return
    
    layout.separator()
    
    # === FLIP/FLOP - Most frequently used ===
    props = context.scene.gph_flip_flop_props
    row = layout.row(align=True)
    
    # Get custom flip/flop icon
    flip_flop_custom_icon = get_icon("gph_flip_flop")
    
    # Main flip/flop button - use custom icon if available
    if flip_flop_custom_icon and flip_flop_custom_icon > 0:
        row.operator("gph.flip_flop_toggle", text="", icon_value=flip_flop_custom_icon, depress=props.is_flopped)
    else:
        # Fallback to default Blender icons
        flip_icon = 'LOOP_BACK' if props.is_flopped else 'LOOP_FORWARDS'
        row.operator("gph.flip_flop_toggle", text="", icon=flip_icon, depress=props.is_flopped)
    
    # Stored frame input (compact)
    sub = row.row(align=True)
    sub.scale_x = 0.6
    sub.prop(props, "stored_frame", text="")
    
    # Set button
    row.operator("gph.set_flip_frame", text="", icon='EYEDROPPER')
    
    layout.separator()
    
    # === LIGHT TABLE ===
    lt_props = context.scene.gph_light_table_props
    row = layout.row(align=True)
    
    # Get custom light table icon
    light_table_custom_icon = get_icon("gph_light_table")
    
    # Toggle button with visual feedback
    if light_table_custom_icon and light_table_custom_icon > 0:
        # Use custom icon
        if lt_props.enabled:
            row.alert = True
        row.operator("gph.toggle_light_table", text="", icon_value=light_table_custom_icon, depress=lt_props.enabled)
    else:
        # Fallback to default icons
        if lt_props.enabled:
            row.alert = True
            icon = 'OUTLINER_OB_LIGHT'
            text = "LT"
        else:
            icon = 'LIGHT'
            text = "LT"
        row.operator("gph.toggle_light_table", text=text, icon=icon, depress=lt_props.enabled)
    
    # Reference frame (compact)
    sub = row.row(align=True)
    sub.scale_x = 0.6
    sub.prop(lt_props, "reference_frame", text="")
    
    # Eyedropper to set reference
    row.operator("gph.set_reference_frame", text="", icon='EYEDROPPER')
    
    layout.separator()
    
    # === KEYFRAME MOVER ===
    kf_props = context.scene.gph_keyframe_props
    row = layout.row(align=True)
    
    # Move backward/forward buttons with custom icons
    backward_icon = get_icon("gph_move_backward")
    forward_icon = get_icon("gph_move_forward")
    
    if backward_icon and backward_icon > 0:
        row.operator("gph.keyframe_mover_backward", text="", icon_value=backward_icon)
    else:
        row.operator("gph.keyframe_mover_backward", text="", icon='BACK')
    
    if forward_icon and forward_icon > 0:
        row.operator("gph.keyframe_mover_forward", text="", icon_value=forward_icon)
    else:
        row.operator("gph.keyframe_mover_forward", text="", icon='FORWARD')
    
    # Frame offset input (compact)
    sub = row.row(align=True)
    sub.scale_x = 0.5
    sub.prop(kf_props, "frame_offset", text="")
    
    layout.separator()
    
    # === KEYFRAME SPACING ===
    spacing_props = context.scene.gph_keyframe_spacing_props
    row = layout.row(align=True)
    
    # Custom icon for spacing if available
    spacing_icon = get_icon("gph_keyframe_spacing")
    
    if spacing_icon and spacing_icon > 0:
        row.label(text="", icon_value=spacing_icon)
    else:
        row.label(text="", icon='KEYFRAME_HLT')
    
    # Spacing value input
    sub = row.row(align=True)
    sub.scale_x = 0.6
    sub.prop(spacing_props, "spacing_frames", text="")
    
    # Apply button
    op = row.operator("gph.keyframe_spacing", text="Space", icon='KEYFRAME')
    op.spacing_frames = spacing_props.spacing_frames
    op.ripple_edit = spacing_props.ripple_edit
    
    layout.separator()

    # === MORE TOOLS MENU ===
    layout.menu("DOPESHEET_MT_gp_helper_tools", text="", icon='DOWNARROW_HLT')


class DOPESHEET_MT_gp_helper_tools(Menu):
    """Additional GP Helper tools dropdown menu"""
    bl_label = "GP Helper Tools"

    def draw(self, context):
        layout = self.layout
        
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            layout.label(text="No GP object active", icon='ERROR')
            return
        
        # === BREAKDOWN HELPER ===
        layout.label(text="Breakdown Helper", icon='KEYFRAME_HLT')
        
        row = layout.row(align=True)
        row.operator("gph.breakdown_favor_first", text="Favor First (25%)")
        row = layout.row(align=True)
        row.operator("gph.breakdown_middle", text="Middle (50%)")
        row = layout.row(align=True)
        row.operator("gph.breakdown_favor_last", text="Favor Last (75%)")
        
        layout.separator()
        
        # === KEYFRAME LAYER CONTROLS ===
        layout.label(text="Layer Controls", icon='OUTLINER_DATA_GP_LAYER')
        layout.operator("gph.refresh_layers", text="Refresh Layers", icon='FILE_REFRESH')
        
        layout.separator()
        
        # === ONION SKIN QUICK ACCESS ===
        layout.label(text="Onion Skin", icon='ONIONSKIN_ON')
        
        gp_data = obj.data
        
        # Try to get overlay from context
        overlay = None
        if hasattr(context.space_data, 'overlay'):
            overlay = context.space_data.overlay
        
        if overlay and hasattr(overlay, 'use_gpencil_onion_skin'):
            layout.prop(overlay, "use_gpencil_onion_skin", text="Show Onion Skin")
        
        layout.prop(gp_data, "ghost_before_range", text="Before")
        layout.prop(gp_data, "ghost_after_range", text="After")
        layout.prop(gp_data, "onion_factor", text="Opacity", slider=True)
        
        layout.separator()
        
        # === MARKER SPACING ===
        layout.label(text="Marker Spacing", icon='MARKER_HLT')
        layout.operator("gph.add_gp_marker", text="Add Marker at Current", icon='ADD')
        layout.operator("gph.marker_spacing", text="Apply Marker Spacing", icon='KEYFRAME_HLT')
        layout.operator("gph.clear_markers", text="Clear GP Markers", icon='X')
        
        layout.separator()
        
        # === PANEL LINK ===
        layout.operator("screen.region_toggle", text="Toggle Sidebar (N)", icon='MENU_PANEL').region_type = 'UI'


# Registration is handled in ui/__init__.py
classes = (
    DOPESHEET_MT_gp_helper_tools,
)