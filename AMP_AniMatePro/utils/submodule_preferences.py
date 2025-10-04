"""
Sub-module preferences access utilities

This module provides helper functions for sub-modules to access their preferences
that have been integrated into the main addon preferences.
"""

import bpy
from typing import Any


def get_submodule_preference(module_name: str, property_name: str, default: Any = None, context=None) -> Any:
    """
    Get a sub-module preference value from the main addon preferences.

    Args:
        module_name: Name of the sub-module (e.g., 'anim_onionskinning')
        property_name: Original property name from the sub-module
        default: Default value if property not found
        context: Blender context (optional, will use bpy.context if not provided)

    Returns:
        Property value or default

    Example:
        # From a sub-module, get the 'before_color' property
        before_color = get_submodule_preference('anim_onionskinning', 'before_color', (1.0, 0.0, 0.0))
    """
    if context is None:
        context = bpy.context

    try:
        # Get the main addon name from the current package
        from .. import __package__ as base_package

        addon_prefs = context.preferences.addons[base_package].preferences

        # Create the prefixed property name that was used during integration
        prefixed_name = f"{module_name}_{property_name}"

        return getattr(addon_prefs, prefixed_name, default)

    except Exception as e:
        print(f"[AMP Sub-Preferences] Error getting {module_name}.{property_name}: {e}")
        return default


def set_submodule_preference(module_name: str, property_name: str, value: Any, context=None) -> bool:
    """
    Set a sub-module preference value in the main addon preferences.

    Args:
        module_name: Name of the sub-module (e.g., 'anim_onionskinning')
        property_name: Original property name from the sub-module
        value: Value to set
        context: Blender context (optional, will use bpy.context if not provided)

    Returns:
        True if successful, False otherwise

    Example:
        # From a sub-module, set the 'before_color' property
        success = set_submodule_preference('anim_onionskinning', 'before_color', (0.5, 0.5, 1.0))
    """
    if context is None:
        context = bpy.context

    try:
        # Get the main addon name from the current package
        from .. import __package__ as base_package

        addon_prefs = context.preferences.addons[base_package].preferences

        # Create the prefixed property name that was used during integration
        prefixed_name = f"{module_name}_{property_name}"

        setattr(addon_prefs, prefixed_name, value)
        return True

    except Exception as e:
        print(f"[AMP Sub-Preferences] Error setting {module_name}.{property_name}: {e}")
        return False


def has_submodule_preference(module_name: str, property_name: str, context=None) -> bool:
    """
    Check if a sub-module preference exists in the main addon preferences.

    Args:
        module_name: Name of the sub-module (e.g., 'anim_onionskinning')
        property_name: Original property name from the sub-module
        context: Blender context (optional, will use bpy.context if not provided)

    Returns:
        True if the property exists, False otherwise
    """
    if context is None:
        context = bpy.context

    try:
        # Get the main addon name from the current package
        from .. import __package__ as base_package

        addon_prefs = context.preferences.addons[base_package].preferences

        # Create the prefixed property name that was used during integration
        prefixed_name = f"{module_name}_{property_name}"

        return hasattr(addon_prefs, prefixed_name)

    except Exception:
        return False


def list_submodule_preferences(module_name: str, context=None) -> list:
    """
    List all preferences for a specific sub-module.

    Args:
        module_name: Name of the sub-module (e.g., 'anim_onionskinning')
        context: Blender context (optional, will use bpy.context if not provided)

    Returns:
        List of property names (without the module prefix)
    """
    if context is None:
        context = bpy.context

    try:
        # Get the main addon name from the current package
        from .. import __package__ as base_package

        addon_prefs = context.preferences.addons[base_package].preferences

        # Find all properties that start with the module prefix
        prefix = f"{module_name}_"
        properties = []

        for attr_name in dir(addon_prefs):
            if attr_name.startswith(prefix) and not attr_name.startswith("__"):
                # Remove the prefix to get the original property name
                original_name = attr_name[len(prefix) :]
                properties.append(original_name)

        return properties

    except Exception as e:
        print(f"[AMP Sub-Preferences] Error listing preferences for {module_name}: {e}")
        return []
