bl_info = {
    "name": "GP Helper",
    "author": "CGstuff",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "Dope Sheet > N-panel, Animation Editors",
    "description": "Grease Pencil automation tools including Breakdown Helper, Flip/Flop, and Light Table for professional 2D animation workflow",
    "category": "Animation",
    "doc_url": "",
    "tracker_url": "",
}

import bpy

# Reload support for development
if "bpy" in locals():
    import importlib
    if "operators" in locals():
        importlib.reload(operators)
    if "ui" in locals():
        importlib.reload(ui)
    if "properties" in locals():
        importlib.reload(properties)
    if "utils" in locals():
        importlib.reload(utils)

from . import operators, ui, properties, utils

modules = [
    properties,
    operators,
    ui,
]

def register():
    # Load custom icons first
    utils.load_icons()
    
    # Register modules
    for module in modules:
        module.register()

def unregister():
    # Unregister modules
    for module in reversed(modules):
        module.unregister()
    
    # Unload custom icons
    utils.unload_icons()

if __name__ == "__main__":
    register()