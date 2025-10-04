"""
Keyframe utilities - Simplified wrappers for GP keyframe handling

This module provides centralized functions to detect and collect GP keyframes,
reducing code duplication across operators.

Scope: GP drawing frames + GP-specific animated properties (layer attrs, materials, modifiers, shader effects)
"""

def has_keyframe_at_frame(obj, frame):
    """
    Check if there's ANY keyframe at the specified frame in a GP object.

    Checks:
    - GP drawing frames in all visible, unlocked layers
    - GP layer attribute keyframes (opacity, tint, etc.)
    - GP material animation keyframes
    - GP modifier animation keyframes
    - GP shader effect animation keyframes

    Args:
        obj: Grease Pencil object to check
        frame: Frame number to check for keyframes

    Returns:
        bool: True if any keyframe exists at the specified frame
    """
    if not obj or obj.type != 'GREASEPENCIL':
        return False

    gpencil_data = obj.data

    if not gpencil_data or not gpencil_data.layers:
        return False

    # Check GP drawing frames in all visible, unlocked layers
    for layer in gpencil_data.layers:
        if not layer.lock and not layer.hide:
            for gp_frame in layer.frames:
                if gp_frame.frame_number == frame:
                    return True

    # Check GP layer attribute keyframes (object-level)
    if obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for fcurve in action.fcurves:
            # Only check layer-specific fcurves
            if 'layers[' in fcurve.data_path:
                for keyframe in fcurve.keyframe_points:
                    if abs(keyframe.co[0] - frame) < 0.01:
                        return True

    # Check GP layer attribute keyframes (GP data-level)
    if gpencil_data.animation_data and gpencil_data.animation_data.action:
        action = gpencil_data.animation_data.action
        for fcurve in action.fcurves:
            # Only check layer-specific fcurves
            if 'layers[' in fcurve.data_path:
                for keyframe in fcurve.keyframe_points:
                    if abs(keyframe.co[0] - frame) < 0.01:
                        return True

    # Check GP material animation keyframes
    if gpencil_data.materials:
        for material in gpencil_data.materials:
            if material and material.animation_data and material.animation_data.action:
                action = material.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        if abs(keyframe.co[0] - frame) < 0.01:
                            return True

    # Check GP modifier animation keyframes
    if obj.modifiers and obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for modifier in obj.modifiers:
            modifier_path_prefix = f'modifiers["{modifier.name}"]'
            for fcurve in action.fcurves:
                if fcurve.data_path.startswith(modifier_path_prefix):
                    for keyframe in fcurve.keyframe_points:
                        if abs(keyframe.co[0] - frame) < 0.01:
                            return True

    # Check GP shader effect animation keyframes
    if obj.shader_effects and obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for effect in obj.shader_effects:
            effect_path_prefix = f'shader_effects["{effect.name}"]'
            for fcurve in action.fcurves:
                if fcurve.data_path.startswith(effect_path_prefix):
                    for keyframe in fcurve.keyframe_points:
                        if abs(keyframe.co[0] - frame) < 0.01:
                            return True

    return False


def get_keyframes_after_frame(obj, frame):
    """
    Get all keyframes that come after the specified frame for a GP object.

    Collects keyframes from:
    - GP drawing frames in all visible, unlocked layers
    - GP layer attribute animations
    - GP material animations
    - GP modifier animations
    - GP shader effect animations

    Args:
        obj: Grease Pencil object
        frame: Frame number to search after

    Returns:
        list: Sorted list of unique frame numbers after the specified frame
    """
    keyframes = []

    if not obj or obj.type != 'GREASEPENCIL':
        return keyframes

    gpencil_data = obj.data

    if not gpencil_data or not gpencil_data.layers:
        return keyframes

    # Collect GP drawing frames
    for layer in gpencil_data.layers:
        if not layer.lock and not layer.hide:
            for gp_frame in layer.frames:
                if gp_frame.frame_number > frame:
                    keyframes.append(gp_frame.frame_number)

    # Collect object-level animation keyframes (layer attributes, modifiers, effects)
    if obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                kf_frame = int(keyframe.co[0])
                if kf_frame > frame:
                    keyframes.append(kf_frame)

    # Collect GP data-level animation keyframes (layer attributes)
    if gpencil_data.animation_data and gpencil_data.animation_data.action:
        action = gpencil_data.animation_data.action
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                kf_frame = int(keyframe.co[0])
                if kf_frame > frame:
                    keyframes.append(kf_frame)

    # Collect material animation keyframes
    if gpencil_data.materials:
        for material in gpencil_data.materials:
            if material and material.animation_data and material.animation_data.action:
                action = material.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if kf_frame > frame:
                            keyframes.append(kf_frame)

    return sorted(list(set(keyframes)))


def get_all_keyframes_in_range(obj, start_frame, end_frame):
    """
    Get all keyframes in the specified range (inclusive) for a GP object.

    Collects keyframes from all GP-related animation sources.

    Args:
        obj: Grease Pencil object
        start_frame: Start of range (inclusive)
        end_frame: End of range (inclusive)

    Returns:
        list: Sorted list of unique frame numbers in the range
    """
    keyframes = []

    if not obj or obj.type != 'GREASEPENCIL':
        return keyframes

    gpencil_data = obj.data

    if not gpencil_data or not gpencil_data.layers:
        return keyframes

    # Collect GP drawing frames
    for layer in gpencil_data.layers:
        if not layer.lock and not layer.hide:
            for gp_frame in layer.frames:
                if start_frame <= gp_frame.frame_number <= end_frame:
                    keyframes.append(gp_frame.frame_number)

    # Collect object-level animation keyframes
    if obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                kf_frame = int(keyframe.co[0])
                if start_frame <= kf_frame <= end_frame:
                    keyframes.append(kf_frame)

    # Collect GP data-level animation keyframes
    if gpencil_data.animation_data and gpencil_data.animation_data.action:
        action = gpencil_data.animation_data.action
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                kf_frame = int(keyframe.co[0])
                if start_frame <= kf_frame <= end_frame:
                    keyframes.append(kf_frame)

    # Collect material animation keyframes
    if gpencil_data.materials:
        for material in gpencil_data.materials:
            if material and material.animation_data and material.animation_data.action:
                action = material.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if start_frame <= kf_frame <= end_frame:
                            keyframes.append(kf_frame)

    return sorted(list(set(keyframes)))


def get_all_keyframes(obj):
    """
    Get ALL keyframes for a GP object.

    Collects keyframes from all GP-related animation sources.

    Args:
        obj: Grease Pencil object

    Returns:
        list: Sorted list of all unique frame numbers
    """
    keyframes = []

    if not obj or obj.type != 'GREASEPENCIL':
        return keyframes

    gpencil_data = obj.data

    if not gpencil_data or not gpencil_data.layers:
        return keyframes

    # Collect all GP drawing frames
    for layer in gpencil_data.layers:
        if not layer.lock and not layer.hide:
            for gp_frame in layer.frames:
                keyframes.append(gp_frame.frame_number)

    # Collect object-level animation keyframes
    if obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframes.append(int(keyframe.co[0]))

    # Collect GP data-level animation keyframes
    if gpencil_data.animation_data and gpencil_data.animation_data.action:
        action = gpencil_data.animation_data.action
        for fcurve in action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframes.append(int(keyframe.co[0]))

    # Collect material animation keyframes
    if gpencil_data.materials:
        for material in gpencil_data.materials:
            if material and material.animation_data and material.animation_data.action:
                action = material.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        keyframes.append(int(keyframe.co[0]))

    return sorted(list(set(keyframes)))
