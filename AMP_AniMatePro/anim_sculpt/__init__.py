import bpy
from . import anim_sculpt

classes = (anim_sculpt.classes,)


modules = (anim_sculpt,)


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
