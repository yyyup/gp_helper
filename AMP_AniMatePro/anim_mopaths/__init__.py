import bpy
from . import anim_mopaths, anim_offset_mopaths

modules = (anim_mopaths, anim_offset_mopaths)


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
