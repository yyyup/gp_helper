##################
##    utils     ##
## operators.py ##
##################

import bpy
from .api import dprint
from .. import utils

from .. import __package__ as base_package


class AMP_OT_ResetGraphEditorFlag_LMB(bpy.types.Operator):
    bl_idname = "anim.amp_jump_to_keyframe_tracking"
    bl_label = "Reset Graph Editor Flags"
    bl_description = "Reset flags to False"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences
        if prefs.jump_already_made:
            prefs.jump_already_made = False
            dprint("Persistent flags reset to False.")
        return {"FINISHED"}


class AMP_OT_CallHelpPanel(bpy.types.Operator):

    bl_idname = "anim.amp_call_help_panel"
    bl_label = "Instructions"
    bl_description = "Press to get more detail about this section"

    panel_name: bpy.props.StringProperty()

    def execute(self, context):
        if self.panel_name in dir(bpy.types):
            panel_class = getattr(bpy.types, self.panel_name)
            if hasattr(panel_class, "bl_idname"):
                bpy.ops.wm.call_panel(name=panel_class.bl_idname)
                return {"FINISHED"}
        self.report({"WARNING"}, "Panel not found: " + self.panel_name)
        return {"CANCELLED"}


class AMP_OT_AnimationEditors(bpy.types.Operator):

    bl_idname = "space.amp_animation_editors"
    bl_label = "Editor Switcher"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """
Switch to different editor spaces in Blender.
Supports all editor types including animation editors, 3D Viewport, Image Editor, Node Editors, and more.
Hold Shift to open the editor in a new window instead of changing the current area."""

    space_type: bpy.props.EnumProperty(
        name="Space Type",
        description="The type of editor space to switch to",
        items=[
            # Core editors
            ("VIEW_3D", "3D Viewport", "Switch to 3D Viewport"),
            ("IMAGE_EDITOR", "Image Editor", "Switch to Image Editor"),
            ("NODE_EDITOR", "Node Editor", "Switch to Node Editor"),
            ("SEQUENCE_EDITOR", "Video Sequencer", "Switch to Video Sequencer"),
            ("CLIP_EDITOR", "Movie Clip Editor", "Switch to Movie Clip Editor"),
            ("TEXT_EDITOR", "Text Editor", "Switch to Text Editor"),
            ("CONSOLE", "Python Console", "Switch to Python Console"),
            ("INFO", "Info", "Switch to Info Editor"),
            ("OUTLINER", "Outliner", "Switch to Outliner"),
            ("PROPERTIES", "Properties", "Switch to Properties Panel"),
            ("FILE_BROWSER", "File Browser", "Switch to File Browser"),
            ("SPREADSHEET", "Spreadsheet", "Switch to Spreadsheet"),
            ("PREFERENCES", "Preferences", "Switch to Preferences"),
            # Animation editors
            ("DOPESHEET_EDITOR", "Dope Sheet", "Switch to Dope Sheet Editor"),
            ("GRAPH_EDITOR", "Graph Editor", "Switch to Graph Editor"),
            ("NLA_EDITOR", "NLA Editor", "Switch to NLA Editor"),
            ("TIMELINE", "Timeline", "Switch to Timeline"),
            ("DRIVERS_EDITOR", "Drivers", "Switch to Drivers Editor"),
        ],
    )

    subspace_type: bpy.props.EnumProperty(
        name="Subspace Type",
        description="The subspace mode to switch to within the specified editor",
        items=[
            # Animation editor modes
            ("DOPESHEET", "Dope Sheet", "Basic Dope Sheet"),
            ("ACTION", "Action Editor", "Action Editor"),
            ("SHAPEKEY", "Shape Key Editor", "Shape Key Editor"),
            ("GPENCIL", "Grease Pencil", "Grease Pencil"),
            ("MASK", "Mask", "Mask Editor"),
            ("CACHEFILE", "Cache File", "Cache File Editor"),
            # File browser modes
            ("ASSETS", "Asset Browser", "Asset Browser"),
            ("FILES", "File Browser", "File Browser"),
            # Node editor types
            ("ShaderNodeTree", "Shader Nodes", "Shader Node Editor"),
            ("CompositorNodeTree", "Compositor", "Compositor Node Editor"),
            ("TextureNodeTree", "Texture Nodes", "Texture Node Editor"),
            ("GeometryNodeTree", "Geometry Nodes", "Geometry Node Editor"),
            # Image editor modes
            ("VIEW", "View", "Image Viewer"),
            ("UV", "UV Editor", "UV Editor"),
            ("PAINT", "Paint", "Image Paint"),
            ("MASK", "Mask", "Mask Editor"),
        ],
        default="DOPESHEET",
    )

    @classmethod
    def poll(cls, context):
        return context.area is not None

    def invoke(self, context, event):
        # Check if Shift is pressed
        if event.shift:
            # Store the current area dimensions for new window creation
            self.original_area = context.area
            self.create_new_window = True
        else:
            self.create_new_window = False

        return self.execute(context)

    def execute(self, context):
        area = context.area

        if not area:
            self.report({"WARNING"}, "No active area found.")
            return {"CANCELLED"}

        # Map our custom enum values to Blender's recognized area types and ui_types
        space_type_map = {
            # Core editors (change area.type)
            "VIEW_3D": {"area_type": "VIEW_3D", "ui_type": None},
            "IMAGE_EDITOR": {"area_type": "IMAGE_EDITOR", "ui_type": None},
            "NODE_EDITOR": {"area_type": "NODE_EDITOR", "ui_type": None},
            "SEQUENCE_EDITOR": {"area_type": "SEQUENCE_EDITOR", "ui_type": None},
            "CLIP_EDITOR": {"area_type": "CLIP_EDITOR", "ui_type": None},
            "TEXT_EDITOR": {"area_type": "TEXT_EDITOR", "ui_type": None},
            "CONSOLE": {"area_type": "CONSOLE", "ui_type": None},
            "INFO": {"area_type": "INFO", "ui_type": None},
            "OUTLINER": {"area_type": "OUTLINER", "ui_type": None},
            "PROPERTIES": {"area_type": "PROPERTIES", "ui_type": None},
            "FILE_BROWSER": {"area_type": "FILE_BROWSER", "ui_type": None},
            "SPREADSHEET": {"area_type": "SPREADSHEET", "ui_type": None},
            "PREFERENCES": {"area_type": "PREFERENCES", "ui_type": None},
            # Animation editors (change area.type and ui_type)
            "DOPESHEET_EDITOR": {"area_type": "DOPESHEET_EDITOR", "ui_type": "DOPESHEET"},
            "GRAPH_EDITOR": {"area_type": "DOPESHEET_EDITOR", "ui_type": "FCURVES"},
            "NLA_EDITOR": {"area_type": "DOPESHEET_EDITOR", "ui_type": "NLA_EDITOR"},
            "TIMELINE": {"area_type": "DOPESHEET_EDITOR", "ui_type": "TIMELINE"},
            "DRIVERS_EDITOR": {"area_type": "DOPESHEET_EDITOR", "ui_type": "DRIVERS"},
        }

        mapping = space_type_map.get(self.space_type)
        if not mapping:
            self.report({"WARNING"}, f"Unknown space type: {self.space_type}")
            return {"CANCELLED"}

        # If Shift was pressed, create a new window
        if getattr(self, "create_new_window", False):
            return self._create_new_window(context, mapping)
        else:
            return self._change_current_area(context, area, mapping)

    def _create_new_window(self, context, mapping):
        """Create a new window with the specified editor type"""
        original_area = getattr(self, "original_area", context.area)

        # Get the original area dimensions
        area_width = original_area.width
        area_height = original_area.height

        # Create a new window
        bpy.ops.wm.window_new()

        # Get the new window
        new_window = context.window_manager.windows[-1]
        new_area = new_window.screen.areas[0]

        # Set the area type
        new_area.type = mapping["area_type"]

        # Set the ui_type if specified
        if mapping["ui_type"] is not None:
            if hasattr(new_area, "ui_type"):
                new_area.ui_type = mapping["ui_type"]

        # Configure the space in the new window
        new_space = new_area.spaces.active
        self._configure_space(new_space, new_area)

        self.report({"INFO"}, f"Opened {self.space_type} in new window.")
        return {"FINISHED"}

    def _change_current_area(self, context, area, mapping):
        """Change the current area to the specified editor type"""
        # Change the area type if needed
        if area.type != mapping["area_type"]:
            area.type = mapping["area_type"]
            self.report({"INFO"}, f"Changed area type to {mapping['area_type']}.")

        # Change the ui_type if specified
        if mapping["ui_type"] is not None:
            if hasattr(area, "ui_type") and area.ui_type != mapping["ui_type"]:
                area.ui_type = mapping["ui_type"]
                self.report({"INFO"}, f"Changed UI type to {mapping['ui_type']}.")

        # After changing types, re-fetch the active space
        space = area.spaces.active
        self._configure_space(space, area)

        return {"FINISHED"}

    def _configure_space(self, space, area):
        """Configure the space with subspace settings"""
        if self.space_type == "FILE_BROWSER":
            # Handle File Browser modes (Asset Browser vs regular File Browser)
            if hasattr(space, "browse_mode"):
                if self.subspace_type == "ASSETS":
                    # Set to Asset Browser mode
                    if space.browse_mode != "ASSETS":
                        space.browse_mode = "ASSETS"
                        self.report({"INFO"}, "Set File Browser to Asset Browser mode.")
                else:
                    # For any other case (FILES or no subspace), ensure it's NOT in ASSETS mode
                    if space.browse_mode == "ASSETS":
                        # Try to set to FILES mode, fallback to first available mode
                        try:
                            space.browse_mode = "FILES"
                            self.report({"INFO"}, "Set File Browser to Files mode.")
                        except:
                            # If FILES doesn't exist, try to set to any non-ASSETS mode
                            available_modes = [
                                item.identifier for item in space.bl_rna.properties["browse_mode"].enum_items
                            ]
                            non_asset_modes = [mode for mode in available_modes if mode != "ASSETS"]
                            if non_asset_modes:
                                space.browse_mode = non_asset_modes[0]
                                self.report({"INFO"}, f"Set File Browser to {non_asset_modes[0]} mode.")
            else:
                self.report({"WARNING"}, "File Browser does not have browse_mode property.")
        elif self.space_type == "NODE_EDITOR" and self.subspace_type:
            # Handle node editor tree types
            node_tree_types = ["ShaderNodeTree", "CompositorNodeTree", "TextureNodeTree", "GeometryNodeTree"]
            if self.subspace_type in node_tree_types:
                if hasattr(space, "tree_type"):
                    if space.tree_type != self.subspace_type:
                        space.tree_type = self.subspace_type
                        self.report({"INFO"}, f"Set Node Editor to {self.subspace_type}.")
        elif self.space_type == "IMAGE_EDITOR" and self.subspace_type:
            # Handle image editor modes
            if self.subspace_type == "UV" and hasattr(space, "mode"):
                if space.mode != "UV":
                    space.mode = "UV"
                    self.report({"INFO"}, "Set Image Editor to UV mode.")
            elif self.subspace_type == "PAINT" and hasattr(space, "mode"):
                if space.mode != "PAINT":
                    space.mode = "PAINT"
                    self.report({"INFO"}, "Set Image Editor to Paint mode.")
        elif self.space_type == "DOPESHEET_EDITOR" and hasattr(space, "mode") and self.subspace_type:
            # Handle dope sheet editor modes
            valid_modes = [item.identifier for item in space.bl_rna.properties["mode"].enum_items]
            if self.subspace_type in valid_modes:
                if space.mode != self.subspace_type:
                    space.mode = self.subspace_type
                    self.report({"INFO"}, f"Set Dope Sheet mode to {self.subspace_type}.")

        return {"FINISHED"}


