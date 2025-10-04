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




# NEW IMPORTS
from .GPH_breakdown import (
    GPH_OT_add_breakdown,
    GPH_OT_breakdown_preset,
    GPH_OT_breakdown_favor_first,
    GPH_OT_breakdown_middle,
    GPH_OT_breakdown_favor_last
)
from .GPH_flip_flop import (
    GPH_OT_flip_flop_toggle,
    GPH_OT_set_flip_frame,
    GPH_OT_flip_to_previous,
    GPH_OT_flip_to_next,
    GPH_OT_reset_flip_flop
)
from .GPH_light_table import (
    GPH_OT_toggle_light_table,
    GPH_OT_set_reference_frame,
    GPH_OT_update_light_table,
    GPH_OT_clear_reference,
    GPH_OT_jump_to_reference
)

from .GPH_layer_operations import (
    GPH_OT_layer_solo,
    GPH_OT_layer_duplicate,
    GPH_OT_layer_make_active,
)
from .GPH_refresh_icons import GPH_OT_refresh_icons

classes = (
    # Existing operators
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

    # NEW: Breakdown operators
    GPH_OT_add_breakdown,
    GPH_OT_breakdown_preset,
    GPH_OT_breakdown_favor_first,
    GPH_OT_breakdown_middle,
    GPH_OT_breakdown_favor_last,

    # NEW: Flip/Flop operators
    GPH_OT_flip_flop_toggle,
    GPH_OT_set_flip_frame,
    GPH_OT_flip_to_previous,
    GPH_OT_flip_to_next,
    GPH_OT_reset_flip_flop,

    # NEW: Light Table operators
    GPH_OT_toggle_light_table,
    GPH_OT_set_reference_frame,
    GPH_OT_update_light_table,
    GPH_OT_clear_reference,
    GPH_OT_jump_to_reference,
    
    # NEW: Layer management operators
    GPH_OT_layer_solo,
    GPH_OT_layer_duplicate,
    GPH_OT_layer_make_active,

    # NEW: Utility operators
    GPH_OT_refresh_icons,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)