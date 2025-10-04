"""
AniMate Pro - Animation Modifiers

This module provides a system for managing multiple F-curve modifiers as groups
with a unified interface using the GUI pins system.

Features:
- Group multiple F-curve modifiers together
- Control shared properties (influence, frame range, blend) via GUI pins
- Reusable modifier groups with unique names
- Automatic synchronization of modifier properties
- Interactive editing with real-time feedback

Supported Modifiers:
- Generator
- Built-In Function
- Envelope
- Cycles
- Noise
- Limits
- Stepped Interpolation
"""

import bpy
from bpy.props import (
    StringProperty,
    FloatProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup
from typing import List, Dict, Optional, Tuple, Any
import uuid
import hashlib
import random
from ..utils.curve import all_fcurves


# ============================================================================
# MODIFIER TYPE DEFINITIONS
# ============================================================================


class ModifierType:
    """Enumeration for supported F-curve modifier types."""

    FNGENERATOR = "FNGENERATOR"
    CYCLES = "CYCLES"
    NOISE = "NOISE"
    LIMITS = "LIMITS"
    STEPPED = "STEPPED"

    @classmethod
    def get_all_types(cls):
        """Get all available modifier types as enum items."""
        return [
            (cls.FNGENERATOR, "Built-In Function", "Built-in mathematical functions"),
            (cls.CYCLES, "Cycles", "Cycle repetition modifier"),
            (cls.NOISE, "Noise", "Random noise modifier"),
            (cls.LIMITS, "Limits", "Value clamping modifier"),
            (cls.STEPPED, "Stepped Interpolation", "Stepped interpolation modifier"),
        ]

    @classmethod
    def get_display_name(cls, modifier_type):
        """Get display name for a modifier type."""
        type_map = {
            cls.FNGENERATOR: "Built-In Function",
            cls.CYCLES: "Cycles",
            cls.NOISE: "Noise",
            cls.LIMITS: "Limits",
            cls.STEPPED: "Stepped Interpolation",
        }
        return type_map.get(modifier_type, "Unknown")


# ============================================================================
# PROPERTY GROUPS
# ============================================================================


class AMP_PG_ModifierReference(PropertyGroup):
    """Reference to an F-curve modifier within a modifier group."""

    # Pointer to the action containing the F-curve
    action: PointerProperty(name="Action", description="Action containing the F-curve", type=bpy.types.Action)

    # F-curve identification properties
    fcurve_data_path: StringProperty(name="Data Path", description="Data path of the F-curve", default="")

    fcurve_array_index: IntProperty(name="Array Index", description="Array index of the F-curve", default=0)

    # For Blender 4.4+ slotted actions - store slot information
    action_slot_handle: IntProperty(
        name="Action Slot Handle",
        description="Handle of the action slot (for Blender 4.4+ slotted actions)",
        default=-1,
    )

    action_slot_identifier: StringProperty(
        name="Action Slot Identifier",
        description="Identifier of the action slot (for cross-version compatibility)",
        default="",
    )

    # Fallback identification for index-based lookup
    fcurve_index: IntProperty(
        name="F-Curve Index", description="Index of the F-curve in the action (fallback identifier)", default=-1
    )

    modifier_name: StringProperty(name="Modifier Name", description="Name of the modifier", default="")

    modifier_type: EnumProperty(
        name="Modifier Type",
        description="Type of the modifier",
        items=ModifierType.get_all_types(),
        default=ModifierType.NOISE,
    )

    # Unique identifier for this reference - generated once and never changed
    unique_id: StringProperty(
        name="Unique ID",
        description="Unique identifier for this modifier reference (UUID)",
        default="",
    )


def update_group_name(self, context):
    """Update callback when group name changes - updates all modifier names."""
    # Check if we have a previous name to compare
    if self.previous_name and self.previous_name != self.name:
        # Name has changed, update all modifier names
        update_group_modifier_names(context, self, self.previous_name, self.name)

        # Refresh UI to show changes
        from .anim_modifiers_operators import refresh_ui

        refresh_ui()

    # Update the previous name for next comparison
    self.previous_name = self.name


def update_random_properties(self, context):
    """Update callback for randomization properties."""
    # Only sync if we're currently editing
    if self.is_editing:
        first_modifier = get_first_group_modifier(context, self)
        if first_modifier:
            sync_modifier_properties(context, self, first_modifier)


def update_group_visibility(self, context):
    """Update callback when group visibility is toggled - enables/disables all modifiers in the group."""
    # Skip if we're syncing to prevent infinite recursion
    if self.get("_syncing", False):
        return

    try:
        # Get all modifiers in this group
        modifiers = get_all_group_modifiers(context, self)

        if not modifiers:
            return

        # Toggle the 'mute' property of all modifiers (inverted logic since mute=True means disabled)
        for modifier in modifiers:
            if modifier and hasattr(modifier, "mute"):
                modifier.mute = not self.visible

        # Refresh the UI to show changes
        try:
            from .anim_modifiers_operators import refresh_ui

            refresh_ui()
        except ImportError:
            # Fallback if refresh_ui is not available
            for area in context.screen.areas:
                if area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
                    area.tag_redraw()

    except Exception as e:
        # Handle gracefully if there are any issues
        print(f"Error updating group visibility: {e}")


def sync_group_visibility_from_modifiers(context, group):
    """Sync the group's visibility property based on the current state of its modifiers."""
    try:
        modifiers = get_all_group_modifiers(context, group)
        if not modifiers:
            return

        # Check if any modifier is not muted (visible)
        # If all modifiers are muted, group is invisible
        # If any modifier is not muted, group is visible
        has_visible_modifier = any(
            hasattr(modifier, "mute") and not modifier.mute for modifier in modifiers if modifier
        )

        # Only update if the state has changed to avoid infinite loops
        if group.visible != has_visible_modifier:
            # Set a flag to prevent update callback during sync
            group["_syncing"] = True
            group.visible = has_visible_modifier
            del group["_syncing"]

    except Exception as e:
        print(f"Error syncing group visibility: {e}")


class AMP_PG_ModifierGroup(PropertyGroup):
    """A group of F-curve modifiers that can be controlled together."""

    name: StringProperty(
        name="Name", description="Name of the modifier group", default="Modifier Group", update=update_group_name
    )

    # Action association - links this group to a specific action
    action_name: StringProperty(
        name="Action Name", description="Name of the action this modifier group belongs to", default=""
    )

    # Modifier type for this group (all modifiers in group must be of this type)
    modifier_type: EnumProperty(
        name="Modifier Type",
        description="Type of modifiers in this group",
        items=ModifierType.get_all_types(),
        default=ModifierType.NOISE,
    )

    # References to modifiers in this group
    modifier_references: CollectionProperty(
        type=AMP_PG_ModifierReference, name="Modifier References", description="References to modifiers in this group"
    )

    # GUI pins control properties
    main_start_frame: FloatProperty(
        name="Main Start Frame", description="Start frame for the main pin range", default=1.0
    )

    main_end_frame: FloatProperty(name="Main End Frame", description="End frame for the main pin range", default=100.0)

    blend_start_frame: FloatProperty(
        name="Blend Start Frame", description="Start frame for the blend range", default=1.0
    )

    blend_end_frame: FloatProperty(name="Blend End Frame", description="End frame for the blend range", default=100.0)

    # Randomization properties
    random_offset: FloatProperty(
        name="Random Offset",
        description="Random offset multiplier applied to offset properties (0.0 = no randomization, 1.0 = full randomization)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=update_random_properties,
    )

    random_phase: FloatProperty(
        name="Random Phase",
        description="Random phase multiplier applied to phase properties (0.0 = no randomization, 1.0 = full randomization)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=update_random_properties,
    )

    random_blend: FloatProperty(
        name="Random Blend",
        description="Random blend multiplier applied to blend_in/blend_out properties (0.0 = no randomization, 1.0 = full randomization)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=update_random_properties,
    )

    random_range: FloatProperty(
        name="Random Range",
        description="Random range multiplier applied to frame_start/frame_end properties (0.0 = no randomization, 1.0 = full randomization)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=update_random_properties,
    )

    # Track if we're currently editing this group
    is_editing: BoolProperty(
        name="Is Editing", description="Whether this modifier group is currently being edited", default=False
    )

    # Visibility toggle for all modifiers in the group
    visible: BoolProperty(
        name="Visible",
        description="Show/hide all modifiers in this group in the Graph Editor",
        default=True,
        update=update_group_visibility,
    )

    # Internal property to track the previous name for rename detection
    previous_name: StringProperty(
        name="Previous Name", description="Internal property to track previous name for rename detection", default=""
    )

    # Unique identifier for this modifier group - generated once and never changed
    # This is used to match modifier groups with their F-curve modifiers reliably
    unique_id: StringProperty(
        name="Unique ID",
        description="Unique identifier for this modifier group (UUID) - used for reliable F-curve matching",
        default="",
    )


class AMP_PG_AnimModifiersSettings(PropertyGroup):
    """Settings for the animation modifiers system."""

    # Collection of modifier groups
    modifier_groups: CollectionProperty(
        type=AMP_PG_ModifierGroup, name="Modifier Groups", description="Collection of modifier groups"
    )

    # Active group index
    active_group_index: IntProperty(
        name="Active Group Index", description="Index of the currently active modifier group", default=0, min=0
    )

    # Currently editing group (only one can be edited at a time)
    editing_group_index: IntProperty(
        name="Editing Group Index",
        description="Index of the modifier group currently being edited (-1 = none)",
        default=-1,
    )

    # Clipboard for copy/paste functionality
    clipboard_data: StringProperty(
        name="Clipboard Data",
        description="JSON data for copied modifier group settings",
        default="",
    )

    clipboard_modifier_type: StringProperty(
        name="Clipboard Modifier Type",
        description="Type of modifier in clipboard for validation",
        default="",
    )


# ============================================================================
# SLOT HANDLING UTILITIES (Cross-Version Compatibility)
# ============================================================================


def get_current_slot_info(context):
    """Get current slot information for the active object/action."""
    obj = context.object
    if not obj or not obj.animation_data or not obj.animation_data.action:
        return None, None

    action = obj.animation_data.action

    # Check if we're in Blender 4.4+ with slotted actions
    if hasattr(action, "is_action_layered") and action.is_action_layered:
        slot = obj.animation_data.action_slot
        if slot:
            return slot.handle, slot.identifier

    return None, None


def store_slot_reference(ref, context, fcurve):
    """Store slot reference information in the modifier reference."""
    slot_handle, slot_identifier = get_current_slot_info(context)

    if slot_handle is not None:
        ref.action_slot_handle = slot_handle
        ref.action_slot_identifier = slot_identifier
    else:
        ref.action_slot_handle = -1
        ref.action_slot_identifier = ""


def find_slot_by_reference(action, ref):
    """Find action slot by stored reference information."""
    if not hasattr(action, "slots") or ref.action_slot_handle == -1:
        return None

    # Try handle-based lookup first (most reliable)
    for slot in action.slots:
        if slot.handle == ref.action_slot_handle:
            return slot

    # Fallback to identifier-based lookup
    if ref.action_slot_identifier:
        for slot in action.slots:
            if slot.identifier == ref.action_slot_identifier:
                return slot

    return None


def get_slot_context_for_reference(context, ref):
    """Get the correct slot context for a specific reference by temporarily switching to it."""
    if not ref.action:
        return None, None

    action = ref.action

    # For non-slotted actions, return None
    if not hasattr(action, "is_action_layered") or not action.is_action_layered:
        return None, None

    # Find the object that owns this action
    target_obj = None
    for obj in context.scene.objects:
        if obj.animation_data and obj.animation_data.action == action:
            target_obj = obj
            break

    if not target_obj:
        return None, None

    # Store original state
    original_active = context.view_layer.objects.active
    original_slot = None
    if target_obj.animation_data:
        original_slot = target_obj.animation_data.action_slot

    try:
        # Temporarily activate the target object
        context.view_layer.objects.active = target_obj

        # Find and set the correct slot for this reference
        slot = find_slot_by_reference(action, ref)
        if slot:
            target_obj.animation_data.action_slot = slot
            return slot.handle, slot.identifier
        else:
            # If we can't find the specific slot, return the stored reference info
            return ref.action_slot_handle if ref.action_slot_handle != -1 else None, ref.action_slot_identifier

    finally:
        # Restore original state
        context.view_layer.objects.active = original_active
        if target_obj.animation_data and original_slot:
            target_obj.animation_data.action_slot = original_slot

    return None, None


def get_fcurves_for_slot(action, slot):
    """Get all F-curves for a specific slot in a layered action."""
    fcurves = []

    if not hasattr(action, "layers"):
        return fcurves

    for layer in action.layers:
        for strip in layer.strips:
            if strip.type == "KEYFRAME":
                channelbag = strip.channelbag(slot, ensure=False)
                if channelbag:
                    fcurves.extend(channelbag.fcurves)

    return fcurves


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_modifier_groups(context):
    """Get the modifier groups collection from the window manager."""
    # Use WindowManager for cross-version compatibility and better pointer storage
    return context.window_manager.amp_anim_modifiers.modifier_groups


def get_current_action_groups(context):
    """Get modifier groups that belong to the current active action."""
    all_groups = get_modifier_groups(context)
    if not all_groups:
        return []

    # Get current action name
    current_action_name = ""
    if context.object and context.object.animation_data and context.object.animation_data.action:
        current_action_name = context.object.animation_data.action.name

    # Filter groups that belong to current action
    current_groups = []
    for group in all_groups:
        if group.action_name == current_action_name:
            current_groups.append(group)

    return current_groups


def get_anim_modifiers_settings(context):
    """Get the animation modifiers settings from the window manager."""
    settings = context.window_manager.amp_anim_modifiers

    return settings


def get_active_modifier_group(context):
    """Get the currently active modifier group (from current action only)."""
    settings = get_anim_modifiers_settings(context)
    if not settings:
        return None

    # Get current action groups only
    current_action_groups = get_current_action_groups(context)
    if not current_action_groups:
        return None

    # Map the active index to the filtered groups
    # This is a bit complex since we need to find the correct group by index
    groups = settings.modifier_groups
    if 0 <= settings.active_group_index < len(groups):
        candidate_group = groups[settings.active_group_index]
        # Verify this group belongs to current action
        current_action_name = ""
        if context.object and context.object.animation_data and context.object.animation_data.action:
            current_action_name = context.object.animation_data.action.name

        if candidate_group.action_name == current_action_name:
            return candidate_group

    return None


def get_editing_modifier_group(context):
    """Get the modifier group currently being edited (from current action only)."""
    settings = get_anim_modifiers_settings(context)
    if not settings:
        return None

    groups = settings.modifier_groups
    if not groups:
        return None

    if 0 <= settings.editing_group_index < len(groups):
        candidate_group = groups[settings.editing_group_index]
        # Verify this group belongs to current action
        current_action_name = ""
        if context.object and context.object.animation_data and context.object.animation_data.action:
            current_action_name = context.object.animation_data.action.name

        if candidate_group.action_name == current_action_name:
            return candidate_group

    return None


def ensure_unique_group_name(groups, base_name):
    """Ensure a modifier group name is unique within the collection."""
    if not groups:
        return base_name

    existing_names = {group.name for group in groups}
    if base_name not in existing_names:
        return base_name

    counter = 1
    while f"{base_name}.{counter:03d}" in existing_names:
        counter += 1
    return f"{base_name}.{counter:03d}"


# ============================================================================
# UNIQUE ID UTILITIES
# ============================================================================


def generate_unique_id():
    """Generate a new unique identifier (UUID)."""
    return str(uuid.uuid4())


def ensure_group_has_unique_id(group):
    """Ensure a modifier group has a unique ID, generating one if needed."""
    if not group.unique_id:
        group.unique_id = generate_unique_id()
    return group.unique_id


def ensure_reference_has_unique_id(ref):
    """Ensure a modifier reference has a unique ID, generating one if needed."""
    if not ref.unique_id:
        ref.unique_id = generate_unique_id()
    return ref.unique_id


def upgrade_existing_groups_to_unique_ids(context):
    """Upgrade existing modifier groups to use unique IDs for backward compatibility."""
    settings = get_anim_modifiers_settings(context)
    if not settings:
        return

    upgraded_count = 0

    for group in settings.modifier_groups:
        # Ensure group has unique ID
        if not group.unique_id:
            group_unique_id = ensure_group_has_unique_id(group)

            # Ensure all references have unique IDs
            for ref in group.modifier_references:
                if not ref.unique_id:
                    reference_unique_id = ensure_reference_has_unique_id(ref)

            upgraded_count += 1

    if upgraded_count > 0:
        print(f"Upgraded {upgraded_count} modifier groups to use unique IDs")

    return upgraded_count


def get_fcurve_by_reference(context, ref):
    """Get an F-curve by action pointer and identification properties."""
    # Method 1: Use stored action pointer if available
    if ref.action and _is_action_valid(ref.action):
        action = ref.action

        # Check if this is a slotted action and we have slot information
        if hasattr(action, "is_action_layered") and action.is_action_layered and ref.action_slot_handle != -1:
            slot = find_slot_by_reference(action, ref)
            if slot:
                # Search F-curves in the specific slot
                slot_fcurves = get_fcurves_for_slot(action, slot)
                for fcurve in slot_fcurves:
                    if fcurve.data_path == ref.fcurve_data_path and fcurve.array_index == ref.fcurve_array_index:
                        return fcurve

                # Fallback: Try index-based lookup within slot
                if ref.fcurve_index >= 0 and ref.fcurve_index < len(slot_fcurves):
                    return slot_fcurves[ref.fcurve_index]

            # If we couldn't find it in the specific slot, try all slots in the action
            # This is important for the select operator which should find F-curves across all slots
            if hasattr(action, "slots"):
                for slot in action.slots:
                    slot_fcurves = get_fcurves_for_slot(action, slot)
                    for fcurve in slot_fcurves:
                        if fcurve.data_path == ref.fcurve_data_path and fcurve.array_index == ref.fcurve_array_index:
                            # Update the reference with the correct slot info for future use
                            ref.action_slot_handle = slot.handle
                            ref.action_slot_identifier = slot.identifier
                            return fcurve
        else:
            # Legacy action or non-slotted: Try data_path + array_index matching first
            if ref.fcurve_data_path:
                for fcurve in all_fcurves(action):
                    if fcurve.data_path == ref.fcurve_data_path and fcurve.array_index == ref.fcurve_array_index:
                        return fcurve

            # Fallback: Try index-based lookup if data_path failed
            if ref.fcurve_index >= 0:
                try:
                    fcurves_list = list(all_fcurves(action))
                    if 0 <= ref.fcurve_index < len(fcurves_list):
                        return fcurves_list[ref.fcurve_index]
                except (IndexError, TypeError):
                    pass

    # Method 2: Fallback to current object's action
    if not context.object or not context.object.animation_data:
        return None

    action = context.object.animation_data.action
    if not action:
        return None

    # Update the action reference for future use
    ref.action = action

    # Check current slot context and update slot reference
    slot_handle, slot_identifier = get_current_slot_info(context)
    if slot_handle is not None:
        ref.action_slot_handle = slot_handle
        ref.action_slot_identifier = slot_identifier

        # Try to find F-curve in current slot context
        if hasattr(action, "is_action_layered") and action.is_action_layered:
            slot = context.object.animation_data.action_slot
            if slot:
                slot_fcurves = get_fcurves_for_slot(action, slot)
                for i, fcurve in enumerate(slot_fcurves):
                    if fcurve.data_path == ref.fcurve_data_path and fcurve.array_index == ref.fcurve_array_index:
                        # Update the index reference for future use (within slot)
                        ref.fcurve_index = i
                        return fcurve

    # Legacy fallback: Search for F-curve by data_path and array_index
    if ref.fcurve_data_path:
        for i, fcurve in enumerate(all_fcurves(action)):
            if fcurve.data_path == ref.fcurve_data_path and fcurve.array_index == ref.fcurve_array_index:
                # Update the index reference for future use
                ref.fcurve_index = i
                return fcurve

    return None


def _is_action_valid(action):
    """Check if an action pointer is still valid and accessible."""
    try:
        # Try to access basic properties to verify the object still exists
        _ = action.name
        _ = action.fcurves
        return True
    except (AttributeError, ReferenceError):
        return False


def get_modifier_by_reference(context, ref):
    """Get a modifier by its reference, using name and type matching."""
    fcurve = get_fcurve_by_reference(context, ref)
    if not fcurve:
        return None

    # Method 1: Try exact name match
    for modifier in fcurve.modifiers:
        if modifier.name == ref.modifier_name:
            return modifier

    # Method 2: Fallback - match by modifier type (handles slotted action cases)
    for modifier in fcurve.modifiers:
        if hasattr(modifier, "type") and modifier.type == ref.modifier_type:
            return modifier

    return None


def get_all_group_modifiers(context, group):
    """Get all modifiers belonging to a modifier group."""

    modifiers = []
    for i, ref in enumerate(group.modifier_references):
        modifier = get_modifier_by_reference(context, ref)
        if modifier:
            modifiers.append(modifier)
        else:
            pass

    return modifiers


def update_group_modifier_names(context, group, old_name, new_name):
    """Update all modifier names when a group is renamed."""
    old_modifier_name = f"{old_name}_AMP"
    new_modifier_name = f"{new_name}_AMP"

    # Update all modifiers in the group
    for ref in group.modifier_references:
        modifier = get_modifier_by_reference(context, ref)
        if modifier and modifier.name == old_modifier_name:
            modifier.name = new_modifier_name
            # Also update the reference
            ref.modifier_name = new_modifier_name


def fcurve_has_group_modifier(fcurve, group_name):
    """Check if an F-curve already has a modifier for the specified group (legacy method)."""
    modifier_name = f"{group_name}_AMP"

    for modifier in fcurve.modifiers:
        if modifier.name == modifier_name:
            return True

    return False


def fcurve_has_group_modifier_by_group(fcurve, group):
    """Check if an F-curve already has a modifier for the specified group."""
    if not group:
        return False

    # Check if this F-curve is already referenced in the group
    for ref in group.modifier_references:
        if ref.fcurve_data_path == fcurve.data_path and ref.fcurve_array_index == fcurve.array_index:
            return True

    return False


def get_group_modifier_name(group_name):
    """Get the standardized modifier name for a group."""
    return f"{group_name}_AMP"


def get_first_group_modifier(context, group):
    """Get the first modifier in a group (used as reference for properties)."""

    for i, ref in enumerate(group.modifier_references):

        modifier = get_modifier_by_reference(context, ref)
        if modifier:
            return modifier
        else:
            pass

    return None


def sync_modifier_properties(context, group, source_modifier):
    """Synchronize properties from source modifier to all other modifiers in the group."""

    modifiers = get_all_group_modifiers(context, group)

    # Find the source modifier reference to get its fcurve info
    source_ref = None
    for ref in group.modifier_references:
        modifier = get_modifier_by_reference(context, ref)
        if modifier == source_modifier:
            source_ref = ref
            break

    for ref in group.modifier_references:
        modifier = get_modifier_by_reference(context, ref)
        if not modifier or modifier == source_modifier:
            continue

        # Create a unique seed for this specific curve using multiple factors
        # This ensures each curve gets a truly different random value
        seed_string = f"{group.name}_{ref.fcurve_data_path}_{ref.fcurve_array_index}_{ref.modifier_name}"
        seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
        seed_value = int(seed_hash[:8], 16)  # Use first 8 hex chars as seed

        # Generate offset randomization
        random.seed(seed_value)
        offset_random_factor = random.uniform(-1.0, 1.0)

        # Generate phase randomization with different seed
        random.seed(seed_value + 12345)  # Offset seed for phase
        phase_random_factor = random.uniform(-1.0, 1.0)

        # Sync properties based on modifier type
        if group.modifier_type == ModifierType.NOISE:
            if hasattr(source_modifier, "blend_type"):
                modifier.blend_type = source_modifier.blend_type
            if hasattr(source_modifier, "scale"):
                modifier.scale = source_modifier.scale
            if hasattr(source_modifier, "strength"):
                modifier.strength = source_modifier.strength
            if hasattr(source_modifier, "offset"):
                # Apply randomized offset: base value + (random factor * amplitude * multiplier)
                offset_amplitude = abs(source_modifier.offset) if source_modifier.offset != 0 else 100.0
                offset_variation = offset_random_factor * offset_amplitude * group.random_offset
                modifier.offset = source_modifier.offset + offset_variation
            if hasattr(source_modifier, "phase"):
                # Apply randomized phase: base value + (random factor * amplitude * multiplier)
                phase_amplitude = abs(source_modifier.phase) if source_modifier.phase != 0 else 1.0
                phase_variation = phase_random_factor * phase_amplitude * group.random_phase
                modifier.phase = source_modifier.phase + phase_variation
            if hasattr(source_modifier, "depth"):
                modifier.depth = source_modifier.depth
            if hasattr(source_modifier, "lacunarity"):
                modifier.lacunarity = source_modifier.lacunarity
            if hasattr(source_modifier, "roughness"):
                modifier.roughness = source_modifier.roughness

        elif group.modifier_type == ModifierType.FNGENERATOR:
            if hasattr(source_modifier, "function_type"):
                modifier.function_type = source_modifier.function_type
            if hasattr(source_modifier, "use_additive"):
                modifier.use_additive = source_modifier.use_additive
            if hasattr(source_modifier, "amplitude"):
                modifier.amplitude = source_modifier.amplitude
            if hasattr(source_modifier, "phase_multiplier"):
                modifier.phase_multiplier = source_modifier.phase_multiplier
            if hasattr(source_modifier, "phase_offset"):
                # Apply randomized phase offset
                phase_amplitude = abs(source_modifier.phase_offset) if source_modifier.phase_offset != 0 else 1.0
                phase_variation = phase_random_factor * phase_amplitude * group.random_phase
                modifier.phase_offset = source_modifier.phase_offset + phase_variation
            if hasattr(source_modifier, "value_offset"):
                # Apply randomized value offset
                value_amplitude = abs(source_modifier.value_offset) if source_modifier.value_offset != 0 else 1.0
                offset_variation = offset_random_factor * value_amplitude * group.random_offset
                modifier.value_offset = source_modifier.value_offset + offset_variation

        elif group.modifier_type == ModifierType.CYCLES:
            if hasattr(source_modifier, "mode_before"):
                modifier.mode_before = source_modifier.mode_before
            if hasattr(source_modifier, "cycles_before"):
                modifier.cycles_before = source_modifier.cycles_before
            if hasattr(source_modifier, "mode_after"):
                modifier.mode_after = source_modifier.mode_after
            if hasattr(source_modifier, "cycles_after"):
                modifier.cycles_after = source_modifier.cycles_after

        elif group.modifier_type == ModifierType.LIMITS:
            if hasattr(source_modifier, "use_min_x"):
                modifier.use_min_x = source_modifier.use_min_x
            if hasattr(source_modifier, "min_x"):
                modifier.min_x = source_modifier.min_x
            if hasattr(source_modifier, "use_min_y"):
                modifier.use_min_y = source_modifier.use_min_y
            if hasattr(source_modifier, "min_y"):
                modifier.min_y = source_modifier.min_y

        elif group.modifier_type == ModifierType.STEPPED:
            if hasattr(source_modifier, "frame_step"):
                modifier.frame_step = source_modifier.frame_step
            if hasattr(source_modifier, "frame_offset"):
                # Apply randomized frame offset
                offset_amplitude = abs(source_modifier.frame_offset) if source_modifier.frame_offset != 0 else 10.0
                offset_variation = offset_random_factor * offset_amplitude * group.random_offset
                modifier.frame_offset = source_modifier.frame_offset + int(offset_variation)
            if hasattr(source_modifier, "use_frame_start"):
                modifier.use_frame_start = source_modifier.use_frame_start
            if hasattr(source_modifier, "frame_start"):
                modifier.frame_start = source_modifier.frame_start
            if hasattr(source_modifier, "use_frame_end"):
                modifier.use_frame_end = source_modifier.use_frame_end
            if hasattr(source_modifier, "frame_end"):
                modifier.frame_end = source_modifier.frame_end


def sync_group_properties_to_modifiers(context, group):
    """
    Synchronize group properties to all modifiers in the group.

    Important: The GUI pins system and Blender modifiers have different conventions:
    - GUI pins: main pins define 100% effect area, blend pins extend outside for blending
    - Modifiers: start/end define total effect area, blend_in/out eat inward from boundaries

    So we map:
    - modifier.frame_start = group.blend_start_frame (leftmost GUI pin)
    - modifier.frame_end = group.blend_end_frame (rightmost GUI pin)
    - modifier.blend_in = distance from left boundary to main start
    - modifier.blend_out = distance from main end to modifier end
    """

    modifiers = get_all_group_modifiers(context, group)

    for i, modifier in enumerate(modifiers):
        # Set influence
        # modifier.influence = group.influence

        # Calculate base frame range
        base_frame_start = group.blend_start_frame
        base_frame_end = group.blend_end_frame

        # Apply random range if enabled
        if group.random_range > 0.0:
            # Create unique seed for range randomization
            range_seed_string = f"{group.name}_range_{i}"
            range_seed_hash = hashlib.md5(range_seed_string.encode()).hexdigest()
            range_seed_value = int(range_seed_hash[:8], 16)

            # Calculate the total range and center
            total_range = base_frame_end - base_frame_start
            center_frame = (base_frame_start + base_frame_end) / 2

            # Generate random factors for making the range "fuzzier" (expand/contract around center)
            random.seed(range_seed_value)
            start_fuzz_factor = random.uniform(-1.0, 1.0)  # How much to move start boundary
            random.seed(range_seed_value + 11111)  # Different seed for end
            end_fuzz_factor = random.uniform(-1.0, 1.0)  # How much to move end boundary

            # Calculate maximum fuzziness (how much each boundary can move)
            max_fuzz = total_range * 0.2 * group.random_range  # Maximum 20% of range as fuzziness

            # Apply fuzziness: move start inward/outward, end inward/outward
            # Negative values make the range contract, positive values make it expand
            start_fuzz = start_fuzz_factor * max_fuzz
            end_fuzz = end_fuzz_factor * max_fuzz

            # Apply fuzziness to boundaries
            randomized_frame_start = (
                base_frame_start - start_fuzz
            )  # Negative fuzz moves start left (expands), positive moves right (contracts)
            randomized_frame_end = (
                base_frame_end + end_fuzz
            )  # Positive fuzz moves end right (expands), negative moves left (contracts)

            # Ensure start is always before end with minimum gap
            min_gap = max(1.0, total_range * 0.1)  # Minimum 10% of original range or 1 frame
            if randomized_frame_start >= randomized_frame_end:
                # If boundaries crossed, reset to center with minimum gap
                randomized_frame_start = center_frame - min_gap / 2
                randomized_frame_end = center_frame + min_gap / 2
        else:
            randomized_frame_start = base_frame_start
            randomized_frame_end = base_frame_end

        # Enable frame range restriction and set randomized frames
        modifier.use_restricted_range = True
        modifier.frame_start = randomized_frame_start
        modifier.frame_end = randomized_frame_end

        # Calculate base blend values using original group values (not randomized range)
        base_blend_in = max(0, group.main_start_frame - group.blend_start_frame)
        base_blend_out = max(0, group.blend_end_frame - group.main_end_frame)

        # Apply randomization to blend values if random_blend is enabled
        if group.random_blend > 0.0:
            # Create unique seed for this modifier using group name and modifier index
            blend_seed_string = f"{group.name}_blend_{i}"
            blend_seed_hash = hashlib.md5(blend_seed_string.encode()).hexdigest()
            blend_seed_value = int(blend_seed_hash[:8], 16)

            # Generate separate random factors for blend_in and blend_out (including random signs)
            random.seed(blend_seed_value)
            blend_in_random_factor = random.uniform(-1.0, 1.0)  # Already includes random sign
            random.seed(blend_seed_value + 54321)  # Different seed for blend_out
            blend_out_random_factor = random.uniform(-1.0, 1.0)  # Already includes random sign

            # Apply randomization to blend_in (beginning) - allow truly random variations
            if hasattr(modifier, "blend_in"):
                if base_blend_in > 0:
                    # Use base value as amplitude for variation, with random sign
                    blend_in_variation = blend_in_random_factor * base_blend_in * group.random_blend
                    new_blend_in = base_blend_in + blend_in_variation
                    # Clamp to reasonable bounds: allow negative but not too extreme
                    modifier.blend_in = max(-base_blend_in * 0.5, min(base_blend_in * 2.0, new_blend_in))
                else:
                    # If base is 0, create small random variation around 0
                    default_amplitude = 5.0  # 5 frames as default amplitude
                    blend_in_variation = blend_in_random_factor * default_amplitude * group.random_blend
                    modifier.blend_in = max(0, blend_in_variation)  # Don't go negative when base is 0

            # Apply randomization to blend_out (end) - allow truly random variations
            if hasattr(modifier, "blend_out"):
                if base_blend_out > 0:
                    # Use base value as amplitude for variation, with random sign
                    blend_out_variation = blend_out_random_factor * base_blend_out * group.random_blend
                    new_blend_out = base_blend_out + blend_out_variation
                    # Clamp to reasonable bounds: allow negative but not too extreme
                    modifier.blend_out = max(-base_blend_out * 0.5, min(base_blend_out * 2.0, new_blend_out))
                else:
                    # If base is 0, create small random variation around 0
                    default_amplitude = 5.0  # 5 frames as default amplitude
                    blend_out_variation = blend_out_random_factor * default_amplitude * group.random_blend
                    modifier.blend_out = max(0, blend_out_variation)  # Don't go negative when base is 0
        else:
            # No randomization, use base values
            if hasattr(modifier, "blend_in"):
                modifier.blend_in = base_blend_in
            if hasattr(modifier, "blend_out"):
                modifier.blend_out = base_blend_out


def select_group_fcurves(context, group):
    """Select and unhide all F-curves associated with a modifier group."""
    if not context.object or not context.object.animation_data:
        return

    action = context.object.animation_data.action
    if not action:
        return

    # Safely deselect all objects in the scene (context-safe method)
    # First check if we need to change mode
    original_mode = None
    if context.object and hasattr(context.object, "mode"):
        original_mode = context.object.mode

    try:
        # If we're not in object mode, temporarily switch to it for object selection
        if original_mode and original_mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except RuntimeError as e:
                # If we can't switch modes, use the context-safe method
                print(f"Warning: Could not switch to object mode: {e}")
                pass

        # Try the operator-based method first (more reliable when possible)
        try:
            bpy.ops.object.select_all(action="DESELECT")
        except RuntimeError:
            # Fallback to context-safe method if operator fails
            for obj in context.scene.objects:
                obj.select_set(False)
    except Exception as e:
        print(f"Warning: Error during object deselection: {e}")
        # Final fallback - use direct property access
        for obj in context.scene.objects:
            obj.select_set(False)

    # Find the object that owns the F-curves in this group
    owner_object = None

    # For slotted actions (4.4+), we need to find the object with the correct slot
    if hasattr(action, "is_action_layered") and action.is_action_layered:
        # Get slot information from the first reference
        target_slot_handle = None
        target_slot_identifier = None

        for ref in group.modifier_references:
            if ref.action_slot_handle != -1:
                target_slot_handle = ref.action_slot_handle
                target_slot_identifier = ref.action_slot_identifier
                break

        # Search for object with this action and slot
        for obj in context.scene.objects:
            if obj.animation_data and obj.animation_data.action == action:
                # Check if this object has the correct slot active
                if hasattr(obj.animation_data, "action_slot") and obj.animation_data.action_slot:
                    current_slot = obj.animation_data.action_slot

                    # Match by handle first (most reliable)
                    if target_slot_handle is not None and current_slot.handle == target_slot_handle:
                        owner_object = obj
                        break

                    # Fallback to identifier match
                    elif target_slot_identifier and current_slot.identifier == target_slot_identifier:
                        owner_object = obj
                        break
    else:
        # Non-slotted action (4.3 and earlier) - find any object with this action
        for obj in context.scene.objects:
            if obj.animation_data and obj.animation_data.action == action:
                # Verify this object actually has the F-curves from our group
                original_active = context.view_layer.objects.active
                context.view_layer.objects.active = obj

                has_group_fcurves = False
                for ref in group.modifier_references:
                    fcurve = get_fcurve_by_reference(context, ref)
                    if fcurve:
                        has_group_fcurves = True
                        break

                # Restore original active object
                context.view_layer.objects.active = original_active

                if has_group_fcurves:
                    owner_object = obj
                    break

    # Select only the owner object
    if owner_object:
        try:
            owner_object.select_set(True)
            context.view_layer.objects.active = owner_object

            # For slotted actions, ensure we set the correct slot
            if hasattr(action, "is_action_layered") and action.is_action_layered:
                if hasattr(owner_object.animation_data, "action_slot"):
                    # Find and set the correct slot
                    for ref in group.modifier_references:
                        if ref.action_slot_handle != -1:
                            slot = find_slot_by_reference(action, ref)
                            if slot:
                                owner_object.animation_data.action_slot = slot
                                break

            # If it's an armature, try to handle bone selection issues
            if owner_object.type == "ARMATURE":
                # Check if any of the F-curves are bone-related and might need special handling
                bone_data_paths = []
                for ref in group.modifier_references:
                    if ref.fcurve_data_path and (
                        "pose.bones[" in ref.fcurve_data_path or "bones[" in ref.fcurve_data_path
                    ):
                        bone_data_paths.append(ref.fcurve_data_path)

                if bone_data_paths:
                    # Extract bone names and check if they exist and are visible
                    import re

                    hidden_bones = []
                    missing_bones = []

                    for data_path in bone_data_paths:
                        # Extract bone name from data path like 'pose.bones["Bone.001"].location'
                        bone_match = re.search(r'pose\.bones\["([^"]+)"\]|bones\["([^"]+)"\]', data_path)
                        if bone_match:
                            bone_name = bone_match.group(1) or bone_match.group(2)

                            # Check if bone exists
                            if bone_name in owner_object.data.bones:
                                bone = owner_object.data.bones[bone_name]
                                # Check if bone is hidden
                                if bone.hide:
                                    hidden_bones.append(bone_name)
                            else:
                                missing_bones.append(bone_name)

                    # Report issues if any
                    if hidden_bones or missing_bones:
                        warning_msg = "Modifier group selection issues detected:\n"
                        if hidden_bones:
                            warning_msg += f"Hidden bones: {', '.join(hidden_bones[:3])}"
                            if len(hidden_bones) > 3:
                                warning_msg += f" and {len(hidden_bones) - 3} more"
                            warning_msg += "\n"
                        if missing_bones:
                            warning_msg += f"Missing bones: {', '.join(missing_bones[:3])}"
                            if len(missing_bones) > 3:
                                warning_msg += f" and {len(missing_bones) - 3} more"

                        print(f"Warning: {warning_msg}")
                        # Store warning for UI display if needed
                        if hasattr(context.window_manager, "amp_modifier_warning"):
                            context.window_manager.amp_modifier_warning = warning_msg

        except Exception as e:
            print(f"Warning: Could not select owner object '{owner_object.name}': {e}")
            # The object might be hidden, deleted, or in a restricted layer
            if hasattr(context.window_manager, "amp_modifier_warning"):
                context.window_manager.amp_modifier_warning = (
                    f"Cannot select object '{owner_object.name}' - it may be hidden, deleted, or on a restricted layer"
                )

    # Restore original mode if we changed it
    if original_mode and original_mode != "OBJECT" and context.object:
        try:
            bpy.ops.object.mode_set(mode=original_mode)
        except RuntimeError as e:
            print(f"Warning: Could not restore original mode '{original_mode}': {e}")

    # Now deselect all F-curves first
    try:
        for fcurve in all_fcurves(action):
            fcurve.select = False
    except Exception as e:
        print(f"Warning: Error deselecting F-curves: {e}")

    # Then select and unhide only the group's F-curves
    selected_count = 0
    failed_count = 0
    for ref in group.modifier_references:
        try:
            fcurve = get_fcurve_by_reference(context, ref)
            if fcurve:
                fcurve.select = True
                fcurve.hide = False
                selected_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"Warning: Could not select F-curve for reference {ref.fcurve_data_path}: {e}")
            failed_count += 1

    # Report selection results
    if failed_count > 0:
        warning_msg = f"Selected {selected_count} F-curves, but {failed_count} F-curves could not be found or selected. They may be from deleted or hidden elements."
        print(f"Warning: {warning_msg}")
        if hasattr(context.window_manager, "amp_modifier_warning"):
            context.window_manager.amp_modifier_warning = warning_msg
    else:
        # Clear any previous warnings if selection was successful
        if hasattr(context.window_manager, "amp_modifier_warning"):
            context.window_manager.amp_modifier_warning = ""


