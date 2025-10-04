import bpy
from . import anim_visual_aid

modules = (anim_visual_aid,)


# Register classes and properties
def register():
    for module in modules:
        try:
            module.register()
        except Exception as e:
            print(f"Failed to register {module}: {e}")


# Unregister classes and properties
def unregister():
    for module in reversed(modules):
        try:
            module.unregister()
        except Exception as e:
            print(f"Failed to unregister {module}: {e}")
