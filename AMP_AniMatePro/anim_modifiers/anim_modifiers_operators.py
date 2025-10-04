"""
AniMate Pro - Animation Modifiers Operators

This module provides operators for managing F-curve modifier groups.

Operators:
- Add modifier group
- Remove modifier group
- Edit modifier group (modal with GUI pins)
- Add modifiers to group
- Remove modifiers from group
- Move groups up/down in list
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty
from typing import List, Dict, Optional, Set
from ..utils.gui_pins import ScopeGUI, BlendType
from ..utils import get_prefs


def refresh_ui():
    """Refresh all UI areas to update displays."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        # Fallback if context is not available
        pass


from .anim_modifiers import (
    ModifierType,
    get_modifier_groups,
    get_current_action_groups,
    get_active_modifier_group,
    get_editing_modifier_group,
    get_anim_modifiers_settings,
    ensure_unique_group_name,
    get_fcurve_by_reference,
    get_modifier_by_reference,
    get_all_group_modifiers,
    sync_group_properties_to_modifiers,
    select_group_fcurves,
    ensure_group_fcurves_selected,
    get_smart_frame_range,
    fcurve_has_group_modifier,
    get_group_modifier_name,
    get_first_group_modifier,
    sync_modifier_properties,
    AMP_PG_ModifierReference,
)
from ..utils.curve import all_fcurves


# ============================================================================
# MODIFIER GROUP MANAGEMENT OPERATORS
# ============================================================================


class AMP_OT_add_modifier_group(Operator):
    """Add a new modifier group"""

    bl_idname = "anim.amp_add_modifier_group"
    bl_label = "Add Modifier Group"
    bl_description = "Add a new modifier group with a specific modifier type"
    bl_options = {"REGISTER", "UNDO"}

    modifier_type: EnumProperty(
        name="Modifier Type",
        description="Type of modifier for this group",
        items=ModifierType.get_all_types(),
        default=ModifierType.NOISE,
    )

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        # Require active object with animation data and selected F-curves
        return (
            context.object
            and context.object.animation_data
            and context.object.animation_data.action
            and context.selected_editable_fcurves
        )

    def invoke(self, context, event):
        """Show popup to select modifier type."""
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        """Draw the popup interface with buttons for each modifier type."""
        layout = self.layout
        layout.label(text="Select Modifier Type:", icon="MODIFIER")

        # Create buttons for each modifier type
        col = layout.column(align=False)
        for modifier_type, display_name, description in ModifierType.get_all_types():
            row = col.row()
            op = row.operator("anim.amp_create_modifier_group_with_type", text=display_name, icon="PLUS")
            op.modifier_type = modifier_type
            op.display_name = display_name

    def execute(self, context):
        """This should not be called directly anymore."""
        return {"CANCELLED"}


class AMP_OT_create_modifier_group_with_type(Operator):
    """Create a new modifier group with a specific modifier type"""

    bl_idname = "anim.amp_create_modifier_group_with_type"
    bl_label = "Create Modifier Group"
    bl_description = "Create a new modifier group with the specified type"
    bl_options = {"REGISTER", "UNDO"}

    modifier_type: EnumProperty(
        name="Modifier Type",
        description="Type of modifier for this group",
        items=ModifierType.get_all_types(),
        default=ModifierType.NOISE,
    )

    display_name: StringProperty(
        name="Display Name",
        description="Display name for the modifier type",
        default="",
    )

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        # Same requirements as add modifier group
        return (
            context.object
            and context.object.animation_data
            and context.object.animation_data.action
            and context.selected_editable_fcurves
        )

    def execute(self, context):
        """Execute the operator."""
        if not context.object:
            self.report({"ERROR"}, "No active object")
            return {"CANCELLED"}

        if not context.object.animation_data:
            context.object.animation_data_create()

        # Ensure the settings exist
        settings = get_anim_modifiers_settings(context)
        if not settings:
            self.report(
                {"ERROR"}, "Animation modifiers settings not found. Please enable the AMP Animation Modifiers addon."
            )
            return {"CANCELLED"}

        groups = settings.modifier_groups

        # Create unique name based on modifier type
        base_name = f"{self.display_name} Group"
        unique_name = ensure_unique_group_name(groups, base_name)

        # Add new group
        new_group = groups.add()
        new_group.name = unique_name
        new_group.previous_name = unique_name  # Initialize previous name tracking
        new_group.modifier_type = self.modifier_type

        # Generate unique ID for this group
        from ..anim_modifiers.anim_modifiers import ensure_group_has_unique_id

        group_unique_id = ensure_group_has_unique_id(new_group)

        # Associate with current action
        if context.object.animation_data and context.object.animation_data.action:
            new_group.action_name = context.object.animation_data.action.name

        # Set as active
        settings.active_group_index = len(groups) - 1

        # Get smart frame range (selected keyframes > F-curve range > scene range)
        start_frame, end_frame = get_smart_frame_range(context)

        new_group.main_start_frame = start_frame
        new_group.main_end_frame = end_frame
        new_group.blend_start_frame = start_frame
        new_group.blend_end_frame = end_frame

        # Auto-assign to selected F-curves if any are selected
        modifiers_added = 0
        skipped_duplicates = 0
        if context.selected_editable_fcurves:
            modifier_name = get_group_modifier_name(new_group.name)

            for i, fcurve in enumerate(context.selected_editable_fcurves):

                # Check if this F-curve already has a modifier for this group (using unique ID)
                from ..anim_modifiers.anim_modifiers import fcurve_has_group_modifier_by_group

                if fcurve_has_group_modifier_by_group(fcurve, new_group):
                    skipped_duplicates += 1
                    continue

                # Add the modifier using the group's modifier type
                modifier = fcurve.modifiers.new(type=self.modifier_type)

                # Set the modifier name to the standardized format
                modifier.name = modifier_name

                # Enable frame range restriction by default
                modifier.use_restricted_range = True

                # Create reference (we store unique IDs in the reference system since
                # F-curve modifiers don't support custom properties)
                ref = new_group.modifier_references.add()
                ref.action = context.active_object.animation_data.action  # Store action pointer
                ref.fcurve_data_path = fcurve.data_path
                ref.fcurve_array_index = fcurve.array_index
                ref.modifier_name = modifier.name
                ref.modifier_type = self.modifier_type

                # Generate unique ID for this reference
                from ..anim_modifiers.anim_modifiers import ensure_reference_has_unique_id

                reference_unique_id = ensure_reference_has_unique_id(ref)

                # Store slot reference for cross-version compatibility
                from ..anim_modifiers.anim_modifiers import store_slot_reference

                store_slot_reference(ref, context, fcurve)

                fcurves_list = list(all_fcurves(context.object.animation_data.action))
                try:
                    ref.fcurve_index = fcurves_list.index(fcurve)
                except ValueError:
                    ref.fcurve_index = -1

                modifiers_added += 1

            # Sync properties to all modifiers
            sync_group_properties_to_modifiers(context, new_group)

        # Report creation with info about auto-assignment and duplicates
        if modifiers_added > 0:
            msg = f"Added {self.display_name} modifier group '{unique_name}' with {modifiers_added} modifiers (frames {start_frame:.0f}-{end_frame:.0f})"
            if skipped_duplicates > 0:
                msg += f". Skipped {skipped_duplicates} duplicate F-curves"
            self.report({"INFO"}, msg)
        else:
            self.report(
                {"INFO"},
                f"Added {self.display_name} modifier group '{unique_name}' (frames {start_frame:.0f}-{end_frame:.0f}). Select F-curves and use 'Add to Selected F-curves' to add modifiers.",
            )

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


