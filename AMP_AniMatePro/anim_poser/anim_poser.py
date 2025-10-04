import bpy
from bpy.props import BoolProperty, PointerProperty, StringProperty
from bpy.types import PropertyGroup, Panel, Operator
from bpy.app.handlers import persistent
from .. import utils
from .. import __package__ as base_package

# ---------------------------
# Property Group Definition
# ---------------------------


class AMP_CollectionExcludeState(PropertyGroup):
    collection_name: StringProperty(name="Collection Name", default="")
    exclude: BoolProperty(name="Exclude", default=False)


# New property group to store the hide_viewport state for lvl1 objects
class AMP_ObjectHideState(PropertyGroup):
    object_name: StringProperty(name="Object Name", default="")
    hide_viewport: BoolProperty(name="Hide Viewport", default=False)


class AMP_PG_AnimPoserProperties(PropertyGroup):
    isolate_character: BoolProperty(
        name="Isolate Character",
        description="Enable or disable character isolation in Pose Mode",
        default=False,
        update=lambda self, context: self.update_isolate_character(context),
    )

    exclude_states: bpy.props.CollectionProperty(
        type=AMP_CollectionExcludeState,
        name="Exclude States",
    )

    # New collection to store level 1 object hide states
    hidden_object_states: bpy.props.CollectionProperty(
        type=AMP_ObjectHideState,
        name="Hidden Object States",
    )

    previous_mode: StringProperty(name="Previous Mode", default="")

    def update_isolate_character(self, context):
        if self.isolate_character:
            # Add the handler if not already registered.
            if isolate_character_handler not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(isolate_character_handler)
            # Only isolate immediately if already in Pose Mode.
            if context.mode == "POSE":
                # use underscore variant here to avoid view‐layer ops
                enable_isolate_character_(context, self)
        else:
            if isolate_character_handler in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(isolate_character_handler)
            disable_isolate_character_(context, self)
            self.previous_mode = ""
            self.exclude_states.clear()
            self.hidden_object_states.clear()


# ---------------------------
# Handler Implementation
# ---------------------------


@persistent
def isolate_character_handler(scene, depsgraph):
    props = bpy.context.scene.anim_poser_props
    current_mode = bpy.context.mode

    try:
        if props.previous_mode != current_mode:
            if current_mode == "POSE":
                # use underscore variant without triggering new view layers
                enable_isolate_character_(bpy.context, props, enter_pose_mode=False)
            elif props.previous_mode == "POSE":
                disable_isolate_character_(bpy.context, props)
            props.previous_mode = current_mode
    except Exception as e:
        disable_isolate_character_(bpy.context, props)
        raise e


# Rename current functions by appending an underscore


def enable_isolate_character_(context, props, enter_pose_mode=True):
    scene = context.scene
    addon_prefs = context.preferences.addons[base_package].preferences
    view_layer = context.view_layer

    # Safeguard: record only top-level (lvl 1) collection states if not already stored.
    props.exclude_states.clear()
    for collection in scene.collection.children:
        # Only record state for top-level collections.
        layer_collection = find_top_level_layer_collection(view_layer, collection.name)
        if layer_collection:
            state = props.exclude_states.add()
            state.collection_name = collection.name
            state.exclude = layer_collection.exclude

    # Store and hide level 1 objects (objects directly linked to the scene collection)
    props.hidden_object_states.clear()
    for obj in scene.collection.objects:
        state = props.hidden_object_states.add()
        state.object_name = obj.name
        state.hide_viewport = obj.hide_viewport
        obj.hide_viewport = True

    selected_armatures = [obj for obj in context.selected_objects if obj.type == "ARMATURE"]

    if not selected_armatures and enter_pose_mode:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="POSE")
        return

    temp_collection_names = []
    selectable_objects = set(bpy.context.selectable_objects)

    for armature in selected_armatures:
        temp_collection_name = f"{armature.name}_temp"
        temp_collection = bpy.data.collections.get(temp_collection_name)
        if not temp_collection:
            temp_collection = bpy.data.collections.new(temp_collection_name)
            scene.collection.children.link(temp_collection)

        temp_collection_names.append(temp_collection_name)

        if armature.name not in temp_collection.objects:
            temp_collection.objects.link(armature)

        for obj in bpy.data.objects:
            if obj not in selectable_objects and addon_prefs.isolate_char_limit_to_selectable:
                continue

            include_object = False

            if addon_prefs.isolate_char_include_armature:
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE" and mod.object == armature:
                        include_object = True
                        break

            if not include_object and addon_prefs.isolate_char_include_modifiers:
                for mod in obj.modifiers:
                    if mod.type != "ARMATURE" and hasattr(mod, "object") and mod.object == armature:
                        include_object = True
                        break

            if not include_object and addon_prefs.isolate_char_include_constraints:
                for con in obj.constraints:
                    if con.type in {"CHILD_OF", "COPY_TRANSFORMS", "ARMATURE"}:
                        # support both new multi‐target and legacy single‐target APIs
                        targets = getattr(con, "targets", None)
                        if targets:
                            for t in targets:
                                if t.target == armature:
                                    include_object = True
                                    break
                            if include_object:
                                break
                        else:
                            if getattr(con, "target", None) == armature:
                                include_object = True
                                break

            if include_object and addon_prefs.isolate_char_include_children:
                for child in obj.children:
                    if child not in selectable_objects and addon_prefs.isolate_char_limit_to_selectable:
                        continue
                    if child.name not in temp_collection.objects:
                        temp_collection.objects.link(child)

            if include_object:
                if obj.name not in temp_collection.objects:
                    temp_collection.objects.link(obj)

    for collection in scene.collection.children:
        if collection.name not in temp_collection_names:
            layer_collection = find_top_level_layer_collection(view_layer, collection.name)
            if layer_collection:
                layer_collection.exclude = True


