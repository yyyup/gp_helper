import bpy
from .. import utils


class AMP_OT_AnimLoop(bpy.types.Operator):

    bl_idname = "anim.amp_anim_loop"
    bl_label = "Anim Looper"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Make animation cyclical and looping
- Hold SHIFT to open the dialog."""

    repeat_options = [
        ("REPEAT", "Repeat", "Repeat the animation"),
        ("MIRROR", "Mirror", "Mirror the animation"),
        ("REPEAT_OFFSET", "Offset", "Offset the animation"),
        ("NONE", "None", "No change"),
    ]

    handles_options = [
        ("FREE", "Free", "Free handle type", "HANDLE_FREE", 0),
        ("ALIGNED", "Aligned", "Aligned handle type", "HANDLE_ALIGNED", 1),
        ("VECTOR", "Vector", "Vector handle type", "HANDLE_VECTOR", 2),
        ("AUTO", "Automatic", "Automatic handle type", "HANDLE_AUTO", 3),
        ("AUTO_CLAMPED", "Auto Clamped", "Auto Clamped handle type", "HANDLE_AUTOCLAMPED", 4),
        ("NO_CHANGE", "No Change", "No change", "CANCEL", 5),
    ]

    interpoaltion_options = [
        ("CONSTANT", "Constant", "Constant interpolation", "IPO_CONSTANT", 0),
        ("LINEAR", "Linear", "Linear interpolation", "IPO_LINEAR", 1),
        ("BEZIER", "Bezier", "Bezier interpolation", "IPO_BEZIER", 2),
        ("NO_CHANGE", "No Change", "No change", "CANCEL", 3),
    ]

    range_options = [
        ("MINMAX_ACTION", "Min/Max Keyframes Action", "Use min/max frames from the entire action"),
        ("ACTIVE_RANGE", "Active Range (Manual/Preview/Scene)", "Use the active range from the scene"),
        ("MINMAX_FCURVE", "Min/Max Keyframes per FCurve", "Use min/max frames per F-Curve"),
    ]

    before_mode: bpy.props.EnumProperty(
        name="Before Mode",
        items=repeat_options,
        default="REPEAT",
    )

    after_mode: bpy.props.EnumProperty(
        name="After Mode",
        items=repeat_options,
        default="REPEAT",
    )

    cycles_after: bpy.props.IntProperty(
        name="Count After",
        default=0,
        min=0,
    )

    cycles_before: bpy.props.IntProperty(
        name="Count Before",
        default=0,
        min=0,
    )

    cyclical: bpy.props.BoolProperty(
        name="Add/Remove Cyclical Modifier",
        default=True,
    )

    ensure_start_end_keyframes: bpy.props.BoolProperty(
        name="Ensure Start/End Keyframes",
        description="Ensure keyframes at start and end frames",
        default=True,
    )

    selection: bpy.props.EnumProperty(
        name="Apply to",
        items=[
            ("ALL", "Active Action", "All the action's F-Curves"),
            ("SELECTED", "Selected Curves", "Only selected F-Curves"),
        ],
        default="ALL",
    )

    match_loop: bpy.props.EnumProperty(
        name="Match Loop",
        items=[
            ("START_TO_END", "Start to End", "Copy initial pose to the end"),
            ("END_TO_START", "End to Start", "Copy final pose to the start"),
            ("NONE", "None", "No matching"),
        ],
        default="START_TO_END",
    )

    loop_handles: bpy.props.EnumProperty(
        name="Start/End Handles",
        items=handles_options,
        default="AUTO_CLAMPED",
    )

    loop_interpolation: bpy.props.EnumProperty(
        name="Start/End Interpolation",
        items=interpoaltion_options,
        default="BEZIER",
    )

    intermediate_handle_types: bpy.props.EnumProperty(
        name="Intermediate Handles",
        items=handles_options,
        default="NO_CHANGE",
    )

    intermediate_handle_interpolation: bpy.props.EnumProperty(
        name="Intermediate Interpolation",
        items=interpoaltion_options,
        default="NO_CHANGE",
    )

    cycle_aware: bpy.props.BoolProperty(
        name="Enable Cycle Aware Keying",
        default=True,
    )

    range_mode: bpy.props.EnumProperty(
        name="Range",
        items=range_options,
        default="MINMAX_ACTION",
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        if event.shift:
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if not obj.animation_data or not obj.animation_data.action or context.selected_visible_fcurves is None:
            self.report({"ERROR"}, "No animation data found.")
            return {"CANCELLED"}

        action = obj.animation_data.action
        # fcurves = action.fcurves[:] if self.selection == "ALL" else context.selected_visible_fcurves
        fcurves = list(utils.curve.all_fcurves(action)) if self.selection == "ALL" else context.selected_visible_fcurves
        context.scene.tool_settings.use_keyframe_cycle_aware = self.cycle_aware

        if not self.cyclical:
            for fc in fcurves:
                self.remove_cyclic_modifier_from_fcurves(fc)
            self.report({"INFO"}, "Cyclical modifiers removed.")
            return {"FINISHED"}

        scene = context.scene
        if self.range_mode == "ACTIVE_RANGE":
            start_frame = scene.frame_start
            end_frame = scene.frame_end
        elif self.range_mode == "MINMAX_ACTION":
            all_frames = [kf.co.x for fc in fcurves for kf in fc.keyframe_points]
            if not all_frames:
                self.report({"ERROR"}, "No keyframes found.")
                return {"CANCELLED"}
            start_frame = min(all_frames)
            end_frame = max(all_frames)
        else:
            # For MINMAX_FCURVE, handled per fcurve inside the loop
            start_frame = None
            end_frame = None

        for fcurve in fcurves:
            if not fcurve.keyframe_points:
                continue

            if self.range_mode == "MINMAX_FCURVE":
                fc_frames = [kf.co.x for kf in fcurve.keyframe_points]
                start_fc_frame = min(fc_frames)
                end_fc_frame = max(fc_frames)
            else:
                start_fc_frame = start_frame
                end_fc_frame = end_frame

            if self.ensure_start_end_keyframes:
                self.ensure_keyframe_exists(fcurve, start_fc_frame)
                self.ensure_keyframe_exists(fcurve, end_fc_frame)

            if self.intermediate_handle_types != "NO_CHANGE":
                for kf in fcurve.keyframe_points:
                    if kf.co.x not in (start_fc_frame, end_fc_frame):
                        kf.handle_left_type = self.intermediate_handle_types
                        kf.handle_right_type = self.intermediate_handle_types

            if self.intermediate_handle_interpolation != "NO_CHANGE":
                for kf in fcurve.keyframe_points:
                    if kf.co.x not in (start_fc_frame, end_fc_frame):
                        kf.interpolation = self.intermediate_handle_interpolation

            if self.cyclical:
                self.add_cyclic_modifier_to_fcurves(
                    fcurve,
                    use_restricted_range=False,
                    start_frame=start_fc_frame,
                    end_frame=end_fc_frame,
                )
            else:
                self.remove_cyclic_modifier_from_fcurves(fcurve)

            if self.match_loop == "START_TO_END":
                self.copy_keyframe(fcurve, start_fc_frame, end_fc_frame)
            elif self.match_loop == "END_TO_START":
                self.copy_keyframe(fcurve, end_fc_frame, start_fc_frame)

            self.set_keyframe_properties(fcurve, {start_fc_frame, end_fc_frame})
            fcurve.update()

        return {"FINISHED"}

    def ensure_keyframe_exists(self, fcurve, frame):
        if not any(kf.co.x == frame for kf in fcurve.keyframe_points):
            # Insert a default keyframe at the given frame
            value = fcurve.evaluate(frame)
            fcurve.keyframe_points.insert(frame=frame, value=value)

    def add_cyclic_modifier_to_fcurves(self, fcurve, use_restricted_range=False, start_frame=0, end_frame=250):
        self.remove_cyclic_modifier_from_fcurves(fcurve, name="AnimLooper")
        cycles_modifier = fcurve.modifiers.new(type="CYCLES")
        if cycles_modifier:
            cycles_modifier.name = "AnimLooper"
            cycles_modifier.mode_before = self.before_mode
            cycles_modifier.cycles_before = self.cycles_before
            cycles_modifier.mode_after = self.after_mode
            cycles_modifier.cycles_after = self.cycles_after
            cycles_modifier.use_restricted_range = use_restricted_range
            if use_restricted_range:
                cycles_modifier.frame_start = start_frame
                cycles_modifier.frame_end = end_frame

    def remove_cyclic_modifier_from_fcurves(self, fcurve, name="AnimLooper"):
        looper_cycles_modifier = next(
            (mod for mod in fcurve.modifiers if mod.type == "CYCLES" and mod.name == name), None
        )
        if looper_cycles_modifier:
            fcurve.modifiers.remove(looper_cycles_modifier)
        else:
            try:
                fcurve.modifiers.remove(next(mod for mod in fcurve.modifiers if mod.type == "CYCLES"))
            except:
                pass

    def copy_keyframe(self, fcurve, source_frame, target_frame):
        source_kf = next((kf for kf in fcurve.keyframe_points if kf.co.x == source_frame), None)
        target_kf = next((kf for kf in fcurve.keyframe_points if kf.co.x == target_frame), None)

        if not source_kf:
            self.report({"WARNING"}, f"No source keyframe found at frame {source_frame} on F-Curve {fcurve.data_path}.")
            return

        if not target_kf:
            target_kf = fcurve.keyframe_points.insert(frame=target_frame, value=source_kf.co.y)
        target_kf.co_ui.y = source_kf.co_ui.y

    def set_keyframe_properties(self, fcurve, frames):
        for frame in frames:
            keyframe = next((kf for kf in fcurve.keyframe_points if kf.co.x == frame), None)
            if keyframe:
                if self.loop_interpolation != "NO_CHANGE":
                    keyframe.interpolation = self.loop_interpolation
                if self.loop_handles != "NO_CHANGE":
                    keyframe.handle_left_type = self.loop_handles
                    keyframe.handle_right_type = self.loop_handles
            else:
                self.report({"WARNING"}, f"No keyframe found at frame {frame} on F-Curve {fcurve.data_path}.")

    def draw(self, context):

        layout = self.layout
        layout.ui_units_x = 20
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(self, "cyclical")
        layout.prop(self, "cycle_aware")
        layout.separator()
        col = layout.column(align=True)
        col.enabled = self.cyclical
        col.prop(self, "range_mode")
        col.prop(self, "ensure_start_end_keyframes")
        col.separator()
        col.prop(self, "selection")
        col.prop(self, "match_loop")
        col.separator()
        col.prop(self, "before_mode")
        col.prop(self, "cycles_before")
        col.prop(self, "after_mode")
        col.prop(self, "cycles_after")
        col.separator()
        col.prop(self, "loop_handles")
        col.prop(self, "loop_interpolation")
        col.separator()
        col.prop(self, "intermediate_handle_types")
        col.prop(self, "intermediate_handle_interpolation")


def draw_animloop_panel(self, context):
    layout = self.layout
    AnimLoopButton(layout, context)


def AnimLoopButton(layout, context, text="Anim Loop", icon_value=1):
    layout.operator(
        "anim.amp_anim_loop",
        text=text,
        icon_value=icon_value,
    )


classes = [
    AMP_OT_AnimLoop,
]


def register_properties():
    pass


def unregister_properties():
    pass


def register():
    register_properties()
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
    except:
        utils.dutils.dprint(f"{cls} already registered, skipping...")


def unregister():
    try:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    except:
        utils.dutils.dprint(f"{cls} not found, skipping...")
    unregister_properties()


if __name__ == "__main__":
    register()
