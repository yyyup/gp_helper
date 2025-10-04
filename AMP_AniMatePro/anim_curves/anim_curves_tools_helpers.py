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


# =============================================================================
# KEYFRAME CACHE SYSTEM
# =============================================================================


class KeyframeCache:
    """
    Numpy-based cache for keyframe data to enable fast iteration during operations.
    Caches initially selected keyframes and maintains them throughout the operation.
    """

    def __init__(self):
        self.fcurve_data = {}  # fcurve -> cache data mapping
        self.initially_selected_indices = {}  # fcurve -> initially selected keyframe indices (immutable)
        self.cached_keyframe_indices = {}  # fcurve -> indices of keyframes we're working with

    def cache_keyframes(self, fcurves):
        """Cache keyframe data for initially selected keyframes in all F-curves."""
        self.fcurve_data.clear()
        self.initially_selected_indices.clear()
        self.cached_keyframe_indices.clear()

        for fcurve in fcurves:
            selected_keys = get_selected_keyframes(fcurve)
            if not selected_keys:
                continue

            # Cache all keyframe indices for operations, even if only some are selected
            num_keys = len(fcurve.keyframe_points)
            all_indices = list(range(num_keys))
            self.initially_selected_indices[fcurve] = np.array(all_indices, dtype=np.int32)
            self.cached_keyframe_indices[fcurve] = np.array(all_indices, dtype=np.int32)

            # Cache all keyframe data for this curve
            keyframe_points = fcurve.keyframe_points
            num_keys = len(keyframe_points)

            # Create numpy arrays for fast access
            frames = np.zeros(num_keys, dtype=np.float32)
            values = np.zeros(num_keys, dtype=np.float32)
            handle_left_x = np.zeros(num_keys, dtype=np.float32)
            handle_left_y = np.zeros(num_keys, dtype=np.float32)
            handle_right_x = np.zeros(num_keys, dtype=np.float32)
            handle_right_y = np.zeros(num_keys, dtype=np.float32)
            handle_left_types = []
            handle_right_types = []

            # Populate arrays
            for i, keyframe in enumerate(keyframe_points):
                frames[i] = keyframe.co[0]
                values[i] = keyframe.co[1]
                handle_left_x[i] = keyframe.handle_left[0]
                handle_left_y[i] = keyframe.handle_left[1]
                handle_right_x[i] = keyframe.handle_right[0]
                handle_right_y[i] = keyframe.handle_right[1]
                handle_left_types.append(keyframe.handle_left_type)
                handle_right_types.append(keyframe.handle_right_type)

            # Compute local slopes and handle orientations for slope-based handle preservation
            local_slopes = self._compute_local_slopes(frames, values)
            handle_left_orientations = self._compute_handle_orientations(
                frames, values, handle_left_x, handle_left_y, local_slopes, is_left=True
            )
            handle_right_orientations = self._compute_handle_orientations(
                frames, values, handle_right_x, handle_right_y, local_slopes, is_left=False
            )

            # Prepare indices for mapping initial selection (now all indices)
            indices = self.initially_selected_indices[fcurve]
            # Store cache data with initial and current values
            self.fcurve_data[fcurve] = {
                "original_frames": frames.copy(),
                "original_values": values.copy(),
                "original_handle_left_x": handle_left_x.copy(),
                "original_handle_left_y": handle_left_y.copy(),
                "original_handle_right_x": handle_right_x.copy(),
                "original_handle_right_y": handle_right_y.copy(),
                "original_handle_left_types": handle_left_types.copy(),
                "original_handle_right_types": handle_right_types.copy(),
                "current_frames": frames.copy(),
                "current_values": values.copy(),
                "current_handle_left_x": handle_left_x.copy(),
                "current_handle_left_y": handle_left_y.copy(),
                "current_handle_right_x": handle_right_x.copy(),
                "current_handle_right_y": handle_right_y.copy(),
                "keyframe_points": keyframe_points,
                # Mapping arrays to track which indices correspond to initially selected keyframes
                "initially_selected_frames": frames[indices].copy(),
                "initially_selected_values": values[indices].copy(),
                # Slope-based handle orientation preservation data
                "original_local_slopes": local_slopes.copy(),
                "original_handle_left_orientations": handle_left_orientations.copy(),
                "original_handle_right_orientations": handle_right_orientations.copy(),
            }

    def get_selected_data(self, fcurve):
        """Get numpy arrays for initially selected keyframes of a specific F-curve."""
        if fcurve not in self.fcurve_data or fcurve not in self.initially_selected_indices:
            return None

        cache = self.fcurve_data[fcurve]
        indices = self.initially_selected_indices[fcurve]

        return {
            "indices": indices,
            "original_frames": cache["original_frames"][indices],
            "original_values": cache["original_values"][indices],
            "original_handle_left_x": cache["original_handle_left_x"][indices],
            "original_handle_left_y": cache["original_handle_left_y"][indices],
            "original_handle_right_x": cache["original_handle_right_x"][indices],
            "original_handle_right_y": cache["original_handle_right_y"][indices],
            "current_frames": cache["current_frames"][indices],
            "current_values": cache["current_values"][indices],
            "current_handle_left_x": cache["current_handle_left_x"][indices],
            "current_handle_left_y": cache["current_handle_left_y"][indices],
            "current_handle_right_x": cache["current_handle_right_x"][indices],
            "current_handle_right_y": cache["current_handle_right_y"][indices],
        }

    def update_selected_values(self, fcurve, new_values):
        """Update cached values for initially selected keyframes."""
        if fcurve not in self.fcurve_data or fcurve not in self.initially_selected_indices:
            return

        cache = self.fcurve_data[fcurve]
        indices = self.initially_selected_indices[fcurve]

        # Safety check: ensure values are finite and within reasonable range
        new_values = np.asarray(new_values)
        if not np.all(np.isfinite(new_values)):
            # If values are not finite, restore to original values
            new_values = cache["original_values"][indices]

        # Clamp values to prevent extreme overflow
        new_values = np.clip(new_values, -1e10, 1e10)

        # Update current values for the initially selected keyframes
        cache["current_values"][indices] = new_values

        # Update handles using slope-based orientation preservation
        prefs = get_prefs()
        if not prefs.guipins_fast_handles:
            self._update_handles_preserving_orientation(fcurve, indices)

    def update_selected_frames(self, fcurve, new_frames):
        """Update cached frame positions for initially selected keyframes."""
        if fcurve not in self.fcurve_data or fcurve not in self.initially_selected_indices:
            return

        cache = self.fcurve_data[fcurve]
        indices = self.initially_selected_indices[fcurve]

        # Update current frames for the initially selected keyframes
        cache["current_frames"][indices] = new_frames

        # Update handles using slope-based orientation preservation
        # Note: For frame operations, we need to also update handle X positions proportionally
        prefs = get_prefs()
        if not prefs.guipins_fast_handles:
            self._update_handles_preserving_orientation_with_frame_scaling(fcurve, indices, new_frames)

    def apply_to_fcurves(self, operation_type=None):
        """Apply cached data back to the actual F-curve keyframes."""
        prefs = get_prefs()
        for fcurve, cache in self.fcurve_data.items():
            keyframe_points = cache["keyframe_points"]

            for i, keyframe in enumerate(keyframe_points):
                # Update keyframe position and value
                keyframe.co[0] = cache["current_frames"][i]
                keyframe.co[1] = cache["current_values"][i]

                # Update handles
                keyframe.handle_left[0] = cache["current_handle_left_x"][i]
                keyframe.handle_left[1] = cache["current_handle_left_y"][i]
                keyframe.handle_right[0] = cache["current_handle_right_x"][i]
                keyframe.handle_right[1] = cache["current_handle_right_y"][i]

            # Update handle types if operation is specified
            if operation_type and prefs.guipins_fast_handles:
                self.update_handle_types(fcurve, operation_type)

            # Update the F-curve to refresh the display
            fcurve.update()

    def restore_original(self):
        """Restore all keyframes to their original cached state."""
        for fcurve, cache in self.fcurve_data.items():
            keyframe_points = cache["keyframe_points"]

            for i, keyframe in enumerate(keyframe_points):
                # Restore original position and value
                keyframe.co[0] = cache["original_frames"][i]
                keyframe.co[1] = cache["original_values"][i]

                # Restore original handles
                keyframe.handle_left[0] = cache["original_handle_left_x"][i]
                keyframe.handle_left[1] = cache["original_handle_left_y"][i]
                keyframe.handle_right[0] = cache["original_handle_right_x"][i]
                keyframe.handle_right[1] = cache["original_handle_right_y"][i]

                # Restore original handle types
                keyframe.handle_left_type = cache["original_handle_left_types"][i]
                keyframe.handle_right_type = cache["original_handle_right_types"][i]

            # Reset current cache to original values
            cache["current_frames"][:] = cache["original_frames"]
            cache["current_values"][:] = cache["original_values"]
            cache["current_handle_left_x"][:] = cache["original_handle_left_x"]
            cache["current_handle_left_y"][:] = cache["original_handle_left_y"]
            cache["current_handle_right_x"][:] = cache["original_handle_right_x"]
            cache["current_handle_right_y"][:] = cache["original_handle_right_y"]

            # Update the F-curve to refresh display
            fcurve.update()

    def update_handle_types(self, fcurve, operation_type):
        """Update handle types based on the operation being performed."""
        if fcurve not in self.fcurve_data or fcurve not in self.initially_selected_indices:
            return

        cache = self.fcurve_data[fcurve]
        indices = self.initially_selected_indices[fcurve]
        keyframe_points = cache["keyframe_points"]

        # # Set appropriate handle types based on operation
        # if operation_type in [CurveOperationType.EASE, CurveOperationType.EASE_TO_EASE, CurveOperationType.BLEND_EASE]:
        #     # For easing operations, use AUTO handles for smooth curves
        #     handle_type = "AUTO"
        # elif operation_type in [CurveOperationType.SMOOTH]:
        #     # For smoothing, use AUTO_CLAMPED to prevent overshooting
        #     handle_type = "AUTO_CLAMPED"
        # elif operation_type in [CurveOperationType.BLEND_FRAME, CurveOperationType.TIME_OFFSET]:
        #     # For frame operations, keep original handle types
        #     return
        # else:
        #     # For other operations, use AUTO as default
        #     handle_type = "AUTO_CLAMPED"

        # Set handle to "AUTO_CLAMPED" for all operations
        handle_type = "AUTO"

        # Update handle types for initially selected keyframes
        for i in indices:
            if i < len(keyframe_points):
                keyframe = keyframe_points[i]
                # Only convert to AUTO_CLAMPED if not already AUTO or AUTO_CLAMPED
                if keyframe.handle_left_type not in ["AUTO", "AUTO_CLAMPED"]:
                    keyframe.handle_left_type = handle_type
                if keyframe.handle_right_type not in ["AUTO", "AUTO_CLAMPED"]:
                    keyframe.handle_right_type = handle_type

    def reset_to_original(self):
        """Reset current values to original values for fresh operation application."""
        for fcurve, cache in self.fcurve_data.items():
            # Reset current arrays to original values
            cache["current_frames"][:] = cache["original_frames"]
            cache["current_values"][:] = cache["original_values"]
            cache["current_handle_left_x"][:] = cache["original_handle_left_x"]
            cache["current_handle_left_y"][:] = cache["original_handle_left_y"]
            cache["current_handle_right_x"][:] = cache["original_handle_right_x"]
            cache["current_handle_right_y"][:] = cache["original_handle_right_y"]

            # Note: We don't need to reset slope orientation data as they are computed
            # dynamically when needed and are relative to the original keyframe positions

    def get_initially_selected_indices(self, fcurve):
        """Get the indices of initially selected keyframes for a specific F-curve."""
        return self.initially_selected_indices.get(fcurve, np.array([], dtype=np.int32))

    # =============================================================================
    # SLOPE-BASED HANDLE ORIENTATION PRESERVATION
    # =============================================================================

    def _compute_local_slopes(self, frames, values):
        """
        Compute the local slope at each keyframe based on its neighbors.
        This represents the orientation of the curve at each keyframe.

        Args:
            frames: Array of keyframe X positions
            values: Array of keyframe Y values

        Returns:
            Array of slopes (dy/dx) at each keyframe position
        """
        num_keys = len(frames)
        slopes = np.zeros(num_keys, dtype=np.float32)

        for i in range(num_keys):
            if num_keys == 1:
                # Single keyframe, slope is undefined/zero
                slopes[i] = 0.0
            elif i == 0:
                # First keyframe: use slope to next keyframe
                if frames[i + 1] != frames[i] and np.isfinite(values[i + 1]) and np.isfinite(values[i]):
                    slopes[i] = (values[i + 1] - values[i]) / (frames[i + 1] - frames[i])
                else:
                    slopes[i] = 0.0
            elif i == num_keys - 1:
                # Last keyframe: use slope from previous keyframe
                if frames[i] != frames[i - 1] and np.isfinite(values[i]) and np.isfinite(values[i - 1]):
                    slopes[i] = (values[i] - values[i - 1]) / (frames[i] - frames[i - 1])
                else:
                    slopes[i] = 0.0
            else:
                # Middle keyframe: use average of slopes to neighbors
                left_slope = 0.0
                right_slope = 0.0

                if frames[i] != frames[i - 1] and np.isfinite(values[i]) and np.isfinite(values[i - 1]):
                    left_slope = (values[i] - values[i - 1]) / (frames[i] - frames[i - 1])

                if frames[i + 1] != frames[i] and np.isfinite(values[i + 1]) and np.isfinite(values[i]):
                    right_slope = (values[i + 1] - values[i]) / (frames[i + 1] - frames[i])

                # Average the slopes for smooth transition
                if np.isfinite(left_slope) and np.isfinite(right_slope):
                    slopes[i] = (left_slope + right_slope) / 2.0
                else:
                    slopes[i] = 0.0

        # Final safety check: ensure all slopes are finite
        slopes = np.where(np.isfinite(slopes), slopes, 0.0)

        return slopes

    def _compute_handle_orientations(self, frames, values, handle_x, handle_y, local_slopes, is_left=True):
        """
        Compute the relative orientation of each handle with respect to the local slope.
        This stores how each handle is oriented relative to the keyframe's local slope.

        Args:
            frames: Array of keyframe X positions
            values: Array of keyframe Y values
            handle_x: Array of handle X positions
            handle_y: Array of handle Y positions
            local_slopes: Array of local slopes at each keyframe
            is_left: Whether these are left handles (True) or right handles (False)

        Returns:
            Array of relative orientations (as slope deviations from local slope)
        """
        num_keys = len(frames)
        orientations = np.zeros(num_keys, dtype=np.float32)

        for i in range(num_keys):
            # Calculate the slope from keyframe to handle
            dx = handle_x[i] - frames[i]
            dy = handle_y[i] - values[i]

            if abs(dx) < 1e-6:
                # Handle is vertical relative to keyframe
                handle_slope = np.inf if dy > 0 else -np.inf
            else:
                handle_slope = dy / dx

            # Store the relative orientation (deviation from local slope)
            if not np.isinf(handle_slope) and not np.isinf(local_slopes[i]):
                orientations[i] = handle_slope - local_slopes[i]
            else:
                # Special case for infinite slopes - preserve the sign
                if np.isinf(handle_slope) and np.isinf(local_slopes[i]):
                    orientations[i] = 0.0  # Both infinite, no relative change
                elif np.isinf(handle_slope):
                    orientations[i] = np.inf if dy > 0 else -np.inf
                else:
                    orientations[i] = handle_slope

        return orientations

    def _update_handles_preserving_orientation(self, fcurve, indices):
        """
        Update handle positions to preserve their orientation relative to the new local slopes.
        This is the core of the slope-based handle preservation system.

        Args:
            fcurve: The F-curve being updated
            indices: Array of keyframe indices to update
        """
        if fcurve not in self.fcurve_data:
            return

        cache = self.fcurve_data[fcurve]

        # Initialize a set to track which keyframes should keep their original handle types
        if "preserve_handle_types" not in cache:
            cache["preserve_handle_types"] = set()

        # Recompute local slopes with current keyframe positions
        current_slopes = self._compute_local_slopes(cache["current_frames"], cache["current_values"])

        # Update handles for the specified indices
        for i in indices:
            # Get handle types to determine which handles to update
            left_type = cache["original_handle_left_types"][i]
            right_type = cache["original_handle_right_types"][i]

            # Track if this keyframe has AUTO or AUTO_CLAMPED handles that should be preserved
            if left_type in ["AUTO", "AUTO_CLAMPED"] or right_type in ["AUTO", "AUTO_CLAMPED"]:
                cache["preserve_handle_types"].add(i)

            # Update left handle if it's not AUTO or AUTO_CLAMPED
            if left_type not in ["AUTO", "AUTO_CLAMPED"]:
                # Get the original relative orientation
                original_orientation = cache["original_handle_left_orientations"][i]

                # Calculate new handle slope based on current local slope + original relative orientation
                new_local_slope = current_slopes[i]

                if not np.isinf(original_orientation):
                    new_handle_slope = new_local_slope + original_orientation
                else:
                    new_handle_slope = original_orientation

                # Calculate new handle position maintaining the same X distance
                keyframe_x = cache["current_frames"][i]
                keyframe_y = cache["current_values"][i]
                original_handle_x = cache["original_handle_left_x"][i]

                # Preserve the X distance from keyframe to handle
                handle_dx = original_handle_x - cache["original_frames"][i]
                new_handle_x = keyframe_x + handle_dx

                # Calculate Y position based on the preserved slope
                if not np.isinf(new_handle_slope):
                    new_handle_y = keyframe_y + new_handle_slope * handle_dx
                else:
                    # Vertical handle case
                    original_handle_y = cache["original_handle_left_y"][i]
                    handle_dy = original_handle_y - cache["original_values"][i]
                    new_handle_y = keyframe_y + handle_dy

                # Update the cached handle position
                cache["current_handle_left_x"][i] = new_handle_x
                cache["current_handle_left_y"][i] = new_handle_y

            # Update right handle if it's not AUTO or AUTO_CLAMPED
            if right_type not in ["AUTO", "AUTO_CLAMPED"]:
                # Get the original relative orientation
                original_orientation = cache["original_handle_right_orientations"][i]

                # Calculate new handle slope based on current local slope + original relative orientation
                new_local_slope = current_slopes[i]

                if not np.isinf(original_orientation):
                    new_handle_slope = new_local_slope + original_orientation
                else:
                    new_handle_slope = original_orientation

                # Calculate new handle position maintaining the same X distance
                keyframe_x = cache["current_frames"][i]
                keyframe_y = cache["current_values"][i]
                original_handle_x = cache["original_handle_right_x"][i]

                # Preserve the X distance from keyframe to handle
                handle_dx = original_handle_x - cache["original_frames"][i]
                new_handle_x = keyframe_x + handle_dx

                # Calculate Y position based on the preserved slope
                if not np.isinf(new_handle_slope):
                    new_handle_y = keyframe_y + new_handle_slope * handle_dx
                else:
                    # Vertical handle case
                    original_handle_y = cache["original_handle_right_y"][i]
                    handle_dy = original_handle_y - cache["original_values"][i]
                    new_handle_y = keyframe_y + handle_dy

                # Update the cached handle position
                cache["current_handle_right_x"][i] = new_handle_x
                cache["current_handle_right_y"][i] = new_handle_y

    def _update_handles_preserving_orientation_with_frame_scaling(self, fcurve, indices, new_frames):
        """
        Update handle positions for frame operations, scaling handle X positions proportionally
        while preserving their orientation relative to the local slopes.

        Args:
            fcurve: The F-curve being updated
            indices: Array of keyframe indices to update
            new_frames: Array of new frame positions for the keyframes
        """
        if fcurve not in self.fcurve_data:
            return

        cache = self.fcurve_data[fcurve]

        # Recompute local slopes with current keyframe positions
        current_slopes = self._compute_local_slopes(cache["current_frames"], cache["current_values"])

        # Update handles for the specified indices
        for i, keyframe_idx in enumerate(indices):
            # Get handle types to determine which handles to update
            left_type = cache["original_handle_left_types"][keyframe_idx]
            right_type = cache["original_handle_right_types"][keyframe_idx]

            # Calculate frame scaling factor for this keyframe
            original_frame = cache["original_frames"][keyframe_idx]
            new_frame = new_frames[i]

            # Update left handle if it's not AUTO or AUTO_CLAMPED
            if left_type not in ["AUTO", "AUTO_CLAMPED"]:
                # Get the original relative orientation
                original_orientation = cache["original_handle_left_orientations"][keyframe_idx]

                # Calculate new handle slope based on current local slope + original relative orientation
                new_local_slope = current_slopes[keyframe_idx]

                if not np.isinf(original_orientation):
                    new_handle_slope = new_local_slope + original_orientation
                else:
                    new_handle_slope = original_orientation

                # Calculate new handle position with frame scaling
                original_handle_x = cache["original_handle_left_x"][keyframe_idx]
                original_handle_dx = original_handle_x - original_frame

                # Scale the handle X distance proportionally to the frame change
                if abs(original_frame) > 1e-6:
                    scale_factor = new_frame / original_frame if original_frame != 0 else 1.0
                    new_handle_dx = original_handle_dx * scale_factor
                else:
                    new_handle_dx = original_handle_dx

                new_handle_x = new_frame + new_handle_dx

                # Calculate Y position based on the preserved slope
                keyframe_y = cache["current_values"][keyframe_idx]
                if not np.isinf(new_handle_slope):
                    new_handle_y = keyframe_y + new_handle_slope * new_handle_dx
                else:
                    # Vertical handle case - scale Y distance proportionally
                    original_handle_y = cache["original_handle_left_y"][keyframe_idx]
                    original_keyframe_y = cache["original_values"][keyframe_idx]
                    handle_dy = original_handle_y - original_keyframe_y
                    new_handle_y = keyframe_y + handle_dy

                # Update the cached handle position
                cache["current_handle_left_x"][keyframe_idx] = new_handle_x
                cache["current_handle_left_y"][keyframe_idx] = new_handle_y

            # Update right handle if it's not AUTO or AUTO_CLAMPED
            if right_type not in ["AUTO", "AUTO_CLAMPED"]:
                # Get the original relative orientation
                original_orientation = cache["original_handle_right_orientations"][keyframe_idx]

                # Calculate new handle slope based on current local slope + original relative orientation
                new_local_slope = current_slopes[keyframe_idx]

                if not np.isinf(original_orientation):
                    new_handle_slope = new_local_slope + original_orientation
                else:
                    new_handle_slope = original_orientation

                # Calculate new handle position with frame scaling
                original_handle_x = cache["original_handle_right_x"][keyframe_idx]
                original_handle_dx = original_handle_x - original_frame

                # Scale the handle X distance proportionally to the frame change
                if abs(original_frame) > 1e-6:
                    scale_factor = new_frame / original_frame if original_frame != 0 else 1.0
                    new_handle_dx = original_handle_dx * scale_factor
                else:
                    new_handle_dx = original_handle_dx

                new_handle_x = new_frame + new_handle_dx

                # Calculate Y position based on the preserved slope
                keyframe_y = cache["current_values"][keyframe_idx]
                if not np.isinf(new_handle_slope):
                    new_handle_y = keyframe_y + new_handle_slope * new_handle_dx
                else:
                    # Vertical handle case - scale Y distance proportionally
                    original_handle_y = cache["original_handle_right_y"][keyframe_idx]
                    original_keyframe_y = cache["original_values"][keyframe_idx]
                    handle_dy = original_handle_y - original_keyframe_y
                    new_handle_y = keyframe_y + handle_dy

                # Update the cached handle position
                cache["current_handle_right_x"][keyframe_idx] = new_handle_x
                cache["current_handle_right_y"][keyframe_idx] = new_handle_y

    # =============================================================================
    # DEPRECATED HANDLE INTERPOLATION METHODS
    # =============================================================================

    def _calculate_handle_interpolation_factor(self, handle_x, keyframe_frames):
        """DEPRECATED: Calculate interpolation factor for a handle X position within keyframe range."""
        if len(keyframe_frames) < 2:
            return 0.0

        min_frame = np.min(keyframe_frames)
        max_frame = np.max(keyframe_frames)

        if max_frame - min_frame == 0:
            return 0.0

        # Clamp handle position to keyframe range for interpolation
        clamped_x = np.clip(handle_x, min_frame, max_frame)
        return (clamped_x - min_frame) / (max_frame - min_frame)

    def _interpolate_values_at_t(self, values, frames, target_frame):
        """DEPRECATED: Interpolate values at a specific frame position."""
        if len(values) < 2 or len(frames) < 2:
            return values[0] if len(values) > 0 else 0.0

        # Find the interpolation position
        min_frame = np.min(frames)
        max_frame = np.max(frames)

        if max_frame - min_frame == 0:
            return values[0]

        # Calculate interpolation factor
        t = (target_frame - min_frame) / (max_frame - min_frame)
        t = np.clip(t, 0.0, 1.0)

        # Linear interpolation for simplicity
        # Could be enhanced with more sophisticated interpolation later
        return values[0] + (values[-1] - values[0]) * t

    def _calculate_transformation_at_position(
        self, target_x, original_frames, original_values, new_values, pin_positions=None
    ):
        """
        Calculate what transformation should be applied at a specific X position,
        treating it as if there was a keyframe at that position.

        This treats handles as independent keyframes and applies the same
        intensity/blending that would be applied to a keyframe at this X coordinate.

        Args:
            target_x: X position where we want to calculate transformation
            original_frames: Array of original keyframe frames
            original_values: Array of original keyframe values
            new_values: Array of new keyframe values
            pin_positions: Optional pin positions for spatial weighting

        Returns:
            Transformation intensity (0.0 to 1.0) that should be applied at target_x
        """
        if len(original_frames) == 0 or len(original_values) == 0 or len(new_values) == 0:
            return 0.0

        # If we only have one keyframe, use its transformation
        if len(original_frames) == 1:
            original_change = new_values[0] - original_values[0]
            return original_change

        # Find the frame range
        min_frame = np.min(original_frames)
        max_frame = np.max(original_frames)

        # If target_x is outside the frame range, use the nearest edge transformation
        if target_x <= min_frame:
            # Use the leftmost keyframe's transformation
            original_change = new_values[0] - original_values[0]
            return original_change
        elif target_x >= max_frame:
            # Use the rightmost keyframe's transformation
            original_change = new_values[-1] - original_values[-1]
            return original_change
        else:
            # Interpolate between keyframes to find the transformation at target_x
            # Find the two keyframes that bracket target_x
            left_idx = 0
            right_idx = len(original_frames) - 1

            for i in range(len(original_frames) - 1):
                if original_frames[i] <= target_x <= original_frames[i + 1]:
                    left_idx = i
                    right_idx = i + 1
                    break

            # Calculate interpolation factor
            left_frame = original_frames[left_idx]
            right_frame = original_frames[right_idx]

            if right_frame - left_frame == 0:
                # Frames are the same, use left transformation
                original_change = new_values[left_idx] - original_values[left_idx]
                return original_change

            t = (target_x - left_frame) / (right_frame - left_frame)

            # Interpolate the transformation between the two keyframes
            left_change = new_values[left_idx] - original_values[left_idx]
            right_change = new_values[right_idx] - original_values[right_idx]

            interpolated_change = left_change + (right_change - left_change) * t
            return interpolated_change