# Dummy operator for preview buttons on the UI


class AMP_OT_LoadDefaultCategories(bpy.types.Operator):
    """Load default categories on startup"""

    bl_idname = "anim.amp_load_default_categories"
    bl_label = "Load Default Categories"
    bl_description = "Load default categories from JSON files"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        try:
            from ..ui.addon_ui import _ensure_default_categories_loaded

            _ensure_default_categories_loaded()
            print("[AMP] Default categories loaded successfully")
        except Exception as e:
            print(f"[AMP] Error loading default categories: {e}")
            import traceback

            traceback.print_exc()
        return {"FINISHED"}


class AMP_OT_ButtonsPreview(bpy.types.Operator):
    bl_idname = "anim.amp_buttons_preview"
    bl_label = "Preview Button"
    bl_description = "Preview button for UI"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}


classes = (
    AMP_OT_ResetGraphEditorFlag_LMB,
    AMP_OT_AnimationEditors,
    AMP_OT_CallHelpPanel,
    AMP_OT_LoadDefaultCategories,
    AMP_OT_ButtonsPreview,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError or AttributeError:
            utils.dprint("Class already registered, skiping...")


def unregister():
    try:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    except RuntimeError or AttributeError:
        utils.dprint("Class not found, skiping...")


##################
##    utils     ##
## operators.py ##
##################
