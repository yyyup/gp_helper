import bpy
import gpu
import blf
from bpy.types import Scene
from gpu_extras.batch import batch_for_shader
import math
from math import radians
import numpy as np
from ..utils.curve import is_fcurve_in_radians, get_nla_strip_offset
from ..utils import ensure_alpha, refresh_ui
from ..utils.customIcons import get_icon
from .. import __package__ as base_package

addon_keymaps = []


def draw_gui_help_text(context, x, y, operator=None):
    """Draw GUI help text in the Graph Editor."""

    prefs = bpy.context.preferences.addons[base_package].preferences

    blf.enable(0, blf.SHADOW)
    blf.shadow(0, 6, 0, 0, 0, 1)
    blf.shadow_offset(0, 2, -2)
    font_id = 0
    blf.size(font_id, 12)

    safe_text_color = ensure_alpha(prefs.text_color)
    blf.color(0, *safe_text_color)

    props = bpy.context.scene.keyframe_lattice_settings

    if prefs.timeline_gui_toggle:

        lines = [
            "______________________",
            "Anim Lattice Help:",
            "______________________",
            "",
            "Drag Control points to scale",
            "",
        ]

        # Add mode-specific controls
        mode = operator.mode if operator else props.mode
        if mode == "WARP":
            warp_lines = [
                "WARP MODE:",
                "Use Control Points to warp the lattice",
                "+ / - : Add/Remove Columns",
                "Shift + / - : Add/Remove Rows",
                "",
            ]
            lines.extend(warp_lines)

        lines.extend(
            [
                "ESC - Cancel",
                "RMB - Options",
                "ENTER - Finish",
                "Ctrl+Z - Undo",
                "Ctrl+Shift+Z - Redo",
                "H - Toggle Help",
            ]
        )

        for line in reversed(lines):
            text_width, text_height = blf.dimensions(font_id, line)
            blf.position(font_id, x, y, 0)
            blf.draw(font_id, line)
            y += text_height + 5
    else:
        blf.position(0, 20, 30, 0)
        blf.draw(0, "GUI Help (H)")

    blf.disable(0, blf.SHADOW)


def update_lattice(self, context):
    """Update callback for lattice properties to mark operator as dirty."""
    # Find the running operator instance and mark it as dirty
    for window in context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == "GRAPH_EDITOR":
                # Check if the operator is running by looking for the class variable
                if hasattr(AMP_OT_anim_lattice, "_is_running") and AMP_OT_anim_lattice._is_running:
                    # Set a flag that will be checked in the modal method
                    # We'll use a scene property as a bridge since we can't directly access the operator instance
                    context.scene["lattice_needs_update"] = True
                    break


class ControlPoint:
    # def __init__(self, index, position, operator, shape="square", section=(0, 0)):

    def __init__(self, index, position, operator, shape="square", section=(0, 0), *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.index = index
        self.position = position
        self.size = 10
        self.is_hovered = False
        self.shape = shape
        self.section = section
        self.operator = operator
        # self.offset = get_nla_strip_offset(bpy.context.active_object)

    def draw(self):
        cp_color = (1.0, 0.5, 0.0, 1.0) if self.is_hovered else (1.0, 1.0, 1.0, 1.0)
        lcp_color = (1.0, 0.5, 0.0, 1.0) if self.is_hovered else (1.0, 0.5, 0.0, 0.5)
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        # Convert position to screen space using operator's method
        screen_pos = self.operator.graph_to_screen(self.position[0], self.position[1])
        if self.shape == "circle":
            draw_circle(shader, screen_pos, self.size / 2, cp_color)
        elif self.shape == "rhomboid":
            draw_rhomboid(shader, screen_pos, self.size, lcp_color)
        else:
            half_size = self.size / 2
            x, y = screen_pos
            vertices = [
                (x - half_size, y - half_size),
                (x + half_size, y - half_size),
                (x + half_size, y + half_size),
                (x - half_size, y + half_size),
            ]

            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})
            shader.bind()
            shader.uniform_float("color", cp_color)
            batch.draw(shader)

    def check_hover(self, mouse_x, mouse_y):
        screen_x, screen_y = self.operator.graph_to_screen(self.position[0], self.position[1])
        half_size = self.size / 2
        is_now_hovered = (
            screen_x - half_size <= mouse_x <= screen_x + half_size
            and screen_y - half_size <= mouse_y <= screen_y + half_size
        )
        hovered = False

        if is_now_hovered and not self.is_hovered:
            self.is_hovered = True
            bpy.context.window.cursor_set("SCROLL_XY")
            hovered = True
        elif not is_now_hovered and self.is_hovered:
            self.is_hovered = False
            bpy.context.window.cursor_set("DEFAULT")

        return hovered


class LoopControlPoint(ControlPoint):
    # def __init__(
    #     self, index, position, operator, shape="rhomboid", section=(0, 0), orientation="horizontal", associated_cp=None
    # ):
    #     super().__init__(index, position, operator, shape, section)
    def __init__(
        self,
        index,
        position,
        operator,
        shape="rhomboid",
        section=(0, 0),
        orientation="horizontal",
        associated_cp=None,
        *args,
        **kwargs,
    ):
        super().__init__(index, position, operator, shape, section, *args, **kwargs)
        self.orientation = orientation  # 'horizontal' or 'vertical'
        self.associated_cp = associated_cp  # The CP this LCP is associated with
        self.display_distance = self.size * 20  # Display when mouse is within this distance
        self.is_displayed = False

    def draw(self):
        if not self.is_displayed:
            return
        super().draw()

    def check_hover(self, mouse_x, mouse_y):
        # Convert control point position to screen space using operator's method
        screen_x, screen_y = self.operator.graph_to_screen(*self.position)
        half_size = self.size / 2

        # Larger area for displaying the control point
        display_half_size = self.display_distance / 2

        mouse_distance = math.hypot(mouse_x - screen_x, mouse_y - screen_y)
        if mouse_distance <= display_half_size:
            self.is_displayed = True
        else:
            self.is_displayed = False

        if not self.is_displayed:
            self.is_hovered = False
            return False

        # Check hover over the actual control point area
        is_now_hovered = (
            screen_x - half_size <= mouse_x <= screen_x + half_size
            and screen_y - half_size <= mouse_y <= screen_y + half_size
        )
        hovered = False

        if is_now_hovered and not self.is_hovered:
            self.is_hovered = True
            bpy.context.window.cursor_set("SCROLL_XY")
            hovered = True

        elif not is_now_hovered and self.is_hovered:
            self.is_hovered = False
            bpy.context.window.cursor_set("DEFAULT")

        return hovered


class AMP_OT_anim_lattice(bpy.types.Operator):
    bl_idname = "anim.amp_anim_lattice"
    bl_label = "Anim Lattice"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Drag control points to scale keyframes proportionally within a bounding box.