class AMP_OT_remove_modifier_group(Operator):
    """Remove the active modifier group and all its modifiers from F-curves"""

    bl_idname = "anim.amp_remove_modifier_group"
    bl_label = "Remove Modifier Group"
    bl_description = "Remove the active modifier group and all its modifiers from F-curves"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        # Require active object with animation data and an active group from current action
        if not (context.object and context.object.animation_data and context.object.animation_data.action):
            return False

        settings = get_anim_modifiers_settings(context)
        if not settings or not settings.modifier_groups:
            return False

        # Check if there's an active group for the current action
        active_group = get_active_modifier_group(context)
        return active_group is not None

    def execute(self, context):
        """Execute the operator."""
        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        # Stop editing if this group is being edited
        settings = get_anim_modifiers_settings(context)
        if settings and settings.editing_group_index == settings.active_group_index:
            settings.editing_group_index = -1

        # Remove all modifiers in the group
        modifiers_removed = 0
        for ref in group.modifier_references:
            modifier = get_modifier_by_reference(context, ref)
            if modifier:
                fcurve = get_fcurve_by_reference(context, ref)
                if fcurve:
                    fcurve.modifiers.remove(modifier)
                    modifiers_removed += 1

        group_name = group.name

        # Remove the group
        groups = get_modifier_groups(context)
        groups.remove(settings.active_group_index)

        # Adjust active index
        if settings.active_group_index >= len(groups) and len(groups) > 0:
            settings.active_group_index = len(groups) - 1
        elif len(groups) == 0:
            settings.active_group_index = 0

        self.report({"INFO"}, f"Removed modifier group '{group_name}' and {modifiers_removed} modifiers")

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


class AMP_OT_apply_modifier_group(Operator):
    """Apply all modifiers in the active group and remove the group"""

    bl_idname = "anim.amp_apply_modifier_group"
    bl_label = "Apply Modifier Group"
    bl_description = "Apply all modifiers in the active group to their F-curves and remove the group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        # Require active object with animation data and an active group from current action
        if not (context.object and context.object.animation_data and context.object.animation_data.action):
            return False

        settings = get_anim_modifiers_settings(context)
        if not settings or not settings.modifier_groups:
            return False

        # Check if there's an active group for the current action with modifiers
        active_group = get_active_modifier_group(context)
        return active_group is not None and len(active_group.modifier_references) > 0

    def execute(self, context):
        """Execute the operator."""
        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        # Check if group has any modifiers
        if not group.modifier_references:
            self.report({"WARNING"}, "No modifiers in the active group")
            return {"CANCELLED"}

        # Stop editing if this group is being edited
        settings = get_anim_modifiers_settings(context)
        if settings and settings.editing_group_index == settings.active_group_index:
            settings.editing_group_index = -1

        # Apply all modifiers in the group
        modifiers_applied = 0
        for ref in group.modifier_references:
            fcurve = get_fcurve_by_reference(context, ref)
            modifier = get_modifier_by_reference(context, ref)

            if fcurve and modifier:
                try:
                    # Apply the modifier by baking its effect into the keyframes
                    # Store original keyframe data
                    original_keyframes = []
                    for keyframe in fcurve.keyframe_points:
                        original_keyframes.append((keyframe.co[0], keyframe.co[1]))

                    # Evaluate the curve with modifier and store new values
                    new_values = []
                    for frame, value in original_keyframes:
                        # Evaluate the curve at this frame (includes modifier effects)
                        new_value = fcurve.evaluate(frame)
                        new_values.append((frame, new_value))

                    # Remove the modifier first
                    fcurve.modifiers.remove(modifier)

                    # Update keyframe values with the baked modifier effect
                    for i, (frame, new_value) in enumerate(new_values):
                        if i < len(fcurve.keyframe_points):
                            fcurve.keyframe_points[i].co[1] = new_value

                    # Update the curve
                    fcurve.update()
                    modifiers_applied += 1

                except Exception as e:
                    # Log error but continue with other modifiers
                    print(
                        f"Error applying modifier {ref.modifier_name} to {ref.fcurve_data_path}[{ref.fcurve_array_index}]: {e}"
                    )
                    # Still try to remove the modifier if it exists
                    try:
                        if modifier in fcurve.modifiers:
                            fcurve.modifiers.remove(modifier)
                    except:
                        pass
                    continue

        group_name = group.name

        # Remove the group
        groups = get_modifier_groups(context)
        groups.remove(settings.active_group_index)

        # Adjust active index
        if settings.active_group_index >= len(groups) and len(groups) > 0:
            settings.active_group_index = len(groups) - 1
        elif len(groups) == 0:
            settings.active_group_index = 0

        total_modifiers = len(group.modifier_references)
        if modifiers_applied == total_modifiers:
            self.report({"INFO"}, f"Applied modifier group '{group_name}' with {modifiers_applied} modifiers")
        elif modifiers_applied > 0:
            self.report(
                {"WARNING"},
                f"Applied modifier group '{group_name}': {modifiers_applied}/{total_modifiers} modifiers applied successfully",
            )
        else:
            self.report({"ERROR"}, f"Failed to apply any modifiers from group '{group_name}'")

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


