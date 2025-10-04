import bpy
import bl_ui
from bpy.props import BoolProperty
from ..utils import get_prefs
from ..utils.customIcons import get_icon

# Store original draw methods for restoration
_original_draw_methods = {}

# Store toggle functions for each editor
_toggle_functions = {}

# Track if we've initialized to prevent double-setup
_initialized = False


def initialize_header_system():
    """Initialize the header system - should be called during addon registration"""
    global _initialized
    if not _initialized:
        # Ensure clean slate
        cleanup_header_modifications()

        # Ensure window manager properties are initialized to True
        _ensure_window_manager_props_initialized()
        _initialized = True


def _ensure_window_manager_props_initialized():
    """Ensure window manager properties are initialized to True"""
    try:
        import bpy

        if bpy.context and bpy.context.window_manager:
            wm = bpy.context.window_manager
            # Set all display properties to True to ensure consistent state
            wm.display_vanilla_top_graph = True
            wm.display_vanilla_top_dope = True
            wm.display_vanilla_top_nla = True
    except Exception as e:
        pass


def evaluate_amp_vanilla_top_menus(self, context):
    """Main evaluation function for vanilla top menus - now delegates to reload_top_bars_position

    This function is kept for backward compatibility but now simply calls the merged
    reload_top_bars_position function which handles both vanilla menu evaluation
    and top bar positioning in a single, more granular operation.
    """
    # Delegate to the merged function for comprehensive handling
    reload_top_bars_position(self, context)


def _is_minimal_draw_method(draw_method):
    """Check if the draw method is our minimal fake one"""
    if not hasattr(draw_method, "__name__"):
        return False

    # Check if it's a local function named 'minimal_draw'
    return (
        draw_method.__name__ == "minimal_draw"
        and hasattr(draw_method, "__code__")
        and "template_header" in draw_method.__code__.co_names
    )


def _is_toggle_function(func):
    """Check if a function is one of our toggle functions"""
    if not hasattr(func, "__name__"):
        return False

    # Check if it's one of our known toggle functions
    if func in _toggle_functions.values():
        return True

    # Check by naming pattern
    func_name = func.__name__
    return (func_name.startswith("_draw_") and func_name.endswith("_toggle")) or "toggle_draw" in func_name


def _store_original_draw_method(header_class):
    """Store the original draw method if not already stored and not our minimal fake one

    This prevents storing our minimal draw method when UI reloads occur while
    the header is in collapsed state, ensuring we always preserve the original
    Blender draw method for proper restoration.
    """
    class_name = header_class.__name__
    if class_name not in _original_draw_methods:
        # Only store if it's not our minimal fake draw method
        if not _is_minimal_draw_method(header_class.draw):
            _original_draw_methods[class_name] = header_class.draw


def _restore_original_headers():
    """Restore all original header draw methods"""
    import bl_ui.space_graph
    import bl_ui.space_dopesheet
    import bl_ui.space_nla

    headers = [
        bl_ui.space_graph.GRAPH_HT_header,
        bl_ui.space_dopesheet.DOPESHEET_HT_header,
        bl_ui.space_nla.NLA_HT_header,
    ]

    for header_class in headers:
        class_name = header_class.__name__
        if class_name in _original_draw_methods:
            header_class.draw = _original_draw_methods[class_name]


def _complete_restoration_to_vanilla():
    """Complete restoration of all headers to vanilla Blender state

    This function ensures that when collapsible_vanilla_top_panels is disabled,
    all headers are completely restored to their original state with no
    toggle functions or modifications remaining.
    """
    # Remove ALL toggle functions from ALL possible locations
    _comprehensive_toggle_cleanup()

    # Restore all original header draw methods
    _restore_original_headers()


# Editor configuration for dynamic handling
EDITOR_CONFIGS = {
    "graph": {
        "module": "bl_ui.space_graph",
        "header_class": "GRAPH_HT_header",
        "menu_class": "GRAPH_MT_editor_menus",
        "wm_prop": "display_vanilla_top_graph",
        "icon": "COLLAPSEMENU",
    },
    "dope": {
        "module": "bl_ui.space_dopesheet",
        "header_class": "DOPESHEET_HT_header",
        "menu_class": "DOPESHEET_MT_editor_menus",
        "wm_prop": "display_vanilla_top_dope",
        "icon": "COLLAPSEMENU",
    },
    "nla": {
        "module": "bl_ui.space_nla",
        "header_class": "NLA_HT_header",
        "menu_class": "NLA_MT_editor_menus",
        "wm_prop": "display_vanilla_top_nla",
        "icon": "COLLAPSEMENU",
    },
}