def ensure_group_fcurves_selected(context, group):
    """Efficiently ensure all F-curves in group are selected without deselecting others."""
    if not context.object or not context.object.animation_data:
        return False

    action = context.object.animation_data.action
    if not action:
        return False

    any_reselected = False
    # Only select group F-curves that aren't already selected
    for ref in group.modifier_references:
        fcurve = get_fcurve_by_reference(context, ref)
        if fcurve and not fcurve.select:
            fcurve.select = True
            fcurve.hide = False
            any_reselected = True

    return any_reselected


def get_group_animation_name(context, group):
    """Get the name of the animation action associated with a modifier group."""
    if not context.object or not context.object.animation_data:
        return "No Animation"

    action = context.object.animation_data.action
    if not action:
        return "No Action"

    return action.name


def get_selected_keyframes_range(context):
    """Get the frame range of selected keyframes from selected F-curves."""
    if not context.selected_editable_fcurves:
        return None

    min_frame = float("inf")
    max_frame = float("-inf")
    has_selected_keyframes = False

    for fcurve in context.selected_editable_fcurves:
        for keyframe in fcurve.keyframe_points:
            if keyframe.select_control_point:
                has_selected_keyframes = True
                frame = keyframe.co[0]
                min_frame = min(min_frame, frame)
                max_frame = max(max_frame, frame)

    if has_selected_keyframes:
        return (min_frame, max_frame)
    return None


