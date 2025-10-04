import bpy
from .. import utils
import math
from bpy.types import Menu, Operator
from bl_operators.presets import AddPresetBase

stored_slice_frames = []


def ensure_only_available(self, context):
    any_key_set = any([self.key_location, self.key_rotation, self.key_scale, self.key_custom])
    if self.key_available and any_key_set:
        if self.key_available != False:
            self.key_available = False
    elif not self.key_available and any_key_set:
        pass
    else:
        if not self.key_available:
            self.key_available = True
            self.key_location = False
            self.key_rotation = False
            self.key_scale = False
            self.key_custom = False


class SlicerFrame:
    def __init__(self, fcurve, frame, closest_frame, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fcurve = fcurve
        self.original_frame = frame
        self.closest_frame = closest_frame
        self.handle_type = None
        self.handle_left = None
        self.handle_right = None


insertion_criteria = [
    ("ON_MARKERS", "On Markers", "Insert keyframes on existing markers", "MARKER", 0),
    ("FRAME_STEP", "Frame Step", "Insert keyframes based on a frame step interval", "NEXT_KEYFRAME", 1),
    (
        "ON_MARKERS_AND_FRAME_STEP",
        "Markers & Frame Step",
        "Insert keyframes on markers and frame step intervals",
        "MARKER_HLT",
        2,
    ),
    (
        "CLOSEST_FULL_FRAME",
        "Closest Full Frame",
        "Remove subframes and keep the closest whole frame to the original keyframes",
        "STICKY_UVS_DISABLE",
        3,
    ),
    ("STORED_SLICE_FRAMES", "Stored Slice Frames", "Slice on stored list of frames", "PASTEDOWN", 4),
]

handle_type_options = [
    ("FREE", "Free", "Free handle type", "HANDLE_FREE", 0),
    ("ALIGNED", "Aligned", "Aligned handle type", "HANDLE_ALIGNED", 1),
    ("VECTOR", "Vector", "Vector handle type", "HANDLE_VECTOR", 2),
    ("AUTO", "Automatic", "Automatic handle type", "HANDLE_AUTO", 3),
    ("AUTO_CLAMPED", "Auto Clamped", "Auto Clamped handle type", "HANDLE_AUTOCLAMPED", 4),
]

interpolation_options = [
    ("CONSTANT", "Constant", "Constant interpolation", "IPO_CONSTANT", 0),
    ("LINEAR", "Linear", "Linear interpolation", "IPO_LINEAR", 1),
    ("BEZIER", "Bezier", "Bezier interpolation", "IPO_BEZIER", 2),
]

selection_options = [
    ("SELECTED_CURVES", "Selected FCurves", "Slice all selected FCurves", "RESTRICT_SELECT_OFF", 0),
    (
        "ALL_CURVES",
        "All FCurves from selected elements",
        "Slice all FCurves from the selected objects or bones",
        "FCURVE",
        1,
    ),
]

range_options = [
    ("PREVIEW", "Preview Range", "Use the preview range for keyframe insertion", "PREVIEW_RANGE", 0),
    ("SELECTED", "Selected Range", "Use the selected keyframes for keyframe insertion", "KEYFRAME", 1),
    ("SCENE", "Scene Range", "Use the entire scene for keyframe insertion", "SCENE_DATA", 2),
]


def closest_whole_frame(value):
    if (value - math.floor(value)) >= 0.5:
        return math.ceil(value)
    else:
        return math.floor(value)


def find_keyframe_index(fcurve, frame, threshold=1e-6):
    for i, keyframe in enumerate(fcurve.keyframe_points):
        if abs(keyframe.co.x - frame) <= threshold:
            return i
    return -1


def snap_close_subframes(slicer_frames_list):
    for slicer_frame in slicer_frames_list:
        if abs(slicer_frame.original_frame - slicer_frame.closest_frame) <= 0.01:
            original_keyframe_index = find_keyframe_index(slicer_frame.fcurve, slicer_frame.original_frame)
            if original_keyframe_index != -1:
                slicer_frame.fcurve.keyframe_points[original_keyframe_index].co.x = slicer_frame.closest_frame
                slicer_frame.fcurve.update()


# Helpers to classify and filter FCurves by channel type so channel toggles remain honored
def _fcurve_channel_category(fcurve):
    dp = getattr(fcurve, "data_path", "") or ""
    dp = str(dp)
    # Object and PoseBone channels usually end with these names
    if dp.endswith("location"):
        return "LOCATION"
    if dp.endswith("scale"):
        return "SCALE"
    if dp.endswith("rotation_euler") or dp.endswith("rotation_quaternion") or dp.endswith("rotation_axis_angle"):
        return "ROTATION"
    # Custom properties are addressed with bracket notation e.g. ["prop"] possibly nested in pose.bones
    if "]" in dp and "[" in dp and dp.strip().endswith("]"):
        return "CUSTOM"
    return "OTHER"


def _filter_fcurves_by_channel_toggles(fcurves, op_self):
    # If "Available" is active or no specific toggles, return as-is
    if getattr(op_self, "key_available", True) or not any(
        (op_self.key_location, op_self.key_rotation, op_self.key_scale, op_self.key_custom)
    ):
        return list(fcurves)

    out = []
    for fc in fcurves:
        cat = _fcurve_channel_category(fc)
        if cat == "LOCATION" and op_self.key_location:
            out.append(fc)
        elif cat == "ROTATION" and op_self.key_rotation:
            out.append(fc)
        elif cat == "SCALE" and op_self.key_scale:
            out.append(fc)
        elif cat == "CUSTOM" and op_self.key_custom:
            out.append(fc)
        # ignore "OTHER" when specific channel toggles are set
    return out


class AMP_OT_AnimSlicer(bpy.types.Operator):
    bl_idname = "anim.amp_anim_slicer"
    bl_label = "Anim Slicer"
    bl_description = """Slice all the whole action or selected FCurves:
Slice on:
    - Markers: Every marker.
    - Frame Step: Every N frames.
    - Markers & Frame Step: Every marker and every N frames.
    - Closest Full Frame: Remove subframes and keep the closest whole frame to the original keyframes.
    - Stored Slice Frames: Insert keyframes on stored list of frames.
Range:
    - If keyframes the range will be between the first and last selected keyframes.
    - If no keyframes the range will be the preview range.
    - Otherwise the range will be the entire scene
When pressing the button:
    - Hold SHIFT to skip the options in a dialog.
    - Hold CTRL to store frames from selected FCurves"""

    bl_options = {"REGISTER", "UNDO", "PRESET"}

    range_options: bpy.props.EnumProperty(
        name="Range",
        items=range_options,
        default="SCENE",
        description="Define the range for keyframe insertion",
    )
    selection_mode: bpy.props.EnumProperty(
        name="Selection Mode",
        items=selection_options,
        default="ALL_CURVES",
        description="Define which FCurves will be sliced.",
    )
    key_available: bpy.props.BoolProperty(
        name="Available",
        default=True,
        update=ensure_only_available,
    )
    key_location: bpy.props.BoolProperty(
        name="Location",
        default=False,
        description="Key Location",
        update=ensure_only_available,
    )
    key_rotation: bpy.props.BoolProperty(
        name="Rotation",
        default=False,
        description="Key Rotation",
        update=ensure_only_available,
    )
    key_scale: bpy.props.BoolProperty(
        name="Scale",
        default=False,
        description="Key Scale",
        update=ensure_only_available,
    )
    key_custom: bpy.props.BoolProperty(
        name="Custom",
        default=False,
        description="Key Custom Properties",
        update=ensure_only_available,
    )
    insertion_type: bpy.props.EnumProperty(
        name="Insertion Type",
        items=insertion_criteria,
        default="FRAME_STEP",
        description="Slice keyframes based on the specified criteria",
    )
    frame_step: bpy.props.IntProperty(
        name="Frame Step",
        default=5,
        min=1,
        description="Frame step interval for keyframe slicing",
        update=utils.curve.update_frame_start_range,
    )
    frame_start_range: bpy.props.IntProperty(
        name="Start Offset",
        default=0,
        min=0,
        description="Offset of the start frame within the range to start keyframing from",
        update=utils.curve.update_frame_step,
    )
    clear_others: bpy.props.BoolProperty(
        name="Clear Other Keyframes",
        default=True,
        description="Delete keyframes outside of the markers or steps",
    )
    clear_markers: bpy.props.BoolProperty(
        name="Clear Markers",
        default=False,
        description="Delete all markers",
    )
    keep_camera_markers: bpy.props.BoolProperty(
        name="Keep Camera Markers",
        default=True,
        description="Keep markers bound to cameras",
    )
    handle_type: bpy.props.EnumProperty(
        name="Handle Type",
        items=handle_type_options,
        default="AUTO_CLAMPED",
        description="Handle type for keyframes",
    )
    interpolation_type: bpy.props.EnumProperty(
        name="Interpolation Type",
        items=interpolation_options,
        default="BEZIER",
        description="Interpolation type for all keyframes",
    )
    kf_on_last: bpy.props.BoolProperty(name="Keyframe on Last Frame", default=True)
    kf_on_first: bpy.props.BoolProperty(name="Keyframe on First Frame", default=True)
    frame_end: bpy.props.IntProperty(
        name="Frame End",
        default=250,
        min=1,
        description="End Frame within the range to end keyframing at",
    )
    frame_start: bpy.props.IntProperty(
        name="Frame Start",
        default=1,
        min=1,
        description="Start Frame within the range to end keyframing at",
    )
    use_preview_range: bpy.props.BoolProperty(
        name="Use Preview Range",
        default=False,
        description="Use the preview range for keyframe insertion",
    )

    def draw(self, context):
        layout = self.layout
        draw_anim_slicer_options(self, layout, context)

    def invoke(self, context, event):
        global stored_slice_frames

        if event.ctrl:
            fcurves = self.get_keying_fcurves(self.selection_mode)
            frames = set()
            for fcurve in fcurves:
                for keyframe in fcurve.keyframe_points:
                    frames.add(keyframe.co.x)
            stored_slice_frames = sorted(frames)
            self.report({"INFO"}, f"Stored {len(stored_slice_frames)} frames from selected FCurves.")
            return {"CANCELLED"}

        if not event.shift:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)

        return self.execute(context)

    def get_keying_fcurves(self, selection_mode):
        context = bpy.context
        fcurves = []
        if selection_mode == "SELECTED_CURVES":
            fcurves = context.selected_visible_fcurves
        else:
            fcurves = []
            seen_fcurves = set()
            for obj in context.selected_objects:
                if obj.animation_data and obj.animation_data.action:
                    fcurves_extend = utils.curve.all_fcurves(obj.animation_data.action)
                    for fcurve in fcurves_extend:
                        if fcurve not in seen_fcurves:
                            fcurves.append(fcurve)
                            seen_fcurves.add(fcurve)

        return fcurves

    def execute(self, context):
        if not context.active_object:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        ensure_only_available(self, context)

        frame_range = utils.curve.determine_frame_range(self, context)

        if self.insertion_type == "CLOSEST_FULL_FRAME":
            # Use presampling-aware closest-frame processing
            self.process_closest_full_frame(context, frame_range)
            return {"FINISHED"}

        elif self.insertion_type == "STORED_SLICE_FRAMES":
            global stored_slice_frames
            stored_frames = stored_slice_frames
            if not stored_frames:
                self.report({"ERROR"}, "No stored slice frames. Hold CTRL when calling the operator to store frames.")
                return {"CANCELLED"}
            frames_to_insert = [frame for frame in stored_frames if frame_range[0] <= frame <= frame_range[1]]
        else:
            frames_to_insert = utils.curve.determine_insertion_frames(self, frame_range[0], frame_range[1])

        if not self.kf_on_last and frame_range[1] in frames_to_insert:
            frames_to_insert.remove(frame_range[1])
        if not self.kf_on_first and frame_range[0] in frames_to_insert:
            frames_to_insert.remove(frame_range[0])

        fcurves_all = self.get_keying_fcurves(self.selection_mode)
        # Respect channel toggles by filtering which fcurves to key
        fcurves = _filter_fcurves_by_channel_toggles(fcurves_all, self)

        # Presample evaluated values for all frames to insert before altering any keys
        samples = {}
        for fc in fcurves:
            framevals = {}
            for fr in frames_to_insert:
                if frame_range[0] <= fr <= frame_range[1]:
                    try:
                        framevals[fr] = fc.evaluate(fr)
                    except Exception:
                        continue
            samples[fc] = framevals

        # Now insert keys using sampled values
        for fc, framevals in samples.items():
            for fr, val in framevals.items():
                idx = find_keyframe_index(fc, fr)
                if idx == -1:
                    kp = fc.keyframe_points.insert(fr, val)
                else:
                    kp = fc.keyframe_points[idx]
                    kp.co.y = val
                kp.handle_left_type = self.handle_type
                kp.handle_right_type = self.handle_type
                kp.interpolation = self.interpolation_type
            fc.update()

        if self.clear_others:
            utils.curve.clear_other_keyframes(context, fcurves, frames_to_insert, frame_range)
        if self.clear_markers:
            bpy.ops.anim.amp_delete_markers(keep_camera_markers=self.keep_camera_markers)
        if fcurves:
            if context.space_data and context.space_data.type == "GRAPH_EDITOR":
                bpy.ops.graph.select_all(action="DESELECT")
            elif context.space_data and context.space_data.type == "DOPESHEET_EDITOR":
                bpy.ops.action.select_all(action="DESELECT")

        # Keys were already created with the chosen handle/interpolation above.
        # Perform a light pass to ensure adjacent interpolation when needed.
        for fcurve in fcurves:
            if not fcurve.keyframe_points:
                continue
            for i, keyframe in enumerate(fcurve.keyframe_points):
                if keyframe.co[0] in frames_to_insert:
                    keyframe.handle_left_type = keyframe.handle_right_type = self.handle_type
                    if 0 < i < len(fcurve.keyframe_points) - 1:
                        fcurve.keyframe_points[i].interpolation = self.interpolation_type
                        fcurve.keyframe_points[i - 1].interpolation = self.interpolation_type
            fcurve.update()

        self.report(
            {"INFO"},
            f"Inserted keyframes at {len(frames_to_insert)} frames and updated handle types and interpolation.",
        )
        return {"FINISHED"}

    def process_closest_full_frame(self, context, frame_range):
        # Collect subframe keys to snap
        slicer_frames_list = self.collect_slicer_frames(frame_range)

        # Before altering, presample the value at the target whole frame to preserve exact evaluation
        presamples = {}
        for sf in slicer_frames_list:
            closest = float(sf.closest_frame)
            try:
                val = sf.fcurve.evaluate(closest)
            except Exception:
                continue
            presamples.setdefault(sf.fcurve, {})[closest] = val

        # Insert presampled full-frame keys and remove original subframe keys
        for fc, framevals in presamples.items():
            for fr, val in framevals.items():
                idx = find_keyframe_index(fc, fr)
                if idx == -1:
                    kp = fc.keyframe_points.insert(fr, val)
                else:
                    kp = fc.keyframe_points[idx]
                    kp.co.y = val
                kp.interpolation = self.interpolation_type
                kp.handle_left_type = self.handle_type
                kp.handle_right_type = self.handle_type
            fc.update()

        # Remove the original subframe keys now that whole-frame keys are in place
        for sf in slicer_frames_list:
            try:
                idx = find_keyframe_index(sf.fcurve, sf.original_frame)
                if idx != -1:
                    sf.fcurve.keyframe_points.remove(sf.fcurve.keyframe_points[idx])
                    sf.fcurve.update()
            except Exception:
                continue

        if self.clear_others:
            self.remove_subframes()

        self.report(
            {"INFO"},
            f"Processed {len(slicer_frames_list)} frames to the closest full frames.",
        )

    def collect_slicer_frames(self, frame_range):
        slicer_frames_list = []
        fcurves = self.get_keying_fcurves(self.selection_mode)
        for fcurve in fcurves:
            for keyframe in fcurve.keyframe_points:
                original_frame = keyframe.co[0]
                if frame_range[0] <= original_frame <= frame_range[1] and not original_frame.is_integer():
                    try:
                        closest_frame = closest_whole_frame(original_frame)
                        slicer_frame = SlicerFrame(fcurve, original_frame, closest_frame)
                        slicer_frames_list.append(slicer_frame)
                    except Exception as e:
                        utils.api.dprint(f"Error creating SlicerFrame for frame {original_frame}: {e}")
                        continue
        return slicer_frames_list

    def insert_full_frames(self, slicer_frames_list):

        snap_close_subframes(slicer_frames_list)

        for slicer_frame in slicer_frames_list:
            try:
                closest_frame = float(slicer_frame.closest_frame)
                if not math.isfinite(closest_frame):
                    utils.api.dprint(f"Invalid closest_frame: {closest_frame}")
                    continue

                keyframe_index = find_keyframe_index(slicer_frame.fcurve, closest_frame)
                if keyframe_index == -1:
                    y = slicer_frame.fcurve.evaluate(closest_frame)
                    new_keyframe = slicer_frame.fcurve.keyframe_points.insert(closest_frame, y)
                    new_keyframe.interpolation = self.interpolation_type
                    new_keyframe.handle_left_type = self.handle_type
                    new_keyframe.handle_right_type = self.handle_type
                    slicer_frame.fcurve.update()

                original_keyframe_index = find_keyframe_index(slicer_frame.fcurve, slicer_frame.original_frame)
                if original_keyframe_index != -1:
                    slicer_frame.fcurve.keyframe_points.remove(
                        slicer_frame.fcurve.keyframe_points[original_keyframe_index]
                    )
                    slicer_frame.fcurve.update()

            except Exception as e:
                utils.api.dprint(f"Error processing slicer_frame: {e}")
                continue

    def remove_subframes(self):
        frame_range = utils.curve.determine_frame_range(self, bpy.context)
        for fcurve in self.get_keying_fcurves(self.selection_mode):
            for kp in reversed(fcurve.keyframe_points):
                if frame_range[0] <= kp.co.x <= frame_range[1] and not kp.co.x.is_integer():
                    fcurve.keyframe_points.remove(kp)
            fcurve.update()


