"""
Rounded Box Drawing Utility for Blender GUI
Provides rounded rectangles with GPU shaders
"""

import gpu
import gpu_extras
from gpu_extras.batch import batch_for_shader
from math import pi, cos, sin


class RoundedBoxDrawer:
    """A utility class for drawing rounded rectangles"""

    def __init__(self):
        self.modal_draw_visualizer_vars_1F0F9 = {"arc_points": [], "corner_points": []}
        self._last_box_bounds = None

    def draw_quad(self, quads, color):
        """Draw filled quadrilaterals"""
        vertices = []
        indices = []
        for i, quad in enumerate(quads):
            vertices.extend(quad)
            indices.extend([(i * 4, i * 4 + 1, i * 4 + 2), (i * 4 + 2, i * 4 + 1, i * 4 + 3)])
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": tuple(vertices)}, indices=tuple(indices))
        shader.bind()
        shader.uniform_float("color", color)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)

    def draw_line(self, coords, color, width):
        """Draw lines"""
        shader = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
        shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", width)
        batch = batch_for_shader(shader, "LINES", {"pos": coords, "color": [color, color]})
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)

    def draw_rounded_corner(self, Color, Color_Fill, Position, Thickness, Radius, Resolution, Fill, Start_Angle):
        """Draw rounded corner"""
        self.modal_draw_visualizer_vars_1F0F9["arc_points"] = []
        self.modal_draw_visualizer_vars_1F0F9["corner_points"] = []
        width = max(1, min(12, Thickness))
        total_segments = int(Resolution * 0.5)
        start_angle_rad = Start_Angle * (pi / 180)

        # Calculate key vertices
        vertex_start = (Position[0] + Radius * cos(start_angle_rad), Position[1] + Radius * sin(start_angle_rad))
        vertex_end = (
            Position[0] + Radius * cos(start_angle_rad + pi / 2),
            Position[1] + Radius * sin(start_angle_rad + pi / 2),
        )
        vertex_position = Position

        # Create arc vertices
        vertices = []
        vertex_colors = []
        for i in range(total_segments + 1):
            angle = start_angle_rad + (pi / 2) * i / total_segments
            x = Radius * cos(angle) + Position[0]
            y = Radius * sin(angle) + Position[1]
            vertices.append((x, y))
            vertex_colors.append(Color)

        # Fill vertices and drawing
        vertices_fill = [Position]
        fill_colors = []
        for i in range(total_segments + 1):
            angle = start_angle_rad + (pi / 2) * i / total_segments
            x = Radius * cos(angle) + Position[0]
            y = Radius * sin(angle) + Position[1]
            vertices_fill.append((x, y))
            fill_colors.append(Color_Fill)

        # Draw filled corner
        indices = [(0, i, i + 1) for i in range(1, total_segments + 1)]
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batch = batch_for_shader(shader, "TRIS", {"pos": vertices_fill}, indices=indices)
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_float("color", Color_Fill)
        batch.draw(shader)

        # Draw corner outline
        shader = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
        shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", width)
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": vertices, "color": vertex_colors})
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)

        # Store points for visualization
        for vertex in vertices:
            if vertex != vertex_start and vertex != vertex_end and vertex != vertex_position:
                self.modal_draw_visualizer_vars_1F0F9["arc_points"].append(vertex)
        self.modal_draw_visualizer_vars_1F0F9["corner_points"].extend([vertex_start, vertex_end, vertex_position])
        return [
            self.modal_draw_visualizer_vars_1F0F9["arc_points"],
            self.modal_draw_visualizer_vars_1F0F9["corner_points"],
        ]

    def draw_rounded_box_new(
        self, Location, Width, Height, Line_Color, Fill_Color, Line_Width, Corner_Radius, Corner_Resolution
    ):
        """Draw rounded box"""
        # Draw corners in the exact same order and positions
        arc_points_0_bdd30, corner_points_1_bdd30 = self.draw_rounded_corner(
            Line_Color, Fill_Color, Location, Line_Width, Corner_Radius, Corner_Resolution, True, 90.0
        )
        arc_points_0_83a9d, corner_points_1_83a9d = self.draw_rounded_corner(
            Line_Color,
            Fill_Color,
            (float(Location[0] + Width), Location[1]),
            Line_Width,
            Corner_Radius,
            Corner_Resolution,
            True,
            0.0,
        )
        arc_points_0_c9fc9, corner_points_1_c9fc9 = self.draw_rounded_corner(
            Line_Color,
            Fill_Color,
            (Location[0], float(Location[1] - Height)),
            Line_Width,
            Corner_Radius,
            Corner_Resolution,
            True,
            180.0,
        )
        arc_points_0_e2167, corner_points_1_e2167 = self.draw_rounded_corner(
            Line_Color,
            Fill_Color,
            (float(Location[0] + Width), float(Location[1] - Height)),
            Line_Width,
            Corner_Radius,
            Corner_Resolution,
            True,
            270.0,
        )

        # Draw quads
        # Top quad
        quads = [
            [
                tuple(corner_points_1_bdd30[0]),
                tuple(corner_points_1_83a9d[1]),
                tuple(corner_points_1_bdd30[2]),
                tuple(corner_points_1_83a9d[2]),
            ]
        ]
        self.draw_quad(quads, Fill_Color)

        # Right quad
        quads = [
            [
                tuple(corner_points_1_83a9d[0]),
                tuple(corner_points_1_83a9d[2]),
                tuple(corner_points_1_e2167[1]),
                tuple(corner_points_1_e2167[2]),
            ]
        ]
        self.draw_quad(quads, Fill_Color)

        # Bottom quad
        quads = [
            [
                tuple(corner_points_1_e2167[2]),
                tuple(corner_points_1_e2167[0]),
                tuple(corner_points_1_c9fc9[2]),
                tuple(corner_points_1_c9fc9[1]),
            ]
        ]
        self.draw_quad(quads, Fill_Color)

        # Left quad
        quads = [
            [
                tuple(corner_points_1_c9fc9[0]),
                tuple(corner_points_1_c9fc9[2]),
                tuple(corner_points_1_bdd30[1]),
                tuple(corner_points_1_bdd30[2]),
            ]
        ]
        self.draw_quad(quads, Fill_Color)

        # Center quad
        quads = [
            [
                tuple(corner_points_1_83a9d[2]),
                tuple(corner_points_1_bdd30[2]),
                tuple(corner_points_1_e2167[2]),
                tuple(corner_points_1_c9fc9[2]),
            ]
        ]
        self.draw_quad(quads, Fill_Color)

        # Draw edge lines
        edges = [
            (corner_points_1_bdd30[0], corner_points_1_83a9d[1]),
            (corner_points_1_83a9d[0], corner_points_1_e2167[1]),
            (corner_points_1_e2167[0], corner_points_1_c9fc9[1]),
            (corner_points_1_c9fc9[0], corner_points_1_bdd30[1]),
        ]
        for edge in edges:
            self.draw_line(edge, Line_Color, Line_Width)

    def draw_rounded_box(
        self, Location, Width, Height, Line_Color, Fill_Color, Line_Width, Corner_Radius, Corner_Resolution
    ):
        """Main function to draw rounded box"""
        # Store bounds for collision detection
        self._last_box_bounds = (Location[0], Location[1], Width, Height)

        self.draw_rounded_box_new(
            Location, Width, Height, Line_Color, Fill_Color, Line_Width, Corner_Radius, Corner_Resolution
        )

    def is_mouse_over_box(self, mouse_coordinates):
        """Check if mouse coordinates are within the last drawn box bounds"""
        if not self._last_box_bounds or not mouse_coordinates:
            return False

        x, y, width, height = self._last_box_bounds
        mx, my = mouse_coordinates

        return mx >= x and my >= (y - height) and mx <= (x + width) and my <= y


