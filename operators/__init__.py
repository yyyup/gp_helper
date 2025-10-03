import bpy

from .GPH_keyframe_mover import (
    GPH_OT_keyframe_mover,
    GPH_OT_keyframe_mover_forward,
    GPH_OT_keyframe_mover_backward,
    GPH_OT_refresh_layers,
    GPH_OT_keyframe_mover_layer_forward,
    GPH_OT_keyframe_mover_layer_backward
)
from .GPH_dissolve_automation import GPH_OT_dissolve_setup, GPH_OT_dissolve_refresh
from .GPH_marker_spacing import GPH_OT_marker_spacing, GPH_OT_clear_markers, GPH_OT_add_gp_marker
from .GPH_keyframe_spacing import GPH_OT_keyframe_spacing

classes = (
    GPH_OT_keyframe_mover,
    GPH_OT_keyframe_mover_forward,
    GPH_OT_keyframe_mover_backward,
    GPH_OT_refresh_layers,
    GPH_OT_keyframe_mover_layer_forward,
    GPH_OT_keyframe_mover_layer_backward,
    GPH_OT_keyframe_spacing,
    GPH_OT_dissolve_setup,
    GPH_OT_dissolve_refresh,
    GPH_OT_marker_spacing,
    GPH_OT_clear_markers,
    GPH_OT_add_gp_marker,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)