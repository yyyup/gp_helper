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
import math
from .. import utils
import numpy as np

group_name = "amp_action"
user_preview_range = {}
user_scene_range = {}


def add_curve3d(context, name, key_amount=0):
    curve_data = bpy.data.curves.new(name, "CURVE")
    spline = curve_data.splines.new("BEZIER")
    if key_amount > 0:
        spline.bezier_points.add(key_amount)
    obj = bpy.data.objects.new(name, curve_data)
    context.collection.objects.link(obj)
    return obj


def new(action_group_name, keys_to_add, key_interp="AUTO_CLAMPED", color=(1, 1, 1)):
    """Adds an F-Curve in the 'amp_action' action with specified control points"""
    action = utils.set_amp_timeline_tools_action()

    # Create a new F-Curve (handling both legacy and slotted actions)
    if hasattr(action, "layers"):
        # Slotted action system (Blender 4.5+)
        if not action.slots:
            slot = action.slots.new(id_type="OBJECT", name="amp_timeline_tools")
        else:
            slot = action.slots[0]

        if not action.layers:
            layer = action.layers.new(name="amp_timeline_tools_layer")
        else:
            layer = action.layers[0]

        if not layer.strips:
            strip = layer.strips.new(type="KEYFRAME")
        else:
            strip = layer.strips[0]

        channelbag = strip.channelbag(slot, ensure=True)
        blends_curve = channelbag.fcurves.new(data_path="Magnet", index=0)

        # Create or get the group
        group = next((g for g in channelbag.groups if g.name == action_group_name), None)
        if group is None:
            group = channelbag.groups.new(action_group_name)
        blends_curve.group = group
    else:
        # Legacy action system (Blender < 4.5)
        blends_curve = action.fcurves.new(data_path="Magnet", index=0, action_group=action_group_name)

    blends_curve.color_mode = "CUSTOM"
    blends_curve.color = color

    # Add keyframe points
    keys = blends_curve.keyframe_points
    keys.add(keys_to_add)

    # Manually set the position for each keyframe point
    # Example positions, adjust as needed for your mask
    if keys_to_add >= 4:
        keys[0].co = (0, 0)
        keys[1].co = (10, 0)
        keys[2].co = (20, 1)
        keys[3].co = (30, 1)

    for k in keys:
        k.handle_left_type = key_interp
        k.handle_right_type = key_interp

    blends_curve.lock = True
    blends_curve.select = True
    blends_curve.update()

    return blends_curve


def create_path(context, fcurves):
    curve_obj = add_curve3d(context, "amp_timeline_tools_path")
    curve_obj.data.dimensions = "3D"
    curve_obj.data.bevel_depth = 0.1

    x = {}
    y = {}
    z = {}
    frames = []
    for fcurve in fcurves:
        if fcurve.data_path == "location":
            for k in fcurve.keyframe_points:
                f = k.co.x
                if f not in frames:
                    frames.append(f)
                if fcurve.array_index == 0:
                    x["curve"] = fcurve
                    x[f] = k.co.y
                elif fcurve.array_index == 1:
                    y["curve"] = fcurve
                    y[f] = k.co.y
                elif fcurve.array_index == 2:
                    z["curve"] = fcurve
                    z[f] = k.co.y
    frames.sort()
    utils.dprint(f"frames: {frames}")
    utils.dprint(f"x: {x}")
    utils.dprint(f"y: {y}")
    utils.dprint(f"z: {z}")
    points = curve_obj.data.splines[0].bezier_points
    points.add(len(frames))
    utils.dprint(f"amount of frames: {len(frames)}")
    n = 0
    for f in frames:
        if x.get(f) is None:
            points[n].co.x = x["curve"].evaluate(f)
        else:
            points[n].co.x = x.get(f)

        if y.get(f) is None:
            points[n].co.y = y["curve"].evaluate(f)
        else:
            points[n].co.y = y.get(f)

        if x.get(f) is None:
            points[n].co.z = z["curve"].evaluate(f)
        else:
            points[n].co.z = z.get(f)

        points[n].handle_left_type = "AUTO"
        points[n].handle_right_type = "AUTO"

        utils.dprint(f"frame: {f}")
        utils.dprint(f"point coordinate: {points[n].co}")
        utils.dprint(f"n: {n}")

        n += 1


def get_selected(fcurves):
    """return selected fcurves in the current action with the exception of the reference fcurves"""

    selected = []

    for fcurve in fcurves:
        if getattr(fcurve.group, "name", None) == group_name:
            continue  # we don't want to add to the list the helper curves we have created

        if fcurve.select:
            selected.append(fcurve)

    return selected


def get_all_fcurves(obj):
    trans_action = obj.animation_data.action
    trans_fcurves = getattr(trans_action, "fcurves", None)
    if trans_fcurves:
        trans_fcurves = trans_fcurves.items()
    else:
        trans_fcurves = []

    if obj.type != "ARMATURE":
        shapes_action = obj.data.shape_keys.animation_data.action
        shapes_fcurves = getattr(shapes_action, "fcurves", None)
        if shapes_fcurves:
            shapes_fcurves = shapes_fcurves.items()
        else:
            shapes_fcurves = []
        return trans_fcurves + shapes_fcurves
    else:
        return trans_fcurves


def remove_helpers(objects):
    """Remove the all the helper curves that have been added to an object action"""

    for obj in objects:
        action = obj.animation_data.action

        for fcurve in all_fcurves(action):
            if getattr(fcurve.group, "name", None) == group_name:
                remove_fcurve_from_action(action, fcurve)


def get_slope(fcurve):
    """Gets the slope of a curve at a specific range"""
    selected_keys = utils.key.get_selected_index(fcurve)
    first_key, last_key = utils.key.first_and_last_selected(fcurve, selected_keys)
    slope = (first_key.co.y**2 - last_key.co.y**2) / (first_key.co.x**2 - last_key.co.x**2)
    return slope


def add_cycle(fcurve, before="MIRROR", after="MIRROR"):
    """Adds cycle modifier to an fcurve"""
    cycle = fcurve.modifiers.new("CYCLES")

    cycle.mode_before = before
    cycle.mode_after = after


def duplicate(fcurve, selected_keys=True, before="NONE", after="NONE", lock=False):
    """Duploicates an fcurve"""

    action = fcurve.id_data
    index = len(all_fcurves(action))

    if selected_keys:
        selected_keys = get_selected(fcurve)
    else:
        selected_keys = fcurve.keyframe_points.items()

    clone_name = "%s.%d.clone" % (fcurve.data_path, fcurve.array_index)

    dup = action.fcurves.new(data_path=clone_name, index=index, action_group=group_name)
    dup.keyframe_points.add(len(selected_keys))
    dup.color_mode = "CUSTOM"
    dup.color = (0, 0, 0)

    dup.lock = lock
    dup.select = False

    groups = get_active_groups(action)
    groups[group_name].lock = lock
    groups[group_name].color_set = "THEME10"

    for i, (index, key) in enumerate(selected_keys):
        dup.keyframe_points[i].co = key.co

    add_cycle(dup, before=before, after=after)

    dup.update()

    return dup


def duplicate_from_data(fcurves, global_fcurve, new_data_path, before="NONE", after="NONE", lock=False):
    """Duplicates a curve using the global values"""

    index = len(fcurves)
    every_key = global_fcurve["every_key"]
    original_keys = global_fcurve["original_keys"]

    dup = fcurves.new(data_path=new_data_path, index=index, action_group=group_name)
    dup.keyframe_points.add(len(every_key))
    dup.color_mode = "CUSTOM"
    dup.color = (0, 0, 0)

    dup.lock = lock
    dup.select = False

    action = fcurves.id_data
    groups = get_active_groups(action)
    groups[group_name].lock = lock
    groups[group_name].color_set = "THEME10"

    i = 0

    for index in every_key:
        dup.keyframe_points[i].co.x = original_keys[index]["x"]
        dup.keyframe_points[i].co.y = original_keys[index]["y"]

        i += 1

    add_cycle(dup, before=before, after=after)

    dup.update()

    return dup