class CurveOperationType:
    """Enumeration for curve operation types."""

    BLEND_EASE = "BLEND_EASE"
    # BLEND_FRAME = "BLEND_FRAME"
    BLEND_INFINITE = "BLEND_INFINITE"
    BLEND_NEIGHBOR = "BLEND_NEIGHBOR"
    BLEND_DEFAULT = "BLEND_DEFAULT"
    BLEND_OFFSET = "BLEND_OFFSET"

    EASE = "EASE"
    EASE_TO_EASE = "EASE_TO_EASE"

    SCALE_AVERAGE = "SCALE_AVERAGE"
    SCALE_LEFT = "SCALE_LEFT"
    SCALE_RIGHT = "SCALE_RIGHT"

    SHEAR_LEFT = "SHEAR_LEFT"
    SHEAR_RIGHT = "SHEAR_RIGHT"

    PUSH_PULL = "PUSH_PULL"
    TIME_OFFSET = "TIME_OFFSET"
    TWEEN = "TWEEN"

    SMOOTH = "SMOOTH"
    SMOOTH_JITTER = "SMOOTH_JITTER"

    WAVE_NOISE = "WAVE_NOISE"
    PERLIN_NOISE = "PERLIN_NOISE"

    @classmethod
    def get_all_operations(cls):
        """Get all curve operations with their display names and descriptions."""
        return [
            (cls.BLEND_EASE, "Blend Ease", "From current to C shape"),
            # (cls.BLEND_FRAME, "Blend Frame", "From current to set frames"),
            (cls.BLEND_INFINITE, "Blend Infinite", "Adds or adjust keys to conform to the adjacent slope"),
            (cls.BLEND_NEIGHBOR, "Blend Neighbor", "From current to neighbors. Overshoots key values"),
            (cls.BLEND_DEFAULT, "Blend Default", "From default value"),
            (cls.BLEND_OFFSET, "Blend Offset", "Offset key values to neighbors"),
            (cls.EASE, "Ease", "C shape transition"),
            (cls.EASE_TO_EASE, "Ease To Ease", "S shape transition"),
            (cls.SCALE_AVERAGE, "Scale Average", "Scale to average value"),
            (cls.SCALE_LEFT, "Scale Left", "Scale anchor to left neighbor"),
            (cls.SCALE_RIGHT, "Scale Right", "Scale anchor to right neighbor"),
            (cls.SHEAR_LEFT, "Shear Left", "Overshoots key values"),
            (cls.SHEAR_RIGHT, "Shear Right", "Overshoots key values"),
            (cls.PUSH_PULL, "Push Pull", "Overshoots key values"),
            (cls.TIME_OFFSET, "Time Offset", "Slide fcurve in time without affecting keys frame value"),
            (cls.TWEEN, "Tween", "Sets key value using neighbors as reference. Overshoots key values"),
            (cls.SMOOTH, "Smooth", "Smooths out fcurve keys"),
            (cls.SMOOTH_JITTER, "Smooth Jitter", "Remove jitter/noise using Butterworth filter"),
            (cls.WAVE_NOISE, "Wave-Noise", "Add wave or random values to keys"),
            (cls.PERLIN_NOISE, "Perlin Noise", "Add Perlin noise to keys"),
        ]

    @classmethod
    def requires_keyframes(cls, operation_type):
        """Check if an operation requires selected keyframes to work."""
        # Operations that require multiple selected keyframes
        keyframe_required_ops = {
            cls.SCALE_AVERAGE,
            cls.SCALE_LEFT,
            cls.SCALE_RIGHT,
            cls.SHEAR_LEFT,
            cls.SHEAR_RIGHT,
            cls.TIME_OFFSET,
            cls.SMOOTH,
            cls.SMOOTH_JITTER,
            cls.WAVE_NOISE,
            cls.PERLIN_NOISE,
        }
        return operation_type in keyframe_required_ops

    @classmethod
    def supports_current_frame_mode(cls, operation_type):
        """Check if an operation supports current frame mode (works without selected keyframes)."""
        # Operations that can work on current frame with neighbors
        current_frame_ops = {
            cls.BLEND_EASE,
            cls.BLEND_NEIGHBOR,
            cls.BLEND_DEFAULT,
            cls.BLEND_OFFSET,
            cls.BLEND_INFINITE,
            cls.EASE,
            cls.EASE_TO_EASE,
            cls.PUSH_PULL,
            cls.TWEEN,
        }
        return operation_type in current_frame_ops

    @classmethod
    def supports_overshoot(cls, operation_type):
        """Check if an operation supports overshoot behavior."""
        # Operations that do NOT support overshoot (use clamp_factor_no_overshoot)
        no_overshoot_operations = {
            cls.BLEND_DEFAULT,
            cls.SCALE_AVERAGE,
            cls.BLEND_INFINITE,
        }
        return operation_type not in no_overshoot_operations


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def refresh_fcurves_display(context):
    """Refresh F-curve display similar to timewarper implementation."""
    # Update all visible F-curves
    if hasattr(context, "visible_fcurves"):
        for fc in context.visible_fcurves:
            fc.update()

    # Also update selected/editable F-curves
    if hasattr(context, "selected_editable_fcurves"):
        for fc in context.selected_editable_fcurves:
            fc.update()
    elif hasattr(context, "editable_fcurves"):
        for fc in context.editable_fcurves:
            fc.update()

    # Force UI refresh
    refresh_ui(context)


