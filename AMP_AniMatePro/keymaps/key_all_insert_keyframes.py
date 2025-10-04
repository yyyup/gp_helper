# key_all_scrub.py
# Key maps for the Timeline Tools addon

import bpy
from .keymaps_utils import toggle_keymaps, unregister_keymaps, register_keymaps


keymaps_to_toggle = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    # {
    #     "name": "Pose",
    #     "space_type": "VIEW_3D",
    #     "region_type": "WINDOW",
    #     "operator_idname": "anim.keyframe_insert",
    #     "type": "I",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    {
        "name": "Pose",
        "space_type": "VIEW_3D",
        "region_type": "WINDOW",
        "operator_idname": "pose.ik_add",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {},
    },
    # {
    #     "name": "Object Mode",
    #     "space_type": "VIEW_3D",
    #     "region_type": "WINDOW",
    #     "operator_idname": "anim.keyframe_insert",
    #     "type": "I",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "action.keyframe_insert",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {},
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.keyframe_insert",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {},
    },
]


keymaps_to_register = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    # {
    #     "name": "3D View",
    #     "space_type": "VIEW_3D",
    #     "region_type": "WINDOW",
    #     "operator_idname": "anim.amp_timeline_insert_keyframe",
    #     "type": "I",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    # {
    #     "name": "3D View",
    #     "space_type": "VIEW_3D",
    #     "region_type": "WINDOW",
    #     "operator_idname": "wm.call_menu",
    #     "type": "I",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {"shift": True},
    #     "properties": {"name": "TIMELINE_MT_dynamic_keyframe_insert_menu"},
    # },
    {
        "name": "3D View",
        "space_type": "VIEW_3D",
        "region_type": "WINDOW",
        "operator_idname": "wm.call_panel",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {"name": "AMP_PT_InsertKeyPreferencesVIEW"},
    },
    {
        "name": "Pose",
        "space_type": "VIEW_3D",
        "region_type": "WINDOW",
        "operator_idname": "wm.call_panel",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {"name": "AMP_PT_InsertKeyPreferencesVIEW"},
    },
    {
        "name": "Object Mode",
        "space_type": "VIEW_3D",
        "region_type": "WINDOW",
        "operator_idname": "wm.call_panel",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {"name": "AMP_PT_InsertKeyPreferencesVIEW"},
    },
    # {
    #     "name": "Pose",
    #     "space_type": "VIEW_3D",
    #     "region_type": "WINDOW",
    #     "operator_idname": "anim.amp_timeline_insert_keyframe",
    #     "type": "I",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    # {
    #     "name": "Object Mode",
    #     "space_type": "VIEW_3D",
    #     "region_type": "WINDOW",
    #     "operator_idname": "anim.amp_timeline_insert_keyframe",
    #     "type": "I",
    #     "event_value": {"value": "PRESS"},
    #     "modifiers": {},
    #     "properties": {},
    # },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_timeline_insert_keyframe",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {},
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "wm.call_panel",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {"name": "AMP_PT_InsertKeyPreferencesGraph"},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "anim.amp_timeline_insert_keyframe",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {},
        "properties": {},
    },
    {
        "name": "Dopesheet",
        "space_type": "DOPESHEET_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "wm.call_panel",
        "type": "I",
        "event_value": {"value": "PRESS"},
        "modifiers": {"shift": True},
        "properties": {"name": "AMP_PT_InsertKeyPreferencesDope"},
    },
]


def register():
    toggle_keymaps(keymaps_to_toggle, False)
    register_keymaps(keymaps_to_register)


def unregister():
    unregister_keymaps(keymaps_to_register)
    toggle_keymaps(keymaps_to_toggle, True)


if __name__ == "__main__":
    register()
