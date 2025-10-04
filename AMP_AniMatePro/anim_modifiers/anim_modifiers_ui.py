"""
AniMate Pro - Animation Modifiers UI

This module provides UI components for the animation modifiers system.

UI Components:
- Modifier groups list
- Group management buttons
- Modifier management buttons
- Main draw function for integration
"""

import bpy
from bpy.types import UIList, Panel
from .anim_modifiers import (
    get_modifier_groups,
    get_current_action_groups,
    get_active_modifier_group,
    get_editing_modifier_group,
    get_anim_modifiers_settings,
    get_group_animation_name,
    get_smart_frame_range,
    get_animation_slot_layer_info,
    get_first_group_modifier,
    sync_group_visibility_from_modifiers,
    ModifierType,
)


# ============================================================================
# UI LISTS
# ============================================================================


class AMP_UL_modifier_groups(UIList):
    """UI list for modifier groups."""

    def filter_items(self, context, data, propname):
        """Filter items to show groups for actions from all selected objects and their slots."""
        groups = getattr(data, propname)

        # Get all action names from selected objects (including all slot contexts)
        relevant_action_names = set()

        # Check all selected objects
        selected_objects = context.selected_objects if context.selected_objects else []

        # Also include the active object if it's not in selected objects
        if context.object and context.object not in selected_objects:
            selected_objects = [context.object] + list(selected_objects)

        for obj in selected_objects:
            if obj and obj.animation_data and obj.animation_data.action:
                action = obj.animation_data.action
                relevant_action_names.add(action.name)

                # For slotted actions, we want to show groups for all slots of this action
                # Since the action name is the same across all slots, we just need the action name
                # The slot-aware functions will handle filtering during selection

        # If no selected objects with actions, fall back to active object only
        if not relevant_action_names and context.object:
            if context.object.animation_data and context.object.animation_data.action:
                relevant_action_names.add(context.object.animation_data.action.name)

        # Filter groups by relevant actions
        filtered = []
        for i, group in enumerate(groups):
            if group.action_name in relevant_action_names:
                filtered.append(self.bitflag_filter_item)
            else:
                filtered.append(0)  # Hide this item

        return filtered, []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        """Draw a modifier group item."""
        group = item

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            # Visibility toggle button (eye icon)
            eye_icon = "HIDE_OFF" if group.visible else "HIDE_ON"
            row.prop(group, "visible", text="", icon=eye_icon, emboss=False)

            # Select F-curves button
            select_op = row.operator("anim.amp_select_group_fcurves", text="", icon="RESTRICT_SELECT_OFF", emboss=True)
            select_op.group_name = group.name  # Pass the specific group name

            # Modifier type icon (based on type)
            type_icons = {
                "FNGENERATOR": "FCURVE",
                "CYCLES": "MODIFIER",
                "NOISE": "FORCE_TURBULENCE",
                "LIMITS": "CON_DISTLIMIT",
                "STEPPED": "IPO_CONSTANT",
            }
            icon = type_icons.get(group.modifier_type, "MODIFIER")
            row.label(text="", icon=icon)

            # Group name (editable)
            row.prop(group, "name", text="", emboss=False)

            # Modifier count
            modifier_count = len(group.modifier_references)
            row.label(text=f"({modifier_count})")

            # Edit status indicator (no button)
            if group.is_editing:
                row.label(text="", icon="REC")  # Recording icon to show editing
            else:
                row.label(text="", icon="RADIOBUT_OFF")  # Empty circle when not editing

        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=group.name)


# ============================================================================
# MAIN DRAW FUNCTION
# ============================================================================