def add_clone(objects, cycle_before="NONE", cycle_after="NONE", selected_keys=False):
    """Create an fcurve clone"""

    for obj in objects:
        fcurves = all_fcurves(obj.animation_data.action)

        for fcurve in fcurves:
            if getattr(fcurve.group, "name", None) == group_name:
                continue  # we don't want to add to the list the helper curves we have created

            if fcurve.hide or not fcurve.select:
                continue

            duplicate(
                fcurve,
                selected_keys=selected_keys,
                before=cycle_before,
                after=cycle_after,
            )

            fcurve.update()


def remove_clone(objects):
    """Removes an fcurve clone"""

    for obj in objects:
        action = obj.animation_data.action
        fcurves = all_fcurves(action)

        amp = bpy.context.scene.amp_timeline_tools
        aclones = amp.clone_data.clones
        clones_n = len(aclones)
        blender_n = len(fcurves) - clones_n

        for n in range(clones_n):
            maybe_clone = fcurves[blender_n]
            if "clone" in maybe_clone.data_path:
                clone = maybe_clone
                remove_fcurve_from_action(action, clone)
                aclones.remove(0)


def move_clone(objects):
    """Moves clone fcurve in time"""

    for obj in objects:
        action = obj.animation_data.action

        amp = bpy.context.scene.amp_timeline_tools
        aclone_data = amp.clone_data
        aclones = aclone_data.clones
        move_factor = aclone_data.move_factor
        fcurves = all_fcurves(action)
        for aclone in aclones:
            clone = fcurves[aclone.fcurve.index]
            fcurve = fcurves[aclone.original_fcurve.index]
            selected_keys = key.get_selected_index(fcurve)
            key1, key2 = key.first_and_last_selected(fcurve, selected_keys)
            amount = abs(key2.co.x - key1.co.x)
            for key in clone.keyframe_points:
                key.co.x = key.co.x + (amount * move_factor)

            clone.update()

            key.attach_selection_to_fcurve(fcurve, clone, is_gradual=False)

            fcurve.update()


def valid_anim(obj):

    anim = obj.animation_data
    action = getattr(anim, "action", None)
    fcurves = getattr(action, "fcurves", None)

    return fcurves


def valid_obj(context, obj, check_ui=True):

    if not valid_anim(obj):
        return False

    if check_ui:
        visible = obj.visible_get()

        if context.area.type != "VIEW_3D":
            if not context.space_data.dopesheet.show_hidden and not visible:
                return False

    return True


def valid_fcurve(context, obj, fcurve, action_type="transfrom_action", check_ui=True):

    if not fcurve:
        return False

    try:
        if action_type == "transfrom_action":
            prop = obj.path_resolve(fcurve.data_path)
        else:
            prop = fcurve.data_path
    except:
        prop = None

    if not prop:
        return False

    if check_ui and context.area.type == "GRAPH_EDITOR":
        if context.space_data.use_only_selected_keyframe_handles and not fcurve.select:
            return False

        # if context.area.type != 'VIEW_3D':
        if fcurve.lock or fcurve.hide:
            return False

    if getattr(fcurve.group, "name", None) == utils.curve.group_name:
        return False  # we don't want to select keys on reference fcurves

    if obj.type == "ARMATURE":

        if getattr(fcurve.group, "name", None) == "Object Transforms":
            # When animating an object, by default its fcurves grouped with this name.
            return False

        elif not fcurve.group:
            transforms = (
                "location",
                "rotation_euler",
                "scale",
                "rotation_quaternion",
                "rotation_axis_angle",
                '["',  # custom property
            )
            if fcurve.data_path.startswith(transforms):
                # fcurve belongs to the  object, so skip it
                return False

        # if fcurve.group.name not in bones_names:
        # return

        split_data_path = fcurve.data_path.split(sep='"')
        if len(split_data_path) > 1:
            bone_name = split_data_path[1]
            bone = obj.data.bones.get(bone_name)
        else:
            bone = None

        if not bone:
            return False

        if check_ui:
            if bone.hide:
                return False

            if context.area.type == "VIEW_3D":
                if not bone.select:
                    return False
            else:
                only_selected = context.space_data.dopesheet.show_only_selected
                if only_selected and not bone.select:
                    return False

    # if getattr(fcurve.group, 'name', None) == curve.group_name:
    #     return False  # we don't want to select keys on reference fcurves

    return True


def get_selected_keyframes_range_offset(context):
    """
    Returns the range of selected keyframes as (min_frame, max_frame) or None if no keyframes are selected.
    This function targets the Graph Editor context to ensure accuracy in detecting selected keyframes
    for both Object and Pose Mode.
    """
    obj = context.active_object
    if not obj or not obj.animation_data or not obj.animation_data.action:
        return None

    action = obj.animation_data.action
    min_frame, max_frame = float("inf"), -float("inf")
    has_selected_keyframes = False

    if context.mode == "POSE" and obj.type == "ARMATURE":
        # Collect names of selected bones for comparison
        selected_bones_names = {bone.name for bone in context.selected_pose_bones}
        for fcurve in context.visible_fcurves:
            bone_name = fcurve.data_path.split('"')[1] if '"' in fcurve.data_path else None
            if bone_name in selected_bones_names:
                for keyframe in fcurve.keyframe_points:
                    if keyframe.select_control_point:
                        min_frame = min(min_frame, keyframe.co.x)
                        max_frame = max(max_frame, keyframe.co.x)
                        has_selected_keyframes = True
    else:
        # Object Mode, process all F-Curves
        for fcurve in context.visible_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    min_frame = min(min_frame, keyframe.co.x)
                    max_frame = max(max_frame, keyframe.co.x)
                    has_selected_keyframes = True

    if has_selected_keyframes:
        return (int(min_frame), int(max_frame))
    else:
        return None


def get_selected_keyframes_range(context):
    """
    Returns the range of selected keyframes as (min_frame, max_frame) or None if no keyframes are selected.
    This function targets the Graph Editor context to ensure accuracy in detecting selected keyframes
    for both Object and Pose Mode.
    """
    min_frame, max_frame = float("inf"), -float("inf")
    has_selected_keyframes = False

    for fcurve in context.selected_visible_fcurves:
        for keyframe in fcurve.keyframe_points:
            if keyframe.select_control_point or keyframe.select_left_handle or keyframe.select_right_handle:
                min_frame = min(min_frame, keyframe.co.x)
                max_frame = max(max_frame, keyframe.co.x)
                has_selected_keyframes = True

    if has_selected_keyframes:
        return (int(min_frame), int(max_frame))
    else:
        return None


def get_keyframes_in_range(context, frame_start, frame_end):
    keyframes = set()
    selected_curves = context.selected_visible_fcurves

    for fcurve in selected_curves:
        for keyframe in fcurve.keyframe_points:
            if frame_start <= keyframe.co.x <= frame_end:
                keyframes.add(int(keyframe.co.x))

    return keyframes


def find_closest_keyframe_to_playhead(context):
    """
    Finds the closest keyframe to the playhead for the current action.
    Prefers the previous keyframe if two are equally far away.
    Works in both Object and Pose Modes.
    """
    obj = context.active_object
    if not obj or not obj.animation_data or not obj.animation_data.action:
        return context.scene.frame_current

    action = obj.animation_data.action
    current_frame = context.scene.frame_current
    # Compute the NLA offset from the active object
    nla_offset = get_nla_strip_offset(obj)
    closest_keyframe = None
    closest_distance = float("inf")

    if (context.selected_objects and obj.type != "ARMATURE") or (
        obj.type == "ARMATURE" and context.selected_pose_bones
    ):
        fcurves = all_fcurves(action)
        if context.mode == "POSE" and obj.type == "ARMATURE":
            selected_bones_names = {bone.name for bone in context.selected_pose_bones}
            fcurves = (
                fcurve
                for fcurve in fcurves
                if '"' in fcurve.data_path and fcurve.data_path.split('"')[1] in selected_bones_names
            )

        for fcurve in fcurves:
            for keyframe in fcurve.keyframe_points:
                effective_frame = keyframe.co.x + nla_offset
                distance = abs(effective_frame - current_frame)
                if distance < closest_distance or (distance == closest_distance and effective_frame <= current_frame):
                    closest_distance = distance
                    closest_keyframe = effective_frame
    else:
        return current_frame

    return closest_keyframe