def get_selected_keyframes(fcurve):
    """Get selected keyframes from an F-curve."""
    if not fcurve:
        return []

    selected_keys = []
    for i, keyframe in enumerate(fcurve.keyframe_points):
        if keyframe.select_control_point:
            selected_keys.append((i, keyframe))

    return selected_keys


def clamp_factor(factor):
    """Clamp factor based on overshoot preference."""
    prefs = get_prefs()
    max_factor = 2.0 if prefs.guipins_overshoot else 1.0
    return np.clip(factor, -max_factor, max_factor)


def get_max_factor():
    """Get the maximum factor range based on overshoot preference."""
    prefs = get_prefs()
    return 2.0 if prefs.guipins_overshoot else 1.0


def clamp_factor_no_overshoot(factor):
    """
    Clamp factor to ±1.0 regardless of overshoot preference.

    Used for operations that should not allow overshoot:
    - blend_default
    - scale_average
    - blend_infinite (blend to slope)
    """
    return np.clip(factor, -1.0, 1.0)


def get_fcurve_context():
    """Get the current F-curve context from the Graph Editor."""
    context = bpy.context
    if context.space_data.type != "GRAPH_EDITOR":
        return None, []

    fcurves = []
    if context.selected_editable_fcurves:
        fcurves = context.selected_editable_fcurves
    elif context.editable_fcurves:
        fcurves = context.editable_fcurves

    return context, fcurves


