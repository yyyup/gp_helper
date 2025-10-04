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
from .. import utils
from . import support


from bpy.props import (
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
)
from bpy.types import Operator


class AMP_OT_activate_anim_offset(Operator):
    """Activates Anim Offset without masks"""

    bl_idname = "anim.amp_activate_anim_offset"
    bl_label = "AnimOffset"
    message = "AnimOffset Active"

    # bl_options = {'UNDO_GROUPED'}

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def execute(self, context):

        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        # If there's a mask active, clean it up first since we're activating without mask
        if anim_offset.mask_in_use:
            support.remove_mask(context)
            support.reset_timeline_mask(context)

        anim_offset.user_scene_auto = scene.tool_settings.use_keyframe_insert_auto
        support.store_user_timeline_ranges(context)

        scene.tool_settings.use_keyframe_insert_auto = False

        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(support.magnet_handlers)
            utils.amp_draw_header_handler(action="ADD")
            utils.add_message(self.message)

        context.area.tag_redraw()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

        anim_offset.quick_anim_offset_in_use = True

        return {"FINISHED"}


class AMP_OT_deactivate_anim_offset(Operator):
    """Deactivates Anim Offset"""

    bl_idname = "anim.amp_deactivate_anim_offset"
    bl_label = "AnimOffset off"

    # bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def execute(self, context):
        utils.amp_draw_header_handler(action="REMOVE")

        if support.magnet_handlers in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(support.magnet_handlers)
            utils.remove_message()

        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        if anim_offset.mask_in_use:
            support.remove_mask(context)
            support.reset_timeline_mask(context)

        scene.tool_settings.use_keyframe_insert_auto = anim_offset.user_scene_auto

        if anim_offset.quick_anim_offset_in_use:
            anim_offset.quick_anim_offset_in_use = False

        # bpy.ops.wm.redraw_timer()
        for area in bpy.context.screen.areas:
            area.tag_redraw()
        # context.area.tag_redraw()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        # bpy.data.window_managers['WinMan'].windows.update()
        # bpy.data.window_managers['WinMan'].update_tag()
        return {"FINISHED"}