def find_closest_keyframe(fcurve, frame_start, frame_end, to_right):
    """
    Finds the closest keyframe outside of the selected range in the specified direction.
    Returns the keyframe point if found, otherwise None.
    """
    if to_right:
        outside_keyframes = [kp for kp in fcurve.keyframe_points if kp.co.x > frame_end]
        outside_keyframes.sort(key=lambda kp: kp.co.x)
    else:
        outside_keyframes = [kp for kp in fcurve.keyframe_points if kp.co.x < frame_start]
        outside_keyframes.sort(key=lambda kp: kp.co.x, reverse=True)

    return outside_keyframes[0] if outside_keyframes else None


def find_keyframes(context):
    """Collect keyframes from various animation data sources, adapting to the context."""
    keyframes = []
    editors = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}

    # offset = get_nla_strip_offset(context.active_object)

    # Check for animation editor contexts
    if context.area is not None and context.area.type in editors:
        for fcurve in context.visible_fcurves:
            keyframes.extend(
                [
                    context.active_object.animation_data.nla_tweak_strip_time_to_scene(keyframe.co[0])
                    for keyframe in fcurve.keyframe_points
                ]
            )
    else:
        # Handle the object/bone context
        if context.mode == "POSE":
            armature = context.active_object if context.active_object.type == "ARMATURE" else None
            # Ensure the armature has animation data and an action
            if armature.animation_data and armature.animation_data.action:
                # Collect keyframes from selected bones in Pose Mode
                # if bone selected and active:
                if context.selected_pose_bones:
                    for bone in context.selected_pose_bones:
                        # Construct the data path for this bone
                        bone_path = f'pose.bones["{bone.name}"]'
                        for fcurve in all_fcurves(armature.animation_data.action):
                            # Check if this F-curve is associated with the current bone
                            if bone_path in fcurve.data_path:
                                keyframes.extend(
                                    [
                                        armature.animation_data.nla_tweak_strip_time_to_scene(keyframe.co[0])
                                        for keyframe in fcurve.keyframe_points
                                    ]
                                )
                else:
                    for bone in context.visible_pose_bones:  # armature.pose.bones:
                        # break early if bone not in visible_pose_bones
                        bone_path = f'pose.bones["{bone.name}"]'
                        for fcurve in all_fcurves(armature.animation_data.action):
                            if bone_path in fcurve.data_path:
                                keyframes.extend(
                                    [
                                        armature.animation_data.nla_tweak_strip_time_to_scene(keyframe.co[0])
                                        for keyframe in fcurve.keyframe_points
                                    ]
                                )

        else:
            # Collect keyframes from selected objects
            for obj in context.selected_objects:
                if obj.animation_data and obj.animation_data.action:
                    for fcurve in all_fcurves(obj.animation_data.action):
                        keyframes.extend(
                            [
                                context.active_object.animation_data.nla_tweak_strip_time_to_scene(keyframe.co[0])
                                for keyframe in fcurve.keyframe_points
                            ]
                        )

    return sorted(set(keyframes))


# def select_keyframe_in_editors(target_frame, context):
#     scene = context.scene
#     areas = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}

#     if context.area is not None and context.area.type not in areas:
#         return
#     # Compute the NLA offset from the active object
#     # nla_offset = get_nla_strip_offset(context.active_object) if context.active_object else 0

#     if context.area is not None:
#         if context.visible_fcurves is not None:
#             if context.area.type == "GRAPH_EDITOR":
#                 try:
#                     bpy.ops.graph.select_all(action="DESELECT")
#                 except RuntimeError as e:
#                     utils.dprint(e)
#             elif context.area.type == ("DOPESHEET_EDITOR" or "TIMELINE"):
#                 try:
#                     bpy.ops.action.select_all(action="DESELECT")
#                 except RuntimeError as e:
#                     utils.dprint(e)

#             for fcurve in context.visible_fcurves:
#                 for keyframe in fcurve.keyframe_points:
#                     # Compare the effective frame including the nla offset
#                     if target_frame is not None and (
#                         (context.active_object.animation_data.nla_tweak_strip_time_to_scene(keyframe.co[0]))
#                         == target_frame
#                     ):
#                         keyframe.select_control_point = True
#                         break

#             utils.refresh_ui(context)


def create_area_context_override(context, valid_area_types=None, current_area_first=True):
    """
    Create context overrides for specified area types.

    This is a general-purpose method for creating context overrides that can be used
    with any Blender area type (e.g., VIEW_3D, NODE_EDITOR, etc.).

    Args:
        context: The current Blender context
        valid_area_types: Set/list of valid area types. If None, returns all areas.
        current_area_first: If True, prioritize current area in results

    Returns:
        List of tuples: (area, override_dict) for each valid area
    """
    areas_to_process = []

    # Convert to set for faster lookup
    if valid_area_types is not None and not isinstance(valid_area_types, set):
        valid_area_types = set(valid_area_types)

    # Helper to create override dict
    def create_override(window, area, region=None):
        if region is None:
            region = next((r for r in area.regions if r.type == "WINDOW"), None)

        if not region:
            return None

        return {
            "window": window,
            "screen": window.screen,
            "area": area,
            "region": region,
            "space_data": area.spaces.active,
        }

    # Process current area first if requested
    if current_area_first and context.area:
        if valid_area_types is None or context.area.type in valid_area_types:
            # For current area, use existing context values when available
            override = {
                "area": context.area,
                "region": context.region or next((r for r in context.area.regions if r.type == "WINDOW"), None),
                "space_data": context.space_data or context.area.spaces.active,
            }
            # Add window and screen if available
            if context.window:
                override["window"] = context.window
                override["screen"] = context.screen or context.window.screen

            if override["region"]:  # Only add if we have a valid region
                areas_to_process.append((context.area, override))

    # Find all matching areas across all windows
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            # Skip current area if already processed
            if current_area_first and area == context.area:
                continue

            # Check if area type matches
            if valid_area_types is None or area.type in valid_area_types:
                override = create_override(window, area)
                if override:
                    areas_to_process.append((area, override))

    return areas_to_process


def select_keyframe_in_editors(context):
    """Select keyframes at the current frame across all animation editors.
    This function selects all keyframes that exist at the current frame position
    in the Graph Editor, Dopesheet Editor, and Timeline. It first deselects all
    keyframes, then selects only those at the current frame using column selection.
    The function handles context overrides to operate on editors that are not
    currently active, ensuring consistent selection across all animation editors
    in the current workspace.
    Args:
        context: The Blender context object containing information about the
            current state, including the active object and available areas.
    Returns:
        None
    Notes:
        - Requires an active object with animation data and at least one FCurve
        - Will silently exit if no active object or animation data is found
        - Prints status messages for debugging purposes
        - Handles RuntimeError and TypeError exceptions gracefully when context
          operations fail
    Example:
        >>> select_keyframe_in_editors(bpy.context)
        Selected keyframes in GRAPH_EDITOR editor (current context).
        Selected keyframes in DOPESHEET_EDITOR editor (with override).
    """
    # Early exit if no active object or no animation data
    if not context.active_object:
        return

    # Check if active object has animation data
    obj = context.active_object
    if not obj.animation_data or not obj.animation_data.action:
        return

    # Check if there are any fcurves to work with
    action = obj.animation_data.action
    fcurves_exist = any(all_fcurves(action))
    if not fcurves_exist:
        return

    # Internal method to perform selection operations
    def _perform_selection(area_type):
        try:

            if area_type == "GRAPH_EDITOR":
                bpy.ops.graph.select_all(action="DESELECT")
                bpy.ops.graph.select_column(mode="CFRA")

            elif area_type in {"DOPESHEET_EDITOR"}:
                bpy.ops.action.select_all(action="DESELECT")
                bpy.ops.action.select_column(mode="CFRA")

            return True
        except RuntimeError:
            return False

    # Get context overrides for all animation editors
    animation_editors = {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}
    areas_to_process = create_area_context_override(context, animation_editors)

    # Process each editor type separately, stopping after first successful selection
    for editor_type in animation_editors:
        editor_found = False

        # Find and process the first editor of this type
        for area, ctx_override in areas_to_process:
            if area.type != editor_type:
                continue

            editor_found = True

            try:
                # If this is the current area, try without override first
                if area == context.area:
                    if _perform_selection(area.type):
                        # print(f"Selected keyframes in {area.type} editor (current context).")
                        break

                # Try with context override
                with context.temp_override(**ctx_override):
                    # Check if we have proper context for animation operations
                    if not hasattr(bpy.context, "visible_fcurves"):
                        continue

                    # if _perform_selection(area.type):
                    #     print(f"Selected keyframes in {area.type} editor (with override).")
                    # else:
                    #     print("Failed to select keyframes in editor:", area.type)

            except (RuntimeError, TypeError):
                # Context override failed or invalid context
                print("Failed to process editor:", area.type)

            # Break after processing first editor of this type
            break


