import bpy
from .. import utils
from ..utils.customIcons import get_icon


class AMP_OT_Retimer(bpy.types.Operator):
    """Animation Retimer"""

    bl_idname = "anim.amp_anim_retimer"
    bl_label = "Animation FPS Retimer"
    bl_options = {"REGISTER", "UNDO"}

    # Operator properties
    source_frame_rate: bpy.props.FloatProperty(name="Source Frame Rate", default=24.0)
    target_frame_rate: bpy.props.FloatProperty(name="Target Frame Rate", default=24.0)
    cleanup_method: bpy.props.EnumProperty(
        name="Cleanup Method",
        items=[
            (
                "PRESERVE",
                "Smart: Preserve Tangents",
                """Preserve the shape of the F-Curves
by inserting keyframes in whole frames and removing those in subframes.""",
                "FCURVE",
                0,
            ),
            (
                "SNAP",
                "Snap to Frames",
                """Snap keyframes to whole frames
This can cause keyframes to be shifted by a frame creating curvature distortion.""",
                "SNAP_ON",
                1,
            ),
            ("SUBFRAMES", "Sub Frames", """Leave the subframes un touched""", "PARTICLE_POINT", 2),
        ],
        default="PRESERVE",
    )
    interpolation: bpy.props.EnumProperty(
        name="Interpolation",
        items=[
            ("BEZIER", "Bezier", "", "IPO_BEZIER", 0),
            ("CONSTANT", "Constant", "", "IPO_CONSTANT", 1),
            ("LINEAR", "Linear", "", "IPO_LINEAR", 2),
            ("SOURCE", "Source", "", "RECOVER_LAST", 3),
        ],
        default="SOURCE",
    )
    frame_handlers: bpy.props.EnumProperty(
        name="Frame Handlers",
        items=[
            ("VECTOR", "Vector", "", "HANDLE_VECTOR", 0),
            ("AUTO_CLAMPED", "Auto Clamped", "", "HANDLE_AUTOCLAMPED", 1),
            ("AUTO", "Auto", "", "HANDLE_AUTO", 2),
            ("ALIGNED", "Aligned", "", "HANDLE_ALIGNED", 3),
            ("FREE", "Free", "", "HANDLE_FREE", 4),
            ("SOURCE", "Source", "", "RECOVER_LAST", 5),
        ],
        default="SOURCE",
    )

    # def invoke(self, context, event):
    #     wm = context.window_manager
    #     return wm.invoke_props_dialog(self)

    def execute(self, context):
        scale_factor = self.target_frame_rate / self.source_frame_rate

        for obj in context.selected_objects:
            # Handle object-level animation data (e.g., for mesh objects)
            if obj.animation_data and obj.animation_data.action:
                retime_action(self, obj.animation_data.action, scale_factor)

        # Redraw the area to reflect the changes
        for area in context.screen.areas:
            if area.type == "GRAPH_EDITOR":
                area.tag_redraw()

        return {"FINISHED"}


