import bpy
import rna_keymap_ui
from . import __package__ as base_package
from . import changelog
from .keymaps import (
    key_all_scrub,
    key_all_scrub_off,
    key_editors_jump_to_first_kyeframe_LMBrelease,
    key_editors_jump_to_first_kyeframe_LMBrelease_off,
    key_editors_jump_to_first_kyeframe_ctrlGpress,
    key_editors_jump_to_first_kyeframe_ctrlGpress_off,
    key_graph_anim_tools,
    key_graph_anim_tools_off,
    key_graph_dope_select_fcurves,
    key_graph_dope_select_fcurves_off,
    # key_graph_editor_lock_transforms,
    key_all_insert_keyframes,
    key_all_insert_keyframes_off,
    key_all_world_transforms,
    key_all_world_transforms_off,
    key_all_autokeying,
    key_all_autokeying_off,
    key_graph_editor_isolate_curves,
    key_graph_editor_isolate_curves_off,
    key_graph_editor_zoom_curves,
    key_graph_editor_zoom_curves_off,
)


def graph_editor_jump_to_keyframe_kmi_active_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.graph_editor_jump_to_keyframe_kmi_active:
        key_editors_jump_to_first_kyeframe_LMBrelease_off.unregister()
        key_editors_jump_to_first_kyeframe_LMBrelease.register()
    else:
        key_editors_jump_to_first_kyeframe_LMBrelease.unregister()
        key_editors_jump_to_first_kyeframe_LMBrelease_off.register()


def scrub_timeline_kmi_active_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.scrub_timeline_keymap_kmi_active:
        key_all_scrub_off.unregister()
        key_all_scrub.register()
    else:
        key_all_scrub.unregister()
        key_all_scrub_off.register()


def graph_editor_jump_to_keyframe_ctrl_g_kmi_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.graph_editor_jump_to_keyframe_ctrl_g_kmi_active:
        key_editors_jump_to_first_kyeframe_ctrlGpress_off.unregister()
        key_editors_jump_to_first_kyeframe_ctrlGpress.register()
    else:
        key_editors_jump_to_first_kyeframe_ctrlGpress.unregister()
        key_editors_jump_to_first_kyeframe_ctrlGpress_off.register()


def key_graph_dope_select_fcurves_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.graph_dope_select_fcurves_kmi_active:
        key_graph_dope_select_fcurves_off.unregister()
        key_graph_dope_select_fcurves.register()
    else:
        key_graph_dope_select_fcurves.unregister()
        key_graph_dope_select_fcurves_off.register()


def key_all_insert_keyframes_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.all_insert_keyframes_kmi_active:
        key_all_insert_keyframes_off.unregister()
        key_all_insert_keyframes.register()
    else:
        key_all_insert_keyframes.unregister()
        key_all_insert_keyframes_off.register()


def key_all_world_transforms_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.all_world_transforms_kmi_active:
        key_all_world_transforms_off.unregister()
        key_all_world_transforms.register()
    else:
        key_all_world_transforms.unregister()
        key_all_world_transforms_off.register()


def key_graph_anim_tools_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.graph_anim_tools_kmi_active:
        key_graph_anim_tools_off.unregister()
        key_graph_anim_tools.register()
    else:
        key_graph_anim_tools.unregister()
        key_graph_anim_tools_off.register()


def key_all_autokeying_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.all_autokeying_kmi_active:
        key_all_autokeying_off.unregister()
        key_all_autokeying.register()
    else:
        key_all_autokeying.unregister()
        key_all_autokeying_off.register()


def key_graph_editor_isolate_curves_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.graph_editor_isolate_curves_kmi_active:
        key_graph_editor_isolate_curves_off.unregister()
        key_graph_editor_isolate_curves.register()
    else:
        key_graph_editor_isolate_curves.unregister()
        key_graph_editor_isolate_curves_off.register()


def key_graph_editor_zoom_curves_toggle(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.graph_editor_zoom_curves_kmi_active:
        key_graph_editor_zoom_curves_off.unregister()
        key_graph_editor_zoom_curves.register()
    else:
        key_graph_editor_zoom_curves.unregister()
        key_graph_editor_zoom_curves_off.register()


def draw_keymap(layout, context, keymap_name, editor_name, operator_name, extra_func=None):
    """
    Draw the main keymap and detect/draw any conflicts.
    Optionally draw additional keymaps using the provided extra_func.
    """
    box = layout.box()
    box.label(text=keymap_name)

    # Draw the main keymap entry
    draw_rna_keymap(box, context, keymap_name, editor_name, operator_name)

    row = box.row()
    col1 = row.column()
    col1.label(text="", icon="BLANK1")
    col2 = row.column()

    # Draw any conflicts
    draw_conflicts(col2, context, keymap_name, editor_name, operator_name)

    # If extra_func is provided, call it with layout and context
    if extra_func:
        extra_func(col2, context)

    layout.separator(factor=2)


def draw_rna_keymap(layout, context, keymap_name, editor_name, operator_name):
    """
    Draw the main keymap entry using Blender's rna_keymap_ui.
    """
    wm = context.window_manager
    kc = wm.keyconfigs.user

    if not kc:
        layout.label(text="No user key configuration found.", icon="ERROR")
        return

    # Locate the keymap and operator
    for km in kc.keymaps:
        if km.name != editor_name:
            continue

        for kmi in km.keymap_items:
            if kmi.idname == operator_name:
                row = layout.row()
                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, row, 0)