class AMP_OT_move_modifier_group(Operator):
    """Move modifier group up or down in the list"""

    bl_idname = "anim.amp_move_modifier_group"
    bl_label = "Move Modifier Group"
    bl_description = "Move the active modifier group up or down in the list"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        name="Direction",
        description="Direction to move the group",
        items=[
            ("UP", "Up", "Move group up"),
            ("DOWN", "Down", "Move group down"),
        ],
        default="UP",
    )

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        # Require active object with animation data and multiple groups from current action
        if not (context.object and context.object.animation_data and context.object.animation_data.action):
            return False

        settings = get_anim_modifiers_settings(context)
        if not settings or not settings.modifier_groups:
            return False

        # Check if there's an active group for the current action and multiple groups to move
        active_group = get_active_modifier_group(context)
        if not active_group:
            return False

        # Get current action groups to check if we have multiple
        current_action_groups = get_current_action_groups(context)
        return len(current_action_groups) > 1

    def execute(self, context):
        """Execute the operator."""
        settings = get_anim_modifiers_settings(context)
        if not settings:
            return {"CANCELLED"}

        groups = settings.modifier_groups
        if not groups:
            return {"CANCELLED"}

        current_index = settings.active_group_index

        if self.direction == "UP" and current_index > 0:
            groups.move(current_index, current_index - 1)
            settings.active_group_index = current_index - 1
            # Update editing index if needed
            if settings.editing_group_index == current_index:
                settings.editing_group_index = current_index - 1
            elif settings.editing_group_index == current_index - 1:
                settings.editing_group_index = current_index

        elif self.direction == "DOWN" and current_index < len(groups) - 1:
            groups.move(current_index, current_index + 1)
            settings.active_group_index = current_index + 1
            # Update editing index if needed
            if settings.editing_group_index == current_index:
                settings.editing_group_index = current_index + 1
            elif settings.editing_group_index == current_index + 1:
                settings.editing_group_index = current_index

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


# ============================================================================
# MODIFIER MANAGEMENT OPERATORS
# ============================================================================


class AMP_OT_add_modifiers_to_group(Operator):
    """Add modifiers to all selected F-curves in the active group"""

    bl_idname = "anim.amp_add_modifiers_to_group"
    bl_label = "Add Modifiers to Group"
    bl_description = "Add modifiers to all selected F-curves using the group's modifier type"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Execute the operator."""
        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        # Get selected F-curves
        if not context.selected_editable_fcurves:
            self.report({"WARNING"}, "No F-curves selected")
            return {"CANCELLED"}

        modifiers_added = 0
        skipped_duplicates = 0
        modifier_name = get_group_modifier_name(group.name)

        # Ensure the group has a unique ID
        from ..anim_modifiers.anim_modifiers import ensure_group_has_unique_id

        group_unique_id = ensure_group_has_unique_id(group)

        for fcurve in context.selected_editable_fcurves:
            # Check if this F-curve already has a modifier for this group (using group reference)
            from ..anim_modifiers.anim_modifiers import fcurve_has_group_modifier_by_group

            if fcurve_has_group_modifier_by_group(fcurve, group):
                skipped_duplicates += 1
                continue

            # Add the modifier using the group's modifier type
            modifier = fcurve.modifiers.new(type=group.modifier_type)

            # Set the modifier name to the standardized format
            modifier.name = modifier_name

            # Enable frame range restriction by default
            modifier.use_restricted_range = True

            # Create reference (we store unique IDs in the reference system since
            # F-curve modifiers don't support custom properties)
            ref = group.modifier_references.add()
            ref.action = context.active_object.animation_data.action  # Store action pointer
            ref.fcurve_data_path = fcurve.data_path
            ref.fcurve_array_index = fcurve.array_index
            ref.modifier_name = modifier.name
            ref.modifier_type = group.modifier_type

            # Generate unique ID for this reference
            from ..anim_modifiers.anim_modifiers import ensure_reference_has_unique_id

            reference_unique_id = ensure_reference_has_unique_id(ref)

            # Store slot reference for cross-version compatibility
            from ..anim_modifiers.anim_modifiers import store_slot_reference

            store_slot_reference(ref, context, fcurve)

            fcurves_list = list(all_fcurves(context.object.animation_data.action))
            try:
                ref.fcurve_index = fcurves_list.index(fcurve)
            except ValueError:
                ref.fcurve_index = -1

            modifiers_added += 1

        # Sync properties to all modifiers
        sync_group_properties_to_modifiers(context, group)

        modifier_type_name = ModifierType.get_display_name(group.modifier_type)
        msg = f"Added {modifiers_added} {modifier_type_name} modifiers to group '{group.name}'"
        if skipped_duplicates > 0:
            msg += f". Skipped {skipped_duplicates} duplicate F-curves"
        self.report({"INFO"}, msg)

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


class AMP_OT_remove_modifiers_from_group(Operator):
    """Remove selected F-curves' modifiers from the active group"""

    bl_idname = "anim.amp_remove_modifiers_from_group"
    bl_label = "Remove Modifiers from Group"
    bl_description = "Remove modifiers from selected F-curves that belong to the active group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Execute the operator."""
        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        if not context.selected_editable_fcurves:
            self.report({"WARNING"}, "No F-curves selected")
            return {"CANCELLED"}

        modifiers_removed = 0
        refs_to_remove = []

        for fcurve in context.selected_editable_fcurves:
            # Find references for this F-curve
            for i, ref in enumerate(group.modifier_references):
                if ref.fcurve_data_path == fcurve.data_path and ref.fcurve_array_index == fcurve.array_index:

                    # Remove the modifier
                    modifier = get_modifier_by_reference(context, ref)
                    if modifier:
                        fcurve.modifiers.remove(modifier)
                        modifiers_removed += 1

                    # Mark reference for removal
                    refs_to_remove.append(i)

        # Remove references (in reverse order to maintain indices)
        for i in reversed(refs_to_remove):
            group.modifier_references.remove(i)

        self.report({"INFO"}, f"Removed {modifiers_removed} modifiers from group '{group.name}'")

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


# ============================================================================
# MODIFIER GROUP EDITING OPERATOR (MODAL)
# ============================================================================