def deselect_all_keyframes_in_editors(context):
    areas = {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}

    if (context.area.type not in areas) or (context.area is None) or (context.area.type is None):
        return

    if context.area.type == "GRAPH_EDITOR":
        try:
            bpy.ops.graph.select_all(action="DESELECT")
        except RuntimeError as e:
            utils.dprint(e)

    elif context.area.type == ("DOPESHEET_EDITOR" or "TIMELINE"):
        try:
            bpy.ops.action.select_all(action="DESELECT")
        except RuntimeError as e:
            utils.dprint(e)

    # Redraw the area to update the UI
    utils.refresh_ui(context)


# def has_selected_keyframes(context):
#     space_type = context.space_data.type
#     active_object = context.active_object

#     if active_object is None:
#         return False

#     if space_type == "GRAPH_EDITOR":
#         active_fcurves = context.selected_visible_fcurves

#         if active_fcurves:
#             for fcurve in active_fcurves:
#                 for keyframe in fcurve.keyframe_points:
#                     if keyframe.select_control_point or keyframe.select_left_handle or keyframe.select_right_handle:
#                         return True

#     elif space_type == "DOPESHEET_EDITOR":
#         animation_data = active_object.animation_data

#         if animation_data and animation_data.action:
#             for fcurve in all_fcurves(animation_data.action):
#                 for keyframe in fcurve.keyframe_points:
#                     if keyframe.select_control_point:
#                         return True

#         if active_object.type == "GREASEPENCIL":
#             grease = context.grease_pencil
#             for layer in grease.layers:
#                 for frame in layer.frames:
#                     if frame.select:
#                         return True

#         if hasattr(active_object.data, "materials") and active_object.data.materials:
#             for material in active_object.data.materials:
#                 if (
#                     material is not None
#                     and material.node_tree
#                     and material.node_tree.animation_data
#                     and material.node_tree.animation_data.action
#                 ):
#                     action_fcurves = all_fcurves(material.node_tree.animation_data.action)
#                     for fcurve in action_fcurves:
#                         if "nodes[" in fcurve.data_path and ".inputs[" in fcurve.data_path:
#                             for keyframe in fcurve.keyframe_points:
#                                 if keyframe.select_control_point:
#                                     return True

#     return False


def has_selected_keyframes(context):
    space = context.space_data.type
    obj = context.active_object
    if not obj:
        return False

    # Helper to scan any fcurve for selected handles/points
    def fcurve_has_selected(fcurves, check_handles=False):
        for fc in fcurves:
            for kp in fc.keyframe_points:
                if kp.select_control_point or (check_handles and (kp.select_left_handle or kp.select_right_handle)):
                    return True
        return False

    if space == "GRAPH_EDITOR":
        # only selected & visible f-curves, check handles too
        return fcurve_has_selected(context.selected_visible_fcurves, check_handles=True)

    if space == "DOPESHEET_EDITOR":
        # 1) Grease Pencil frames
        gp = getattr(context, "grease_pencil", None)
        if gp:
            if any(frame.select for layer in gp.layers for frame in layer.frames):
                return True

        # 2) Object action F-curves
        ad = getattr(obj, "animation_data", None)
        if ad and ad.action:
            if fcurve_has_selected(all_fcurves(ad.action)):
                return True

        # 3) Material node-tree F-curves (only input sockets)
        mats = getattr(obj.data, "materials", ())
        mat_fcs = (
            fc
            for mat in mats
            if mat and mat.node_tree and mat.node_tree.animation_data and mat.node_tree.animation_data.action
            for fc in all_fcurves(mat.node_tree.animation_data.action)
            if "nodes[" in fc.data_path and ".inputs[" in fc.data_path
        )
        return fcurve_has_selected(mat_fcs)

    return False


def delete_keyframes(context, frames_to_delete):

    if frames_to_delete is None:
        frames_to_delete = []
    else:
        frames_to_delete = sorted([round(frame) for frame in frames_to_delete])

    active_fcurves = context.selected_visible_fcurves
    if active_fcurves is not None:
        for fcurve in active_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.co.x in frames_to_delete:
                    fcurve.keyframe_points.remove(keyframe)


def key_custom_properties(target, frame):
    """
    Keyframe custom properties for the given target at the specified frame.
    Handles objects and bones in pose mode.
    """
    if hasattr(target, "pose") and bpy.context.mode == "POSE":
        for bone in target.pose.bones:
            if bone.bone.select:
                for prop in [p for p in bone.keys() if p not in {"_RNA_UI", "cycles"}]:
                    # Using get() method to safely access properties
                    if hasattr(bone, prop):
                        bone.keyframe_insert(data_path=f'["{prop}"]', frame=frame, group=bone.name)
    else:
        for prop in [p for p in target.keys() if p not in {"_RNA_UI", "cycles"}]:
            # Using get() method to safely access properties
            try:
                if hasattr(target, prop):
                    target.keyframe_insert(data_path=f'["{prop}"]', frame=frame)
            except:
                pass


# def keyframe_targets(
#     self,
#     context,
#     targets,
#     frame,
#     location=False,
#     rotation=False,
#     scale=False,
#     custom=False,
# ):
#     for target in targets:
#         transformations_keyed = location or rotation or scale

#         if location:
#             key_standard_properties(target, "location", frame)
#         if rotation:
#             key_standard_properties(
#                 target,
#                 (
#                     "rotation_quaternion"
#                     if getattr(target, "rotation_mode", "XYZ") == "QUATERNION"
#                     else "rotation_euler"
#                 ),
#                 frame,
#             )
#         if scale:
#             key_standard_properties(target, "scale", frame)

#         # Key all available fcurves if none of the transformations are keyed
#         if not transformations_keyed:
#             key_available_fcurves(self, context, target, frame)

#         if custom:
#             key_custom_properties(target, frame)


def keyframe_targets(
    self,
    context,
    targets,
    frame,
    location=False,
    rotation=False,
    scale=False,
    custom=False,
):
    """
    Keyframe properties for the given targets at the specified frame.
    Compatible with Blender 4.5 slotted actions.
    """
    for target in targets:
        # Get all fcurves for this target using the existing infrastructure
        if hasattr(target, "animation_data") and target.animation_data and target.animation_data.action:
            action = target.animation_data.action
            fcurves = list(all_fcurves(action))

            # Filter fcurves based on target type (for pose bones)
            if isinstance(target, bpy.types.PoseBone):
                bone_path = f'pose.bones["{target.name}"]'
                fcurves = [fc for fc in fcurves if fc.data_path.startswith(bone_path)]

            keyframe_fcurves(self, context, fcurves, frame, location, rotation, scale, custom)

        # Key custom properties directly on the target
        if custom:
            key_custom_properties(target, frame)


def keyframe_fcurves(
    self,
    context,
    fcurves,
    frame,
    location=False,
    rotation=False,
    scale=False,
    custom=False,
):
    """
    Keyframe specific fcurves based on transformation types.
    """
    for fcurve in fcurves:
        data_path = fcurve.data_path
        transformations_keyed = location or rotation or scale

        if not transformations_keyed:
            # Key all available fcurves because no specific transformation was requested
            key_fcurve(fcurve, frame)
        else:
            # Determine if the current fcurve should be keyframed based on its data_path
            should_key = False
            if location and "location" in data_path:
                should_key = True
            elif rotation and (
                "rotation_quaternion" in data_path
                or "rotation_euler" in data_path
                or "rotation_axis_angle" in data_path
            ):
                should_key = True
            elif scale and "scale" in data_path:
                should_key = True

            if should_key:
                key_fcurve(fcurve, frame)

        # Key custom properties, identifying them by exclusion or specific markers in their data paths
        if custom and (
            data_path.startswith('["')
            or data_path.split(".")[0]
            not in ["location", "rotation_euler", "rotation_quaternion", "rotation_axis_angle", "scale"]
        ):
            key_fcurve(fcurve, frame)