def apply_blend_function(value, blend_type, t):
    """Apply blending function to a value."""
    if blend_type == BlendType.LINEAR:
        return value * t
    elif blend_type == BlendType.QUADRATIC_IN:
        return value * (t * t)
    elif blend_type == BlendType.QUADRATIC_OUT:
        return value * (1 - (1 - t) * (1 - t))
    elif blend_type == BlendType.QUADRATIC_IN_OUT:
        if t < 0.5:
            return value * (2 * t * t)
        else:
            return value * (1 - 2 * (1 - t) * (1 - t))
    elif blend_type == BlendType.CUBIC_IN:
        return value * (t * t * t)
    elif blend_type == BlendType.CUBIC_OUT:
        return value * (1 - (1 - t) * (1 - t) * (1 - t))
    elif blend_type == BlendType.CUBIC_IN_OUT:
        if t < 0.5:
            return value * (4 * t * t * t)
        else:
            return value * (1 - 4 * (1 - t) * (1 - t) * (1 - t))
    elif blend_type == BlendType.EXPONENTIAL_IN:
        return value * (0 if t == 0 else math.pow(2, 10 * (t - 1)))
    elif blend_type == BlendType.EXPONENTIAL_OUT:
        return value * (1 if t == 1 else 1 - math.pow(2, -10 * t))
    elif blend_type == BlendType.EXPONENTIAL_IN_OUT:
        if t == 0:
            return 0
        elif t == 1:
            return value
        elif t < 0.5:
            return value * (math.pow(2, 20 * t - 10) / 2)
        else:
            return value * ((2 - math.pow(2, -20 * t + 10)) / 2)

    return value * t  # Default to linear