def draw_anim_modifiers_panel(layout, context):
    """
    Main draw function for the animation modifiers panel.

    This function can be integrated into any panel by calling it with
    the panel's layout and context.
    """

    # Check if we have an active object first
    if not context.object:
        layout.label(text="No active object", icon="INFO")
        layout.label(text="Select an object to use modifier groups")
        return

    # Check if object has animation data
    if not context.object.animation_data:
        layout.label(text="No animation data", icon="INFO")
        layout.label(text="Add keyframes or create an action first")
        return

    # Use our debug function instead of direct access
    settings = get_anim_modifiers_settings(context)
    groups = settings.modifier_groups

    # Check if we have an active action
    has_action = context.object.animation_data.action
    if not has_action:
        layout.label(text="No active action", icon="INFO")
        layout.label(text="Create or select an action to use modifier groups")
        return

    # Show current action info and selected objects info
    selected_objects = context.selected_objects if context.selected_objects else []
    if context.object and context.object not in selected_objects:
        selected_objects = [context.object] + list(selected_objects)

    # Show info about selected objects with actions
    objects_with_actions = []
    for obj in selected_objects:
        if obj and obj.animation_data and obj.animation_data.action:
            objects_with_actions.append(obj)

    if len(objects_with_actions) > 1:
        # Multiple objects selected
        action_row = layout.row()
        action_row.label(text=f"Selected Objects: {len(objects_with_actions)} with actions", icon="OBJECT_DATA")

        # Show a condensed list of objects and their actions
        info_box = layout.box()
        info_col = info_box.column()
        info_col.scale_y = 0.8
        for obj in objects_with_actions[:3]:  # Show first 3 objects
            obj_row = info_col.row()
            obj_row.label(text=f"• {obj.name}: {obj.animation_data.action.name}", icon="ACTION")
        if len(objects_with_actions) > 3:
            info_col.label(text=f"... and {len(objects_with_actions) - 3} more")
    else:
        # Single object (original behavior)
        action_name = context.object.animation_data.action.name
        action_row = layout.row()
        action_row.label(text=f"Action: {action_name}", icon="ACTION")

    # Get groups for all selected objects' actions (this will now use the enhanced filter)
    # The filter_items method will handle showing groups from all relevant actions
    all_relevant_groups = []
    relevant_action_names = set()

    for obj in objects_with_actions:
        if obj.animation_data and obj.animation_data.action:
            relevant_action_names.add(obj.animation_data.action.name)

    # Get groups for all relevant actions
    for group in settings.modifier_groups:
        if group.action_name in relevant_action_names:
            all_relevant_groups.append(group)

    # Check if we have any groups for the selected objects' actions
    if not all_relevant_groups:
        info_box = layout.box()
        info_col = info_box.column()
        info_col.label(text="No modifier groups for this action", icon="INFO")

        # Check if we have selected F-curves to provide helpful message
        if context.selected_editable_fcurves:
            info_col.label(text=f"Selected F-curves: {len(context.selected_editable_fcurves)}")
            add_row = info_col.row()
            add_row.operator("anim.amp_add_modifier_group", text="Add Modifier Group", icon="ADD")
            add_row.operator("anim.amp_refresh_modifier_groups", text="", icon="FILE_REFRESH")
        else:
            info_col.label(text="Select F-curves in the Graph Editor first")
            info_col.label(text="Then add a modifier group")
        return

    # Check if we have selected F-curves for adding modifiers
    has_selected_fcurves = bool(context.selected_editable_fcurves)
    if not has_selected_fcurves:
        warning_box = layout.box()
        warning_col = warning_box.column()
        warning_col.label(text="No F-curves selected", icon="INFO")
        warning_col.label(text="Select F-curves in Graph Editor to add modifiers")

    # Display any warnings from modifier group operations
    if hasattr(context.window_manager, "amp_modifier_warning") and context.window_manager.amp_modifier_warning:
        warning_box = layout.box()
        warning_col = warning_box.column()
        warning_col.alert = True  # Make it visually prominent
        warning_col.label(text="Modifier Group Warning:", icon="ERROR")

        # Split long warning messages into multiple lines for better readability
        warning_text = context.window_manager.amp_modifier_warning
        if len(warning_text) > 50:
            lines = warning_text.split("\n")
            for line in lines:
                if len(line) > 50:
                    # Split long lines at word boundaries
                    words = line.split(" ")
                    current_line = ""
                    for word in words:
                        if len(current_line + word) > 50 and current_line:
                            warning_col.label(text=current_line.strip())
                            current_line = word + " "
                        else:
                            current_line += word + " "
                    if current_line.strip():
                        warning_col.label(text=current_line.strip())
                else:
                    warning_col.label(text=line)
        else:
            warning_col.label(text=warning_text)

        # Add a button to clear the warning
        clear_op = warning_col.operator("wm.context_set_string", text="Clear Warning", icon="X")
        clear_op.data_path = "window_manager.amp_modifier_warning"
        clear_op.value = ""

    # Groups list
    list_row = layout.row()
    list_row.template_list(
        "AMP_UL_modifier_groups", "", settings, "modifier_groups", settings, "active_group_index", rows=4
    )

    # List controls
    list_controls = list_row.column(align=True)
    list_controls.operator("anim.amp_add_modifier_group", text="", icon="ADD")
    remove_op = list_controls.operator("anim.amp_remove_modifier_group", text="", icon="REMOVE")
    apply_op = list_controls.operator("anim.amp_apply_modifier_group", text="", icon="CHECKMARK")
    list_controls.separator()

    # Copy/Paste controls as icons
    copy_op = list_controls.operator("anim.amp_copy_modifier_group_settings", text="", icon="COPYDOWN")
    paste_op = list_controls.operator("anim.amp_paste_modifier_group_settings", text="", icon="PASTEDOWN")
    list_controls.separator()

    # Refresh and clear controls
    refresh_op = list_controls.operator("anim.amp_refresh_modifier_groups", text="", icon="FILE_REFRESH")
    clear_op = list_controls.operator("anim.amp_clear_orphaned_amp_modifiers", text="", icon="TRASH")
    list_controls.separator()

    list_controls.operator("anim.amp_move_modifier_group", text="", icon="TRIA_UP").direction = "UP"
    list_controls.operator("anim.amp_move_modifier_group", text="", icon="TRIA_DOWN").direction = "DOWN"

    # Active group controls - use current action groups
    active_group = get_active_modifier_group(context)
    if active_group:

        # Group properties box
        group_box = layout.box()
        group_col = group_box.column()

        # Group name and type
        name_row = group_col.row()
        name_row.prop(active_group, "name", text="Name")

        type_row = group_col.row()
        type_row.label(text="Type:")
        type_row.label(text=ModifierType.get_display_name(active_group.modifier_type))

        # Animation name (if available)
        animation_name = get_group_animation_name(context, active_group)
        action_row = group_col.row()
        action_row.label(text="Animation:")
        action_row.label(text=animation_name)

        # Slot and layer info for Blender 4.4+
        slot_info, layer_info = get_animation_slot_layer_info(context)
        if slot_info and layer_info:
            slot_row = group_col.row()
            slot_row.label(text="Slot:")
            slot_row.label(text=slot_info)

            layer_row = group_col.row()
            layer_row.label(text="Layer:")
            layer_row.label(text=layer_info)

        # Frame range display
        frame_row = group_col.row(align=True)
        frame_row.label(text="Frame Range:")
        frame_row.label(text=f"{active_group.main_start_frame:.0f} - {active_group.main_end_frame:.0f}")

        # Modifier count
        modifier_count = len(active_group.modifier_references)
        count_row = group_col.row()
        count_row.label(text="Modifiers:")
        count_row.label(text=str(modifier_count))
        # Action buttons
        actions_box = layout.box()
        actions_col = actions_box.column(align=True)

        # Edit button
        edit_row = actions_col.row()
        if active_group.is_editing:
            edit_row.operator("anim.amp_edit_modifier_group", text="Stop Editing", icon="PAUSE")
        else:
            edit_row.operator("anim.amp_edit_modifier_group", text="Edit Group", icon="PLAY")

        # Individual group refresh button
        refresh_single_op = edit_row.operator("anim.amp_refresh_single_modifier_group", text="", icon="FILE_REFRESH")
        refresh_single_op.group_name = active_group.name

        actions_col.separator()

        # Group management
        group_row = actions_col.row(align=True)
        group_row.operator("anim.amp_apply_modifier_group", text="Apply Group", icon="CHECKMARK")

        actions_col.separator()

        # Modifier management
        mod_row = actions_col.row(align=True)
        mod_row.operator("anim.amp_add_modifiers_to_group", text="Add F-curves", icon="ADD")
        mod_row.operator("anim.amp_remove_modifiers_from_group", text="Remove F-curves", icon="REMOVE")

        # Warning if editing another group
        editing_group = get_editing_modifier_group(context)
        if editing_group and editing_group != active_group:
            warning_box = layout.box()
            warning_col = warning_box.column()
            warning_col.label(text=f"Currently editing: {editing_group.name}", icon="INFO")
            warning_col.label(text="Stop editing to edit another group")

        # Modifier Properties (centralized controls)
        if modifier_count > 0:
            props_box = layout.box()
            props_col = props_box.column()
            props_col.label(text="Modifier Properties", icon="PROPERTIES")

            # Get the first modifier as reference
            first_modifier = get_first_group_modifier(context, active_group)
            is_editing = active_group.is_editing

            if first_modifier:
                # Enable/disable based on edit mode
                props_col.enabled = is_editing

                # Randomization properties (always available)
                random_col = props_col.column()
                random_col.enabled = True  # Always enabled
                random_col.label(text="Randomization:")

                rand_row = random_col.row(align=True)
                rand_row.prop(active_group, "random_offset", text="Random Offset")
                rand_row = random_col.row(align=True)
                rand_row.prop(active_group, "random_phase", text="Random Phase")
                rand_row = random_col.row(align=True)
                rand_row.prop(active_group, "random_blend", text="Random Blend")
                rand_row = random_col.row(align=True)
                rand_row.prop(active_group, "random_range", text="Random Range")

                # Show properties based on modifier type
                if active_group.modifier_type == ModifierType.NOISE:
                    if hasattr(first_modifier, "blend_type"):
                        props_col.prop(first_modifier, "blend_type", text="Blend Type")
                    if hasattr(first_modifier, "scale"):
                        props_col.prop(first_modifier, "scale", text="Scale")
                    if hasattr(first_modifier, "strength"):
                        props_col.prop(first_modifier, "strength", text="Strength")
                    if hasattr(first_modifier, "offset"):
                        props_col.prop(first_modifier, "offset", text="Offset")
                    if hasattr(first_modifier, "phase"):
                        props_col.prop(first_modifier, "phase", text="Phase")
                    if hasattr(first_modifier, "depth"):
                        props_col.prop(first_modifier, "depth", text="Depth")
                    if hasattr(first_modifier, "lacunarity"):
                        props_col.prop(first_modifier, "lacunarity", text="Lacunarity")
                    if hasattr(first_modifier, "roughness"):
                        props_col.prop(first_modifier, "roughness", text="Roughness")

                elif active_group.modifier_type == ModifierType.FNGENERATOR:
                    if hasattr(first_modifier, "function_type"):
                        props_col.prop(first_modifier, "function_type", text="Function Type")
                    if hasattr(first_modifier, "use_additive"):
                        props_col.prop(first_modifier, "use_additive", text="Additive")
                    if hasattr(first_modifier, "amplitude"):
                        props_col.prop(first_modifier, "amplitude", text="Amplitude")
                    if hasattr(first_modifier, "phase_multiplier"):
                        props_col.prop(first_modifier, "phase_multiplier", text="Phase Multiplier")
                    if hasattr(first_modifier, "phase_offset"):
                        props_col.prop(first_modifier, "phase_offset", text="Phase Offset")
                    if hasattr(first_modifier, "value_offset"):
                        props_col.prop(first_modifier, "value_offset", text="Value Offset")

                elif active_group.modifier_type == ModifierType.CYCLES:
                    if hasattr(first_modifier, "mode_before"):
                        props_col.prop(first_modifier, "mode_before", text="Mode Before")
                    if hasattr(first_modifier, "cycles_before"):
                        props_col.prop(first_modifier, "cycles_before", text="Cycles Before")
                    if hasattr(first_modifier, "mode_after"):
                        props_col.prop(first_modifier, "mode_after", text="Mode After")
                    if hasattr(first_modifier, "cycles_after"):
                        props_col.prop(first_modifier, "cycles_after", text="Cycles After")

                elif active_group.modifier_type == ModifierType.LIMITS:
                    if hasattr(first_modifier, "use_min_x"):
                        props_col.prop(first_modifier, "use_min_x", text="Use Min X")
                    if hasattr(first_modifier, "min_x"):
                        row = props_col.row()
                        row.prop(first_modifier, "min_x", text="Min X")
                        row.enabled = getattr(first_modifier, "use_min_x", False)
                    if hasattr(first_modifier, "use_min_y"):
                        props_col.prop(first_modifier, "use_min_y", text="Use Min Y")
                    if hasattr(first_modifier, "min_y"):
                        row = props_col.row()
                        row.prop(first_modifier, "min_y", text="Min Y")
                        row.enabled = getattr(first_modifier, "use_min_y", False)

                elif active_group.modifier_type == ModifierType.STEPPED:
                    if hasattr(first_modifier, "frame_step"):
                        props_col.prop(first_modifier, "frame_step", text="Frame Step")
                    if hasattr(first_modifier, "frame_offset"):
                        props_col.prop(first_modifier, "frame_offset", text="Frame Offset")
                    if hasattr(first_modifier, "use_frame_start"):
                        props_col.prop(first_modifier, "use_frame_start", text="Use Frame Start")
                    if hasattr(first_modifier, "frame_start"):
                        row = props_col.row()
                        row.prop(first_modifier, "frame_start", text="Frame Start")
                        row.enabled = getattr(first_modifier, "use_frame_start", False)
                    if hasattr(first_modifier, "use_frame_end"):
                        props_col.prop(first_modifier, "use_frame_end", text="Use Frame End")
                    if hasattr(first_modifier, "frame_end"):
                        row = props_col.row()
                        row.prop(first_modifier, "frame_end", text="Frame End")
                        row.enabled = getattr(first_modifier, "use_frame_end", False)

                # Sync button
                if is_editing:
                    sync_row = props_col.row()
                    sync_row.operator(
                        "anim.amp_sync_modifier_properties", text="Sync Properties to All", icon="FILE_REFRESH"
                    )
            else:
                props_col.label(text="No modifiers found", icon="ERROR")

    else:
        # We have groups but no active group for current action
        if all_relevant_groups:
            info_box = layout.box()
            info_col = info_box.column()
            info_col.label(text="Please select a modifier group from the list", icon="INFO")

    # # Context info
    # layout.separator()
    # info_box = layout.box()
    # info_col = info_box.column()
    # info_col.label(text="Info:", icon="QUESTION")

    # # Show current context
    # if context.space_data and context.space_data.type == "GRAPH_EDITOR":
    #     if context.selected_editable_fcurves:
    #         fcurve_count = len(context.selected_editable_fcurves)
    #         info_col.label(text=f"Selected F-curves: {fcurve_count}")

    #         # Show selected keyframes info
    #         selected_keyframes = 0
    #         for fcurve in context.selected_editable_fcurves:
    #             for keyframe in fcurve.keyframe_points:
    #                 if keyframe.select_control_point:
    #                     selected_keyframes += 1

    #         if selected_keyframes > 0:
    #             info_col.label(text=f"Selected keyframes: {selected_keyframes}")
    #             info_col.label(text="→ Frame range will auto-detect")
    #         else:
    #             info_col.label(text="→ Will use full F-curve range")
    #     else:
    #         info_col.label(text="No F-curves selected")
    #         info_col.label(text="→ Will use scene frame range")
    # else:
    #     info_col.label(text="Switch to Graph Editor for full functionality")

    # # Usage instructions
    # usage_col = info_col.column(align=True)
    # usage_col.scale_y = 0.8
    # usage_col.label(text="1. Select F-curves and keyframes (optional)")
    # usage_col.label(text="2. Add modifier group (auto-assigns to selection)")
    # usage_col.label(text="3. Frame range auto-detected from keyframes")
    # usage_col.label(text="4. Click Edit in list to modify with GUI pins")
    # usage_col.label(text="5. Apply group to bake effects permanently")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def draw_modifier_type_menu(layout, context):
    """Draw a menu for selecting modifier types."""
    for modifier_type, display_name, description in ModifierType.get_all_types():
        op = layout.operator("anim.amp_add_modifiers_to_group", text=display_name)
        op.modifier_type = modifier_type


# ============================================================================
# REGISTRATION
# ============================================================================


classes = [
    AMP_UL_modifier_groups,
]


def register():
    """Register UI classes."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister UI classes."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
