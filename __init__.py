bl_info = {
    "name": "GP Helper",
    "author": "CGstuff",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Dope Sheet > N-panel, Animation Editors",
    "description": "Grease Pencil automation tools and helper operators for Blender",
    "category": "Animation",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
from . import operators, ui, properties

modules = [
    properties,
    operators,
    ui,
]

def register():
    for module in modules:
        module.register()

def unregister():
    for module in reversed(modules):
        module.unregister()

if __name__ == "__main__":
    register()