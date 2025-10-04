# key_editor_LMB.py
# Key maps for the Timeline Tools addon

import bpy
from .keymaps_utils import toggle_keymaps, unregister_keymaps, register_keymaps


keymaps_to_toggle = [
    # (Keymap area, operator_idname, event_type, event_value, {modifiers}, {properties})
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.frame_jump",
        "type": "G",
        "event_value": {"value": "PRESS"},
        "modifiers": {"ctrl": True},
        "properties": {},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "action.frame_jump",
        "type": "G",
        "event_value": {"value": "PRESS"},
        "modifiers": {"ctrl": True},
        "properties": {},
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.frame_jump",
        "type": "G",
        "event_value": {"value": "PRESS"},
        "modifiers": {"oskey": True},
        "properties": {},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "action.frame_jump",
        "type": "G",
        "event_value": {"value": "PRESS"},
        "modifiers": {"oskey": True},
        "properties": {},
    },
]

keymaps_to_register_framejump_ctrlG = [
    # (Keymap area, operator_idname, event_type, event_value, {modifiers}, {properties})
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_move_playhead_to_first_selected_keyframe",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"ctrl": True},
        "properties": {},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_move_playhead_to_first_selected_keyframe",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"ctrl": True},
        "properties": {},
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_move_playhead_to_first_selected_keyframe",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"oskey": True},
        "properties": {},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_move_playhead_to_first_selected_keyframe",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"oskey": True},
        "properties": {},
    },
]


def register():
    # toggle_keymaps(keymaps_to_toggle, False)
    register_keymaps(keymaps_to_register_framejump_ctrlG)


def unregister():
    unregister_keymaps(keymaps_to_register_framejump_ctrlG)
    # toggle_keymaps(keymaps_to_toggle, True)


if __name__ == "__main__":
    register()
