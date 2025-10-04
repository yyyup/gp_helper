# key_graph_editor_lock_transforms_kmi_active.py
# Key maps for the Timeline Tools addon
# * DEPRECATED - already in Blender since 4.1
# * These keymap is for locking the transformation of the keyframe movements


import bpy
from .keymaps_utils import toggle_keymaps, unregister_keymaps, register_keymaps


keymaps_to_toggle = [
    # (Keymap definition, operator_idname, event_type, {event_value(s)}, {modifiers}, {properties})
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "transform.translate",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "ANY"},
        "modifiers": {},
        "properties": {
            # "use_snap_self": True,
            # "use_snap_edit": True,
            # "use_snap_nonedit": True,
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.select_box",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "ANY"},
        "modifiers": {},
        "properties": {
            # "tweak": True,
            # "include_handles": True,
            # "use_curve_selection": True,
            # "wait_for_input": True,
        },
    },
]

keymaps_to_register = [
    # (Keymap definition, operator_idname, event_type, event_value, modifiers, properties)
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "transform.translate",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "NORTH"},
        "modifiers": {},
        "properties": {
            "constraint_axis": (False, True, False),
            "use_snap_self": True,
            "use_snap_edit": True,
            "use_snap_nonedit": True,
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "transform.translate",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "SOUTH"},
        "modifiers": {},
        "properties": {
            "constraint_axis": (False, True, False),
            "use_snap_self": True,
            "use_snap_edit": True,
            "use_snap_nonedit": True,
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "transform.translate",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "WEST"},
        "modifiers": {},
        "properties": {
            "constraint_axis": (True, False, False),
            "use_snap_self": True,
            "use_snap_edit": True,
            "use_snap_nonedit": True,
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "transform.translate",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "EAST"},
        "modifiers": {},
        "properties": {
            "constraint_axis": (True, False, False),
            "use_snap_self": True,
            "use_snap_edit": True,
            "use_snap_nonedit": True,
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.select_box",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "ANY"},
        "modifiers": {"shift": True},
        "properties": {
            "tweak": True,
            "include_handles": True,
            "use_curve_selection": True,
            "wait_for_input": True,
            "mode": "ADD",
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.select_box",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "ANY"},
        "modifiers": {"oskey": True},
        "properties": {
            "tweak": True,
            "include_handles": True,
            "use_curve_selection": True,
            "wait_for_input": True,
            "mode": "SUB",
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.select_box",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "ANY"},
        "modifiers": {"ctrl": True},
        "properties": {
            "tweak": True,
            "include_handles": True,
            "use_curve_selection": True,
            "wait_for_input": True,
            "mode": "SUB",
        },
    },
    {
        "name": "Graph Editor",
        "space_type": "GRAPH_EDITOR",
        "region_type": "WINDOW",
        "operator_idname": "graph.select_box",
        "type": "LEFTMOUSE",
        "event_value": {"value": "CLICK_DRAG", "direction": "ANY"},
        "modifiers": {},
        "properties": {
            "tweak": True,
            "include_handles": True,
            "use_curve_selection": True,
            "wait_for_input": True,
            "mode": "SET",
        },
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
