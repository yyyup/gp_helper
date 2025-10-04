"""
GP Helper - Dope Sheet Header UI
Add this file as: ui/GPH_header.py
"""

import bpy
from bpy.types import Header, Menu

class DOPESHEET_HT_gp_helper(Header):
    """GP Helper tools in Dope Sheet header"""
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'HEADER'

    def draw(self, context):
        layout = self.layout
        
        print("DEBUG: GP Helper header draw() called")
        
        # Only show for Grease Pencil objects
        obj = context.active_object
        print(f"DEBUG: Active object: {obj}")
        print(f"DEBUG: Object type: {obj.type if obj else 'None'}")
        
        if not obj or obj.type != 'GREASEPENCIL':
            print("DEBUG: Not showing GP Helper header - no GP object active")
            return
        
        print("DEBUG: Drawing GP Helper header!")
        
        layout.separator_spacer()
        
        # Flip/Flop - most used
        props = context.scene.gph_flip_flop_props
        row = layout.row(align=True)
        
        flip_icon = 'LOOP_BACK' if props.is_flopped else 'LOOP_FORWARDS'
        row.operator("gph.flip_flop_toggle", text="Flip/Flop", icon=flip_icon)
        row.prop(props, "stored_frame", text="")
        
        layout.separator()
        
        # Light Table
        lt_props = context.scene.gph_light_table_props
        row = layout.row(align=True)
        
        if lt_props.enabled:
            row.alert = True
            icon = 'OUTLINER_OB_LIGHT'
        else:
            icon = 'LIGHT'
        
        row.operator("gph.toggle_light_table", text="Light Table", icon=icon, depress=lt_props.enabled)
        row.prop(lt_props, "reference_frame", text="")
        
        layout.separator()
        
        # More tools menu
        layout.menu("DOPESHEET_MT_gp_helper_tools", text="GP Tools", icon='DOWNARROW_HLT')


class DOPESHEET_MT_gp_helper_tools(Menu):
    """Additional GP Helper tools"""
    bl_label = "GP Helper Tools"

    def draw(self, context):
        layout = self.layout
        
        # Keyframe Spacing
        layout.label(text="Keyframe Spacing", icon='KEYFRAME_HLT')
        props = context.scene.gph_keyframe_spacing_props
        layout.prop(props, "spacing_frames", text="Frame Interval")
        layout.operator("gph.keyframe_spacing", text="Space Selected Keyframes")
        
        layout.separator()
        
        # Keyframe Tools
        layout.label(text="Keyframe Mover", icon='FORWARD')
        kf_props = context.scene.gph_keyframe_props
        row = layout.row(align=True)
        row.operator("gph.keyframe_mover_backward", text="", icon='BACK')
        row.operator("gph.keyframe_mover_forward", text="", icon='FORWARD')
        row.prop(kf_props, "frame_offset", text="Offset")
        
        layout.separator()
        
        # Onion Skinning Quick Access
        layout.label(text="Onion Skin", icon='ONIONSKIN')
        
        obj = context.active_object
        if obj and obj.type == 'GREASEPENCIL':
            gp_data = obj.data
            layout.prop(gp_data, "ghost_before_range", text="Before")
            layout.prop(gp_data, "ghost_after_range", text="After")
            layout.prop(gp_data, "onion_factor", text="Opacity", slider=True)