def _create_toggle_function(editor_key):
    """Create a toggle function for a specific editor"""
    config = EDITOR_CONFIGS[editor_key]

    def toggle_draw(self, context):
        wm = context.window_manager
        layout = self.layout
        layout.row().prop(wm, config["wm_prop"], text="", **get_icon(config["icon"]), emboss=True)

    # Give it a unique name to help with identification
    toggle_draw.__name__ = f"_draw_{editor_key}_toggle"
    toggle_draw.__editor_key__ = editor_key  # Add metadata for identification
    return toggle_draw


def _get_all_ui_functions_from_class(ui_class):
    """Get all dynamically registered UI functions from a class"""
    functions = []
    try:
        if hasattr(ui_class, "_dyn_ui_initialize"):
            dyn_ui = ui_class._dyn_ui_initialize()
            functions = list(dyn_ui)
    except Exception as e:
        pass
    return functions


def _comprehensive_toggle_cleanup(specific_toggle_function=None):
    """Comprehensively remove toggle functions from all possible locations

    This function removes toggle functions from ALL headers and menus across
    ALL editors to prevent duplicates regardless of panel state changes.

    Args:
        specific_toggle_function: If provided, only remove this specific function.
                                If None, remove all known toggle functions.
    """

    if specific_toggle_function:
        # When we have a specific toggle function, determine target editor
        target_editor_key = getattr(specific_toggle_function, "__editor_key__", None)

        if target_editor_key and target_editor_key in EDITOR_CONFIGS:
            # We know which editor this toggle belongs to, only clean that one
            _cleanup_specific_editor(target_editor_key, specific_toggle_function)
        else:
            # Fallback: check function name to determine the editor
            func_name = getattr(specific_toggle_function, "__name__", "")
            target_editor_key = None

            for editor_key in EDITOR_CONFIGS:
                if f"_draw_{editor_key}_toggle" in func_name:
                    target_editor_key = editor_key
                    break

            if target_editor_key:
                _cleanup_specific_editor(target_editor_key, specific_toggle_function)
            else:
                _cleanup_all_editors(specific_toggle_function)
    else:
        # Remove ALL toggle functions from ALL editors
        _cleanup_all_editors()


def _cleanup_specific_editor(editor_key, specific_toggle_function=None):
    """Clean up toggle functions from a specific editor only"""
    config = EDITOR_CONFIGS[editor_key]
    try:
        module = __import__(config["module"], fromlist=[config["header_class"], config["menu_class"]])
        header_class = getattr(module, config["header_class"])
        menu_class = getattr(module, config["menu_class"])

        if specific_toggle_function:
            # Remove only the specific toggle function
            _safe_remove_from_class(header_class, specific_toggle_function)
            _safe_remove_from_class(menu_class, specific_toggle_function)
        else:
            # Remove all toggle functions from this specific editor
            for toggle_key, toggle_function in _toggle_functions.items():
                if toggle_key == editor_key:  # Only remove toggles that belong to this editor
                    _safe_remove_from_class(header_class, toggle_function)
                    _safe_remove_from_class(menu_class, toggle_function)

            # Clean up orphaned toggles for this editor
            _cleanup_orphaned_toggles(header_class, menu_class, editor_key)

    except (ImportError, AttributeError) as e:
        print(f"DEBUG: Cannot access {editor_key} editor classes: {e}")


def _cleanup_all_editors(specific_toggle_function=None):
    """Clean up toggle functions from all editors"""
    for editor_key in EDITOR_CONFIGS:
        config = EDITOR_CONFIGS[editor_key]
        try:
            module = __import__(config["module"], fromlist=[config["header_class"], config["menu_class"]])
            header_class = getattr(module, config["header_class"])
            menu_class = getattr(module, config["menu_class"])

            if specific_toggle_function:
                # Remove only the specific toggle function from all editors
                _safe_remove_from_class(header_class, specific_toggle_function)
                _safe_remove_from_class(menu_class, specific_toggle_function)
            else:
                # Remove ALL toggle functions from this editor
                for toggle_key, toggle_function in _toggle_functions.items():
                    _safe_remove_from_class(header_class, toggle_function)
                    _safe_remove_from_class(menu_class, toggle_function)

                # Clean up orphaned toggles
                _cleanup_orphaned_toggles(header_class, menu_class, editor_key)

        except (ImportError, AttributeError) as e:
            print(f"DEBUG: Cannot access {editor_key} editor classes: {e}")


