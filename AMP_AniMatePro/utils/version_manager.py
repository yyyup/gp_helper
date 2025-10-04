import bpy
import os


def is_forge_version():
    # Get the addon directory path
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    forge_modules_path = os.path.join(addon_dir, "forge_modules")
    
    # Check if forge_modules folder exists in the addon directory
    if os.path.exists(forge_modules_path) and os.path.isdir(forge_modules_path):
        return True
    return False
