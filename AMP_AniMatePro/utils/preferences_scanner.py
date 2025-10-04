"""
Preferences Scanner Utility

This module automatically discovers and integrates preferences from sub-modules
into the main addon preferences class.
"""

import os
import sys
import importlib
import importlib.util
import inspect
from typing import Dict, List, Any

try:
    import bpy
    from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty, EnumProperty, FloatVectorProperty
except ImportError:
    # Handle case where bpy is not available (e.g., during development)
    bpy = None
    BoolProperty = FloatProperty = IntProperty = StringProperty = EnumProperty = FloatVectorProperty = None


def scan_for_preferences(addon_path: str, base_package: str) -> Dict[str, Any]:
    """
    Scan through the addon directory tree looking for preferences.py files
    and extract property definitions from them.

    Args:
        addon_path: Path to the addon root directory
        base_package: Base package name for the addon

    Returns:
        Dictionary mapping module names to their property definitions
    """
    preferences_map = {}

    for root, dirs, files in os.walk(addon_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        if "preferences.py" in files:
            pref_file_path = os.path.join(root, "preferences.py")

            # Skip the main preferences.py file
            if os.path.normpath(pref_file_path) == os.path.normpath(os.path.join(addon_path, "preferences.py")):
                continue

            # Calculate relative module path
            rel_path = os.path.relpath(root, addon_path)
            if rel_path == ".":
                module_name = f"{base_package}.preferences"
            else:
                module_parts = rel_path.replace(os.sep, ".").split(".")
                module_name = f"{base_package}.{'.'.join(module_parts)}.preferences"

            try:
                properties = extract_properties_from_file(pref_file_path, module_name)
                if properties:
                    preferences_map[module_name] = properties
                    print(f"[AMP Preferences Scanner] Found preferences in: {module_name}")
            except Exception as e:
                print(f"[AMP Preferences Scanner] Error scanning {pref_file_path}: {e}")

    return preferences_map


def extract_properties_from_file(file_path: str, module_name: str) -> Dict[str, Any]:
    """
    Extract property definitions from a preferences.py file.

    Args:
        file_path: Path to the preferences.py file
        module_name: Module name for importing

    Returns:
        Dictionary of property definitions
    """
    properties = {}

    try:
        # Read the file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to import the module to get the actual property objects
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for AddonPreferences classes
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and hasattr(obj, "__annotations__")
                        and bpy
                        and issubclass(obj, bpy.types.AddonPreferences)
                    ):

                        # Extract properties from the class
                        for attr_name in dir(obj):
                            if not attr_name.startswith("_"):
                                attr = getattr(obj, attr_name)
                                # Check if this is a Blender property
                                if bpy and hasattr(attr, "__class__") and "Property" in str(type(attr)):
                                    # Create a prefixed property name to avoid conflicts
                                    module_prefix = module_name.split(".")[-2] if "." in module_name else "sub"
                                    prefixed_name = f"{module_prefix}_{attr_name}"
                                    properties[prefixed_name] = attr

        except Exception as import_error:
            print(f"[AMP Preferences Scanner] Could not import {module_name}: {import_error}")
            # Fallback: parse the file content for basic property definitions
            properties = parse_properties_from_content(content, file_path)

    except Exception as e:
        print(f"[AMP Preferences Scanner] Error reading {file_path}: {e}")

    return properties


