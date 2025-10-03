import bpy
from bpy.types import Panel

class GPH_PT_breakdown_panel(Panel):
    """Panel for breakdown helper tools"""
    bl_label = "Breakdown Helper"
    bl_idname = "GPH_PT_breakdown_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 1  # High priority - near top

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_breakdown_props

        # Check if GP object exists
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            layout.label(text="No Grease Pencil object active", icon='ERROR')
            return

        # Quick presets - most common use case
        box = layout.box()
        box.label(text="Quick Breakdown:", icon='KEYFRAME_HLT')

        row = box.row(align=True)
        row.scale_y = 1.5  # Make buttons bigger
        row.operator("gph.breakdown_favor_first", text="25%")
        row.operator("gph.breakdown_middle", text="50%")
        row.operator("gph.breakdown_favor_last", text="75%")

        layout.separator()

        # Advanced settings
        box = layout.box()
        box.label(text="Advanced Settings:", icon='SETTINGS')

        # Position control
        col = box.column(align=True)
        col.prop(props, "use_custom_offset")

        if props.use_custom_offset:
            col.prop(props, "custom_offset", text="Offset (frames)")
        else:
            col.prop(props, "position", text="Position", slider=True)

        # Copy mode
        box.prop(props, "copy_mode", text="Mode")

        # Options
        col = box.column(align=True)
        col.prop(props, "shift_subsequent")
        col.prop(props, "apply_to_all_layers")

        layout.separator()

        # Manual execution with custom settings
        layout.operator("gph.add_breakdown", text="Add Custom Breakdown", icon='KEYFRAME')

        # Info/Help
        box = layout.box()
        box.label(text="Usage:", icon='INFO')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Select 2+ keyframes")
        col.label(text="2. Click preset or adjust settings")
        col.label(text="3. Breakdown created between pairs")
