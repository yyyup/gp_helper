import bpy
from .. import utils


class AMP_OT_MarkerTools(bpy.types.Operator):

    bl_idname = "anim.amp_markers_tools"
    bl_label = "Insert Markers"
    bl_description = """Insert Markers based on specified range and criteria"""

    bl_options = {"REGISTER", "UNDO"}

    insertion_criteria = [
        (
            "MRKR_EVERY_X_FRAMES",
            "Frame Step",
            "Insert markers every X frames",
            "MARKER",
            0,
        ),
        (
            "MRKR_DIVIDE_BY",
            "Divisions",
            "Divide the range in X segments separated by Markers",
            "NEXT_KEYFRAME",
            1,
        ),
        (
            "MRKR_EVERY_KEYFRAME",
            "On Keyframes",
            "Insert markers on every keyframe",
            "KEYFRAME",
            2,
        ),
    ]

    range_options = [
        ("PREVIEW", "Preview Range", "Use the preview range for keyframe insertion", "PREVIEW_RANGE", 0),
        ("SELECTED", "Selected Range", "Use the selected keyframes for keyframe insertion", "KEYFRAME", 1),
        ("SCENE", "Scene Range", "Use the entire scene for keyframe insertion", "SCENE_DATA", 2),
    ]

    range_options: bpy.props.EnumProperty(
        name="Range",
        items=range_options,
        default="SCENE",
        description="Define the range for keyframe insertion",
    )

    insertion_type: bpy.props.EnumProperty(
        name="Insertion Type",
        items=insertion_criteria,
        default="MRKR_EVERY_X_FRAMES",
        description="insert markers based on the specified criteria",
    )

    frame_step: bpy.props.IntProperty(
        name="Frame Step",
        default=10,
        min=1,
        description="Frame step interval between markers",
        update=utils.curve.update_frame_start_range,
    )
    frame_start_range: bpy.props.IntProperty(
        name="Frame Start",
        default=0,
        min=0,
        description="Offset start inserting markers",
        update=utils.curve.update_frame_step,
    )
    marker_on_last: bpy.props.BoolProperty(name="Marker on Last Frame", default=True)
    marker_on_first: bpy.props.BoolProperty(name="Marker on First Frame", default=True)
    clear_others: bpy.props.BoolProperty(
        name="Clear Others",
        default=True,
        description="Delete other Markers on the timeline",
    )

    keep_camera_markers: bpy.props.BoolProperty(
        name="Keep Camera Markers",
        default=True,
        description="Keep markers bound to cameras",
    )

    def draw(self, context):
        layout = self.layout
        draw_markers_tools_options(self, layout, context)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):

        # First, clear existing markers if clear_others is True
        if self.clear_others:
            bpy.ops.anim.amp_delete_markers(keep_camera_markers=self.keep_camera_markers)

        # Determine the frame range based on the range_selection
        frame_range = utils.curve.determine_frame_range(self, context)

        start, end = frame_range[0], frame_range[1]

        if self.marker_on_last:
            bpy.context.scene.timeline_markers.new(name="F{}".format(end), frame=int(end))

        if self.marker_on_first and self.frame_start_range != 0:
            bpy.context.scene.timeline_markers.new(name="F{}".format(start), frame=int(start))

        if self.insertion_type == "MRKR_EVERY_X_FRAMES":
            self.insert_markers_every_x_frames(context, frame_range, self.frame_step, self.frame_start_range)

        elif self.insertion_type == "MRKR_DIVIDE_BY":
            self.insert_markers_divide_by(
                context,
                frame_range,
                self.frame_step,
            )
        elif self.insertion_type == "MRKR_EVERY_KEYFRAME":
            self.inser_makers_on_keyframes(context, frame_range)

        # update_property_group(self, context)

        utils.refresh_ui(context)

        self.report({"INFO"}, "Markers added successfully.")
        return {"FINISHED"}

    def insert_markers_every_x_frames(self, context, frame_range, frame_step, frame_start_range):
        """Insert markers every X frames within the specified frame range."""
        start, end = frame_range[0], frame_range[1]
        start = start
        end = end
        for frame in range(start + frame_start_range, end, frame_step):
            bpy.context.scene.timeline_markers.new(name=f"F{frame}", frame=frame)

    def insert_markers_divide_by(self, context, frame_range, segments):
        """Divide the frame range into segments and insert a marker at the start of each segment."""
        start, end = frame_range[0], frame_range[1]
        start = int(start)
        end = int(end)
        segments = max(1, segments)  # Ensure at least one segment
        total_frames = end - start
        segment_length = total_frames / segments  # Calculate segment length as a float

        for i in range(segments):
            frame = int(round(start + (i * segment_length)))

            # Ensure the frame is within the specified range
            if start <= frame <= end:
                bpy.context.scene.timeline_markers.new(name=f"F{frame}", frame=frame)

    def inser_makers_on_keyframes(self, context, frame_range):
        """Insert markers on every keyframe within the specified frame range."""
        start, end = frame_range[0], frame_range[1]
        start = int(start)
        end = int(end)
        fcurves = utils.curve.all_fcurves(context.active_object.animation_data.action)

        for fcurve in fcurves:
            for kf in fcurve.keyframe_points:
                frame = int(kf.co.x)
                bpy.context.scene.timeline_markers.new(name=f"F{frame}", frame=frame)


