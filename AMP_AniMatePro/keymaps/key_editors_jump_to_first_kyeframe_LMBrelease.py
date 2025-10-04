# key_editor_LMB.py
# Key maps for the Timeline Tools addon

import bpy
from .keymaps_utils import toggle_keymaps, unregister_keymaps, register_keymaps


keymaps_to_toggle = [
    # (Keymap area, operator_idname, event_type, event_value, {modifiers}, {properties})
]

keymaps_to_register_framejump = [
    # (Keymap area, operator_idname, event_type, event_value, {modifiers}, {properties})
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_jump_to_keyframe_tracking",
        "type": "LEFTMOUSE",
        "event_value": {"value": "RELEASE"},
        "modifiers": {},
        "properties": {},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_jump_to_keyframe_tracking",
        "type": "LEFTMOUSE",
        "event_value": {"value": "RELEASE"},
        "modifiers": {},
        "properties": {},
    },
]


def register():
    # toggle_keymaps(keymaps_to_toggle, False)
    register_keymaps(keymaps_to_register_framejump)


def unregister():
    unregister_keymaps(keymaps_to_register_framejump)
    # toggle_keymaps(keymaps_to_toggle, True)


if __name__ == "__main__":
    register()