def disable_isolate_character_(context, props):
    scene = context.scene
    view_layer = context.view_layer

    # Safeguard: if no stored states, assume already restored, so do nothing.
    if not props.exclude_states:
        return

    for state in props.exclude_states:
        try:
            layer_collection = find_top_level_layer_collection(view_layer, state.collection_name)
            if layer_collection:
                layer_collection.exclude = state.exclude
        except Exception:
            # Continue restoring remaining states even if one fails
            pass
    props.exclude_states.clear()

    # Restore the hide_viewport state for level 1 objects
    for obj_state in props.hidden_object_states:
        obj = bpy.data.objects.get(obj_state.object_name)
        if obj:
            obj.hide_viewport = obj_state.hide_viewport
    props.hidden_object_states.clear()

    temp_collections = [col for col in scene.collection.children if col.name.endswith("_temp")]
    for temp_col in temp_collections:
        try:
            scene.collection.children.unlink(temp_col)
            bpy.data.collections.remove(temp_col)
        except Exception as e:
            pass


# New implementation using view layers and an isolation collection


def enable_isolate_character(context, props, enter_pose_mode=True):
    scene = context.scene
    current_vl = context.view_layer

    # store original mode so we can restore later
    scene["amp_original_mode"] = context.mode

    if current_vl.name == "amp_character_isolation":
        return

    if scene.view_layers.get("amp_character_isolation"):
        disable_isolate_character(context, props)

    scene["amp_original_viewlayer"] = current_vl.name

    isolation_coll = bpy.data.collections.get("amp_character_isolation_coll")
    if not isolation_coll:
        isolation_coll = bpy.data.collections.new("amp_character_isolation_coll")
        scene.collection.children.link(isolation_coll)
    for obj in list(isolation_coll.objects):
        isolation_coll.objects.unlink(obj)

    addon_prefs = context.preferences.addons[base_package].preferences
    selected_armatures = [obj for obj in context.selected_objects if obj.type == "ARMATURE"]

    if not selected_armatures and enter_pose_mode:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="POSE")
        return

    for armature in selected_armatures:
        if armature.name not in isolation_coll.objects:
            isolation_coll.objects.link(armature)
        for obj in bpy.data.objects:
            include_object = False
            if addon_prefs.isolate_char_include_armature:
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE" and mod.object == armature:
                        include_object = True
                        break
            if not include_object and addon_prefs.isolate_char_include_modifiers:
                for mod in obj.modifiers:
                    if mod.type != "ARMATURE" and hasattr(mod, "object") and mod.object == armature:
                        include_object = True
                        break
            if not include_object and addon_prefs.isolate_char_include_constraints:
                for con in obj.constraints:
                    if con.type in {"CHILD_OF", "COPY_TRANSFORMS", "ARMATURE"}:
                        targets = getattr(con, "targets", None)
                        if targets:
                            for t in targets:
                                if t.target == armature:
                                    include_object = True
                                    break
                            if include_object:
                                break
                        else:
                            if getattr(con, "target", None) == armature:
                                include_object = True
                                break
            if include_object:
                if obj.name not in isolation_coll.objects:
                    isolation_coll.objects.link(obj)
        if addon_prefs.isolate_char_include_children:
            for child in armature.children:
                if child.name not in isolation_coll.objects:
                    isolation_coll.objects.link(child)

    isolation_vl = scene.view_layers.new("amp_character_isolation")
    for lc in isolation_vl.layer_collection.children:
        if lc.collection.name != "amp_character_isolation_coll":
            lc.exclude = True
        else:
            lc.exclude = False

    if context.window:
        context.window.view_layer = isolation_vl
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    # only force Pose Mode entry when requested
    if enter_pose_mode:
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")


