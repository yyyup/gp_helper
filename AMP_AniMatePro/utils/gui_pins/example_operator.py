"""
Example operator demonstrating the Enhanced ScopeGUI system usage.

This operator shows how to integrate the completely refactored ScopeGUI into a Blender operator
for creating interactive scope-based animation tools with the new enhanced drag system.

New Features in Enhanced ScopeGUI:
- Bar Level Positioning: Outer bar (moves all pins) at level 6, Main bar (moves main pins) at level 7
- Enhanced Drag System: Hover highlighting, cursor hiding, central overlay for options
- Central Overlay: Displays options/percentages in editor center during drag
- Interactive Navigation: Drag up/down to navigate through options with boundary constraints
- Blend Terminology: Updated from "decay" to "blend" throughout the system
- Visual Feedback: Improved hover opacity and three-tier opacity system for bars

Enhanced Drag Interactions:
- Intensity Handler: Shows 0-100% values in central overlay during drag
- Blend Selectors: Shows all BlendType enum values in central overlay during drag
- All Elements: Highlight on hover to indicate interactivity
- Cursor Management: Automatically hidden during drag operations and restored after

Quick Drag Mode:
- When quick_drag=True, the factor handler starts dragging immediately on mouse movement
- No need to click first - just move the mouse to adjust the factor value
- Left mouse button click stops quick drag and switches to normal interaction mode
- Enter key confirms and finishes the operator
- Escape key cancels the operator

Usage Example:
    bpy.ops.anim.amp_scope_gui_example(start_frame=1, end_frame=100, operation_name="Enhanced Scope Example", blend_range=10, intensity_multiplier=1.0, use_factor=True, factor_value=0.0, factor_multiplier=1.0, quick_drag=True)
"""

import bpy
from bpy.types import Operator
from ..gui_pins import ScopeGUI, BlendType
from .. import get_prefs