def draw_rna_conflict(layout, context, keymap_name, operator_name):
    """
    Draw the keymap entry using Blender's rna_keymap_ui.
    """
    wm = context.window_manager
    kc = wm.keyconfigs.user

    # Locate the keymap and operator
    for km in kc.keymaps:
        if km.name == keymap_name:
            for kmi in km.keymap_items:
                if kmi.idname == operator_name:
                    sub_box = layout.box()
                    row = sub_box.row()
                    rna_keymap_ui.draw_kmi([], kc, km, kmi, row, 0)
                    return


def draw_conflicts(layout, context, keymap_name, editor_name, operator_name):
    wm = context.window_manager
    kc = wm.keyconfigs.user

    if not kc:
        layout.label(text="No user key configuration found.", icon="ERROR")
        return

    # Locate all keymap items for the operator in the specific editor
    found_kmis = []
    found_kms = []

    for km in kc.keymaps:
        if km.name != editor_name:
            continue

        for kmi in km.keymap_items:
            if kmi.idname == operator_name:
                found_kmis.append(kmi)
                found_kms.append(km)

    if not found_kmis:
        layout.label(text="Operator keymap not found.", icon="ERROR")
        return  # No keymap entries found to check for conflicts

    if found_kmis:

        # For each found_kmi, detect conflicts
        for found_kmi, found_km in zip(found_kmis, found_kms):
            conflicting_keymaps = detect_conflicts_for_keymap_item(wm, found_km, found_kmi)

            if conflicting_keymaps:
                conflict_container = layout.column()
                row = conflict_container.row()
                conflic_icon = (
                    "DOWNARROW_HLT"
                    if changelog.panels_visibility.get(str(keymap_name + editor_name + operator_name), False)
                    else "ERROR"
                )
                op = row.operator(
                    "ui.amp_toggle_panels_visibility",
                    text="Potential Keymap Conflicts",
                    icon=conflic_icon,
                )
                op.version = str(keymap_name + editor_name + operator_name)
                # row.label(text=f"Potential Keymap Conflicts")
                if changelog.panels_visibility.get(str(keymap_name + editor_name + operator_name), False):
                    for conflict in conflicting_keymaps:
                        draw_rna_conflict(
                            conflict_container,
                            context,
                            keymap_name=conflict["keymap_name"],
                            operator_name=conflict["operator_name"],
                        )


def detect_conflicts_for_keymap_item(wm, found_km, found_kmi):
    """
    Detect conflicts for a given KeyMapItem, considering keymaps with the same name,
    or all keymaps if the found keymap is global ('Window').
    """
    key_combo = {
        "type": found_kmi.type,
        "value": found_kmi.value,
        "ctrl": found_kmi.ctrl,
        "alt": found_kmi.alt,
        "shift": found_kmi.shift,
        "oskey": found_kmi.oskey,
        "key_modifier": found_kmi.key_modifier,
    }

    conflicting_keymaps = []
    conflict_identifiers = set()

    is_global = found_km.name == "Window"

    for kc in wm.keyconfigs:
        for km in kc.keymaps:
            matches_space = km.space_type == found_km.space_type
            matches_region = km.region_type == found_km.region_type
            matches_modal = km.is_modal == found_km.is_modal

            # If our keymap is global, we compare with all keymaps
            # Otherwise, we compare only with keymaps of the same name
            matches_name = True if is_global else km.name == found_km.name

            # Skip non-matching keymaps
            if not (matches_space and matches_region and matches_modal and matches_name):
                continue

            for kmi in km.keymap_items:
                if kmi == found_kmi:  # Skip the original keymap item
                    continue

                # Check if the key combination matches
                if (
                    kmi.type == key_combo["type"]
                    and kmi.value == key_combo["value"]
                    and kmi.ctrl == key_combo["ctrl"]
                    and kmi.alt == key_combo["alt"]
                    and kmi.shift == key_combo["shift"]
                    and kmi.oskey == key_combo["oskey"]
                    and kmi.key_modifier == key_combo["key_modifier"]
                ):
                    # Ignore conflicts with the same operator
                    if kmi.idname != found_kmi.idname:
                        conflict_id = f"{km.name}_{kmi.idname}"
                        if conflict_id not in conflict_identifiers:
                            conflict_identifiers.add(conflict_id)
                            conflicting_keymaps.append(
                                {
                                    "type": kmi.type,
                                    "keymap_name": km.name,
                                    "operator_name": kmi.idname,
                                    "keymap_item": kmi,
                                }
                            )
    return conflicting_keymaps


addon_keymaps = [
    key_all_scrub,
    key_editors_jump_to_first_kyeframe_LMBrelease,
    key_editors_jump_to_first_kyeframe_ctrlGpress,
    key_graph_dope_select_fcurves,
    key_all_insert_keyframes,
    key_all_world_transforms,
    key_graph_anim_tools,
    key_all_autokeying,
    key_graph_editor_isolate_curves,
    key_graph_editor_zoom_curves,
]


def register():
    # Register keymaps
    graph_editor_jump_to_keyframe_kmi_active_toggle(None, bpy.context)
    scrub_timeline_kmi_active_toggle(None, bpy.context)
    graph_editor_jump_to_keyframe_ctrl_g_kmi_toggle(None, bpy.context)
    key_graph_dope_select_fcurves_toggle(None, bpy.context)
    key_all_insert_keyframes_toggle(None, bpy.context)
    key_all_world_transforms_toggle(None, bpy.context)
    key_graph_anim_tools_toggle(None, bpy.context)
    key_all_autokeying_toggle(None, bpy.context)
    key_graph_editor_isolate_curves_toggle(None, bpy.context)
    key_graph_editor_zoom_curves_toggle(None, bpy.context)


def unregister():
    # Unregister keymaps
    for keymap in addon_keymaps:
        try:
            keymap.unregister()
        except AttributeError as e:
            print(f"Error unregistering keymap {keymap}: {e}")
            pass
