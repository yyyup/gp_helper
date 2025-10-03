import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, IntProperty, PointerProperty

from .GPH_dissolve_props import GPH_dissolve_properties
from .GPH_marker_spacing_props import GPH_marker_spacing_properties
from .GPH_keyframe_props import GPH_LayerKeyframeSettings, GPH_KeyframeProperties
from .GPH_keyframe_spacing_props import GPH_KeyframeSpacingProps

classes = (
    GPH_dissolve_properties,
    GPH_marker_spacing_properties,
    GPH_LayerKeyframeSettings,
    GPH_KeyframeProperties,
    GPH_KeyframeSpacingProps,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.gph_dissolve_props = PointerProperty(type=GPH_dissolve_properties)
    bpy.types.Scene.gph_marker_spacing_props = PointerProperty(type=GPH_marker_spacing_properties)
    bpy.types.Scene.gph_keyframe_props = PointerProperty(type=GPH_KeyframeProperties)
    bpy.types.Scene.gph_keyframe_spacing_props = PointerProperty(type=GPH_KeyframeSpacingProps)

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