def get_fcurves_frame_range(context):
    """Get the frame range from all selected F-curves (all keyframes, not just selected ones)."""
    if not context.selected_editable_fcurves:
        return None

    min_frame = float("inf")
    max_frame = float("-inf")
    has_keyframes = False

    for fcurve in context.selected_editable_fcurves:
        if fcurve.keyframe_points:
            has_keyframes = True
            for keyframe in fcurve.keyframe_points:
                frame = keyframe.co[0]
                min_frame = min(min_frame, frame)
                max_frame = max(max_frame, frame)

    if has_keyframes:
        return (min_frame, max_frame)
    return None


def get_smart_frame_range(context):
    """Get smart frame range: selected keyframes first, then all keyframes from selected F-curves, then scene range."""
    # First try to get range from selected keyframes
    selected_range = get_selected_keyframes_range(context)
    if selected_range:
        return selected_range

    # Then try to get range from all keyframes in selected F-curves
    fcurves_range = get_fcurves_frame_range(context)
    if fcurves_range:
        return fcurves_range

    # Finally fall back to scene frame range
    scene = context.scene
    return (scene.frame_start, scene.frame_end)


def get_animation_slot_layer_info(context):
    """Get animation slot and layer information for Blender 4.4+."""
    try:
        # Check if we're in Blender 4.4+ with animation layers support
        if hasattr(bpy.app, "version") and bpy.app.version >= (4, 4, 0):
            obj = context.object
            if obj and obj.animation_data:
                # Get current slot and layer info
                slot_info = "Default Slot"
                layer_info = "Base Layer"

                # Try to get slot information
                if hasattr(obj.animation_data, "action_slot"):
                    slot = obj.animation_data.action_slot
                    if slot:
                        slot_info = slot.name

                # Try to get layer information
                if hasattr(obj.animation_data, "action") and obj.animation_data.action:
                    action = obj.animation_data.action
                    if hasattr(action, "layers") and action.layers:
                        # Get active layer
                        for layer in action.layers:
                            if getattr(layer, "is_active", False):
                                layer_info = layer.name
                                break

                return slot_info, layer_info
    except Exception:
        pass

    return None, None


