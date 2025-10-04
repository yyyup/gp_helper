# keymaps_utils.py
# Keymap utilities for the Timeline Tools addon

import bpy
from .. import utils


def match_keymap_item(kmi, keymap_def):
    # Operator ID and Type match
    if "operator_idname" in keymap_def and kmi.idname != keymap_def["operator_idname"]:
        return (
            False,
            f"Operator ID mismatch: expected '{keymap_def['operator_idname']}', found '{kmi.idname}'",
        )
    if "type" in keymap_def and kmi.type != keymap_def["type"]:
        return (
            False,
            f"Type mismatch: expected '{keymap_def['type']}', found '{kmi.type}'",
        )

    # Event value comparison
    expected_value = keymap_def.get("event_value", {}).get("value", "PRESS")  # Default to 'PRESS'
    if kmi.value != expected_value:
        return (
            False,
            f"Mismatch in value: expected '{expected_value}', found '{kmi.value}'",
        )

    # Handling complex types like tuples for 'constraint_axis'
    if "constraint_axis" in keymap_def.get("properties", {}):
        expected_constraint_axis = tuple(keymap_def["properties"]["constraint_axis"])
        actual_constraint_axis = tuple(getattr(kmi.properties, "constraint_axis", (False, False, False)))
        if actual_constraint_axis != expected_constraint_axis:
            return (
                False,
                f"Mismatch in property constraint_axis: expected '{expected_constraint_axis}', found '{actual_constraint_axis}'",
            )

    # Modifiers comparison, handling boolean conversion
    for modifier in ["shift", "ctrl", "alt", "oskey"]:
        expected_mod_value = keymap_def.get("modifiers", {}).get(modifier, False)
        actual_mod_value = bool(
            getattr(kmi, modifier + "_ui", False)
        )  # Using *_ui properties for actual boolean states
        if actual_mod_value != expected_mod_value:
            return (
                False,
                f"Mismatch in modifier {modifier}: expected '{expected_mod_value}', found '{actual_mod_value}'",
            )

    # Custom properties comparison
    for prop, expected_value in keymap_def.get("properties", {}).items():
        if prop == "constraint_axis":  # Already handled above
            continue
        if isinstance(expected_value, (list, tuple)):
            actual_value = getattr(kmi.properties, prop, None)
            expected_value = tuple(expected_value)  # Ensure tuple comparison
            actual_value = tuple(actual_value) if actual_value else None
        elif actual_value != expected_value:
            return (
                False,
                f"Mismatch in property {prop}: expected '{expected_value}', found '{actual_value}'",
            )

    return True, "Match found"


def register_keymaps(keymaps_list):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        utils.dprint("Addon keyconfig not available.")
        return

    for keymap_def in keymaps_list:
        try:
            km = kc.keymaps.get(keymap_def["name"], None)
            if not km:
                km = kc.keymaps.new(
                    name=keymap_def["name"],
                    space_type=keymap_def.get("space_type", "EMPTY"),
                    region_type=keymap_def.get("region_type", "WINDOW"),
                )
                utils.dprint(f"Created new keymap: {keymap_def['name']}")

            # Check if the keymap item already exists
            exists = False
            for kmi in km.keymap_items:
                match, _ = match_keymap_item(kmi, keymap_def)
                if match:
                    exists = True
                    utils.dprint(f"Keymap item already exists: {keymap_def['operator_idname']} in {keymap_def['name']}")
                    break

            if not exists:
                # Create a new keymap item since it doesn't exist
                kmi = km.keymap_items.new(
                    idname=keymap_def["operator_idname"],
                    type=keymap_def["type"],
                    value=keymap_def["event_value"].get("value", "PRESS"),  # Default to 'PRESS' if not specified
                )

                # Set direction if specified
                if "direction" in keymap_def["event_value"]:
                    kmi.direction = keymap_def["event_value"]["direction"]

                # Setting modifiers
                for modifier, value in keymap_def.get("modifiers", {}).items():
                    setattr(kmi, modifier, value)

                # Setting custom properties
                for prop, value in keymap_def.get("properties", {}).items():
                    if hasattr(kmi.properties, prop):
                        setattr(kmi.properties, prop, value)
                    else:
                        utils.dprint(f"Property {prop} does not exist on {keymap_def['operator_idname']}")

                utils.dprint(f"Registered new keymap item: {keymap_def['operator_idname']} in {keymap_def['name']}")
            else:
                utils.dprint(
                    f"Skipped registering keymap item: {keymap_def['operator_idname']} in {keymap_def['name']} (already exists)"
                )
        except Exception as e:
            pass


def unregister_keymaps(keymaps_list):
    try:
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon
        if not kc:
            utils.dprint("Addon keyconfig not available.")
            return

        for keymap_def in keymaps_list:
            km = kc.keymaps.get(keymap_def["name"], None)
            if km:
                for kmi in km.keymap_items:
                    match, debug_message = match_keymap_item(kmi, keymap_def)
                    if match:
                        utils.dprint(f"Unregistering match: {debug_message}")
                        km.keymap_items.remove(kmi)
                    else:
                        pass
                        # utils.dprint(f"No match for unregister: {debug_message}")
    except Exception as e:
        pass


def toggle_keymaps(keymaps_list, enable):
    wm = bpy.context.window_manager
    # kc = wm.keyconfigs.user  # Consider using 'user' keyconfig to include Blender's defaults

    for keymap_def in keymaps_list:
        try:
            # Attempt to find the keymap in both the addon and the user configurations
            km = wm.keyconfigs.default.keymaps.get(keymap_def["name"], None)

            if km:
                for kmi in km.keymap_items:
                    match, debug_message = match_keymap_item(kmi, keymap_def)
                    if match:

                        kmi.active = enable

                        utils.dprint(f"Toggled '{kmi.idname}' in '{km.name}': {'enabled' if enable else 'disabled'}")
                    else:
                        # This else block might be verbose for debugging and can be removed or commented out for production
                        pass
                        # utils.dprint(f"Skipped '{kmi.idname}' in '{km.name}': {debug_message}")
        except Exception as e:
            pass