def parse_properties_from_content(content: str, file_path: str) -> Dict[str, Any]:
    """
    Fallback method to parse property definitions from file content using basic string parsing.
    This is used when importing the module fails.

    Args:
        content: File content as string
        file_path: Path to the file (for error reporting)

    Returns:
        Dictionary of property definitions (simplified)
    """
    properties = {}

    try:
        # Extract module name from file path for prefixing
        path_parts = file_path.replace("\\", "/").split("/")
        module_prefix = "sub"

        # Try to find a meaningful module name
        for i, part in enumerate(path_parts):
            if part == "forge_modules" and i + 1 < len(path_parts):
                module_prefix = path_parts[i + 1]
                break
            elif "modules" in part and i + 1 < len(path_parts):
                module_prefix = path_parts[i + 1]
                break

        # Simple pattern matching for property definitions
        import re

        # Pattern to match property definitions
        prop_pattern = r"(\w+):\s*(\w+Property)\s*\("
        matches = re.findall(prop_pattern, content)

        for prop_name, prop_type in matches:
            if not prop_name.startswith("_"):
                prefixed_name = f"{module_prefix}_{prop_name}"

                # Create a basic property based on type (only if bpy is available)
                if bpy and BoolProperty:
                    if prop_type == "BoolProperty":
                        properties[prefixed_name] = BoolProperty(
                            name=f"{module_prefix.title()} {prop_name.replace('_', ' ').title()}",
                            description=f"Property from {module_prefix} module",
                            default=False,
                        )
                    elif prop_type == "FloatProperty":
                        properties[prefixed_name] = FloatProperty(
                            name=f"{module_prefix.title()} {prop_name.replace('_', ' ').title()}",
                            description=f"Property from {module_prefix} module",
                            default=0.0,
                        )
                    elif prop_type == "IntProperty":
                        properties[prefixed_name] = IntProperty(
                            name=f"{module_prefix.title()} {prop_name.replace('_', ' ').title()}",
                            description=f"Property from {module_prefix} module",
                            default=0,
                        )
                    elif prop_type == "StringProperty":
                        properties[prefixed_name] = StringProperty(
                            name=f"{module_prefix.title()} {prop_name.replace('_', ' ').title()}",
                            description=f"Property from {module_prefix} module",
                            default="",
                        )
                    elif prop_type == "FloatVectorProperty":
                        properties[prefixed_name] = FloatVectorProperty(
                            name=f"{module_prefix.title()} {prop_name.replace('_', ' ').title()}",
                            description=f"Property from {module_prefix} module",
                            size=3,
                            default=(0.0, 0.0, 0.0),
                        )

    except Exception as e:
        print(f"[AMP Preferences Scanner] Error parsing content from {file_path}: {e}")

    return properties


def integrate_sub_preferences(main_preferences_class, addon_path: str, base_package: str):
    """
    Integrate sub-module preferences into the main preferences class.

    Args:
        main_preferences_class: The main AddonPreferences class to extend
        addon_path: Path to the addon root directory
        base_package: Base package name for the addon
    """
    try:
        # Scan for preferences
        preferences_map = scan_for_preferences(addon_path, base_package)

        # Add properties to the main class
        for module_name, properties in preferences_map.items():
            for prop_name, prop_definition in properties.items():
                if not hasattr(main_preferences_class, prop_name):
                    setattr(main_preferences_class, prop_name, prop_definition)
                    print(f"[AMP Preferences Scanner] Added property: {prop_name} from {module_name}")
                else:
                    print(f"[AMP Preferences Scanner] Property {prop_name} already exists, skipping")

    except Exception as e:
        print(f"[AMP Preferences Scanner] Error integrating sub-preferences: {e}")


def get_sub_preference(context, module_prefix: str, property_name: str, default=None):
    """
    Helper function to get a sub-module preference value.

    Args:
        context: Blender context
        module_prefix: Module prefix used when registering the property
        property_name: Original property name
        default: Default value if property not found

    Returns:
        Property value or default
    """
    try:
        addon_prefs = context.preferences.addons[__package__].preferences
        prefixed_name = f"{module_prefix}_{property_name}"
        return getattr(addon_prefs, prefixed_name, default)
    except Exception:
        return default


def set_sub_preference(context, module_prefix: str, property_name: str, value):
    """
    Helper function to set a sub-module preference value.

    Args:
        context: Blender context
        module_prefix: Module prefix used when registering the property
        property_name: Original property name
        value: Value to set
    """
    try:
        addon_prefs = context.preferences.addons[__package__].preferences
        prefixed_name = f"{module_prefix}_{property_name}"
        setattr(addon_prefs, prefixed_name, value)
    except Exception as e:
        print(f"[AMP Preferences Scanner] Error setting preference {prefixed_name}: {e}")