def retime_action(self, action, scale_factor, specific_fcurve=None):
    """Apply retiming to an action or a specific F-Curve."""
    fcurves = [specific_fcurve] if specific_fcurve else utils.curve.all_fcurves(action)

    bpy.context.scene.frame_current = bpy.context.scene.frame_start

    for fcurve in fcurves:
        if fcurve:  # Check if fcurve is not None

            # Collect all keyframes in the fcurve
            keyframes = list(fcurve.keyframe_points)

            # Sort keyframes by their original frame number
            keyframes.sort(key=lambda keyframe: keyframe.co.x)

            original_first_frame = fcurve.keyframe_points[0].co.x if fcurve.keyframe_points else None

            # Iterate through sorted keyframes for retiming
            for keyframe in keyframes:
                # Store original handle types
                original_left_handle_type = keyframe.handle_left_type
                original_right_handle_type = keyframe.handle_right_type

                # Temporarily set handle types to 'AUTO_CLAMPED' for smooth transition
                keyframe.handle_left_type = "AUTO_CLAMPED"
                keyframe.handle_right_type = "AUTO_CLAMPED"

                # Scale the keyframe's frame (time)
                keyframe.co.x *= scale_factor
                keyframe.handle_left.x *= scale_factor  # Note: See below for adjustment
                keyframe.handle_right.x *= scale_factor  # Note: See below for adjustment

                # Revert handle types to original
                keyframe.handle_left_type = original_left_handle_type
                keyframe.handle_right_type = original_right_handle_type

                # Note: Adjusting handles after reverting types if not 'SOURCE'
                if self.interpolation != "SOURCE":
                    keyframe.interpolation = self.interpolation

                if self.frame_handlers != "SOURCE":
                    keyframe.handle_left_type = self.frame_handlers
                    keyframe.handle_right_type = self.frame_handlers

    if self.cleanup_method == "SNAP":

        for fcurve in fcurves:

            if fcurve:

                # Collect all keyframes in the fcurve
                keyframes = list(fcurve.keyframe_points)
                # Sort keyframes by their original frame number
                keyframes.sort(key=lambda keyframe: keyframe.co.x)

                for keyframe in keyframes:
                    keyframe.co.x = round(keyframe.co.x)

                utils.curve.correct_offset(fcurve, original_first_frame)

                fcurve.update()

        self.report({"INFO"}, "Keyframes snapped to whole frames")

    elif self.cleanup_method == "PRESERVE":

        # utils.curve.smart_preserve_fcurves(fcurves, original_first_frame, shift_offset=True)
        op = bpy.ops.anim.amp_anim_slicer(
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

        # self.report({"INFO"}, "FCurve shapes preserved")

    else:
        pass


class AMP_PG_AnimRetimerProperties(bpy.types.PropertyGroup):
    source_frame_rate: bpy.props.FloatProperty(name="Source Frame Rate", default=24.0)
    target_frame_rate: bpy.props.FloatProperty(name="Target Frame Rate", default=24.0)
    snap_to_frames: bpy.props.BoolProperty(name="Snap to Frames", default=True)
    interpolation: bpy.props.EnumProperty(
        name="Interpolation",
        items=[
            ("BEZIER", "Bezier", "", "IPO_BEZIER", 0),
            ("CONSTANT", "Constant", "", "IPO_CONSTANT", 1),
            ("LINEAR", "Linear", "", "IPO_LINEAR", 2),
            ("SOURCE", "Source", "", "RECOVER_LAST", 3),
        ],
        default="SOURCE",
    )
    frame_handlers: bpy.props.EnumProperty(
        name="Frame Handlers",
        items=[
            ("VECTOR", "Vector", "", "HANDLE_VECTOR", 0),
            ("AUTO_CLAMPED", "Auto Clamped", "", "HANDLE_AUTOCLAMPED", 1),
            ("AUTO", "Auto", "", "HANDLE_AUTO", 2),
            ("ALIGNED", "Aligned", "", "HANDLE_ALIGNED", 3),
            ("FREE", "Free", "", "HANDLE_FREE", 4),
            ("SOURCE", "Source", "", "RECOVER_LAST", 5),
        ],
        default="SOURCE",
    )
    cleanup_method: bpy.props.EnumProperty(
        name="Cleanup Method",
        items=[
            (
                "PRESERVE",
                "Smart: Preserve Tangents",
                """Preserve the shape of the F-Curves
by inserting keyframes in whole frames and removing those in subframes.""",
                "FCURVE",
                0,
            ),
            (
                "SNAP",
                "Snap to Frames",
                """Snap keyframes to whole frames
This can cause keyframes to be shifted by a frame creating curvature distortion.""",
                "SNAP_ON",
                1,
            ),
            ("SUBFRAMES", "Sub Frames", """Leave the subframes un touched""", "PARTICLE_POINT", 2),
        ],
        default="PRESERVE",
    )


class AMP_PT_RetimerGraph(bpy.types.Panel):
    bl_label = "Anim Retimer"
    bl_idname = "AMP_PT_RetimerGraph"
    bl_parent_id = "AMP_PT_AniMateProGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", **get_icon("AMP_anim_retimer"))

    def draw(self, context):
        draw_animretimer_panel(self, context)


