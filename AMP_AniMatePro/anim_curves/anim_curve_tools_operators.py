import bpy
import bmesh
import mathutils
from mathutils import Vector
import math
import numpy as np
import random
from typing import List, Tuple, Dict, Optional, Any
from ..utils.gui_pins import ScopeGUI, BlendType, StandaloneFactor
from ..utils import get_prefs, refresh_ui
from ..utils.curve import (
    s_curve,
    apply_gaussian_smooth,
    butterworth_lowpass_filter,
    butterworth_lowpass_filter_time_aware,
    _apply_time_aware_gaussian_smooth,
    get_selected_keyframes_range_offset,
    get_active_fcurves_obj,
    selected_elements_fcurves,
)
from ..utils.key import get_property_default_value
from . import anim_curve_tools as act
from . import anim_curves_tools_helpers as act_help


# Update the operations mapping (renamed from CURVE_OPERATIONS_CACHED)
CURVE_OPERATIONS = {
    act_help.CurveOperationType.BLEND_EASE: act.blend_ease,
    # act_help.CurveOperationType.BLEND_FRAME: act.blend_frame,
    act_help.CurveOperationType.BLEND_INFINITE: act.blend_infinite,
    act_help.CurveOperationType.BLEND_NEIGHBOR: act.blend_neighbor,
    act_help.CurveOperationType.BLEND_DEFAULT: act.blend_default,
    act_help.CurveOperationType.BLEND_OFFSET: act.blend_offset,
    act_help.CurveOperationType.EASE: act.ease,
    act_help.CurveOperationType.EASE_TO_EASE: act.ease_to_ease,
    act_help.CurveOperationType.SCALE_AVERAGE: act.scale_average,
    act_help.CurveOperationType.SCALE_LEFT: act.scale_left,
    act_help.CurveOperationType.SCALE_RIGHT: act.scale_right,
    act_help.CurveOperationType.SHEAR_LEFT: act.shear_left,
    act_help.CurveOperationType.SHEAR_RIGHT: act.shear_right,
    act_help.CurveOperationType.PUSH_PULL: act.push_pull,
    act_help.CurveOperationType.TIME_OFFSET: act.time_offset,
    act_help.CurveOperationType.TWEEN: act.tween,
    act_help.CurveOperationType.SMOOTH: act.smooth,
    act_help.CurveOperationType.SMOOTH_JITTER: act.smooth_jitter,
    act_help.CurveOperationType.WAVE_NOISE: act.wave_noise,
    act_help.CurveOperationType.PERLIN_NOISE: act.perlin_turbulence,
}


# =============================================================================
# MAIN CURVE TOOLS OPERATOR
# =============================================================================