def _cleanup_orphaned_toggles(header_class, menu_class, editor_key):
    """Clean up any orphaned toggle functions from specific classes"""
    # Get all current UI functions to check for orphaned toggles
    header_functions = _get_all_ui_functions_from_class(header_class)
    menu_functions = _get_all_ui_functions_from_class(menu_class)

    # Remove any orphaned toggle functions by pattern matching
    all_functions = header_functions + menu_functions
    orphaned_toggles = [func for func in all_functions if _is_toggle_function(func)]

    for func in orphaned_toggles:
        _safe_remove_from_class(header_class, func)
        _safe_remove_from_class(menu_class, func)


def _safe_remove_from_class(target_class, draw_function):
    """Safely remove a draw function from a class if it exists"""
    try:
        if hasattr(target_class, "_dyn_ui_initialize"):
            dyn_ui = target_class._dyn_ui_initialize()
            if draw_function in dyn_ui:
                target_class.remove(draw_function)
                func_name = getattr(draw_function, "__name__", "unnamed_function")
                return True
            else:
                func_name = getattr(draw_function, "__name__", "unnamed_function")
                return False
        else:
            pass
            return False
    except (ValueError, AttributeError) as e:
        # Function wasn't in the class or class doesn't support dynamic UI
        func_name = getattr(draw_function, "__name__", "unnamed_function")
        return False


def _safe_add_to_class(target_class, draw_function, prepend=True):
    """Safely add a draw function to a class if it doesn't already exist"""
    try:
        if hasattr(target_class, "_dyn_ui_initialize"):
            dyn_ui = target_class._dyn_ui_initialize()
            if draw_function not in dyn_ui:
                if prepend:
                    target_class.prepend(draw_function)
                else:
                    target_class.append(draw_function)
                func_name = getattr(draw_function, "__name__", "unnamed_function")
                return True
            else:
                func_name = getattr(draw_function, "__name__", "unnamed_function")
                return False
        else:
            return False
    except AttributeError as e:
        # Class doesn't support dynamic UI
        func_name = getattr(draw_function, "__name__", "unnamed_function")
        return False


def _handle_editor_header(editor_key, show_vanilla):
    """Generic handler for editor header visibility"""
    config = EDITOR_CONFIGS[editor_key]

    # Import the module dynamically
    module = __import__(config["module"], fromlist=[config["header_class"], config["menu_class"]])
    header_class = getattr(module, config["header_class"])
    menu_class = getattr(module, config["menu_class"])

    # Get or create the toggle function
    if editor_key not in _toggle_functions:
        _toggle_functions[editor_key] = _create_toggle_function(editor_key)

    toggle_function = _toggle_functions[editor_key]

    _store_original_draw_method(header_class)

    # Simple cleanup: only remove from current editor's classes
    _safe_remove_from_class(header_class, toggle_function)
    _safe_remove_from_class(menu_class, toggle_function)

    if show_vanilla:
        # Restore original draw method
        if header_class.__name__ in _original_draw_methods:
            header_class.draw = _original_draw_methods[header_class.__name__]

        # Add toggle to menu when panel is expanded
        _safe_add_to_class(menu_class, toggle_function, prepend=True)
    else:
        # Replace with minimal draw method that preserves prepend/append functionality
        def minimal_draw(self, context):
            layout = self.layout
            layout.template_header()

        header_class.draw = minimal_draw

        # if dope register the ui mode first
        if editor_key == "dope":
            import bl_ui

            bl_ui.space_dopesheet.DOPESHEET_HT_header.append(draw_dope_filter)

        # Add toggle to header when panel is collapsed
        _safe_add_to_class(header_class, toggle_function, prepend=False)

        # Handle any additional functions specific to this editor
        if "additional_functions" in config:
            for func in config["additional_functions"]:
                _safe_add_to_class(header_class, func, prepend=False)
        # # Add toggle to header when panel is collapsed
        # _safe_add_to_class(header_class, toggle_function, prepend=False)


def _handle_graph_header(show_vanilla):
    """Handle Graph Editor header visibility"""
    _handle_editor_header("graph", show_vanilla)


def _handle_dope_header(show_vanilla):
    """Handle Dope Sheet Editor header visibility"""
    import bl_ui

    # Always remove draw_dope_filter first to ensure clean state
    try:
        bl_ui.space_dopesheet.DOPESHEET_HT_header.remove(draw_dope_filter)
    except ValueError:
        # Function wasn't in the header, which is fine
        pass

    _handle_editor_header("dope", show_vanilla)


def _handle_nla_header(show_vanilla):
    """Handle NLA Editor header visibility"""
    _handle_editor_header("nla", show_vanilla)