# bl_label = "Timeline Tools"
# bl_idname = "AMP_PT_TimelineToolsView"
# bl_space_type = "VIEW_3D"
# bl_region_type = "UI"
# bl_category = "Animation"
# bl_parent_id = "AMP_PT_AniMateProView"


class AMP_PT_RetimerView(bpy.types.Panel):
    bl_label = "Anim Retimer"
    bl_idname = "AMP_PT_RetimerView"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "AMP_PT_AniMateProView"
    bl_options = {"DEFAULT_CLOSED"}
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", **get_icon("AMP_anim_retimer"))

    def draw(self, context):
        draw_animretimer_panel(self, context)


class AMP_PT_RetimerDope(bpy.types.Panel):
    bl_label = "Anim Retimer"
    bl_idname = "AMP_PT_RetimerDope"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_parent_id = "AMP_PT_AniMateProDope"
    bl_options = {"DEFAULT_CLOSED"}
    bl_category = "Animation"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", **get_icon("AMP_anim_retimer"))

    def draw(self, context):
        draw_animretimer_panel(self, context)


def draw_animretimer_panel(self, context):
    layout = self.layout
    props = context.scene.anim_retimer_props

    row = layout.row()
    split = row.split(factor=0.4)
    split.alignment = "RIGHT"
    split.label(text="Scene Frame Rate")
    split.menu(
        "RENDER_MT_framerate_presets",
        text=(
            (
                "{:.2f}".format(round((context.scene.render.fps / context.scene.render.fps_base), 2))
                if (context.scene.render.fps / context.scene.render.fps_base) != round(context.scene.render.fps)
                else str(context.scene.render.fps)
            )
            + " fps"
        ),
    )

    row = layout.row()
    split = row.split(factor=0.4)
    split.alignment = "RIGHT"
    split.label(text="Source Frame Rate")
    split.prop(props, "source_frame_rate", text="")

    row = layout.row()
    split = row.split(factor=0.4)
    split.alignment = "RIGHT"
    split.label(text="Target Frame Rate")
    split.prop(props, "target_frame_rate", text="")

    row = layout.row()
    split = row.split(factor=0.4)
    split.alignment = "RIGHT"
    split.label(text="Cleanup Method")
    split.prop(props, "cleanup_method", text="")

    col = layout.column()
    col.active = props.cleanup_method != "PRESERVE"

    row = col.row()
    split = row.split(factor=0.4)
    split.alignment = "RIGHT"
    split.label(text="Interpolation")
    split.prop(props, "interpolation", text="")

    row = col.row()
    split = row.split(factor=0.4)
    split.alignment = "RIGHT"
    split.label(text="Keyframe Handlers")
    split.prop(props, "frame_handlers", text="")

    layout.separator()

    row = layout.row()
    row.scale_y = 1.5

    row.separator()

    op = row.operator("anim.amp_anim_retimer", text="Retime", icon="TIME")
    op.source_frame_rate = props.source_frame_rate
    op.target_frame_rate = props.target_frame_rate
    op.interpolation = props.interpolation
    op.frame_handlers = props.frame_handlers
    op.cleanup_method = props.cleanup_method

    row.separator()


classes = (
    AMP_OT_Retimer,
    # AMP_PT_RetimerGraph,
    # AMP_PT_RetimerDope,
    # AMP_PT_RetimerView,
)


def register_properties():
    bpy.utils.register_class(AMP_PG_AnimRetimerProperties)
    bpy.types.Scene.anim_retimer_props = bpy.props.PointerProperty(type=AMP_PG_AnimRetimerProperties)


def unregister_properties():
    del bpy.types.Scene.anim_retimer_props
    bpy.utils.unregister_class(AMP_PG_AnimRetimerProperties)


def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()


if __name__ == "__main__":
    register()
