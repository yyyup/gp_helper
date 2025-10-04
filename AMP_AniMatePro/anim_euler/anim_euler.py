import bpy
import math
import numpy as np
from .. import utils
from mathutils import Euler, Quaternion


def euler_to_quaternion(euler, order):
    euler_rad = Euler((euler[0], euler[1], euler[2]), order)
    return np.array(euler_rad.to_quaternion())


def quaternion_to_euler(quaternion, order):
    quat = Quaternion((quaternion[0], quaternion[1], quaternion[2], quaternion[3]))
    euler_rad = quat.to_euler(order)
    return np.array([euler_rad.x, euler_rad.y, euler_rad.z])


def quaternion_difference(quat1, quat2):
    """Calculate the difference between two quaternions."""
    conjugate_quat2 = np.array([quat2[0], -quat2[1], -quat2[2], -quat2[3]])
    diff = np.array(
        [
            quat1[0] * conjugate_quat2[0]
            - quat1[1] * conjugate_quat2[1]
            - quat1[2] * conjugate_quat2[2]
            - quat1[3] * conjugate_quat2[3],
            quat1[0] * conjugate_quat2[1]
            + quat1[1] * conjugate_quat2[0]
            + quat1[2] * conjugate_quat2[3]
            - quat1[3] * conjugate_quat2[2],
            quat1[0] * conjugate_quat2[2]
            - quat1[1] * conjugate_quat2[3]
            + quat1[2] * conjugate_quat2[0]
            + quat1[3] * conjugate_quat2[1],
            quat1[0] * conjugate_quat2[3]
            + quat1[1] * conjugate_quat2[2]
            - quat1[2] * conjugate_quat2[1]
            + quat1[3] * conjugate_quat2[0],
        ]
    )
    norm = np.linalg.norm(diff)
    if norm > 0:
        diff /= norm
    return diff


def find_euler_rotation_fcurves(action, data_path_prefix=""):
    """Find the fcurves corresponding to the Euler rotation angles."""
    fcurves = {"X": None, "Y": None, "Z": None}
    for fcurve in utils.curve.all_fcurves(action):
        if fcurve.data_path.startswith(data_path_prefix) and fcurve.data_path.endswith("rotation_euler"):
            if fcurve.array_index == 0:
                fcurves["X"] = fcurve
            elif fcurve.array_index == 1:
                fcurves["Y"] = fcurve
            elif fcurve.array_index == 2:
                fcurves["Z"] = fcurve
    return fcurves


def find_first_keyframe(action):
    """Find the first keyframe in the given action."""
    keyframes = []
    for fcurve in utils.curve.all_fcurves(action):
        for kp in fcurve.keyframe_points:
            keyframes.append(kp.co.x)
    if not keyframes:
        return None
    return int(min(keyframes))


class AMP_OT_EulerFilter(bpy.types.Operator):

    bl_idname = "anim.amp_euler_filter"
    bl_label = "Euler Filter to Range"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Apply Euler filter to current range