def key_fcurve(fcurve, frame, value=None):
    """
    Insert a keyframe on an fcurve at the specified frame.
    """
    if value is not None:
        fcurve.keyframe_points.insert(frame, value, options={"FAST"})
    else:
        # Evaluate the current value of the F-Curve at this frame and insert a keyframe
        current_value = fcurve.evaluate(frame)
        fcurve.keyframe_points.insert(frame, current_value, options={"FAST"})

    # Update the fcurve to refresh the UI
    fcurve.update()


def key_available_fcurves(self, context, target, frame):
    """
    Insert keyframes for all animatable properties (fcurves) of the target at the specified frame.
    Updated to avoid TypeError by removing the use of a non-existent 'find' method.
    """

    selected_fcurves = context.selected_visible_fcurves

    if selected_fcurves is not None:
        for fcurve in selected_fcurves:
            if isinstance(target, bpy.types.PoseBone):
                bone_path = 'pose.bones["{}"]'.format(target.name)
                if not fcurve.data_path.startswith(bone_path):
                    continue

            # if fcurve.lock or fcurve.hide:
            #     continue

            # Manually search for a keyframe at the specified frame
            keyframe_point = next((kp for kp in fcurve.keyframe_points if int(kp.co.x) == frame), None)

            if keyframe_point is not None:
                # Keyframe exists, update its value
                keyframe_point.co.y = fcurve.evaluate(frame)
            else:
                # Keyframe does not exist, insert a new one
                fcurve.keyframe_points.insert(frame, fcurve.evaluate(frame)).interpolation = "BEZIER"
    else:
        self.report({"WARNING"}, "No keyframes selected.")
        return {"CANCELLED"}


def key_standard_properties(target, data_path, frame):
    """
    Insert keyframe for standard properties (location, rotation, scale) at the given frame.
    The object's current value for the property is used.
    """
    current_frame = bpy.context.scene.frame_current
    bpy.context.scene.frame_current = frame

    try:
        target.keyframe_insert(data_path=data_path, frame=frame)
    finally:
        bpy.context.scene.frame_current = current_frame


def find_range_between_selected_keyframes(context):
    min_frame, max_frame = float("inf"), -float("inf")

    offset = get_nla_strip_offset(context.active_object)

    selected_curves = context.selected_visible_fcurves
    for fcurve in selected_curves:
        for keyframe_point in fcurve.keyframe_points:
            if keyframe_point.select_control_point:
                frame = keyframe_point.co.x
                if frame < min_frame:
                    min_frame = frame
                if frame > max_frame:
                    max_frame = frame

    if min_frame == float("inf") or max_frame == -float("inf"):
        utils.dprint("No keyframes selected.")
        return (0, 0)

    min_frame = math.floor(min_frame)

    if not max_frame.is_integer():
        max_frame = math.ceil(max_frame)
    else:
        max_frame = math.floor(max_frame)

    return (int(min_frame - offset), int(max_frame - offset))


def determine_frame_range_priority(self, context):
    if has_selected_keyframes(context):
        return find_range_between_selected_keyframes(context)
    elif context.scene.use_preview_range:
        return (context.scene.frame_preview_start, context.scene.frame_preview_end)
    else:
        return (context.scene.frame_start, context.scene.frame_end)


def determine_frame_range(self, context):
    if self.range_options == "SELECTED":
        selected_range = find_range_between_selected_keyframes(context)
        return selected_range
    elif self.range_options == "PREVIEW":
        return (context.scene.frame_preview_start, context.scene.frame_preview_end)
    else:
        offset = get_nla_strip_offset(context.active_object)
        return (context.scene.frame_start - offset, context.scene.frame_end - offset)


def determine_insertion_frames(self, frame_start, frame_end):
    frame_start = int(frame_start)
    frame_end = int(frame_end)

    frame_step = max(int(self.frame_step), 1)
    frame_start_range = self.frame_start_range

    frames_to_insert = []

    if self.insertion_type == "ON_MARKERS":
        markers = bpy.context.scene.timeline_markers
        frames_to_insert = [marker.frame for marker in markers if frame_start <= marker.frame <= frame_end]

    elif self.insertion_type == "FRAME_STEP":
        frames_to_insert = list(range(frame_start + frame_start_range, frame_end + 1, frame_step))

    elif self.insertion_type == "ON_MARKERS_AND_FRAME_STEP":
        markers = bpy.context.scene.timeline_markers
        marker_frames = {marker.frame for marker in markers if frame_start <= marker.frame <= frame_end}
        step_frames = set(range(frame_start + frame_start_range, frame_end + 1, frame_step))
        frames_to_insert = sorted(marker_frames.union(step_frames))

    if frame_start not in frames_to_insert:
        frames_to_insert.insert(0, frame_start)
    if frame_end not in frames_to_insert:
        frames_to_insert.append(frame_end)

    return frames_to_insert


def update_frame_start_range(self, context):
    """
    Update callback for frame_start_range to ensure it's smaller than frame_step.
    """

    if self.frame_step <= self.frame_start_range:
        self.frame_start_range = self.frame_step - 1


def update_frame_step(self, context):
    """
    Update callback for frame_start_range to ensure it's smaller than frame_step.
    """

    if self.frame_step < self.frame_start_range:
        self.frame_step = self.frame_start_range + 1


def update_frame_range_start_frame(self, context):
    if self.end_range > context.scene.frame_end:
        self.end_range = context.scene.frame_end
    if self.end_range <= self.start_range:
        self.start_range = self.end_range - 1


def update_frame_range_end_frame(self, context):

    if self.start_range < context.scene.frame_start:
        self.start_range = context.scene.frame_start
    if self.end_range < self.start_range:
        self.end_range = self.start_range + 1


def is_close_to_whole_frame(value, epsilon=1e-9):
    return abs(round(value) - value) < epsilon


def clear_other_keyframes(context, fcurves, frames_to_keep, frame_range):
    frame_start, frame_end = frame_range

    for fcurve in fcurves:
        # Check if the F-Curve is relevant based on the target type
        keyframe_points_to_remove = [
            kp for kp in fcurve.keyframe_points if frame_start <= kp.co.x <= frame_end and kp.co.x not in frames_to_keep
        ]

        # Create a list to collect the indices of keyframe points to remove
        indices_to_remove = []
        for kp in keyframe_points_to_remove:
            # Find the index of the keyframe point to remove
            index = [i for i, point in enumerate(fcurve.keyframe_points) if point == kp]
            if index:
                indices_to_remove.extend(index)

        # Remove keyframes in reverse order to maintain correct indices
        for index in sorted(indices_to_remove, reverse=True):
            fcurve.keyframe_points.remove(fcurve.keyframe_points[index])

        keys_to_remove = [kp for kp in fcurve.keyframe_points if not is_close_to_whole_frame(kp.co.x)]
        for kp in keys_to_remove:
            fcurve.keyframe_points.remove(kp)
        fcurve.update()


def correct_offset(fcurve, original_first_frame):
    """
    Corrects the offset of all keyframes in an F-Curve based on the shift
    from the original first frame to the new first frame position.

    Parameters:
    - fcurve (bpy.types.FCurve): The F-Curve to correct.
    - original_first_frame (float): The original x position of the first keyframe.
    """
    if original_first_frame is not None:
        new_first_frame = fcurve.keyframe_points[0].co.x
        shift = new_first_frame - original_first_frame

        # Step 4: Adjust all keyframes if there's a shift
        if shift != 0:
            for keyframe in fcurve.keyframe_points:
                keyframe.co.x -= shift
                keyframe.handle_left.x -= shift
                keyframe.handle_right.x -= shift


