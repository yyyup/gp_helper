import bpy
from bpy.types import PropertyGroup
from bpy.props import IntProperty

def update_active_layer(self, context):
    """Update the active GP layer when list selection changes"""
    obj = context.active_object
    if obj and obj.type == 'GREASEPENCIL':
        gp_data = obj.data
        layers_list = list(gp_data.layers)

        if 0 <= self.active_layer_index < len(layers_list):
            gp_data.layers.active = layers_list[self.active_layer_index]

class GPH_LayerManagerProps(PropertyGroup):
    """Properties for layer manager"""

    active_layer_index: IntProperty(
        name="Active Layer Index",
        description="Index of the active layer in the list",
        default=0,
        min=0,
        update=update_active_layer
    )