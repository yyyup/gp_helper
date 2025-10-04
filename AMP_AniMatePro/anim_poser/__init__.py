import bpy
from . import anim_poser, anim_silhouette

modules = (anim_poser, anim_silhouette)


# Register classes and properties
def register():
    for module in modules:
        try:
            module.register()
        except:
            pass


# Unregister classes and properties
def unregister():
    for module in reversed(modules):
        try:
            module.unregister()
        except:
            pass