def apply_blend_curve(values, blend_type, t_values):
    """Apply blending curve to values based on blend type."""
    # Import BlendType locally to avoid circular imports
    from ..utils.gui_pins import BlendType

    if blend_type == BlendType.LINEAR:
        return values * t_values
    elif blend_type == BlendType.QUADRATIC_IN:
        return values * (t_values * t_values)
    elif blend_type == BlendType.QUADRATIC_OUT:
        return values * (1 - (1 - t_values) * (1 - t_values))
    elif blend_type == BlendType.QUADRATIC_IN_OUT:
        mask = t_values < 0.5
        result = np.zeros_like(values)
        result[mask] = values[mask] * (2 * t_values[mask] * t_values[mask])
        result[~mask] = values[~mask] * (1 - 2 * (1 - t_values[~mask]) * (1 - t_values[~mask]))
        return result
    elif blend_type == BlendType.CUBIC_IN:
        return values * (t_values * t_values * t_values)
    elif blend_type == BlendType.CUBIC_OUT:
        return values * (1 - (1 - t_values) * (1 - t_values) * (1 - t_values))
    elif blend_type == BlendType.CUBIC_IN_OUT:
        mask = t_values < 0.5
        result = np.zeros_like(values)
        result[mask] = values[mask] * (4 * t_values[mask] * t_values[mask] * t_values[mask])
        result[~mask] = values[~mask] * (1 - 4 * (1 - t_values[~mask]) * (1 - t_values[~mask]) * (1 - t_values[~mask]))
        return result
    elif blend_type == BlendType.EXPONENTIAL_IN:
        # Avoid division by zero
        safe_t = np.where(t_values == 0, 1e-10, t_values)
        return values * np.where(t_values == 0, 0, np.power(2, 10 * (safe_t - 1)))
    elif blend_type == BlendType.EXPONENTIAL_OUT:
        return values * np.where(t_values == 1, 1, 1 - np.power(2, -10 * t_values))
    elif blend_type == BlendType.EXPONENTIAL_IN_OUT:
        result = np.zeros_like(values)
        mask_zero = t_values == 0
        mask_one = t_values == 1
        mask_left = (t_values < 0.5) & ~mask_zero & ~mask_one
        mask_right = (t_values >= 0.5) & ~mask_zero & ~mask_one

        result[mask_zero] = 0
        result[mask_one] = values[mask_one]
        result[mask_left] = values[mask_left] * (np.power(2, 20 * t_values[mask_left] - 10) / 2)
        result[mask_right] = values[mask_right] * ((2 - np.power(2, -20 * t_values[mask_right] + 10)) / 2)
        return result

    return values * t_values  # Default to linear