class AMP_OT_edit_modifier_group(Operator):
    """Edit modifier group with GUI pins interface"""

    bl_idname = "anim.amp_edit_modifier_group"
    bl_label = "Edit Modifier Group"
    bl_description = "Edit the active modifier group using GUI pins interface"
    bl_options = {"REGISTER", "UNDO", "GRAB_CURSOR"}

    # Class variables for modal operation
    _scope_gui = None
    _draw_handler = None
    _is_running = False
    _group_index = -1
    _initial_values = {}

    def invoke(self, context, event):
        """Initialize and start the modal operator."""

        # Check if any group is already being edited - if so, stop editing instead of starting new session
        settings = get_anim_modifiers_settings(context)
        if settings and settings.editing_group_index >= 0:
            # Find the group that's currently being edited
            groups = settings.modifier_groups
            if 0 <= settings.editing_group_index < len(groups):
                editing_group = groups[settings.editing_group_index]
                editing_group.is_editing = False

            # Clear the editing state
            settings.editing_group_index = -1

            # If there's a running modal instance, stop it
            if self._is_running:
                self._finish(context, confirmed=True)

            self.report({"INFO"}, "Stopped editing modifier group")
            return {"FINISHED"}

        # Get the active group
        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        # Check if we're in the Graph Editor
        if not context.space_data or context.space_data.type != "GRAPH_EDITOR":
            self.report({"ERROR"}, "Must be in the Graph Editor to edit modifier groups")
            return {"CANCELLED"}

        # Check if there are any F-curves available
        if not context.object or not context.object.animation_data or not context.object.animation_data.action:
            self.report({"ERROR"}, "No animation data or action found")
            return {"CANCELLED"}

        # Store the group index
        settings = get_anim_modifiers_settings(context)
        if not settings:
            self.report({"ERROR"}, "Animation modifiers settings not found")
            return {"CANCELLED"}

        self._group_index = settings.active_group_index

        # Set this group as editing
        settings.editing_group_index = self._group_index
        group.is_editing = True

        # Select and unhide all F-curves in the group
        select_group_fcurves(context, group)

        # Store initial values for undo
        self._store_initial_values(context, group)

        # Initialize the scope GUI
        frame_range = (group.main_start_frame, group.main_end_frame)

        self._scope_gui = ScopeGUI(
            frame_range=frame_range,
            operation_name=f"Editing: {group.name}",
            blend_range=max(1, int((group.blend_end_frame - group.blend_start_frame) / 3)),
            start_blend=BlendType.LINEAR,  # Always linear for modifiers
            end_blend=BlendType.LINEAR,  # Always linear for modifiers
            operation_options=None,  # No operation switching for modifiers
            factor_value=None,  # No factor for modifiers
            factor_multiplier=1.0,
            quick_drag=False,
            show_intensity=False,  # Hide intensity handler for modifiers
            show_blend_selectors=False,  # Hide blend selectors for modifiers
        )

        # Set pin positions manually
        if hasattr(self._scope_gui, "pins") and self._scope_gui.pins:
            # Pin order: [secondary_left, main_left, main_right, secondary_right]
            pin_positions = [
                group.blend_start_frame,
                group.main_start_frame,
                group.main_end_frame,
                group.blend_end_frame,
            ]

            for i, pin in enumerate(self._scope_gui.pins):
                if i < len(pin_positions):
                    pin.frame = pin_positions[i]

        # Set colors from preferences
        prefs = get_prefs()
        main_color = (0.05, 0.05, 0.05, 0.75)
        accent_color = (1.0, 0.5, 0.0, 1.0)
        self._scope_gui.set_colors(main_color, accent_color)

        # Activate the GUI
        self._scope_gui.activate()

        # Register draw handler
        self._draw_handler = context.space_data.draw_handler_add(
            self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
        )

        # Start modal operation
        context.window_manager.modal_handler_add(self)
        self._is_running = True

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """Handle modal events."""

        # Check if we're still in the Graph Editor
        if not context.space_data or context.space_data.type != "GRAPH_EDITOR":
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        # Get the group being edited
        group = self._get_editing_group(context)
        if not group:
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        if not self._scope_gui:
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        # Handle passthrough events
        if event.type in {"MIDDLE_MOUSE", "MWHEELUP", "MWHEELDOWN"}:
            return {"PASS_THROUGH"}

        # Handle exit conditions
        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        # Ensure F-curves are selected when starting interactions
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            ensure_group_fcurves_selected(context, group)

        # Update GUI
        result = self._scope_gui.update(context, event)

        # Check if GUI is actually handling the event based on dragging state
        gui_is_dragging = hasattr(self._scope_gui, "dragging_element") and self._scope_gui.dragging_element is not None

        # Check for GUI events
        if result == "CONFIRMED":
            self._finish(context, confirmed=True)
            return {"FINISHED"}
        elif result == "CANCELLED":
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        # Always apply changes on mouse movement for live updates of modifier and group properties
        if event.type == "MOUSEMOVE":
            self._apply_changes_to_group(context, group)
            # Ensure F-curves stay selected periodically for performance
            if not hasattr(self, "_selection_check_counter"):
                self._selection_check_counter = 0
            self._selection_check_counter += 1
            if self._selection_check_counter % 20 == 0:
                ensure_group_fcurves_selected(context, group)

        # Apply changes in real-time when interacting with the scope GUI
        if self._scope_gui and self._scope_gui.is_active:
            self._apply_changes_to_group(context, group)

        # Handle confirmation
        if event.type == "RET" and event.value == "PRESS":
            self._finish(context, confirmed=True)
            return {"FINISHED"}

        # Redraw
        context.area.tag_redraw()

        # Only block LMB when actually dragging a GUI element
        # This allows normal LMB interactions when not dragging
        if gui_is_dragging and event.type == "LEFTMOUSE":
            return {"RUNNING_MODAL"}
        else:
            return {"PASS_THROUGH"}

    def _store_initial_values(self, context, group):
        """Store initial values for undo."""
        self._initial_values = {
            "main_start_frame": group.main_start_frame,
            "main_end_frame": group.main_end_frame,
            "blend_start_frame": group.blend_start_frame,
            "blend_end_frame": group.blend_end_frame,
        }

    def _get_editing_group(self, context):
        """Get the group currently being edited."""
        settings = get_anim_modifiers_settings(context)
        if not settings:
            return None

        if self._group_index != settings.editing_group_index:
            return None

        groups = settings.modifier_groups
        if 0 <= self._group_index < len(groups):
            return groups[self._group_index]
        return None

    def _apply_changes_to_group(self, context, group):
        """Apply GUI changes to the modifier group."""
        if not self._scope_gui:
            return

        # Update group properties from GUI
        if hasattr(self._scope_gui, "pins") and len(self._scope_gui.pins) >= 4:
            # Pin order: [secondary_left, main_left, main_right, secondary_right]
            group.blend_start_frame = self._scope_gui.pins[0].frame
            group.main_start_frame = self._scope_gui.pins[1].frame
            group.main_end_frame = self._scope_gui.pins[2].frame
            group.blend_end_frame = self._scope_gui.pins[3].frame

        # Sync properties to all modifiers in the group
        sync_group_properties_to_modifiers(context, group)

        # Also sync modifier-specific properties if we have modifiers
        first_modifier = get_first_group_modifier(context, group)
        if first_modifier:
            sync_modifier_properties(context, group, first_modifier)

        # Refresh UI to show changes
        refresh_ui()

    def _finish(self, context, confirmed):
        """Finish the modal operation."""
        # Get the group
        group = self._get_editing_group(context)

        if not confirmed and group:
            # Restore initial values
            group.main_start_frame = self._initial_values["main_start_frame"]
            group.main_end_frame = self._initial_values["main_end_frame"]
            group.blend_start_frame = self._initial_values["blend_start_frame"]
            group.blend_end_frame = self._initial_values["blend_end_frame"]

            # Sync restored values to modifiers
            sync_group_properties_to_modifiers(context, group)

        # Clear editing state
        if group:
            group.is_editing = False

        settings = get_anim_modifiers_settings(context)
        if settings:
            settings.editing_group_index = -1

        # Cleanup GUI
        if self._scope_gui:
            self._scope_gui.deactivate()
            self._scope_gui = None

        # Remove draw handler
        if self._draw_handler and context.space_data:
            context.space_data.draw_handler_remove(self._draw_handler, "WINDOW")
            self._draw_handler = None

        self._is_running = False

        refresh_ui()

    def _draw_callback(self, context):
        """Draw callback for the GUI."""
        if self._scope_gui:
            self._scope_gui.draw(context)


