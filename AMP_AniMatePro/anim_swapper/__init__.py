import bpy
from . import anim_swapper

modules = (
    anim_swapper,
)


# Register classes and properties
def register():
    for module in modules:

        module.register()


# Unregister classes and properties
def unregister():
    for module in reversed(modules):
        try:
            module.unregister()
        except:
            pass