# =============================================================================
# SPATIAL EFFECT MODULATION
# =============================================================================


def calculate_spatial_weights(keyframes, pin_positions, start_blend, end_blend):
    """
    Calculate spatial effect weights for keyframes based on pin positions.

    Args:
        keyframes: numpy array of keyframe frame positions
        pin_positions: list of 4 frame positions [secondary_left, main_left, main_right, secondary_right]
        start_blend: BlendType for left side decay
        end_blend: BlendType for right side decay

    Returns:
        numpy array of weights (0.0 to 1.0) for each keyframe
    """
    if len(pin_positions) < 4:
        return np.ones(len(keyframes))  # No spatial modulation if pins not available

    secondary_left = pin_positions[0]
    main_left = pin_positions[1]
    main_right = pin_positions[2]
    secondary_right = pin_positions[3]

    weights = np.zeros(len(keyframes))

    # Calculate blend distances for each side
    tolerance = 0.001  # Small tolerance for float comparison
    left_blend_distance = abs(main_left - secondary_left)
    right_blend_distance = abs(secondary_right - main_right)

    # Determine which sides have valid blend distances
    left_can_blend = left_blend_distance > tolerance
    right_can_blend = right_blend_distance > tolerance

    # Check if main pins are overlapping or too close together
    main_pin_distance = abs(main_right - main_left)
    min_distance_threshold = 0.1  # Minimum distance to avoid blending glitches

    if main_pin_distance < min_distance_threshold:
        # When main pins are overlapping or too close, use simplified blending
        main_center = (main_left + main_right) * 0.5

        for i, frame in enumerate(keyframes):
            if secondary_left <= frame <= secondary_right:
                # Within secondary pin range
                if frame <= main_center:
                    # Left side of center
                    if left_can_blend:
                        t = (frame - secondary_left) / (main_center - secondary_left)
                        t = np.clip(t, 0.0, 1.0)
                        weights[i] = apply_blend_function(1.0, start_blend, t)
                    else:
                        # No left blend possible - use full weight
                        weights[i] = 1.0
                else:
                    # Right side of center
                    if right_can_blend:
                        t = (secondary_right - frame) / (secondary_right - main_center)
                        t = np.clip(t, 0.0, 1.0)
                        weights[i] = apply_blend_function(1.0, end_blend, t)
                    else:
                        # No right blend possible - use full weight
                        weights[i] = 1.0
            else:
                # Outside secondary pins: 0% effect
                weights[i] = 0.0
    else:
        # Normal case: main pins are sufficiently separated
        for i, frame in enumerate(keyframes):
            if main_left <= frame <= main_right:
                # Between main pins: 100% effect
                weights[i] = 1.0
            elif secondary_left <= frame < main_left:
                # Left decay region: from 0% at secondary to 100% at main
                if left_can_blend:
                    t = (frame - secondary_left) / (main_left - secondary_left)
                    t = np.clip(t, 0.0, 1.0)
                    weights[i] = apply_blend_function(1.0, start_blend, t)
                else:
                    # No left blend possible - use full weight if between pins
                    weights[i] = 1.0
            elif main_right < frame <= secondary_right:
                # Right decay region: from 100% at main to 0% at secondary
                if right_can_blend:
                    t = (secondary_right - frame) / (secondary_right - main_right)
                    t = np.clip(t, 0.0, 1.0)
                    weights[i] = apply_blend_function(1.0, end_blend, t)
                else:
                    # No right blend possible - use full weight if between pins
                    weights[i] = 1.0
            else:
                # Outside secondary pins: 0% effect
                weights[i] = 0.0

    return weights


