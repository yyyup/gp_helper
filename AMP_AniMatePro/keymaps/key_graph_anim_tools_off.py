# key_all_scrub.py
# Key maps for the Timeline Tools addon

import bpy
from .keymaps_utils import toggle_keymaps, unregister_keymaps, register_keymaps


keymaps_to_toggle = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    # {
    #     "name": "Window",
    #     "space_type": "EMPTY",
    #     "region_type": "WINDOW",
    #     "operator_idname": "wm.toolbar",
    #     "type": "SPACE",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    # {
    #     "name": "Window",
    #     "space_type": "EMPTY",
    #     "region_type": "WINDOW",
    #     "operator_idname": "wm.search_menu",
    #     "type": "SPACE",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    # {
    #     "name": "Frames",
    #     "space_type": "EMPTY",
    #     "region_type": "WINDOW",
    #     "operator_idname": "screen.animation_play",
    #     "type": "SPACE",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
]


keymaps_to_register = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_anim_sculpt",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {},
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_anim_lattice",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {},
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_anim_timewarper",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"ctrl": True},
        "properties": {},
    },
]


def register():
    # toggle_keymaps(keymaps_to_toggle, False)
    register_keymaps(keymaps_to_register)


def unregister():
    unregister_keymaps(keymaps_to_register)
    # toggle_keymaps(keymaps_to_toggle, True)


if __name__ == "__main__":
    register()