def disable_isolate_character(context, props):
    # first check if the isolate mode should still be held because the condidition to exist is not met (if the isolate property is on and we are still in pose mode)
    if props.isolate_character and context.mode == "POSE":
        return
    scene = context.scene
    current_vl = context.view_layer
    if current_vl.name == "amp_character_isolation":
        original_vl_name = scene.get("amp_original_viewlayer", None)
        if original_vl_name and original_vl_name in scene.view_layers:
            if context.window:
                context.window.view_layer = scene.view_layers[original_vl_name]
                bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        isolation_vl = scene.view_layers.get("amp_character_isolation")
        if isolation_vl:
            scene.view_layers.remove(isolation_vl)
        scene["amp_original_viewlayer"] = ""
        isolation_coll = bpy.data.collections.get("amp_character_isolation_coll")
        if isolation_coll:
            try:
                scene.collection.children.unlink(isolation_coll)
            except Exception:
                pass
            bpy.data.collections.remove(isolation_coll)

        # restore original object mode
        orig_mode = scene.get("amp_original_mode", None)
        if orig_mode:
            try:
                bpy.ops.object.mode_set(mode=orig_mode)
            except Exception:
                pass
        scene["amp_original_mode"] = ""


# ---------------------------
# Helper Functions
# ---------------------------


def find_layer_collection(layer_collection, name):
    """Recursively find a layer collection by name."""
    if layer_collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, name)
        if found:
            return found
    return None


def find_top_level_layer_collection(view_layer, name):
    """Find a top-level layer collection by name."""
    for layer_col in view_layer.layer_collection.children:
        if layer_col.name == name:
            return layer_col
    return None


# ---------------------------
# UI Integration
# ---------------------------


class AMP_PT_AnimPoserOptions(Panel):
    bl_label = "Anim Poser Options"
    bl_idname = "AMP_PT_AnimPoserOptions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Anim Poser"
    bl_context = ""
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        props = context.scene.anim_poser_props
        ui_column = layout.column(align=False)

        ui_column.separator(factor=2)

        pose_anim = ui_column.row(align=True)
        pose_anim.scale_y = 1.5
        AnimPoserLeft(pose_anim, context, "Match Left", "TRIA_LEFT")
        AnimPoserRight(pose_anim, context, "Match Right", "TRIA_RIGHT")

        pose_anim = ui_column.row(align=True)
        pose_anim.scale_y = 1.5
        AnimPoserCopy(pose_anim, context, "Copy Pose", "COPYDOWN")
        AnimPoserPoseToRange(pose_anim, context, "Paste Pose to Range", "PASTEDOWN")

        ui_column.separator()

        ui_column.prop(props, "isolate_character", text="Isolate Character")


# ---------------------------
# Operator Definitions (Existing)
# ---------------------------


class AMP_OT_MatchSelectedKeyframeValues(bpy.types.Operator):
    bl_idname = "anim.amp_match_selected_keyframe_values"
    bl_label = "Match to Keyframe"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Match the value of the first or last keyframe.
