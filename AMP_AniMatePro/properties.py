import bpy
from bpy.types import PropertyGroup, Scene
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.utils import register_class, unregister_class
from . import utils


# Property group to hold all the custom properties
class TIMELINE_ScrubbingSettings(PropertyGroup):
    drag_threshold: IntProperty(
        name="Drag Threshold",
        description="Minimum mouse movement in pixels to initiate a drag",
        default=5,
        min=1,
        max=100,
    )

    timeline_sensitivity: FloatProperty(
        name="Timeline Sensitivity",
        description="Sensitivity of timeline scrubbing",
        default=0.5,
        min=0.01,
        max=2,
    )

    limit_to_active_range: BoolProperty(
        name="Limit to Active Range",
        description="Limit scrubbing to the active frame range",
        default=True,
    )

    timeline_gui_toggle: BoolProperty(
        name="Toggle GUI",
        description="Toggle the display of the GUI help",
        default=False,
    )

    timeline_gui_offset: FloatProperty(
        name="Timeline GUI Offset",
        description="Offset for the timeline GUI in pixels",
        default=0.0,
    )

    timeline_gui_color: FloatVectorProperty(
        name="GUI Color", default=(1.0, 1.0, 1.0), subtype="COLOR", min=0.0, max=1.0
    )

    timeline_gui_text_size: IntProperty(
        name="GUI Text Size",
        description="Text size for the timeline GUI",
        default=10,  # Default size
        min=1,
        max=50,
    )
    initial_mouse_x: FloatProperty(name="Initial Mouse X")

    initial_frame: IntProperty(name="Initial Frame")

    has_dragged: BoolProperty(name="Has Dragged", default=False)

    is_sensitivity_mode: BoolProperty(name="Is Sensitivity Mode", default=False)

    show_frame_number: BoolProperty(name="Show Frame Number at cursor", default=True)

    current_mode: StringProperty(name="Current Mode", default="SCRUBBING")

    scrubbing_error: StringProperty(name="Scrubbing errors", default="")

    text_color: FloatVectorProperty(
        name="Text Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,  # Minimum color value
        max=1.0,  # Maximum color value
        description="Color for the text",
    )

    accent_color: FloatVectorProperty(
        name="Accent Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 0.5, 0.0, 1.0),
        min=0.0,  # Minimum color value
        max=1.0,  # Maximum color value
        description="Accent color for the GUI",
    )
    text_size: IntProperty(
        name="Text Size",
        description="Size of the text in the GUI",
        default=12,
        min=1,
        max=100,
    )
    # Enum property to hold the modes PLAY, TOOLBOX, and SEARCH
    mode_options = [
        ("PLAY", "Play", "Play Animation", "PLAY", 0),
        ("TOOLBAR", "Toolbar", "Show Toolbar", "TOOL_SETTINGS", 1),
        ("SEARCH", "Search", "Search Menu", "VIEWZOOM", 2),
    ]

    mode: EnumProperty(
        name="Spacebar Action",
        description="Select the Spacebar action",
        items=mode_options,
        default="PLAY",
    )

    lock_text_in_place: BoolProperty(
        name="Lock Text While Scrubbing",
        description="Whether to move frames text while dragging the mouse",
        default=True,
    )

    lock_vertical_movement: BoolProperty(
        name="Allow Vertical Movement",
        description="Allow the drawn text to follow the mouse's vertical movement",
        default=True,
    )

    allow_horizontal_movement: BoolProperty(
        name="Allow Horizontal Movement",
        description="Allow the drawn text to follow the mouse's horizontal movement",
        default=True,
    )

    # In your TIMELINE_ScrubbingSettings PropertyGroup
    preview_range_set_scrub: BoolProperty(
        name="Operation Started",
        description="Flag to indicate if the preview range setting operation has started",
        default=False,
    )

    preview_start_frame: IntProperty(
        name="Preview Start Frame",
        description="Frame number where the preview range starts",
        default=1,
    )

    frame_last_action: BoolProperty(
        name="Frame Last Action",
        description="Zooming last action on the Editors",
        default=False,
    )

    deselect_state_index: bpy.props.IntProperty(default=-1, name="Select Index for select curves operator")
    last_transform_type: bpy.props.StringProperty(default="", name="Last Transform for select curves operator")
    solo_fcurve: bpy.props.BoolProperty(default=False, name="Solo Fcurve for select curves operator")
    set_keyframe_value: bpy.props.FloatProperty(
        default=1.0, name="Set Value", description="Set the value of all selected keframes"
    )

    icons_loaded: bpy.props.BoolProperty(default=False, name="Icons Loaded")


# Register properties
def register():
    register_class(TIMELINE_ScrubbingSettings)
    # Scene.timeline_scrub_settings = PointerProperty(type=TIMELINE_ScrubbingSettings)


# Unregister properties
def unregister():
    unregister_class(TIMELINE_ScrubbingSettings)
    del Scene.timeline_scrub_settings
