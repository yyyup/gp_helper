import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from ..utils.general import (
    reboot_theme_colors,
    set_autokeying_theme_colors,
    reset_autokeying_theme_colors,
)
from .. import utils

draw_handler_square = None
draw_handler_text = None
draw_handler_dict = {}

MSG_BUS_OWNER = "amp_autokeying_owner"
from .. import __package__ as base_package


def get_panel_dimensions(area):
    prefs = bpy.context.preferences.addons[base_package].preferences
    n_panel_width = 0
    tool_settings_height = 0

    # Handle dimensions for different area types
    if area.type == "VIEW_3D":
        n_panel_width = [region.width for region in area.regions if region.type == "UI"][0]
        tool_settings_height = prefs.tool_settings_height if bpy.context.space_data.show_region_tool_header else 0
        if not prefs.include_n_panel_width:
            n_panel_width = prefs.n_panel_bar if area.spaces.active.show_region_ui else 0
    elif area.type in ["DOPESHEET_EDITOR", "GRAPH_EDITOR", "NLA_EDITOR"]:
        tool_settings_height = prefs.tool_settings_height  # You may want to adapt this value
        n_panel_width = 0  # You may want to adapt this value

    return n_panel_width, tool_settings_height


# def draw_frame():
#     prefs = bpy.context.preferences.addons[base_package].preferences
#     auto_keying_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
#     if not prefs.viewport_frame or not auto_keying_on:
#         return

#     context = bpy.context
#     area = context.area
#     region = context.region

#     areas_to_draw = []
#     if prefs.viewport_frame:
#         areas_to_draw.append("VIEW_3D")
#     if prefs.frame_dopesheet and auto_keying_on:
#         areas_to_draw.append("DOPESHEET_EDITOR")
#     if prefs.frame_grapheditor and auto_keying_on:
#         areas_to_draw.append("GRAPH_EDITOR")
#     if prefs.frame_nla and auto_keying_on:
#         areas_to_draw.append("NLA_EDITOR")

#     if area.type in areas_to_draw:
#         if area.type in areas_to_draw and area == area:
#             n_panel_width, tool_settings_height = get_panel_dimensions(area)
#             region = next(region for region in area.regions if region.type == "WINDOW")
#             width, height = region.width, region.height

#             # Custom handling for Graph Editor and other editors
#             if area.type in ["GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"]:
#                 offset = prefs.frame_offset_editors
#                 frame_width = prefs.frame_width_editors
#                 tool_settings_height = prefs.frame_top_offset_editors
#                 n_panel_width = 0
#             else:
#                 offset = prefs.frame_offset
#                 frame_width = prefs.frame_width

#             vertices_outer = [
#                 (offset, offset, 0.0),
#                 (width - offset - n_panel_width, offset, 0.0),
#                 (
#                     width - offset - n_panel_width,
#                     height - offset - tool_settings_height,
#                     0.0,
#                 ),
#                 (offset, height - offset - tool_settings_height, 0.0),
#             ]

#             vertices_inner = [
#                 (offset + frame_width, offset + frame_width, 0.0),
#                 (
#                     width - offset - n_panel_width - frame_width,
#                     offset + frame_width,
#                     0.0,
#                 ),
#                 (
#                     width - offset - n_panel_width - frame_width,
#                     height - offset - tool_settings_height - frame_width,
#                     0.0,
#                 ),
#                 (
#                     offset + frame_width,
#                     height - offset - tool_settings_height - frame_width,
#                     0.0,
#                 ),
#             ]

#             vertices_viewport = [
#                 (0, 0, 0.0),
#                 (width, 0, 0.0),
#                 (width, height, 0.0),
#                 (0, height, 0.0),
#             ]

#             # Combine the vertices
#             vertices = vertices_viewport + vertices_outer + vertices_inner

#             # Indices for the inner frame
#             indices_inner = [
#                 (4, 5, 9),
#                 (4, 9, 8),
#                 (5, 6, 10),
#                 (5, 10, 9),
#                 (6, 7, 11),
#                 (6, 11, 10),
#                 (7, 4, 8),
#                 (7, 8, 11),
#             ]

#             # Indices for the outer frame
#             indices_outer = [
#                 (0, 1, 5),
#                 (0, 5, 4),
#                 (1, 2, 6),
#                 (1, 6, 5),
#                 (2, 3, 7),
#                 (2, 7, 6),
#                 (3, 0, 4),
#                 (3, 4, 7),
#             ]

#             shader = gpu.shader.from_builtin("UNIFORM_COLOR")
#             # shader.bind()

#             # Draw outer frame
#             if prefs.frame_outter and area.type == "VIEW_3D":
#                 shader.uniform_float("color", prefs.frame_outter_color)
#                 batch = batch_for_shader(
#                     shader, "TRIS", {"pos": vertices}, indices=indices_outer
#                 )
#                 batch.draw(shader)

#             # Draw inner frame, only if frame_inner is True
#             if prefs.frame_inner:  # Check the new property here
#                 shader.uniform_float("color", prefs.frame_color)
#                 batch = batch_for_shader(
#                     shader, "TRIS", {"pos": vertices}, indices=indices_inner
#                 )
#                 batch.draw(shader)