def smart_preserve_fcurves(fcurves, original_first_frame=0, shift_offset=True):
    """
    Preserves the F-Curves by inserting keyframes at whole frames and optionally correcting
    the offset to maintain the original animation start position.

    Parameters:
    - fcurves (list of bpy.types.FCurve): The F-Curves to process.
    - original_first_frame (float): The x position of the first keyframe before retiming.
    - shift_offset (bool): Whether to correct the offset after processing.
    """
    for fcurve in fcurves:
        whole_frames = set()

        subframe_keyframes = []

        for keyframe in fcurve.keyframe_points:
            frame = keyframe.co.x
            if frame == round(frame):
                whole_frames.add(round(frame))
            else:
                subframe_keyframes.append(keyframe)

        # Insert keyframes at the nearest whole frame for subframe keyframes
        for keyframe in subframe_keyframes:
            if keyframe.co.x is not None:
                nearest_whole_frame = round(keyframe.co.x)

            # Only insert a new keyframe if there isn't already one at this frame
            if nearest_whole_frame not in whole_frames:
                # Evaluate the fcurve at this frame to get the correct value
                value = fcurve.evaluate(nearest_whole_frame)
                new_keyframe = fcurve.keyframe_points.insert(nearest_whole_frame, value, options={"NEEDED", "FAST"})
                # Set the handle types for the new keyframe
                # new_keyframe.interpolation = keyframe.interpolation
                # new_keyframe.handle_left_type = keyframe.handle_left_type
                # new_keyframe.handle_right_type = keyframe.handle_right_type

                new_keyframe.interpolation = "BEZIER"
                new_keyframe.handle_left_type = "AUTO_CLAMPED"
                new_keyframe.handle_right_type = "AUTO_CLAMPED"

                whole_frames.add(nearest_whole_frame)

        # Second pass: Remove the original subframe keyframes
        if shift_offset:
            delete_subframe_keyframes(fcurve)

        correct_offset(fcurve, original_first_frame)


def delete_subframe_keyframes(fcurve):
    """
    Deletes keyframes that are not on whole frames from the specified F-Curve.

    Parameters:
    - fcurve (bpy.types.FCurve): The F-Curve from which to remove subframe keyframes.
    """
    indexes_to_remove = []

    for index, keyframe in enumerate(fcurve.keyframe_points):
        if keyframe.co.x != round(keyframe.co.x):
            indexes_to_remove.append(index)

    indexes_to_remove.sort(reverse=True)

    for index in indexes_to_remove:
        fcurve.keyframe_points.remove(fcurve.keyframe_points[index])

    utils.dprint(f"Removed {len(indexes_to_remove)} subframe keyframe(s) from the F-Curve.")


def find_owner(fcurve):
    id_data = fcurve.id_data
    if isinstance(id_data, bpy.types.Action):
        for obj in bpy.data.objects:
            if obj.animation_data and obj.animation_data.action == id_data:
                return obj
        return None
    else:
        return id_data


def is_fcurve_in_radians(fcurve):
    """Converts the value to degrees if the F-Curve represents rotation in radians."""
    data_path = fcurve.data_path

    if ("rotation_euler" or "delta_rotation_euler") in data_path:
        return True

    if any(key in data_path for key in ["location", "scale", "rotation_quaternion", "delta_rotation_quaternion"]):

        return False

    path_parts = data_path.rsplit(".", 1)
    if len(path_parts) == 2:
        owner_path, property_name = path_parts
    else:
        owner_path = ""
        property_name = path_parts[0]

    owner = find_owner(fcurve)
    if owner is None:
        return False

    try:
        if owner_path:
            owner = owner.path_resolve(owner_path)

        prop_def = owner.bl_rna.properties.get(property_name)

        if prop_def:
            unit = getattr(prop_def, "unit", None)
            if unit == "ROTATION":
                return True
    except Exception:
        pass

    return False


def get_nla_strip_offset(obj, fcurve=None):
    """
    Returns the calculated offset of the matching NLA strip for the given object.

    The returned offset is computed as:
        (strip.frame_start_ui - strip.action_frame_start)

    Mechanisms:
      - If tweak mode is active (scene.is_nla_tweakmode True), ALWAYS returns the offset
        of the strip being tweaked. It first checks bpy.context.active_nla_strip;
        if not found, it checks bpy.context.active_nla_track for a selected strip.
        If no selected strip is found, it iterates over all NLA tracks and returns the offset
        of the first available strip.
      - When not in tweak mode, it uses the action from the FCurve (if provided) or
        the object's active action and returns the offset of the matching strip (by comparing
        action names).

    Args:
        obj (bpy.types.Object): The Blender object whose NLA data is examined.
        fcurve (bpy.types.FCurve, optional): Optional FCurve to determine the action.

    Returns:
        float: The calculated offset (frame_start_ui - action_frame_start) of the matching NLA strip,
               or 0 if not found.
    """
    if not obj or not obj.animation_data:
        print("Object has no animation data.")
        return 0

    # Helper: calculate the effective offset for a given strip.
    def calc_offset(strip):
        try:
            act_frame_start = strip.action_frame_start
        except AttributeError:
            act_frame_start = 0
        return strip.frame_start_ui - act_frame_start

    # --- Tweak Mode Branch ---
    if getattr(bpy.context.scene, "is_nla_tweakmode", False):
        # 1. Try to get the active NLA strip from context.
        active_strip = getattr(bpy.context, "active_nla_strip", None)
        if active_strip:
            print(
                "Tweak mode active. Using active_nla_strip:",
                active_strip.name,
                "with offset:",
                calc_offset(active_strip),
            )
            return calc_offset(active_strip)

        # 2. Try to get the active NLA track and look for a selected strip.
        active_track = getattr(bpy.context, "active_nla_track", None)
        if active_track and active_track.strips:
            for strip in active_track.strips:
                if strip.select:
                    print(
                        "Tweak mode active. Using selected strip in active_nla_track:",
                        strip.name,
                        "with offset:",
                        calc_offset(strip),
                    )
                    return calc_offset(strip)
            # Fallback: use the first strip of the active track.
            print(
                "Tweak mode active. No selected strip in active_nla_track; using first strip:",
                active_track.strips[0].name,
                "with offset:",
                calc_offset(active_track.strips[0]),
            )
            return calc_offset(active_track.strips[0])

        # 3. Iterate over all NLA tracks to find a selected strip.
        for track in obj.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.select:
                    # print(
                    #     "Tweak mode active. Found selected strip in track",
                    #     track.name,
                    #     ":",
                    #     strip.name,
                    #     "with offset:",
                    #     calc_offset(strip),
                    # )
                    return calc_offset(strip)

        # 4. Fallback: use the first available strip from any track.
        # for track in obj.animation_data.nla_tracks:
        #     if track.strips:
        #         print(
        #             "Tweak mode active. Fallback: using first strip in track",
        #             track.name,
        #             ":",
        #             track.strips[0].name,
        #             "with offset:",
        #             calc_offset(track.strips[0]),
        #         )
        #         return calc_offset(track.strips[0])

        print("Tweak mode active but no strip found.")
        return 0

    # --- Non-Tweak Mode Branch ---
    # Determine the target action.
    if fcurve is not None:
        target_action = fcurve.id_data
    else:
        target_action = obj.animation_data.action

    # If there's no target action, return the offset of the first available strip.
    if target_action is None:
        for track in obj.animation_data.nla_tracks:
            if track.strips:
                print(
                    "No target action. Using first strip found:",
                    track.strips[0].name,
                    "with offset:",
                    calc_offset(track.strips[0]),
                )
                return calc_offset(track.strips[0])
        return 0

    target_action_name = target_action.name
    # Search for a strip with a matching action name.
    for track in obj.animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action and strip.action.name == target_action_name:
                # print("Found matching strip:", strip.name, "with offset:", calc_offset(strip))
                return calc_offset(strip)

    return 0


from typing import Iterable, Tuple, Any


def get_active_groups(action: bpy.types.Action):
    """
    Return a dictionary of active F-Curve groups for the entire action,
    merging groups from all slots, layers, and strips.
    In legacy mode (pre‑4.4), it returns a dict keyed by group name from action.groups.
    """
    groups = {}
    if hasattr(action, "slots") and action.slots and hasattr(action, "layers"):
        for slot in action.slots:
            for layer in action.layers:
                # Ensure the layer has at least one strip.
                if layer.strips:
                    for strip in layer.strips:
                        channelbag = strip.channelbag(slot, ensure=True)
                        for group in channelbag.groups:
                            groups[group.name] = group
        return groups
    else:
        return {group.name: group for group in action.groups}


def all_fcurves(action: bpy.types.Action) -> Iterable[bpy.types.FCurve]:
    """Return all FCurves from an action, handling legacy and slotted actions."""
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in strip.channelbags:
                    yield from channelbag.fcurves
    else:
        yield from action.fcurves


def selected_fcurves() -> Iterable[bpy.types.FCurve]:
    """Return selected visible FCurves from the built-in context."""
    return bpy.context.selected_visible_fcurves


