"""
Icon loader for GP Helper addon
Handles loading and registration of custom PNG icons
"""

import bpy
import bpy.utils.previews
import os

# Global variable to store icon previews
preview_collections = {}

def load_icons():
    """Load all custom icons from the icons folder"""
    global preview_collections
    
    # Create a new preview collection
    pcoll = bpy.utils.previews.new()
    
    # Get the icons directory path
    addon_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    icons_dir = os.path.join(addon_dir, "icons")
    
    print(f"GP Helper: Loading icons from {icons_dir}")
    
    # Check if icons directory exists
    if not os.path.exists(icons_dir):
        print(f"GP Helper: Icons directory not found at {icons_dir}")
        preview_collections["main"] = pcoll
        return
    
    # Icon mapping: filename (without .png) -> icon identifier
    icon_files = {
        "GP_Keyframe_spacing": "gph_keyframe_spacing",
        "GP_move_back": "gph_move_backward",
        "GP_move_Front": "gph_move_forward",
        "GP_flip_flop": "gph_flip_flop",
        "GP_light_table": "gph_light_table",
        "GP_breakdown": "gph_breakdown",
        "GP_onion_skin": "gph_onion_skin",
    }
    
    # Load each icon
    loaded_count = 0
    for filename, icon_id in icon_files.items():
        icon_path = os.path.join(icons_dir, f"{filename}.png")
        
        if os.path.exists(icon_path):
            try:
                pcoll.load(icon_id, icon_path, 'IMAGE')
                print(f"GP Helper: Loaded icon '{filename}.png' as '{icon_id}'")
                loaded_count += 1
            except Exception as e:
                print(f"GP Helper: Failed to load icon '{filename}.png': {e}")
        else:
            print(f"GP Helper: Icon file not found: {filename}.png")
    
    print(f"GP Helper: Successfully loaded {loaded_count} custom icons")
    
    # Store the preview collection
    preview_collections["main"] = pcoll


def get_icon(icon_name):
    """
    Get icon ID for use in UI
    
    Args:
        icon_name: Name of the icon (e.g., "gph_keyframe_spacing")
    
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
        bpy.utils.previews.remove(pcoll)
    
    preview_collections.clear()
    print("GP Helper: Unloaded all custom icons")