# ============================================================================
# UTILITY OPERATORS
# ============================================================================


class AMP_OT_select_group_fcurves(Operator):
    """Select all F-curves belonging to the active modifier group"""

    bl_idname = "anim.amp_select_group_fcurves"
    bl_label = "Select Group F-curves"
    bl_description = "Select and unhide all F-curves belonging to the active modifier group"
    bl_options = {"REGISTER", "UNDO"}

    # Property to identify which specific group to select (optional - defaults to active group)
    group_name: StringProperty(
        name="Group Name",
        description="Name of the specific group to select (if empty, uses active group)",
        default="",
    )

    def execute(self, context):
        """Execute the operator."""
        # Get the target group - either specified by name or the active group
        if self.group_name:
            # Find the group by name
            settings = get_anim_modifiers_settings(context)
            if not settings:
                self.report({"WARNING"}, "Animation modifiers settings not found")
                return {"CANCELLED"}

            group = None
            group_index = -1
            for i, g in enumerate(settings.modifier_groups):
                if g.name == self.group_name:
                    group = g
                    group_index = i
                    break

            if not group:
                self.report({"WARNING"}, f"Modifier group '{self.group_name}' not found")
                return {"CANCELLED"}

            # Set this group as active for UI consistency
            settings.active_group_index = group_index
        else:
            # Use active group
            group = get_active_modifier_group(context)
            if not group:
                self.report({"WARNING"}, "No active modifier group")
                return {"CANCELLED"}

        # Use the same logic as the edit operator - simple and reliable
        # Just use the select_group_fcurves function that already works
        select_group_fcurves(context, group)

        # Count F-curves for reporting
        fcurves_found = 0
        for ref in group.modifier_references:
            fcurve = get_fcurve_by_reference(context, ref)
            if fcurve:
                fcurves_found += 1

        if fcurves_found > 0:
            self.report({"INFO"}, f"Selected {fcurves_found} F-curves for group '{group.name}'")
        else:
            self.report({"WARNING"}, f"No F-curves found for group '{group.name}'")

        # Refresh UI to update displays
        refresh_ui()

        return {"FINISHED"}


class AMP_OT_sync_modifier_properties(Operator):
    """Synchronize modifier properties across all modifiers in the active group"""

    bl_idname = "anim.amp_sync_modifier_properties"
    bl_label = "Sync Modifier Properties"
    bl_description = "Synchronize properties from the first modifier to all other modifiers in the group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Execute the operator."""
        group = get_active_modifier_group(context)
        if not group:
            return {"CANCELLED"}

        first_modifier = get_first_group_modifier(context, group)
        if not first_modifier:
            return {"CANCELLED"}

        # Synchronize properties
        sync_modifier_properties(context, group, first_modifier)

        # Also sync group properties (including random blend)
        sync_group_properties_to_modifiers(context, group)

        # Refresh UI to show changes
        refresh_ui()

        return {"FINISHED"}


