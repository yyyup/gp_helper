import bpy
from ..utils.customIcons import get_icon
from ..utils import get_prefs


#############################
###    HELPER FUNCTIONS   ###
#############################


def _draw_forge_link(layout, feature_name):
    """Draw a forge upgrade link when forge version is required but not available"""
    # Create the forge upgrade button
    row = layout.row()
    row.operator("wm.url_open", text="Forge Feature", **get_icon("AMP_Forge")).url = (
        "https://nda.gumroad.com/l/animate_forge"
    )



def _draw_experimental_enable_button(layout, feature_name):
    """Draw experimental enable button when experimental feature is disabled"""
    row = layout.row()
    prefs = get_prefs()
    try:
        row.prop(prefs, "experimental", text="Enable Experimental", **get_icon("EXPERIMENTAL"))
    except:
        # Fallback if EXPERIMENTAL icon is not available
        row.prop(prefs, "experimental", text="Enable Experimental", icon="SETTINGS")


# Registry to store all panel drawing functions
PANEL_REGISTRY = {}


def register_panel_function(panel_id, panel_function):
    """Register a panel function in the global registry"""
    PANEL_REGISTRY[panel_id] = panel_function


def draw_panel_as_section(
    layout,
    context,
    panel_name,
    icon_name,
    draw_function=None,
    panel_id=None,
    region_key="side_view",
    experimental=False,
    requires_forge=False,
):
    """
    Draw panel content directly without header styling.

    Args:
        layout: The layout to draw into
        context: The current context
        panel_name: Display name for the panel (unused)
        icon_name: Icon identifier for the panel (unused)
        draw_function: Function to call for drawing panel content (optional if panel_id is provided)
        panel_id: ID to register this panel for popover use (optional)
        region_key: Region identifier for state management (unused)
        experimental: Whether this panel is experimental (default: False)
        requires_forge: Whether this panel requires forge version (default: False)
    """
    prefs = get_prefs()

    # Check forge requirement first
    if requires_forge and not prefs.forge_version:
        # Draw forge link instead
        _draw_forge_link(layout, panel_name)
        return

    # Check experimental flag
    if experimental and not prefs.experimental:
        # Draw experimental enable button instead
        _draw_experimental_enable_button(layout, panel_name)
        return

    # Register panel for popover use if panel_id is provided
    if panel_id and draw_function:
        register_panel_function(panel_id, draw_function)

    # Call the provided draw function with a mock panel object
    if draw_function and callable(draw_function):
        # Create a mock panel object for compatibility with existing panel draw functions
        mock_panel = type("MockPanel", (), {"layout": layout})()
        try:
            draw_function(mock_panel, context)
        except Exception as e:
            # Fallback: try calling with just layout and context if panel signature fails
            try:
                draw_function(layout, context)

            except Exception:
                # Show error if both calling methods fail
                error_row = layout.row()
                error_row.alert = True
                error_row.label(text=f"{str(e)[:50]}...")


##################################
###         UI BUTTONS         ###
##################################


def draw_button_in_context(
    layout, context, supported_areas, icon_id, draw_fn, experimental=False, requires_forge=False
):
    """Helper to draw buttons based on context with poll method.

    Args:
        layout: The layout to draw into
        context: The current context
        supported_areas: Set of area types where the button should be active, or "ANY" for universal
        icon_id: Icon identifier string for the button
        draw_fn: Function to call to draw the actual button UI
        experimental: Whether this button is experimental (default: False)
        requires_forge: Whether this button requires forge version (default: False)
    """
    prefs = get_prefs()

    # Check forge requirement first
    if requires_forge and not prefs.forge_version:
        # Draw forge link instead
        _draw_forge_link(layout, "Feature")
        return

    # Check experimental flag
    if experimental and not prefs.experimental:
        # Draw experimental enable button instead
        _draw_experimental_enable_button(layout, "Feature")
        return

    @staticmethod
    def poll():
        """Poll method to check if button should be enabled"""
        # If supported_areas is "ANY", button works everywhere
        if supported_areas == "ANY":
            return True

        return (
            hasattr(context, "area")
            and context.area is not None
            and hasattr(context.area, "type")
            and context.area.type is not None
            and context.area.type in supported_areas
        )

    # Check if we're in the correct area type
    is_supported = poll()

    if is_supported:
        # Try to draw the actual button, fallback to fake button if error occurs
        try:
            draw_fn(layout, context)
        except AttributeError:
            # Draw a fake/disabled button when space_data doesn't have required attributes
            layout.active = False
            layout.operator("anim.amp_buttons_preview", text="", **get_icon(icon_id))
    else:
        # Draw fake button for unsupported areas to avoid AttributeError
        layout.active = False
        layout.operator("anim.amp_buttons_preview", text="", **get_icon(icon_id))


