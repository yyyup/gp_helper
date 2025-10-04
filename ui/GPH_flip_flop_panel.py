import bpy
from bpy.types import Panel
from ..utils import get_icon

class GPH_PT_flip_flop_panel(Panel):
    """Panel for flip/flop tool"""
    bl_label = "Flip/Flop"
    bl_idname = "GPH_PT_flip_flop_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 0  # Top priority - most used tool

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_flip_flop_props
        scene = context.scene

        # Status indicator - FIXED HEIGHT to prevent button jumping
        box = layout.box()
        col = box.column(align=True)
        
        # First row - always shown
        row = col.row()
        if props.is_flopped:
            row.alert = True
            row.label(text=f"FLOPPED → Frame {scene.frame_current}", icon='DECORATE_KEYFRAME')
        else:
            row.label(text=f"Current Frame: {scene.frame_current}", icon='KEYFRAME')
        
        # Second row - always present (either shows original or is empty)
        row = col.row()
        if props.is_flopped:
            row.label(text=f"Original: {props.original_frame}")
        else:
            row.label(text="")  # Empty label to maintain height

        layout.separator()

        # Main flip/flop button - BIG and obvious
        row = layout.row()
        row.scale_y = 2.0

        flip_icon = 'LOOP_BACK' if props.is_flopped else 'LOOP_FORWARDS'
        row.operator("gph.flip_flop_toggle", text="FLIP/FLOP", icon=flip_icon, depress=props.is_flopped)

        layout.separator()

        # Stored frame control
        box = layout.box()
        box.label(text="Reference Frame:", icon='KEYFRAME_HLT')
        
        col = box.column(align=True)
        col.prop(props, "stored_frame", text="Target Frame")
        col.operator("gph.set_flip_frame", text="Set to Current", icon_value=get_icon("gph_picker"))

        layout.separator()

        # Reset button - only show when flopped
        if props.is_flopped:
            layout.operator("gph.reset_flip_flop", text="Reset", icon='LOOP_BACK')