class AMP_OT_toggle_anim_offset_mask(Operator):
    """Toggles Anim Offset mask on/off"""

    bl_idname = "anim.amp_toggle_anim_offset_mask"
    bl_label = "Toggle AnimOffset Mask"
    bl_options = {"UNDO_GROUPED", "GRAB_CURSOR"}
    message = "AnimOffset Active"

    # Pin positions for mask control
    pin_positions: bpy.props.FloatVectorProperty(
        name="Pin Positions",
        description="Positions of the 4 mask pins (secondary_left, main_left, main_right, secondary_right)",
        size=4,
        default=(0.0, 0.0, 0.0, 0.0),
    )

    # Blend types for GUI pins
    start_blend: bpy.props.EnumProperty(
        name="Start Blend",
        description="Blending type for the start of the range",
        items=[
            ("linear", "Linear", "Linear blend"),
            ("quadratic_in", "Quad In", "Quadratic ease in"),
            ("quadratic_out", "Quad Out", "Quadratic ease out"),
            ("quadratic_in_out", "Quad In/Out", "Quadratic ease in/out"),
            ("cubic_in", "Cubic In", "Cubic ease in"),
            ("cubic_out", "Cubic Out", "Cubic ease out"),
            ("cubic_in_out", "Cubic In/Out", "Cubic ease in/out"),
            ("exponential_in", "Expo In", "Exponential ease in"),
            ("exponential_out", "Expo Out", "Exponential ease out"),
            ("exponential_in_out", "Expo In/Out", "Exponential ease in/out"),
        ],
        default="linear",
    )

    end_blend: bpy.props.EnumProperty(
        name="End Blend",
        description="Blending type for the end of the range",
        items=[
            ("linear", "Linear", "Linear blend"),
            ("quadratic_in", "Quad In", "Quadratic ease in"),
            ("quadratic_out", "Quad Out", "Quadratic ease out"),
            ("quadratic_in_out", "Quad In/Out", "Quadratic ease in/out"),
            ("cubic_in", "Cubic In", "Cubic ease in"),
            ("cubic_out", "Cubic Out", "Cubic ease out"),
            ("cubic_in_out", "Cubic In/Out", "Cubic ease in/out"),
            ("exponential_in", "Expo In", "Exponential ease in"),
            ("exponential_out", "Expo Out", "Exponential ease out"),
            ("exponential_in_out", "Expo In/Out", "Exponential ease in/out"),
        ],
        default="linear",
    )

    # Class variables for modal operation
    _scope_gui = None
    _draw_handler = None
    _is_running = False

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def invoke(self, context, event):
        """Toggle mask on/off - if mask exists, delete it; if not, create it."""
        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        # Check if a mask already exists
        existing_action = bpy.data.actions.get("amp_action")
        if anim_offset.mask_in_use and existing_action:
            # Mask exists - turn it off (delete it)
            bpy.ops.anim.amp_delete_anim_offset_mask()
            return {"FINISHED"}
        elif anim_offset.mask_in_use and not existing_action:
            # mask_in_use is True but no action exists - reset the flag
            anim_offset.mask_in_use = False

        # No mask exists - create one
        if self._is_running:
            self.report({"WARNING"}, "AnimOffset mask is already running")
            return {"CANCELLED"}

        # Initialize and create mask using the existing add_anim_offset_mask logic
        return self._create_mask(context, event)

    def _create_mask(self, context, event):
        """Create a new mask - reuses the logic from add_anim_offset_mask."""
        from ..utils.gui_pins import ScopeGUI

        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        # Initialize AnimOffset if not already active
        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            anim_offset.user_scene_auto = scene.tool_settings.use_keyframe_insert_auto
            support.store_user_timeline_ranges(context)
            bpy.app.handlers.depsgraph_update_post.append(support.magnet_handlers)
            utils.amp_draw_header_handler(action="ADD")
            utils.add_message(self.message)

        scene.tool_settings.use_keyframe_insert_auto = False

        # Ensure AnimOffset is marked as active
        anim_offset.quick_anim_offset_in_use = True

        # Create new blends
        support.add_blends()

        # Determine initial pin positions from selected keyframes
        frame_range = self._get_frame_range_from_selection_or_mask(context)
        if not frame_range:
            # If no selection, center at playhead with 20-frame range
            current_frame = scene.frame_current
            frame_range = (current_frame - 10, current_frame + 10)

        pin_positions = self._get_initial_pin_positions(context, frame_range)
        self.pin_positions = pin_positions

        # Initialize the scope GUI for mask control
        self._scope_gui = ScopeGUI(
            frame_range=(pin_positions[1], pin_positions[2]),  # main_left, main_right
            operation_name="Anim Offset",
            blend_range=max(1, int((pin_positions[3] - pin_positions[0]) / 3)),
            start_blend=self.start_blend,
            end_blend=self.end_blend,
            operation_options=None,  # No operation switching for mask
            factor_value=None,  # No factor for mask
            factor_multiplier=1.0,
            quick_drag=False,
            show_intensity=False,  # Hide intensity handler for AnimOffset mask
        )

        # Set pin positions manually
        if hasattr(self._scope_gui, "pins") and self._scope_gui.pins:
            for i, pin in enumerate(self._scope_gui.pins):
                if i < len(pin_positions):
                    pin.frame = pin_positions[i]

        # Set colors for mask interface
        main_color = (0.1, 0.1, 0.1, 0.8)
        accent_color = (0.8, 0.4, 0.1, 1.0)  # Orange for mask
        self._scope_gui.set_colors(main_color, accent_color)

        # Activate the GUI
        self._scope_gui.activate()

        # Register draw handler
        self._draw_handler = context.space_data.draw_handler_add(
            self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
        )
        # Store the space_data where the handler was added for removal later
        self._handler_space = context.space_data

        # Set initial mask values
        self._update_mask_from_pins(context)

        # Start modal operation
        context.window_manager.modal_handler_add(self)
        self._is_running = True
        self._startup_frames = 10  # Wait 10 frames before checking AnimOffset status

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """Handle modal events for mask manipulation - runs transparently."""
        if not self._scope_gui:
            return {"CANCELLED"}

        # Exit if area or region no longer valid (e.g., area changed)
        if context.area is None or context.region is None:
            self._finish_mask(context, confirmed=False, shutdown=True)
            return {"FINISHED"}

        # If user switched away from Graph Editor or Dope Sheet Editor, shut down mask
        if context.area.type not in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}:
            self._finish_mask(context, confirmed=False, shutdown=True)
            return {"FINISHED"}

        # Check if AnimOffset is still active - if not, shut down
        # Only check after a short delay to ensure AnimOffset is fully activated
        if hasattr(self, "_startup_frames"):
            self._startup_frames -= 1
        else:
            self._startup_frames = 10  # Wait 10 frames before checking status

        if self._startup_frames <= 0:
            anim_offset = context.scene.amp_timeline_tools.anim_offset
            if (
                not anim_offset.quick_anim_offset_in_use
                or support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post
            ):
                self._finish_mask(context, confirmed=True, shutdown=True)
                return {"FINISHED"}

        # Pass through wheel and middle mouse events
        if event.type in {"MIDDLE_MOUSE", "MWHEELUP", "MWHEELDOWN", "WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
            return {"PASS_THROUGH"}

        # Pass through keyboard events that aren't handled by GUI
        if event.type in {"TAB", "SPACE"} or (event.type.startswith("NUMPAD") and event.type != "RET"):
            return {"PASS_THROUGH"}

        # Check if GUI is interacting with mouse events
        is_gui_dragging = hasattr(self._scope_gui, "dragging_element") and self._scope_gui.dragging_element is not None

        # Check if mouse is over GUI elements by checking if any element is hovered
        is_mouse_over_gui = False
        if hasattr(self._scope_gui, "pins") and self._scope_gui.pins:
            for pin in self._scope_gui.pins:
                if hasattr(pin, "is_hovered") and pin.is_hovered:
                    is_mouse_over_gui = True
                    break

        # Also check handlers and other GUI elements
        if not is_mouse_over_gui:
            gui_elements = []
            if hasattr(self._scope_gui, "intensity_handler"):
                gui_elements.append(self._scope_gui.intensity_handler)
            if hasattr(self._scope_gui, "factor_handler"):
                gui_elements.append(self._scope_gui.factor_handler)
            if hasattr(self._scope_gui, "blend_selectors"):
                gui_elements.extend(self._scope_gui.blend_selectors)
            if hasattr(self._scope_gui, "bars"):
                gui_elements.extend(self._scope_gui.bars)

            for element in gui_elements:
                if hasattr(element, "is_hovered") and element.is_hovered:
                    is_mouse_over_gui = True
                    break

        # Update GUI - let it handle its own events
        result = self._scope_gui.update(context, event)

        # Update mask when pins change
        if self._scope_gui.is_active:
            self._update_mask_from_pins(context)

        # Handle mouse events based on GUI interaction
        if event.type == "LEFTMOUSE":
            if is_gui_dragging or is_mouse_over_gui:
                # Block mouse events when GUI is handling them
                return {"RUNNING_MODAL"}
            else:
                # Pass through when not interacting with GUI
                return {"PASS_THROUGH"}

        # Pass through all other events
        return {"PASS_THROUGH"}

    def _get_frame_range_from_selection_or_mask(self, context):
        """Get frame range from selected keyframes or existing mask."""
        # First try selected keyframes
        selected_keyframes = utils.curve.get_selected_keyframes_range_offset(context)
        if selected_keyframes:
            return selected_keyframes

        # Then try existing mask data from the F-curve
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        if anim_offset.mask_in_use:
            # Get range from the mask F-curve instead of timeline ranges
            blends_action = bpy.data.actions.get("amp_action")
            if blends_action:
                blends_curves = list(utils.curve.all_fcurves(blends_action))
                if blends_curves and len(blends_curves) > 0:
                    blend_curve = blends_curves[0]
                    keys = blend_curve.keyframe_points
                    if len(keys) >= 4:
                        # Extract main range from the mask F-curve (keys 1 and 2)
                        main_left = keys[1].co.x
                        main_right = keys[2].co.x
                        return (main_left, main_right)

            # Fallback to anim_offset properties if F-curve data is not available
            reference_frame = anim_offset.reference_frame
            mask_range = anim_offset.ao_mask_range
            return (reference_frame - mask_range, reference_frame + mask_range)

        return None

    def _get_initial_pin_positions(self, context, frame_range):
        """Calculate initial pin positions based on frame range."""
        min_frame, max_frame = frame_range
        center_frame = (min_frame + max_frame) / 2
        range_size = max_frame - min_frame

        # Create reasonable blend margins (10% of range on each side, minimum 2 frames)
        blend_margin = max(2, range_size * 0.1)

        # Pin positions: secondary_left, main_left, main_right, secondary_right
        secondary_left = min_frame - blend_margin
        main_left = min_frame
        main_right = max_frame
        secondary_right = max_frame + blend_margin

        return (secondary_left, main_left, main_right, secondary_right)

    def _update_mask_from_pins(self, context):
        """Update the mask F-curve based on current pin positions."""
        if not self._scope_gui or not hasattr(self._scope_gui, "pins"):
            return

        # Get current pin positions
        pins = self._scope_gui.pins
        if len(pins) < 4:
            return

        pin_positions = [pin.frame for pin in pins]
        self.pin_positions = pin_positions

        # Get blend types from GUI
        gui_values = self._scope_gui.get_values() if hasattr(self._scope_gui, "get_values") else {}
        start_blend = gui_values.get("start_blend", self.start_blend)
        end_blend = gui_values.get("end_blend", self.end_blend)

        # Update operator properties to stay in sync with GUI
        self.start_blend = start_blend
        self.end_blend = end_blend

        # Update the blend values using the pin positions and blend types
        support.set_blend_values_from_pins(context, pin_positions, start_blend, end_blend)

        # Update anim_offset properties based on pins (keep these for internal logic)
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        secondary_left, main_left, main_right, secondary_right = pin_positions

        center_frame = (main_left + main_right) / 2
        mask_range = (main_right - main_left) / 2
        blend_range = max((main_left - secondary_left), (secondary_right - main_right))

        anim_offset.reference_frame = int(center_frame)
        anim_offset.ao_mask_range = int(mask_range)
        anim_offset.ao_blend_range = int(blend_range)

        # Mark mask as in use
        anim_offset.mask_in_use = True

    def _finish_mask(self, context, confirmed=True, shutdown=False):
        """Finish the mask operation."""
        # Clean up draw handler
        if getattr(self, "_draw_handler", None):
            # Remove handler from the stored space_data if available
            handler_space = getattr(self, "_handler_space", None)
            if handler_space is not None:
                handler_space.draw_handler_remove(self._draw_handler, "WINDOW")
            self._draw_handler = None
            # Clear stored handler space
            if hasattr(self, "_handler_space"):
                del self._handler_space

        # Clean up GUI
        if self._scope_gui:
            self._scope_gui.deactivate()
            self._scope_gui = None

        anim_offset = context.scene.amp_timeline_tools.anim_offset

        if confirmed or shutdown:
            # Finalize the mask - keep it active
            anim_offset.mask_in_use = True
            anim_offset.quick_anim_offset_in_use = True

            # Set current frame to center of mask if we have valid pin positions
            if len(self.pin_positions) >= 4:
                center_frame = (self.pin_positions[1] + self.pin_positions[2]) / 2
                context.scene.frame_current = int(center_frame)
        else:
            # This shouldn't happen since we removed cancel options, but keep for safety
            support.remove_mask(context)
            anim_offset.mask_in_use = False

        self._is_running = False
        # Fully deactivate AnimOffset on shutdown (e.g., area change)
        if shutdown:
            # Manually deactivate since context may be invalid for operator call
            utils.amp_draw_header_handler(action="REMOVE")
            if support.magnet_handlers in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(support.magnet_handlers)
                utils.remove_message()
            
            # Clean up anim_offset state
            anim_offset.quick_anim_offset_in_use = False
            if anim_offset.mask_in_use:
                support.remove_mask(context)
                support.reset_timeline_mask(context)
            
            # Restore user settings
            if hasattr(anim_offset, 'user_scene_auto'):
                context.scene.tool_settings.use_keyframe_insert_auto = anim_offset.user_scene_auto
        
        # Safely redraw the UI without error if context.area is None
        try:
            context.area.tag_redraw()
        except Exception:
            for area in bpy.context.screen.areas:
                area.tag_redraw()

    def _draw_callback(self, context):
        """Draw callback for the scope GUI."""
        if self._scope_gui:
            self._scope_gui.draw(context)


class AMP_OT_add_anim_offset_mask(Operator):
    """Adds or modifies Anim Offset mask and activates it using GUI pins"""

    bl_idname = "anim.amp_add_anim_offset_mask"
    bl_label = "AnimOffset Mask"
    bl_options = {"UNDO_GROUPED", "GRAB_CURSOR"}
    message = "AnimOffset Active"

    # Pin positions for mask control
    pin_positions: bpy.props.FloatVectorProperty(
        name="Pin Positions",
        description="Positions of the 4 mask pins (secondary_left, main_left, main_right, secondary_right)",
        size=4,
        default=(0.0, 0.0, 0.0, 0.0),
    )

    # Blend types for GUI pins
    start_blend: bpy.props.EnumProperty(
        name="Start Blend",
        description="Blending type for the start of the range",
        items=[
            ("linear", "Linear", "Linear blend"),
            ("quadratic_in", "Quad In", "Quadratic ease in"),
            ("quadratic_out", "Quad Out", "Quadratic ease out"),
            ("quadratic_in_out", "Quad In/Out", "Quadratic ease in/out"),
            ("cubic_in", "Cubic In", "Cubic ease in"),
            ("cubic_out", "Cubic Out", "Cubic ease out"),
            ("cubic_in_out", "Cubic In/Out", "Cubic ease in/out"),
            ("exponential_in", "Expo In", "Exponential ease in"),
            ("exponential_out", "Expo Out", "Exponential ease out"),
            ("exponential_in_out", "Expo In/Out", "Exponential ease in/out"),
        ],
        default="linear",
    )

    end_blend: bpy.props.EnumProperty(
        name="End Blend",
        description="Blending type for the end of the range",
        items=[
            ("linear", "Linear", "Linear blend"),
            ("quadratic_in", "Quad In", "Quadratic ease in"),
            ("quadratic_out", "Quad Out", "Quadratic ease out"),
            ("quadratic_in_out", "Quad In/Out", "Quadratic ease in/out"),
            ("cubic_in", "Cubic In", "Cubic ease in"),
            ("cubic_out", "Cubic Out", "Cubic ease out"),
            ("cubic_in_out", "Cubic In/Out", "Cubic ease in/out"),
            ("exponential_in", "Expo In", "Exponential ease in"),
            ("exponential_out", "Expo Out", "Exponential ease out"),
            ("exponential_in_out", "Expo In/Out", "Exponential ease in/out"),
        ],
        default="linear",
    )

    # Class variables for modal operation
    _scope_gui = None
    _draw_handler = None
    _is_running = False

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def invoke(self, context, event):
        """Initialize and start the modal mask operator."""
        from ..utils.gui_pins import ScopeGUI

        if self._is_running:
            self.report({"WARNING"}, "AnimOffset mask is already running")
            return {"CANCELLED"}

        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        # Check if a mask already exists - if so, don't create a new one
        existing_action = bpy.data.actions.get("amp_action")
        if anim_offset.mask_in_use and existing_action:
            # A mask already exists - don't create a new one
            self.report({"INFO"}, "AnimOffset mask already exists - use modify or delete first")
            return {"CANCELLED"}
        elif anim_offset.mask_in_use and not existing_action:
            # mask_in_use is True but no action exists - reset the flag
            anim_offset.mask_in_use = False

        # Initialize AnimOffset if not already active
        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            anim_offset.user_scene_auto = scene.tool_settings.use_keyframe_insert_auto
            support.store_user_timeline_ranges(context)
            bpy.app.handlers.depsgraph_update_post.append(support.magnet_handlers)
            utils.amp_draw_header_handler(action="ADD")
            utils.add_message(self.message)

        scene.tool_settings.use_keyframe_insert_auto = False

        # Ensure AnimOffset is marked as active
        anim_offset.quick_anim_offset_in_use = True

        # Create new blends since we've confirmed no mask exists
        support.add_blends()

        # Determine initial pin positions from selected keyframes
        frame_range = self._get_frame_range_from_selection_or_mask(context)
        if not frame_range:
            # If no selection, center at playhead with 20-frame range
            current_frame = scene.frame_current
            frame_range = (current_frame - 10, current_frame + 10)

        pin_positions = self._get_initial_pin_positions(context, frame_range)
        self.pin_positions = pin_positions

        # Initialize the scope GUI for mask control
        self._scope_gui = ScopeGUI(
            frame_range=(pin_positions[1], pin_positions[2]),  # main_left, main_right
            operation_name="Anim Offset",
            blend_range=max(1, int((pin_positions[3] - pin_positions[0]) / 3)),
            start_blend=self.start_blend,
            end_blend=self.end_blend,
            operation_options=None,  # No operation switching for mask
            factor_value=None,  # No factor for mask
            factor_multiplier=1.0,
            quick_drag=False,
            show_intensity=False,  # Hide intensity handler for AnimOffset mask
        )

        # Set pin positions manually
        if hasattr(self._scope_gui, "pins") and self._scope_gui.pins:
            for i, pin in enumerate(self._scope_gui.pins):
                if i < len(pin_positions):
                    pin.frame = pin_positions[i]

        # Set colors for mask interface
        main_color = (0.1, 0.1, 0.1, 0.8)
        accent_color = (0.8, 0.4, 0.1, 1.0)  # Orange for mask
        self._scope_gui.set_colors(main_color, accent_color)

        # Activate the GUI
        self._scope_gui.activate()

        # Register draw handler
        self._draw_handler = context.space_data.draw_handler_add(
            self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
        )

        # Set initial mask values
        self._update_mask_from_pins(context)

        # Start modal operation
        context.window_manager.modal_handler_add(self)
        self._is_running = True
        self._startup_frames = 10  # Wait 10 frames before checking AnimOffset status

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """Handle modal events for mask manipulation - runs transparently."""
        if not self._scope_gui:
            return {"CANCELLED"}

        # Check if AnimOffset is still active - if not, shut down
        # Only check after a short delay to ensure AnimOffset is fully activated
        if hasattr(self, "_startup_frames"):
            self._startup_frames -= 1
        else:
            self._startup_frames = 10  # Wait 10 frames before checking status

        if self._startup_frames <= 0:
            anim_offset = context.scene.amp_timeline_tools.anim_offset
            if (
                not anim_offset.quick_anim_offset_in_use
                or support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post
            ):
                self._finish_mask(context, confirmed=True, shutdown=True)
                return {"FINISHED"}

        # Pass through wheel and middle mouse events
        if event.type in {"MIDDLE_MOUSE", "MWHEELUP", "MWHEELDOWN", "WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
            return {"PASS_THROUGH"}

        # Pass through keyboard events that aren't handled by GUI
        if event.type in {"TAB", "SPACE"} or (event.type.startswith("NUMPAD") and event.type != "RET"):
            return {"PASS_THROUGH"}

        # Check if GUI is interacting with mouse events
        is_gui_dragging = hasattr(self._scope_gui, "dragging_element") and self._scope_gui.dragging_element is not None

        # Check if mouse is over GUI elements by checking if any element is hovered
        is_mouse_over_gui = False
        if hasattr(self._scope_gui, "pins") and self._scope_gui.pins:
            for pin in self._scope_gui.pins:
                if hasattr(pin, "is_hovered") and pin.is_hovered:
                    is_mouse_over_gui = True
                    break

        # Also check handlers and other GUI elements
        if not is_mouse_over_gui:
            gui_elements = []
            if hasattr(self._scope_gui, "intensity_handler"):
                gui_elements.append(self._scope_gui.intensity_handler)
            if hasattr(self._scope_gui, "factor_handler"):
                gui_elements.append(self._scope_gui.factor_handler)
            if hasattr(self._scope_gui, "blend_selectors"):
                gui_elements.extend(self._scope_gui.blend_selectors)
            if hasattr(self._scope_gui, "bars"):
                gui_elements.extend(self._scope_gui.bars)

            for element in gui_elements:
                if hasattr(element, "is_hovered") and element.is_hovered:
                    is_mouse_over_gui = True
                    break

        # Update GUI - let it handle its own events
        result = self._scope_gui.update(context, event)

        # Update mask when pins change
        if self._scope_gui.is_active:
            self._update_mask_from_pins(context)

        # Handle mouse events based on GUI interaction
        if event.type == "LEFTMOUSE":
            if is_gui_dragging or is_mouse_over_gui:
                # Block mouse events when GUI is handling them
                return {"RUNNING_MODAL"}
            else:
                # Pass through when not interacting with GUI
                return {"PASS_THROUGH"}

        # Pass through all other events
        return {"PASS_THROUGH"}

    def _get_frame_range_from_selection_or_mask(self, context):
        """Get frame range from selected keyframes or existing mask."""
        # First try selected keyframes
        selected_keyframes = utils.curve.get_selected_keyframes_range_offset(context)
        if selected_keyframes:
            return selected_keyframes

        # Then try existing mask data from the F-curve
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        if anim_offset.mask_in_use:
            # Get range from the mask F-curve instead of timeline ranges
            blends_action = bpy.data.actions.get("amp_action")
            if blends_action:
                blends_curves = list(utils.curve.all_fcurves(blends_action))
                if blends_curves and len(blends_curves) > 0:
                    blend_curve = blends_curves[0]
                    keys = blend_curve.keyframe_points
                    if len(keys) >= 4:
                        # Extract main range from the mask F-curve (keys 1 and 2)
                        main_left = keys[1].co.x
                        main_right = keys[2].co.x
                        return (main_left, main_right)

            # Fallback to anim_offset properties if F-curve data is not available
            reference_frame = anim_offset.reference_frame
            mask_range = anim_offset.ao_mask_range
            return (reference_frame - mask_range, reference_frame + mask_range)

        return None

    def _get_initial_pin_positions(self, context, frame_range):
        """Calculate initial pin positions based on frame range."""
        min_frame, max_frame = frame_range
        center_frame = (min_frame + max_frame) / 2
        range_size = max_frame - min_frame

        # Create reasonable blend margins (10% of range on each side, minimum 2 frames)
        blend_margin = max(2, range_size * 0.1)

        # Pin positions: secondary_left, main_left, main_right, secondary_right
        secondary_left = min_frame - blend_margin
        main_left = min_frame
        main_right = max_frame
        secondary_right = max_frame + blend_margin

        return (secondary_left, main_left, main_right, secondary_right)

    def _update_mask_from_pins(self, context):
        """Update the mask F-curve based on current pin positions."""
        if not self._scope_gui or not hasattr(self._scope_gui, "pins"):
            return

        # Get current pin positions
        pins = self._scope_gui.pins
        if len(pins) < 4:
            return

        pin_positions = [pin.frame for pin in pins]
        self.pin_positions = pin_positions

        # Get blend types from GUI
        gui_values = self._scope_gui.get_values() if hasattr(self._scope_gui, "get_values") else {}
        start_blend = gui_values.get("start_blend", self.start_blend)
        end_blend = gui_values.get("end_blend", self.end_blend)

        # Update operator properties to stay in sync with GUI
        self.start_blend = start_blend
        self.end_blend = end_blend

        # Update the blend values using the pin positions and blend types
        support.set_blend_values_from_pins(context, pin_positions, start_blend, end_blend)

        # Update anim_offset properties based on pins (keep these for internal logic)
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        secondary_left, main_left, main_right, secondary_right = pin_positions

        center_frame = (main_left + main_right) / 2
        mask_range = (main_right - main_left) / 2
        blend_range = max((main_left - secondary_left), (secondary_right - main_right))

        anim_offset.reference_frame = int(center_frame)
        anim_offset.ao_mask_range = int(mask_range)
        anim_offset.ao_blend_range = int(blend_range)

        # Mark mask as in use
        anim_offset.mask_in_use = True

    def _finish_mask(self, context, confirmed=True, shutdown=False):
        """Finish the mask operation."""
        # Clean up draw handler
        if self._draw_handler:
            context.space_data.draw_handler_remove(self._draw_handler, "WINDOW")
            self._draw_handler = None

        # Clean up GUI
        if self._scope_gui:
            self._scope_gui.deactivate()
            self._scope_gui = None

        anim_offset = context.scene.amp_timeline_tools.anim_offset

        if confirmed or shutdown:
            # Finalize the mask - keep it active
            anim_offset.mask_in_use = True
            anim_offset.quick_anim_offset_in_use = True

            # Set current frame to center of mask if we have valid pin positions
            if len(self.pin_positions) >= 4:
                center_frame = (self.pin_positions[1] + self.pin_positions[2]) / 2
                context.scene.frame_current = int(center_frame)
        else:
            # This shouldn't happen since we removed cancel options, but keep for safety
            support.remove_mask(context)
            anim_offset.mask_in_use = False

        self._is_running = False
        # Fully deactivate AnimOffset on shutdown (e.g., area change)
        if shutdown:
            bpy.ops.anim.amp_deactivate_anim_offset()
        # Safely redraw the UI without error if context.area is None
        try:
            context.area.tag_redraw()
        except Exception:
            for area in bpy.context.screen.areas:
                area.tag_redraw()

    def _draw_callback(self, context):
        """Draw callback for the scope GUI."""
        if self._scope_gui:
            self._scope_gui.draw(context)


class AMP_OT_add_anim_offset_mask_legacy(Operator):
    """Adds or modifies Anim Offset mask and activates it"""

    bl_idname = "anim.amp_add_anim_offset_mask_legacy"
    bl_label = "AnimOffset Mask (Legacy)"
    bl_options = {"UNDO_GROUPED"}
    message = "AnimOffset Active"

    sticky: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def margin_blend_info(self, context, side):
        # status bar info when the blends are being modified
        margin = None
        blend = None

        if side == "Left":
            blend = context.scene.frame_preview_start
            margin = context.scene.frame_start
        elif side == "Right":
            blend = context.scene.frame_preview_end
            margin = context.scene.frame_end

        margin_info = f"{side} Margin: {margin}     "
        blend_info = f"{side} Blend: {blend}     "

        if margin == blend:
            return margin_info
        elif side == "Left":
            return margin_info + blend_info
        elif side == "Right":
            return blend_info + margin_info

    def finish_mask(self, context):
        context.window.cursor_set("DEFAULT")
        context.window.workspace.status_text_set(None)
        context.scene.amp_timeline_tools.anim_offset.mask_in_use = True
        context.scene.amp_timeline_tools.anim_offset.quick_anim_offset_in_use = True
        context.area.tag_redraw()
        # bpy.ops.wm.redraw_timer(type='DRAW', iterations=1)

    def constraint(self, limit, side, frame, gap=0):
        # Use to limit the mask margins and blends
        condition = None
        n = 0
        if side == "L":
            n = 1
            condition = frame > limit + gap
        if side == "R":
            n = -1
            condition = frame < limit - gap

        if condition:
            return frame
        else:
            return limit + (gap * n)

    def info(self, context, event):
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        if anim_offset.mask_in_use:
            left_mouse_info = "Move margins"
            ctrl_info = "+ CTRL: Move blends       "
            alt_info = "+ ALT: Move range       "
        else:
            left_mouse_info = "Create mask"
            ctrl_info = ""
            alt_info = ""

        if event.shift:
            context.window.workspace.status_text_set(
                f"MOUSE-LB: {left_mouse_info}       " f"{ctrl_info}" f"{alt_info}" f"MOUSE-RB: Exit masking mode"
            )
            if event.ctrl:
                context.window.workspace.status_text_set(
                    f"MOUSE-LB: Move blends       " f"ALT: Move range       " f"MOUSE-RB: Exit masking mode"
                )
            if event.alt:
                context.window.workspace.status_text_set(
                    f"MOUSE-LB: Move range       " f"CTRL: Move blends       " f"MOUSE-RB: Exit masking mode"
                )

        elif event.ctrl:
            context.window.workspace.status_text_set(
                f"MOUSE-LB: Move blends       " f"+ SHIFT: Persistent masking       " f"MOUSE-RB: Exit masking mode"
            )
        elif event.alt:
            context.window.workspace.status_text_set(
                f"MOUSE-LB: Move range       " f"+ SHIFT: Persistent masking       " f"MOUSE-RB: Exit masking mode"
            )
        else:
            context.window.workspace.status_text_set(
                f"MOUSE-LB: {left_mouse_info}       "
                f"+ SHIFT: Persistent masking       "
                f"{ctrl_info}"
                f"{alt_info}"
                f"MOUSE-RB: Exit masking mode"
            )

    def modal(self, context, event):
        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        x = event.mouse_region_x
        y = event.mouse_region_y
        co = bpy.context.region.view2d.region_to_view(x, y)
        frame = int(co[0])

        context.window.cursor_set("SCROLL_X")

        # info for the status bar
        self.info(context, event)

        # if not self.sticky:
        if self.created and not event.shift and not event.alt and not event.ctrl and not self.sticky:
            # if there are not modifier keys leaves msking
            self.finish_mask(context)
            return {"FINISHED"}

        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                # ------------- setup ---------------
                self.leftmouse = True
                self.init_mouse_x = event.mouse_x
                self.leftmouse_frame = frame
                self.delta_start = scene.frame_start - scene.frame_preview_start
                self.delta_end = scene.frame_preview_end - scene.frame_end
                self.end_distance = abs(self.leftmouse_frame - scene.frame_end)
                self.start_distance = abs(self.leftmouse_frame - scene.frame_start)
                self.init_preview_start = scene.frame_preview_start
                self.init_start = scene.frame_start
                self.init_end = scene.frame_end
                self.init_preview_end = scene.frame_preview_end
                # anim_offset.mask_in_use = True

            elif event.value == "RELEASE":
                # ----------- center cursor ----------
                start = scene.frame_start
                end = scene.frame_end
                scene.frame_current = int((end + start) / 2)

                self.leftmouse = False
                self.created = True
                anim_offset.mask_in_use = True

        elif event.type == "MOUSEMOVE":

            anim_offset = scene.amp_timeline_tools.anim_offset

            if not anim_offset.mask_in_use:
                # ------------ fill timeline -----------
                scene.use_preview_range = True
                scene.frame_start = -100
                scene.frame_end = -100
                scene.frame_preview_start = -100
                scene.frame_preview_end = -100

            if self.leftmouse:
                if anim_offset.mask_in_use and scene.frame_start != scene.frame_end:
                    if event.ctrl:
                        # ----------- blends ------------
                        if self.end_distance < self.start_distance:
                            scene.frame_preview_end = self.constraint(scene.frame_end, "L", frame)
                            context.window.workspace.status_text_set(f"Right Blend: {scene.frame_preview_end}")
                        else:
                            scene.frame_preview_start = self.constraint(scene.frame_start, "R", frame)
                            context.window.workspace.status_text_set(f"Left Blend: {scene.frame_preview_start}     ")

                        support.set_blend_values(context)

                    elif event.alt:
                        # -------------- Move range -------------
                        left_info = self.margin_blend_info(context, "Left")
                        right_info = self.margin_blend_info(context, "Right")
                        context.window.workspace.status_text_set(left_info + right_info)

                        distance = frame - self.leftmouse_frame
                        scene.frame_preview_start = self.init_preview_start + distance
                        scene.frame_start = self.init_start + distance
                        scene.frame_end = self.init_end + distance
                        scene.frame_preview_end = self.init_preview_end + distance
                        support.set_blend_values(context)

                    else:
                        # -------------- Move margins -------------
                        end_distance = abs(self.leftmouse_frame - scene.frame_end)
                        start_distance = abs(self.leftmouse_frame - scene.frame_start)

                        if end_distance < start_distance:
                            scene.frame_end = self.constraint(scene.frame_start, "L", frame, gap=1)
                            scene.frame_preview_end = scene.frame_end + self.delta_end
                            info = self.margin_blend_info(context, "Right")
                            context.window.workspace.status_text_set(info)
                        else:
                            scene.frame_start = self.constraint(scene.frame_end, "R", frame, gap=1)
                            scene.frame_preview_start = scene.frame_start - self.delta_start
                            info = self.margin_blend_info(context, "Left")
                            context.window.workspace.status_text_set(info)

                        support.set_blend_values(context)

                else:
                    # --------------- Add mask ----------------
                    context.window.workspace.status_text_set(
                        f"Left Margin: {scene.frame_start}     " f"Right Margin: {scene.frame_end}     "
                    )
                    direction = None
                    if event.mouse_x > self.init_mouse_x:
                        direction = "R"
                    elif event.mouse_x < self.init_mouse_x:
                        direction = "L"

                    if direction == "R":
                        scene.frame_end = frame
                        scene.frame_preview_end = frame

                        scene.frame_start = self.leftmouse_frame
                        scene.frame_preview_start = self.leftmouse_frame

                    elif direction == "L":
                        scene.frame_start = frame
                        scene.frame_preview_start = frame

                        scene.frame_end = self.leftmouse_frame
                        scene.frame_preview_end = self.leftmouse_frame

                    support.set_blend_values(context)

        elif event.type in {"RIGHTMOUSE", "ESC"}:
            self.finish_mask(context)
            return {"CANCELLED"}

        elif event.type in {"MIDDLEMOUSE", "RET"}:
            self.finish_mask(context)
            return {"FINISHED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        scene = context.scene
        anim_offset = scene.amp_timeline_tools.anim_offset

        self.leftmouse = False
        self.created = False

        if support.magnet_handlers not in bpy.app.handlers.depsgraph_update_post:
            anim_offset.user_scene_auto = scene.tool_settings.use_keyframe_insert_auto
            support.store_user_timeline_ranges(context)
            bpy.app.handlers.depsgraph_update_post.append(support.magnet_handlers)
            # utils.set_bar_color()
            utils.amp_draw_header_handler(action="ADD")
            utils.add_message(self.message)

        # Determine if keyframes are selected and adjust mask accordingly
        selected_keyframes = utils.curve.get_selected_keyframes_range_offset(context)

        if selected_keyframes and not self.sticky:
            min_frame, max_frame = map(int, selected_keyframes)

            self.leftmouse = False
            self.created = True

            anim_offset.mask_in_use = True

            scene.frame_current = int(
                context.active_object.animation_data.nla_tweak_strip_time_to_scene(((min_frame + max_frame) / 2))
            )
            anim_offset.reference_frame = int(((min_frame + max_frame) / 2))
            anim_offset.ao_mask_range = int((max_frame - min_frame) / 2)

            scene.use_preview_range = True
            scene.frame_preview_start, scene.frame_preview_end = min_frame, max_frame

        scene.tool_settings.use_keyframe_insert_auto = False

        support.add_blends()

        context.window_manager.modal_handler_add(self)

        if selected_keyframes and not self.sticky:

            support.set_blend_values(context)
            self.finish_mask(context)
            anim_offset.mask_in_use = True
            self.created = True

        return {"RUNNING_MODAL"}


class AMP_OT_delete_anim_offset_mask(Operator):
    """Deletes Anim Offset mask and deactivates it"""

    bl_idname = "anim.amp_delete_anim_offset_mask"
    bl_label = "AnimOffset Mask off"

    # bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def execute(self, context):
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        utils.amp_draw_header_handler(action="REMOVE")
        anim_offset.quick_anim_offset_in_use = False

        # Let the deactivate operator handle all cleanup properly
        bpy.ops.anim.amp_deactivate_anim_offset()
        return {"FINISHED"}


class AMP_OT_anim_offset_settings(Operator):
    """Shows global options for Anim Offset"""

    bl_idname = "anim.amp_anim_offset_settings"
    bl_label = "Anim Offset Settings"
    # bl_options = {'REGISTER'}

    slot_index: IntProperty()

    @classmethod
    def poll(cls, context):
        return support.poll(context)

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=200)

    def draw(self, context):
        anim_offset = context.scene.amp_timeline_tools.anim_offset
        mask_in_use = context.scene.amp_timeline_tools.anim_offset.mask_in_use

        layout = self.layout

        layout.label(text="Settings")
        layout.separator()
        if not mask_in_use:
            layout.active = False

        #

        # layout.prop(anim_offset, 'end_on_release', text='masking ends on mouse release')
        # layout.prop(anim_offset, 'fast_mask', text='Fast offset calculation')
        # if context.area.type != 'VIEW_3D':

        #

        layout.prop(anim_offset, "insert_outside_keys", text="Auto Key outside margins")
        layout.separator()

        #

        layout.label(text="Mask blend interpolation")
        row = layout.row(align=True)
        row.prop(anim_offset, "easing", text="", icon_only=False)
        row.prop(anim_offset, "interp", text="", expand=True)
        # layout.prop(amp_timeline_tools.amp_anim_offset, 'use_markers', text='Use Markers')


classes = (
    # AMP_OT_modal_test,
    AMP_OT_toggle_anim_offset_mask,
    AMP_OT_add_anim_offset_mask,
    AMP_OT_add_anim_offset_mask_legacy,
    AMP_OT_activate_anim_offset,
    AMP_OT_deactivate_anim_offset,
    AMP_OT_delete_anim_offset_mask,
    AMP_OT_anim_offset_settings,
)
