import bpy


class ActiveElement:
    """
    Resolves the actual active element in the context,
    whether it's an object or pose bone.
    """

    def __init__(self):
        self.context = bpy.context

    @property
    def element(self):
        # Return pose bone only in pose mode
        if self.context.active_pose_bone and self.context.mode == "POSE":
            return self.context.active_pose_bone
        # Otherwise, return the active object
        elif self.context.active_object:
            return self.context.active_object
        return None

    @property
    def type(self):
        if self.context.active_pose_bone and self.context.mode == "POSE":
            return "POSE_BONE"
        elif self.context.active_object:
            return "OBJECT"
        return "NONE"


# Convenience functions
def get_active_element():
    """Get the active element (object or pose bone)."""
    return ActiveElement().element


def get_active_element_type():
    """Get the type of the active element."""
    return ActiveElement().type


# Context property extensions
def context_active_element_get(self):
    """Context property getter for active_element."""
    return ActiveElement().element


def context_active_element_type_get(self):
    """Context property getter for active_element_type."""
    return ActiveElement().type


def register_context_properties():
    """Register context properties."""
    bpy.types.Context.active_element = property(context_active_element_get)
    bpy.types.Context.active_element_type = property(context_active_element_type_get)


def unregister_context_properties():
    """Unregister context properties."""
    for prop in ("active_element", "active_element_type"):
        if hasattr(bpy.types.Context, prop):
            delattr(bpy.types.Context, prop)


def register():
    """Register the addon."""
    register_context_properties()


def unregister():
    """Unregister the addon."""
    unregister_context_properties()
