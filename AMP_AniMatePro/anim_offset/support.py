# licence
"""
Copyright (C) 2018 Ares Deveaux


Created by Ares Deveaux

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import bpy
import os
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.types import SpaceGraphEditor
from .. import utils

from .. import __package__ as base_package

# Anim_transform global variables
user_preview_range = {}
user_scene_range = {}
global_values = {}
last_op = None


# ---------- Main Tool ------------


def auto_center_frame_in_mask_range(context):
    """
    Auto-center the current frame to the middle of the mask range if the current frame
    is outside the 100% influence area (between main pins).
    """
    scene = context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset

    if not anim_offset.mask_in_use:
        return False

    # Get the mask F-curve to determine the main pin positions
    blends_action = bpy.data.actions.get("amp_action")
    if not blends_action:
        return False

    blends_curves = list(utils.curve.all_fcurves(blends_action))
    if not blends_curves or len(blends_curves) == 0:
        return False

    blend_curve = blends_curves[0]
    keys = blend_curve.keyframe_points

    if len(keys) < 4:
        return False

    # Extract main pin positions (keys 1 and 2 are the main pins with 100% influence)
    main_left_frame = keys[1].co.x
    main_right_frame = keys[2].co.x

    # Get current frame in action time (accounting for NLA offset)
    current_frame = scene.frame_current
    if context.active_object and context.active_object.animation_data:
        current_action_frame = context.active_object.animation_data.nla_tweak_strip_time_to_scene(
            current_frame, invert=True
        )
    else:
        current_action_frame = current_frame

    # Check if current frame is outside the 100% influence area (between main pins)
    if current_action_frame < main_left_frame or current_action_frame > main_right_frame:
        # Calculate center frame between main pins and round to full frame
        center_frame = (main_left_frame + main_right_frame) / 2
        center_frame_rounded = round(center_frame)

        # Convert back to scene time if needed
        if context.active_object and context.active_object.animation_data:
            scene_center_frame = context.active_object.animation_data.nla_tweak_strip_time_to_scene(
                center_frame_rounded
            )
        else:
            scene_center_frame = center_frame_rounded

        # Move the current frame to the center
        scene.frame_current = int(scene_center_frame)
        return True
    # No centering needed
    return False


def magnet_handlers(scene):
    """Function to be run by the anim_offset Handler"""

    global last_op

    context = bpy.context

    # Check if the current context is the Graph Editor
    if context.area and context.area.type == "GRAPH_EDITOR":
        # utils.dprint("Graph Editor")
        return

    anim_offset = scene.amp_timeline_tools.anim_offset

    # Auto-center frame FIRST if mask is in use and current frame is outside the 100% influence area
    # If centering occurred, exit early to safeguard transformations
    if anim_offset.mask_in_use:
        if auto_center_frame_in_mask_range(context):
            return

    external_op = context.active_operator

    if context.scene.tool_settings.use_keyframe_insert_auto or (context.mode != "OBJECT" and context.mode != "POSE"):

        utils.amp_draw_header_handler(action="REMOVE")
        if anim_offset.mask_in_use:
            remove_mask(context)
            reset_timeline_mask(context)

        bpy.app.handlers.depsgraph_update_post.remove(magnet_handlers)
        utils.remove_message()
        return

    if anim_offset.mask_in_use:
        # Check if we're outside the mask range and should add keys
        blends_action = bpy.data.actions.get("amp_action")
        blends_curves = list(utils.curve.all_fcurves(blends_action)) if blends_action else None

        if blends_curves is not None and len(blends_curves) > 0:
            blends_curve = blends_curves[0]
            current_frame = context.scene.frame_current
            current_factor = blends_curve.evaluate(current_frame)

            # If we're outside the influence area (factor close to 0) and auto-key is enabled
            if current_factor < 0.1 and anim_offset.insert_outside_keys:
                add_keys(context)
                return

    # if external_op is last_op and anim_offset.fast_mask:
    pref = context.preferences.addons[base_package].preferences
    if external_op is last_op and pref.ao_fast_offset:
        return
    last_op = context.active_operator

    # context.scene.tool_settings.use_keyframe_insert_auto = False

    selected_objects = context.selected_objects

    for obj in selected_objects:
        # Use get_active_fcurves_obj to get FCurves specific to this object's slot
        for fcurve in utils.curve.get_active_fcurves_obj(obj):
            if fcurve.data_path.endswith("rotation_mode"):
                continue
            magnet(context, obj, fcurve)

    return


def magnet(context, obj, fcurve):
    """Modify all the keys in every fcurve of the current object proportionally to the change in transformation
    on the current frame by the user"""

    scene = context.scene

    # Exit conditions
    if fcurve.lock:
        return
    if getattr(fcurve.group, "name", None) == "amp_action":
        return

    # Prepare for change detection
    changes_detected = False  # Flag to track if any changes were made

    blends_action = bpy.data.actions.get("amp_action")
    blends_curves = list(utils.curve.all_fcurves(blends_action)) if blends_action else None

    delta_y = get_delta(context, obj, fcurve)

    for k in fcurve.keyframe_points:
        # Determine the factor for modification
        if not context.scene.amp_timeline_tools.anim_offset.mask_in_use:
            factor = 1
        elif blends_curves is not None and len(blends_curves) > 0:
            # Use the mask F-curve to determine influence
            blends_curve = blends_curves[0]
            keyframe_scene_time = context.active_object.animation_data.nla_tweak_strip_time_to_scene(k.co.x)
            factor = blends_curve.evaluate(keyframe_scene_time)
        else:
            factor = 0

        # Calculate the new value
        new_y = k.co_ui.y + (delta_y * factor)

        # Check if the new value is different from the current one
        if k.co_ui.y != new_y:
            k.co_ui.y = new_y  # Apply the change
            changes_detected = True  # Mark that a change was detected

    # Update the fcurve only if changes were detected
    if changes_detected:
        fcurve.update()


def get_delta(context, obj, fcurve):
    """Determine the transformation change by the user of the current object"""
    current_frame = context.active_object.animation_data.nla_tweak_strip_time_to_scene(
        context.scene.frame_current, invert=True
    )

    curve_value = fcurve.evaluate(current_frame)

    try:
        prop = obj.path_resolve(fcurve.data_path)
    except:
        print(f"Failed to resolve path: {fcurve.data_path}")
        return 0

    if prop:
        try:
            target = prop[fcurve.array_index]
        except TypeError:
            target = prop

        # Enhanced type check with debug information
        if isinstance(target, (int, float)):
            return target - curve_value
        else:
            return 0
    else:
        return 0


# ----------- Mask -----------


def add_blends():
    """Add a curve with 4 control points to an action called 'amp_anim' that would act as a mask for anim_offset"""
    action = utils.set_amp_timeline_tools_action()
    # Clear existing F-Curves to ensure a fresh start
    fcurves = utils.curve.all_fcurves(action)
    # fcurves.clear()
    for fc in fcurves:
        utils.curve.remove_fcurve_from_action(action, fc)
    # Add a new F-Curve with four control points
    return utils.curve.new("Magnet", 4)


def remove_mask(context):
    """Removes the fcurve and action that are been used as a mask for anim_offset"""

    anim_offset = context.scene.amp_timeline_tools.anim_offset
    blends_action = bpy.data.actions.get("amp_action")
    blends_curves = list(utils.curve.all_fcurves(blends_action)) if blends_action else None

    if blends_curves is not None and len(blends_curves) > 0:
        utils.curve.remove_fcurve_from_action(blends_action, blends_curves[0])
        # reset_timeline_mask(context)

    # delete action
    if blends_action is not None:

        bpy.data.actions.remove(blends_action)

    anim_offset.mask_in_use = False

    return


def set_blend_values(context):
    """Modify the position of the fcurve 4 control points that is been used as mask to anim_offset"""

    scene = context.scene
    blends_action = bpy.data.actions.get("amp_action")
    blends_curves = list(utils.curve.all_fcurves(blends_action)) if blends_action else None

    if blends_curves is not None:
        blend_curve = blends_curves[0]
        keys = blend_curve.keyframe_points

        if len(keys) < 4:
            utils.dprint(f"Error: Not enough keyframe points in the F-Curve. {len(keys)} points found.")
            utils.dprint(f"{keys}")
            # Optionally, add missing keyframe points here
            return

        left_blend = scene.frame_preview_start
        left_margin = scene.frame_start
        right_margin = scene.frame_end
        right_blend = scene.frame_preview_end

        keys[0].co.x = left_blend
        keys[0].co.y = 0
        keys[1].co.x = left_margin
        keys[1].co.y = 1
        keys[2].co.x = right_margin
        keys[2].co.y = 1
        keys[3].co.x = right_blend
        keys[3].co.y = 0

        mask_interpolation(keys, context)


def set_blend_values_from_pins(context, pin_positions, start_blend="linear", end_blend="linear"):
    """
    Modify the position of the fcurve 4 control points using pin positions.

    Args:
        context: Blender context
        pin_positions: List of 4 frame positions [secondary_left, main_left, main_right, secondary_right]
        start_blend: Blend type for left side (linear, quadratic_in, quadratic_out, cubic_in, cubic_out)
        end_blend: Blend type for right side (linear, quadratic_in, quadratic_out, cubic_in, cubic_out)
    """
    blends_action = bpy.data.actions.get("amp_action")
    blends_curves = list(utils.curve.all_fcurves(blends_action)) if blends_action else None

    if blends_curves is not None and len(pin_positions) >= 4:
        blend_curve = blends_curves[0]
        keys = blend_curve.keyframe_points

        if len(keys) < 4:
            utils.dprint(f"Error: Not enough keyframe points in the F-Curve. {len(keys)} points found.")
            return

        secondary_left, main_left, main_right, secondary_right = pin_positions

        # Set keyframe positions and values based on pin positions
        keys[0].co.x = secondary_left
        keys[0].co.y = 0
        keys[1].co.x = main_left
        keys[1].co.y = 1
        keys[2].co.x = main_right
        keys[2].co.y = 1
        keys[3].co.x = secondary_right
        keys[3].co.y = 0

        # Apply blend types to mask interpolation
        mask_interpolation_with_blend_types(keys, context, start_blend, end_blend)


def mask_interpolation_with_blend_types(keys, context, start_blend, end_blend):
    """
    Apply interpolation to mask keys based on GUI pin blend types.

    Args:
        keys: F-curve keyframe points
        context: Blender context
        start_blend: Blend type for left side
        end_blend: Blend type for right side
    """

    def gui_blend_to_blender_interp(blend_type):
        """Convert GUI pin blend type to Blender interpolation and easing."""
        blend_map = {
            "linear": ("LINEAR", "EASE_IN_OUT"),
            "quadratic_in": ("CUBIC", "EASE_IN"),
            "quadratic_out": ("CUBIC", "EASE_OUT"),
            "quadratic_in_out": ("CUBIC", "EASE_IN_OUT"),
            "cubic_in": ("CUBIC", "EASE_IN"),
            "cubic_out": ("CUBIC", "EASE_OUT"),
            "cubic_in_out": ("CUBIC", "EASE_IN_OUT"),
            "exponential_in": ("EXPO", "EASE_IN"),
            "exponential_out": ("EXPO", "EASE_OUT"),
            "exponential_in_out": ("EXPO", "EASE_IN_OUT"),
        }
        return blend_map.get(blend_type, ("LINEAR", "EASE_IN_OUT"))

    # Get interpolation settings for start and end blends
    start_interp, start_easing = gui_blend_to_blender_interp(start_blend)
    end_interp, end_easing = gui_blend_to_blender_interp(end_blend)

    # Apply interpolation to the mask keys
    # Key 0: Start blend (secondary_left to main_left)
    keys[0].interpolation = start_interp
    keys[0].easing = start_easing

    # Key 1: Middle plateau (main_left to main_right) - always linear
    keys[1].interpolation = "LINEAR"
    keys[1].easing = "EASE_IN_OUT"

    # Key 2: End blend (main_right to secondary_right)
    keys[2].interpolation = end_interp
    keys[2].easing = end_easing

    # Key 3: End point - no interpolation after this
    keys[3].interpolation = "LINEAR"
    keys[3].easing = "EASE_IN_OUT"


def mask_interpolation(keys, context):
    anim_offset = context.scene.amp_timeline_tools.anim_offset
    interp = anim_offset.interp
    easing = anim_offset.easing

    oposite = None

    if easing == "EASE_IN":
        oposite = "EASE_OUT"
    elif easing == "EASE_OUT":
        oposite = "EASE_IN"
    elif easing == "EASE_IN_OUT":
        oposite = "EASE_IN_OUT"

    keys[0].interpolation = interp
    keys[0].easing = easing
    keys[1].interpolation = "LINEAR"
    keys[1].easing = "EASE_IN_OUT"
    keys[2].interpolation = interp
    keys[2].easing = oposite


def add_keys(context):
    selected_objects = context.selected_objects

    for obj in selected_objects:
        # Use get_active_fcurves_obj to get FCurves specific to this object's slot
        for fcurve in utils.curve.get_active_fcurves_obj(obj):

            if fcurve.lock:
                return

            if getattr(fcurve.group, "name", None) == "amp_timeline_tools":
                return  # we don't want to select keys on reference fcurves

            keys = fcurve.keyframe_points
            cur_index = utils.key.on_current_frame(fcurve)
            delta_y = get_delta(context, obj, fcurve)

            if not cur_index:
                cur_frame = context.scene.frame_current
                y = fcurve.evaluate(cur_frame) + delta_y
                utils.key.insert_key(keys, cur_frame, y)
            else:
                key = keys[cur_index]
                key.co_ui.y += delta_y


# -------- For mask interface -------


def set_timeline_ranges(context, left_blend, left_margin, right_margin, right_blend):
    """Use the timeline playback and preview ranges to represent the mask"""

    scene = context.scene
    scene.use_preview_range = True

    scene.frame_preview_start = left_blend
    scene.frame_start = left_margin
    scene.frame_end = right_margin
    scene.frame_preview_end = right_blend


def reset_timeline_mask(context):
    """Resets the timeline playback and preview ranges to what the user had it as"""

    scene = context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset

    scene.frame_preview_start = anim_offset.user_preview_start
    scene.frame_preview_end = anim_offset.user_preview_end
    scene.use_preview_range = anim_offset.user_preview_use
    scene.frame_start = anim_offset.user_scene_start
    scene.frame_end = anim_offset.user_scene_end
    # scene.tool_settings.use_keyframe_insert_auto = anim_offset.user_scene_auto


def reset_timeline_blends(context):
    """Resets the timeline playback and preview ranges to what the user had it as"""

    scene = context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset

    scene.frame_preview_start = anim_offset.user_preview_start
    scene.frame_preview_end = anim_offset.user_preview_end
    scene.use_preview_range = anim_offset.user_preview_use


def store_user_timeline_ranges(context):
    """Stores the timeline playback and preview ranges"""

    scene = context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset

    anim_offset.user_preview_start = scene.frame_preview_start
    anim_offset.user_preview_end = scene.frame_preview_end
    anim_offset.user_preview_use = scene.use_preview_range
    anim_offset.user_scene_start = scene.frame_start
    anim_offset.user_scene_end = scene.frame_end
    # anim_offset.user_scene_auto = scene.tool_settings.use_keyframe_insert_auto


# ---------- Functions for Operators ------------


def poll(context):
    """Poll for all the anim_offset related operators"""

    objects = context.selected_objects
    area = context.area.type
    return (
        objects
        is not None
        # and area == "GRAPH_EDITOR"
        # or area == "DOPESHEET_EDITOR"
        # or area == "VIEW_3D"
    )


def get_anim_offset_globals(context, obj):
    """Get global values for the anim_offset"""
    anim = obj.animation_data
    if anim is None:
        return

    # Use get_active_fcurves_obj to get FCurves specific to this object's slot
    fcurves = list(utils.curve.get_active_fcurves_obj(obj))
    if not fcurves:
        return

    curves = {}

    for index, fcurve in enumerate(fcurves):
        if fcurve.lock is True:
            continue

        cur_frame = context.scene.frame_current
        cur_frame_y = fcurve.evaluate(cur_frame)
        values = {"x": cur_frame, "y": cur_frame_y}

        curves[index] = {"current_frame": values}

    global_values[obj.name] = curves


def update_blend_range(self, context):
    """Update the mask F-curve when blend range property changes"""
    # Skip if GUI pins system is handling mask updates
    anim_offset = context.scene.amp_timeline_tools.anim_offset
    if anim_offset.mask_in_use:
        # GUI pins system is active - it handles all mask updates
        return

    # Legacy property-based behavior for when GUI pins are not active
    ao_blend_range = anim_offset.ao_blend_range
    ao_mask_range = anim_offset.ao_mask_range
    reference_frame = anim_offset.reference_frame

    # Calculate pin positions from current properties
    center_frame = reference_frame
    main_left = center_frame - ao_mask_range
    main_right = center_frame + ao_mask_range
    secondary_left = main_left - ao_blend_range
    secondary_right = main_right + ao_blend_range

    pin_positions = [secondary_left, main_left, main_right, secondary_right]
    set_blend_values_from_pins(context, pin_positions)


def update_mask_range(self, context):
    """Update the mask F-curve when mask range property changes"""
    # Skip if GUI pins system is handling mask updates
    anim_offset = context.scene.amp_timeline_tools.anim_offset
    if anim_offset.mask_in_use:
        # GUI pins system is active - it handles all mask updates
        return

    # Legacy property-based behavior for when GUI pins are not active
    ao_mask_range = anim_offset.ao_mask_range
    ao_blend_range = anim_offset.ao_blend_range
    reference_frame = anim_offset.reference_frame

    # Calculate pin positions from current properties
    center_frame = reference_frame
    main_left = center_frame - ao_mask_range
    main_right = center_frame + ao_mask_range
    secondary_left = main_left - ao_blend_range
    secondary_right = main_right + ao_blend_range

    pin_positions = [secondary_left, main_left, main_right, secondary_right]
    set_blend_values_from_pins(context, pin_positions)


def autokeying_changed_anim_offset(*args):
    context = bpy.context
    scene = bpy.context.scene
    anim_offset = scene.amp_timeline_tools.anim_offset

    if scene.tool_settings.use_keyframe_insert_auto:

        # bpy.ops.anim.amp_deactivate_anim_offset
        if magnet_handlers in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(magnet_handlers)
            utils.remove_message()

        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        if anim_offset.mask_in_use:
            remove_mask(context)
            reset_timeline_mask(context)

        # scene.tool_settings.use_keyframe_insert_auto = anim_offset.user_scene_auto

        for area in bpy.context.screen.areas:
            area.tag_redraw()

        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        utils.amp_draw_header_handler(action="REMOVE")


def subscribe_to_autokeying_changes_anim_offset():
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.ToolSettings, "use_keyframe_insert_auto"),
        owner="AUTOKEYING_ANIM_OFFSET",
        args=(),
        notify=autokeying_changed_anim_offset,
        options={"PERSISTENT"},
    )


def unsubscribe_from_property_anim_offset():
    bpy.msgbus.clear_by_owner("AUTOKEYING_ANIM_OFFSET")
