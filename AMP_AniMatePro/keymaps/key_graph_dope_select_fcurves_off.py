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


keymaps_to_register_graph_editor = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    ###
    ### TRANSLATION
    ###
    # Press 1 to toggle selection of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift 1 to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press G to toggle selection of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    ###
    ### ROTATION
    ###
    # Press 1 to toggle selection of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift 1 to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press G to toggle selection of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    ###
    ### SCALE
    ###
    # Press 1 to toggle selection of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift 1 to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press G to toggle selection of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "CUSTOMPROPS",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "CUSTOMPROPS",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
]

keymaps_to_register_dopesheet = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    ###
    ### TRANSLATION
    ###
    # Press 1 to toggle selection of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift 1 to toggle visibility of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press G to toggle selection of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "TRANSLATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    ###
    ### ROTATION
    ###
    # Press 1 to toggle selection of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift 1 to toggle visibility of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "TOGGLE_VISIBILITY",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press G to toggle selection of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "ROTATION",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    ###
    ### SCALE
    ###
    # Press 1 to toggle selection of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift 1 to toggle visibility of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    # Press G to toggle selection of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    # Press shift G to toggle visibility of translation fcurves
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "SCALE",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {
            "action_type": "CUSTOMPROPS",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": False,
            "isolate": "EXIT_ISOLATE",
        },
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_toggle_fcurves_selection",
        "type": "F24",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {
            "action_type": "CUSTOMPROPS",
            "extra_options": "DESELECT_ALL",
            "transform_if_selected": True,
            "isolate": "ISOLATE",
        },
    },
]


def register():
    # toggle_keymaps(keymaps_to_toggle, False)
    register_keymaps(keymaps_to_register_graph_editor)
    register_keymaps(keymaps_to_register_dopesheet)


def unregister():
    unregister_keymaps(keymaps_to_register_dopesheet)
    unregister_keymaps(keymaps_to_register_graph_editor)
    # toggle_keymaps(keymaps_to_toggle, True)


if __name__ == "__main__":
    register()