# =============================================================================
# OPERATION DISPATCHER
# =============================================================================


def apply_curve_operation(
    operation_type, factor, intensity, start_blend, end_blend, pin_positions, keyframe_cache, noise_properties=None
):
    """Apply a curve operation using the keyframe cache for fast updates with spatial modulation."""
    context, fcurves = get_fcurve_context()
    if not context or not fcurves or not keyframe_cache:
        return

    # Get the operation function
    from .anim_curve_tools_operators import CURVE_OPERATIONS

    operation_func = CURVE_OPERATIONS.get(operation_type)
    if not operation_func:
        return

    # IMPORTANT: Reset to original values before applying operation
    # This prevents accumulation of effects during real-time updates
    keyframe_cache.reset_to_original()

    # Apply operation to all cached F-curves
    for fcurve in fcurves:
        selected_data = keyframe_cache.get_selected_data(fcurve)
        if selected_data:
            # Calculate spatial weights for this F-curve's keyframes
            # Use original frames to ensure consistent spatial weights when switching operations
            spatial_weights = calculate_spatial_weights(
                selected_data["original_frames"], pin_positions, start_blend, end_blend
            )

            # Apply operation with spatial weights using wrapper
            call_operation_with_spatial_weights(
                operation_func,
                fcurve,
                selected_data,
                factor,
                intensity,
                start_blend,
                end_blend,
                pin_positions,
                keyframe_cache,
                spatial_weights,
                noise_properties,
            )

    # Apply cached changes back to F-curves with proper handle types
    keyframe_cache.apply_to_fcurves(operation_type)

    # Update all visible F-curves for proper redrawing (similar to timewarper)
    if hasattr(context, "visible_fcurves"):
        for fc in context.visible_fcurves:
            fc.update()

    refresh_ui(context)


# =============================================================================
# DYNAMIC REFERENCE KEYFRAME UTILITIES
# =============================================================================


def is_within_blend_range(frame, pin_positions):
    """
    Check if a frame is within the current blend range (between secondary pins).

    Args:
        frame: Frame number to check
        pin_positions: List of 4 frame positions [secondary_left, main_left, main_right, secondary_right]

    Returns:
        bool: True if frame is within blend range
    """
    if len(pin_positions) < 4:
        return False

    secondary_left, _, _, secondary_right = pin_positions
    return secondary_left <= frame <= secondary_right


def get_keyframes_outside_blend_range(fcurve, pin_positions):
    """
    Get all keyframes that are outside the current blend range.

    Args:
        fcurve: The F-curve to analyze
        pin_positions: List of 4 frame positions [secondary_left, main_left, main_right, secondary_right]

    Returns:
        tuple: (left_keyframes, right_keyframes) - lists of (frame, value) tuples
    """
    if len(pin_positions) < 4:
        return [], []

    secondary_left, _, _, secondary_right = pin_positions
    left_keyframes = []
    right_keyframes = []

    for keyframe in fcurve.keyframe_points:
        frame = keyframe.co[0]
        value = keyframe.co[1]

        if frame < secondary_left:
            left_keyframes.append((frame, value))
        elif frame > secondary_right:
            right_keyframes.append((frame, value))

    # Sort by frame for consistency
    left_keyframes.sort(key=lambda x: x[0])
    right_keyframes.sort(key=lambda x: x[0])

    return left_keyframes, right_keyframes


def get_dynamic_reference_keyframes(fcurve, pin_positions, initially_selected_indices, operation_type=None):
    """
    Get reference keyframes that are just outside the current blend range.

    This function dynamically evaluates keyframes based on the current pin positions,
    always taking the ones immediately outside the blend range OR the initially
    selected ones in case the blend is past those limits to avoid errors.

    If no further frames exist in the right direction, use the last ones from the selection.

    The number and type of reference keyframes depend on the operation:
    - blend_neighbor, ease, ease_to_ease, blend_ease: Need immediate neighbors (1 on each side)
    - smooth: Needs more context keyframes (2-3 on each side)
    - blend_infinite: Needs slope calculation from multiple keyframes
    - tween: Needs immediate neighbors for interpolation

    Args:
        fcurve: The F-curve to analyze
        pin_positions: List of 4 frame positions [secondary_left, main_left, main_right, secondary_right]
        initially_selected_indices: Indices of initially selected keyframes (immutable)
        operation_type: Type of operation to determine reference strategy

    Returns:
        dict: Contains reference keyframe data based on operation requirements
    """
    if len(pin_positions) < 4:
        return None

    secondary_left, main_left, main_right, secondary_right = pin_positions
    keyframe_points = fcurve.keyframe_points

    # Find the blend range boundaries (secondary pins)
    blend_left_frame = secondary_left
    blend_right_frame = secondary_right

    # Determine how many reference keyframes we need based on operation
    if operation_type in [CurveOperationType.SMOOTH]:
        # Smooth operations need more context for better averaging
        reference_count = 3
    elif operation_type in [CurveOperationType.BLEND_INFINITE]:
        # Infinite blending needs multiple points for slope calculation
        reference_count = 2
    elif operation_type in [
        CurveOperationType.EASE,
        CurveOperationType.EASE_TO_EASE,
        CurveOperationType.BLEND_EASE,
        CurveOperationType.BLEND_NEIGHBOR,
        CurveOperationType.TWEEN,
    ]:
        # Ease, blend, and tween operations need immediate neighbors (1 on each side)
        reference_count = 1
    else:
        # Default: most operations just need immediate neighbors
        reference_count = 1

    # Collect keyframes outside the blend range
    left_keyframes = []
    right_keyframes = []

    for i, keyframe in enumerate(keyframe_points):
        frame = keyframe.co[0]
        value = keyframe.co[1]

        if frame < blend_left_frame:
            left_keyframes.append((frame, value, i))
        elif frame > blend_right_frame:
            right_keyframes.append((frame, value, i))

    # Sort by frame for consistency
    left_keyframes.sort(key=lambda x: x[0])
    right_keyframes.sort(key=lambda x: x[0])

    # Get the required number of reference keyframes
    left_references = []
    right_references = []

    # For left side, we want the closest keyframes to the blend range
    if left_keyframes:
        # Take the last N keyframes (closest to blend range)
        left_references = (
            left_keyframes[-reference_count:] if len(left_keyframes) >= reference_count else left_keyframes
        )

    # For right side, we want the closest keyframes to the blend range
    if right_keyframes:
        # Take the first N keyframes (closest to blend range)
        right_references = (
            right_keyframes[:reference_count] if len(right_keyframes) >= reference_count else right_keyframes
        )

    # FALLBACK STRATEGY: If no external keyframes found, use initially selected keyframes as fallback
    if not left_references and initially_selected_indices is not None and len(initially_selected_indices) > 0:
        # Use the leftmost initially selected keyframe
        leftmost_idx = int(np.min(initially_selected_indices))
        if leftmost_idx < len(keyframe_points):
            kf = keyframe_points[leftmost_idx]
            left_references = [(kf.co[0], kf.co[1], leftmost_idx)]

    if not right_references and initially_selected_indices is not None and len(initially_selected_indices) > 0:
        # Use the rightmost initially selected keyframe
        rightmost_idx = int(np.max(initially_selected_indices))
        if rightmost_idx < len(keyframe_points):
            kf = keyframe_points[rightmost_idx]
            right_references = [(kf.co[0], kf.co[1], rightmost_idx)]

    # If we still don't have reference frames in one direction but have selection,
    # use the edge keyframes from selection
    if (
        not left_references
        and not right_references
        and initially_selected_indices is not None
        and len(initially_selected_indices) >= 2
    ):
        # Use first and last selected as references
        leftmost_idx = int(np.min(initially_selected_indices))
        rightmost_idx = int(np.max(initially_selected_indices))

        if leftmost_idx < len(keyframe_points):
            kf = keyframe_points[leftmost_idx]
            left_references = [(kf.co[0], kf.co[1], leftmost_idx)]

        if rightmost_idx < len(keyframe_points):
            kf = keyframe_points[rightmost_idx]
            right_references = [(kf.co[0], kf.co[1], rightmost_idx)]

    # Prepare return data with operation-specific information
    result = {
        "left_references": left_references,
        "right_references": right_references,
        "blend_left_frame": blend_left_frame,
        "blend_right_frame": blend_right_frame,
        "operation_type": operation_type,
    }

    # Add compatibility fields for operations that expect single values
    if left_references:
        result["left_value"] = left_references[-1][1]  # Closest to blend range
        result["left_frame"] = left_references[-1][0]
    else:
        result["left_value"] = None
        result["left_frame"] = None

    if right_references:
        result["right_value"] = right_references[0][1]  # Closest to blend range
        result["right_frame"] = right_references[0][0]
    else:
        result["right_value"] = None
        result["right_frame"] = None

    return result


