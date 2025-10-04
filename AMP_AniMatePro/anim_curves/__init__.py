import bpy
from . import anim_curves
from . import anim_curve_tools_operators

modules = (anim_curves, anim_curve_tools_operators)


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
