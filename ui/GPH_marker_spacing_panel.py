import bpy
from bpy.types import Panel

class GPH_PT_marker_spacing_panel(Panel):
    bl_label = "Marker Spacing"
    bl_idname = "GPH_PT_marker_spacing_panel"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_category = "GP Helper"

    def draw(self, context):
        layout = self.layout
        props = context.scene.gph_marker_spacing_props

        layout.label(text="Marker-Based Spacing", icon='MARKER_HLT')

        # Spacing method selection
        box = layout.box()
        box.label(text="Spacing Method:", icon='PREFERENCES')
        box.prop(props, "spacing_method", expand=True)

        # Method-specific settings
        if props.spacing_method == 'MULTIPLIER':
            box.prop(props, "spacing_multiplier")
            box.prop(props, "auto_detect_spacing")
        else:  # FIXED
            box.prop(props, "fixed_spacing")

        # Target settings
        box = layout.box()
        box.label(text="Target:", icon='RESTRICT_SELECT_OFF')
        box.prop(props, "target_selected_only")

        # GP Marker creation
        box = layout.box()
        box.label(text="GP Spacing Markers:", icon='MARKER_HLT')
        box.operator("gph.add_gp_marker", text="Add GP Marker at Current Frame", icon='ADD')

        # Cleanup options
        box = layout.box()
        box.label(text="Cleanup:", icon='TRASH')
        box.prop(props, "auto_cleanup_markers")

        layout.separator()

        # Action buttons
        layout.operator("gph.marker_spacing", text="Apply Marker Spacing", icon='KEYFRAME_HLT')

        layout.separator()
        layout.operator("gph.clear_markers", text="Clear All GP Spacing Markers", icon='X')