# =============================================================================
# REFERENCE COORDINATE CALCULATION
# =============================================================================


def calculate_reference_coordinates(fcurve, selected_data, pin_positions, operation_type):
    """
    Calculate reference coordinates (X and Y positions) for curve operations.

    This consolidates the repeated logic for getting reference values and frame positions
    across all curve operation functions.

    Args:
        fcurve: The F-curve being operated on
        selected_data: Data about selected keyframes
        pin_positions: Pin positions for reference
        operation_type: Type of operation to determine reference strategy

    Returns:
        dict: Contains left_neighbor_x, left_neighbor_y, right_neighbor_x, right_neighbor_y
              and local_x, local_y coordinates
    """
    indices = selected_data["indices"]
    original_values = selected_data["original_values"]
    original_frames = selected_data["original_frames"]

    # Store immutable fallback values to prevent feedback loops
    fallback_left_y = original_values[0].item() if hasattr(original_values[0], "item") else float(original_values[0])
    fallback_right_y = (
        original_values[-1].item() if hasattr(original_values[-1], "item") else float(original_values[-1])
    )
    fallback_left_x = original_frames[0].item() if hasattr(original_frames[0], "item") else float(original_frames[0])
    fallback_right_x = (
        original_frames[-1].item() if hasattr(original_frames[-1], "item") else float(original_frames[-1])
    )

    # Get dynamic reference keyframes
    ref_data = get_dynamic_reference_keyframes(fcurve, pin_positions, indices, operation_type)

    if ref_data and ref_data["left_value"] is not None and ref_data["right_value"] is not None:
        left_neighbor_y = ref_data["left_value"]
        right_neighbor_y = ref_data["right_value"]

        # Use actual keyframe frames from dynamic reference keyframes (outside blend range)
        # This ensures we're referencing the correct neighboring keyframes, not pin positions
        left_neighbor_x = ref_data["left_frame"] if ref_data["left_frame"] is not None else original_frames[0]
        right_neighbor_x = ref_data["right_frame"] if ref_data["right_frame"] is not None else original_frames[-1]
    else:
        # Use the pre-stored immutable reference values to prevent feedback loops
        left_neighbor_y = fallback_left_y
        right_neighbor_y = fallback_right_y
        left_neighbor_x = fallback_left_x
        right_neighbor_x = fallback_right_x

    # Calculate local coordinates
    local_y = right_neighbor_y - left_neighbor_y
    local_x = right_neighbor_x - left_neighbor_x

    return {
        "left_neighbor_x": left_neighbor_x,
        "left_neighbor_y": left_neighbor_y,
        "right_neighbor_x": right_neighbor_x,
        "right_neighbor_y": right_neighbor_y,
        "local_x": local_x,
        "local_y": local_y,
        "ref_data": ref_data,
    }


def apply_spatial_weights_to_values(original_values, target_values, intensity, spatial_weights):
    """
    Apply spatial weights to blend between original and target values.

    Args:
        original_values: numpy array of original keyframe values
        target_values: numpy array of target keyframe values
        intensity: float, base intensity (0-100)
        spatial_weights: numpy array of spatial weights (0.0-1.0)

    Returns:
        numpy array of final values with spatial weighting applied
    """
    # Calculate the effect difference first
    effect_difference = target_values - original_values

    if spatial_weights is None:
        # No spatial weighting, use intensity as multiplier
        intensity_multiplier = intensity / 100.0
        scaled_difference = effect_difference * intensity_multiplier
    else:
        # Apply spatial weights to the intensity multiplier
        intensity_multiplier = (intensity / 100.0) * spatial_weights
        scaled_difference = effect_difference * intensity_multiplier

    return original_values + scaled_difference


def call_operation_with_spatial_weights(
    operation_func,
    fcurve,
    selected_data,
    factor,
    intensity,
    start_blend,
    end_blend,
    pin_positions,
    cache,
    spatial_weights,
    noise_properties=None,
):
    """
    Call a cached operation function and apply spatial weights to the result.

    This is a wrapper that allows existing cached functions to work with spatial weights
    without modifying each one individually.

    Args:
        operation_func: The cached operation function to call
        fcurve: The F-curve being operated on
        selected_data: Data about selected keyframes
        factor: Primary factor parameter (-1.0 to 1.0)
        intensity: Intensity multiplier (-1.0 to 1.0)
        start_blend: Start blend type
        end_blend: End blend type
        pin_positions: Pin positions for reference
        cache: Keyframe cache
        spatial_weights: Spatial weights for blending
    """
    # Store original values before operation
    original_values = selected_data["original_values"].copy()

    # All operations now support factor parameter
    if spatial_weights is None:
        # Call with factor parameter and noise properties
        operation_func(
            fcurve, selected_data, factor, intensity, start_blend, end_blend, pin_positions, cache, noise_properties
        )
        return
    else:
        # Apply the operation at full intensity to get target values
        operation_func(
            fcurve, selected_data, factor, 1.0, start_blend, end_blend, pin_positions, cache, noise_properties
        )

    # Get the result values from cache
    current_cache = cache.fcurve_data[fcurve]
    indices = cache.initially_selected_indices[fcurve]
    target_values = current_cache["current_values"][indices]

    # Apply spatial weights to the final result
    final_values = apply_spatial_weights_to_values(original_values, target_values, intensity * 100.0, spatial_weights)

    # Update cache with spatially weighted values
    cache.update_selected_values(fcurve, final_values)