Select keyframes. Match the value of the closest keyframe to the left or right
of the selected keyframes.
Choose the direction of the match (left or right)"""

    to_right: BoolProperty(name="Match to Right", default=True)

    def execute(self, context):
        selected_frame_range = utils.curve.get_selected_keyframes_range(context)

        if selected_frame_range is None:
            self.report({"ERROR"}, "No keyframes selected.")
            return {"CANCELLED"}

        frame_start, frame_end = selected_frame_range

        keyframe_matched = False

        for fcurve in context.selected_visible_fcurves:
            closest_keyframe = utils.curve.find_closest_keyframe(fcurve, frame_start, frame_end, self.to_right)
            if closest_keyframe is None:
                continue

            keyframe_matched = True
            value_to_propagate = closest_keyframe.co.y

            for kp in [kp for kp in fcurve.keyframe_points if kp.select_control_point]:
                kp.co.y = value_to_propagate
                kp.handle_left.y = value_to_propagate
                kp.handle_right.y = value_to_propagate

        if not keyframe_matched:
            self.report({"WARNING"}, "No keyframes in the direction to match.")
            return {"CANCELLED"}

        bpy.context.view_layer.update()
        return {"FINISHED"}


class AMP_OT_PastePoseToRange(bpy.types.Operator):
    bl_idname = "anim.amp_propagate_pose_to_range"
    bl_label = "Paste Pose to Range"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Paste the copied pose over all frames in the available range.
Range:
    - If preview range is set it will use it.
    - If no preview range and keyframes selected the range will be between the first and
      last selected keyframes.
    - Otherwise the range will be the entire scene.

How to Use (in Pose Mode):
    - Select bones. Copy Pose.
    - Execute Paste Pose to Range"""

    selected_keyframes: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == "ARMATURE" and context.active_pose_bone

    def execute(self, context):
        frame_start, frame_end = utils.curve.determine_frame_range_priority(self, context)
        keys_in_range = utils.curve.get_keyframes_in_range(context, frame_start, frame_end)

        # Set the scene to the first frame of the range and paste the pose
        context.scene.frame_current = frame_start
        bpy.ops.pose.paste()

        armature = context.active_object
        action = armature.animation_data.action if armature.animation_data else None

        if not action:
            self.report({"ERROR"}, "No animation data found on the armature.")
            return {"CANCELLED"}

        # Collect the initial pose values at the first frame
        initial_values = {}
        for bone in context.selected_pose_bones:
            if bone.name not in initial_values:
                initial_values[bone.name] = {
                    "location": bone.location.copy(),
                    "rotation_quaternion": bone.rotation_quaternion.copy(),
                    "rotation_euler": bone.rotation_euler.copy(),
                    "scale": bone.scale.copy(),
                }

        # Iterate over all frames in the range and propagate the initial values
        for frame in keys_in_range:
            if frame != frame_start:  # We've already pasted at frame_start
                context.scene.frame_current = frame
                for bone in context.selected_pose_bones:
                    # Set the bone's transforms to the initial values
                    if "location" in initial_values[bone.name]:
                        bone.location = initial_values[bone.name]["location"]
                    if "rotation_quaternion" in initial_values[bone.name]:
                        bone.rotation_quaternion = initial_values[bone.name]["rotation_quaternion"]
                    if "rotation_euler" in initial_values[bone.name]:
                        bone.rotation_euler = initial_values[bone.name]["rotation_euler"]
                    if "scale" in initial_values[bone.name]:
                        bone.scale = initial_values[bone.name]["scale"]

                    # Insert keyframes for the transforms
                    bone.keyframe_insert(data_path="location")
                    bone.keyframe_insert(data_path="rotation_quaternion")
                    bone.keyframe_insert(data_path="rotation_euler")
                    bone.keyframe_insert(data_path="scale")

        context.area.tag_redraw()

        return {"FINISHED"}


# ---------------------------
# UI Helper Functions (Existing)
# ---------------------------


def AnimPoserLeft(layout, context, text="", icon_value="LEFTARROW"):
    layout.operator(
        "anim.amp_match_selected_keyframe_values",
        text=text,
        icon=icon_value,
    ).to_right = False


def AnimPoserRight(layout, context, text="", icon_value="RIGHTARROW"):
    layout.operator(
        "anim.amp_match_selected_keyframe_values",
        text=text,
        icon=icon_value,
    ).to_right = True


def AnimPoserCopy(layout, context, text="", icon_value="COPYDOWN"):
    layout.operator(
        "pose.copy",
        text=text,
        icon=icon_value,
    )


def AnimPoserPoseToRange(layout, context, text="", icon_value="PASTEDOWN"):
    layout.operator(
        "anim.amp_propagate_pose_to_range",
        text=text,
        icon=icon_value,
    )


def AnimPoserButtons(layout, context):
    row = layout.row(align=True)
    AnimPoserLeft(row, context, "", "LEFTARROW")
    AnimPoserRight(row, context, "", "RIGHTARROW")
    AnimPoserCopy(row, context, "", "COPYDOWN")
    AnimPoserPoseToRange(row, context, "", "PASTEDOWN")


# ---------------------------
# Registration
# ---------------------------

classes = (
    AMP_CollectionExcludeState,
    AMP_ObjectHideState,
    AMP_PG_AnimPoserProperties,
    AMP_OT_MatchSelectedKeyframeValues,
    AMP_OT_PastePoseToRange,
    # AMP_PT_AnimPoserOptions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.anim_poser_props = PointerProperty(type=AMP_PG_AnimPoserProperties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.anim_poser_props


if __name__ == "__main__":
    register()