class AMP_OT_curve_tools(bpy.types.Operator):
    """
    Interactive curve tools operator with GUI pins system.

    Provides real-time manipulation of F-curve keyframes using various
    curve operations with visual feedback through the GUI pins interface.

    Features:
    - Various curve operations (blend, ease, scale, smooth, etc.)
    - Interactive GUI pins for blend range control
    - Real-time intensity adjustment with multiplier support
    - Factor handler for additional parameter control (-1.0 to 1.0)
    - Quick drag mode for immediate factor adjustment
    - Blend type selectors for customizable falloff curves
    - Full support for Blender 4.5+ slotted actions

    The operator supports both Graph Editor mode (with selected keyframes) and
    Current Frame mode (when no keyframes are selected). In both modes, the system
    properly handles Blender 4.5+ slotted actions by using the correct utility
    functions for F-curve access.

    The operator supports a blend_offset parameter that controls the initial
    positioning of the main pins:
    - When blend_offset = 0: Main pins are positioned at the first/last selected keyframes
    - When blend_offset > 0: Main pins are offset inward by the specified number of frames

    Secondary pins are always positioned at the first and last selected keyframes
    to define the blend range. Operations that use reference keyframes (like
    blend_neighbor, blend_ease, ease, ease_to_ease) dynamically evaluate keyframes
    outside the blend range for more cohesive interaction.

    Quick Drag Mode:
    - When quick_drag=True, factor dragging starts immediately on mouse movement
    - No mouse click required to start dragging factor
    - Left mouse button stops quick drag and enables normal interaction
    - Enter confirms the operation, Escape cancels
    """

    bl_idname = "anim.amp_curve_tools"
    bl_label = "Curve Tools"
    bl_description = "Interactive curve manipulation tools with GUI pins"
    bl_options = {"REGISTER", "UNDO", "GRAB_CURSOR"}

    @classmethod
    def poll(cls, context):
        """Check if the operator can be executed."""
        # Must be in Graph Editor or have selected objects with animation data
        if context.space_data and context.space_data.type == "GRAPH_EDITOR":
            # In Graph Editor - check if we have F-curves
            if not context.editable_fcurves:
                return False

            # If we have selected F-curves, check if operation is valid
            if context.selected_editable_fcurves:
                # Check if any keyframes are selected
                has_selected_keyframes = False
                for fcurve in context.selected_editable_fcurves:
                    for keyframe in fcurve.keyframe_points:
                        if keyframe.select_control_point:
                            has_selected_keyframes = True
                            break
                    if has_selected_keyframes:
                        break

                # For keyframe-required operations, we need selected keyframes
                # This will be checked per operation instance, but we allow the operator to run
                return True
            else:
                return False
        else:
            # Outside Graph Editor - check if we have selected objects with animation data
            # Must have at least one selected object
            if not context.selected_objects:
                return False

            # Use utility functions to check for animation data (handles slotted actions)
            # Try to get F-curves to see if there's any animation data
            try:
                # Use a minimal context check for efficiency
                has_animation = False

                if context.mode == "POSE" and context.active_object and context.selected_pose_bones:
                    # Check if we can get any F-curves from selected pose bones
                    test_fcurves = list(selected_elements_fcurves(context))
                    has_animation = len(test_fcurves) > 0
                else:
                    # Check if any selected object has F-curves
                    for obj in context.selected_objects:
                        if obj.animation_data:
                            test_fcurves = list(get_active_fcurves_obj(obj))
                            if len(test_fcurves) > 0:
                                has_animation = True
                                break

                return has_animation
            except:
                # Fallback to legacy check if utilities fail
                for obj in context.selected_objects:
                    if obj.animation_data and obj.animation_data.action:
                        return True
                return False

    # Operation selection
    operation: bpy.props.EnumProperty(
        name="Operation",
        description="Curve operation to perform",
        items=act_help.CurveOperationType.get_all_operations(),
        default=act_help.CurveOperationType.BLEND_EASE,
    )

    intensity: bpy.props.FloatProperty(
        name="Intensity",
        description="Intensity multiplier for the effect (-1.0 to 1.0). Acts as dampener (< 1.0) or amplifier (> 1.0) of the operation result",
        default=1.0,
        min=-1.0,
        max=1.0,
        unit="NONE",
        subtype="FACTOR",
    )

    # Blend options
    start_blend: bpy.props.EnumProperty(
        name="Start Blend",
        description="Blending type for the start of the range",
        items=[(bt, BlendType.get_display_name(bt), "") for bt in BlendType.get_all()],
        default=BlendType.LINEAR,
    )

    end_blend: bpy.props.EnumProperty(
        name="End Blend",
        description="Blending type for the end of the range",
        items=[(bt, BlendType.get_display_name(bt), "") for bt in BlendType.get_all()],
        default=BlendType.LINEAR,
    )

    # Blend offset for main pins
    blend_offset: bpy.props.FloatProperty(
        name="Blend Offset",
        description="Offset for main pins from the blend frames (in frames)",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit="NONE",
    )

    factor_value: bpy.props.FloatProperty(
        name="Factor Value",
        description="Factor for operation behavior (-2.0 to 2.0 with overshoot, -1.0 to 1.0 without). Controls shape/bias of the operation",
        default=0.0,
        min=-2.0,
        max=2.0,
        precision=2,
    )

    factor_multiplier: bpy.props.FloatProperty(
        name="Factor Multiplier",
        description="Multiplier for the factor value",
        default=1.0,
        min=0.1,
        max=10.0,
    )

    use_factor: bpy.props.BoolProperty(
        name="Use Factor",
        description="Enable the Factor handler in the GUI",
        default=True,
    )

    quick_drag: bpy.props.BoolProperty(
        name="Quick Drag",
        description="Start factor dragging immediately when operator is called",
        default=False,
    )

    use_overshoot: bpy.props.BoolProperty(
        name="Enable Overshoot",
        description="Enable overshoot for operations that support it (extends factor range from ±1.0 to ±2.0)",
        default=False,
    )

    # Noise modifier properties
    noise_phase: bpy.props.FloatProperty(
        name="Noise Phase",
        description="Base phase shift for the noise pattern (changes wave phase)",
        default=0.0,
        min=-6.28318530718,
        max=6.28318530718,  # 2*pi
        precision=3,
        subtype="ANGLE",
    )

    noise_randomization: bpy.props.FloatProperty(
        name="Noise Randomization",
        description="Randomization factor for noise and phase variation between F-curves (0 = identical, 1 = maximum variation)",
        default=0.0,
        min=0.0,
        max=1.0,
        precision=3,
    )

    noise_strength: bpy.props.FloatProperty(
        name="Noise Strength",
        description="Overall strength multiplier for the noise effect",
        default=1.0,
        min=0.0,
        max=10.0,
        precision=2,
    )

    noise_scale: bpy.props.FloatProperty(
        name="Noise Scale",
        description="Scale factor for noise frequency (0 = default scale, negative = tighter, positive = wider)",
        default=0.0,
        min=-10.0,
        max=10.0,
        precision=2,
    )

    # Current frame mode properties
    _current_frame_mode = False
    _init_mouse_x = 0
    _init_mouse_y = 0
    _current_frame_factor = 0.0
    _original_frame_values = {}
    _left_neighbor_values = {}
    _right_neighbor_values = {}
    _current_frame_factor_handler = None

    # Class variables for modal operation
    _scope_gui = None
    _draw_handler = None
    _is_running = False
    _initial_values = {}
    _keyframe_cache = None
    _was_dragging = False  # Track previous drag state for refresh detection

    def invoke(self, context, event):
        """Initialize and start the modal operator."""

        if self._is_running:
            self.report({"WARNING"}, "Curve Tools is already running")
            return {"CANCELLED"}

        # Check if current operation requires keyframes
        if act_help.CurveOperationType.requires_keyframes(self.operation):
            # Operation requires keyframes - check if we have them
            has_selected_keyframes = self._check_selected_keyframes(context)
            if not has_selected_keyframes:
                self.report({"WARNING"}, f"Operation '{self.operation}' requires selected keyframes")
                return {"CANCELLED"}

        # Check if we have selected keyframes first
        has_selected_keyframes = self._check_selected_keyframes(context)

        if not has_selected_keyframes:
            # No keyframes selected - enter current frame mode if supported
            if not act_help.CurveOperationType.supports_current_frame_mode(self.operation):
                self.report({"WARNING"}, f"Operation '{self.operation}' requires selected keyframes")
                return {"CANCELLED"}
            return self._invoke_current_frame_mode(context, event)

        # Check if all selected keyframes are on the current frame
        current_frame = context.scene.frame_current
        if self._all_selected_keyframes_on_current_frame(context, current_frame):
            # All selected keyframes are on current frame - use current frame mode
            if act_help.CurveOperationType.supports_current_frame_mode(self.operation):
                return self._invoke_current_frame_mode(context, event)
            else:
                self.report({"WARNING"}, f"Operation '{self.operation}' requires keyframes on multiple frames")
                return {"CANCELLED"}

        # Store initial keyframe values for undo
        self._store_initial_values(context)

        # Initialize keyframe cache
        self._keyframe_cache = act_help.KeyframeCache()
        self._keyframe_cache.cache_keyframes(context.selected_editable_fcurves)

        # Get frame range from selected keyframes
        # frame_range = self._get_selected_frame_range(context)
        frame_range = get_selected_keyframes_range_offset(context)

        if not frame_range:
            self.report({"WARNING"}, "No keyframes selected")
            return {"CANCELLED"}

        # Get initial pin positions with blend offset
        pin_positions = self._get_initial_pin_positions(frame_range)

        # Initialize the scope GUI
        # Convert the 3-element tuples to a dictionary (id -> name)
        operations_dict = {
            op_id: op_name for op_id, op_name, op_desc in act_help.CurveOperationType.get_all_operations()
        }
        operation_name = operations_dict.get(self.operation, "Unknown Operation")

        # Calculate blend range from secondary pins
        blend_range_frames = pin_positions[3] - pin_positions[0]  # secondary_right - secondary_left

        # Get preferences for overshoot
        prefs = get_prefs()
        factor_range = 2.0 if prefs.guipins_overshoot else 1.0

        # Initialize use_overshoot property to match current preference
        self.use_overshoot = prefs.guipins_overshoot

        # Clamp factor_value to appropriate range
        clamped_factor_value = max(-factor_range, min(factor_range, self.factor_value))

        # Update the operator's factor_value to the clamped value
        self.factor_value = clamped_factor_value

        # Define property definitions for GUI property boxes
        property_definitions = []

        # Add overshoot property for operations that support it
        if act_help.CurveOperationType.supports_overshoot(self.operation):
            property_definitions.append(
                {
                    "path": "use_overshoot",
                    "display_name": "Overshoot",
                    "type": "bool",
                    "range": None,  # Not used for bool
                    "initial_value": self.use_overshoot,
                    "decimal_speed": 1.0,  # Not used for bool
                }
            )

        # Add noise properties for noise operations
        if self.operation in [act_help.CurveOperationType.WAVE_NOISE, act_help.CurveOperationType.PERLIN_NOISE]:
            property_definitions.extend(
                [
                    {
                        "path": "noise_phase",
                        "display_name": "Phase",
                        "type": "float",
                        "range": (-6.28318530718, 6.28318530718),  # 2*pi
                        "initial_value": self.noise_phase,
                        "decimal_speed": 0.1,
                    },
                    {
                        "path": "noise_randomization",
                        "display_name": "Randomization",
                        "type": "float",
                        "range": (0.0, 1.0),
                        "initial_value": self.noise_randomization,
                        "decimal_speed": 0.01,
                    },
                    {
                        "path": "noise_strength",
                        "display_name": "Strength",
                        "type": "float",
                        "range": (0.0, 10.0),
                        "initial_value": self.noise_strength,
                        "decimal_speed": 0.1,
                    },
                    {
                        "path": "noise_scale",
                        "display_name": "Scale",
                        "type": "float",
                        "range": (-10.0, 10.0),
                        "initial_value": self.noise_scale,
                        "decimal_speed": 0.1,
                    },
                ]
            )

        self._scope_gui = ScopeGUI(
            frame_range=(pin_positions[1], pin_positions[2]),  # main_left, main_right
            operation_name=operation_name,
            blend_range=max(1, int(blend_range_frames / 3)),
            start_blend=self.start_blend,
            end_blend=self.end_blend,
            operation_options=act_help.CurveOperationType.get_all_operations(),
            property_definitions=property_definitions,
            factor_value=self.factor_value if self.use_factor else None,
            factor_multiplier=self.factor_multiplier,
            quick_drag=self.quick_drag,
        )

        # Manually set the pin positions to match our calculated positions
        if hasattr(self._scope_gui, "pins") and self._scope_gui.pins:
            for i, pin in enumerate(self._scope_gui.pins):
                if i < len(pin_positions):
                    pin.frame = pin_positions[i]

        # Set colors from preferences
        prefs = get_prefs()
        main_color = (0.05, 0.05, 0.05, 0.75)
        accent_color = (1.0, 0.5, 0.0, 1.0)
        self._scope_gui.set_colors(main_color, accent_color)

        # Set the initial operation in the operation selector
        if hasattr(self._scope_gui, "operation_selector") and self._scope_gui.operation_selector:
            self._scope_gui.operation_selector.set_operation(self.operation)
            self._sync_operation_selector()

        # Activate the GUI
        self._scope_gui.activate()

        # If quick_drag is enabled, warp mouse to factor handler position
        if (
            self.quick_drag
            and self._scope_gui
            and hasattr(self._scope_gui, "factor_handler")
            and self._scope_gui.factor_handler
        ):
            # Get the factor handler screen position
            handler_pos = self._scope_gui.get_factor_handler_screen_position(context)
            if handler_pos and context.region:
                handler_x, handler_y = handler_pos
                # Convert region coordinates to window coordinates for warping
                # The handler position is already in region coordinates
                # We need to add the region's offset to get window coordinates
                region = context.region
                window_x = int(region.x + handler_x)
                window_y = int(region.y + handler_y)
                context.window.cursor_warp(window_x, window_y)

        # Register draw handler
        self._draw_handler = context.space_data.draw_handler_add(
            self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
        )

        # Start modal operation
        context.window_manager.modal_handler_add(self)
        self._is_running = True

        return {"RUNNING_MODAL"}

    def _check_selected_keyframes(self, context):
        """Check if any keyframes are selected in selected F-curves."""
        if not context.selected_editable_fcurves:
            return False

        for fcurve in context.selected_editable_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    return True
        return False

    def _all_selected_keyframes_on_current_frame(self, context, current_frame):
        """Check if all selected keyframes are on the current frame."""
        if not context.selected_editable_fcurves:
            return False

        has_selected_keyframes = False
        for fcurve in context.selected_editable_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    has_selected_keyframes = True
                    # Check if this keyframe is not on the current frame (with tolerance)
                    if abs(keyframe.co[0] - current_frame) > 0.001:
                        return False

        return has_selected_keyframes

    def _invoke_current_frame_mode(self, context, event):
        """Initialize current frame mode when no keyframes are selected."""
        # Check if we have selected objects/bones with animation data
        if not self._has_animation_data(context):
            self.report({"WARNING"}, "No selected objects or bones with animation data")
            return {"CANCELLED"}

        # Check if auto keyframing is enabled
        if not context.scene.tool_settings.use_keyframe_insert_auto:
            self.report({"WARNING"}, "Auto keyframing is disabled and no keyframes are selected")
            return {"CANCELLED"}

        # Find the appropriate target area and region for drawing the factor handler
        # Always use the current area where the operator was called from
        target_area = context.area
        target_region = None

        # Find the main region (not header or tool regions) in the current area
        if target_area:
            for region in target_area.regions:
                if region.type == "WINDOW":
                    target_region = region
                    break

        if not target_area or not target_region:
            self.report({"WARNING"}, "No suitable area found for factor handler display")
            return {"CANCELLED"}

        # Initialize current frame mode
        self._current_frame_mode = True
        # Store original mouse position and region for restoration
        self._init_mouse_x = event.mouse_region_x  # Original region coords
        self._init_mouse_y = event.mouse_region_y
        self._init_region = context.region  # Store original region (might be side panel)
        self._current_frame_factor = 0.0

        # Store original values at current frame and find neighbors
        self._store_current_frame_data(context)

        # Initialize standalone factor handler
        self._current_frame_factor_handler = StandaloneFactor(
            factor=self._current_frame_factor, multiplier=self.factor_multiplier
        )

        # Position the factor handler in the target area region
        # Use the center horizontally and position at the top with offset
        handler_center_x = target_region.width * 0.5  # Center of target region
        handler_center_y = target_region.height - 80  # Near top of target region

        self._current_frame_factor_handler.get_screen_position(
            context, screen_x=handler_center_x, screen_y=handler_center_y
        )

        # Activate the factor handler
        self._current_frame_factor_handler.activate(context)

        factor_center_x = self._current_frame_factor_handler.screen_x
        factor_center_y = self._current_frame_factor_handler.screen_y

        window_x = int(target_region.x + factor_center_x)
        window_y = int(target_region.y + factor_center_y)
        context.window.cursor_warp(window_x, window_y)

        center_x = self._current_frame_factor_handler.screen_x
        center_y = self._current_frame_factor_handler.screen_y
        self._current_frame_factor_handler.start_drag(center_x, center_y, context)

        # Set cursor
        context.window.cursor_set("SCROLL_X")

        # Start modal operation
        context.window_manager.modal_handler_add(self)
        self._is_running = True

        return {"RUNNING_MODAL"}

    def _has_animation_data(self, context):
        """Check if selected objects/bones have animation data."""
        # Use the proper utility function to check for animation data
        # This handles both legacy and slotted actions correctly
        fcurves = list(self._get_animation_fcurves(context))
        return len(fcurves) > 0

    def _store_current_frame_data(self, context):
        """Store original values at current frame and find neighbor values."""
        current_frame = context.scene.frame_current
        self._original_frame_values = {}
        self._left_neighbor_values = {}
        self._right_neighbor_values = {}

        # Get all F-curves from selected objects/bones
        fcurves = self._get_animation_fcurves(context)

        for fcurve in fcurves:
            # Get current value
            current_value = fcurve.evaluate(current_frame)
            self._original_frame_values[fcurve] = current_value

            # Find left and right neighbors
            left_neighbor = None
            right_neighbor = None

            for keyframe in fcurve.keyframe_points:
                frame = keyframe.co[0]
                if frame < current_frame:
                    if left_neighbor is None or frame > left_neighbor[0]:
                        left_neighbor = (frame, keyframe.co[1])
                elif frame > current_frame:
                    if right_neighbor is None or frame < right_neighbor[0]:
                        right_neighbor = (frame, keyframe.co[1])

            # Store neighbor values or fallback to current
            self._left_neighbor_values[fcurve] = left_neighbor[1] if left_neighbor else current_value
            self._right_neighbor_values[fcurve] = right_neighbor[1] if right_neighbor else current_value

    def _get_animation_fcurves(self, context):
        """Get F-curves from selected objects/bones with animation data."""
        fcurves = []

        # Use the proper utility function that handles both legacy and slotted actions
        if context.mode == "POSE" and context.active_object and context.selected_pose_bones:
            # In Pose Mode: Use selected elements fcurves which properly handles slotted actions
            fcurves.extend(selected_elements_fcurves(context))
        else:
            # In Object Mode: Get fcurves from each selected object's active slot
            for obj in context.selected_objects:
                if obj.animation_data:
                    fcurves.extend(get_active_fcurves_obj(obj))

        return fcurves

    def _get_operation_display_name(self):
        """Get display name for current operation."""
        operations_dict = {
            op_id: op_name for op_id, op_name, op_desc in act_help.CurveOperationType.get_all_operations()
        }
        return operations_dict.get(self.operation, "Unknown Operation").replace("_", " ")

    def modal(self, context, event):
        """Handle modal events."""
        # Handle current frame mode
        if self._current_frame_mode:
            return self._modal_current_frame_mode(context, event)

        # Original modal behavior for keyframe selection mode
        # Check if we're in the Graph Editor
        if not context.space_data or context.space_data.type != "GRAPH_EDITOR":
            self.report({"ERROR"}, "Must be in the Graph Editor")
            return {"CANCELLED"}

        # Check if there are any editable F-curves
        if not context.editable_fcurves:
            self.report({"ERROR"}, "No F-curves available")
            return {"CANCELLED"}

        # Check if there are any selected editable F-curves
        if not context.selected_editable_fcurves:
            self.report({"ERROR"}, "No F-curves selected")
            return {"CANCELLED"}

        # Check if any keyframes are selected
        has_selected_keyframes = False
        for fcurve in context.selected_editable_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    has_selected_keyframes = True
                    break
            if has_selected_keyframes:
                break

        if not self._scope_gui:
            return {"CANCELLED"}

        if event.type in {"MIDDLE_MOUSE", "MWHEELUP", "MWHEELDOWN"}:
            return {"PASS_THROUGH"}

        # Handle exit conditions
        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        # Handle quick drag mode - LMB stops quick drag and allows normal interaction
        if self.quick_drag and event.type == "LEFTMOUSE" and event.value == "PRESS":
            # Stop quick drag mode and switch to normal interaction
            if hasattr(self._scope_gui, "factor_handler") and self._scope_gui.factor_handler:
                self._scope_gui.factor_handler.in_quick_drag = False
                self._scope_gui.factor_handler.end_drag(context)
                # Ensure cursor is restored when stopping quick drag
                if hasattr(self._scope_gui, "cursor_manager"):
                    self._scope_gui.cursor_manager.restore_cursor(context)
                # Clear the dragging element to allow normal interaction
                if hasattr(self._scope_gui, "dragging_element"):
                    self._scope_gui.dragging_element = None
            # Set quick_drag to False to switch to normal mode
            self.quick_drag = False
            # Don't return here - let normal mouse handling continue

        # Check if we were dragging before the GUI update
        was_dragging_before = (
            hasattr(self._scope_gui, "dragging_element") and self._scope_gui.dragging_element is not None
        )

        # Update GUI
        result = self._scope_gui.update(context, event)

        # Check if we stopped dragging (drag release)
        is_dragging_now = hasattr(self._scope_gui, "dragging_element") and self._scope_gui.dragging_element is not None

        # If we were dragging and now we're not, refresh F-curves
        if was_dragging_before and not is_dragging_now:
            act_help.refresh_fcurves_display(context)

        # Check for GUI events
        if result == "CONFIRMED":
            self._finish(context, confirmed=True)
            return {"FINISHED"}

        elif result == "CANCELLED":
            self._finish(context, confirmed=False)
            return {"CANCELLED"}

        # Apply curve operation in real-time
        if self._scope_gui.is_active:
            # Update operation from GUI selector
            self._update_operation_from_gui()

            # Apply the operation
            self._apply_operation(context)

            # Force refresh F-curves for real-time feedback
            act_help.refresh_fcurves_display(context)

        # Handle confirmation
        if event.type == "RET" and event.value == "PRESS":
            self._finish(context, confirmed=True)
            return {"FINISHED"}

        # In normal mode (not quick drag), handle mouse press events
        if not self.quick_drag and event.type == "LEFTMOUSE" and event.value == "PRESS":
            return {"RUNNING_MODAL"}

        # Redraw
        context.area.tag_redraw()

        return {"PASS_THROUGH"}

    def _modal_current_frame_mode(self, context, event):
        """Handle modal events for current frame mode."""
        # Handle exit conditions
        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._finish_current_frame_mode(context, confirmed=False)
            return {"CANCELLED"}

        # Handle confirmation
        if event.type in {"RET", "LEFTMOUSE"} and event.value == "PRESS":
            self._finish_current_frame_mode(context, confirmed=True)
            return {"FINISHED"}

        # Handle overshoot toggle (O key)
        if event.type == "O" and event.value == "PRESS":
            # Toggle overshoot for operations that support it
            if act_help.CurveOperationType.supports_overshoot(self.operation):
                # Get preferences and toggle overshoot
                prefs = get_prefs()
                prefs.guipins_overshoot = not prefs.guipins_overshoot
                self.use_overshoot = prefs.guipins_overshoot

                # Update factor range and clamp current factor if needed
                factor_range = 2.0 if prefs.guipins_overshoot else 1.0
                if not prefs.guipins_overshoot:
                    # Overshoot was turned off - clamp factor to ±1.0
                    if self._current_frame_factor_handler:
                        self._current_frame_factor_handler.factor = max(
                            -1.0, min(1.0, self._current_frame_factor_handler.factor)
                        )
                        self._current_frame_factor = self._current_frame_factor_handler.factor

                # Apply the operation with updated factor
                self._apply_current_frame_operation(context)

                # Show feedback message
                overshoot_status = "ON" if prefs.guipins_overshoot else "OFF"
                self.report({"INFO"}, f"Overshoot: {overshoot_status}")

            return {"RUNNING_MODAL"}

        # Handle mouse movement for factor adjustment and hover updates
        if event.type == "MOUSEMOVE":
            if self._current_frame_factor_handler:
                # Update hover state
                self._current_frame_factor_handler.check_hover(event.mouse_region_x, event.mouse_region_y, context)

                # Check if shift key is held
                shift_held = event.shift

                # Update the factor handler (only if dragging)
                if self._current_frame_factor_handler.is_dragging:
                    self._current_frame_factor_handler.update_drag(
                        event.mouse_region_x, event.mouse_region_y, context, shift_held
                    )

                    # Update our internal factor value
                    self._current_frame_factor = self._current_frame_factor_handler.factor

                    # Apply the operation to current frame
                    self._apply_current_frame_operation(context)

        # Redraw
        if context.area:
            context.area.tag_redraw()

        return {"RUNNING_MODAL"}

    def _apply_current_frame_operation(self, context):
        """Apply the curve operation to the current frame values."""
        current_frame = context.scene.frame_current
        factor = self._current_frame_factor

        for fcurve in self._original_frame_values:
            original_value = self._original_frame_values[fcurve]
            left_neighbor = self._left_neighbor_values[fcurve]
            right_neighbor = self._right_neighbor_values[fcurve]

            # Calculate new value based on operation type
            new_value = self._calculate_current_frame_value(
                self.operation, factor, original_value, left_neighbor, right_neighbor
            )

            # Insert/update keyframe at current frame
            self._insert_keyframe_direct(fcurve, current_frame, new_value)

    def _calculate_current_frame_value(self, operation, factor, original_value, left_neighbor, right_neighbor):
        """Calculate the new value for current frame based on operation type."""

        # Use no-overshoot clamping for specific operations
        no_overshoot_operations = {
            act_help.CurveOperationType.BLEND_DEFAULT,
            act_help.CurveOperationType.SCALE_AVERAGE,
            act_help.CurveOperationType.BLEND_INFINITE,
        }

        if operation in no_overshoot_operations:
            factor_clamped = act_help.clamp_factor_no_overshoot(factor)
        else:
            # Clamp factor based on overshoot preference for other operations
            factor_clamped = act_help.clamp_factor(factor)

        if operation == act_help.CurveOperationType.BLEND_NEIGHBOR:
            # Blend towards neighbors based on factor direction
            if factor_clamped < 0:
                # Blend towards left neighbor
                delta = left_neighbor - original_value
                return original_value + delta * abs(factor_clamped)
            else:
                # Blend towards right neighbor
                delta = right_neighbor - original_value
                return original_value + delta * abs(factor_clamped)

        elif operation == act_help.CurveOperationType.TWEEN:
            # Linear interpolation between neighbors
            t = (factor_clamped + 1.0) / 2.0  # Convert to 0,1 range (no overshoot)
            return left_neighbor + (right_neighbor - left_neighbor) * t

        elif operation == act_help.CurveOperationType.PUSH_PULL:
            # Exaggerate or reduce relative to linear interpolation
            linear_value = left_neighbor + (right_neighbor - left_neighbor) * 0.5
            delta = original_value - linear_value
            multiplier = 1.0 + factor_clamped
            return linear_value + delta * multiplier

        elif operation == act_help.CurveOperationType.BLEND_EASE:
            # Apply easing between neighbors
            max_factor = abs(act_help.clamp_factor(1.0))
            t = (factor_clamped + max_factor) / (2.0 * max_factor)  # Convert to 0,1
            # Apply ease-in-out curve
            if t < 0.5:
                ease_t = 2 * t * t
            else:
                ease_t = 1 - 2 * (1 - t) * (1 - t)
            return left_neighbor + (right_neighbor - left_neighbor) * ease_t

        elif operation == act_help.CurveOperationType.EASE:
            # Apply C-curve easing
            max_factor = abs(act_help.clamp_factor(1.0))
            t = (factor_clamped + max_factor) / (2.0 * max_factor)  # Convert to 0,1
            # Apply ease curve based on factor direction
            if factor_clamped >= 0:
                # Ease-out
                ease_t = 1 - (1 - t) * (1 - t)
            else:
                # Ease-in
                ease_t = t * t
            return left_neighbor + (right_neighbor - left_neighbor) * ease_t

        elif operation == act_help.CurveOperationType.EASE_TO_EASE:
            # Apply S-curve easing
            max_factor = abs(act_help.clamp_factor(1.0))
            t = (factor_clamped + max_factor) / (2.0 * max_factor)  # Convert to 0,1
            # S-curve (ease-in-out)
            if t < 0.5:
                ease_t = 2 * t * t
            else:
                ease_t = 1 - 2 * (1 - t) * (1 - t)
            return left_neighbor + (right_neighbor - left_neighbor) * ease_t

        elif operation == act_help.CurveOperationType.BLEND_DEFAULT:
            # Blend towards default value (0.0 for most properties)
            default_value = 0.0  # Could be made property-specific
            delta = default_value - original_value
            return original_value + delta * factor_clamped

        elif operation == act_help.CurveOperationType.BLEND_OFFSET:
            # Offset based on neighbors
            if factor_clamped < 0:
                # Use left neighbor as reference
                delta = left_neighbor - original_value
                return original_value + delta * abs(factor_clamped)
            else:
                # Use right neighbor as reference
                delta = right_neighbor - original_value
                return original_value + delta * abs(factor_clamped)

        elif operation == act_help.CurveOperationType.BLEND_INFINITE:
            # Extend slope infinitely
            if abs(left_neighbor - right_neighbor) > 0.001:
                # Calculate slope between neighbors
                slope = (right_neighbor - left_neighbor) / 2.0  # Simplified slope
                delta = slope * factor_clamped
                return original_value + delta
            else:
                return original_value

        else:
            # Default behavior - blend towards neighbors
            if factor_clamped < 0:
                delta = left_neighbor - original_value
                return original_value + delta * abs(factor_clamped)
            else:
                delta = right_neighbor - original_value
                return original_value + delta * abs(factor_clamped)

    def _get_object_from_fcurve(self, context, fcurve):
        """Get the object that owns this F-curve."""
        if hasattr(fcurve, "id_data") and fcurve.id_data:
            # For direct object F-curves (like object transforms)
            if not isinstance(fcurve.id_data, bpy.types.Action):
                return fcurve.id_data

            # For action F-curves, search through selected objects
            action = fcurve.id_data
            for obj in context.selected_objects:
                if obj.animation_data and obj.animation_data.action == action:
                    return obj

        # Enhanced fallback - search through all F-curves from selected objects using proper utilities
        for obj in context.selected_objects:
            if obj.animation_data:
                # Use the utility function that handles both legacy and slotted actions
                for obj_fcurve in get_active_fcurves_obj(obj):
                    if obj_fcurve == fcurve:
                        return obj

        return None

    def _insert_keyframe_direct(self, fcurve, frame, value):
        """Direct keyframe insertion as fallback."""
        # Find or create keyframe at current frame
        keyframe = None
        for kf in fcurve.keyframe_points:
            if abs(kf.co[0] - frame) < 0.001:  # Frame tolerance
                keyframe = kf
                break

        if keyframe:
            # Update existing keyframe
            keyframe.co[1] = value
        else:
            # Insert new keyframe
            fcurve.keyframe_points.insert(frame, value)

        fcurve.update()

    def _finish_current_frame_mode(self, context, confirmed=True):
        """Finish current frame mode operation."""
        # Deactivate and clean up the factor handler
        if self._current_frame_factor_handler:
            self._current_frame_factor_handler.deactivate(context)
            self._current_frame_factor_handler = None

        # Restore mouse position to where the operation was initially called
        if (
            hasattr(self, "_init_region")
            and self._init_region
            and hasattr(self, "_init_mouse_x")
            and hasattr(self, "_init_mouse_y")
        ):
            # Convert original region coordinates to window coordinates for warping
            original_region = self._init_region
            window_x = int(original_region.x + self._init_mouse_x)
            window_y = int(original_region.y + self._init_mouse_y)
            try:
                context.window.cursor_warp(window_x, window_y)
            except:
                pass  # Fail silently if cursor warping fails

        # Restore cursor
        context.window.cursor_set("DEFAULT")

        current_frame = context.scene.frame_current

        if not confirmed:
            # Restore original values
            for fcurve in self._original_frame_values:
                original_value = self._original_frame_values[fcurve]
                self._insert_keyframe_direct(fcurve, current_frame, original_value)

        # Clean up
        self._current_frame_mode = False
        self._is_running = False
        self._original_frame_values.clear()
        self._left_neighbor_values.clear()
        self._right_neighbor_values.clear()

        # Refresh display
        if context.area:
            context.area.tag_redraw()

    def _store_initial_values(self, context):
        """Store initial keyframe values for undo."""
        self._initial_values = {}

        for fcurve in context.selected_editable_fcurves:
            curve_data = []
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.select_control_point:
                    curve_data.append(
                        {
                            "index": i,
                            "co": keyframe.co.copy(),
                            "handle_left": keyframe.handle_left.copy(),
                            "handle_right": keyframe.handle_right.copy(),
                            "handle_left_type": keyframe.handle_left_type,
                            "handle_right_type": keyframe.handle_right_type,
                        }
                    )

            if curve_data:
                self._initial_values[fcurve] = curve_data

    def _get_selected_frame_range(self, context):
        """Get the frame range of selected keyframes."""
        min_frame = float("inf")

        max_frame = float("-inf")

        for fcurve in context.selected_editable_fcurves:
            for keyframe in fcurve.keyframe_points:
                if keyframe.select_control_point:
                    min_frame = min(min_frame, keyframe.co[0])
                    max_frame = max(max_frame, keyframe.co[0])

        if min_frame == float("inf"):
            return None

        return (int(min_frame), int(max_frame))

    def _get_initial_pin_positions(self, frame_range):
        """
        Get initial pin positions with blend offset applied.

        Returns:
            tuple: (secondary_left, main_left, main_right, secondary_right)
        """
        min_frame, max_frame = frame_range

        # Secondary pins always at the edges of selected keyframes
        secondary_left = min_frame
        secondary_right = max_frame

        # Main pins offset inward by blend_offset, or at edges if offset is 0
        if self.blend_offset > 0:
            main_left = min_frame + self.blend_offset
            main_right = max_frame - self.blend_offset

            # Ensure main pins don't cross each other
            if main_left >= main_right:
                mid_frame = (min_frame + max_frame) / 2
                main_left = mid_frame - 0.5
                main_right = mid_frame + 0.5
        else:
            main_left = min_frame
            main_right = max_frame

        return (secondary_left, main_left, main_right, secondary_right)

    def _apply_operation(self, context):
        """Apply the curve operation with current GUI values using cached data."""
        if not self._scope_gui or not self._keyframe_cache:
            return

        # Get current values from GUI
        values = self._scope_gui.get_values()

        # Debug: Pr

        # Get preferences for overshoot
        prefs = get_prefs()
        factor_range = 2.0 if prefs.guipins_overshoot else 1.0

        # Sync factor values back to operator properties
        if "factor" in values:
            # Clamp factor to appropriate range based on overshoot preference
            self.factor_value = max(-factor_range, min(factor_range, values["factor"]))
        if "factor_multiplier" in values:
            self.factor_multiplier = values["factor_multiplier"]

        # Handle overshoot property and update preferences
        if "use_overshoot" in values:
            old_overshoot = self.use_overshoot
            self.use_overshoot = values["use_overshoot"]
            # Update the global preference to match the operation setting
            prefs.guipins_overshoot = self.use_overshoot
            # Update factor_range for current operation based on new overshoot setting
            factor_range = 2.0 if prefs.guipins_overshoot else 1.0

            # When overshoot is toggled off, clamp current factor_value to non-overshoot range
            if old_overshoot and not self.use_overshoot:
                # Overshoot was turned off - clamp factor to ±1.0
                self.factor_value = max(-1.0, min(1.0, self.factor_value))
                # Also clamp the current factor value in the GUI
                if "factor" in values:
                    values["factor"] = max(-1.0, min(1.0, values["factor"]))
                # Update the factor handler in the GUI if it exists
                if self._scope_gui and hasattr(self._scope_gui, "factor_handler") and self._scope_gui.factor_handler:
                    self._scope_gui.factor_handler.factor = max(-1.0, min(1.0, self._scope_gui.factor_handler.factor))

                # Only sync when overshoot changes, not every frame
                # Sync the preference change back to all PropertyBoxes to ensure UI consistency
                self._sync_property_values_to_gui()

        # Sync GUI property values back to operator before applying operation
        self._sync_property_values_from_gui()

        # Get the current operation from the GUI operation selector
        current_operation = None
        if hasattr(self._scope_gui, "operation_selector") and self._scope_gui.operation_selector:
            current_operation = self._scope_gui.operation_selector.get_current_operation()

        # Fall back to the operator's operation if no GUI operation is set
        if current_operation is None:
            current_operation = self.operation

        factor = values.get("factor", 0.0)
        # Clamp factor for operation as well
        factor = max(-factor_range, min(factor_range, factor))

        # Prepare noise properties for noise operations
        noise_properties = None
        if current_operation in [act_help.CurveOperationType.WAVE_NOISE, act_help.CurveOperationType.PERLIN_NOISE]:
            noise_properties = {
                "noise_phase": self.noise_phase,
                "noise_randomization": self.noise_randomization,
                "noise_strength": self.noise_strength,
                "noise_scale": self.noise_scale,
            }

        # Apply the operation using cached data
        # Factor is the primary parameter, intensity is the multiplier
        act_help.apply_curve_operation(
            current_operation,
            factor,  # Primary factor parameter (respects overshoot)
            values["effective_intensity"],  # Intensity as multiplier
            values["start_blend"],
            values["end_blend"],
            values["pin_positions"],
            self._keyframe_cache,
            noise_properties,  # Pass noise properties
        )

    def _draw_callback(self, context):
        """Draw callback for the scope GUI."""
        if self._scope_gui:
            self._scope_gui.draw(context)

    def _finish(self, context, confirmed=False):
        """Finish the modal operation."""

        # Handle current frame mode
        if self._current_frame_mode:
            self._finish_current_frame_mode(context, confirmed)
            return

        # Make sure the cursor is visible and default
        if hasattr(self._scope_gui, "cursor_manager"):
            self._scope_gui.cursor_manager.restore_cursor(context)

        # Clean up
        if self._draw_handler:
            context.space_data.draw_handler_remove(self._draw_handler, "WINDOW")
            self._draw_handler = None

        if self._scope_gui:
            self._scope_gui.deactivate()
            self._scope_gui = None

        # Handle result based on confirmation
        if confirmed:
            # Commit the changes - apply current cache state to F-curves
            if self._keyframe_cache:
                self._keyframe_cache.apply_to_fcurves(self.operation)
                # Update the scene to reflect committed changes
                context.scene.frame_set(context.scene.frame_current)
                # Force a final refresh
                act_help.refresh_fcurves_display(context)
        else:
            # Restore original values on cancel
            if self._keyframe_cache:
                self._keyframe_cache.restore_original()
            else:
                self._restore_initial_values(context)

        # Clean up cache
        self._keyframe_cache = None

        self._is_running = False
        context.area.tag_redraw()

    def _restore_initial_values(self, context):
        """Restore initial keyframe values on cancel."""
        for fcurve, curve_data in self._initial_values.items():
            for keyframe_data in curve_data:
                i = keyframe_data["index"]
                if i < len(fcurve.keyframe_points):
                    keyframe = fcurve.keyframe_points[i]
                    keyframe.co = keyframe_data["co"]
                    keyframe.handle_left = keyframe_data["handle_left"]
                    keyframe.handle_right = keyframe_data["handle_right"]
                    keyframe.handle_left_type = keyframe_data["handle_left_type"]
                    keyframe.handle_right_type = keyframe_data["handle_right_type"]

            # Update each F-curve individually
            fcurve.update()

        # Update the scene
        context.scene.frame_set(context.scene.frame_current)

        # Force refresh all F-curves
        act_help.refresh_fcurves_display(context)

        # Force update of graph editor
        for area in context.screen.areas:
            if area.type == "GRAPH_EDITOR":
                area.tag_redraw()

    def _update_operation_from_gui(self):
        """Update the operator's operation property from the GUI operation selector."""
        if not self._scope_gui or not hasattr(self._scope_gui, "operation_selector"):
            return

        operation_selector = self._scope_gui.operation_selector
        if operation_selector and operation_selector.operation_options:
            try:
                current_operation = operation_selector.get_current_operation()
                if current_operation and current_operation != self.operation:
                    # Validate that the operation exists in our operations
                    if current_operation in CURVE_OPERATIONS:
                        # Reset cache to original values when switching operations
                        # This ensures all operations are temporary and reversible
                        if self._keyframe_cache:
                            self._keyframe_cache.reset_to_original()

                        self.operation = current_operation
                        # Update the operation name display
                        operations_dict = {
                            op_id: op_name
                            for op_id, op_name, op_desc in act_help.CurveOperationType.get_all_operations()
                        }
                        if current_operation in operations_dict:
                            operation_selector.operation_name = operations_dict[current_operation]

                        # Update property definitions when operation changes
                        self._update_property_definitions_for_operation(current_operation)
            except Exception as e:
                # Log error but don't break the operation
                print(f"Error updating operation from GUI: {e}")

    def _sync_operation_selector(self):
        """Synchronize the operation selector with the current operation."""
        if not self._scope_gui or not hasattr(self._scope_gui, "operation_selector"):
            return

        operation_selector = self._scope_gui.operation_selector
        if operation_selector and operation_selector.operation_options:
            # Find the current operation and update the selector
            for i, (op_id, op_name, op_desc) in enumerate(operation_selector.operation_options):
                if op_id == self.operation:
                    operation_selector.current_option_index = i
                    operation_selector.operation_name = op_name
                    break

    def _sync_property_values_from_gui(self):
        """Sync GUI PropertyBox values back to the operator properties."""
        if not self._scope_gui or not hasattr(self._scope_gui, "property_boxes"):
            return

        # Update operator properties from GUI values
        for prop_box in self._scope_gui.property_boxes:
            if hasattr(prop_box, "property_path"):
                prop_path = prop_box.property_path

                if prop_path == "use_overshoot":
                    if self.use_overshoot != prop_box.current_value:
                        self.use_overshoot = prop_box.current_value
                elif prop_path == "noise_phase":
                    if abs(self.noise_phase - prop_box.current_value) > 0.001:  # Lower threshold
                        self.noise_phase = prop_box.current_value
                elif prop_path == "noise_randomization":
                    if abs(self.noise_randomization - prop_box.current_value) > 0.001:  # Lower threshold
                        self.noise_randomization = prop_box.current_value
                elif prop_path == "noise_strength":
                    if abs(self.noise_strength - prop_box.current_value) > 0.001:  # Lower threshold
                        self.noise_strength = prop_box.current_value
                elif prop_path == "noise_scale":
                    if abs(self.noise_scale - prop_box.current_value) > 0.001:  # Lower threshold
                        self.noise_scale = prop_box.current_value

    def _sync_property_values_to_gui(self):
        """Sync current operator property values back to the GUI PropertyBoxes."""
        if not self._scope_gui or not hasattr(self._scope_gui, "property_boxes"):
            return

        # Update property boxes to match current operator state
        for prop_box in self._scope_gui.property_boxes:
            if hasattr(prop_box, "property_path"):
                prop_path = prop_box.property_path
                old_value = prop_box.current_value
                if prop_path == "use_overshoot":
                    prop_box.current_value = self.use_overshoot
                elif prop_path == "noise_phase":
                    prop_box.current_value = self.noise_phase
                elif prop_path == "noise_randomization":
                    prop_box.current_value = self.noise_randomization
                elif prop_path == "noise_strength":
                    prop_box.current_value = self.noise_strength
                elif prop_path == "noise_scale":
                    prop_box.current_value = self.noise_scale
            # Legacy support for property_name attribute
            elif hasattr(prop_box, "property_name"):
                prop_name = prop_box.property_name
                if prop_name == "use_overshoot":
                    prop_box.current_value = self.use_overshoot

    def _update_property_definitions_for_operation(self, operation_type):
        """Update property definitions when operation changes to show/hide overshoot for appropriate operations."""
        if not self._scope_gui or not hasattr(self._scope_gui, "property_boxes"):
            return

        # Create new property definitions based on the operation
        property_definitions = []

        # Add overshoot property for operations that support it
        if act_help.CurveOperationType.supports_overshoot(operation_type):
            property_definitions.append(
                {
                    "path": "use_overshoot",
                    "display_name": "Overshoot",
                    "type": "bool",
                    "range": None,  # Not used for bool
                    "initial_value": self.use_overshoot,
                    "decimal_speed": 1.0,  # Not used for bool
                }
            )

        # Add noise properties for noise operations
        if operation_type in [act_help.CurveOperationType.WAVE_NOISE, act_help.CurveOperationType.PERLIN_NOISE]:
            property_definitions.extend(
                [
                    {
                        "path": "noise_phase",
                        "display_name": "Phase",
                        "type": "float",
                        "range": (-6.28318530718, 6.28318530718),  # 2*pi
                        "initial_value": self.noise_phase,
                        "decimal_speed": 0.1,
                    },
                    {
                        "path": "noise_randomization",
                        "display_name": "Randomization",
                        "type": "float",
                        "range": (0.0, 1.0),
                        "initial_value": self.noise_randomization,
                        "decimal_speed": 0.01,
                    },
                    {
                        "path": "noise_strength",
                        "display_name": "Strength",
                        "type": "float",
                        "range": (0.0, 10.0),
                        "initial_value": self.noise_strength,
                        "decimal_speed": 0.1,
                    },
                    {
                        "path": "noise_scale",
                        "display_name": "Scale",
                        "type": "float",
                        "range": (-10.0, 10.0),
                        "initial_value": self.noise_scale,
                        "decimal_speed": 0.1,
                    },
                ]
            )

        # Update the ScopeGUI with new property definitions
        self._scope_gui.update_property_definitions(property_definitions)

        # Sync current property values to ensure GUI reflects operator state
        self._sync_property_values_to_gui()


# =============================================================================
# REGISTRATION
# =============================================================================


def register():
    """Register all classes and properties."""
    bpy.utils.register_class(AMP_OT_curve_tools)


def unregister():
    """Unregister all classes and properties."""
    bpy.utils.unregister_class(AMP_OT_curve_tools)


if __name__ == "__main__":
    register()
