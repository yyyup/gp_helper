import bpy


# Panel injection registry for dynamic UI placement
_panel_hooks = []
_panel_picker_context = {}


def _generate_panel_identifier(panel_type):
    """Generate unique identifier for panel hook function"""
    return f"amp_panel_hook_{panel_type.bl_rna.identifier.lower()}"


def _create_panel_picker_ui(panel_type):
    """Create dynamic UI injection for panel selection interface"""
    hook_identifier = _generate_panel_identifier(panel_type)
    display_name = getattr(
        panel_type, "bl_label", panel_type.bl_rna.identifier.replace("_PT_", "").replace("_", " ").title()
    )

    # Get parent panel identifier
    parent_panel = getattr(panel_type, "bl_parent_id", None)
    parent_display = "Parent" if parent_panel else "No Parent"

    # Dynamic code generation for panel placement
    parent_button_code = ""
    if parent_panel:
        parent_button_code = f"""
    # Parent panel button
    parent_op = selection_row.operator("amp.panel_picker_confirm", 
                                      text="", 
                                      icon="FILE_PARENT")
    parent_op.target_panel = "{parent_panel}" """

    injection_code = f"""
def {hook_identifier}(self, context):
    ui_layout = self.layout
    selection_row = ui_layout.row()
    selection_row.alert = True
    selection_row.scale_y = 1
    
    # Main panel button
    placement_op = selection_row.operator("amp.panel_picker_confirm", 
                                         text="Pick {display_name}", 
                                         icon="EYEDROPPER")
    placement_op.target_panel = "{panel_type.bl_rna.identifier}"{parent_button_code}

bpy.types.{panel_type.bl_rna.identifier}.prepend({hook_identifier})
_panel_hooks.append([bpy.types.{panel_type.bl_rna.identifier}, {hook_identifier}])
"""

    try:
        exec(injection_code, globals())
    except Exception:
        pass