def cleanup_header_modifications():
    """Clean up all header modifications and restore originals

    This should be called during addon unregistration to ensure clean state.
    """

    # Use comprehensive cleanup to remove ALL toggle functions from ALL locations
    _comprehensive_toggle_cleanup()

    # Restore all original headers
    _restore_original_headers()

    # Clean up category registrations
    _unregister_all_top_panels()

    # Clear our tracking dictionaries
    _original_draw_methods.clear()
    _toggle_functions.clear()


# -----------------------------------------------------------------------------
# Category/Top Bars Registration Logic
# -----------------------------------------------------------------------------


# Top panel draw functions for each editor
def _draw_top_graph(self, context):
    """Draw top panel UI for Graph Editor"""
    from .addon_ui import draw_top_panel_ui

    draw_top_panel_ui(context, self.layout, "top_graph")


def _draw_top_dope(self, context):
    """Draw top panel UI for Dope Sheet Editor"""
    from .addon_ui import draw_top_panel_ui

    draw_top_panel_ui(context, self.layout, "top_dope")


def _draw_top_nla(self, context):
    """Draw top panel UI for NLA Editor"""
    from .addon_ui import draw_top_panel_ui

    draw_top_panel_ui(context, self.layout, "top_nla")


# Registration state tracking for categories/top panels
_top_panels_registered = {
    "graph": {"target": None, "position": None, "function": None},
    "dope": {"target": None, "position": None, "function": None},
    "nla": {"target": None, "position": None, "function": None},
}


def reload_top_bars_position(self, context):
    """Comprehensive function that handles both vanilla top menu evaluation and top bar positioning

    This function merges the logic from evaluate_amp_vanilla_top_menus to provide granular control over:
    - Vanilla top panel visibility and header modifications
    - Top bar registration order and positioning
    - Toggle function management based on collapsible_vanilla_top_panels setting

    The function ensures proper registration order based on:
    - collapsible_vanilla_top_panels setting
    - top_bars_position setting (LEFT/RIGHT)
    - display_vanilla_top_{editor} flags
    """
    # Ensure we're initialized
    if not _initialized:
        initialize_header_system()

    prefs = get_prefs()
    wm = context.window_manager

    # First, unregister any existing top panel registrations
    _unregister_all_top_panels()

    def _handle_top_panel(self, context, editor_key="graph"):
        # Handle vanilla top menu evaluation first - this sets up the header states
        try:
            if not prefs.collapsible_vanilla_top_panels:
                # Complete restoration to vanilla Blender state
                # This removes ALL toggle functions and restores original draw methods
                _complete_restoration_to_vanilla()
            else:
                # Handle individual editor preferences by replacing draw methods
                # Use window manager properties which are always initialized to True
                if editor_key == "graph":
                    _handle_graph_header(wm.display_vanilla_top_graph)
                elif editor_key == "dope":
                    _handle_dope_header(wm.display_vanilla_top_dope)
                elif editor_key == "nla":
                    _handle_nla_header(wm.display_vanilla_top_nla)

        except Exception as e:
            pass

    # Helper function to determine placement based on conditions
    def get_conditional_placement(editor_type, position_type):
        wm = context.window_manager if context else bpy.context.window_manager

        # Check if vanilla top panels should be displayed
        display_vanilla = {
            "graph": getattr(wm, "display_vanilla_top_graph", False),
            "dope": getattr(wm, "display_vanilla_top_dope", False),
            "nla": getattr(wm, "display_vanilla_top_nla", False),
        }

        # Base class mappings
        header_classes = {
            "graph": bl_ui.space_graph.GRAPH_HT_header,
            "dope": bl_ui.space_dopesheet.DOPESHEET_HT_header,
            "nla": bl_ui.space_nla.NLA_HT_header,
        }

        menu_classes = {
            "graph": bl_ui.space_graph.GRAPH_MT_editor_menus,
            "dope": bl_ui.space_dopesheet.DOPESHEET_MT_editor_menus,
            "nla": bl_ui.space_nla.NLA_MT_editor_menus,
        }

        # Apply the conditional logic you specified:
        if position_type == "TOP_LEFT":
            if prefs.collapsible_vanilla_top_panels:
                if display_vanilla.get(editor_type, False):
                    # If vanilla is displayed, attach categories to left side of the menus prepend
                    return (menu_classes[editor_type], "prepend"), "after"
                else:
                    # If vanilla is hidden, attach categories to header right side append
                    return (header_classes[editor_type], "append"), "before"

            else:
                # Standard TOP_LEFT placement (prepend to menus)
                return (menu_classes[editor_type], "prepend"), "after"

        elif position_type == "TOP_RIGHT":
            if prefs.collapsible_vanilla_top_panels:
                if display_vanilla.get(editor_type, False):
                    return (header_classes[editor_type], "append"), "before"
                else:
                    # If vanilla is hidden, attach categories to header right side append
                    return (header_classes[editor_type], "append"), "before"
            else:
                # Standard TOP_RIGHT placement (append to header)
                return (header_classes[editor_type], "append"), "before"

        else:
            # Fallback to menu prepend
            return (menu_classes[editor_type], "prepend"), "after"

    # Map position preference to target class and method using conditionals
    position_mapping = {
        "TOP_LEFT": {
            "graph": get_conditional_placement("graph", "TOP_LEFT"),
            "dope": get_conditional_placement("dope", "TOP_LEFT"),
            "nla": get_conditional_placement("nla", "TOP_LEFT"),
        },
        "TOP_RIGHT": {
            "graph": get_conditional_placement("graph", "TOP_RIGHT"),
            "dope": get_conditional_placement("dope", "TOP_RIGHT"),
            "nla": get_conditional_placement("nla", "TOP_RIGHT"),
        },
    }

    # Get the mapping for current position preference
    current_mapping = position_mapping.get(prefs.top_bars_position)
    if not current_mapping:
        print(f"Unknown top_bars_position: {prefs.top_bars_position}")
        return

    # Register each editor's top panel to its target
    draw_functions = {"graph": _draw_top_graph, "dope": _draw_top_dope, "nla": _draw_top_nla}

    for editor, ((target_class, method), timing) in current_mapping.items():
        draw_func = draw_functions[editor]

        # Handle the top panel based on timing from conditional placement
        if timing == "before":
            # Register the handle top panel BEFORE evaluating individual panels
            _handle_top_panel(self, context, editor)

            # Then register the top panel
            try:
                if method == "append":
                    target_class.append(draw_func)
                else:  # prepend
                    target_class.prepend(draw_func)

                # Store registration info for later cleanup
                _top_panels_registered[editor] = {"target": target_class, "position": method, "function": draw_func}

            except Exception as e:
                print(f"Failed to register {editor} top panel: {e}")

        else:  # timing == "after"
            # Register the top panel first
            try:
                if method == "append":
                    target_class.append(draw_func)
                else:  # prepend
                    target_class.prepend(draw_func)

                # Store registration info for later cleanup
                _top_panels_registered[editor] = {"target": target_class, "position": method, "function": draw_func}

            except Exception as e:
                print(f"Failed to register {editor} top panel: {e}")

            # Then handle the top panel AFTER registering individual panels
            _handle_top_panel(self, context, editor)