class AMP_OT_DeleteMarkers(bpy.types.Operator):
    """Delete selected markers from the current scene, with an option to keep camera-related markers."""

    bl_idname = "anim.amp_delete_markers"
    bl_label = "Delete Markers"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = (
        "If selected markers exist, delete them. Otherwise, delete all markers, optionally keep camera markers."
    )
    keep_camera_markers: bpy.props.BoolProperty(
        name="Keep Camera Markers",
        default=True,
        description="Keep markers related to the camera",
    )

    def execute(self, context):
        markers_to_remove = []
        markers_selected = False

        for marker in context.scene.timeline_markers:
            if self.keep_camera_markers and marker.camera:
                continue

            if marker.select:
                markers_selected = True
                break

        for marker in context.scene.timeline_markers:
            if markers_selected and marker.select:
                markers_to_remove.append(marker)

            elif not markers_selected and not marker.select:
                markers_to_remove.append(marker)

        # Remove the selected markers
        for marker in markers_to_remove:
            context.scene.timeline_markers.remove(marker)

        self.report({"INFO"}, f"Markers deleted: {len(markers_to_remove)}")
        return {"FINISHED"}


class AMP_PT_MarkersToolsOptions(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_MarkersToolsOptions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        props = context.scene.markers_tools_props

        ui_column = layout.column(align=True)

        ui_column.separator(factor=2)

        slice_anim = ui_column.row(align=True)
        slice_anim.scale_y = 1.5
        MarkersToolsButton(slice_anim, context, "Add Markers", "MARKER")

        draw_markers_tools_options(props, ui_column, context)

        ui_column.separator()
        operations_row = ui_column.row(align=True)
        draw_delete_all_markers(layout, context)
        operations_row.separator()
        draw_markers_lock(props, operations_row, context)


def draw_delete_all_markers(layout, context, text="Delete All Markers"):
    layout.operator(
        "anim.amp_delete_markers",
        text=text,
        icon_value=utils.customIcons.get_icon_id("AMP_markers_delete_all"),
        # emboss=False,
    )


def draw_markers_lock(layout, context, text="Markers Options"):
    lock_row = layout.row(align=True)
    lock_row.prop(
        bpy.data.scenes["Scene"].tool_settings,
        "lock_markers",
        text=text,
        icon_value=(
            utils.customIcons.get_icon_id("AMP_markers_lock")
            if bpy.data.scenes["Scene"].tool_settings.lock_markers
            else utils.customIcons.get_icon_id("AMP_markers_unlock")
        ),
        # emboss=False,
    )


def draw_markers_tools_options(self, layout, context):

    layout.separator(factor=2)

    container = layout.box()

    markers_column = container.column()

    markers_column.separator()

    split = markers_column.split(factor=0.3)
    split.label(text="Insert Markers:")
    split.prop(
        self,
        "insertion_type",
        # icon="MARKER",
        text="",
    )

    markers_column.separator()

    text = "Frame Step" if self.insertion_type == "MRKR_EVERY_X_FRAMES" else "Sections"

    split = markers_column.split(factor=0.3)
    split.label(text=" ")
    col = split.column()

    row = col.row(align=True)
    if self.insertion_type == "MRKR_EVERY_KEYFRAME":
        row.active = False
    row.prop(self, "frame_step", text=text)
    row.separator(factor=0.5)

    row = col.row(align=True)
    if self.insertion_type != "MRKR_EVERY_X_FRAMES":
        row.active = False
    row.prop(self, "frame_start_range")

    markers_column.separator()

    split = markers_column.split(factor=0.3)
    split.label(text="Range:")
    split.prop(self, "range_options", text="")

    markers_column.separator()

    split = markers_column.split(factor=0.3)
    split.label(text="First / Last:")
    col = split.column(align=True)
    col.prop(self, "marker_on_last")
    col.prop(self, "marker_on_first")

    markers_column.separator()

    split = markers_column.split(factor=0.3)
    split.label(text="Clearing:")
    col = split.column(align=True)
    col.prop(self, "clear_others")
    row = col.row(align=True)
    row.active = self.clear_others
    row.prop(self, "keep_camera_markers")


def MarkersToolsButton(layout, context, text, icon_value):

    markers_subrow = layout.row(align=True)
    markers_op = markers_subrow.operator(
        "anim.amp_markers_tools",
        text=text,
        icon_value=icon_value,
        # emboss=False,
    )

    draw_delete_all_markers(markers_subrow, context, text="")

    draw_markers_lock(markers_subrow, context, text="")


classes = (
    AMP_OT_MarkerTools,
    AMP_PT_MarkersToolsOptions,
    AMP_OT_DeleteMarkers,
)


def register():
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
    except:
        utils.dprint(f"{cls} already registered, skipping...")


def unregister():

    try:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    except:
        utils.dprint(f"{cls} not found, skipping...")


if __name__ == "__main__":
    register()
