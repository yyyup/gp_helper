import bpy
from bpy.types import Panel
from ..utils import get_icon

class GPH_PT_light_table_panel(Panel):
    """Panel for light table / reference frame"""
    bl_label = "Light Table"
    bl_idname = "GPH_PT_light_table_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_light_table_props

        # Check if GP object exists
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            layout.label(text="No Grease Pencil object active", icon='ERROR')
            return

        # Main toggle - big and obvious
        box = layout.box()
        row = box.row()
        row.scale_y = 1.5

        # Get custom light table icon with alpha
        light_table_icon = get_icon("gph_light_table_a")

        if props.enabled:
            row.alert = True
            text = "Light Table: ON"
        else:
            text = "Light Table: OFF"

        if light_table_icon and light_table_icon > 0:
            row.operator("gph.toggle_light_table", text=text, icon_value=light_table_icon, depress=props.enabled)
        else:
            icon = 'OUTLINER_OB_LIGHT' if props.enabled else 'LIGHT'
            row.operator("gph.toggle_light_table", text=text, icon=icon, depress=props.enabled)

        # Reference frame controls
        box = layout.box()
        box.label(text="Reference Frame:", icon='KEYFRAME_HLT')

        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(props, "reference_frame", text="Frame")
        row.operator("gph.set_reference_frame", text="", icon_value=get_icon("gph_picker"))

        col.operator("gph.jump_to_reference", text="Jump to Reference", icon='PLAY')

        box.prop(props, "lock_to_current", text="Lock to Current Frame")

        if props.lock_to_current:
            box.label(text=f"Locked: {context.scene.frame_current}", icon='LOCKED')

        # Display settings
        box = layout.box()
        box.label(text="Display:", icon='HIDE_OFF')

        col = box.column(align=True)
        col.prop(props, "opacity", text="Opacity", slider=True)
        col.prop(props, "show_in_front", text="Show in Front")

        # Color tint
        col = box.column(align=True)
        col.prop(props, "use_tint", text="Use Color Tint")
        if props.use_tint:
            col.prop(props, "tint_color", text="")

        layout.separator()

        # Clear button
        if props.enabled:
            layout.operator("gph.clear_reference", text="Clear Light Table", icon='X')

        # Help
        box = layout.box()
        box.label(text="Usage:", icon='INFO')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Set reference frame")
        col.label(text="2. Enable light table")
        col.label(text="3. Draw on current frame")
        col.label(text="4. Reference shows as overlay")