def _unregister_all_top_panels():
    """Unregister all currently registered top panels"""
    for editor, registration_info in _top_panels_registered.items():
        if registration_info["target"] and registration_info["function"]:
            try:
                registration_info["target"].remove(registration_info["function"])
            except Exception as e:
                # Panel might not be registered, ignore error
                pass

    # Reset registration tracking
    for editor in _top_panels_registered:
        _top_panels_registered[editor] = {"target": None, "position": None, "function": None}


def draw_dope_filter(self, context):
    """Draw the Dope Sheet filter panel"""
    layout = self.layout

    # Get the dopesheet space data
    st = context.space_data

    # Draw the dopesheet mode dropdown (Action, Shape Key, Grease Pencil, etc.)
    if st and st.type == "DOPESHEET_EDITOR":
        row = layout.row(align=True)
        row.prop(st, "mode", text="")


# Window Manager Properties for vanilla top panel display states
def register_window_manager_props():
    """Register window manager properties for vanilla top panel states"""
    bpy.types.WindowManager.display_vanilla_top_graph = BoolProperty(
        name="Display Vanilla Top Graph",
        description="Toggle the default top Graph Editor panel",
        default=True,
        update=reload_top_bars_position,
    )

    bpy.types.WindowManager.display_vanilla_top_dope = BoolProperty(
        name="Display Vanilla Top Dope",
        description="Toggle the default top Dope Sheet panel",
        default=True,
        update=reload_top_bars_position,
    )

    bpy.types.WindowManager.display_vanilla_top_nla = BoolProperty(
        name="Display Vanilla Top NLA",
        description="Toggle the default top NLA Editor panel",
        default=True,
        update=reload_top_bars_position,
    )


def unregister_window_manager_props():
    """Unregister window manager properties for vanilla top panel states"""
    del bpy.types.WindowManager.display_vanilla_top_graph
    del bpy.types.WindowManager.display_vanilla_top_dope
    del bpy.types.WindowManager.display_vanilla_top_nla


def register():
    register_window_manager_props()


def unregister():
    unregister_window_manager_props()
    cleanup_header_modifications()