def visible_fcurves() -> Iterable[bpy.types.FCurve]:
    """Return visible FCurves from the built-in context."""
    return bpy.context.visible_fcurves


def selected_keys() -> Iterable[Tuple[bpy.types.FCurve, Any]]:
    """Iterate over editable FCurves, yielding (fcurve, keyframe) tuples for selected keyframes.

    Checks standard FCurve selection flags and also a generic 'select' flag for cases like
    grease pencil frames.
    """
    for f in bpy.context.editable_fcurves:
        for kp in f.keyframe_points:
            if (
                hasattr(kp, "select_control_point")
                and (kp.select_control_point or kp.select_left_handle or kp.select_right_handle)
            ) or getattr(kp, "select", False):
                yield f, kp


def scene_fcurves() -> Iterable:
    added_actions = set()
    scene = bpy.context.scene

    # Process actions from objects, shape keys, and materials only once
    for obj in scene.objects:

        # Objects
        if obj.animation_data and obj.animation_data.action:
            act = obj.animation_data.action
            if act not in added_actions:
                added_actions.add(act)
                for fcu in all_fcurves(act):
                    yield fcu

        # Shape keys
        if hasattr(obj.data, "shape_keys") and obj.data.shape_keys:
            sk = obj.data.shape_keys
            if sk.animation_data and sk.animation_data.action:
                act = sk.animation_data.action
                if act not in added_actions:
                    added_actions.add(act)
                    for fcu in all_fcurves(act):
                        yield fcu

        # Materials
        if hasattr(obj.data, "materials") and obj.data.materials:
            for mat in obj.data.materials:
                if mat and mat.animation_data and mat.animation_data.action:
                    act = mat.animation_data.action
                    if act not in added_actions:
                        added_actions.add(act)
                        for fcu in all_fcurves(act):
                            yield fcu
                if mat and hasattr(mat, "node_tree") and mat.node_tree:
                    if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
                        act = mat.node_tree.animation_data.action
                        if act not in added_actions:
                            added_actions.add(act)
                            for fcu in all_fcurves(act):
                                yield fcu

    # Grease pencil frames
    for gp_obj, gp_layer, gp_frame in scene_gpencil_frames():
        yield gp_frame


def scene_gpencil_frames() -> Iterable[Tuple[bpy.types.Object, bpy.types.GPencilLayer, bpy.types.GPencilFrame]]:
    """Yield grease pencil frames from all grease pencil objects in the scene."""
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type == "GPENCIL" and hasattr(obj.data, "layers"):
            for layer in obj.data.layers:
                for frame in layer.frames:
                    yield obj, layer, frame


def get_active_fcurves_obj(obj) -> Iterable[bpy.types.FCurve]:
    # If obj is an Action, yield its fcurves directly.
    if isinstance(obj, bpy.types.Action):
        yield from obj.fcurves
        return
    anim = obj.animation_data
    if not anim:
        return
    if hasattr(anim, "action_slot") and anim.action_slot:
        act = anim.action
        slot = anim.action_slot
        for layer in act.layers:
            for strip in layer.strips:
                channelbag = strip.channelbag(slot, ensure=True)
                yield from channelbag.fcurves
    elif anim.action:
        yield from all_fcurves(anim.action)


def selected_elements_fcurves(context) -> Iterable[bpy.types.FCurve]:
    """Yield fcurves from selected elements using the active animation slot.
    • In Pose Mode: FCurves from the active object's slot that belong to selected bones.
    • In Object Mode: FCurves from each selected object's active slot.
    """
    if context.mode == "POSE":
        fcurves = list(get_active_fcurves_obj(context.active_object))
        if fcurves:
            selected_names = {bone.name for bone in context.selected_pose_bones}
            for f in fcurves:
                if any(bone_name in f.data_path for bone_name in selected_names):
                    yield f
    else:
        for obj in context.selected_objects:
            for f in get_active_fcurves_obj(obj):
                yield f


def gather_keyframes(scope: str, context) -> list:
    """
    Gather keyframes from fcurves based on the given scope.
      • "SCENE": from all fcurves in the scene.
      • "ACTION": from all fcurves of the active object's action.
      • "SELECTED_ELEMENTS": from animation data of any selected element (Object Mode or selected bones in Pose Mode).
      • "VISIBLE_FCURVES": from all visible fcurves.
      • "SELECTED_KEYS": selected keyframes in editable fcurves.
    """
    if scope == "SCENE":
        return [kf for fcu in scene_fcurves() for kf in fcu.keyframe_points]

    elif scope == "ACTION":
        act = context.active_object.animation_data.action
        return [kf for fcu in all_fcurves(act) for kf in fcu.keyframe_points]

    elif scope == "SELECTED_ELEMENTS":
        kf_list = []
        for fcu in selected_elements_fcurves(context):
            kf_list.extend(fcu.keyframe_points)
        return kf_list

    elif scope == "VISIBLE_FCURVES":
        return [kf for fcu in visible_fcurves() for kf in fcu.keyframe_points]

    elif scope == "SELECTED_KEYS":
        return [key for fcu, key in selected_keys()]

    else:
        return []


def remove_fcurve_from_action(action, fcurve):
    """
    Remove an fcurve from its container.

    - In Blender 4.4+ (with slotted actions), search through action.layers → strips → channelbags.
    - In legacy actions (pre‑4.4) remove directly from action.fcurves.
    """
    if hasattr(action, "layers"):

        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in strip.channelbags:
                    if fcurve in list(channelbag.fcurves):
                        channelbag.fcurves.remove(fcurve)
                        return True
        return False
    else:
        try:
            action.fcurves.remove(fcurve)
            return True
        except Exception as e:
            print("Legacy removal failed:", e)
            return False


def gather_fcurves(scope: str, context) -> list:
    """
    Gather fcurves based on the given scope using the same mechanisms as gather_keyframes.
      • "SCENE": from all fcurves in the scene.
      • "ACTION": from all fcurves of the active object's action.
      • "SELECTED_ELEMENTS": from fcurves of selected elements.
      • "VISIBLE_FCURVES": from all visible fcurves.
      • "SELECTED_KEYS": unique fcurves containing the selected keyframes.
    """
    if scope == "SCENE":
        return list(scene_fcurves())
    elif scope == "ACTION":
        act = (
            context.active_object.animation_data.action
            if context.active_object and context.active_object.animation_data
            else None
        )
        return list(all_fcurves(act)) if act else []
    elif scope == "SELECTED_ELEMENTS":
        return list(selected_elements_fcurves(context))
    elif scope == "VISIBLE_FCURVES":
        return list(visible_fcurves())
    elif scope == "SELECTED_KEYS":
        unique_fcurves = {}
        for fcu, _ in selected_keys():
            key = (id(fcu.id_data), fcu.data_path, fcu.array_index)
            unique_fcurves[key] = fcu
        return list(unique_fcurves.values())
    else:
        return []


def s_curve(x, slope=2.0, width=1.0, height=1.0, xshift=0.0, yshift=0.0):
    """
    Formula for 'S' curve.

    Args:
        x: Input value (typically 0-1 for frame ratio)
        slope: Steepness of the curve (higher = steeper)
        width: Width of the curve
        height: Height of the curve
        xshift: Horizontal shift
        yshift: Vertical shift

    Returns:
        float: Curve value
    """
    curve = height * ((x - xshift) ** slope / ((x - xshift) ** slope + (width - (x - xshift)) ** slope)) + yshift
    if x > xshift + width:
        curve = height + yshift
    elif x < xshift:
        curve = yshift
    return curve


def gaussian_kernel(size, sigma):
    """
    Generate a Gaussian kernel for smoothing.

    Args:
        size: Size of the kernel (should be odd)
        sigma: Standard deviation of the Gaussian distribution

    Returns:
        numpy array: Normalized Gaussian kernel
    """
    if size % 2 == 0:
        size += 1  # Ensure odd size

    kernel = np.zeros(size)
    center = size // 2

    # Generate Gaussian values
    for i in range(size):
        x = i - center
        kernel[i] = np.exp(-(x * x) / (2 * sigma * sigma))

    # Normalize the kernel
    kernel = kernel / np.sum(kernel)
    return kernel