# ============================================================================
# SLOT-AWARE UI HELPERS
# ============================================================================


def get_slot_aware_modifier_references(context, group):
    """Get modifier references that are appropriate for the current slot context."""
    if not context.object or not context.object.animation_data:
        return []

    action = context.object.animation_data.action
    if not action:
        return []

    # If this is not a slotted action, return all references
    if not (hasattr(action, "is_action_layered") and action.is_action_layered):
        return list(group.modifier_references)

    # For slotted actions, filter by current slot
    current_slot_handle, current_slot_identifier = get_current_slot_info(context)
    if current_slot_handle is None:
        return []

    slot_references = []
    for ref in group.modifier_references:
        # Check if this reference belongs to the current slot
        if ref.action_slot_handle == current_slot_handle:
            slot_references.append(ref)
        elif ref.action_slot_handle == -1 and ref.action_slot_identifier == current_slot_identifier:
            # Fallback: Match by identifier if handle not set
            slot_references.append(ref)
        elif ref.action_slot_handle == -1 and ref.action_slot_identifier == "":
            # Legacy reference without slot info - try to validate if it's in current slot
            fcurve = get_fcurve_by_reference(context, ref)
            if fcurve:
                slot_references.append(ref)

    return slot_references


def get_slot_aware_group_modifiers(context, group):
    """Get all modifiers from F-curves that belong to the current slot."""
    if not context.object or not context.object.animation_data:
        return []

    action = context.object.animation_data.action
    if not action:
        return []

    modifiers = []

    # Get slot-appropriate references
    slot_references = get_slot_aware_modifier_references(context, group)

    # Collect modifiers from F-curves
    for ref in slot_references:
        fcurve = get_fcurve_by_reference(context, ref)
        if fcurve:
            for modifier in fcurve.modifiers:
                if modifier.name == ref.modifier_name and modifier.type == ref.modifier_type:
                    modifiers.append(modifier)

    return modifiers


