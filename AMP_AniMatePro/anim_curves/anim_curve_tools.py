"""
AniMate Pro - Curve Tools

This module provides curve manipulation tools for F-curves in the Graph Editor.
Based on the functionality from anim_aide, these tools allow for various curve
operations including blending, easing, scaling, and smoothing.

All operations work on selected keyframes and provide real-time interactive
feedback through the GUI pins system.
"""

import bpy
import bmesh
import mathutils
from mathutils import Vector
import math
import numpy as np
import random
from typing import List, Tuple, Dict, Optional, Any
from ..utils.gui_pins import ScopeGUI, BlendType
from ..utils import get_prefs, refresh_ui
from ..utils.curve import (
    s_curve,
    apply_gaussian_smooth,
    butterworth_lowpass_filter,
    butterworth_lowpass_filter_time_aware,
    _apply_time_aware_gaussian_smooth,
    get_selected_keyframes_range_offset,
)
from ..utils.key import get_property_default_value
from . import anim_curves_tools_helpers as act_help


# =============================================================================
# CACHED BLEND OPERATIONS
# =============================================================================


def blend_ease(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    blend_ease

    Factor behavior:
    - Factor = 0: C-curve ease (sin-based)
    - Factor > 0: Bias towards ease-out
    - Factor < 0: Bias towards ease-in
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get reference coordinates using consolidated helper
    coords = act_help.calculate_reference_coordinates(
        fcurve, selected_data, pin_positions, act_help.CurveOperationType.BLEND_EASE
    )

    if abs(coords["local_x"]) < 0.001:  # Prevent division by zero
        return

    # Calculate factor-based ease curve
    factor_clamped = act_help.clamp_factor(factor)
    flipflop = abs(factor_clamped)

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate frame ratio (position along the interpolation line)
        x = frame - coords["left_neighbor_x"]
        frame_ratio = x / coords["local_x"]

        # Clamp frame_ratio to valid range [0, 1] to prevent invalid power operations
        frame_ratio_clamped = np.clip(frame_ratio, 0.0, 1.0)

        # Calculate ease curve value based on factor
        if abs(factor_clamped) < 0.001:  # Factor approximately 0
            # Standard C-curve ease using sin
            curve_value = np.sin(frame_ratio_clamped * np.pi / 2)
        elif factor_clamped > 0:
            # Bias towards ease-out (right side)
            base_curve = np.sin(frame_ratio_clamped * np.pi / 2)
            ease_out_curve = np.power(frame_ratio_clamped, 1.0 / (1.0 + flipflop * 2.0))
            curve_value = base_curve * (1 - flipflop) + ease_out_curve * flipflop
        else:
            # Bias towards ease-in (left side)
            base_curve = np.sin(frame_ratio_clamped * np.pi / 2)
            ease_in_curve = np.power(frame_ratio_clamped, 1.0 + flipflop * 2.0)
            curve_value = base_curve * (1 - flipflop) + ease_in_curve * flipflop

        # Calculate target value
        target_values[i] = coords["left_neighbor_y"] + coords["local_y"] * curve_value

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def blend_frame(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    blend_frame.

    Factor behavior:
    - Factor = 0: Linear interpolation between reference frames
    - Factor > 0: Bias towards right reference frame
    - Factor < 0: Bias towards left reference frame
    """
    indices = selected_data["indices"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Use pin positions as reference frames
    start_frame = pin_positions[1]  # Main left pin
    end_frame = pin_positions[2]  # Main right pin

    # Calculate factor-based frame blending
    factor_clamped = act_help.clamp_factor(factor)
    max_factor = abs(act_help.clamp_factor(1.0))
    factor_zero_one = (factor_clamped + max_factor) / (2.0 * max_factor)  # Convert to 0..1 range based on max factor

    # Create t values for interpolation
    t_values = np.linspace(0, 1, len(indices))

    # Blend between reference frames based on factor
    target_frames = start_frame + (end_frame - start_frame) * (t_values * factor_zero_one + (1 - factor_zero_one) * 0.5)

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_frames - original_frames
    scaled_difference = effect_difference * intensity_multiplier
    new_frames = original_frames + scaled_difference

    # Update cache
    cache.update_selected_frames(fcurve, new_frames)


def blend_neighbor(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    blend_neighbor

    Factor behavior:
    - Factor = 0: No change (keyframes remain at original values)
    - Factor > 0: Blend towards right neighbor from original positions
    - Factor < 0: Blend towards left neighbor from original positions
    - Factor = 1: Reach the neighbor value exactly
    - Factor = 2 (with overshoot): Overshoot beyond the neighbor value
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) == 0:
        return

    # Get dynamic reference keyframes (left and right neighbors)
    ref_data = act_help.get_dynamic_reference_keyframes(
        fcurve, pin_positions, indices, act_help.CurveOperationType.BLEND_NEIGHBOR
    )

    if ref_data and ref_data["left_value"] is not None and ref_data["right_value"] is not None:
        left_neighbor_y = ref_data["left_value"]
        right_neighbor_y = ref_data["right_value"]
    else:
        # Fallback to first and last selected keyframes
        left_neighbor_y = original_values[0]
        right_neighbor_y = original_values[-1]

    # Calculate factor-based neighbor blending
    factor_clamped = act_help.clamp_factor(factor)

    # Use absolute value of factor as blend strength
    blend_factor = abs(factor_clamped)

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate delta (difference) from original values to target neighbor
        if factor_clamped < 0:
            # Blend towards left neighbor
            delta = left_neighbor_y - original_value
        else:
            # Blend towards right neighbor (including factor = 0)
            delta = right_neighbor_y - original_value

        # Apply the blend: original + delta * blend_factor
        target_values[i] = original_value + delta * blend_factor

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def tween(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    tween

    Factor behavior:
    - Factor = 0: Linear interpolation between neighbors
    - Factor > 0: Bias towards right neighbor
    - Factor < 0: Bias towards left neighbor
    - Factor = 1: Reach the right neighbor exactly
    - Factor = 2 (with overshoot): Overshoot beyond the right neighbor
    - Factor = -2 (with overshoot): Overshoot beyond the left neighbor
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get reference coordinates using consolidated helper
    coords = act_help.calculate_reference_coordinates(
        fcurve, selected_data, pin_positions, act_help.CurveOperationType.TWEEN
    )

    if abs(coords["local_x"]) < 0.001:  # Prevent division by zero
        return

    # Calculate factor-based tween with overshoot support
    factor_clamped = act_help.clamp_factor(factor)
    max_factor = act_help.get_max_factor()

    # Convert factor to interpolation value with overshoot support
    # The pattern follows: factor_zero_one = (factor + max_factor) / (2 * max_factor)
    # This maps factor range [-max_factor, max_factor] to [0, 1] when no overshoot
    # Or to a wider range when overshoot is enabled

    # For standard interpolation: factor 0 = 0.5, factor max_factor = 1.0, factor -max_factor = 0.0
    # But for overshoot: we want factor 1 = 1.0 (right neighbor), factor 2 = 1.5 (overshoot)
    if max_factor == 1.0:
        # No overshoot: standard behavior
        factor_zero_one = (factor_clamped + 1.0) / 2.0
    else:
        # Overshoot enabled: allow interpolation values beyond [0,1]
        # Map [-2, 2] to [-0.5, 1.5] so factor=1 gives 1.0 and factor=2 gives 1.5
        factor_zero_one = factor_clamped / 2.0 + 0.5

    # Calculate tween value with overshoot support
    # factor_zero_one can now go beyond [0,1] when overshoot is enabled
    # When factor = 2 (max overshoot), factor_zero_one = 1.5 (overshoot beyond right neighbor)
    # When factor = -2 (min overshoot), factor_zero_one = -0.5 (overshoot beyond left neighbor)
    tween_value = coords["left_neighbor_y"] + coords["local_y"] * factor_zero_one

    # Apply the same target value to all selected keyframes (tween behavior)
    target_values = np.full_like(original_values, tween_value)

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def scale_average(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    scale_average

    Factor behavior:
    - Factor = 0: No scaling
    - Factor > 0: Scale away from average
    - Factor < 0: Scale towards average
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) == 0:
        return

    # Calculate average value
    average_value = np.mean(original_values)

    # Calculate factor-based scaling (no overshoot for this operation)
    factor_clamped = act_help.clamp_factor_no_overshoot(factor)
    factor_zero_two = factor_clamped + 1.0  # Convert to 0..2 range without overshoot

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Distance from average
        distance = original_value - average_value
        # Scale the distance based on factor
        scaled_distance = distance * factor_zero_two
        # Calculate new value
        target_values[i] = average_value + scaled_distance

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def smooth(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    smooth - Efficient Gaussian smoothing using numpy convolution

    Factor behavior:
    - Factor = 0: Standard Gaussian smoothing (sigma = 1.0)
    - Factor > 0: Increase smoothing strength (higher sigma)
    - Factor < 0: Decrease smoothing strength (lower sigma)

    Uses efficient numpy-based Gaussian kernel convolution for optimal performance.
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Calculate sigma based on factor with overshoot support
    factor_clamped = act_help.clamp_factor(factor)
    base_sigma = 1.5  # Increased from 1.0 for stronger default smoothing

    # Map factor to sigma range with proper overshoot handling
    if factor_clamped >= 0:
        # Positive factor: increase smoothing (higher sigma)
        sigma = base_sigma + factor_clamped * 2.0  # Range: 1.5 to 3.5 (or higher with overshoot)
    else:
        # Negative factor: decrease smoothing (lower sigma)
        sigma = base_sigma + factor_clamped * 1.0  # Range: 0.5 to 1.5 (or lower with overshoot)

    # Minimum sigma to prevent numerical issues
    sigma = max(0.1, sigma)

    # Apply efficient Gaussian smoothing
    if len(original_values) >= 3:
        smoothed_values = _gaussian_smooth_efficient(original_values, sigma)
    elif len(original_values) == 2:
        # For 2 keyframes, apply simple smoothing by weighted averaging
        smoothed_values = original_values.copy()
        weight = min(0.5, sigma * 0.3)  # Scale weight based on sigma
        smoothed_values[0] = original_values[0] * (1 - weight) + original_values[1] * weight
        smoothed_values[1] = original_values[0] * weight + original_values[1] * (1 - weight)
    else:
        smoothed_values = original_values.copy()

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = smoothed_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def _gaussian_smooth_efficient(values, sigma):
    """
    Efficient Gaussian smoothing using numpy convolution.

    Creates a Gaussian kernel and applies it via convolution for optimal performance.
    Handles edge effects using reflection padding.
    """
    # Calculate kernel size based on sigma (truncate at 3 standard deviations)
    kernel_size = int(2 * np.ceil(3 * sigma) + 1)
    if kernel_size % 2 == 0:
        kernel_size += 1  # Ensure odd kernel size

    # Create Gaussian kernel
    x = np.arange(kernel_size) - kernel_size // 2
    kernel = np.exp(-(x**2) / (2 * sigma**2))
    kernel = kernel / np.sum(kernel)  # Normalize

    # Pad values using reflection to handle edges
    pad_size = kernel_size // 2
    padded_values = np.pad(values, pad_size, mode="reflect")

    # Apply convolution
    smoothed_padded = np.convolve(padded_values, kernel, mode="same")

    # Extract the original length result
    smoothed_values = smoothed_padded[pad_size:-pad_size]

    return smoothed_values


def smooth_jitter(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    smooth_jitter - Peak reduction filter for removing abrupt changes and jitter

    Factor behavior:
    - Factor = -1.0: No effect (original values unchanged)
    - Factor = 0: Moderate peak reduction (removes big spikes and abrupt changes)
    - Factor = 1.0: Full effect (maximum peak reduction and jitter removal)

    Focuses on detecting and smoothing abrupt changes between keyframes rather than
    general curve smoothing. Uses adaptive filtering based on local variation.
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Calculate adaptive filtering strength based on factor
    factor_clamped = act_help.clamp_factor(factor)

    # Map factor from [-1, 1] to [0, 1] range for effect strength
    # -1 = no effect, 0 = moderate effect, +1 = full effect
    effect_strength = (factor_clamped + 1.0) / 2.0  # Convert from [-1,1] to [0,1]

    # Apply adaptive peak reduction filtering only if effect_strength > 0
    if effect_strength > 0.001:  # Only apply if there's meaningful effect
        if len(original_values) >= 3:
            filtered_values = _adaptive_peak_reduction(original_values, effect_strength)
        elif len(original_values) == 2:
            # For 2 keyframes, apply minimal smoothing only if there's a significant difference
            filtered_values = original_values.copy()
            value_diff = abs(original_values[1] - original_values[0])
            # Only smooth if the difference is significant (could be a spike)
            if value_diff > 0.1:  # Threshold for considering it a potential spike
                smoothing_factor = 0.1 + effect_strength * 0.3  # Scale with effect strength
                filtered_values[0] = original_values[0] * (1 - smoothing_factor) + original_values[1] * smoothing_factor
                filtered_values[1] = original_values[0] * smoothing_factor + original_values[1] * (1 - smoothing_factor)
        else:
            filtered_values = original_values.copy()
    else:
        # No effect when factor is -1 or close to it
        filtered_values = original_values.copy()

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = filtered_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def _adaptive_peak_reduction(values, effect_strength):
    """
    Adaptive peak reduction filter that focuses on removing abrupt changes and spikes.

    Analyzes local variation to identify peaks and applies selective smoothing
    based on the severity of the change relative to neighboring values.

    Args:
        values: Array of values to filter
        effect_strength: Effect strength from 0.0 (no effect) to 1.0 (full effect)
    """
    if len(values) < 3:
        return values.copy()

    filtered = values.copy().astype(np.float64)

    # Calculate local variation (second derivative approximation)
    # This helps identify abrupt changes and peaks
    for i in range(1, len(values) - 1):
        # Calculate second derivative at this point (curvature)
        left_slope = values[i] - values[i - 1]
        right_slope = values[i + 1] - values[i]
        curvature = abs(right_slope - left_slope)

        # Calculate local variation relative to neighbors
        neighbor_avg = (values[i - 1] + values[i + 1]) / 2.0
        local_deviation = abs(values[i] - neighbor_avg)

        # Determine if this is a peak/spike based on curvature and deviation
        # Higher values indicate more abrupt changes that should be smoothed
        peak_strength = curvature + local_deviation

        # Use effect_strength to control filtering behavior
        # effect_strength = 0: no filtering
        # effect_strength = 1: maximum filtering

        # Base threshold for detecting peaks - lower means more sensitive
        base_threshold = 0.3

        # Adjust threshold based on effect strength
        # Higher effect_strength = lower threshold = more filtering
        threshold = base_threshold * (1.0 - effect_strength * 0.7)

        # Determine smoothing amount based on peak strength and effect strength
        if peak_strength > threshold:
            # Scale smoothing amount by effect strength
            # More effect strength = more smoothing
            smoothing_amount = 0.4 * effect_strength * min(1.0, peak_strength / base_threshold)
        else:
            # For smaller variations, apply gentle smoothing scaled by effect strength
            smoothing_amount = 0.1 * effect_strength * (peak_strength / base_threshold)

        # Clamp smoothing amount
        smoothing_amount = np.clip(smoothing_amount, 0.0, 0.8)

        # Apply adaptive smoothing - blend current value toward neighbor average
        if smoothing_amount > 0:
            filtered[i] = values[i] * (1 - smoothing_amount) + neighbor_avg * smoothing_amount

    return filtered


def _butterworth_filter_efficient(values, cutoff_freq, order=2):
    """
    Efficient Butterworth low-pass filter using numpy.

    Implements a digital Butterworth filter using recursive filtering approach
    for optimal performance without requiring scipy dependencies.
    """
    if len(values) < 3:
        return values.copy()

    # Convert cutoff frequency to filter coefficient (alpha)
    # This is a simplified digital implementation of Butterworth filter
    # Alpha determines the filter strength: lower alpha = more filtering
    alpha = cutoff_freq
    alpha = np.clip(alpha, 0.01, 0.99)

    filtered = values.copy().astype(np.float64)

    # Apply multiple passes for higher order effect
    for _ in range(order):
        # Forward pass - exponential smoothing
        for i in range(1, len(filtered)):
            filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i - 1]

        # Backward pass for zero-phase filtering (similar to filtfilt)
        for i in range(len(filtered) - 2, -1, -1):
            filtered[i] = alpha * filtered[i] + (1 - alpha) * filtered[i + 1]

    return filtered


def blend_infinite(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    blend_infinite

    Factor behavior:
    - Factor = 0: No change (keyframes remain at original values)
    - Factor > 0: Blend towards infinite extension from right neighbor
    - Factor < 0: Blend towards infinite extension from left neighbor
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) == 0:
        return

    # Get dynamic reference keyframes (left and right neighbors)
    ref_data = act_help.get_dynamic_reference_keyframes(
        fcurve, pin_positions, indices, act_help.CurveOperationType.BLEND_INFINITE
    )

    # Get neighbor keyframes
    left_neighbor_frame = None
    left_neighbor_value = None
    right_neighbor_frame = None
    right_neighbor_value = None

    if ref_data:
        if ref_data.get("left_references"):
            left_neighbor_frame = ref_data["left_references"][-1][0]  # Closest to blend range
            left_neighbor_value = ref_data["left_references"][-1][1]
        if ref_data.get("right_references"):
            right_neighbor_frame = ref_data["right_references"][0][0]  # Closest to blend range
            right_neighbor_value = ref_data["right_references"][0][1]

    # Fallback to first and last selected keyframes if no neighbors found
    if left_neighbor_frame is None or left_neighbor_value is None:
        left_neighbor_frame = original_frames[0]
        left_neighbor_value = original_values[0]
    if right_neighbor_frame is None or right_neighbor_value is None:
        right_neighbor_frame = original_frames[-1]
        right_neighbor_value = original_values[-1]

    # Get "far" keyframes for slope calculation
    left_far_frame = None
    left_far_value = None
    right_far_frame = None
    right_far_value = None

    if ref_data:
        if ref_data.get("left_references") and len(ref_data["left_references"]) >= 2:
            left_far_frame = ref_data["left_references"][-2][0]  # Second closest
            left_far_value = ref_data["left_references"][-2][1]
        if ref_data.get("right_references") and len(ref_data["right_references"]) >= 2:
            right_far_frame = ref_data["right_references"][1][0]  # Second closest
            right_far_value = ref_data["right_references"][1][1]

    # Calculate factor-based infinite blending (no overshoot for this operation)
    factor_clamped = act_help.clamp_factor_no_overshoot(factor)
    factor_abs = abs(factor_clamped)

    # Calculate target values
    target_values = original_values.copy()

    if factor_abs > 0.001:  # Only apply if factor is not zero
        if factor_clamped < 0 and left_far_frame is not None:
            # Blend towards left infinite extension
            # Calculate slope from left_far to left_neighbor
            a = left_neighbor_frame - left_far_frame
            o = left_neighbor_value - left_far_value

            if abs(a) > 0.001:  # Avoid division by zero
                for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
                    new_a = frame - left_neighbor_frame
                    new_o = new_a * o / a
                    refe = left_neighbor_value

                    delta = refe + new_o - original_value
                    target_values[i] = original_value + delta * factor_abs

        elif factor_clamped >= 0 and right_far_frame is not None:
            # Blend towards right infinite extension
            # Calculate slope from right_neighbor to right_far
            a = right_far_frame - right_neighbor_frame
            o = right_far_value - right_neighbor_value

            if abs(a) > 0.001:  # Avoid division by zero
                for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
                    new_a = frame - right_neighbor_frame
                    new_o = new_a * o / a
                    refe = right_neighbor_value

                    delta = refe + new_o - original_value
                    target_values[i] = original_value + delta * factor_abs
        else:
            # Fallback: no far keyframes available, use simple linear extension
            if factor_clamped < 0:
                # Extend from left neighbor with zero slope
                for i, original_value in enumerate(original_values):
                    delta = left_neighbor_value - original_value
                    target_values[i] = original_value + delta * factor_abs
            else:
                # Extend from right neighbor with zero slope
                for i, original_value in enumerate(original_values):
                    delta = right_neighbor_value - original_value
                    target_values[i] = original_value + delta * factor_abs

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def blend_default(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    blend_default

    Factor behavior:
    - Factor = 0: Keep current values (no change)
    - Factor = 1: Blend to default value
    - Factor = -1: Scale away from default value (opposite direction)
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) == 0:
        return

    # Advanced default value detection using bl_rna properties
    default_value = get_property_default_value(fcurve)

    # Calculate factor-based default blending (no overshoot for this operation)
    factor_clamped = act_help.clamp_factor_no_overshoot(factor)

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate the distance from original value to default
        distance_to_default = default_value - original_value

        if factor_clamped >= 0:
            # Factor 0 to 1: Blend from current to default
            target_values[i] = original_value + distance_to_default * factor_clamped
        else:
            # Factor -1 to 0: Scale away from default (opposite direction)
            target_values[i] = original_value - distance_to_default * abs(factor_clamped)

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def blend_offset(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    blend_offset

    Factor behavior:
    - Factor = 0: Standard offset between first and last
    - Factor > 0: Increase offset amount
    - Factor < 0: Decrease offset amount (can reverse)
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Calculate offset based on neighbors
    first_value = original_values[0]
    last_value = original_values[-1]
    base_offset = (last_value - first_value) / len(indices)

    # Apply factor to the offset
    factor_clamped = act_help.clamp_factor(factor)
    factor_zero_two = factor_clamped + abs(act_help.clamp_factor(1.0))  # Convert to 0..2 range based on max factor

    # Scale the offset based on factor
    adjusted_offset = base_offset * factor_zero_two

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Apply offset based on position in sequence
        target_values[i] = original_value + adjusted_offset * (i + 1)

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def ease(fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None):
    """
    ease

    This function creates smooth transitions between neighboring keyframes in a "C" shape
    manner (ease-in or ease-out). It takes into account the actual frame separation
    to maintain proper slopes even through gaps.

    Factor behavior:
    - Factor = 0: Linear interpolation between endpoints
    - Factor > 0: Ease towards right (ease-out behavior)
    - Factor < 0: Ease towards left (ease-in behavior)
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get reference coordinates using consolidated helper
    coords = act_help.calculate_reference_coordinates(
        fcurve, selected_data, pin_positions, act_help.CurveOperationType.EASE
    )

    if abs(coords["local_x"]) < 0.001:  # Prevent division by zero
        return

    # Calculate factor-based ease curve
    factor_clamped = act_help.clamp_factor(factor)
    flipflop = abs(factor_clamped)

    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate frame ratio (position along the interpolation line)
        x = frame - coords["left_neighbor_x"]
        frame_ratio = x / coords["local_x"]

        if factor_clamped > 0:
            shift = -1
        else:
            shift = 0

        # Calculate slope based on factor strength
        slope = 1 + (5 * flipflop)

        # Use s_curve function
        ease_y = s_curve(frame_ratio, slope=slope, width=2, height=2, xshift=shift, yshift=shift)

        # Calculate new value
        target_values[i] = coords["left_neighbor_y"] + coords["local_y"] * ease_y

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def ease_to_ease(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    ease_to_ease

    This creates a smooth S-curve (ease-in and ease-out simultaneously) that transitions
    between the neighboring keyframes. The factor controls the shape of the S-curve with
    continuous smooth transitions.

    Factor behavior:
    - Factor = 0: Standard S-curve (smooth sigmoid transition)
    - Factor > 0: More gradual at start, sharper at end (ease-out bias)
    - Factor < 0: Sharper at start, more gradual at end (ease-in bias)

    The transition is now smooth and continuous across the entire factor range,
    similar to other blending operations.
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get reference coordinates using consolidated helper
    coords = act_help.calculate_reference_coordinates(
        fcurve, selected_data, pin_positions, act_help.CurveOperationType.EASE_TO_EASE
    )

    if abs(coords["local_x"]) < 0.001:  # Prevent division by zero
        return

    # Calculate factor-based S-curve
    factor_clamped = act_help.clamp_factor(factor)
    flipflop = abs(factor_clamped)

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate frame ratio (position along the interpolation line)
        x = frame - coords["left_neighbor_x"]
        frame_ratio = x / coords["local_x"]

        # Clamp frame_ratio to valid range [0, 1] to prevent invalid operations
        frame_ratio_clamped = np.clip(frame_ratio, 0.0, 1.0)

        # Calculate S-curve value using the s_curve function for smoother transitions
        if abs(factor_clamped) < 0.001:
            # Factor = 0: Standard S-curve with default parameters
            curve_value = s_curve(frame_ratio_clamped, slope=2.0, width=1.0, height=1.0, xshift=0.0, yshift=0.0)
        else:
            # Factor != 0: Modify the S-curve shape with bias control
            # Adjust slope based on factor to create asymmetric S-curves
            if factor_clamped < 0:
                # Ease-out bias: gentler start (lower slope), sharper end
                # Vary slope from 1.0 to 6.0 based on factor
                slope = 2.0 + flipflop * 4.0
                # Shift the curve slightly to the left for ease-out effect
                xshift = -flipflop * 0.2
            else:
                # Ease-in bias: sharper start (higher slope), gentler end
                # Vary slope from 1.0 to 6.0 based on factor
                slope = 2.0 + flipflop * 4.0
                # Shift the curve slightly to the right for ease-in effect
                xshift = flipflop * 0.2

            # Apply the s_curve function with adjusted parameters
            curve_value = s_curve(frame_ratio_clamped, slope=slope, width=1.0, height=1.0, xshift=xshift, yshift=0.0)

        # Ensure curve_value stays within valid bounds
        curve_value = np.clip(curve_value, 0.0, 1.0)

        # Calculate target value
        target_values[i] = coords["left_neighbor_y"] + coords["local_y"] * curve_value

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def shear(
    fcurve,
    selected_data,
    factor,
    intensity,
    start_blend,
    end_blend,
    pin_positions,
    cache,
    direction,
    noise_properties=None,
):
    """
    Unified shear function that handles both left and right shear directions.

    This function uses the blend limits (pin positions) as reference for shear calculation,
    making the shear effect respect the blend range rather than just the selected keyframes.

    Args:
        fcurve: The F-curve being operated on
        selected_data: Data about selected keyframes
        factor: Shear strength (-1.0 to 1.0)
        intensity: Effect intensity (0-100)
        start_blend: Start blend type
        end_blend: End blend type
        pin_positions: Pin positions for reference
        cache: Keyframe cache
        direction: 'left' or 'right' for shear direction
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Calculate factor-based shear strength
    factor_clamped = act_help.clamp_factor(factor)

    # Get reference coordinates using the appropriate operation type
    operation_type = (
        act_help.CurveOperationType.SHEAR_LEFT if direction == "left" else act_help.CurveOperationType.SHEAR_RIGHT
    )
    coords = act_help.calculate_reference_coordinates(fcurve, selected_data, pin_positions, operation_type)

    if abs(coords["local_x"]) < 0.001:  # Prevent division by zero
        return

    # Use the blend range (from reference coordinates) for shear calculation
    left_frame = coords["left_neighbor_x"]
    right_frame = coords["right_neighbor_x"]
    frame_range = coords["local_x"]

    # Calculate value range to determine shear amount
    min_value = float(np.min(original_values))
    max_value = float(np.max(original_values))
    value_range = max_value - min_value

    # If all values are the same, use a default shear amount based on factor
    if abs(value_range) < 0.001:
        base_shear_amount = abs(factor_clamped) * 1.0  # Default shear amount
    else:
        # Use value range to scale shear effect
        base_shear_amount = value_range * abs(factor_clamped)

    # Calculate target values by applying shear gradient
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate position ratio within blend range (0.0 to 1.0)
        t = (frame - left_frame) / frame_range
        t = np.clip(t, 0.0, 1.0)  # Clamp to valid range

        # Calculate shear offset based on direction and position
        if direction == "left":
            # Left shear: maximum effect at left (t=0), no effect at right (t=1)
            shear_offset = base_shear_amount * (1.0 - t)
            # Apply factor sign for direction
            shear_offset *= np.sign(factor_clamped)
        else:
            # Right shear: no effect at left (t=0), maximum effect at right (t=1)
            shear_offset = base_shear_amount * t
            # Apply factor sign for direction
            shear_offset *= np.sign(factor_clamped)

        # Apply shear offset to the original value
        target_values[i] = original_value + shear_offset

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def push_pull(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    push_pull

    This function calculates the difference between the original keyframe values
    and the linear interpolation line between neighbors, then scales that difference
    by the factor to create the push-pull effect.

    Factor behavior:
    - Factor = 0: No effect (original values)
    - Factor > 0: Exaggerate the difference from linear interpolation
    - Factor < 0: Reduce the difference from linear interpolation (can invert)
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get reference coordinates using consolidated helper
    coords = act_help.calculate_reference_coordinates(
        fcurve, selected_data, pin_positions, act_help.CurveOperationType.PUSH_PULL
    )

    if abs(coords["local_x"]) < 0.001:  # Prevent division by zero
        return

    # Calculate factor-based push-pull
    factor_clamped = act_help.clamp_factor(factor)
    factor_zero_two = factor_clamped + abs(act_help.clamp_factor(1.0))  # Convert to 0..2 range based on max factor

    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Calculate frame ratio (position along the linear interpolation line)
        x = frame - coords["left_neighbor_x"]
        frame_ratio = x / coords["local_x"]

        # Calculate linear interpolation value at this frame
        lineal = coords["left_neighbor_y"] + coords["local_y"] * frame_ratio

        # Calculate difference between original value and linear interpolation
        delta = original_value - lineal

        # Apply push-pull effect: lineal + delta * factor_zero_two
        target_values[i] = lineal + delta * factor_zero_two

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def time_offset(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    Time offset with cyclic value pattern shifting.

    This function samples the actual F-curve (preserving its interpolation characteristics)
    across the entire selected keyframes range, then shifts the pattern cyclically based
    on the factor. Values that leave one end of the range wrap around to the other end.

    Factor behavior:
    - Factor = 0: No shift (original pattern)
    - Factor = 1.0: Shift pattern right by half range (values wrap from end to start)
    - Factor = -1.0: Shift pattern left by half range (values wrap from start to end)

    The shift is fully reversible - sliding the factor back to 0 restores the original pattern.
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) == 0:
        return

    # Get the frame range from selected keyframes
    start_frame = int(original_frames[0])
    end_frame = int(original_frames[-1])
    frame_range = end_frame - start_frame

    if frame_range <= 0:
        return  # No valid range for offset (single keyframe or no range)

    # Check if we've already sampled this F-curve for time offset
    # Store sampled data in the cache's fcurve_data to persist across factor changes
    if fcurve not in cache.fcurve_data:
        return

    fcurve_cache = cache.fcurve_data[fcurve]

    # Check if we've already sampled for time offset
    if "time_offset_sampled_frames" not in fcurve_cache:
        # First time - sample the F-curve at every integer frame to capture the actual curve shape
        # This preserves the proper interpolation (bezier, linear, etc.)
        sampled_frames = np.arange(start_frame, end_frame + 1)
        sampled_values = np.zeros(len(sampled_frames))

        # Evaluate the F-curve at each frame position
        # This gives us the actual interpolated values, not just linear interpolation
        for i, frame in enumerate(sampled_frames):
            sampled_values[i] = fcurve.evaluate(frame)

        # Store the sampled data in the cache for reuse
        fcurve_cache["time_offset_sampled_frames"] = sampled_frames
        fcurve_cache["time_offset_sampled_values"] = sampled_values
        fcurve_cache["time_offset_start_frame"] = start_frame
        fcurve_cache["time_offset_end_frame"] = end_frame
        fcurve_cache["time_offset_frame_range"] = frame_range

    # Retrieve the cached sampled data
    sampled_frames = fcurve_cache["time_offset_sampled_frames"]
    sampled_values = fcurve_cache["time_offset_sampled_values"]
    cached_start_frame = fcurve_cache["time_offset_start_frame"]
    cached_end_frame = fcurve_cache["time_offset_end_frame"]
    cached_frame_range = fcurve_cache["time_offset_frame_range"]

    # Calculate the shift amount based on factor (half the range at factor=1.0)
    factor_clamped = act_help.clamp_factor(factor)
    max_factor = abs(act_help.clamp_factor(1.0))
    shift_amount = (cached_frame_range / 2.0) * (factor_clamped / max_factor)

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0

    # Calculate new values for each selected keyframe
    target_values = np.zeros_like(original_values)

    for i, frame in enumerate(original_frames):
        # Calculate the source position for this frame's value
        # Positive factor = shift right (take values from the left)
        # Negative factor = shift left (take values from the right)
        source_position = frame - shift_amount

        # Handle wrapping using modulo for cyclic behavior
        # Ensure the position stays within the range [start_frame, end_frame]
        while source_position < cached_start_frame:
            source_position += cached_frame_range
        while source_position > cached_end_frame:
            source_position -= cached_frame_range

        # Find the appropriate value from our cached samples
        # Since we sampled at integer frames, we need to interpolate between samples
        # for non-integer source positions
        if source_position == int(source_position):
            # Exact frame match
            sample_idx = int(source_position - cached_start_frame)
            if 0 <= sample_idx < len(sampled_values):
                target_values[i] = sampled_values[sample_idx]
            else:
                # Fallback to original value if something goes wrong
                target_values[i] = original_values[i]
        else:
            # Interpolate between two adjacent samples
            lower_frame = int(np.floor(source_position))
            upper_frame = int(np.ceil(source_position))

            # Calculate interpolation factor
            t = source_position - lower_frame

            # Get sample indices
            lower_idx = lower_frame - cached_start_frame
            upper_idx = upper_frame - cached_start_frame

            # Handle wrapping for indices
            if lower_idx < 0:
                lower_idx += cached_frame_range + 1
            if upper_idx >= len(sampled_values):
                upper_idx -= cached_frame_range + 1

            if 0 <= lower_idx < len(sampled_values) and 0 <= upper_idx < len(sampled_values):
                # Linear interpolation between samples
                lower_value = sampled_values[lower_idx]
                upper_value = sampled_values[upper_idx]
                target_values[i] = lower_value + (upper_value - lower_value) * t
            else:
                # Fallback to original value if indices are out of range
                target_values[i] = original_values[i]

    # Apply intensity blending between original and target values
    # This allows partial application of the effect and smooth transitions
    blended_values = original_values + (target_values - original_values) * intensity_multiplier

    # Update cache with the blended values (keeping original frame positions)
    cache.update_selected_values(fcurve, blended_values)


def wave_noise(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    wave_noise.

    Factor behavior:
    - Factor = 0: Equal wave and noise
    - Factor > 0: More wave, less noise
    - Factor < 0: More noise, less wave
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]

    if len(indices) == 0:
        return

    # Get noise properties or use defaults
    if noise_properties:
        phase = noise_properties.get("noise_phase", 0.0)
        randomization = noise_properties.get("noise_randomization", 0.0)
        strength = noise_properties.get("noise_strength", 1.0)
        scale = noise_properties.get("noise_scale", 0.0)
    else:
        phase = 0.0
        randomization = 0.0
        strength = 1.0
        scale = 0.0

    # Generate F-curve specific random seed based on data_path for consistent per-curve randomization
    import hashlib

    fcurve_id = f"{fcurve.data_path}_{fcurve.array_index}" if fcurve else "default"
    seed_hash = hashlib.md5(fcurve_id.encode()).hexdigest()
    # Convert hash to integer seed (use first 8 characters for reasonable seed size)
    base_seed = int(seed_hash[:8], 16) % 1000000

    # Apply randomization factor to create variation between F-curves
    if randomization > 0.0:
        # Mix base seed with randomization-influenced offset
        random_offset = int(randomization * 1000 * base_seed) % 1000000
        final_seed = (base_seed + random_offset) % 1000000
    else:
        final_seed = 42  # Fixed seed when no randomization

    # Set seed for reproducible noise per F-curve
    np.random.seed(final_seed)

    # Calculate frequency scaling (0 = default, negative = tighter/higher frequency, positive = wider/lower frequency)
    base_frequency = 4.0  # Default 4 cycles
    frequency_multiplier = 2.0 ** (-scale)  # Exponential scaling for intuitive control

    # Calculate randomized phase for this F-curve
    if randomization > 0.0:
        # Add random phase offset based on randomization factor
        random_phase_offset = np.random.uniform(-np.pi, np.pi) * randomization
        effective_phase = phase + random_phase_offset
    else:
        effective_phase = phase

    # Generate wave + noise using numpy with applied properties
    # Both wave and noise are affected by randomization through the seed and phase
    t_values = np.linspace(0, 1, len(indices))  # Removed offset - using normalized range
    wave_values = (
        np.sin(t_values * np.pi * base_frequency * frequency_multiplier + effective_phase) * 0.5
    )  # Randomized phase affects wave
    noise_values = (np.random.random(len(indices)) - 0.5) * 0.5  # Random noise affected by seed

    # Calculate factor-based wave/noise blend
    factor_clamped = act_help.clamp_factor(factor)
    max_factor = abs(act_help.clamp_factor(1.0))
    factor_zero_one = (factor_clamped + max_factor) / (2.0 * max_factor)  # Convert to 0..1 range based on max factor

    wave_weight = factor_zero_one
    noise_weight = 1.0 - factor_zero_one

    combined_values = wave_values * wave_weight + noise_values * noise_weight

    # Apply strength multiplier
    combined_values *= strength

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    scaled_values = combined_values * intensity_multiplier

    # Calculate target values
    target_values = original_values + scaled_values

    # Update cache
    cache.update_selected_values(fcurve, target_values)


def perlin_turbulence(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    perlin_turbulence - Multi-octave Perlin-like noise with turbulence.

    Factor behavior:
    - Factor = 0: Balanced multi-octave noise
    - Factor > 0: More high-frequency detail (turbulent)
    - Factor < 0: More low-frequency smooth noise
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]

    if len(indices) == 0:
        return

    # Get noise properties or use defaults
    if noise_properties:
        phase = noise_properties.get("noise_phase", 0.0)
        randomization = noise_properties.get("noise_randomization", 0.0)
        strength = noise_properties.get("noise_strength", 1.0)
        scale = noise_properties.get("noise_scale", 0.0)
    else:
        phase = 0.0
        randomization = 0.0
        strength = 1.0
        scale = 0.0

    # Generate F-curve specific random seed based on data_path for consistent per-curve randomization
    import hashlib

    fcurve_id = f"{fcurve.data_path}_{fcurve.array_index}" if fcurve else "default"
    seed_hash = hashlib.md5(fcurve_id.encode()).hexdigest()
    # Convert hash to integer seed (use first 8 characters for reasonable seed size)
    base_seed = int(seed_hash[:8], 16) % 1000000

    # Apply randomization factor to create variation between F-curves
    if randomization > 0.0:
        # Mix base seed with randomization-influenced offset
        random_offset = int(randomization * 1000 * base_seed) % 1000000
        final_seed = (base_seed + random_offset) % 1000000
    else:
        final_seed = 42  # Fixed seed when no randomization

    # Set seed for reproducible noise per F-curve
    np.random.seed(final_seed)

    # Calculate frequency scaling (0 = default, negative = tighter/higher frequency, positive = wider/lower frequency)
    frequency_multiplier = 2.0 ** (-scale)  # Exponential scaling for intuitive control

    # Calculate randomized phase for this F-curve
    if randomization > 0.0:
        # Add random phase offset based on randomization factor
        random_phase_offset = np.random.uniform(-np.pi, np.pi) * randomization
        effective_phase = phase + random_phase_offset
    else:
        effective_phase = phase

    # Generate position array normalized to keyframe count (removed offset)
    t_values = np.linspace(0, len(indices) * 0.5, len(indices))  # Removed offset - using normalized range

    # Calculate factor-based frequency control
    factor_clamped = act_help.clamp_factor(factor)

    # Generate multiple octaves of noise with different frequencies, applying randomized phase and scale
    # effective_phase: affects the phase of all octaves (includes randomization)
    octave1 = np.sin(t_values * 1.0 * frequency_multiplier + effective_phase) * 0.5  # Base frequency
    octave2 = np.sin(t_values * 2.0 * frequency_multiplier + effective_phase) * 0.25  # Double frequency, half amplitude
    octave3 = (
        np.sin(t_values * 4.0 * frequency_multiplier + effective_phase) * 0.125
    )  # Quad frequency, quarter amplitude
    octave4 = np.sin(t_values * 8.0 * frequency_multiplier + effective_phase) * 0.0625  # High frequency detail

    # Add some phase-shifted cosine waves for more complex patterns (with randomization)
    octave5 = np.cos(t_values * 3.0 * frequency_multiplier + np.pi / 3 + effective_phase) * 0.2
    octave6 = np.cos(t_values * 6.0 * frequency_multiplier + np.pi / 6 + effective_phase) * 0.1

    # Apply factor-based octave mixing
    if factor_clamped >= 0:
        # More high-frequency detail (turbulent)
        high_freq_weight = 1.0 + factor_clamped * 2.0
        low_freq_weight = 1.0 - factor_clamped * 0.5
    else:
        # More low-frequency smooth noise
        high_freq_weight = 1.0 + factor_clamped * 0.8
        low_freq_weight = 1.0 - factor_clamped * 1.5

    # Combine octaves with weighted mixing
    combined_values = (
        octave1 * low_freq_weight
        + octave2 * low_freq_weight * 0.8
        + octave3 * high_freq_weight
        + octave4 * high_freq_weight * 1.5
        + octave5 * (1.0 + abs(factor_clamped) * 0.5)
        + octave6 * high_freq_weight * 0.7
    )

    # Add some fractal-like turbulence by taking absolute values and re-combining (with randomization)
    turbulence = np.abs(np.sin(t_values * 5.0 * frequency_multiplier + np.pi / 4 + effective_phase)) * 0.15
    combined_values += turbulence * abs(factor_clamped)

    # Normalize to reasonable range and apply strength
    combined_values = combined_values * 0.3 * strength

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    scaled_values = combined_values * intensity_multiplier

    # Calculate target values
    target_values = original_values + scaled_values

    # Update cache
    cache.update_selected_values(fcurve, target_values)


def shear_left(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    shear_left - Simplified wrapper for unified shear function

    Factor behavior:
    - Factor = 0: No shear effect
    - Factor > 0: Increase shear strength
    - Factor < 0: Reverse shear direction
    """
    shear(
        fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, "left", noise_properties
    )


def shear_right(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    shear_right - Simplified wrapper for unified shear function

    Factor behavior:
    - Factor = 0: No shear effect
    - Factor > 0: Increase shear strength
    - Factor < 0: Reverse shear direction
    """
    shear(
        fcurve,
        selected_data,
        factor,
        intensity,
        start_blend,
        end_blend,
        pin_positions,
        cache,
        "right",
        noise_properties,
    )


def scale_left(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    scale_left

    Factor behavior:
    - Factor = 0: No scaling
    - Factor > 0: Scale away from left neighbor
    - Factor < 0: Scale towards left neighbor
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get dynamic reference keyframes (left neighbor)
    ref_data = act_help.get_dynamic_reference_keyframes(
        fcurve, pin_positions, indices, act_help.CurveOperationType.SCALE_LEFT
    )

    if ref_data and ref_data["left_value"] is not None:
        left_neighbor_y = ref_data["left_value"]
    else:
        # Fallback to first selected keyframe
        left_neighbor_y = original_values[0]

    # Calculate factor-based scaling
    factor_clamped = act_help.clamp_factor(factor)
    factor_zero_two = factor_clamped + abs(act_help.clamp_factor(1.0))  # Convert to 0..2 range based on max factor

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Distance from left neighbor
        distance = original_value - left_neighbor_y
        # Scale the distance based on factor
        scaled_distance = distance * factor_zero_two
        # Calculate new value
        target_values[i] = left_neighbor_y + scaled_distance

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)


def scale_right(
    fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties=None
):
    """
    scale_right

    Factor behavior:
    - Factor = 0: No scaling
    - Factor > 0: Scale away from right neighbor
    - Factor < 0: Scale towards right neighbor
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    if len(indices) < 2:
        return

    # Get dynamic reference keyframes (right neighbor)
    ref_data = act_help.get_dynamic_reference_keyframes(
        fcurve, pin_positions, indices, act_help.CurveOperationType.SCALE_RIGHT
    )

    if ref_data and ref_data["right_value"] is not None:
        right_neighbor_y = ref_data["right_value"]
    else:
        # Fallback to last selected keyframe
        right_neighbor_y = original_values[-1]

    # Calculate factor-based scaling
    factor_clamped = act_help.clamp_factor(factor)
    factor_zero_two = factor_clamped + abs(act_help.clamp_factor(1.0))  # Convert to 0..2 range based on max factor

    # Calculate target values using frame-based approach
    target_values = np.zeros_like(original_values)

    for i, (frame, original_value) in enumerate(zip(original_frames, original_values)):
        # Distance from right neighbor
        distance = original_value - right_neighbor_y
        # Scale the distance based on factor
        scaled_distance = distance * factor_zero_two
        # Calculate new value
        target_values[i] = right_neighbor_y + scaled_distance

    # Apply intensity as effect multiplier
    intensity_multiplier = intensity / 100.0  # Convert percentage to multiplier
    effect_difference = target_values - original_values
    scaled_difference = effect_difference * intensity_multiplier
    new_values = original_values + scaled_difference

    # Update cache
    cache.update_selected_values(fcurve, new_values)