class AMP_OT_debug_unique_ids(Operator):
    """Debug operator to check and upgrade unique IDs"""

    bl_idname = "anim.amp_debug_unique_ids"
    bl_label = "Debug Unique IDs"
    bl_description = "Check and upgrade modifier groups to use unique IDs"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Execute the operator."""
        # Upgrade existing groups
        from ..anim_modifiers.anim_modifiers import upgrade_existing_groups_to_unique_ids

        upgraded_count = upgrade_existing_groups_to_unique_ids(context)

        # Report debug information
        settings = get_anim_modifiers_settings(context)
        if settings:
            total_groups = len(settings.modifier_groups)
            groups_with_ids = sum(1 for g in settings.modifier_groups if g.unique_id)

            # Count total references and those with IDs
            total_refs = sum(len(g.modifier_references) for g in settings.modifier_groups)
            refs_with_ids = sum(sum(1 for r in g.modifier_references if r.unique_id) for g in settings.modifier_groups)

            self.report(
                {"INFO"},
                f"Unique ID Status: {groups_with_ids}/{total_groups} groups, {refs_with_ids}/{total_refs} references. Upgraded: {upgraded_count}",
            )
        else:
            self.report({"WARNING"}, "No animation modifiers settings found")

        return {"FINISHED"}


# ============================================================================
# COPY/PASTE OPERATORS
# ============================================================================


class AMP_OT_copy_modifier_group_settings(Operator):
    """Copy modifier group settings to clipboard"""

    bl_idname = "anim.amp_copy_modifier_group_settings"
    bl_label = "Copy Group Settings"
    bl_description = "Copy the current modifier group settings to clipboard"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        group = get_active_modifier_group(context)
        return group is not None

    def execute(self, context):
        """Execute the operator."""
        import json

        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        # Get the first modifier to copy its properties
        first_modifier = get_first_group_modifier(context, group)

        # Create data structure for clipboard
        clipboard_data = {
            "modifier_type": group.modifier_type,
            # Randomization properties
            "random_offset": group.random_offset,
            "random_phase": group.random_phase,
            "random_blend": group.random_blend,
            "random_range": group.random_range,
            # GUI pin frame range properties
            "main_start_frame": group.main_start_frame,
            "main_end_frame": group.main_end_frame,
            "blend_start_frame": group.blend_start_frame,
            "blend_end_frame": group.blend_end_frame,
            # Modifier-specific properties
            "modifier_properties": {},
        }

        # Copy modifier-specific properties if available
        if first_modifier:
            if group.modifier_type == ModifierType.NOISE:
                for prop in ["blend_type", "scale", "strength", "offset", "phase", "depth", "lacunarity", "roughness"]:
                    if hasattr(first_modifier, prop):
                        clipboard_data["modifier_properties"][prop] = getattr(first_modifier, prop)

            elif group.modifier_type == ModifierType.FNGENERATOR:
                for prop in ["function_type", "use_additive", "phase_multiplier", "phase_offset", "value_offset"]:
                    if hasattr(first_modifier, prop):
                        clipboard_data["modifier_properties"][prop] = getattr(first_modifier, prop)

            elif group.modifier_type == ModifierType.CYCLES:
                for prop in ["mode_before", "cycles_before", "mode_after", "cycles_after"]:
                    if hasattr(first_modifier, prop):
                        clipboard_data["modifier_properties"][prop] = getattr(first_modifier, prop)

            elif group.modifier_type == ModifierType.LIMITS:
                for prop in ["use_min_x", "min_x", "use_min_y", "min_y", "use_max_x", "max_x", "use_max_y", "max_y"]:
                    if hasattr(first_modifier, prop):
                        clipboard_data["modifier_properties"][prop] = getattr(first_modifier, prop)

            elif group.modifier_type == ModifierType.STEPPED:
                for prop in [
                    "frame_step",
                    "frame_offset",
                    "use_frame_start",
                    "frame_start",
                    "use_frame_end",
                    "frame_end",
                ]:
                    if hasattr(first_modifier, prop):
                        clipboard_data["modifier_properties"][prop] = getattr(first_modifier, prop)

        # Store in settings clipboard
        settings = get_anim_modifiers_settings(context)
        if settings:
            settings.clipboard_data = json.dumps(clipboard_data)
            settings.clipboard_modifier_type = group.modifier_type

        self.report(
            {"INFO"}, f"Copied settings for {ModifierType.get_display_name(group.modifier_type)} modifier group"
        )
        return {"FINISHED"}


class AMP_OT_paste_modifier_group_settings(Operator):
    """Paste modifier group settings from clipboard"""

    bl_idname = "anim.amp_paste_modifier_group_settings"
    bl_label = "Paste Group Settings"
    bl_description = "Paste modifier group settings from clipboard to the active group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        group = get_active_modifier_group(context)
        if not group:
            return False

        settings = get_anim_modifiers_settings(context)
        if not settings or not settings.clipboard_data:
            return False

        # Check if clipboard contains compatible modifier type
        return settings.clipboard_modifier_type == group.modifier_type

    def execute(self, context):
        """Execute the operator."""
        import json

        group = get_active_modifier_group(context)
        if not group:
            self.report({"WARNING"}, "No active modifier group")
            return {"CANCELLED"}

        settings = get_anim_modifiers_settings(context)
        if not settings or not settings.clipboard_data:
            self.report({"WARNING"}, "No modifier group settings in clipboard")
            return {"CANCELLED"}

        try:
            clipboard_data = json.loads(settings.clipboard_data)
        except json.JSONDecodeError:
            self.report({"ERROR"}, "Invalid clipboard data")
            return {"CANCELLED"}

        # Verify modifier type compatibility
        if clipboard_data.get("modifier_type") != group.modifier_type:
            modifier_type_name = ModifierType.get_display_name(group.modifier_type)
            clipboard_type_name = ModifierType.get_display_name(clipboard_data.get("modifier_type", ""))
            self.report(
                {"WARNING"},
                f"Clipboard contains {clipboard_type_name} settings, but active group is {modifier_type_name}",
            )
            return {"CANCELLED"}

        # Apply randomization settings
        if "random_offset" in clipboard_data:
            group.random_offset = clipboard_data["random_offset"]
        if "random_phase" in clipboard_data:
            group.random_phase = clipboard_data["random_phase"]
        if "random_blend" in clipboard_data:
            group.random_blend = clipboard_data["random_blend"]
        if "random_range" in clipboard_data:
            group.random_range = clipboard_data["random_range"]

        # Apply GUI pin frame range settings
        if "main_start_frame" in clipboard_data:
            group.main_start_frame = clipboard_data["main_start_frame"]
        if "main_end_frame" in clipboard_data:
            group.main_end_frame = clipboard_data["main_end_frame"]
        if "blend_start_frame" in clipboard_data:
            group.blend_start_frame = clipboard_data["blend_start_frame"]
        if "blend_end_frame" in clipboard_data:
            group.blend_end_frame = clipboard_data["blend_end_frame"]

        # Apply modifier properties to the first modifier (which will sync to all others)
        first_modifier = get_first_group_modifier(context, group)
        if first_modifier and "modifier_properties" in clipboard_data:
            modifier_props = clipboard_data["modifier_properties"]

            for prop_name, prop_value in modifier_props.items():
                if hasattr(first_modifier, prop_name):
                    setattr(first_modifier, prop_name, prop_value)

            # Sync properties to all modifiers in the group
            sync_modifier_properties(context, group, first_modifier)

        # Sync group properties to modifiers (for randomization)
        sync_group_properties_to_modifiers(context, group)

        modifier_type_name = ModifierType.get_display_name(group.modifier_type)
        self.report({"INFO"}, f"Pasted settings to {modifier_type_name} modifier group '{group.name}'")

        # Refresh UI
        refresh_ui()

        return {"FINISHED"}


# ============================================================================
# REFRESH/REBUILD OPERATORS
# ============================================================================


class AMP_OT_refresh_modifier_groups(Operator):
    """Scan action for orphaned modifiers and rebuild/refresh modifier groups"""

    bl_idname = "anim.amp_refresh_modifier_groups"
    bl_label = "Refresh All Groups"
    bl_description = "Scan the current action for modifiers with _AMP suffix and rebuild/refresh modifier groups"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        return context.object and context.object.animation_data and context.object.animation_data.action

    def execute(self, context):
        """Execute the operator."""
        if not context.object or not context.object.animation_data or not context.object.animation_data.action:
            self.report({"WARNING"}, "No active object with animation data")
            return {"CANCELLED"}

        action = context.active_object.animation_data.action
        settings = get_anim_modifiers_settings(context)
        if not settings:
            self.report({"ERROR"}, "Animation modifiers settings not found")
            return {"CANCELLED"}

        # Scan all F-curves for modifiers with _AMP suffix
        amp_modifiers = {}  # {group_name: {modifier_type: [(fcurve, modifier), ...]}}

        # Debug: Count total F-curves and modifiers found
        total_fcurves = 0
        total_modifiers = 0
        amp_modifiers_found = 0

        for fcurve in all_fcurves(action):
            total_fcurves += 1
            for modifier in fcurve.modifiers:
                total_modifiers += 1
                if modifier.name.endswith("_AMP"):
                    amp_modifiers_found += 1
                    # Extract group name (remove _AMP suffix)
                    group_name = modifier.name[:-4]  # Remove "_AMP"
                    modifier_type = modifier.type

                    if group_name not in amp_modifiers:
                        amp_modifiers[group_name] = {}
                    if modifier_type not in amp_modifiers[group_name]:
                        amp_modifiers[group_name][modifier_type] = []

                    amp_modifiers[group_name][modifier_type].append((fcurve, modifier))

        # Debug: Report scan results
        print(
            f"Refresh scan results: {total_fcurves} F-curves, {total_modifiers} total modifiers, {amp_modifiers_found} AMP modifiers found"
        )

        if not amp_modifiers:
            self.report(
                {"INFO"},
                f"No modifiers with _AMP suffix found in current action. Scanned {total_fcurves} F-curves with {total_modifiers} total modifiers.",
            )
            return {"FINISHED"}

        groups_refreshed = 0
        groups_created = 0
        modifiers_added = 0

        # Process each group found in F-curves
        for group_name, modifier_types in amp_modifiers.items():
            # Find existing group or create new one
            existing_group = None
            for group in settings.modifier_groups:
                if group.name == group_name and group.action_name == action.name:
                    existing_group = group
                    break

            # Process each modifier type separately (groups are type-specific)
            for modifier_type, fcurve_modifier_pairs in modifier_types.items():
                group_to_use = existing_group

                # If no existing group found, or existing group has different type, create new one
                if not existing_group or existing_group.modifier_type != modifier_type:
                    # Create unique name if type doesn't match
                    if existing_group and existing_group.modifier_type != modifier_type:
                        type_display_name = ModifierType.get_display_name(modifier_type)
                        unique_name = ensure_unique_group_name(
                            settings.modifier_groups, f"{group_name} ({type_display_name})"
                        )
                    else:
                        unique_name = ensure_unique_group_name(settings.modifier_groups, group_name)

                    # Create new group
                    new_group = settings.modifier_groups.add()
                    new_group.name = unique_name
                    new_group.previous_name = unique_name
                    new_group.modifier_type = modifier_type
                    new_group.action_name = action.name

                    # Generate unique ID
                    from ..anim_modifiers.anim_modifiers import ensure_group_has_unique_id

                    ensure_group_has_unique_id(new_group)

                    # Set default frame range
                    start_frame, end_frame = get_smart_frame_range(context)
                    new_group.main_start_frame = start_frame
                    new_group.main_end_frame = end_frame
                    new_group.blend_start_frame = start_frame
                    new_group.blend_end_frame = end_frame

                    group_to_use = new_group
                    groups_created += 1
                else:
                    groups_refreshed += 1

                # Add missing modifiers to the group
                for fcurve, modifier in fcurve_modifier_pairs:
                    # Check if this modifier is already referenced in the group
                    already_referenced = False
                    for ref in group_to_use.modifier_references:
                        if (
                            ref.fcurve_data_path == fcurve.data_path
                            and ref.fcurve_array_index == fcurve.array_index
                            and ref.modifier_name == modifier.name
                        ):
                            already_referenced = True
                            break

                    if not already_referenced:
                        # Create new reference
                        ref = group_to_use.modifier_references.add()
                        ref.action = action
                        ref.fcurve_data_path = fcurve.data_path
                        ref.fcurve_array_index = fcurve.array_index
                        ref.modifier_name = modifier.name
                        ref.modifier_type = modifier_type

                        # Generate unique ID for reference
                        from ..anim_modifiers.anim_modifiers import ensure_reference_has_unique_id

                        ensure_reference_has_unique_id(ref)

                        # Store slot reference for cross-version compatibility
                        from ..anim_modifiers.anim_modifiers import store_slot_reference

                        store_slot_reference(ref, context, fcurve)

                        fcurves_list = list(all_fcurves(action))
                        try:
                            ref.fcurve_index = fcurves_list.index(fcurve)
                        except ValueError:
                            ref.fcurve_index = -1

                        modifiers_added += 1

        # Report results
        if groups_created > 0 or groups_refreshed > 0:
            msg_parts = []
            if groups_created > 0:
                msg_parts.append(f"created {groups_created} groups")
            if groups_refreshed > 0:
                msg_parts.append(f"refreshed {groups_refreshed} groups")

            msg = f"Scan complete: {', '.join(msg_parts)}, added {modifiers_added} modifier references"
            self.report({"INFO"}, msg)
        else:
            self.report({"INFO"}, f"No groups needed updating. Found {modifiers_added} existing references.")

        # Refresh UI
        refresh_ui()
        return {"FINISHED"}


class AMP_OT_refresh_single_modifier_group(Operator):
    """Refresh a specific modifier group by scanning for its modifiers"""

    bl_idname = "anim.amp_refresh_single_modifier_group"
    bl_label = "Refresh Group"
    bl_description = "Scan for modifiers belonging to this specific group and add any missing ones"
    bl_options = {"REGISTER", "UNDO"}

    group_name: StringProperty(
        name="Group Name",
        description="Name of the group to refresh",
        default="",
    )

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        return context.object and context.object.animation_data and context.object.animation_data.action

    def execute(self, context):
        """Execute the operator."""
        if not context.object or not context.object.animation_data or not context.object.animation_data.action:
            self.report({"WARNING"}, "No active object with animation data")
            return {"CANCELLED"}

        action = context.active_object.animation_data.action
        settings = get_anim_modifiers_settings(context)
        if not settings:
            self.report({"ERROR"}, "Animation modifiers settings not found")
            return {"CANCELLED"}

        # Find the target group
        target_group = None
        if self.group_name:
            # Find by name
            for group in settings.modifier_groups:
                if group.name == self.group_name and group.action_name == action.name:
                    target_group = group
                    break
        else:
            # Use active group
            target_group = get_active_modifier_group(context)

        if not target_group:
            self.report({"WARNING"}, "No target group found")
            return {"CANCELLED"}

        # Scan for modifiers matching this group's naming pattern
        expected_modifier_name = get_group_modifier_name(target_group.name)
        modifiers_found = []

        # Debug: Count total F-curves and modifiers
        total_fcurves = 0
        total_modifiers = 0

        for fcurve in all_fcurves(action):
            total_fcurves += 1
            for modifier in fcurve.modifiers:
                total_modifiers += 1
                if modifier.name == expected_modifier_name and modifier.type == target_group.modifier_type:
                    modifiers_found.append((fcurve, modifier))

        # Debug: Report scan results
        print(f"Single group refresh scan results: {total_fcurves} F-curves, {total_modifiers} total modifiers")
        print(f"Looking for modifier name: '{expected_modifier_name}' with type: '{target_group.modifier_type}'")
        print(f"Found {len(modifiers_found)} matching modifiers")

        if not modifiers_found:
            self.report(
                {"INFO"},
                f"No modifiers found with name '{expected_modifier_name}' and type '{target_group.modifier_type}'. Scanned {total_fcurves} F-curves with {total_modifiers} total modifiers.",
            )
            return {"FINISHED"}

        # Add missing modifiers to the group
        modifiers_added = 0
        for fcurve, modifier in modifiers_found:
            # Check if this modifier is already referenced in the group
            already_referenced = False
            for ref in target_group.modifier_references:
                if (
                    ref.fcurve_data_path == fcurve.data_path
                    and ref.fcurve_array_index == fcurve.array_index
                    and ref.modifier_name == modifier.name
                ):
                    already_referenced = True
                    break

            if not already_referenced:
                # Create new reference
                ref = target_group.modifier_references.add()
                ref.action = action
                ref.fcurve_data_path = fcurve.data_path
                ref.fcurve_array_index = fcurve.array_index
                ref.modifier_name = modifier.name
                ref.modifier_type = target_group.modifier_type

                # Generate unique ID for reference
                from ..anim_modifiers.anim_modifiers import ensure_reference_has_unique_id

                ensure_reference_has_unique_id(ref)

                # Store slot reference for cross-version compatibility
                from ..anim_modifiers.anim_modifiers import store_slot_reference

                store_slot_reference(ref, context, fcurve)

                fcurves_list = list(all_fcurves(action))
                try:
                    ref.fcurve_index = fcurves_list.index(fcurve)
                except ValueError:
                    ref.fcurve_index = -1

                modifiers_added += 1

        if modifiers_added > 0:
            self.report({"INFO"}, f"Added {modifiers_added} missing modifiers to group '{target_group.name}'")
        else:
            self.report({"INFO"}, f"Group '{target_group.name}' is already up to date")

        # Refresh UI
        refresh_ui()
        return {"FINISHED"}


class AMP_OT_clear_orphaned_amp_modifiers(Operator):
    """Remove all modifiers with _AMP suffix that are not linked to any group"""

    bl_idname = "anim.amp_clear_orphaned_amp_modifiers"
    bl_label = "Clear Orphaned AMP Modifiers"
    bl_description = "Remove all modifiers with _AMP suffix that are not linked to any modifier group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Check if operator can be executed."""
        return context.object and context.object.animation_data and context.object.animation_data.action

    def invoke(self, context, event):
        """Show confirmation dialog."""
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        """Execute the operator."""
        if not context.object or not context.object.animation_data or not context.object.animation_data.action:
            self.report({"WARNING"}, "No active object with animation data")
            return {"CANCELLED"}

        action = context.active_object.animation_data.action
        settings = get_anim_modifiers_settings(context)
        if not settings:
            self.report({"ERROR"}, "Animation modifiers settings not found")
            return {"CANCELLED"}

        # Collect all modifier names that are referenced by groups in current action
        referenced_modifier_names = set()
        for group in settings.modifier_groups:
            if group.action_name == action.name:
                for ref in group.modifier_references:
                    referenced_modifier_names.add(ref.modifier_name)

        # Find orphaned AMP modifiers
        orphaned_modifiers = []
        total_fcurves = 0
        total_modifiers = 0
        amp_modifiers_found = 0

        for fcurve in all_fcurves(action):
            total_fcurves += 1
            for modifier in fcurve.modifiers:
                total_modifiers += 1
                if modifier.name.endswith("_AMP"):
                    amp_modifiers_found += 1
                    if modifier.name not in referenced_modifier_names:
                        orphaned_modifiers.append((fcurve, modifier))

        # Debug: Report scan results
        print(
            f"Clear orphaned scan results: {total_fcurves} F-curves, {total_modifiers} total modifiers, {amp_modifiers_found} AMP modifiers, {len(orphaned_modifiers)} orphaned"
        )
        print(f"Referenced modifier names: {referenced_modifier_names}")

        if not orphaned_modifiers:
            self.report(
                {"INFO"},
                f"No orphaned AMP modifiers found. Scanned {total_fcurves} F-curves with {amp_modifiers_found} AMP modifiers, all are referenced.",
            )
            return {"FINISHED"}

        # Remove orphaned modifiers
        modifiers_removed = 0
        for fcurve, modifier in orphaned_modifiers:
            try:
                fcurve.modifiers.remove(modifier)
                modifiers_removed += 1
            except Exception as e:
                print(f"Error removing modifier {modifier.name} from {fcurve.data_path}: {e}")

        self.report({"INFO"}, f"Removed {modifiers_removed} orphaned AMP modifiers")

        # Refresh UI
        refresh_ui()
        return {"FINISHED"}


# ============================================================================
# REGISTRATION
# ============================================================================


classes = [
    AMP_OT_add_modifier_group,
    AMP_OT_create_modifier_group_with_type,
    AMP_OT_remove_modifier_group,
    AMP_OT_apply_modifier_group,
    AMP_OT_move_modifier_group,
    AMP_OT_add_modifiers_to_group,
    AMP_OT_remove_modifiers_from_group,
    AMP_OT_edit_modifier_group,
    AMP_OT_select_group_fcurves,
    AMP_OT_sync_modifier_properties,
    AMP_OT_debug_unique_ids,
    AMP_OT_copy_modifier_group_settings,
    AMP_OT_paste_modifier_group_settings,
    AMP_OT_refresh_modifier_groups,
    AMP_OT_refresh_single_modifier_group,
    AMP_OT_clear_orphaned_amp_modifiers,
]


def register():
    """Register operators."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister operators."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