class AMP_OT_panel_picker_activate(bpy.types.Operator):
    """Activate dynamic panel selection mode"""

    bl_idname = "amp.panel_picker_activate"
    bl_label = "Activate Panel Picker"
    bl_description = (
        "Enter interactive mode to select any panel from Blender's UI, including nested and embedded panels"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    # Standard operator context properties
    data_owner_is_popup_panel: bpy.props.BoolProperty(default=False)
    data_owner_popup_panel_index: bpy.props.IntProperty(default=-1)
    category_index: bpy.props.IntProperty(default=-1)
    row_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        # Check if panel picker mode is not already active
        return not getattr(context.scene, "amp_panel_picker_active", False)

    def execute(self, context):
        # Store the operator context for later use
        global _panel_picker_context
        _panel_picker_context = {
            "data_owner_is_popup_panel": self.data_owner_is_popup_panel,
            "data_owner_popup_panel_index": self.data_owner_popup_panel_index,
            "category_index": self.category_index,
            "row_index": self.row_index,
        }

        # Initialize picker mode by injecting UI into available panels
        available_panels = bpy.types.Panel.__subclasses__()

        for panel_class in available_panels:
            # Include all panels - both top-level and nested/embedded panels
            _create_panel_picker_ui(panel_class)

        # Force UI refresh across all interface areas
        for interface_area in context.screen.areas:
            interface_area.tag_redraw()

        # Activate picker mode flag
        if hasattr(context.scene, "amp_panel_picker_active"):
            context.scene.amp_panel_picker_active = True

        self.report({"INFO"}, "Panel picker activated. Click on any panel in the UI to select it.")
        return {"FINISHED"}


class AMP_OT_panel_picker_confirm(bpy.types.Operator):
    """Confirm and apply panel selection"""

    bl_idname = "amp.panel_picker_confirm"
    bl_label = "Confirm Panel Selection"
    bl_description = "Finalize the panel selection"
    bl_options = {"REGISTER", "INTERNAL"}

    target_panel: bpy.props.StringProperty()

    def execute(self, context):
        from ..utils import get_prefs, get_contextual_row, refresh_ui

        # Get the stored context
        global _panel_picker_context
        if not _panel_picker_context:
            self.report({"ERROR"}, "Panel picker context not found")
            return {"CANCELLED"}

        # Create a temporary operator-like object to use with get_contextual_row
        class TempOperator:
            def __init__(self, context_data):
                self.data_owner_is_popup_panel = context_data["data_owner_is_popup_panel"]
                self.data_owner_popup_panel_index = context_data["data_owner_popup_panel_index"]
                self.category_index = context_data["category_index"]
                self.row_index = context_data["row_index"]

        temp_op = TempOperator(_panel_picker_context)

        # Get the target row
        row = get_contextual_row(context, temp_op)
        if not row:
            self.report({"ERROR"}, "Could not find target row")
            return {"CANCELLED"}

        if row.row_type != "PANEL":
            self.report({"ERROR"}, "Target row is not a panel row")
            return {"CANCELLED"}

        # Set the custom panel class name
        row.panel_id = "Panels_CustomPanel"
        row.custom_panel = self.target_panel

        # Clean up UI injections
        self._cleanup_panel_hooks()

        # Deactivate picker mode
        if hasattr(context.scene, "amp_panel_picker_active"):
            context.scene.amp_panel_picker_active = False

        # Clear the stored context
        _panel_picker_context.clear()

        # Refresh UI
        refresh_ui(context)

        # Extract a readable display name
        display_name = self.target_panel.replace("_PT_", "").replace("_", " ").title()
        self.report({"INFO"}, f"Panel '{display_name}' selected successfully")
        return {"FINISHED"}

    def _cleanup_panel_hooks(self):
        """Remove all dynamic UI injections"""
        for panel_class, hook_function in _panel_hooks:
            try:
                panel_class.remove(hook_function)
            except Exception:
                pass

        _panel_hooks.clear()


class AMP_OT_panel_picker_cancel(bpy.types.Operator):
    """Cancel panel picker mode"""

    bl_idname = "amp.panel_picker_cancel"
    bl_label = "Cancel Panel Picker"
    bl_description = "Cancel panel picker mode without selecting a panel"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        # Clean up UI injections
        for panel_class, hook_function in _panel_hooks:
            try:
                panel_class.remove(hook_function)
            except Exception:
                pass

        _panel_hooks.clear()

        # Deactivate picker mode
        if hasattr(context.scene, "amp_panel_picker_active"):
            context.scene.amp_panel_picker_active = False

        # Clear the stored context
        global _panel_picker_context
        _panel_picker_context.clear()

        # Force UI refresh
        for interface_area in context.screen.areas:
            interface_area.tag_redraw()

        self.report({"INFO"}, "Panel picker cancelled")
        return {"FINISHED"}


# Registration
classes = (
    AMP_OT_panel_picker_activate,
    AMP_OT_panel_picker_confirm,
    AMP_OT_panel_picker_cancel,
)


def register():
    from bpy.utils import register_class
    from bpy.types import Scene
    from bpy.props import BoolProperty

    for cls in classes:
        register_class(cls)

    # Register scene property for panel picker state
    Scene.amp_panel_picker_active = BoolProperty(
        name="Panel Picker Active", description="Indicates if panel picker mode is currently active", default=False
    )


def unregister():
    from bpy.utils import unregister_class
    from bpy.types import Scene

    # Clean up any active panel hooks
    for panel_class, hook_function in _panel_hooks:
        try:
            panel_class.remove(hook_function)
        except Exception:
            pass
    _panel_hooks.clear()

    # Clear any stored context
    global _panel_picker_context
    _panel_picker_context.clear()

    # Remove scene property
    try:
        del Scene.amp_panel_picker_active
    except AttributeError:
        pass

    for cls in reversed(classes):
        unregister_class(cls)