def generate_frame_vertices(offset, frame_width, width, height, tool_settings_height, n_panel_width):
    # Define vertices for the outer frame
    vertices_outer = [
        (offset, offset, 0.0),
        (width - offset - n_panel_width, offset, 0.0),
        (width - offset - n_panel_width, height - offset - tool_settings_height, 0.0),
        (offset, height - offset - tool_settings_height, 0.0),
    ]

    # Define vertices for the inner frame
    vertices_inner = [
        (offset + frame_width, offset + frame_width, 0.0),
        (width - offset - n_panel_width - frame_width, offset + frame_width, 0.0),
        (
            width - offset - n_panel_width - frame_width,
            height - offset - tool_settings_height - frame_width,
            0.0,
        ),
        (
            offset + frame_width,
            height - offset - tool_settings_height - frame_width,
            0.0,
        ),
    ]

    # Define vertices for the entire viewport (could be used for background or other purposes)
    vertices_viewport = [
        (0, 0, 0.0),
        (width, 0, 0.0),
        (width, height, 0.0),
        (0, height, 0.0),
    ]

    return vertices_outer, vertices_inner, vertices_viewport


def generate_frame_indices():
    # Indices for the inner frame
    indices_inner = [
        (4, 5, 9),
        (4, 9, 8),
        (5, 6, 10),
        (5, 10, 9),
        (6, 7, 11),
        (6, 11, 10),
        (7, 4, 8),
        (7, 8, 11),
    ]

    # Indices for the outer frame
    indices_outer = [
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]

    return indices_inner, indices_outer


def draw_frame(color_override=None, target_editors_override=None):
    prefs = bpy.context.preferences.addons[base_package].preferences
    auto_keying_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    if not prefs.viewport_frame or not auto_keying_on:
        return

    context = bpy.context
    area = context.area
    region = context.region

    # Determine target editors based on overrides or preferences
    areas_to_draw = target_editors_override if target_editors_override else []
    if not areas_to_draw:  # If override is not provided, use preferences
        if prefs.viewport_frame:
            areas_to_draw.append("VIEW_3D")
        if prefs.frame_dopesheet and auto_keying_on:
            areas_to_draw.append("DOPESHEET_EDITOR")
        if prefs.frame_grapheditor and auto_keying_on:
            areas_to_draw.append("GRAPH_EDITOR")
        if prefs.frame_nla and auto_keying_on:
            areas_to_draw.append("NLA_EDITOR")

    if area.type in areas_to_draw:
        n_panel_width, tool_settings_height = get_panel_dimensions(area)
        region = next(region for region in area.regions if region.type == "WINDOW")
        width, height = region.width, region.height

        # Define colors based on overrides or preferences
        outer_color = color_override if color_override else prefs.frame_outter_color
        inner_color = color_override if color_override else prefs.frame_color

        # Determine frame settings based on editor type
        if area.type in ["GRAPH_EDITOR", "DOPESHEET_EDITOR", "NLA_EDITOR"]:
            offset = prefs.frame_offset_editors
            frame_width = prefs.frame_width_editors
            tool_settings_height = prefs.frame_top_offset_editors
            n_panel_width = 0
        else:
            offset = prefs.frame_offset
            frame_width = prefs.frame_width

        # Generate vertices for outer, inner, and viewport frames
        vertices_outer, vertices_inner, vertices_viewport = generate_frame_vertices(
            offset, frame_width, width, height, tool_settings_height, n_panel_width
        )

        # Combine the vertices
        vertices = vertices_viewport + vertices_outer + vertices_inner

        # Indices for inner and outer frames
        indices_inner, indices_outer = generate_frame_indices()

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")

        # Draw outer frame if enabled and in target area
        if prefs.frame_outter and area.type in areas_to_draw:
            shader.uniform_float("color", outer_color)
            gpu.state.blend_set("ALPHA")
            batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices_outer)
            batch.draw(shader)
            gpu.state.blend_set("NONE")

        # Draw inner frame if enabled
        if prefs.frame_inner:
            shader.uniform_float("color", inner_color)
            batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices_inner)
            batch.draw(shader)