Range:
    - If preview range is set it will use it.
    - If no preview range and keyframes selected the range will be between the first and
      last selected keyframes.
    - Otherwise the range will be the entire scene"""

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        start_frame, end_frame = utils.curve.determine_frame_range_priority(self, context)

        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                self.apply_euler_filter_to_action(obj.animation_data.action, start_frame, end_frame, obj, context)

        return {"FINISHED"}

    def apply_euler_filter_to_action(self, action, start_frame, end_frame, obj, context):
        if obj.type != "ARMATURE":
            data_path_prefix = ""
            fcurves = find_euler_rotation_fcurves(action, data_path_prefix)
            if not all(fcurves.values()):
                return

            rotation_mode = obj.rotation_mode

            for frame in range(start_frame, end_frame + 1):
                euler_angles = [fcurves[axis].evaluate(frame) for axis in "XYZ"]
                quat_before = euler_to_quaternion(euler_angles, rotation_mode)

                # Insert filtering logic here, if needed

                euler_angles_after = quaternion_to_euler(quat_before, rotation_mode)
                quat_after = euler_to_quaternion(euler_angles_after, rotation_mode)

                quat_diff = quaternion_difference(quat_before, quat_after)

                self.apply_filter_to_keyframe(euler_angles_after, fcurves, frame, quat_diff)

            # Optional: key rotation_mode logic commented out below
            # first_frame = find_first_keyframe(action)
            # if first_frame is not None:
            #     bpy.context.scene.frame_set(first_frame)
            #     obj.keyframe_insert(data_path="rotation_mode", frame=first_frame)

        else:
            for bone in obj.pose.bones:
                bone_data_path = f'pose.bones["{bone.name}"].'
                fcurves = find_euler_rotation_fcurves(action, bone_data_path)
                if not all(fcurves.values()):
                    continue

                rotation_mode = bone.rotation_mode

                for frame in range(start_frame, end_frame + 1):
                    euler_angles = [fcurves[axis].evaluate(frame) for axis in "XYZ"]
                    quat_before = euler_to_quaternion(euler_angles, rotation_mode)

                    # Insert filtering logic here, if needed

                    euler_angles_after = quaternion_to_euler(quat_before, rotation_mode)
                    quat_after = euler_to_quaternion(euler_angles_after, rotation_mode)

                    quat_diff = quaternion_difference(quat_before, quat_after)

                    self.apply_filter_to_keyframe(euler_angles_after, fcurves, frame, quat_diff)

    def apply_filter_to_keyframe(self, euler_angles, fcurves, frame, quat_diff):
        for i, axis in enumerate("XYZ"):
            fcurve = fcurves[axis]
            keyframe_point = next((kp for kp in fcurve.keyframe_points if kp.co[0] == frame), None)
            if keyframe_point:
                delta_left = keyframe_point.co - keyframe_point.handle_left
                delta_right = keyframe_point.handle_right - keyframe_point.co

                keyframe_point.co[1] = euler_angles[i]

                keyframe_point.handle_left = keyframe_point.co - delta_left
                keyframe_point.handle_right = keyframe_point.co + delta_right

            fcurve.update()





def convert_rotation_order(obj, bone, new_rotation_mode, is_bone):
    """
    Core function to convert rotation order for a given object or bone, optimizing for both
    quaternion conversions and Euler-to-Euler conversions.
    """
    action = obj.animation_data.action if obj.animation_data else None
    if action:
        fcurves = utils.curve.all_fcurves(action)
        keyframes = set()
        for fcurve in fcurves:
            if (is_bone and fcurve.data_path.startswith('pose.bones["' + bone.name + '"]')) or (
                not is_bone and "rotation" in fcurve.data_path
            ):
                for keyframe_point in fcurve.keyframe_points:
                    keyframes.add(int(keyframe_point.co.x))

        original_mode = bone.rotation_mode if is_bone else obj.rotation_mode
        target = bone if is_bone else obj

        for frame in sorted(keyframes):
            
            bpy.context.scene.frame_set(frame)      
                    
            if original_mode == "QUATERNION" and new_rotation_mode != "QUATERNION":
                quat = target.rotation_quaternion
                euler = quat.to_euler(new_rotation_mode)
                target.rotation_euler = euler
                data_path = "rotation_euler"
                
            elif new_rotation_mode == "QUATERNION":
                euler = target.rotation_euler.copy()
                quat = euler.to_quaternion()
                target.rotation_quaternion = quat
                data_path = "rotation_quaternion"
                
            else:
                current_euler = target.rotation_euler.copy()
                rotation_matrix = current_euler.to_matrix()
                new_euler = rotation_matrix.to_euler(new_rotation_mode)
                target.rotation_euler = new_euler
                data_path = "rotation_euler"
                
            target.keyframe_insert(data_path=data_path, index=-1, frame=frame)

        target.rotation_mode = new_rotation_mode

        cleanup_fcurves(action, bone, original_mode, new_rotation_mode, is_bone)

        print(f"Baked animation for {target.name} to {new_rotation_mode}.")


def cleanup_fcurves(action, bone, original_mode, new_rotation_mode, is_bone):
    """
    Clean up unnecessary fcurves after rotation conversion.
    """
    data_path_check = 'pose.bones["' + bone.name + '"].' if is_bone else "rotation"
    for fcurve in list(utils.curve.all_fcurves(action)):
        if fcurve.data_path.startswith(data_path_check):
            if (original_mode == "QUATERNION" and "rotation_quaternion" in fcurve.data_path) or (
                new_rotation_mode == "QUATERNION" and "rotation_euler" in fcurve.data_path
            ):
                utils.curve.remove_fcurve_from_action(action, fcurve)


def calculate_gimbal_risk(obj, bone_name, mode, context):
    """
    Calculates the gimbal lock risk for given animation data and rotation mode.
    Supports both Euler and quaternion-based animations.
    """
    if obj.type == "ARMATURE" and bone_name:
        action = obj.animation_data.action if obj.animation_data else None
        if not action:
            return 0
        fcurves = [
            fc
            for fc in utils.curve.all_fcurves(action)
            if fc.data_path.startswith('pose.bones["{}"]'.format(bone_name))
        ]
        bone = obj.pose.bones[bone_name]
        use_quat = bone.rotation_mode == "QUATERNION"
    else:
        if not obj.animation_data or not obj.animation_data.action:
            return 0
        action = obj.animation_data.action
        fcurves = utils.curve.all_fcurves(action)
        use_quat = obj.rotation_mode == "QUATERNION"

    risk_scores = []
    keyframes = set()
    if use_quat:
        for fcurve in fcurves:
            if "rotation_quaternion" in fcurve.data_path:
                for kp in fcurve.keyframe_points:
                    keyframes.add(kp.co.x)
    else:
        for fcurve in fcurves:
            if "rotation_euler" in fcurve.data_path:
                for kp in fcurve.keyframe_points:
                    keyframes.add(kp.co.x)

    for frame in sorted(keyframes):
        context.scene.frame_current = int(frame)
        if obj.type == "ARMATURE" and bone_name:
            bone = obj.pose.bones[bone_name]
            if bone.rotation_mode == "QUATERNION":
                euler_angles = bone.rotation_quaternion.to_euler(mode)
            else:
                euler_angles = bone.rotation_euler
        else:
            if obj.rotation_mode == "QUATERNION":
                euler_angles = obj.rotation_quaternion.to_euler(mode)
            else:
                euler_angles = obj.rotation_euler
        converted_euler = euler_angles.to_quaternion().to_euler(mode)
        mid_angle_deviation = abs((converted_euler[1] + math.pi / 2) % math.pi - math.pi / 2)
        risk = mid_angle_deviation / (math.pi / 2)
        risk_scores.append(risk)

    average_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
    return average_risk


def recommend_best_rotation_mode(obj, context):
    """Recommend the best rotation mode (Euler order) to minimize gimbal lock risk."""
    bone = context.active_pose_bone if obj and obj.type == "ARMATURE" and context.active_pose_bone else None
    bone_name = bone.name if bone else ""
    props = bpy.context.scene.amp_animeuler_properties

    if not obj or not (obj.animation_data and obj.animation_data.action):
        props.recommended_mode = "No animation"
        props.sorted_modes = ""
        return ""

    candidate_modes = ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]
    risks = []
    for mode in candidate_modes:
        risk = calculate_gimbal_risk(obj, bone_name, mode, context)
        risks.append((mode, risk))
    risks_sorted = sorted(risks, key=lambda x: x[1])
    best_mode, lowest_risk = risks_sorted[0]
    props.recommended_mode = best_mode
    props.lowest_risk = "{:.3f}".format(lowest_risk)
    # props.sorted_modes = " > ".join([f"{m}({r:.3f})" for m, r in risks_sorted])
    props.sorted_modes = " > ".join([f"{m}" for m, r in risks_sorted])
    print(f"Recommended rotation mode: {best_mode} with an average risk of {lowest_risk:.3f}")
    return best_mode


class AMP_OT_rotation_mode_recommendation(bpy.types.Operator):
    """Recommend the best rotation mode for the selected object"""

    bl_idname = "anim.amp_rotation_mode_recommendation"
    bl_label = "Calculate Recommended Euler Order"

    recommended_mode: bpy.props.StringProperty(default="")
    lowest_risk: bpy.props.StringProperty(default="")

    def execute(self, context):
        original_frame = context.scene.frame_current
        obj = context.active_object
        props = bpy.context.scene.amp_animeuler_properties
        props.recommended_mode = ""
        props.lowest_risk = ""
        props.sorted_modes = ""

        self.recommended_mode = recommend_best_rotation_mode(obj, context)
        context.scene.frame_current = original_frame
        self.bl_label = f"Recommended: {self.recommended_mode}"
        return {"FINISHED"}

    @classmethod
    def description(cls, context, properties):
        if properties.recommended_mode:
            return f"Recommended Mode: {properties.recommended_mode}"
        return "Calculate the best rotation mode for the selected object."


class AMP_PT_rotation_mode_recommendation(bpy.types.Panel):
    """Panel to recommend and apply rotation mode changes"""

    bl_label = "Rotation Mode Recommendation"
    bl_idname = "AMP_PT_rotation_mode_recommendation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 12

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        element = context.active_pose_bone if obj and obj.type == "ARMATURE" else obj
        props = context.scene.amp_animeuler_properties

        # Display the recommended rotation ranking instead of just "Current"
        layout.label(text=f"Current: {element.rotation_mode}")

        recommendation = (
            "Calculate Recommended Euler Order"
            if props.lowest_risk == ""
            else ("Recommended: " + props.recommended_mode)
        )

        op = layout.operator("anim.amp_rotation_mode_recommendation", text=recommendation)
        layout.separator()
        if props.sorted_modes:
            layout.label(text="Rotation Ranking:")
            layout.label(text=props.sorted_modes if props.sorted_modes else "Not calculated")
        layout.separator()

        for mode in ["QUATERNION", "XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]:
            op = layout.operator(
                "anim.amp_bake_to_rotation_mode",
                text=f"Bake to {mode}",
                depress=props.recommended_mode == mode,
            )
            op.new_rotation_mode = mode

        layout.prop(props, "key_rotation_mode", text="Key Rotation Mode")


class AMP_OT_bake_to_rotation_mode(bpy.types.Operator):
    """Bake animation to a specified rotation mode"""

    bl_idname = "anim.amp_bake_to_rotation_mode"
    bl_label = "Bake to Rotation Mode"
    bl_options = {"REGISTER", "UNDO"}

    new_rotation_mode: bpy.props.EnumProperty(
        name="New Rotation Mode",
        description="Select the new rotation mode to bake the animation into",
        items=[
            ("XYZ", "XYZ Euler", ""),
            ("XZY", "XZY Euler", ""),
            ("YXZ", "YXZ Euler", ""),
            ("YZX", "YZX Euler", ""),
            ("ZXY", "ZXY Euler", ""),
            ("ZYX", "ZYX Euler", ""),
            ("QUATERNION", "Quaternion", ""),
        ],
        default="XYZ",
    )

    def execute(self, context):
        original_frame = context.scene.frame_current
        anim = context.active_object.animation_data
        
        if not anim or not anim.action:
            self.report({"WARNING"}, "No animation data found in the active object.")
            return {"CANCELLED"}
        
        new_rotation_mode = self.new_rotation_mode
        props = context.scene.amp_animeuler_properties
        key_rotation_mode = props.key_rotation_mode

        in_pose_mode = (
            context.active_object and
            context.active_object.type == "ARMATURE" and
            context.active_object.mode == "POSE"
        )

        if in_pose_mode:
            armature = context.active_object
            selected_bones = [bone for bone in armature.pose.bones if bone.bone.select]
            # Prevent baking if bones are already in that mode
            if selected_bones and all(b.rotation_mode == new_rotation_mode for b in selected_bones):
                self.report({'WARNING'}, 
                            f"Selected bones already in '{new_rotation_mode}' mode – bake cancelled.")
                return {'CANCELLED'}

            if not selected_bones:
                self.report({"WARNING"}, "No bones selected in Pose Mode.")
                return {"CANCELLED"}

            for bone in selected_bones:
                if not armature.animation_data or not armature.animation_data.action:
                    self.report({"WARNING"}, f"Armature '{armature.name}' has no animation data.")
                    continue

                convert_rotation_order(armature, bone, new_rotation_mode, is_bone=True)

                if key_rotation_mode:
                    action = armature.animation_data.action
                    first_frame = find_first_keyframe(action)
                    if first_frame is not None:
                        data_path = f'pose.bones["{bone.name}"].rotation_mode'
                        self.remove_keyframes(armature, data_path)
                        armature.keyframe_insert(data_path=data_path, frame=first_frame)
                        self.report({"INFO"}, f"Keyed rotation_mode for bone '{bone.name}' at frame {first_frame}.")
        else:
            selected_objects = context.selected_objects
            # Prevent baking if objects are already in that mode
            if selected_objects and all(obj.rotation_mode == new_rotation_mode for obj in selected_objects):
                self.report({'WARNING'}, 
                            f"Selected objects already in '{new_rotation_mode}' mode – bake cancelled.")
                return {'CANCELLED'}

            if not selected_objects:
                self.report({"WARNING"}, "No objects selected.")
                return {"CANCELLED"}

            for obj in selected_objects:
                if not obj.animation_data or not obj.animation_data.action:
                    self.report({"WARNING"}, f"Object '{obj.name}' has no animation data.")
                    continue

                convert_rotation_order(obj, None, new_rotation_mode, is_bone=False)

                if key_rotation_mode:
                    action = obj.animation_data.action
                    first_frame = find_first_keyframe(action)
                    if first_frame is not None:
                        data_path = "rotation_mode"
                        self.remove_keyframes(obj, data_path)
                        obj.keyframe_insert(data_path=data_path, frame=first_frame)
                        self.report({"INFO"}, f"Keyed rotation_mode for object '{obj.name}' at frame {first_frame}.")

        context.scene.frame_current = original_frame 

        if new_rotation_mode != "QUATERNION":
            bpy.ops.graph.euler_filter()
            
        self.report({"INFO"}, f"Baked animation to '{new_rotation_mode}' rotation mode.")
        return {"FINISHED"}

    def remove_keyframes(self, obj, data_path):
        if not obj.animation_data or not obj.animation_data.action:
            return
        action = obj.animation_data.action
        fcurves_to_remove = [fcurve for fcurve in utils.curve.all_fcurves(action) if fcurve.data_path == data_path]
        for fcurve in fcurves_to_remove:
            utils.curve.remove_fcurve_from_action(action, fcurve)
            self.report({"INFO"}, f"Removed existing keyframes for '{data_path}' on '{obj.name}'.")


class AMP_OT_EulerRotRecomButton(bpy.types.Operator):
    """Show rotation mode recommendation panel"""

    bl_idname = "anim.amp_euler_rotation_recommendations"
    bl_label = "Recommend Rotation Mode"

    def execute(self, context):
        props = bpy.context.scene.amp_animeuler_properties
        props.recommended_mode = ""
        props.lowest_risk = ""
        props.sorted_modes = ""
        bpy.ops.wm.call_panel(name="AMP_PT_rotation_mode_recommendation", keep_open=True)
        return {"FINISHED"}


class AMP_PT_AnimEuler(bpy.types.Panel):
    bl_label = ""
    bl_idname = "AMP_PT_AnimEuler"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_ui_units_x = 20

    def draw(self, context):
        layout = self.layout
        ui_column = layout.column(align=True)
        ui_column.separator(factor=2)
        slice_anim = ui_column.row(align=True)
        slice_anim.scale_y = 1.5
        AnimEulerButtons(layout, context)
        props = context.scene.amp_animeuler_properties
        ui_column.prop(props, "key_rotation_mode", text="Key Rotation Mode on First Keyframe")


def AnimEulerButtons(layout, context):
    row = layout.row(align=True)
    AnimEulerFilterButton(row, context, text="")
    AnimEulerGimbalButton(row, context, text="")


def AnimEulerFilterButton(layout, context, text=""):
    row = layout.row(align=True)
    row.operator(
        "anim.amp_euler_filter",
        text=text,
        icon_value=utils.customIcons.get_icon_id("AMP_curves_euler"),
        emboss=False,
    )


def AnimEulerGimbalButton(layout, context, text=""):
    row = layout.row(align=True)
    row.operator(
        "anim.amp_euler_rotation_recommendations",
        text=text,
        icon_value=utils.customIcons.get_icon_id("AMP_curves_gimbal"),
        emboss=False,
    )


classes = (
    AMP_OT_rotation_mode_recommendation,
    AMP_OT_EulerFilter,
    AMP_OT_EulerRotRecomButton,
    AMP_OT_bake_to_rotation_mode,
    AMP_PT_rotation_mode_recommendation,
    AMP_PT_AnimEuler,
)


class AMP_PG_AnimEuler(bpy.types.PropertyGroup):
    recommended_mode: bpy.props.StringProperty(default="")
    lowest_risk: bpy.props.StringProperty(default="")
    sorted_modes: bpy.props.StringProperty(default="")  # <-- New property for sorted ranking
    key_rotation_mode: bpy.props.BoolProperty(
        name="Key Rotation Mode", description="Key rotation mode on first keyframe", default=True
    )


def register_properties():
    bpy.utils.register_class(AMP_PG_AnimEuler)
    bpy.types.Scene.amp_animeuler_properties = bpy.props.PointerProperty(type=AMP_PG_AnimEuler)


def unregister_properties():
    del bpy.types.Scene.amp_animeuler_properties
    bpy.utils.unregister_class(AMP_PG_AnimEuler)


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
