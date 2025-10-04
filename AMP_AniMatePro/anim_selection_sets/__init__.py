import bpy
from . import anim_selection_sets, floating_panels

classes = (anim_selection_sets.classes,)


modules = (
    anim_selection_sets,
    floating_panels,
)


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