def apply_gaussian_smooth(values, sigma=1.0, kernel_size=None):
    """
    Apply Gaussian smoothing to a 1D array of values.

    Args:
        values: numpy array of values to smooth
        sigma: Standard deviation for Gaussian kernel
        kernel_size: Size of the kernel (auto-calculated if None)

    Returns:
        numpy array: Smoothed values
    """
    if len(values) < 3:
        return values.copy()

    # Auto-calculate kernel size if not provided
    if kernel_size is None:
        # Rule of thumb: kernel size = 6 * sigma + 1 (and make it odd)
        kernel_size = int(6 * sigma) + 1
        if kernel_size % 2 == 0:
            kernel_size += 1

    # Limit kernel size to array length
    kernel_size = min(kernel_size, len(values))
    if kernel_size % 2 == 0:
        kernel_size -= 1

    # Generate Gaussian kernel
    kernel = gaussian_kernel(kernel_size, sigma)

    # Apply convolution with edge handling
    smoothed = np.convolve(values, kernel, mode="same")

    # Preserve endpoints to maintain curve boundaries
    smoothed[0] = values[0]
    smoothed[-1] = values[-1]

    return smoothed


def butterworth_lowpass_filter(values, cutoff_freq=0.3, order=2):
    """
    Apply Butterworth low-pass filter for jitter removal.

    This is a simplified implementation that doesn't require scipy.
    Uses a recursive filter approximation.

    Args:
        values: numpy array of values to filter
        cutoff_freq: Cutoff frequency (0.0 to 1.0, where 1.0 is Nyquist)
        order: Filter order (higher = steeper rolloff)

    Returns:
        numpy array: Filtered values
    """
    if len(values) < 3:
        return values.copy()

    # Simple recursive low-pass filter approximation
    # This is a simplified version that gives similar results to Butterworth
    alpha = cutoff_freq
    filtered = values.copy().astype(np.float64)

    # Forward pass
    for i in range(1, len(filtered)):
        filtered[i] = alpha * values[i] + (1 - alpha) * filtered[i - 1]

    # Backward pass for zero-phase filtering
    for i in range(len(filtered) - 2, -1, -1):
        filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i + 1]

    # Apply multiple passes for higher order effect
    for _ in range(order - 1):
        # Forward pass
        for i in range(1, len(filtered)):
            filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i - 1]

        # Backward pass
        for i in range(len(filtered) - 2, -1, -1):
            filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i + 1]

    return filtered


def butterworth_lowpass_filter_time_aware(values, frames, cutoff_freq=0.3, order=2):
    """
    Apply Butterworth low-pass filter for jitter removal with proper time-aware spacing.

    This version properly handles non-uniform keyframe spacing by creating a temporally
    resampled version of the data, applying the filter, and then resampling back.
    This prevents slope discontinuities and preserves natural curve behavior.

    Args:
        values: numpy array of values to filter
        frames: numpy array of frame positions corresponding to values
        cutoff_freq: Cutoff frequency (0.0 to 1.0, where 1.0 is Nyquist)
        order: Filter order (higher = steeper rolloff)

    Returns:
        numpy array: Filtered values
    """
    if len(values) < 3 or len(frames) < 3:
        return values.copy()

    if len(values) != len(frames):
        return values.copy()

    # Calculate time deltas between consecutive keyframes
    time_deltas = np.diff(frames)

    # Find the minimum time delta to determine resampling rate
    min_delta = np.min(time_deltas)
    max_delta = np.max(time_deltas)

    if min_delta <= 0:
        return values.copy()

    # If all keyframes are uniformly spaced, use simple filtering
    if max_delta / min_delta < 2.0:  # Less than 2x variation in spacing
        return _butterworth_uniform_spacing(values, cutoff_freq, order)

    # Create a uniform time grid for resampling
    frame_start = frames[0]
    frame_end = frames[-1]

    # Use a sampling rate that captures the finest detail
    # but is practical for computation
    resample_delta = min(min_delta, 1.0)  # At least 1 frame resolution
    uniform_frames = np.arange(frame_start, frame_end + resample_delta, resample_delta)

    # Interpolate values onto uniform grid
    uniform_values = np.interp(uniform_frames, frames, values)

    # Apply standard Butterworth filter to uniformly sampled data
    filtered_uniform = _butterworth_uniform_spacing(uniform_values, cutoff_freq, order)

    # Interpolate back to original frame positions
    filtered_values = np.interp(frames, uniform_frames, filtered_uniform)

    return filtered_values


def _butterworth_uniform_spacing(values, cutoff_freq=0.3, order=2):
    """
    Apply Butterworth low-pass filter assuming uniform spacing between samples.
    This is the standard implementation for uniformly sampled data.
    """
    if len(values) < 3:
        return values.copy()

    # Convert cutoff frequency to alpha for exponential smoothing
    # This is a simplified Butterworth approximation
    alpha = cutoff_freq
    alpha = np.clip(alpha, 0.01, 0.99)

    filtered = values.copy().astype(np.float64)

    # Apply multiple passes for higher order effect
    for _ in range(order):
        # Forward pass
        for i in range(1, len(filtered)):
            filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i - 1]

        # Backward pass for zero-phase filtering
        for i in range(len(filtered) - 2, -1, -1):
            filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i + 1]

    return filtered


def _apply_time_aware_gaussian_smooth(values, frames, sigma):
    """
    Apply Gaussian smoothing with proper time-aware spacing.

    This function properly handles non-uniform keyframe spacing by creating a temporally
    resampled version of the data, applying the smoothing, and then resampling back.

    Args:
        values: numpy array of values to smooth
        frames: numpy array of frame positions corresponding to values
        sigma: Gaussian sigma parameter for smoothing strength

    Returns:
        numpy array: Smoothed values
    """
    if len(values) < 3 or len(frames) < 3:
        return values.copy()

    if len(values) != len(frames):
        return values.copy()

    # Calculate time deltas between consecutive keyframes
    time_deltas = np.diff(frames)

    # Find the minimum time delta to determine resampling rate
    min_delta = np.min(time_deltas)
    max_delta = np.max(time_deltas)

    if min_delta <= 0:
        return values.copy()

    # If all keyframes are uniformly spaced, use simple smoothing
    if max_delta / min_delta < 2.0:  # Less than 2x variation in spacing
        return apply_gaussian_smooth(values, sigma)

    # Create a uniform time grid for resampling
    frame_start = frames[0]
    frame_end = frames[-1]

    # Use a sampling rate that captures the finest detail
    # but is practical for computation
    resample_delta = min(min_delta, 1.0)  # At least 1 frame resolution
    uniform_frames = np.arange(frame_start, frame_end + resample_delta, resample_delta)

    # Interpolate values onto uniform grid
    uniform_values = np.interp(uniform_frames, frames, values)

    # Apply standard Gaussian smoothing to uniformly sampled data
    smoothed_uniform = apply_gaussian_smooth(uniform_values, sigma)

    # Interpolate back to original frame positions
    smoothed_values = np.interp(frames, uniform_frames, smoothed_uniform)

    return smoothed_values


def get_context_aware_visible_fcurves(context, action=None, selected_element=False):
    """
    Get fcurves in a context-aware way that works from any context.

    Args:
        context: Blender context
        action: Optional action to get fcurves from
        selected_element: If True, restrict fcurves to those of the active element

    Returns:
        List of visible/relevant fcurves
    """
    from .classes import ActiveElement

    if not action and context.active_object and context.active_object.animation_data:
        action = context.active_object.animation_data.action

    if not action:
        return []

    # Try to get visible fcurves from context if we're in an animation editor
    if context.area and context.area.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR", "TIMELINE"}:
        try:
            visible_fcurves = context.visible_fcurves
            if visible_fcurves is not None:
                # Filter out hidden fcurves in graph editor
                if context.area.type == "GRAPH_EDITOR":
                    fcurves = [f for f in visible_fcurves if not f.hide]
                else:
                    fcurves = list(visible_fcurves)

                # Apply selected element filter if requested
                if selected_element:
                    element = ActiveElement.get(context)
                    fcurves = ActiveElement.filter_fcurves_for_element(fcurves, element, context)

                return fcurves
        except (AttributeError, TypeError):
            pass

    # Fallback to all fcurves from the action
    fcurves = list(all_fcurves(action))

    # Apply selected element filter if requested
    if selected_element:
        element = ActiveElement.get(context)
        fcurves = ActiveElement.filter_fcurves_for_element(fcurves, element, context)

    return fcurves
