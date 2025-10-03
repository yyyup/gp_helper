import bpy

from .GPH_keyframe_panel import GPH_PT_keyframe_panel
from .GPH_keyframe_spacing_panel import GPH_PT_keyframe_spacing_panel
from .GPH_dissolve_panel import GPH_PT_dissolve_panel
from .GPH_marker_spacing_panel import GPH_PT_marker_spacing_panel
from .GPH_onion_skin_panel import GPH_PT_onion_skin_panel

classes = (
    GPH_PT_keyframe_spacing_panel,
    GPH_PT_keyframe_panel,
    GPH_PT_dissolve_panel,
    GPH_PT_marker_spacing_panel,
    GPH_PT_onion_skin_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)