import bpy
from bpy.types import Panel

class GPH_PT_dissolve_panel(Panel):
    bl_label = "GP Dissolve Automation"
    bl_idname = "GPH_PT_dissolve_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = "GP Helper"

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_dissolve_props

        layout.label(text="Dissolve Effect Setup", icon='GP_MULTIFRAME_EDITING')

        box = layout.box()
        box.label(text="Layer Selection:", icon='OUTLINER_DATA_GP_LAYER')

        row = box.row()
        row.prop(props, "layer2_name")
        row = box.row()
        row.prop(props, "layer1_name")

        box.operator("gph.dissolve_refresh", icon='FILE_REFRESH')

        box = layout.box()
        box.label(text="Animation Settings:", icon='PREFERENCES')
        box.prop(props, "total_frames")
        box.prop(props, "cycle_length")

        layout.separator()
        layout.operator("gph.dissolve_setup", icon='KEYFRAME_HLT')

