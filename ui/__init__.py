import bpy

from .GPH_keyframe_panel import GPH_PT_keyframe_panel
from .GPH_keyframe_spacing_panel import GPH_PT_keyframe_spacing_panel
from .GPH_dissolve_panel import GPH_PT_dissolve_panel
from .GPH_marker_spacing_panel import GPH_PT_marker_spacing_panel
from .GPH_onion_skin_panel import GPH_PT_onion_skin_panel

# NEW IMPORTS
from .GPH_breakdown_panel import GPH_PT_breakdown_panel
from .GPH_flip_flop_panel import GPH_PT_flip_flop_panel
from .GPH_light_table_panel import GPH_PT_light_table_panel

classes = (
    GPH_PT_keyframe_spacing_panel,
    GPH_PT_keyframe_panel,
    GPH_PT_dissolve_panel,
    GPH_PT_marker_spacing_panel,
    GPH_PT_onion_skin_panel,

    # NEW PANELS (in priority order)
    GPH_PT_flip_flop_panel,        # bl_order = 0 (top)
    GPH_PT_breakdown_panel,        # bl_order = 1
    GPH_PT_light_table_panel,      # bl_order = 2
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)