In WARP mode, use +/- to add/remove columns, Shift +/- for rows.
Hold Shift to launch with the options panel."""

    slice_to_full_frames: bpy.props.BoolProperty(
        name="Slice to Full Frames",
        description="Slice keyframes to closest full frames on finish/cancel",
        default=True,
    )

    zoom_out_times: bpy.props.IntProperty(
        name="Zoom Out Times",
        description="Extra zoom out factor when normalization is on",
        default=10,
        min=1,
        max=100,
    )

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Mode of the lattice",
        items=(
            ("NORMAL", "Normal", "Normal mode"),
            ("WARP", "Warp", "Warp mode"),
        ),
        default="NORMAL",
    )

    # offset: bpy.props.FloatProperty(
    #     name="Offset",
    #     description="Offset for the graph view",
    #     default=0.0,
    # )

    # Define padding constants
    VERTICAL_PADDING = 0.0001  # Value
    HORIZONTAL_PADDING = 1  # Frame

    # Precision constants to prevent keyframe merging
    FRAME_EPSILON = 1e-6  # Minimum distance between keyframes to prevent merging
    MIN_SUBFRAME_DISTANCE = 1e-4  # Minimum subframe distance

    _handle = None
    _is_running = False
    _current_mode = None  # Track the current mode when running

    @classmethod
    def poll(cls, context):
        return (
            context.area.type == "GRAPH_EDITOR"
            and context.active_object is not None
            and context.active_object.animation_data is not None
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        props = bpy.context.scene.keyframe_lattice_settings
        self.current_mode = self.mode
        self.previous_lattice_x = props.lattice_x
        self.previous_lattice_y = props.lattice_y
        self.control_points = []
        self.loop_control_points = []
        self.mouse_x = 0
        self.mouse_y = 0
        self.mouse_graph_x = 0.0
        self.mouse_graph_y = 0.0
        self.dragging_control_point = None
        self.initial_mouse_x = 0
        self.initial_mouse_y = 0
        self.initial_mouse_graph_x = 0.0
        self.initial_mouse_graph_y = 0.0
        self.initial_keyframes = []
        self.initial_bounds = None
        self.initial_control_point_positions = {}
        self.fcurves_to_update = set()
        self.undo_stack = []
        self.context = None
        self.initial_selected_keyframes = []

        # Initialize NumPy arrays
        self.fcurves_array = None
        self.indices_array = None
        self.is_rotation_curve_array = None
        self.initial_co_array = None
        self.initial_handle_left_array = None
        self.initial_handle_right_array = None
        self.relative_co = None
        self.relative_handle_left = None
        self.relative_handle_right = None
        self.relative_co_cell_list = []
        self.relative_handle_left_cell_list = []
        self.relative_handle_right_cell_list = []

        # Checks for normalization on start and end
        self.initial_use_normalization = False
        self.initial_view_settings = {}

        # Flag to handle lattice property changes from UI
        self.lattice_dirty = False

    def invoke(self, context, event):
        if event.shift:
            bpy.ops.wm.call_panel(name="AMP_PT_AnimLatticeOptions", keep_open=True)
            return {"FINISHED"}

        return self.execute(context)

    def init_tool(self, context):
        self.context = context

        self.fcurves_to_update = set()

        self.collect_initial_keyframe_data()

        if not len(self.initial_co_array):
            self.report({"WARNING"}, "No keyframes selected")
            return {"CANCELLED"}

        self.initial_bounds = self.get_initial_bounds()
        if not self.initial_bounds:
            self.report({"WARNING"}, "Unable to determine keyframe bounds")
            return {"CANCELLED"}

        self.compute_relative_positions()

        self.init_control_points(context)

        args = (self, context)
        self._handle = bpy.types.SpaceGraphEditor.draw_handler_add(self.draw_callback, args, "WINDOW", "POST_PIXEL")
        context.area.tag_redraw()

        # Register the initial state with Blender's undo system
        # bpy.ops.ed.undo_push(message="Anim Lattice Start")

        self.push_undo(context)

        return {"RUNNING_MODAL"}

    # def graph_to_screen(self, graph_x, graph_y, offset):
    #     view2d = self.context.region.view2d
    #     screen_x, screen_y = view2d.view_to_region(graph_x + offset, graph_y, clip=False)
    #     return screen_x, screen_y

    # def screen_to_graph(self, screen_x, screen_y, offset):
    #     view2d = self.context.region.view2d
    #     gx, gy = view2d.region_to_view(screen_x, screen_y)
    #     return gx - offset, gy

    def graph_to_screen(self, graph_x, graph_y):
        view2d = self.context.region.view2d
        screen_x, screen_y = view2d.view_to_region(
            bpy.context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x),
            graph_y,
            clip=False,
        )

        return screen_x, screen_y

    def screen_to_graph(self, screen_x, screen_y):
        view2d = self.context.region.view2d
        graph_x, graph_y = view2d.region_to_view(screen_x, screen_y)

        return bpy.context.active_object.animation_data.nla_tweak_strip_time_to_scene(graph_x, invert=True), graph_y

    def push_undo(self, context):
        """Push the current state to the undo stack, including keyframes and control points positions."""
        # Store keyframes state with high precision
        co_array = np.zeros_like(self.initial_co_array, dtype=np.float64)
        handle_left_array = np.zeros_like(self.initial_handle_left_array, dtype=np.float64)
        handle_right_array = np.zeros_like(self.initial_handle_right_array, dtype=np.float64)

        for i in range(len(self.indices_array)):
            fcurve = self.fcurves_array[i]
            index = self.indices_array[i]
            is_rotation_curve = self.is_rotation_curve_array[i]
            kf = fcurve.keyframe_points[index]
            x_value = kf.co[0]
            y_value = math.degrees(kf.co[1]) if is_rotation_curve else kf.co[1]
            handle_left_x = kf.handle_left[0]
            handle_left_y = math.degrees(kf.handle_left[1]) if is_rotation_curve else kf.handle_left[1]
            handle_right_x = kf.handle_right[0]
            handle_right_y = math.degrees(kf.handle_right[1]) if is_rotation_curve else kf.handle_right[1]
            co_array[i] = [x_value, y_value]
            handle_left_array[i] = [handle_left_x, handle_left_y]
            handle_right_array[i] = [handle_right_x, handle_right_y]

        # Determine mode-specific state storage
        props = bpy.context.scene.keyframe_lattice_settings
        if self.mode == "WARP":
            # Store complete control point information in warp mode
            regular_cps = []
            for cp in self.control_points:
                regular_cps.append(
                    {
                        "index": cp.index,
                        "position": [cp.position[0], cp.position[1]],
                        "shape": cp.shape,
                        "section": cp.section,
                    }
                )
            loop_cps = []
            for lcp in self.loop_control_points:
                loop_cps.append(
                    {
                        "index": lcp.index,
                        "position": [lcp.position[0], lcp.position[1]],
                        "shape": lcp.shape,
                        "section": lcp.section,
                        "orientation": lcp.orientation,
                        "associated_cp_index": lcp.associated_cp.index if lcp.associated_cp else None,
                    }
                )
            # Lattice config
            lattice_cfg = {
                "mode": self.mode,
                "lattice_x": props.lattice_x,
                "lattice_y": props.lattice_y,
                "current_mode": self.current_mode,
                "previous_lattice_x": self.previous_lattice_x,
                "previous_lattice_y": self.previous_lattice_y,
            }
            state = {
                "co_array": co_array.copy(),
                "handle_left_array": handle_left_array.copy(),
                "handle_right_array": handle_right_array.copy(),
                "regular_control_points": regular_cps,
                "loop_control_points": loop_cps,
                "lattice_config": lattice_cfg,
                "initial_bounds": self.initial_bounds,
            }
        else:
            # In normal mode, only store keyframe arrays (control points recreated on drag)
            state = {
                "co_array": co_array.copy(),
                "handle_left_array": handle_left_array.copy(),
                "handle_right_array": handle_right_array.copy(),
            }

        # Append to internal undo stack
        self.undo_stack.append(state)

        # **Only update initial arrays and recalculate relative positions in normal mode**
        # In warp mode, we want to preserve the original relative positions
        if self.mode != "WARP":
            # **Update initial keyframe arrays to reflect the new state**
            self.initial_co_array = co_array.copy()
            self.initial_handle_left_array = handle_left_array.copy()
            self.initial_handle_right_array = handle_right_array.copy()

            # **Recalculate bounds and relative positions based on the new state**
            self.initial_bounds = self.get_initial_bounds()
            self.compute_relative_positions()

    def pop_undo(self, context):
        """Pop the last state from the undo stack and restore keyframes and control points."""
        # If there's only one state in the stack, we can't undo further
        if len(self.undo_stack) < 2:
            self.report({"INFO"}, "Nothing to undo")
            return

        # Pop the last state
        self.undo_stack.pop()

        # Now the previous state is the one to restore
        state = self.undo_stack[-1]

        # Restore keyframes
        co_array = state["co_array"]
        handle_left_array = state["handle_left_array"]
        handle_right_array = state["handle_right_array"]

        for i in range(len(self.indices_array)):
            fcurve = self.fcurves_array[i]
            index = self.indices_array[i]
            is_rotation_curve = self.is_rotation_curve_array[i]
            kf = fcurve.keyframe_points[index]
            kf.co[0] = co_array[i][0]
            kf.co[1] = radians(co_array[i][1]) if is_rotation_curve else co_array[i][1]
            kf.handle_left[0] = handle_left_array[i][0]
            kf.handle_left[1] = radians(handle_left_array[i][1]) if is_rotation_curve else handle_left_array[i][1]
            kf.handle_right[0] = handle_right_array[i][0]
            kf.handle_right[1] = radians(handle_right_array[i][1]) if is_rotation_curve else handle_right_array[i][1]

        # Restore complete control point structure
        if "regular_control_points" in state and "loop_control_points" in state:
            # New format with complete control point data
            self.control_points = []
            self.loop_control_points = []

            # Restore regular control points
            for cp_data in state["regular_control_points"]:
                cp = ControlPoint(
                    cp_data["index"],
                    (cp_data["position"][0], cp_data["position"][1]),
                    self,
                    shape=cp_data["shape"],
                    section=cp_data["section"],
                )
                self.control_points.append(cp)

            # Create a lookup dict for associated control points
            cp_lookup = {cp.index: cp for cp in self.control_points}

            # Restore loop control points
            for lcp_data in state["loop_control_points"]:
                associated_cp = None
                if lcp_data["associated_cp_index"] is not None:
                    associated_cp = cp_lookup.get(lcp_data["associated_cp_index"])

                lcp = LoopControlPoint(
                    lcp_data["index"],
                    (lcp_data["position"][0], lcp_data["position"][1]),
                    self,
                    shape=lcp_data["shape"],
                    section=lcp_data["section"],
                    orientation=lcp_data["orientation"],
                    associated_cp=associated_cp,
                )
                self.loop_control_points.append(lcp)

            # Restore lattice configuration if available
            if "lattice_config" in state:
                config = state["lattice_config"]
                props = bpy.context.scene.keyframe_lattice_settings
                # Note: mode is now operator property, not scene property
                props.lattice_x = config["lattice_x"]
                props.lattice_y = config["lattice_y"]
                self.current_mode = config["current_mode"]
                self.previous_lattice_x = config["previous_lattice_x"]
                self.previous_lattice_y = config["previous_lattice_y"]

            # Restore initial bounds if available
            if "initial_bounds" in state:
                self.initial_bounds = state["initial_bounds"]

        else:
            # Legacy format compatibility - restore using old method
            control_point_indices = state.get("control_point_indices", [])
            control_point_positions = state.get("control_point_positions", [])
            for idx, pos in zip(control_point_indices, control_point_positions):
                cp = next((cp for cp in self.control_points + self.loop_control_points if cp.index == idx), None)
                if cp:
                    cp.position = (pos[0], pos[1])

        # Update initial keyframe arrays to reflect restored state
        if self.mode != "WARP":
            self.initial_co_array = co_array.copy()
            self.initial_handle_left_array = handle_left_array.copy()
            self.initial_handle_right_array = handle_right_array.copy()

            # Update initial bounds and recompute relative positions
            self.initial_bounds = self.get_initial_bounds()
            self.compute_relative_positions()

            # In normal mode, recreate control points based on restored keyframe arrays
            self.init_control_points(context)

        # Trigger UI redraw
        context.area.tag_redraw()

    def init_control_points(self, context):
        min_x, max_x, min_y, max_y = self.initial_bounds
        props = bpy.context.scene.keyframe_lattice_settings
        lattice_x = props.lattice_x
        lattice_y = props.lattice_y

        self.control_points = []
        self.loop_control_points = []

        if self.mode == "WARP":
            # Create grid based on lattice_x and lattice_y
            index_counter = 0
            for row in range(lattice_y + 1):
                for col in range(lattice_x + 1):

                    # Calculate normalized positions
                    u = col / lattice_x if lattice_x != 0 else 0.0
                    v = row / lattice_y if lattice_y != 0 else 0.0

                    # Calculate graph positions
                    x = min_x + u * (max_x - min_x)
                    y = min_y + v * (max_y - min_y)
                    index = index_counter
                    index_counter += 1
                    self.control_points.append(ControlPoint(index, (x, y), self, shape="circle", section=(row, col)))

            # Create LoopControlPoints outside the grid with fixed screen space offset
            lcp_index_counter = 1000  # Start index after all control points
            offset_pixels = 20  # Fixed offset in screen space (pixels)

            # Precompute the offset in graph space for horizontal and vertical LCPs
            # We'll use average scaling for simplicity.
            avg_scale_x = (max_x - min_x) / context.region.width
            avg_scale_y = (max_y - min_y) / context.region.height

            # Loop through each CP to create associated LCPs
            for row in range(lattice_y + 1):
                for col in range(lattice_x + 1):
                    cp = self.control_points[row * (lattice_x + 1) + col]
                    cp_x, cp_y = cp.position

                    # Convert CP position to screen space
                    screen_x, screen_y = self.graph_to_screen(cp_x, cp_y)

                    # Left LCPs
                    if col == 0:
                        # Left edge, create LCP to the left
                        lcp_screen_x = screen_x - offset_pixels
                        lcp_screen_y = screen_y
                        lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                        index = lcp_index_counter
                        lcp_index_counter += 1
                        self.loop_control_points.append(
                            LoopControlPoint(
                                index,
                                (lcp_x, lcp_y),
                                self,
                                orientation="horizontal",
                                section=("row", row),
                                associated_cp=cp,
                            )
                        )
                    # Right LCPs
                    if col == lattice_x:
                        # Right edge, create LCP to the right
                        lcp_screen_x = screen_x + offset_pixels
                        lcp_screen_y = screen_y
                        lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                        index = lcp_index_counter
                        lcp_index_counter += 1
                        self.loop_control_points.append(
                            LoopControlPoint(
                                index,
                                (lcp_x, lcp_y),
                                self,
                                orientation="horizontal",
                                section=("row", row),
                                associated_cp=cp,
                            )
                        )

                    # Bottom LCPs
                    if row == 0:
                        # Bottom edge, create LCP below
                        lcp_screen_x = screen_x
                        lcp_screen_y = screen_y - offset_pixels
                        lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                        index = lcp_index_counter
                        lcp_index_counter += 1
                        self.loop_control_points.append(
                            LoopControlPoint(
                                index,
                                (lcp_x, lcp_y),
                                self,
                                orientation="vertical",
                                section=("col", col),
                                associated_cp=cp,
                            )
                        )
                    # Top LCPs
                    if row == lattice_y:
                        # Top edge, create LCP above
                        lcp_screen_x = screen_x
                        lcp_screen_y = screen_y + offset_pixels
                        lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                        index = lcp_index_counter
                        lcp_index_counter += 1
                        self.loop_control_points.append(
                            LoopControlPoint(
                                index,
                                (lcp_x, lcp_y),
                                self,
                                orientation="vertical",
                                section=("col", col),
                                associated_cp=cp,
                            )
                        )
        else:
            # Existing normal mode control points
            positions = [
                (0, (min_x, min_y)),  # Bottom-left corner
                (1, (max_x, min_y)),  # Bottom-right corner
                (2, (max_x, max_y)),  # Top-right corner
                (3, (min_x, max_y)),  # Top-left corner
                (4, ((min_x + max_x) / 2, min_y)),  # Midpoint of bottom edge
                (5, (max_x, (min_y + max_y) / 2)),  # Midpoint of right edge
                (6, ((min_x + max_x) / 2, max_y)),  # Midpoint of top edge
                (7, (min_x, (min_y + max_y) / 2)),  # Midpoint of left edge
                (8, ((min_x + max_x) / 2, (min_y + max_y) / 2)),  # Center point for moving entire box
            ]
            self.control_points = [
                ControlPoint(index, pos, self, shape="circle" if index == 8 else "square") for index, pos in positions
            ]

    def resize_warp_lattice(self, context, new_lattice_x, new_lattice_y):
        """Resize the warp lattice while preserving existing control point positions and keyframe relative positions."""
        old_lattice_x = self.previous_lattice_x
        old_lattice_y = self.previous_lattice_y

        # Store current control point positions by section coordinates
        old_cp_positions_by_section = {cp.section: cp.position for cp in self.control_points}

        # Restore keyframes to original state
        self.restore_to_original_state()

        # Create new orthogonal grid
        self.create_orthogonal_grid(new_lattice_x, new_lattice_y)

        # Compute relative positions for all keyframes in the new grid
        self.compute_relative_positions()

        # Apply preserved control point positions to new grid
        self.interpolate_control_points_to_deformed_positions_by_section(
            old_cp_positions_by_section, old_lattice_x, old_lattice_y, new_lattice_x, new_lattice_y
        )

        # Update keyframes based on the new deformed control point positions
        self.dragging_control_point = 0  # Set a dummy control point as being dragged
        self.update_bounding_box_and_keyframes(context)
        self.dragging_control_point = None  # Reset dragging state

        # Push state to undo stack
        # self.push_undo(context)

    def restore_to_original_state(self):
        """Restore all keyframes to their original positions."""
        for i in range(len(self.indices_array)):
            fcurve = self.fcurves_array[i]
            index = self.indices_array[i]
            is_rotation_curve = self.is_rotation_curve_array[i]
            kf = fcurve.keyframe_points[index]

            # Restore original positions
            original_x, original_y = self.initial_co_array[i]
            original_handle_left_x, original_handle_left_y = self.initial_handle_left_array[i]
            original_handle_right_x, original_handle_right_y = self.initial_handle_right_array[i]

            kf.co[0] = original_x
            kf.co[1] = radians(original_y) if is_rotation_curve else original_y
            kf.handle_left[0] = original_handle_left_x
            kf.handle_left[1] = radians(original_handle_left_y) if is_rotation_curve else original_handle_left_y
            kf.handle_right[0] = original_handle_right_x
            kf.handle_right[1] = radians(original_handle_right_y) if is_rotation_curve else original_handle_right_y

    def create_orthogonal_grid(self, lattice_x, lattice_y):
        """Create an orthogonal grid of control points based on initial bounds."""
        min_x, max_x, min_y, max_y = self.initial_bounds

        self.control_points = []
        self.loop_control_points = []

        # Create grid control points
        index_counter = 0
        for row in range(lattice_y + 1):
            for col in range(lattice_x + 1):
                # Calculate normalized positions
                u = col / lattice_x if lattice_x != 0 else 0.0
                v = row / lattice_y if lattice_y != 0 else 0.0

                # Calculate graph positions
                x = min_x + u * (max_x - min_x)
                y = min_y + v * (max_y - min_y)

                self.control_points.append(
                    ControlPoint(index_counter, (x, y), self, shape="circle", section=(row, col))
                )
                index_counter += 1

        # Create loop control points
        self.create_loop_control_points_for_grid(lattice_x, lattice_y, self.control_points)

    def interpolate_control_points_to_deformed_positions_by_section(
        self, old_cp_positions_by_section, old_lattice_x, old_lattice_y, new_lattice_x, new_lattice_y
    ):
        """Preserve existing control point positions and interpolate new ones."""
        # For each control point in the new grid, calculate its position based on the old deformed grid
        for cp in self.control_points:
            row, col = cp.section
            cp.position = self.calculate_grid_position(
                row, col, new_lattice_x, new_lattice_y, old_lattice_x, old_lattice_y, old_cp_positions_by_section
            )

        # Update loop control points to match their associated control points
        self.update_loop_control_points_positions()

    def update_loop_control_points_positions(self):
        """Update loop control point positions based on their associated control points."""
        offset_pixels = 20

        for lcp in self.loop_control_points:
            if hasattr(lcp, "associated_cp") and lcp.associated_cp:
                cp_x, cp_y = lcp.associated_cp.position
                screen_x, screen_y = self.graph_to_screen(cp_x, cp_y)

                if lcp.orientation == "horizontal":
                    if lcp.section[0] == "row":
                        row = lcp.section[1]
                        # Check if this is left or right edge
                        if lcp.associated_cp.section[1] == 0:  # Left edge
                            lcp_screen_x = screen_x - offset_pixels
                            lcp_screen_y = screen_y
                        else:  # Right edge
                            lcp_screen_x = screen_x + offset_pixels
                            lcp_screen_y = screen_y
                else:  # vertical
                    if lcp.section[0] == "col":
                        col = lcp.section[1]
                        # Check if this is top or bottom edge
                        if lcp.associated_cp.section[0] == 0:  # Bottom edge
                            lcp_screen_x = screen_x
                            lcp_screen_y = screen_y - offset_pixels
                        else:  # Top edge
                            lcp_screen_x = screen_x
                            lcp_screen_y = screen_y + offset_pixels

                lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                lcp.position = (lcp_x, lcp_y)

    def calculate_grid_position(self, row, col, new_x, new_y, old_x, old_y, old_cp_positions_by_section):
        """Calculate the position of a new grid point based on the old deformed grid using section coordinates."""
        # Convert new grid coordinates to normalized coordinates (0-1)
        u = col / new_x if new_x > 0 else 0.0
        v = row / new_y if new_y > 0 else 0.0

        # Handle case where old grid doesn't exist or is invalid
        if old_x == 0 or old_y == 0 or not old_cp_positions_by_section:
            # Fallback to default bounds
            min_x, max_x, min_y, max_y = self.initial_bounds
            x = min_x + u * (max_x - min_x)
            y = min_y + v * (max_y - min_y)
            return (x, y)

        # Map to old grid space
        old_col_exact = u * old_x
        old_row_exact = v * old_y

        # Get integer grid coordinates
        old_col_0 = max(0, min(int(old_col_exact), old_x - 1))
        old_row_0 = max(0, min(int(old_row_exact), old_y - 1))
        old_col_1 = min(old_col_0 + 1, old_x)
        old_row_1 = min(old_row_0 + 1, old_y)

        # Calculate interpolation weights
        col_weight = old_col_exact - old_col_0
        row_weight = old_row_exact - old_row_0

        # Get the four corner sections for bilinear interpolation
        p00_pos = old_cp_positions_by_section.get((old_row_0, old_col_0))
        p10_pos = old_cp_positions_by_section.get((old_row_0, old_col_1))
        p01_pos = old_cp_positions_by_section.get((old_row_1, old_col_0))
        p11_pos = old_cp_positions_by_section.get((old_row_1, old_col_1))

        # If any corner is missing, we can't reliably interpolate.
        # This can happen at the edges when the grid size changes.
        # A robust fallback is needed. For now, let's check and log.
        if not all([p00_pos, p10_pos, p01_pos, p11_pos]):
            # Fallback for edges and corners where one of the points might not exist in the old grid
            # Let's try to find the closest existing point or use the initial bounds
            min_x, max_x, min_y, max_y = self.initial_bounds
            if (row, col) in old_cp_positions_by_section:
                return old_cp_positions_by_section[(row, col)]
            else:
                # Fallback to orthogonal position if we can't interpolate
                return (min_x + u * (max_x - min_x), min_y + v * (max_y - min_y))

        p00, p10, p01, p11 = p00_pos, p10_pos, p01_pos, p11_pos

        # Perform bilinear interpolation
        # Interpolate along x-axis first
        bottom_x = p00[0] * (1 - col_weight) + p10[0] * col_weight
        bottom_y = p00[1] * (1 - col_weight) + p10[1] * col_weight
        top_x = p01[0] * (1 - col_weight) + p11[0] * col_weight
        top_y = p01[1] * (1 - col_weight) + p11[1] * col_weight

        # Interpolate along y-axis
        final_x = bottom_x * (1 - row_weight) + top_x * row_weight
        final_y = bottom_y * (1 - row_weight) + top_y * row_weight

        return (final_x, final_y)

    def create_loop_control_points_for_grid(self, lattice_x, lattice_y, control_points):
        """Create loop control points for the grid."""
        self.loop_control_points = []
        lcp_index_counter = 1000
        offset_pixels = 20

        for row in range(lattice_y + 1):
            for col in range(lattice_x + 1):
                cp = control_points[row * (lattice_x + 1) + col]
                cp_x, cp_y = cp.position
                screen_x, screen_y = self.graph_to_screen(cp_x, cp_y)

                # Left LCPs
                if col == 0:
                    lcp_screen_x = screen_x - offset_pixels
                    lcp_screen_y = screen_y
                    lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                    self.loop_control_points.append(
                        LoopControlPoint(
                            lcp_index_counter,
                            (lcp_x, lcp_y),
                            self,
                            orientation="horizontal",
                            section=("row", row),
                            associated_cp=cp,
                        )
                    )
                    lcp_index_counter += 1

                # Right LCPs
                if col == lattice_x:
                    lcp_screen_x = screen_x + offset_pixels
                    lcp_screen_y = screen_y
                    lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                    self.loop_control_points.append(
                        LoopControlPoint(
                            lcp_index_counter,
                            (lcp_x, lcp_y),
                            self,
                            orientation="horizontal",
                            section=("row", row),
                            associated_cp=cp,
                        )
                    )
                    lcp_index_counter += 1

                # Bottom LCPs
                if row == 0:
                    lcp_screen_x = screen_x
                    lcp_screen_y = screen_y - offset_pixels
                    lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                    self.loop_control_points.append(
                        LoopControlPoint(
                            lcp_index_counter,
                            (lcp_x, lcp_y),
                            self,
                            orientation="vertical",
                            section=("col", col),
                            associated_cp=cp,
                        )
                    )
                    lcp_index_counter += 1

                # Top LCPs
                if row == lattice_y:
                    lcp_screen_x = screen_x
                    lcp_screen_y = screen_y + offset_pixels
                    lcp_x, lcp_y = self.screen_to_graph(lcp_screen_x, lcp_screen_y)
                    self.loop_control_points.append(
                        LoopControlPoint(
                            lcp_index_counter,
                            (lcp_x, lcp_y),
                            self,
                            orientation="vertical",
                            section=("col", col),
                            associated_cp=cp,
                        )
                    )
                    lcp_index_counter += 1

    def compute_bilinear_coordinates(self, x, y, cp_bl, cp_br, cp_tl, cp_tr):
        """Compute bilinear coordinates (u, v) for a point within a quad defined by four control points."""
        # Use iterative method to solve for bilinear coordinates
        # Start with initial guess
        u, v = 0.5, 0.5

        # Iterative solver (Newton-Raphson method)
        for _ in range(10):  # Max 10 iterations
            # Bilinear interpolation
            p = (
                (1 - u) * (1 - v) * cp_bl[0] + u * (1 - v) * cp_br[0] + u * v * cp_tr[0] + (1 - u) * v * cp_tl[0],
                (1 - u) * (1 - v) * cp_bl[1] + u * (1 - v) * cp_br[1] + u * v * cp_tr[1] + (1 - u) * v * cp_tl[1],
            )

            # Error vector
            dx = x - p[0]
            dy = y - p[1]

            # If error is small enough, we're done
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                break

            # Compute Jacobian
            dpdx_du = -(1 - v) * cp_bl[0] + (1 - v) * cp_br[0] - v * cp_tl[0] + v * cp_tr[0]
            dpdy_du = -(1 - v) * cp_bl[1] + (1 - v) * cp_br[1] - v * cp_tl[1] + v * cp_tr[1]
            dpdx_dv = -(1 - u) * cp_bl[0] - u * cp_br[0] + (1 - u) * cp_tl[0] + u * cp_tr[0]
            dpdy_dv = -(1 - u) * cp_bl[1] - u * cp_br[1] + (1 - u) * cp_tl[1] + u * cp_tr[1]

            # Determinant
            det = dpdx_du * dpdy_dv - dpdy_du * dpdx_dv

            if abs(det) < 1e-10:  # Avoid division by zero
                break

            # Newton-Raphson update
            du = (dx * dpdy_dv - dy * dpdx_dv) / det
            dv = (dy * dpdx_du - dx * dpdy_du) / det

            u += du
            v += dv

            # Clamp to reasonable bounds
            u = max(0.0, min(1.0, u))
            v = max(0.0, min(1.0, v))

        return u, v

    def modal(self, context, event):
        if not self._is_running:
            return {"CANCELLED"}

        props = bpy.context.scene.keyframe_lattice_settings
        screen = context.screen

        # Check if lattice properties were updated from UI (only in WARP mode)
        if self.mode == "WARP" and context.scene.get("lattice_needs_update", False):
            context.scene["lattice_needs_update"] = False
            # Handle lattice dimension changes while preserving existing deformation
            self.resize_warp_lattice(context, props.lattice_x, props.lattice_y)
            self.previous_lattice_x = props.lattice_x
            self.previous_lattice_y = props.lattice_y
            # self.push_undo(context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # Handle lattice dimension changes in WARP mode
        if self.mode == "WARP" and (
            props.lattice_x != self.previous_lattice_x or props.lattice_y != self.previous_lattice_y
        ):
            # Handle lattice dimension changes while preserving existing deformation
            self.resize_warp_lattice(context, props.lattice_x, props.lattice_y)
            # self.push_undo(context)
            context.area.tag_redraw()

        self.previous_lattice_x = props.lattice_x
        self.previous_lattice_y = props.lattice_y

        if event.type == "ESC" and event.value == "PRESS" and screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=True)
            return {"RUNNING_MODAL"}

        if event.type == "ESC" and event.value == "PRESS":

            return self.cancel(context)

        if (
            event.type in {"RET"}
            and event.value == "PRESS"
            or (event.type == "Y" and event.shift and event.value == "PRESS")
        ):
            # Finish operation normally

            for fcurve in self.fcurves_to_update:
                fcurve.update()
            return self.finish(context)

        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            bpy.ops.wm.call_panel(name="AMP_PT_AnimLatticeOptions", keep_open=True)
            context.window.cursor_set("DEFAULT")
            return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":

            if (
                not self.context
                or not getattr(self.context, "region", None)
                or not getattr(self.context.region, "view2d", None)
            ):
                return self.cancel(context)
            self.mouse_x = event.mouse_region_x
            self.mouse_y = event.mouse_region_y
            self.mouse_graph_x, self.mouse_graph_y = self.screen_to_graph(self.mouse_x, self.mouse_y)
            if self.dragging_control_point is not None:
                self.handle_mouse_move_drag(context, event)
            else:
                self.handle_mouse_move_hover(context, event)
            context.area.tag_redraw()
            return {"PASS_THROUGH"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            for cp in self.control_points + self.loop_control_points:
                if cp.is_hovered:
                    context.window.cursor_set("SCROLL_XY")
                    self.dragging_control_point = cp.index
                    self.initial_mouse_x = event.mouse_region_x
                    self.initial_mouse_y = event.mouse_region_y
                    self.initial_mouse_graph_x, self.initial_mouse_graph_y = self.screen_to_graph(
                        self.initial_mouse_x, self.initial_mouse_y
                    )
                    self.initial_control_point_positions = {
                        cp_.index: cp_.position for cp_ in self.control_points + self.loop_control_points
                    }
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            context.window.cursor_set("DEFAULT")
            if self.dragging_control_point is not None:
                self.dragging_control_point = None
                self.push_undo(context)
                # Only reinitialize control points in normal mode, not in warp mode
                if self.mode != "WARP":
                    self.init_control_points(context)
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == "H" and event.value == "PRESS":
            prefs = bpy.context.preferences.addons[base_package].preferences
            prefs.timeline_gui_toggle = not prefs.timeline_gui_toggle
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if (event.type == "Z" and (event.ctrl or event.oskey)) and event.value == "PRESS":
            self.pop_undo(context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # Lattice dimension controls (only in warp mode)
        if self.mode == "WARP":
            # Add/Remove columns
            if event.type == "EQUAL" and event.value == "PRESS":  # Plus key
                if event.shift:  # Add row
                    props.lattice_y = min(props.lattice_y + 1, 10)  # Limit to reasonable max
                else:  # Add column
                    props.lattice_x = min(props.lattice_x + 1, 10)  # Limit to reasonable max
                return {"RUNNING_MODAL"}

            if event.type == "MINUS" and event.value == "PRESS":  # Minus key
                if event.shift:  # Remove row
                    props.lattice_y = max(props.lattice_y - 1, 1)  # Minimum 1 row
                else:  # Remove column
                    props.lattice_x = max(props.lattice_x - 1, 1)  # Minimum 1 column
                return {"RUNNING_MODAL"}

        self.previous_lattice_x = props.lattice_x
        self.previous_lattice_y = props.lattice_y

        context.area.tag_redraw()
        return {"PASS_THROUGH"}

    def handle_mouse_move_hover(self, context, event):
        hovered_any = False
        for cp in self.control_points + self.loop_control_points:
            if cp.check_hover(self.mouse_x, self.mouse_y):
                hovered_any = True

    def handle_mouse_move_drag(self, context, event):
        cp = next(
            (cp_ for cp_ in self.control_points + self.loop_control_points if cp_.index == self.dragging_control_point),
            None,
        )
        if not cp:
            return

        props = bpy.context.scene.keyframe_lattice_settings
        delta_x = self.mouse_graph_x - self.initial_mouse_graph_x
        delta_y = self.mouse_graph_y - self.initial_mouse_graph_y
        lock_active = event.shift or props.lock_direction

        if lock_active and self.mode == "WARP":
            dx = self.mouse_x - self.initial_mouse_x
            dy = self.mouse_y - self.initial_mouse_y
            if abs(dx) > abs(dy):
                delta_y = 0
            else:
                delta_x = 0

        if self.mode == "WARP":
            self.handle_drag_warp(cp, delta_x, delta_y)
        else:
            self.handle_drag_normal(cp, delta_x, delta_y)

        self.update_bounding_box_and_keyframes(context)

    def handle_drag_warp(self, cp, delta_x, delta_y):
        props = bpy.context.scene.keyframe_lattice_settings
        if isinstance(cp, LoopControlPoint):
            if cp.orientation == "vertical":
                col = cp.section[1]
                affected = [p for p in self.control_points if p.section[1] == col]
            else:
                row = cp.section[1]
                affected = [p for p in self.control_points if p.section[0] == row]
            for p in affected:
                ix, iy = self.initial_control_point_positions[p.index]
                p.position = (ix + delta_x, iy + delta_y)
            for p in affected:
                assoc = [lcp for lcp in self.loop_control_points if lcp.associated_cp == p]
                for lcp in assoc:
                    icp_x, icp_y = self.initial_control_point_positions[p.index]
                    ilcp_x, ilcp_y = self.initial_control_point_positions[lcp.index]
                    ox = ilcp_x - icp_x
                    oy = ilcp_y - icp_y
                    lcp.position = (p.position[0] + ox, p.position[1] + oy)
        else:
            ix, iy = self.initial_control_point_positions[cp.index]
            cp.position = (ix + delta_x, iy + delta_y)
            assoc = [lcp for lcp in self.loop_control_points if lcp.associated_cp == cp]
            for lcp in assoc:
                icp_x, icp_y = self.initial_control_point_positions[cp.index]
                ilcp_x, ilcp_y = self.initial_control_point_positions[lcp.index]
                ox = ilcp_x - icp_x
                oy = ilcp_y - icp_y
                lcp.position = (cp.position[0] + ox, cp.position[1] + oy)

    def handle_drag_normal(self, cp, delta_x, delta_y):
        if cp.index == 8:  # Center control point - move entire box
            # Move all control points by the same delta
            for other_cp in self.control_points:
                if other_cp.index != 8:  # Don't move center point based on itself
                    ix, iy = self.initial_control_point_positions[other_cp.index]
                    other_cp.position = (ix + delta_x, iy + delta_y)
            # Move center point
            ix, iy = self.initial_control_point_positions[cp.index]
            cp.position = (ix + delta_x, iy + delta_y)
        else:
            # Normal control point behavior with movement constraints for middle points
            ix, iy = self.initial_control_point_positions[cp.index]

            # Constrain movement for middle control points
            if cp.index == 4 or cp.index == 6:  # Bottom middle (4) or Top middle (6)
                # Only allow vertical movement
                cp.position = (ix, iy + delta_y)
            elif cp.index == 5 or cp.index == 7:  # Right middle (5) or Left middle (7)
                # Only allow horizontal movement
                cp.position = (ix + delta_x, iy)
            else:
                # Corner points can move freely
                cp.position = (ix + delta_x, iy + delta_y)

        # Handle associated loop control points
        assoc = [lcp for lcp in self.loop_control_points if lcp.associated_cp == cp]
        for lcp in assoc:
            icp_x, icp_y = self.initial_control_point_positions[cp.index]
            ilcp_x, ilcp_y = self.initial_control_point_positions[lcp.index]
            ox = ilcp_x - icp_x
            oy = ilcp_y - icp_y
            lcp.position = (cp.position[0] + ox, cp.position[1] + oy)

    def execute(self, context):
        obj = context.active_object
        # self.offset = get_nla_strip_offset(obj)
        if not self.__class__._is_running:

            self.initial_use_normalization = context.space_data.use_normalization
            if self.initial_use_normalization:
                context.space_data.use_normalization = False

                # Zoom out to fit all keyframes in the view
                bpy.ops.graph.view_selected()

                for _ in range(self.zoom_out_times):
                    bpy.ops.view2d.zoom_out()

            result = self.init_tool(context)
            if result == {"CANCELLED"}:
                self.cancel(context)
                return {"CANCELLED"}
            context.window_manager.modal_handler_add(self)
            self.__class__._is_running = True
            self.__class__._current_mode = self.mode  # Store the current mode
            return {"RUNNING_MODAL"}
        else:
            # Operator is already running, cancel it
            self.__class__._is_running = False
            self.__class__._current_mode = None  # Clear the current mode
            return self.cancel(context)

    def finish(self, context):
        """Finish the operation successfully - restore settings and cleanup."""
        # Clean up the lattice update flag
        if "lattice_needs_update" in context.scene:
            del context.scene["lattice_needs_update"]

        # Restore cursor to default and make it visible
        context.window.cursor_set("DEFAULT")
        context.window.cursor_modal_restore()

        if self.initial_use_normalization:
            context.space_data.use_normalization = True

        # Apply slice to full frames if enabled
        props = bpy.context.scene.keyframe_lattice_settings
        if props.slice_to_full_frames:
            try:
                bpy.ops.anim.amp_anim_slicer(
                    insertion_type="CLOSEST_FULL_FRAME",
                    selection_mode="ALL_CURVES",
                    range_options="SCENE",
                    clear_others=True,
                    key_available=True,
                    key_location=False,
                    key_rotation=False,
                    key_scale=False,
                    key_custom=False,
                    kf_on_first=False,
                    kf_on_last=False,
                    clear_markers=False,
                )
            except:
                # Ignore errors if slicer is not available
                pass

        self.__class__._is_running = False
        self.__class__._current_mode = None  # Clear the current mode
        if self._handle is not None:
            bpy.types.SpaceGraphEditor.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        # Force redraw all areas to ensure draw callback removal is updated everywhere
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return {"FINISHED"}

    def cancel(self, context):
        """Cancel the operation - restore settings and cleanup."""
        # Clean up the lattice update flag
        if "lattice_needs_update" in context.scene:
            del context.scene["lattice_needs_update"]

        # Restore cursor to default and make it visible
        context.window.cursor_set("DEFAULT")
        context.window.cursor_modal_restore()

        if self.initial_use_normalization:
            context.space_data.use_normalization = True

        # Restore keyframes and control points to their initial state using internal undo buffer
        if self.undo_stack:
            # Get the first state (initial state) from the undo stack
            initial_state = self.undo_stack[0]

            # Restore keyframes to initial positions
            co_array = initial_state["co_array"]
            handle_left_array = initial_state["handle_left_array"]
            handle_right_array = initial_state["handle_right_array"]

            for i in range(len(self.indices_array)):
                fcurve = self.fcurves_array[i]
                index = self.indices_array[i]
                is_rotation_curve = self.is_rotation_curve_array[i]
                kf = fcurve.keyframe_points[index]
                kf.co[0] = co_array[i][0]
                kf.co[1] = radians(co_array[i][1]) if is_rotation_curve else co_array[i][1]
                kf.handle_left[0] = handle_left_array[i][0]
                kf.handle_left[1] = radians(handle_left_array[i][1]) if is_rotation_curve else handle_left_array[i][1]
                kf.handle_right[0] = handle_right_array[i][0]
                kf.handle_right[1] = (
                    radians(handle_right_array[i][1]) if is_rotation_curve else handle_right_array[i][1]
                )

            # Restore control points to initial state
            if "regular_control_points" in initial_state and "loop_control_points" in initial_state:
                # New format with complete control point data
                self.control_points = []
                self.loop_control_points = []

                # Restore regular control points
                for cp_data in initial_state["regular_control_points"]:
                    cp = ControlPoint(
                        cp_data["index"],
                        (cp_data["position"][0], cp_data["position"][1]),
                        self,
                        shape=cp_data["shape"],
                        section=cp_data["section"],
                    )
                    self.control_points.append(cp)

                # Create a lookup dict for associated control points
                cp_lookup = {cp.index: cp for cp in self.control_points}

                # Restore loop control points
                for lcp_data in initial_state["loop_control_points"]:
                    associated_cp = None
                    if lcp_data["associated_cp_index"] is not None:
                        associated_cp = cp_lookup.get(lcp_data["associated_cp_index"])

                    lcp = LoopControlPoint(
                        lcp_data["index"],
                        (lcp_data["position"][0], lcp_data["position"][1]),
                        self,
                        shape=lcp_data["shape"],
                        section=lcp_data["section"],
                        orientation=lcp_data["orientation"],
                        associated_cp=associated_cp,
                    )
                    self.loop_control_points.append(lcp)

                # Restore lattice configuration if available
                if "lattice_config" in initial_state:
                    config = initial_state["lattice_config"]
                    props = bpy.context.scene.keyframe_lattice_settings
                    # Note: mode is now operator property, not scene property
                    props.lattice_x = config["lattice_x"]
                    props.lattice_y = config["lattice_y"]
                    self.current_mode = config["current_mode"]
                    self.previous_lattice_x = config["previous_lattice_x"]
                    self.previous_lattice_y = config["previous_lattice_y"]

                # Restore initial bounds if available
                if "initial_bounds" in initial_state:
                    self.initial_bounds = initial_state["initial_bounds"]

        self.__class__._is_running = False
        self.__class__._current_mode = None  # Clear the current mode
        if self._handle is not None:
            bpy.types.SpaceGraphEditor.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None

        refresh_ui(context)

        return {"CANCELLED"}

    def draw(self, context):
        layout = self.layout
        props = bpy.context.scene.keyframe_lattice_settings

        # Show current mode (read-only)
        layout.label(text=f"Mode: {self.mode}")

        if self.mode == "WARP":
            layout.prop(props, "lattice_x", text="Columns")
            layout.prop(props, "lattice_y", text="Rows")
        layout.prop(props, "lock_direction", text="Lock Direction")

    def draw_callback(self, _self, context):
        # Safety check: if operator instance is no longer valid, don't draw anything
        try:
            # Try to access operator properties to check if instance is still valid
            mode = self.mode
            initial_bounds = self.initial_bounds
            control_points = self.control_points
        except (ReferenceError, AttributeError):
            # Operator instance has been removed or attributes are not available, stop drawing
            return

        props = bpy.context.scene.keyframe_lattice_settings
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")

        if mode == "WARP":
            lattice_x = props.lattice_x
            lattice_y = props.lattice_y
            min_x, max_x, min_y, max_y = initial_bounds

            cp_positions = {cp.index: cp.position for cp in control_points}

            # Draw vertical and horizontal grid lines
            for row in range(lattice_y + 1):
                for col in range(lattice_x):
                    start_cp_index = row * (lattice_x + 1) + col
                    end_cp_index = row * (lattice_x + 1) + (col + 1)
                    if start_cp_index in cp_positions and end_cp_index in cp_positions:
                        start_pos = self.graph_to_screen(*cp_positions[start_cp_index])
                        end_pos = self.graph_to_screen(*cp_positions[end_cp_index])
                        batch_obj = batch_for_shader(shader, "LINES", {"pos": [start_pos, end_pos]})
                        shader.bind()
                        shader.uniform_float("color", (0.5, 0.5, 0.5, 0.5))
                        batch_obj.draw(shader)

            for col in range(lattice_x + 1):
                for row in range(lattice_y):
                    start_cp_index = row * (lattice_x + 1) + col
                    end_cp_index = (row + 1) * (lattice_x + 1) + col
                    if start_cp_index in cp_positions and end_cp_index in cp_positions:
                        start_pos = self.graph_to_screen(*cp_positions[start_cp_index])
                        end_pos = self.graph_to_screen(*cp_positions[end_cp_index])
                        batch_obj = batch_for_shader(shader, "LINES", {"pos": [start_pos, end_pos]})
                        shader.bind()
                        shader.uniform_float("color", (0.5, 0.5, 0.5, 0.5))
                        batch_obj.draw(shader)

        # Draw the rectangle (bounding box)
        if mode != "WARP":
            corner_indices = [0, 1, 2, 3]
            vertices = [
                self.graph_to_screen(*control_points[i].position) for i in corner_indices if i < len(control_points)
            ]

            shader.bind()
            shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
            batch_obj = batch_for_shader(shader, "LINE_LOOP", {"pos": vertices})
            batch_obj.draw(shader)
            # Explicitly draw the left edge (between bottom-left and top-left)
            if len(vertices) == 4:
                batch_left = batch_for_shader(shader, "LINES", {"pos": [vertices[0], vertices[3]]})
                batch_left.draw(shader)

        # Draw control points
        for cp in control_points + getattr(self, "loop_control_points", []):
            cp.draw()

        # Draw help text
        text_x, text_y = 30, 40
        draw_gui_help_text(context, text_x, text_y, self)

        gpu.state.blend_set("NONE")

    def collect_initial_keyframe_data(self):
        """Collect initial keyframe data and store in NumPy arrays."""
        self.initial_selected_keyframes = []  # Initialize the list
        selected_fcurves = bpy.context.selected_editable_fcurves
        props = bpy.context.scene.keyframe_lattice_settings
        self.fcurves_to_update = set()

        # Lists to collect data before converting to NumPy arrays
        fcurves_list = []
        indices_list = []
        is_rotation_curve_list = []
        initial_co_list = []
        initial_handle_left_list = []
        initial_handle_right_list = []
        relative_co_cell_list = []
        relative_handle_left_cell_list = []
        relative_handle_right_cell_list = []

        for fcurve in selected_fcurves:
            for idx, kf in enumerate(fcurve.keyframe_points):
                if kf.select_control_point:
                    self.fcurves_to_update.add(fcurve)

                    is_rotation_curve = is_fcurve_in_radians(fcurve)

                    if is_rotation_curve:
                        y_value = math.degrees(kf.co[1])
                        handle_left_y = math.degrees(kf.handle_left[1])
                        handle_right_y = math.degrees(kf.handle_right[1])
                    else:
                        y_value = kf.co[1]
                        handle_left_y = kf.handle_left[1]
                        handle_right_y = kf.handle_right[1]

                    fcurves_list.append(fcurve)
                    indices_list.append(idx)
                    is_rotation_curve_list.append(is_rotation_curve)
                    initial_co_list.append([kf.co[0], y_value])
                    initial_handle_left_list.append([kf.handle_left[0], handle_left_y])
                    initial_handle_right_list.append([kf.handle_right[0], handle_right_y])

                    # Initialize relative positions with empty dicts
                    relative_co_cell_list.append({})
                    relative_handle_left_cell_list.append({})
                    relative_handle_right_cell_list.append({})

                    self.initial_selected_keyframes.append(kf)

        # Convert lists to NumPy arrays with high precision
        self.fcurves_array = np.array(fcurves_list, dtype=object)
        self.indices_array = np.array(indices_list, dtype=int)
        self.is_rotation_curve_array = np.array(is_rotation_curve_list, dtype=bool)
        self.initial_co_array = np.array(initial_co_list, dtype=np.float64)
        self.initial_handle_left_array = np.array(initial_handle_left_list, dtype=np.float64)
        self.initial_handle_right_array = np.array(initial_handle_right_list, dtype=np.float64)

        # These are lists of dicts; we keep them as is
        self.relative_co_cell_list = relative_co_cell_list
        self.relative_handle_left_cell_list = relative_handle_left_cell_list
        self.relative_handle_right_cell_list = relative_handle_right_cell_list

        # Initialize the list to store relative_keys per keyframe
        self.relative_keys = [None] * len(self.indices_array)

    def ensure_keyframe_spacing(self, new_positions):
        """
        Ensure keyframes maintain minimum spacing to prevent merging.
        This is especially important for subframes.
        """
        if len(new_positions) <= 1:
            return new_positions

        # Sort by position to check spacing
        sorted_indices = np.argsort(new_positions)
        adjusted_positions = new_positions.copy()

        for i in range(1, len(sorted_indices)):
            current_idx = sorted_indices[i]
            prev_idx = sorted_indices[i - 1]

            # Check if keyframes are too close
            distance = adjusted_positions[current_idx] - adjusted_positions[prev_idx]
            if abs(distance) < self.FRAME_EPSILON:
                # Add small epsilon to maintain spacing
                if distance >= 0:
                    adjusted_positions[current_idx] = adjusted_positions[prev_idx] + self.MIN_SUBFRAME_DISTANCE
                else:
                    adjusted_positions[current_idx] = adjusted_positions[prev_idx] - self.MIN_SUBFRAME_DISTANCE

        return adjusted_positions

    # def restore_initial_selection(self):
    #     pass

    def compute_relative_positions(self):
        min_x0, max_x0, min_y0, max_y0 = self.initial_bounds
        props = bpy.context.scene.keyframe_lattice_settings
        lattice_x = props.lattice_x
        lattice_y = props.lattice_y

        # Reset relative_keys when recomputing relative positions
        self.relative_keys = [None] * len(self.indices_array)

        if self.mode == "WARP":
            # WARP mode requires per-keyframe computations
            for i in range(len(self.indices_array)):
                init_x, init_y = self.initial_co_array[i]
                init_handle_left_x, init_handle_left_y = self.initial_handle_left_array[i]
                init_handle_right_x, init_handle_right_y = self.initial_handle_right_array[i]

                if lattice_x == 0 or lattice_y == 0:
                    # Avoid division by zero
                    continue

                # Determine which cell the keyframe belongs to
                col = min(int((init_x - min_x0) / (max_x0 - min_x0) * lattice_x), lattice_x - 1)
                row = min(int((init_y - min_y0) / (max_y0 - min_y0) * lattice_y), lattice_y - 1)

                # Calculate cell boundaries
                cell_min_x = min_x0 + (col / lattice_x) * (max_x0 - min_x0)
                cell_max_x = min_x0 + ((col + 1) / lattice_x) * (max_x0 - min_x0)
                cell_min_y = min_y0 + (row / lattice_y) * (max_y0 - min_y0)
                cell_max_y = min_y0 + ((row + 1) / lattice_y) * (max_y0 - min_y0)

                # Compute relative positions within the cell
                u = (init_x - cell_min_x) / (cell_max_x - cell_min_x) if cell_max_x != cell_min_x else 0.0
                v = (init_y - cell_min_y) / (cell_max_y - cell_min_y) if cell_max_y != cell_min_y else 0.0

                handle_left_u = (
                    (init_handle_left_x - cell_min_x) / (cell_max_x - cell_min_x) if cell_max_x != cell_min_x else 0.0
                )
                handle_left_v = (
                    (init_handle_left_y - cell_min_y) / (cell_max_y - cell_min_y) if cell_max_y != cell_min_y else 0.0
                )

                handle_right_u = (
                    (init_handle_right_x - cell_min_x) / (cell_max_x - cell_min_x) if cell_max_x != cell_min_x else 0.0
                )
                handle_right_v = (
                    (init_handle_right_y - cell_min_y) / (cell_max_y - cell_min_y) if cell_max_y != cell_min_y else 0.0
                )

                # Store relative positions in the lists
                self.relative_co_cell_list[i][(row, col)] = (u, v)
                self.relative_handle_left_cell_list[i][(row, col)] = (handle_left_u, handle_left_v)
                self.relative_handle_right_cell_list[i][(row, col)] = (handle_right_u, handle_right_v)
        else:
            # NORMAL mode
            denom_x = max_x0 - min_x0
            denom_y = max_y0 - min_y0

            if denom_x == 0:
                u_array = np.zeros(len(self.indices_array))
                handle_left_u_array = np.zeros(len(self.indices_array))
                handle_right_u_array = np.zeros(len(self.indices_array))
            else:
                u_array = (self.initial_co_array[:, 0] - min_x0) / denom_x
                handle_left_u_array = (self.initial_handle_left_array[:, 0] - min_x0) / denom_x
                handle_right_u_array = (self.initial_handle_right_array[:, 0] - min_x0) / denom_x

            if denom_y == 0:
                v_array = np.zeros(len(self.indices_array))
                handle_left_v_array = np.zeros(len(self.indices_array))
                handle_right_v_array = np.zeros(len(self.indices_array))
            else:
                v_array = (self.initial_co_array[:, 1] - min_y0) / denom_y
                handle_left_v_array = (self.initial_handle_left_array[:, 1] - min_y0) / denom_y
                handle_right_v_array = (self.initial_handle_right_array[:, 1] - min_y0) / denom_y

            # Store relative positions
            self.relative_co = np.column_stack((u_array, v_array))
            self.relative_handle_left = np.column_stack((handle_left_u_array, handle_left_v_array))
            self.relative_handle_right = np.column_stack((handle_right_u_array, handle_right_v_array))

    def get_initial_bounds(self):
        if len(self.initial_co_array) == 0:
            return None
        min_x = np.min(self.initial_co_array[:, 0])
        max_x = np.max(self.initial_co_array[:, 0])
        min_y = np.min(self.initial_co_array[:, 1])
        max_y = np.max(self.initial_co_array[:, 1])
        return min_x, max_x, min_y, max_y

    def update_bounding_box_and_keyframes(self, context):
        if self.dragging_control_point is None:
            return

        # Get initial bounds
        min_x0, max_x0, min_y0, max_y0 = self.initial_bounds
        props = bpy.context.scene.keyframe_lattice_settings

        # Get the positions of the control points
        cp_positions = {cp.index: cp.position for cp in self.control_points}

        if self.mode == "WARP":
            # Handle grid-based warp without clamping to initial bounds
            lattice_x = props.lattice_x
            lattice_y = props.lattice_y

            # Ensure lattice_x and lattice_y are greater than 0 to avoid division by zero
            if lattice_x == 0 or lattice_y == 0:
                self.report({"ERROR"}, "Lattice divisions must be greater than 0 in WARP mode.")
                return

            # Iterate over each keyframe to update its position based on control points
            for i in range(len(self.indices_array)):
                fcurve = self.fcurves_array[i]
                index = self.indices_array[i]
                kf = fcurve.keyframe_points[index]
                is_rotation_curve = self.is_rotation_curve_array[i]

                # Determine which cell the keyframe belongs to based on initial relative positions
                relative_key = self.relative_keys[i]
                if relative_key is None:
                    # Calculate relative cell based on initial positions
                    init_x, init_y = self.initial_co_array[i]
                    col = min(
                        int(
                            (init_x - self.initial_bounds[0])
                            / (self.initial_bounds[1] - self.initial_bounds[0])
                            * lattice_x
                        ),
                        lattice_x - 1,
                    )
                    row = min(
                        int(
                            (init_y - self.initial_bounds[2])
                            / (self.initial_bounds[3] - self.initial_bounds[2])
                            * lattice_y
                        ),
                        lattice_y - 1,
                    )
                    relative_key = (row, col)
                    self.relative_keys[i] = relative_key  # Cache for future use

                if relative_key not in self.relative_co_cell_list[i]:
                    self.report(
                        {"WARNING"},
                        f"Keyframe at index {index} missing relative position in cell {relative_key}.",
                    )
                    continue  # Skip if relative positions are missing

                u, v = self.relative_co_cell_list[i][relative_key]
                handle_left_u, handle_left_v = self.relative_handle_left_cell_list[i][relative_key]
                handle_right_u, handle_right_v = self.relative_handle_right_cell_list[i][relative_key]

                row, col = relative_key

                # Get current positions of the four control points defining the cell
                try:
                    Q00 = cp_positions[row * (lattice_x + 1) + col]
                    Q10 = cp_positions[row * (lattice_x + 1) + (col + 1)]
                    Q11 = cp_positions[(row + 1) * (lattice_x + 1) + (col + 1)]
                    Q01 = cp_positions[(row + 1) * (lattice_x + 1) + col]
                except KeyError:
                    self.report({"ERROR"}, f"Missing control point for cell ({row}, {col}).")
                    continue  # Skip this cell

                # Compute new position in quadrilateral for keyframe based on current control points
                new_x = (1 - u) * (1 - v) * Q00[0] + u * (1 - v) * Q10[0] + u * v * Q11[0] + (1 - u) * v * Q01[0]
                new_y = (1 - u) * (1 - v) * Q00[1] + u * (1 - v) * Q10[1] + u * v * Q11[1] + (1 - u) * v * Q01[1]

                # Compute new positions for handles
                new_handle_left_x = (
                    (1 - handle_left_u) * (1 - handle_left_v) * Q00[0]
                    + handle_left_u * (1 - handle_left_v) * Q10[0]
                    + handle_left_u * handle_left_v * Q11[0]
                    + (1 - handle_left_u) * handle_left_v * Q01[0]
                )
                new_handle_left_y = (
                    (1 - handle_left_u) * (1 - handle_left_v) * Q00[1]
                    + handle_left_u * (1 - handle_left_v) * Q10[1]
                    + handle_left_u * handle_left_v * Q11[1]
                    + (1 - handle_left_u) * handle_left_v * Q01[1]
                )

                new_handle_right_x = (
                    (1 - handle_right_u) * (1 - handle_right_v) * Q00[0]
                    + handle_right_u * (1 - handle_right_v) * Q10[0]
                    + handle_right_u * handle_right_v * Q11[0]
                    + (1 - handle_right_u) * handle_right_v * Q01[0]
                )
                new_handle_right_y = (
                    (1 - handle_right_u) * (1 - handle_right_v) * Q00[1]
                    + handle_right_u * (1 - handle_right_v) * Q10[1]
                    + handle_right_u * handle_right_v * Q11[1]
                    + (1 - handle_right_u) * handle_right_v * Q01[1]
                )

                # Set new positions
                kf.co[0] = new_x
                kf.co[1] = radians(new_y) if is_rotation_curve else new_y

                kf.handle_left[0] = new_handle_left_x
                kf.handle_left[1] = radians(new_handle_left_y) if is_rotation_curve else new_handle_left_y

                kf.handle_right[0] = new_handle_right_x
                kf.handle_right[1] = radians(new_handle_right_y) if is_rotation_curve else new_handle_right_y

        else:
            # Handle NORMAL mode
            cp_positions = {cp.index: cp.position for cp in self.control_points}

            if self.dragging_control_point == 8:  # Center control point - translate all keyframes
                # Calculate the translation delta from center point movement
                center_x = (min_x0 + max_x0) / 2
                center_y = (min_y0 + max_y0) / 2
                new_center_x, new_center_y = cp_positions[8]

                delta_x = new_center_x - center_x
                delta_y = new_center_y - center_y

                # Apply translation to all keyframes
                for i in range(len(self.indices_array)):
                    fcurve = self.fcurves_array[i]
                    index = self.indices_array[i]
                    kf = fcurve.keyframe_points[index]
                    is_rotation_curve = self.is_rotation_curve_array[i]

                    # Get initial positions and add delta
                    init_x, init_y = self.initial_co_array[i]
                    init_handle_left_x, init_handle_left_y = self.initial_handle_left_array[i]
                    init_handle_right_x, init_handle_right_y = self.initial_handle_right_array[i]

                    new_x = init_x + delta_x
                    new_y = init_y + delta_y
                    new_handle_left_x = init_handle_left_x + delta_x
                    new_handle_left_y = init_handle_left_y + delta_y
                    new_handle_right_x = init_handle_right_x + delta_x
                    new_handle_right_y = init_handle_right_y + delta_y

                    # Set new positions
                    kf.co[0] = new_x
                    kf.co[1] = radians(new_y) if is_rotation_curve else new_y
                    kf.handle_left[0] = new_handle_left_x
                    kf.handle_left[1] = radians(new_handle_left_y) if is_rotation_curve else new_handle_left_y
                    kf.handle_right[0] = new_handle_right_x
                    kf.handle_right[1] = radians(new_handle_right_y) if is_rotation_curve else new_handle_right_y

            else:
                # Normal control point behavior - scaling
                # Determine which bounds to update based on the dragged control point
                min_x, max_x, min_y, max_y = min_x0, max_x0, min_y0, max_y0

                if self.dragging_control_point in [1, 2, 5]:  # Right side
                    max_x = cp_positions[self.dragging_control_point][0]
                if self.dragging_control_point in [2, 3, 6]:  # Top side
                    max_y = cp_positions[self.dragging_control_point][1]
                if self.dragging_control_point in [0, 3, 7]:  # Left side
                    min_x = cp_positions[self.dragging_control_point][0]
                if self.dragging_control_point in [0, 1, 4]:  # Bottom side
                    min_y = cp_positions[self.dragging_control_point][1]

                # Remove clamping constraints to allow control points to cross each other
                # This allows more flexible manipulation without position limitations
                
                if max_x == min_x:
                    max_x += 0.0001
                if max_y == min_y:
                    max_y += 0.0001

                denom_x = max_x - min_x
                denom_y = max_y - min_y

                new_x_array = min_x + self.relative_co[:, 0] * denom_x
                new_y_array = min_y + self.relative_co[:, 1] * denom_y

                new_handle_left_x_array = min_x + self.relative_handle_left[:, 0] * denom_x
                new_handle_left_y_array = min_y + self.relative_handle_left[:, 1] * denom_y

                new_handle_right_x_array = min_x + self.relative_handle_right[:, 0] * denom_x
                new_handle_right_y_array = min_y + self.relative_handle_right[:, 1] * denom_y

                new_x_array = self.ensure_keyframe_spacing(new_x_array)

                for i in range(len(self.indices_array)):
                    fcurve = self.fcurves_array[i]
                    index = self.indices_array[i]
                    kf = fcurve.keyframe_points[index]
                    is_rotation_curve = self.is_rotation_curve_array[i]

                    kf.co[0] = new_x_array[i]
                    kf.co[1] = radians(new_y_array[i]) if is_rotation_curve else new_y_array[i]

                    kf.handle_left[0] = new_handle_left_x_array[i]
                    kf.handle_left[1] = (
                        radians(new_handle_left_y_array[i]) if is_rotation_curve else new_handle_left_y_array[i]
                    )

                    kf.handle_right[0] = new_handle_right_x_array[i]
                    kf.handle_right[1] = (
                        radians(new_handle_right_y_array[i]) if is_rotation_curve else new_handle_right_y_array[i]
                    )

                positions = {
                    0: (min_x, min_y),
                    1: (max_x, min_y),
                    2: (max_x, max_y),
                    3: (min_x, max_y),
                    4: ((min_x + max_x) / 2, min_y),
                    5: (max_x, (min_y + max_y) / 2),
                    6: ((min_x + max_x) / 2, max_y),
                    7: (min_x, (min_y + max_y) / 2),
                    8: ((min_x + max_x) / 2, (min_y + max_y) / 2),  # Update center point position
                }

                for cp in self.control_points:
                    if cp.index != self.dragging_control_point:
                        cp.position = positions.get(cp.index, cp.position)


class AMP_PG_AnimLatticeSettings(bpy.types.PropertyGroup):
    slice_to_full_frames: bpy.props.BoolProperty(
        name="Slice to Full Frames",
        description="Slice keyframes to closest full frames on finish/cancel",
        default=True,
    )

    lattice_x: bpy.props.IntProperty(
        name="Lattice X",
        description="Number of divisions in the X-axis",
        default=1,
        min=1,
        max=10,
        update=update_lattice,
    )

    lattice_y: bpy.props.IntProperty(
        name="Lattice Y",
        description="Number of divisions in the Y-axis",
        default=1,
        min=1,
        max=10,
        update=update_lattice,
    )

    lock_direction: bpy.props.BoolProperty(
        name="Lock Direction",
        description="Lock control point movement to the dominant axis (X or Y)",
        default=False,
    )


class AMP_PT_AnimLatticeOptions(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_AnimLatticeOptions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_ui_units_x = 20

    def draw(self, context):
        draw_anim_lattice_panel(self.layout, context)


def draw_circle(shader, center, radius, color, num_segments=16):
    from math import pi, cos, sin

    vertices = []
    for i in range(num_segments + 1):
        angle = 2 * pi * i / num_segments
        x = center[0] + cos(angle) * radius
        y = center[1] + sin(angle) * radius
        vertices.append((x, y))
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def draw_rhomboid(shader, center, size, color):
    """
    Draws a rhombus centered at 'center' with the given 'size' and 'color' using the provided 'shader'.

    Parameters:
    - shader: The shader program to use for rendering.
    - center: A tuple (x, y) representing the center position of the rhombus.
    - size: The length of the diagonals of the rhombus.
    - color: A tuple or list representing the color (e.g., (r, g, b, a)).
    """
    x, y = center
    half_size = size / 2
    angles = [0, 90, 180, 270]
    vertices = []

    for angle in angles:
        rad = math.radians(angle)
        vx = x + math.cos(rad) * half_size
        vy = y + math.sin(rad) * half_size
        vertices.append((vx, vy))

    vertices.append(vertices[0])

    batch = batch_for_shader(shader, "TRI_FAN", {"pos": vertices})

    shader.bind()
    shader.uniform_float("color", color)

    batch.draw(shader)


def draw_anim_lattice_panel(layout, context):
    """Unified panel drawing function for Anim Lattice options.

    This function is used by both the main panel and the popup panel
    to ensure consistent UI behavior.
    """
    props = context.scene.keyframe_lattice_settings

    layout.use_property_split = True
    layout.use_property_decorate = False

    layout.label(text="Anim Lattice Options", icon="MOD_LATTICE")

    ui_column = layout.column()

    # Only show start buttons when not running - never show stop buttons
    ui_column.separator()

    if not AMP_OT_anim_lattice._is_running:
        # Show start buttons for both modes
        row = ui_column.row(align=True)
        btn_normal = row.operator("anim.amp_anim_lattice", text="Start Normal", icon="MOD_LATTICE")
        btn_normal.mode = "NORMAL"
        btn_warp = row.operator("anim.amp_anim_lattice", text="Start Warp", icon="MOD_LATTICE")
        btn_warp.mode = "WARP"

    ui_column.separator(factor=2)

    box = ui_column.box()
    container = box.column(align=False)

    # Slice to full frames - only enabled when snap is disabled
    slice_container = container.column()
    slice_container.prop(props, "slice_to_full_frames", text="Slice to full frames")
    # if mode WARP
    if AMP_OT_anim_lattice._current_mode == "WARP" or not AMP_OT_anim_lattice._is_running:

        container.separator()

        # Show lattice controls when not running
        lattice_container = container.column()
        lattice_container.prop(props, "lattice_x", text="Columns")
        lattice_container.prop(props, "lattice_y", text="Rows")

        container.separator()

        # Lock Direction control
        container.prop(props, "lock_direction", text="Lock Direction")


classes = (
    AMP_PG_AnimLatticeSettings,
    AMP_OT_anim_lattice,
    AMP_PT_AnimLatticeOptions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add the property group to the Scene
    Scene.keyframe_lattice_settings = bpy.props.PointerProperty(type=AMP_PG_AnimLatticeSettings)


def unregister():
    # Remove the property group from the Scene
    del Scene.keyframe_lattice_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