def draw_anim_slicer_options(self, layout, context):
    container = layout.box()
    slicer_column = container.column()

    split = slicer_column.split(factor=0.3)
    split.label(text="Affect:")
    split.prop(self, "selection_mode", text="")

    slicer_column.separator()

    split = slicer_column.split(factor=0.3)
    split.label(text="Slice on:")
    split.prop(self, "insertion_type", icon="KEYFRAME", text="")

    if self.insertion_type == "STORED_SLICE_FRAMES":
        global stored_slice_frames
        if not stored_slice_frames:
            slicer_column.label(
                text="No stored slice frames. Hold CTRL when calling the operator to store frames.", icon="ERROR"
            )

    if self.insertion_type in {"FRAME_STEP", "ON_MARKERS_AND_FRAME_STEP"}:
        split = slicer_column.split(factor=0.3)
        split.label(text=" ")
        column = split.column(align=True)
        column.active = True
        column.separator(factor=1)
        column.prop(self, "frame_step")
        column.separator(factor=0.5)
        column.prop(self, "frame_start_range")
    elif self.insertion_type == "CLOSEST_FULL_FRAME":
        split = slicer_column.split(factor=0.3)
        split.label(text="Interpolation:")
        split.prop(self, "interpolation_type", text="", icon_only=True, emboss=False)
        split.enabled = False

        split = slicer_column.split(factor=0.3)
        split.label(text="Handle:")
        split.prop(self, "handle_type", text="", icon_only=True, emboss=False)
        split.enabled = False

    slicer_column.separator()

    split = slicer_column.split(factor=0.3)
    split.label(text="Range:")
    split.prop(self, "range_options", text="")

    slicer_column.separator()

    if self.insertion_type != "CLOSEST_FULL_FRAME":
        split = slicer_column.split(factor=0.3)
        split.label(text="Interpolation:")
        split.prop(self, "interpolation_type", text="")
        slicer_column.separator()

        split = slicer_column.split(factor=0.3)
        split.active = self.interpolation_type == "BEZIER"
        split.label(text="Handle:")
        split.prop(self, "handle_type", text="")
        slicer_column.separator()

    split = slicer_column.split(factor=0.3)
    split.label(text="Channels:")
    column = split.column(align=True)
    available_row = column.row(align=True)
    available_row.enabled = True
    if self.key_location or self.key_rotation or self.key_scale or self.key_custom:
        available_row.enabled = False
    available_row.prop(self, "key_available", icon="KEYFRAME_HLT", text="Available")

    column.separator()

    column.prop(self, "key_location", icon="CON_LOCLIMIT", text="Location")
    column.prop(self, "key_rotation", icon="CON_ROTLIMIT", text="Rotation")
    column.prop(self, "key_scale", icon="CON_SIZELIMIT", text="Scale")
    column.prop(self, "key_custom", icon="KEYINGSET", text="Custom Props")

    column.separator()
    column.prop(self, "kf_on_first", text="Add Keyframe on First Frame")
    column.prop(self, "kf_on_last", text="Add Keyframe on Last Frame")

    column.separator()
    column.prop(self, "clear_others", text="Clear Other Keyframes")
    column.prop(self, "clear_markers", text="Clear Markers")
    row = column.row(align=True)
    row.active = self.clear_markers
    row.prop(self, "keep_camera_markers", text="Keep Camera Markers")
    column.separator()


def AnimSlicerButton(layout, context, text, icon_value):
    slice_subrow = layout.row(align=True)
    slice_op = slice_subrow.operator(
        "anim.amp_anim_slicer",
        text=text,
        icon=icon_value,
    )


classes = (AMP_OT_AnimSlicer,)


def register():
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
    except Exception as e:
        utils.api.dprint(f"Registration failed for {cls}: {e}")


def unregister():
    try:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    except Exception as e:
        utils.api.dprint(f"Unregistration failed for {cls}: {e}")


if __name__ == "__main__":
    register()