def draw_text():
    prefs = bpy.context.preferences.addons[base_package].preferences
    auto_keying_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    if not prefs.viewport_text or not auto_keying_on:
        return

    context = bpy.context
    area = context.area
    region = context.region

    if context.area.type == "VIEW_3D":  # Simplified condition
        n_panel_width, tool_settings_height = get_panel_dimensions(context.area)
        region = next(region for region in context.area.regions if region.type == "WINDOW")
        width, height = region.width, region.height

    # Calculate the actual usable width for text drawing
    usable_width = width - n_panel_width

    # Initialize text_offset_x and text_offset_y
    text_offset_x = prefs.text_offset  # Offset from the left
    text_offset_y = prefs.text_offset  # Offset from the bottom
    text_position = prefs.text_position

    # Draw the text using the property value
    font_id = 0
    blf.size(font_id, prefs.text_size)
    text_width, text_height = blf.dimensions(font_id, prefs.text_content)

    frame_offset_x = 0
    frame_offset_y = 0

    if prefs.viewport_frame:
        inner_offset = prefs.frame_width
        outter_offset = prefs.frame_width
        if prefs.frame_inner:
            inner_offset = prefs.frame_width
            outter_offset = prefs.frame_offset
        elif prefs.frame_outter:
            outter_offset = prefs.frame_offset
        else:
            outter_offset = 0
            inner_offset = 0

        frame_offset_x = outter_offset + inner_offset
        frame_offset_y = outter_offset + inner_offset

    # Positioning based on text_position
    if text_position == "BL":
        text_offset_x += frame_offset_x
        text_offset_y += frame_offset_y
    elif text_position == "B":
        text_offset_x = (usable_width - text_width) / 2
        text_offset_y += frame_offset_y
    elif text_position == "BR":
        text_offset_x = width - text_width - prefs.text_offset - n_panel_width - frame_offset_x
        text_offset_y += frame_offset_y
    elif text_position == "TL":
        text_offset_x += frame_offset_x
        text_offset_y = height - prefs.text_size - prefs.text_offset - tool_settings_height - frame_offset_y
    elif text_position == "T":
        text_offset_x = (usable_width - text_width) / 2
        text_offset_y = height - prefs.text_size - prefs.text_offset - tool_settings_height - frame_offset_y
    elif text_position == "TR":
        text_offset_x = width - text_width - prefs.text_offset - n_panel_width - frame_offset_x
        text_offset_y = height - prefs.text_size - prefs.text_offset - tool_settings_height - frame_offset_y
    elif text_position == "R":
        text_offset_x = width - text_width - prefs.text_offset - n_panel_width - frame_offset_x
        text_offset_y = (height - prefs.text_size) / 2
    elif text_position == "L":
        text_offset_x += frame_offset_x
        text_offset_y = (height - prefs.text_size) / 2

    # Enable shadow
    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 5, 0, 0, 0, 0.8)
    blf.shadow_offset(0, 3, -3)

    # Draw the text
    blf.position(font_id, text_offset_x, text_offset_y, 0)
    r, g, b, a = prefs.rec_text_color
    blf.color(font_id, r, g, b, a)  # 1.0)
    blf.draw(font_id, prefs.text_content)

    blf.disable(0, blf.SHADOW)


def notify_func(*args):
    global draw_handler_dict, draw_handler_text
    auto_keying_on = bpy.context.scene.tool_settings.use_keyframe_insert_auto

    if auto_keying_on:

        set_autokeying_theme_colors()
        # Logic to add handlers, ensuring not to duplicate existing ones
        if "SpaceView3D" not in draw_handler_dict:
            draw_handler_text = bpy.types.SpaceView3D.draw_handler_add(draw_text, (), "WINDOW", "POST_PIXEL")
            draw_handler_dict["SpaceView3D"] = draw_handler_text

    else:
        reset_autokeying_theme_colors()
        # Properly check and remove handlers if they exist
        if draw_handler_text:
            bpy.types.SpaceView3D.draw_handler_remove(draw_handler_text, "WINDOW")
            draw_handler_text = None
            # Remove from dict to ensure consistency
            if "SpaceView3D" in draw_handler_dict:
                del draw_handler_dict["SpaceView3D"]

    # Trigger redraw of all relevant areas
    for area in bpy.context.screen.areas:
        if area.type in ["VIEW_3D", "DOPESHEET_EDITOR", "GRAPH_EDITOR", "NLA_EDITOR"]:
            area.tag_redraw()
    utils.refresh_ui(bpy.context)


def subscribe_to_property():

    bpy.msgbus.subscribe_rna(
        key=(bpy.types.ToolSettings, "use_keyframe_insert_auto"),
        owner=MSG_BUS_OWNER,
        args=(),
        notify=notify_func,
        options={"PERSISTENT"},
    )


def unsubscribe_from_property():
    bpy.msgbus.clear_by_owner(MSG_BUS_OWNER)


def register():
    global draw_handler_dict, draw_handler_text

    draw_areas = [
        "SpaceView3D",
        "SpaceDopeSheetEditor",
        "SpaceGraphEditor",
        "SpaceNLA",
    ]

    for area in draw_areas:
        handler = eval(f"bpy.types.{area}.draw_handler_add(draw_frame, (), 'WINDOW', 'POST_PIXEL')")
        draw_handler_dict[area] = handler
    draw_handler_text = bpy.types.SpaceView3D.draw_handler_add(draw_text, (), "WINDOW", "POST_PIXEL")

    subscribe_to_property()

    # notify_func()


def unregister():

    bpy.types.SpaceView3D.draw_handler_remove(draw_handler_text, "WINDOW")
    # Unregister all draw handlers
    for area, handler in draw_handler_dict.items():
        if "Space" in area:
            eval(f"bpy.types.{area}.draw_handler_remove(handler, 'WINDOW')")

    unsubscribe_from_property()


if __name__ == "__main__":
    register()
