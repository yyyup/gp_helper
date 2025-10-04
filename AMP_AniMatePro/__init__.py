#############
## init.py ##
#############

# license


"""
            #################################
            ## AniMate Pro: Timeline Tools ##
            #################################

Copyright (C) 2024, Jose Ignacio de Andres, NotThatNDA, www.x.com/notthatnda

GNU GENERAL PUBLIC LICENSE Version 3

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.
If not, see <https://www.gnu.org/licenses/>.

"""

# Credits

"""
Addon created by not_that_nda (Nacho de Andres)

Original code for anim_offset from Ares Deveaux
Adaptation to AniMatePro by not_that_nda (Nacho de Andres)

"""

bl_info = {
    "name": "AniMate - AniMate Pro Core",
    "category": "Animation",
    "description": "Supercharge your Animation Workflow",
    "author": "NotThatNDA",
    "blender": (4, 1, 0),
    "version": (0, 25, 30922),
    "location": "Animation Editors and 3D View",
    "warning": "Early Access",
    "doc_url": "https://linktr.ee/notthatnda",
    "tracker_url": "https://discord.gg/JWzJxTKx48",
    "support": "COMMUNITY",
    "location": "Preferences > Addons > AniMatePro",
}
from .ui import blender_ui, top_sections, ui, side_panles_ui, addon_ui, addon_ui_default_top_panels

from .ui.top_sections_definitions import section_definitions as section_definitions

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, PropertyGroup, Operator, Scene
from bpy.app.handlers import persistent, depsgraph_update_post, load_post, load_pre
from bpy.utils import register_class, unregister_class
from .utils import customIcons, get_prefs
from .utils.version_manager import is_forge_version

CORE_VERSION = False
FORGE_VERSION = is_forge_version() and not CORE_VERSION

from . import (
    preferences,
    utils,
    operators,
    anim_offset,
    properties,
    autoKeying,
    anim_slicer,
    markers_tools,
    anim_sculpt,
    anim_shifter,
    anim_curves,
    anim_scrub,
    anim_euler,
    anim_retimer,
    anim_keyframer,
    anim_looper,
    anim_baker,
    anim_mopaths,
    anim_timewarper,
    anim_timeblocker,
    anim_nudger,
    anim_lattice,
    anim_swapper,
    anim_poser,
    anim_selection_sets,
    anim_modifiers,
    register_keymaps,
    classes as amp_classes,
    anim_visual_aid,
)


class TIMELINE_scene_properties(PropertyGroup):
    anim_offset: PointerProperty(type=anim_offset.props.AMP_AnimOffset)


addon_modules = [
    preferences,
    operators,
    utils,
    anim_modifiers,
    ui,
    amp_classes,
    anim_swapper,
    addon_ui,
    properties,
    anim_curves,
    anim_offset,
    autoKeying,
    anim_slicer,
    markers_tools,
    anim_sculpt,
    anim_shifter,
    anim_euler,
    anim_scrub,
    anim_retimer,
    anim_keyframer,
    anim_looper,
    anim_baker,
    anim_mopaths,
    anim_selection_sets,
    anim_timewarper,
    anim_timeblocker,
    anim_nudger,
    anim_lattice,
    anim_poser,
    register_keymaps,
    anim_visual_aid,
    blender_ui,
    addon_ui_default_top_panels,
    customIcons,
]

if FORGE_VERSION:
    from . import forge_modules

    addon_modules.extend(forge_modules.modules)


@persistent
def load_post_handler(scene):
    utils.remove_message()
    utils.dprint("Initializing AniMate Pro")


def register():

    for module in addon_modules:
        module.register()

    register_class(TIMELINE_scene_properties)
    load_post.append(load_post_handler)
    Scene.amp_timeline_tools = PointerProperty(type=TIMELINE_scene_properties)
    prefs = get_prefs()
    prefs.forge_version = FORGE_VERSION


def unregister():
    del Scene.amp_timeline_tools
    load_post.remove(load_post_handler)
    unregister_class(TIMELINE_scene_properties)

    for module in reversed(addon_modules):
        try:
            module.unregister()
        except AttributeError:
            pass


if __name__ == "__main__":
    register()

#############
## init.py ##
#############