# Convenience functions that match the interface expected by the selection sets GUI
def draw_rounded_box_xy(
    x, y, width, height, line_color, fill_color, line_width=1.0, corner_radius=4.0, corner_resolution=8
):
    """
    Draw a rounded box

    Args:
        x, y: Position
        width, height: Dimensions
        line_color: RGBA color for outline
        fill_color: RGBA color for fill
        line_width: Width of outline
        corner_radius: Radius of rounded corners
        corner_resolution: Number of segments for rounded corners
    """
    try:
        drawer = RoundedBoxDrawer()
        location = (x, y + height)
        drawer.draw_rounded_box(
            location, width, height, line_color, fill_color, line_width, corner_radius, corner_resolution
        )
        return True
    except Exception as e:
        print(f"[DRAW_ROUNDED_BOX] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def is_mouse_over_rounded_box(location, width, height, mouse_coordinates):
    """
    Standalone function to check if mouse is over a rounded box area
    Uses simple bounding box collision detection
    """
    if not mouse_coordinates:
        return False

    x, y = location
    mx, my = mouse_coordinates

    return mx >= x and my >= y and mx <= (x + width) and my <= (y + height)


def draw_rounded_box_with_collision(
    location,
    width,
    height,
    mouse_coordinates,
    line_color=(1.0, 1.0, 1.0, 1.0),
    fill_color=(0.5, 0.5, 0.5, 0.8),
    hover_fill_color=None,
    line_width=1.0,
    corner_radius=10.0,
    corner_resolution=10,
):
    """
    Draw a rounded box with collision detection
    """
    drawer = RoundedBoxDrawer()
    is_mouse_over = is_mouse_over_rounded_box(location, width, height, mouse_coordinates)

    # Use hover color if mouse is over and hover color is specified
    if is_mouse_over and hover_fill_color:
        current_fill_color = hover_fill_color
    else:
        current_fill_color = fill_color

    box_location = (location[0], location[1] + height)
    drawer.draw_rounded_box(
        box_location, width, height, line_color, current_fill_color, line_width, corner_radius, corner_resolution
    )

    return drawer, is_mouse_over


# For compatibility with selection sets GUI, provide a simple function
def simple_box_collision(box_x, box_y, box_width, box_height, mouse_x, mouse_y):
    """Simple bounding box collision detection"""
    return box_x <= mouse_x <= box_x + box_width and box_y <= mouse_y <= box_y + box_height
