import bpy
from . import anim_lattice

classes = (anim_lattice.classes,)


modules = (anim_lattice,)


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
