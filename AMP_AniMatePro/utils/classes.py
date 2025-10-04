
class ActiveElement:
    """Helper class to get the active element based on the current mode."""

    @staticmethod
    def get(context):
        """
        Get the active element based on the current mode.

        Returns:
            Object mode: active object
            Pose mode: active pose bone
            Edit mode: active object
            Grease pencil: active grease pencil object
        """
        mode = context.mode
        active_object = context.active_object

        if not active_object:
            return None

        if mode == "POSE" and active_object.type == "ARMATURE":
            # Return active pose bone
            return context.active_pose_bone
        elif mode in {"EDIT_MESH", "EDIT_CURVE", "EDIT_SURFACE", "EDIT_TEXT", "EDIT_ARMATURE", "EDIT_LATTICE"}:
            # Edit mode - return active object
            return active_object
        elif active_object.type == "GPENCIL":
            # Grease pencil object
            return active_object
        else:
            # Object mode or any other mode - return active object
            return active_object

    @staticmethod
    def filter_fcurves_for_element(fcurves, element, context):
        """
        Filter fcurves to only include those belonging to the given element.

        Args:
            fcurves: List of fcurves to filter
            element: The active element (object or pose bone)
            context: Blender context

        Returns:
            List of filtered fcurves
        """
        if not element:
            return []

        # If element is a pose bone, filter for bone-specific fcurves
        if hasattr(element, "name") and hasattr(element, "bone"):
            # This is a pose bone
            bone_name = element.name
            bone_path = f'pose.bones["{bone_name}"]'
            return [fc for fc in fcurves if fc.data_path.startswith(bone_path)]
        else:
            # For objects, return all fcurves (they're already filtered by object)
            return fcurves