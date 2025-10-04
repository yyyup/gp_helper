# key_all_scrub.py
# Key maps for the Timeline Tools addon

import bpy
from .keymaps_utils import toggle_keymaps, unregister_keymaps, register_keymaps


keymaps_to_toggle = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
]


keymaps_to_register = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    {
        "name": "Window",
        "space_type": "EMPTY",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_copy_world_transforms",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"alt": True},
        "properties": {},
    },
    {
        "name": "Screen",
        "space_type": "EMPTY",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_paste_world_transforms",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"alt": True},
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