class AMP_OT_scope_gui_example(Operator):
    """
    Example operator using the Enhanced ScopeGUI system.

    Demonstrates all new features including:
    - Enhanced drag system with central overlay
    - Bar level positioning (outer bar at level 6, main bar at level 7)
    - Hover highlighting and cursor management
    - Blend terminology (updated from decay)
    - Interactive option navigation during drag
    - Quick drag mode for immediate factor adjustment

    Quick Drag Mode:
    - When quick_drag=True, factor dragging starts immediately on mouse movement
    - No mouse click required to start dragging
    - Left mouse button stops quick drag and enables normal interaction
    - Enter confirms the operation, Escape cancels

    The ScopeGUI provides 4 pins (2 main, 2 secondary), intensity control,
    and blend type selectors with enhanced visual feedback.
    """

    bl_idname = "anim.amp_scope_gui_example"
    bl_label = "Enhanced Scope GUI Example"
    bl_description = "Demonstrates the enhanced ScopeGUI with central overlay, hover highlighting, improved drag interactions, and Factor handler"
    bl_options = {"REGISTER", "UNDO", "GRAB_CURSOR"}

    # Properties for the enhanced scope GUI
    start_frame: bpy.props.IntProperty(
        name="Start Frame",
        description="Starting frame for the scope range (main pins will be positioned here)",
        default=1,
    )

    end_frame: bpy.props.IntProperty(
        name="End Frame",
        description="Ending frame for the scope range (main pins will be positioned here)",
        default=100,
    )

    operation_name: bpy.props.StringProperty(
        name="Operation Name",
        description="Name displayed in the operation box (level 4) during interaction",
        default="Enhanced Scope Example",
    )

    blend_range: bpy.props.IntProperty(
        name="Blend Range",
        description="Distance in frames for secondary pins from main pins (creates blending falloff)",
        default=10,
        min=1,
    )

    # Example property values for PropertyBox demonstration
    example_int_value: bpy.props.IntProperty(
        name="Example Int",
        description="Example integer property for PropertyBox demonstration",
        default=50,
        min=0,
        max=100,
    )

    example_float_value: bpy.props.FloatProperty(
        name="Example Float",
        description="Example float property for PropertyBox demonstration",
        default=1.5,
        min=0.0,
        max=10.0,
    )

    example_bool_value: bpy.props.BoolProperty(
        name="Example Bool",
        description="Example boolean property for PropertyBox demonstration",
        default=True,
    )

    # Factor properties for Factor handler demonstration
    factor_value: bpy.props.FloatProperty(
        name="Factor Value",
        description="Factor value for the Factor handler demonstration (range depends on guipins_overshoot preference)",
        default=0.0,
        min=-1.0,
        max=1.0,
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

    # Class variables for modal operation
    _scope_gui = None
    _draw_handler = None
    _is_running = False

    @classmethod
    def poll(cls, context):
        """Check if the operator can be executed."""
        return context.space_data and context.space_data.type in {"GRAPH_EDITOR", "DOPESHEET_EDITOR"}

    def invoke(self, context, event):
        """
        Initialize and start the enhanced modal operator.

        Creates a ScopeGUI instance with the new enhanced drag system,
        sets up color preferences, and activates the interactive interface.

        Returns:
            {"RUNNING_MODAL"}: Modal operator is active
            {"CANCELLED"}: Operator could not start (already running)
        """
        if self._is_running:
            self.report({"WARNING"}, "Enhanced Scope GUI Example is already running")
            return {"CANCELLED"}

        # Use operator arguments for frame range (don't override with scene values)
        # Only use scene defaults if the operator was called with default values
        scene = context.scene
        if self.start_frame == 1 and self.end_frame == 100:
            # If using defaults, use scene frame range
            self.start_frame = scene.frame_start
            self.end_frame = scene.frame_end

        # Define property boxes for demonstration
        property_definitions = [
            {
                "path": "example_int_value",
                "display_name": "Int Property",
                "type": "int",
                "range": (0, 100),
                "initial_value": self.example_int_value,
                "decimal_speed": 1.0,
            },
            {
                "path": "example_float_value",
                "display_name": "Float Property",
                "type": "float",
                "range": (0.0, 10.0),
                "initial_value": self.example_float_value,
                "decimal_speed": 0.1,
            },
            {
                "path": "example_bool_value",
                "display_name": "Bool Property",
                "type": "bool",
                "range": None,  # Not used for bool
                "initial_value": self.example_bool_value,
                "decimal_speed": 1.0,  # Not used for bool
            },
        ]

        # Initialize the enhanced scope GUI with new drag system
        self._scope_gui = ScopeGUI(
            frame_range=(self.start_frame, self.end_frame),
            operation_name=self.operation_name,
            blend_range=self.blend_range,
            start_blend=BlendType.LINEAR,
            end_blend=BlendType.LINEAR,
            property_definitions=property_definitions,
            factor_value=self.factor_value if self.use_factor else None,
            factor_multiplier=self.factor_multiplier,
            quick_drag=self.quick_drag,
        )

        # Set custom colors from preferences if available
        prefs = get_prefs()
        if hasattr(prefs, "tw_pin_color"):  # Reuse timewarper colors for consistency
            # main_color = (*prefs.tw_pin_color[:3], 0.8)
            # accent_color = (*prefs.tw_pin_color[:3], 1.0)
            main_color = (0.05, 0.05, 0.05, 0.75)
            accent_color = (1.0, 0.5, 0.0, 1.0)
            self._scope_gui.set_colors(main_color, accent_color)

        # Activate the enhanced GUI (enables hover detection and drawing)
        self._scope_gui.activate()

        # Register draw handler for rendering the GUI
        self._draw_handler = context.space_data.draw_handler_add(
            self._draw_callback, (context,), "WINDOW", "POST_PIXEL"
        )

        # Start modal operation
        context.window_manager.modal_handler_add(self)
        self._is_running = True

        # If quick_drag is enabled, warp mouse to factor handler position
        if self.quick_drag and self._scope_gui and self._scope_gui.factor_handler:
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

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """
        Handle modal events for the enhanced drag system.

        The enhanced ScopeGUI automatically handles:
        - Hover highlighting for all interactive elements
        - Cursor hiding during drag operations
        - Central overlay display with option navigation
        - Drag up/down to change values with boundary constraints

        Quick Drag Mode:
        - When quick_drag is True, factor dragging starts immediately on mouse movement
        - LMB click stops quick drag and allows normal interaction
        - Enter confirms and finishes the operator
        - ESC cancels the operator

        Args:
            context: Blender context
            event: Input event (mouse, keyboard)

        Returns:
            {"RUNNING_MODAL"}: Continue modal operation
            {"FINISHED"}: Operation completed
            {"CANCELLED"}: Operation cancelled
            {"PASS_THROUGH"}: Pass event to other handlers
        """
        if not self._is_running or not self._scope_gui:
            return {"CANCELLED"}

        # Handle exit conditions
        if event.type in {"ESC", "RIGHTMOUSE"}:
            # Ensure cursor is restored when cancelling
            if self._scope_gui and hasattr(self._scope_gui, "cursor_manager"):
                self._scope_gui.cursor_manager.restore_cursor(context)
            return self._finish(context)

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

        # Handle enhanced scope GUI updates (includes all new drag features)
        if event.type in {"MOUSEMOVE", "LEFTMOUSE"}:
            result = self._scope_gui.update(context, event)

            if result:
                # Process the updated values (includes new blend terminology)
                self._process_scope_values(context, result)

        # In normal mode (not quick drag), handle mouse press events
        if not self.quick_drag and event.type in {"LEFTMOUSE", "RIGHTMOUSE"} and event.value == "PRESS":
            return {"RUNNING_MODAL"}

        # Handle confirmation
        if event.type in {"RET", "NUMPAD_ENTER"}:
            return self._finish(context, confirmed=True)

        # Redraw the area to show updates
        if context.area:
            context.area.tag_redraw()

        return {"PASS_THROUGH"}

    def _draw_callback(self, context):
        """Draw callback for the scope GUI."""
        if self._scope_gui:
            self._scope_gui.draw(context)

    def _process_scope_values(self, context, values):
        """
        Process the updated values from the enhanced scope GUI.

        This demonstrates how to access all the enhanced GUI values including
        the new blend terminology and improved data structure.

        Args:
            context: Blender context
            values (dict): Contains all scope values:
                - pin_positions: All 4 pin frame positions
                - pin_influences: Calculated influence values for secondary pins
                - intensity: Percentage value (0-100, or higher with multiplier)
                - start_blend: Left blend selector value (BlendType enum)
                - end_blend: Right blend selector value (BlendType enum)
                - main_pins: Main pin positions [left, right]
                - secondary_pins: Secondary pin positions [left, right]
                - properties: Dictionary of property values
                - factor: Factor value (range depends on guipins_overshoot preference) if factor handler is enabled
                - effective_factor: Factor * multiplier if factor handler is enabled
                - factor_multiplier: Factor multiplier if factor handler is enabled
        """
        # Sync property values back to operator properties
        properties = values.get("properties", {})
        if "example_int_value" in properties:
            self.example_int_value = properties["example_int_value"]
        if "example_float_value" in properties:
            self.example_float_value = properties["example_float_value"]
        if "example_bool_value" in properties:
            self.example_bool_value = properties["example_bool_value"]

        # Sync factor values back to operator properties
        if "factor" in values:
            self.factor_value = values["factor"]
        if "factor_multiplier" in values:
            self.factor_multiplier = values["factor_multiplier"]

        # Example: Print the current values to console (useful for debugging)
        print("Enhanced Scope GUI Values:")
        print(f"  Pin Positions: {values['pin_positions']}")
        print(f"  Pin Influences: {values['pin_influences']}")
        print(f"  Intensity: {values['intensity']:.1f}%")
        print(f"  Start Blend Type: {values['start_blend']}")  # Updated terminology
        print(f"  End Blend Type: {values['end_blend']}")  # Updated terminology
        print(f"  Main Pins Range: {values['main_pins']}")
        print(f"  Secondary Pins Range: {values['secondary_pins']}")
        print(f"  Properties: {properties}")

        # Print factor values if available
        if "factor" in values:
            print(f"  Factor: {values['factor']:.2f}")
            print(f"  Effective Factor: {values['effective_factor']:.2f}")
            print(f"  Factor Multiplier: {values['factor_multiplier']:.1f}x")

        # Example: Real-time processing of values for animation tools
        # This is where you would implement your specific animation logic
        # based on the enhanced scope system with the new drag interactions
        pass

    def _finish(self, context, confirmed=False):
        """Finish the modal operation."""
        # Clean up
        if self._draw_handler:
            context.space_data.draw_handler_remove(self._draw_handler, "WINDOW")
            self._draw_handler = None

        if self._scope_gui:
            # Always ensure cursor is restored when finishing/cancelling
            self._scope_gui.deactivate(context)

            if confirmed:
                # Get final values and apply them
                final_values = self._scope_gui.get_values()
                self._apply_final_values(context, final_values)
                self.report({"INFO"}, f"Applied {self.operation_name}")
            else:
                self.report({"INFO"}, f"Cancelled {self.operation_name}")

        self._scope_gui = None
        self._is_running = False

        # Ensure cursor is always visible when exiting (safety measure)
        try:
            context.window.cursor_modal_restore()
        except:
            # Silent fail - cursor might already be restored
            pass

        # Redraw the area
        if context.area:
            context.area.tag_redraw()

        return {"FINISHED"}

    def _apply_final_values(self, context, values):
        """Apply the final scope values to the animation data."""
        # This is where you would implement the actual animation modification
        # based on the final scope values

        print("Final Scope Values Applied:")
        print(f"  Main Range: {values['main_pins'][0]:.1f} to {values['main_pins'][1]:.1f}")
        print(f"  Blend Range: {values['secondary_pins'][0]:.1f} to {values['secondary_pins'][1]:.1f}")
        print(f"  Intensity: {values['intensity']:.1f}%")
        print(f"  Blend Types: {values['start_blend']} -> {values['end_blend']}")

        # Print factor values if available
        if "factor" in values:
            print(f"  Factor: {values['factor']:.2f}")
            print(f"  Effective Factor: {values['effective_factor']:.2f}")
            print(f"  Factor Multiplier: {values['factor_multiplier']:.1f}x")

        # Example implementation could include:
        # - Modifying keyframe values based on the scope
        # - Applying curves with the specified decay types
        # - Scaling effects based on the intensity
        # - Using the pin influences for gradual falloff
        pass

    def cancel(self, context):
        """Cancel the modal operation."""
        return self._finish(context, confirmed=False)


# Helper function for creating scope GUI instances
def create_scope_gui(frame_range, operation_name, **kwargs):
    """
    Helper function to create a ScopeGUI instance with default settings.

    Args:
        frame_range (tuple): (start_frame, end_frame)
        operation_name (str): Name of the operation
        **kwargs: Additional parameters for ScopeGUI

    Returns:
        ScopeGUI: Configured ScopeGUI instance
    """
    # Set default values
    defaults = {
        "blend_range": None,
        "start_blend": BlendType.LINEAR,
        "end_blend": BlendType.LINEAR,
    }

    # Update with provided kwargs
    defaults.update(kwargs)

    # Create and return the scope GUI
    return ScopeGUI(frame_range=frame_range, operation_name=operation_name, **defaults)


# Registration
classes = (AMP_OT_scope_gui_example,)


def register():
    """Register the example classes."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister the example classes."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