def ensure_slot_aware_group_fcurves_selected(context, group):
    """Select F-curves in the group that belong to the current slot."""
    if not context.object or not context.object.animation_data:
        return False

    action = context.object.animation_data.action
    if not action:
        return False

    any_reselected = False

    # Get slot-appropriate references
    slot_references = get_slot_aware_modifier_references(context, group)

    # Only select group F-curves that aren't already selected
    for ref in slot_references:
        fcurve = get_fcurve_by_reference(context, ref)
        if fcurve and not fcurve.select:
            fcurve.select = True
            fcurve.hide = False
            any_reselected = True

    return any_reselected


def has_slot_aware_modifiers(context, group):
    """Check if a group has any modifiers in the current slot context."""
    slot_references = get_slot_aware_modifier_references(context, group)
    return len(slot_references) > 0


def get_slot_aware_modifier_count(context, group):
    """Get the count of modifiers in the current slot context."""
    slot_references = get_slot_aware_modifier_references(context, group)
    return len(slot_references)


# ============================================================================
# REGISTRATION
# ============================================================================


def register():
    bpy.utils.register_class(AMP_PG_ModifierReference)
    bpy.utils.register_class(AMP_PG_ModifierGroup)
    bpy.utils.register_class(AMP_PG_AnimModifiersSettings)

    # Register on WindowManager for better cross-version compatibility and pointer storage
    bpy.types.WindowManager.amp_anim_modifiers = PointerProperty(
        type=AMP_PG_AnimModifiersSettings,
        name="AMP Animation Modifiers",
        description="AniMate Pro animation modifiers settings",
    )

    # Add a property for storing warnings about modifier group operations
    bpy.types.WindowManager.amp_modifier_warning = StringProperty(
        name="Modifier Warning",
        description="Warning message about modifier group operations",
        default="",
    )


def unregister():
    """Unregister property groups."""
    # Remove from window manager
    if hasattr(bpy.types.WindowManager, "amp_anim_modifiers"):
        del bpy.types.WindowManager.amp_anim_modifiers

    if hasattr(bpy.types.WindowManager, "amp_modifier_warning"):
        del bpy.types.WindowManager.amp_modifier_warning

    bpy.utils.unregister_class(AMP_PG_AnimModifiersSettings)
    bpy.utils.unregister_class(AMP_PG_ModifierGroup)
    bpy.utils.unregister_class(AMP_PG_ModifierReference)


if __name__ == "__main__":
    register()
