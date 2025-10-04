import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, IntProperty, PointerProperty

from .GPH_dissolve_props import GPH_dissolve_properties
from .GPH_marker_spacing_props import GPH_marker_spacing_properties
from .GPH_keyframe_props import GPH_LayerKeyframeSettings, GPH_KeyframeProperties
from .GPH_keyframe_spacing_props import GPH_KeyframeSpacingProps
from .GPH_breakdown_props import GPH_BreakdownProps
from .GPH_flip_flop_props import GPH_FlipFlopProps
from .GPH_light_table_props import GPH_LightTableProps
from .GPH_layer_props import GPH_LayerManagerProps  # NEW

classes = (
    GPH_dissolve_properties,
    GPH_marker_spacing_properties,
    GPH_LayerKeyframeSettings,
    GPH_KeyframeProperties,
    GPH_KeyframeSpacingProps,
    GPH_BreakdownProps,
    GPH_FlipFlopProps,
    GPH_LightTableProps,
    GPH_LayerManagerProps,  # NEW
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.gph_dissolve_props = PointerProperty(type=GPH_dissolve_properties)
    bpy.types.Scene.gph_marker_spacing_props = PointerProperty(type=GPH_marker_spacing_properties)
    bpy.types.Scene.gph_keyframe_props = PointerProperty(type=GPH_KeyframeProperties)
    bpy.types.Scene.gph_keyframe_spacing_props = PointerProperty(type=GPH_KeyframeSpacingProps)
    bpy.types.Scene.gph_breakdown_props = PointerProperty(type=GPH_BreakdownProps)
    bpy.types.Scene.gph_flip_flop_props = PointerProperty(type=GPH_FlipFlopProps)
    bpy.types.Scene.gph_light_table_props = PointerProperty(type=GPH_LightTableProps)
    bpy.types.Scene.gph_layer_manager_props = PointerProperty(type=GPH_LayerManagerProps)  # NEW

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Scene, 'gph_dissolve_props'):
        del bpy.types.Scene.gph_dissolve_props
    if hasattr(bpy.types.Scene, 'gph_marker_spacing_props'):
        del bpy.types.Scene.gph_marker_spacing_props
    if hasattr(bpy.types.Scene, 'gph_keyframe_props'):
        del bpy.types.Scene.gph_keyframe_props
    if hasattr(bpy.types.Scene, 'gph_keyframe_spacing_props'):
        del bpy.types.Scene.gph_keyframe_spacing_props
    if hasattr(bpy.types.Scene, 'gph_breakdown_props'):
        del bpy.types.Scene.gph_breakdown_props
    if hasattr(bpy.types.Scene, 'gph_flip_flop_props'):
        del bpy.types.Scene.gph_flip_flop_props
    if hasattr(bpy.types.Scene, 'gph_light_table_props'):
        del bpy.types.Scene.gph_light_table_props
    if hasattr(bpy.types.Scene, 'gph_layer_manager_props'):
        del bpy.types.Scene.gph_layer_manager_props  # NEW