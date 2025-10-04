import bpy
from bpy.types import Panel

class GPH_PT_keyframe_panel(Panel):
    """Panel in the Dope Sheet for keyframe tools"""
    bl_label = "Keyframe Tools"
    bl_idname = "GPH_PT_keyframe_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'GP Helper'

    def draw_header(self, context):
        layout = self.layout
        layout.operator("gph.refresh_icons", text="", icon='FILE_REFRESH', emboss=False)

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_keyframe_props

        # Master controls section
        layout.label(text="Master Controls:")

        # Create a row for the master controls with arrows left, frame picker right
        row = layout.row()

        # Left side: arrows together
        arrow_row = row.row(align=True)
        arrow_row.operator("gph.keyframe_mover_backward", text="", icon='BACK')
        arrow_row.operator("gph.keyframe_mover_forward", text="", icon='FORWARD')

        # Right side: frame picker
        row.prop(props, "frame_offset", text="")

        # Refresh layers button
        layout.separator()
        row = layout.row()
        row.operator("gph.refresh_layers", text="Refresh Layers", icon='FILE_REFRESH')

        # Layer controls toggle
        layout.prop(props, "show_layer_controls", text="Show Layer Controls")

        # Individual layer controls
        if props.show_layer_controls and len(props.layer_settings) > 0:
            layout.separator()
            layout.label(text="Individual Layer Controls:")

            for i, layer_setting in enumerate(props.layer_settings):
                # Create a box for each layer
                box = layout.box()

                # Single horizontal row: checkbox + arrows + layer name
                row = box.row(align=False)

                # Enable/disable checkbox
                row.prop(layer_setting, "is_enabled", text="")

                if layer_setting.is_enabled:
                    # Arrow controls grouped together
                    arrow_row = row.row(align=True)
                    backward_op = arrow_row.operator("gph.keyframe_mover_layer_backward", text="", icon='BACK')
                    backward_op.layer_name = layer_setting.layer_name
                    forward_op = arrow_row.operator("gph.keyframe_mover_layer_forward", text="", icon='FORWARD')
                    forward_op.layer_name = layer_setting.layer_name
                else:
                    # If disabled, add spacing where arrows would be
                    spacer = row.row(align=True)
                    spacer.enabled = False
                    spacer.label(text="  ")

                # Layer name on the right
                row.label(text=layer_setting.layer_name)

        elif props.show_layer_controls and len(props.layer_settings) == 0:
            layout.separator()
            col = layout.column()
            col.label(text="No layers found.", icon='INFO')
            col.label(text="Click 'Refresh Layers' to detect GP layers.")