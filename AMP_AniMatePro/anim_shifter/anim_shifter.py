import bpy
from bpy.props import EnumProperty, IntProperty, BoolProperty, FloatProperty
from bpy.types import Operator, Panel
from .. import utils


class AMP_OT_AnimShifter(Operator):

    bl_idname = "anim.amp_anim_shifter"
    bl_label = "Anim Shifter"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Shift animation keyframes.
Hold Shift while clicking to skip the options panel."""

    # New scope property (exact same as timewarper)
    scope: bpy.props.EnumProperty(
        name="Scope",
        description="Scope of the Time Warper tool",
        items=(
            ("SCENE", "Scene", "Apply to keyframes in the entire scene"),
            ("ACTION", "Action", "Apply to all fcurves in the active object's action"),
            (
                "SELECTED_ELEMENTS",
                "Selected Elements",
                "Apply to animation data for any selected object or selected bones in Pose Mode",
            ),
            ("VISIBLE_FCURVES", "Visible FCurves", "Apply to all visible fcurves"),
            ("SELECTED_KEYS", "Selected Keys", "Apply to selected keyframes on visible fcurves"),
        ),
        default="ACTION",
    )

    shift_amount: IntProperty(
        name="Shift Amount",
        description="""Amount to shift the keyframes by:
- Positive values shift keyframes to the right.
- Negative values shift keyframes to the left.""",
        default=5,
    )
    add_on_slice: BoolProperty(
        name="Add Keyframe on Slice",
        description="""Insert a keyframe at the slicing frame if the F-Curves have no keyframes on the slicing frame.""",
        default=True,
    )
    add_hold_keyframes: BoolProperty(
        name="Add Hold Keyframes",
        description="""Insert keyframes to hold the animation if the F-Curves have no keyframes on the slicing frame.""",
        default=True,
    )

    # current_frame: IntProperty(
    #     name="Current Frame",
    #     description="The current frame when the operator is invoked",
    #     default=0,
    # )

    # nla_offset: IntProperty(
    #     name="NLA Offset",
    #     description="Offset value for NLA strips",
    #     default=0,
    # )

    # def invoke(self, context, event):
    #     self.current_frame = context.scene.frame_current
    #     if not event.shift:
    #         wm = context.window_manager
    #         return wm.invoke_props_dialog(self)
    #     obj = context.active_object
    #     self.nla_offset = utils.curve.get_nla_strip_offset(obj)
    #     return self.execute(context)
    current_frame: IntProperty(
        name="Current Frame",
        description="The current frame when the operator is invoked",
        default=0,
    )
    effective_frame: FloatProperty(
        name="Effective Frame",
        description="The effective frame when the operator is invoked",
        default=0,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def invoke(self, context, event):
        if not event.shift:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        self.draw_anim_shifter_options(layout, context)

    def draw_anim_shifter_options(self, layout, context):
        container = layout.box()
        layout.use_property_split = True
        layout.use_property_decorate = False

        slicer_column = container.column()
        slicer_column.prop(self, "scope")
        slicer_column.prop(self, "shift_amount")
        slicer_column.prop(self, "add_on_slice")
        slicer_column.prop(self, "add_hold_keyframes")

    def collect_material_fcurves(self, material, all_fcurves):
        """Collect F-Curves from material and its node tree."""
        if material.animation_data and material.animation_data.action:
            all_fcurves.extend(material.animation_data.action.fcurves)

        if material.node_tree and material.node_tree.animation_data and material.node_tree.animation_data.action:
            action_fcurves = material.node_tree.animation_data.action.fcurves
            for fcurve in action_fcurves:
                if "nodes[" in fcurve.data_path and ".inputs[" in fcurve.data_path:
                    all_fcurves.append(fcurve)

    def insert_hold_keyframe(self, fcurves):
        """Insert a hold keyframe at the current frame for all F-Curves if not present."""
        for fcurve in fcurves:
            if not any(kp.co.x == self.current_frame for kp in fcurve.keyframe_points):
                value = fcurve.evaluate(self.current_frame)
                fcurve.keyframe_points.insert(self.current_frame, value, options={"FAST"})
        for fcurve in fcurves:
            fcurve.update()

    def shift_keyframes_and_copy_value(self, fcurves, shift):
        """Shift keyframes and optionally copy the current value to the target frame."""
        for fcurve in fcurves:
            current_value = fcurve.evaluate(self.current_frame)
            target_frame = self.current_frame + shift

            if self.add_on_slice:
                if not any(kp.co.x == target_frame for kp in fcurve.keyframe_points):
                    fcurve.keyframe_points.insert(target_frame, current_value, options={"FAST"})

            for keyframe in fcurve.keyframe_points:
                if (shift > 0 and keyframe.co.x > self.current_frame) or (
                    shift < 0 and keyframe.co.x < self.current_frame
                ):
                    keyframe.co_ui.x += shift

            fcurve.update()

    def find_frame(self, layer, frame_number):
        """Find a Grease Pencil frame by its frame_number."""
        for frame in layer.frames:
            if frame.frame_number == frame_number:
                return frame
        return None

    def find_previous_frame(self, layer, frame_number):
        """Find the nearest previous Grease Pencil frame before the given frame_number."""
        previous_frames = [f.frame_number for f in layer.frames if f.frame_number < frame_number]
        if not previous_frames:
            return None
        previous_frame_number = max(previous_frames)
        return self.find_frame(layer, previous_frame_number)

    def find_next_frame(self, layer, frame_number):
        """Find the nearest next Grease Pencil frame after the given frame_number."""
        next_frames = [f.frame_number for f in layer.frames if f.frame_number > frame_number]
        if not next_frames:
            return None
        next_frame_number = min(next_frames)
        return self.find_frame(layer, next_frame_number)

    def shift_gpencil_keyframes(self, gpencil_objects, shift, context):
        """Shift Grease Pencil frames."""
        for gpencil in gpencil_objects:
            for layer in gpencil.data.layers:

                frames_to_shift = [
                    frame.frame_number
                    for frame in layer.frames
                    if (shift > 0 and frame.frame_number > self.current_frame)
                    or (shift < 0 and frame.frame_number < self.current_frame)
                ]

                frames_to_shift.sort(reverse=(shift > 0))

                print("Frames to shift:", frames_to_shift)

                for frame_number in frames_to_shift:
                    try:
                        layer.frames.move(frame_number, frame_number + shift)
                    except RuntimeError as e:
                        print(f"Failed to shift frame {frame_number} in layer '{layer.name}': {e}")
                    print(f"Shifted frame {frame_number} to {frame_number + shift}")

                if self.add_on_slice:
                    new_slice_frame = self.current_frame

                    if new_slice_frame < context.scene.frame_start or new_slice_frame > context.scene.frame_end:
                        self.report(
                            {"WARNING"},
                            f"New slice frame {new_slice_frame} is out of the scene's frame range. Skipping add_on_slice for layer '{layer.name}'.",
                        )
                        continue

                    if self.find_frame(layer, new_slice_frame):
                        self.report(
                            {"WARNING"},
                            f"Frame {new_slice_frame} already exists in layer '{layer.name}'. Skipping add_on_slice.",
                        )
                        continue

                    source_frame = self.find_previous_frame(layer, self.current_frame)
                    if not source_frame:
                        source_frame = self.find_next_frame(layer, self.current_frame)

                    if source_frame:
                        try:
                            layer.frames.copy(source_frame.frame_number, new_slice_frame)
                        except RuntimeError as e:
                            self.report(
                                {"ERROR"},
                                f"Failed to copy frame {source_frame.frame_number} to {new_slice_frame} in layer '{layer.name}': {e}",
                            )
                    else:
                        self.report(
                            {"WARNING"},
                            f"No suitable source frame found to add slice at frame {new_slice_frame} in layer '{layer.name}'.",
                        )

                if self.add_hold_keyframes:
                    hold_frame_number = self.current_frame + shift

                    if hold_frame_number < context.scene.frame_start or hold_frame_number > context.scene.frame_end:
                        self.report(
                            {"WARNING"},
                            f"Hold frame {hold_frame_number} is out of the scene's frame range. Skipping add_hold_keyframes for layer '{layer.name}'.",
                        )
                    elif self.find_frame(layer, hold_frame_number):
                        self.report(
                            {"WARNING"},
                            f"Hold frame {hold_frame_number} already exists in layer '{layer.name}'. Skipping add_hold_keyframes.",
                        )
                    else:
                        source_frame = self.find_previous_frame(layer, self.current_frame)
                        if not source_frame:
                            source_frame = self.find_next_frame(self.current_frame)

                        if source_frame:
                            try:
                                layer.frames.copy(source_frame.frame_number, hold_frame_number)
                            except RuntimeError as e:
                                self.report(
                                    {"ERROR"},
                                    f"Failed to copy frame {source_frame.frame_number} to {hold_frame_number} in layer '{layer.name}': {e}",
                                )
                        else:
                            self.report(
                                {"WARNING"},
                                f"No suitable source frame found to add hold frame at {hold_frame_number} in layer '{layer.name}'.",
                            )

    def execute(self, context):
        self.current_frame = context.scene.frame_current
        obj = context.active_object
        self.effective_frame = int(obj.animation_data.nla_tweak_strip_time_to_scene(self.current_frame, invert=True))
        print(self.effective_frame)
        fcurves = utils.curve.gather_fcurves(self.scope, context)
        target_frame = self.effective_frame + self.shift_amount

        for fcu in fcurves:
            # Evaluate fcurve at effective frame instead of current frame.
            current_value = fcu.evaluate(self.effective_frame)

            if self.add_hold_keyframes:
                if not any(round(kp.co.x) == round(self.effective_frame) for kp in fcu.keyframe_points):
                    fcu.keyframe_points.insert(self.effective_frame, current_value, options={"FAST"})

            for kf in fcu.keyframe_points:
                # Shift keyframes relative to effective frame.
                if self.shift_amount > 0 and kf.co.x > self.effective_frame:
                    kf.co_ui.x += self.shift_amount
                elif self.shift_amount < 0 and kf.co.x < self.effective_frame:
                    kf.co_ui.x += self.shift_amount

            if self.add_on_slice:
                if not any(round(kp.co.x) == round(target_frame) for kp in fcu.keyframe_points):
                    fcu.keyframe_points.insert(target_frame, current_value, options={"FAST"})

        for fcurve in context.editable_fcurves:
            fcurve.update()

        # Adjust scene frame range.
        if self.shift_amount > 0:
            context.scene.frame_end += self.shift_amount
        else:
            context.scene.frame_start += self.shift_amount

        # Optionally set the scene frame to the effective frame.
        context.scene.frame_current = int(self.current_frame)
        self.report({"INFO"}, "Animation keyframes shifted successfully.")
        return {"FINISHED"}


def AnimShifterButton(layout, context, text, icon_value):
    row = layout.row(align=True)
    row.operator(
        "anim.amp_anim_shifter",
        text=text,
        icon_value=icon_value,
    )


classes = (AMP_OT_AnimShifter,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