def draw_external_addon_panel_button(
    layout, context, panel_class_name, method_name, fallback_label, fallback_urls, icon_id
):
    """Helper to draw buttons for external addon panels with fallback to purchase links.

    Args:
        layout: The layout to draw into
        context: The current context
        panel_class_name: Name of the panel class to look for (e.g., "AMP_CT_PT_CopyPasteTransforms")
        method_name: Name of the method to call on the panel class (e.g., "draw_compact_labels")
        fallback_label: Label to show when addon is not available
        fallback_urls: Dict with 'super_hive' and 'gumroad' URLs
        icon_id: Icon identifier for the fallback button
    """
    panel_class = getattr(bpy.types, panel_class_name, None)

    if panel_class and hasattr(panel_class, method_name):
        # Panel is available, call its method
        method = getattr(panel_class, method_name)
        method(layout, context)
    else:
        # Panel not available, show fallback with purchase links
        row = layout.row()
        row.label(text=fallback_label, icon="URL")
        if fallback_urls.get("gumroad"):
            row.operator("wm.url_open", text="", **get_icon("Gumroad")).url = fallback_urls["gumroad"]
        if fallback_urls.get("super_hive"):
            row.operator("wm.url_open", text="", **get_icon("SuperHive")).url = fallback_urls["super_hive"]


#############################
###   EXTERNAL PANELS     ###
#############################


def validate_external_panel_exists(panel_class_name):
    """
    Validate that an external panel class exists in bpy.types.
    This function can be used in conditional expressions.

    Args:
        panel_class_name: The name of the panel class to check (e.g., "ANIMLAYERS_PT_VIEW_3D_List")

    Returns:
        bool: True if the panel class exists and has a draw method, False otherwise
    """
    if not panel_class_name:
        return False

    if hasattr(bpy.types, panel_class_name):
        panel_class = getattr(bpy.types, panel_class_name)
        return hasattr(panel_class, "draw")

    return False


def draw_external_panel(layout, context, panel_class_name, fallback_message=None):
    """
    Generic function to draw an external addon panel

    Args:
        layout: The layout to draw into
        context: The current context
        panel_class_name: The name of the panel class to look for in bpy.types
        fallback_message: Optional custom message when panel is not available
    """
    if hasattr(bpy.types, panel_class_name):
        # Get the panel class from bpy.types
        panel_class = getattr(bpy.types, panel_class_name)
        if hasattr(panel_class, "draw"):
            # Create a mock panel object for compatibility
            mock_panel = type("MockPanel", (), {"layout": layout})()
            try:
                # Call the draw method of the panel class
                panel_class.draw(mock_panel, context)
            except Exception as e:
                error_row = layout.row()
                error_row.alert = True
                error_row.label(text=f"Panel error: {str(e)[:50]}...", icon="ERROR")
        else:
            # Panel class exists but no draw method
            error_row = layout.row()
            error_row.alert = True
            error_row.label(text=f"{panel_class_name} has no draw method", icon="ERROR")
    else:
        # Panel class not found - show fallback message
        box = layout.box()
        col = box.column(align=True)
        if fallback_message:
            col.label(text=fallback_message, icon="INFO")
        else:
            col.label(text=f"{panel_class_name} Not Available", icon="INFO")
            col.label(text="External addon required")


def create_external_panel_function(panel_class_name, fallback_message=None):
    """
    Factory function to create a panel drawing function for external addons

    Args:
        panel_class_name: The name of the panel class to look for in bpy.types
        fallback_message: Optional custom message when panel is not available

    Returns:
        A function that can be used with _draw_panel_as_section
    """

    def draw_panel(layout, context):
        draw_external_panel(layout, context, panel_class_name, fallback_message)

    return draw_panel


#############################
###    DYNAMIC POPOVER    ###
#############################


class AMP_PT_DynamicPopover(bpy.types.Panel):
    """Dynamic popover panel that can display content from any registered panel"""

    bl_label = "Dynamic Panel"
    bl_idname = "AMP_PT_dynamic_popover"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout

        # Get the panel function from window manager properties
        wm = context.window_manager
        if hasattr(wm, "amp_popover_panel_key"):
            panel_key = wm.amp_popover_panel_key

            # Get the panel function from our registry
            panel_function = PANEL_REGISTRY.get(panel_key)
            if panel_function and callable(panel_function):
                try:
                    # Create a mock panel object for compatibility
                    mock_panel = type("MockPanel", (), {"layout": layout})()
                    try:
                        panel_function(mock_panel, context)
                    except Exception:
                        # Fallback: try calling with just layout and context
                        panel_function(layout, context)
                except Exception as e:
                    error_row = layout.row()
                    error_row.alert = True
                    error_row.label(text=f"Panel error: {str(e)[:50]}...", icon="ERROR")
            else:
                layout.label(text="Panel not found", icon="ERROR")
        else:
            layout.label(text="No panel specified", icon="INFO")


def call_popover_panel(context, panel_key):
    """Call a popover with the specified panel content"""
    # Store the panel key in window manager for the popover to use
    context.window_manager.amp_popover_panel_key = panel_key

    # Call the popover
    bpy.ops.wm.call_menu(name="AMP_PT_dynamic_popover")
