import bpy
from bpy.props import (
    FloatVectorProperty,
    PointerProperty,
    CollectionProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, Operator, Panel, AddonPreferences
from bpy.utils import register_class, unregister_class
from ..utils.customIcons import get_icon
from .. import __package__ as base_package
from .anim_poser import (
    enable_isolate_character,
    disable_isolate_character,
    enable_isolate_character_,       # add underscore versions
    disable_isolate_character_,
)

# ----------------------------------------------------
# PROPERTY GROUPS
# ----------------------------------------------------


class AMP_SilhouetteShadingInfo(PropertyGroup):
    """Stores shading information for a specific SpaceView3D."""

    space_id: StringProperty(
        name="Space ID",
        description="Unique identifier for the SpaceView3D",
    )
    shading_background_type: StringProperty(
        name="Background Type",
        default="WORLD",
    )

    shading_background_color: FloatVectorProperty(
        name="Background Color",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        size=3,
    )

    shading_type: StringProperty(
        name="Shading Type",
        default="SOLID",
    )

    shading_light: StringProperty(
        name="Shading Light",
        default="FLAT",
    )

    shading_color_type: StringProperty(
        name="Color Type",
        default="SINGLE",
    )

    shading_single_color: FloatVectorProperty(
        name="Single Color",
        subtype="COLOR",
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        size=3,
    )

    shading_show_shadows: bpy.props.BoolProperty(name="Show Shadows", default=True)
    shading_show_cavity: bpy.props.BoolProperty(name="Show Cavity", default=True)
    overlay_show_overlays: bpy.props.BoolProperty(name="Show Overlays", default=True)
    shading_show_backface_culling: bpy.props.BoolProperty(name="Show Backface Culling", default=True)


class AMP_PG_AnimSilhouetteProps(PropertyGroup):
    """Global properties for the Anim Silhouette addon."""

    # Collection to store shading info for multiple viewports
    shading_infos: CollectionProperty(type=AMP_SilhouetteShadingInfo)


# ----------------------------------------------------
# FUNCTIONS TO CAPTURE AND RESTORE SHADING
# ----------------------------------------------------


def get_shading_info(space_data):
    shading = space_data.shading
    overlay = space_data.overlay
    shading_info = {
        "background_type": shading.background_type,
        "background_color": shading.background_color[:],
        "shading_type": shading.type,
        "shading_light": shading.light,
        "shading_color_type": shading.color_type,
        "single_color": shading.single_color[:],
        "show_shadows": shading.show_shadows,
        "show_cavity": shading.show_cavity,
        "overlay_show_overlays": overlay.show_overlays,
        "show_backface_culling": shading.show_backface_culling,
    }
    return shading_info


def set_shading_info(shading_info, space_data):
    shading = space_data.shading
    overlay = space_data.overlay

    # Helper function to validate enum values
    def validate_enum(prop, value, default):
        enum_items = [item.identifier for item in prop.enum_items]
        if value not in enum_items:
            print(f"Warning: '{value}' is not a valid value for '{prop.identifier}'. Falling back to '{default}'.")
            return default
        return value

    # Validate and set background type
    shading.background_type = validate_enum(
        shading.bl_rna.properties["background_type"], shading_info.get("background_type", "WORLD"), "WORLD"
    )

    # Validate and set shading color type
    shading.color_type = validate_enum(
        shading.bl_rna.properties["color_type"], shading_info.get("shading_color_type", "SINGLE"), "SINGLE"
    )

    # Set colors
    shading.background_color = shading_info.get("background_color", shading.background_color)[:3]
    shading.single_color = shading_info.get("single_color", shading.single_color)[:3]

    # Validate and set shading type and light
    shading.type = validate_enum(shading.bl_rna.properties["type"], shading_info.get("shading_type", "SOLID"), "SOLID")
    shading.light = validate_enum(shading.bl_rna.properties["light"], shading_info.get("shading_light", "FLAT"), "FLAT")

    # Set other shading options
    shading.show_shadows = shading_info.get("show_shadows", shading.show_shadows)
    shading.show_cavity = shading_info.get("show_cavity", shading.show_cavity)

    # Set overlay options
    overlay.show_overlays = shading_info.get("overlay_show_overlays", overlay.show_overlays)

    # Restore backface culling state
    shading.show_backface_culling = shading_info.get("show_backface_culling", shading.show_backface_culling)


# ----------------------------------------------------
# OPERATOR TO TOGGLE SILHOUETTE
# ----------------------------------------------------


class AMP_OT_ToggleSilhouette(Operator):
    """Toggle silhouette mode for the active viewport."""

    bl_idname = "anim.amp_toggle_silhouette"
    bl_label = "Toggle Silhouette"
    bl_description = "Enable or disable silhouette mode for this viewport"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        addon_prefs = context.preferences.addons[base_package].preferences
        poser_props = bpy.context.scene.anim_poser_props
        armatures_selected = any(obj.type == "ARMATURE" for obj in context.selected_objects)

        # Ensure the active space is a 3D view
        space = context.space_data
        if space.type != "VIEW_3D":
            self.report({"WARNING"}, "Active space is not a 3D View")
            return {"CANCELLED"}

        shading_infos = scene.amp_silhouette.shading_infos
        space_id = str(space.as_pointer())  # More reliable unique identifier

        # Check if silhouette is already enabled for this space
        existing_info = None
        existing_index = -1
        for i, info in enumerate(shading_infos):
            if info.space_id == space_id:
                existing_info = info
                existing_index = i
                break

        if existing_info is None:
            # Enable silhouette
            shading_info = get_shading_info(space)
            # Add shading info to the collection
            new_info = shading_infos.add()
            new_info.space_id = space_id
            new_info.shading_background_type = shading_info["background_type"]
            new_info.shading_background_color = shading_info["background_color"]
            new_info.shading_type = shading_info["shading_type"]
            new_info.shading_light = shading_info["shading_light"]
            new_info.shading_color_type = shading_info["shading_color_type"]
            new_info.shading_single_color = shading_info["single_color"]
            new_info.shading_show_shadows = shading_info["show_shadows"]
            new_info.shading_show_cavity = shading_info["show_cavity"]
            new_info.overlay_show_overlays = shading_info["overlay_show_overlays"]
            new_info.shading_show_backface_culling = shading_info["show_backface_culling"]

            # Apply silhouette shading
            shading = space.shading
            shading.background_type = "VIEWPORT"
            shading.background_color = addon_prefs.poser_background_color[:3]
            shading.type = "SOLID"
            shading.light = "FLAT"
            shading.color_type = "SINGLE"
            shading.single_color = addon_prefs.poser_foreground_color[:3]
            shading.show_shadows = False
            shading.show_cavity = False
            shading.show_backface_culling = False
            space.overlay.show_overlays = False

            if armatures_selected:
                enable_isolate_character_(context, poser_props, enter_pose_mode=False)

            self.report({"INFO"}, "Silhouette mode enabled for this viewport.")
        else:
            # Disable silhouette and restore shading
            shading_info = {
                "background_type": existing_info.shading_background_type,
                "background_color": existing_info.shading_background_color,
                "shading_type": existing_info.shading_type,
                "shading_light": existing_info.shading_light,
                "shading_color_type": existing_info.shading_color_type,
                "single_color": existing_info.shading_single_color,
                "show_shadows": existing_info.shading_show_shadows,
                "show_cavity": existing_info.shading_show_cavity,
                "overlay_show_overlays": existing_info.overlay_show_overlays,
                "show_backface_culling": existing_info.shading_show_backface_culling,
            }
            set_shading_info(shading_info, space)

            # Remove the shading info entry by index
            if existing_index != -1:
                shading_infos.remove(existing_index)
                self.report({"INFO"}, "Silhouette mode disabled for this viewport.")
            else:
                self.report({"WARNING"}, "Failed to find silhouette info to remove.")

            if armatures_selected:
                disable_isolate_character_(context, poser_props)

        return {"FINISHED"}


# ----------------------------------------------------
# PANEL
# ----------------------------------------------------


class AMP_PT_AnimSilhouettePanel(Panel):
    bl_idname = "AMP_PT_AnimSilhouettePanel"
    bl_label = "Anim Silhouette"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Anim Tools"

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.preferences.addons[base_package].preferences
        props = context.scene.amp_silhouette

        box = layout.box()
        box.label(text="Silhouette Colors:")
        box.prop(addon_prefs, "poser_background_color", text="Background")
        box.prop(addon_prefs, "poser_foreground_color", text="Foreground")

        layout.separator()
        # Add a toggle button for the current viewport
        shading_infos = context.scene.amp_silhouette.shading_infos
        space = context.space_data
        if space.type != "VIEW_3D":
            layout.label(text="Not a 3D View")
            return

        space_id = str(space.as_pointer())  # Ensure consistency with operator
        is_enabled = False
        for info in shading_infos:
            if info.space_id == space_id:
                is_enabled = True
                break

        layout.operator(
            "anim.amp_toggle_silhouette",
            text="Disable Silhouette" if is_enabled else "Enable Silhouette",
            **get_icon("AMP_silhouette_on" if is_enabled else "AMP_silhouette_off"),
        )


# ----------------------------------------------------
# BUTTON IN HEADER
# ----------------------------------------------------


def SilhouetteButton(self, context):
    """Add a toggle button to the 3D View header."""
    layout = self.layout
    shading_infos = context.scene.amp_silhouette.shading_infos
    space = context.space_data
    if space.type != "VIEW_3D":
        return

    space_id = str(space.as_pointer())
    is_enabled = False
    for info in shading_infos:
        if info.space_id == space_id:
            is_enabled = True
            break

    layout.operator(
        "anim.amp_toggle_silhouette",
        text="",
        **get_icon("AMP_silhouette_on" if is_enabled else "AMP_silhouette_off"),
        emboss=True,
    )


# ----------------------------------------------------
# REGISTER / UNREGISTER
# ----------------------------------------------------


def register_silohuette_button(self, context):
    prefs = context.preferences.addons[base_package].preferences

    try:
        bpy.types.VIEW3D_HT_header.remove(SilhouetteButton)
    except:
        pass
    
    if prefs.poser_silohuette_button:
        bpy.types.VIEW3D_HT_header.append(SilhouetteButton)
    else:
        bpy.types.VIEW3D_HT_header.remove(SilhouetteButton)


classes = (
    AMP_SilhouetteShadingInfo,
    AMP_PG_AnimSilhouetteProps,
    AMP_OT_ToggleSilhouette,
    # AMP_PT_AnimSilhouettePanel,
)


def register():
    for cls in classes:
        register_class(cls)

    register_silohuette_button(None, bpy.context)

    bpy.types.Scene.amp_silhouette = PointerProperty(type=AMP_PG_AnimSilhouetteProps)


def unregister():

    try:
        bpy.types.VIEW3D_HT_header.remove(SilhouetteButton)
    except:
        pass

    del bpy.types.Scene.amp_silhouette

    for cls in reversed(classes):
        unregister_class(cls)
