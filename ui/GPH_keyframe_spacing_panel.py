import bpy
from bpy.types import Panel

class GPH_PT_keyframe_spacing_panel(Panel):
    """Panel in the Dope Sheet for keyframe spacing tools"""
    bl_label = "Keyframe Spacing"
    bl_idname = "GPH_PT_keyframe_spacing_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'
    bl_order = 0  # This makes it appear above other panels

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_keyframe_spacing_props

        # Spacing frames input
        row = layout.row()
        row.prop(props, "spacing_frames", text="Frame Interval")
        


        # Space keyframes button
        row = layout.row()
        op = row.operator("gph.keyframe_spacing", text="Space Selected Keyframes")
        op.spacing_frames = props.spacing_frames
        op.ripple_edit = props.ripple_edit