"""
Icon loader for GP Helper addon
Handles loading and registration of custom PNG icons
"""

import bpy
import bpy.utils.previews
import os
from bpy.app.handlers import persistent

# Global variable to store icon previews
preview_collections = {}

def load_icons():
    """Load all custom icons from the icons folder"""
    global preview_collections
    
    # CRITICAL: Remove old collection if it exists
    if "main" in preview_collections:
        try:
            bpy.utils.previews.remove(preview_collections["main"])
        except:
            pass
        preview_collections.clear()
    
    # Create a new preview collection
    pcoll = bpy.utils.previews.new()
    
    # Get the icons directory path
    addon_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    icons_dir = os.path.join(addon_dir, "icons")
    
    print(f"========================================")
    print(f"GP Helper: LOADING ICONS")
    print(f"GP Helper: Icons directory: {icons_dir}")
    print(f"GP Helper: Directory exists: {os.path.exists(icons_dir)}")
    
    if os.path.exists(icons_dir):
        print(f"GP Helper: Files in directory: {os.listdir(icons_dir)}")
    
    # Icon mapping: filename (without .png) -> icon identifier
    icon_files = {
        "GP_move_back": "gph_move_backward",
        "GP_move_Front": "gph_move_forward",
        "GP_light_table": "gph_light_table",
        "GP_flip_flop": "gph_flip_flop",
    }
    
    # Load each icon
    loaded_count = 0
    for filename, icon_id in icon_files.items():
        icon_path = os.path.join(icons_dir, f"{filename}.png")
        
        print(f"GP Helper: Attempting to load: {icon_path}")
        print(f"GP Helper: File exists: {os.path.exists(icon_path)}")
        
        if os.path.exists(icon_path):
            try:
                # Use absolute path - critical for icon loading
                abs_path = os.path.abspath(icon_path)
                print(f"GP Helper: Absolute path: {abs_path}")
                
                pcoll.load(icon_id, abs_path, 'IMAGE')
                print(f"GP Helper: ✓✓✓ SUCCESS! Loaded '{filename}.png' as '{icon_id}'")
                print(f"GP Helper: Icon ID in collection: {icon_id in pcoll}")
                if icon_id in pcoll:
                    print(f"GP Helper: Icon object: {pcoll[icon_id]}")
                    print(f"GP Helper: Icon ID number: {pcoll[icon_id].icon_id}")
                loaded_count += 1
            except Exception as e:
                print(f"GP Helper: ✗✗✗ FAILED to load '{filename}.png': {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"GP Helper: ✗ Icon file not found: {filename}.png")
    
    print(f"GP Helper: Total icons loaded: {loaded_count}")
    print(f"GP Helper: Icons in collection: {list(pcoll.keys())}")
    print(f"========================================")
    
    # Store the preview collection
    preview_collections["main"] = pcoll


def get_icon(icon_name):
    """
    Get icon ID for use in UI
    
    Args:
        icon_name: Name of the icon (e.g., "gph_move_backward")
    
    Returns:
        Icon ID number for use in layout.operator(..., icon_value=...)
        Returns 0 if icon not found (will use default icon)
    """
    global preview_collections
    
    pcoll = preview_collections.get("main")
    if not pcoll:
        return 0
    
    icon = pcoll.get(icon_name)
    if icon:
        return icon.icon_id
    
    return 0


def unload_icons():
    """Unload all custom icons"""
    global preview_collections

    for pcoll in preview_collections.values():
        try:
            bpy.utils.previews.remove(pcoll)
        except:
            pass

    preview_collections.clear()


@persistent
def load_icons_on_file_load(dummy):
    """Handler to reload icons when opening a file"""
    load_icons()