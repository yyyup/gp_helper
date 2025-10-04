# ---------------- anim_flex_motion_paths.py ----------------

import bpy
from mathutils import Matrix
from bpy.props import (
    BoolProperty,
    PointerProperty,
    CollectionProperty,
    FloatVectorProperty,
    StringProperty,
    IntProperty,
    EnumProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList
from ..utils.customIcons import get_icon
from .anim_mopaths_ui import motion_path_options

is_updating_visibility = False
is_updating_motion_paths = False
last_active_item = None


def serialize_matrix(matrix):
    return [element for row in matrix for element in row]


def deserialize_matrix(matrix_list):
    return Matrix([matrix_list[i : i + 4] for i in range(0, 16, 4)])


def get_selected_items(context):
    if context.mode == "POSE":
        return context.selected_pose_bones or []
    else:
        return context.selected_objects or []


def is_item_in_list(item, props):
    for elem in props.elements:
        if isinstance(item, bpy.types.Object) and elem.item_type == "OBJECT" and elem.object_ref == item:
            return True
        elif (
            isinstance(item, bpy.types.PoseBone)
            and elem.item_type == "BONE"
            and elem.armature_ref == item.id_data
            and elem.bone_name == item.name
        ):
            return True
    return False


def get_element_for_item(item, props):
    for elem in props.elements:
        if elem.item_type == "OBJECT" and elem.object_ref == item:
            return elem
        elif elem.item_type == "BONE" and elem.armature_ref == item.id_data and elem.bone_name == item.name:
            return elem
    return None


def get_element_for_empty(obj, props):
    for elem in props.elements:
        if elem.empty_ref == obj:
            return elem
    return None


def create_temp_collection():
    collection_name = "MotionPaths_CustomOrigins"
    if collection_name in bpy.data.collections:
        return bpy.data.collections[collection_name]
    else:
        new_collection = bpy.data.collections.new(collection_name)
        # new_collection.hide_render = True
        bpy.context.scene.collection.children.link(new_collection)
        return new_collection


def find_layer_collection(layer_collection, name):
    if layer_collection.collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        res = find_layer_collection(child, name)
        if res:
            return res
    return None


def set_collection_exclude(collection_name, exclude):
    view_layer = bpy.context.view_layer
    layer_coll = find_layer_collection(view_layer.layer_collection, collection_name)
    if layer_coll:
        layer_coll.exclude = exclude


def store_selection_and_mode(context):
    mode = context.mode
    sel_objs = context.selected_objects
    sel_bones = []
    active_obj = context.view_layer.objects.active
    active_bone = None
    if mode == "POSE" and active_obj and active_obj.type == "ARMATURE":
        for b in context.selected_pose_bones:
            sel_bones.append(b.name)
        if context.active_pose_bone:
            active_bone = context.active_pose_bone.name
    return mode, sel_objs, active_obj, sel_bones, active_bone


def restore_selection_and_mode(context, mode, sel_objs, active_obj, sel_bones, active_bone):
    if context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        except:
            pass

    bpy.ops.object.select_all(action="DESELECT")
    for o in sel_objs:
        if o and o.name in context.view_layer.objects:
            o.select_set(True)
    if active_obj and active_obj.name in context.view_layer.objects:
        context.view_layer.objects.active = active_obj

    if mode == "POSE" and active_obj and active_obj.type == "ARMATURE":
        if context.mode != "POSE":
            try:
                bpy.ops.object.mode_set(mode="POSE", toggle=False)
            except:
                pass
        for b in sel_bones:
            pb = active_obj.pose.bones.get(b)
            if pb:
                pb.bone.select = True
        if active_bone and active_obj.pose.bones.get(active_bone):
            pb = active_obj.pose.bones.get(active_bone)
            pb.bone.select = True
            context.view_layer.objects.active = active_obj
    else:
        if context.mode != mode:
            try:
                bpy.ops.object.mode_set(mode=mode, toggle=False)
            except:
                pass


def unlock_object_mode():
    tool_settings = bpy.context.scene.tool_settings
    was_locked = tool_settings.lock_object_mode
    if was_locked:
        tool_settings.lock_object_mode = False
    return was_locked


def lock_object_mode(was_locked):
    if was_locked:
        bpy.context.scene.tool_settings.lock_object_mode = True


def force_object_mode():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_in_object_mode(obj):
    force_object_mode()
    bpy.ops.object.select_all(action="DESELECT")
    if obj:
        # Ensure the object's collection is visible in the view layer
        for coll in obj.users_collection:
            layer_coll = bpy.context.view_layer.layer_collection
            sub_coll = find_layer_collection(layer_coll, coll.name)
            if sub_coll:
                sub_coll.exclude = False

        if obj.name in bpy.context.view_layer.objects:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        else:
            print(f"Object {obj.name} is not in the current view layer")


def get_or_create_empty_for_element(elem, temp_collection):
    empty_name = f"AMP_FMP_CustomOrigin_{elem.name}"
    sub_collection_name = f"AMP_FMP_CustomOrigin_{elem.name}_Collection"
    if empty_name in bpy.data.objects:
        empty = bpy.data.objects[empty_name]
        if sub_collection_name in bpy.data.collections:
            sub_collection = bpy.data.collections[sub_collection_name]
        else:
            sub_collection = bpy.data.collections.new(sub_collection_name)
            temp_collection.children.link(sub_collection)
            set_collection_exclude(sub_collection.name, True)
    else:
        sub_collection = bpy.data.collections.new(sub_collection_name)
        temp_collection.children.link(sub_collection)
        set_collection_exclude(sub_collection.name, True)
        empty = bpy.data.objects.new(empty_name, None)
        sub_collection.objects.link(empty)

    if elem.item_type == "OBJECT" and elem.object_ref:
        wm = elem.object_ref.matrix_world.copy()
        empty.parent = elem.object_ref
        empty.matrix_world = wm
    elif elem.item_type == "BONE" and elem.armature_ref and elem.bone_name:
        armature = elem.armature_ref
        pose_bone = armature.pose.bones.get(elem.bone_name)
        if pose_bone:
            wm = armature.matrix_world @ pose_bone.matrix
            empty.parent = armature
            empty.parent_type = "BONE"
            empty.parent_bone = elem.bone_name
            empty.matrix_world = wm

    elem.empty_ref = empty
    elem.collection_name = sub_collection.name
    return empty

def set_motion_path_properties(empty):
    props = bpy.context.scene.mp_props
    if empty and empty.motion_path and empty.animation_visualization and empty.animation_visualization.motion_path:

        mp = empty.motion_path
        av = empty.animation_visualization.motion_path

        if bpy.app.version >= (4, 2, 0):
            av.use_camera_space_bake = props.use_camera_space_bake

        av.show_frame_numbers = False
        av.show_keyframe_highlight = False
        av.show_keyframe_numbers = False

        mp.lines = props.lines
        mp.line_thickness = props.line_thickness
        if bpy.app.version >= (4, 2, 0):
            mp.use_custom_color = props.use_custom_color
            if props.use_custom_color:
                mp.color = props.color_before
                mp.color_post = props.color_after


def recalc_motion_path(empty):
    mode, sel_objs, active_obj, sel_bones, active_bone = store_selection_and_mode(bpy.context)
    force_object_mode()
    collection_name = None
    props = bpy.context.scene.mp_props
    for elem in props.elements:
        if elem.empty_ref == empty:
            collection_name = elem.collection_name
            break
    if collection_name:
        set_collection_exclude(collection_name, False)

    # update view layer
    bpy.context.view_layer.update()

    select_in_object_mode(empty)

    # Check if motion path exists, if not calculate it first
    if not empty.motion_path:
        try:
            bpy.ops.object.paths_calculate()
        except RuntimeError as e:
            print(f"Error calculating motion paths for {empty.name}: {e}")
            restore_selection_and_mode(bpy.context, mode, sel_objs, active_obj, sel_bones, active_bone)
            return
    
    set_motion_path_properties(empty)

    # Only update if motion path exists
    if empty.motion_path:
        try:
            bpy.ops.object.paths_update()
        except RuntimeError as e:
            print(f"Error updating motion paths for {empty.name}: {e}")

    restore_selection_and_mode(bpy.context, mode, sel_objs, active_obj, sel_bones, active_bone)


def create_motion_path(obj):
    select_in_object_mode(obj)
    try:
        bpy.ops.object.paths_calculate()
        set_motion_path_properties(obj)
        # Only update if motion path was successfully created
        if obj.motion_path:
            bpy.ops.object.paths_update()
    except RuntimeError as e:
        print(f"Error creating motion paths for {obj.name}: {e}")


def ensure_motion_paths_handler():
    global is_updating_motion_paths
    if is_updating_motion_paths:
        return
    is_updating_motion_paths = True

    try:
        for elem in bpy.context.scene.mp_props.elements:
            empty = elem.empty_ref
            if empty and not empty.motion_path:
                recalc_motion_path(empty)
            elif empty:
                set_motion_path_properties(empty)
    finally:
        is_updating_motion_paths = False


def ensure_motion_paths(self, context):
    props = bpy.context.scene.mp_props

    was_locked = unlock_object_mode()
    mode, sel_objs, active_obj, sel_bones, active_bone = store_selection_and_mode(bpy.context)

    force_object_mode()

    for elem in props.elements:
        empty = elem.empty_ref
        if empty:
            # Ensure the collection containing the empty is enabled in the view layer
            previous_exclusion_state = None
            if elem.collection_name in bpy.data.collections:
                layer_coll = bpy.context.view_layer.layer_collection
                sub_coll = find_layer_collection(layer_coll, elem.collection_name)
                if sub_coll:
                    previous_exclusion_state = sub_coll.exclude
                    sub_coll.exclude = False

            # Select the empty
            select_in_object_mode(empty)

            # Update the properties of the motion path
            set_motion_path_properties(empty)

            # Recalculate or recreate the motion path
            recalc_motion_path(empty)

            # Restore the collection's exclusion state if it was previously excluded
            if previous_exclusion_state is not None and previous_exclusion_state:
                layer_coll = bpy.context.view_layer.layer_collection
                sub_coll = find_layer_collection(layer_coll, elem.collection_name)
                if sub_coll:
                    sub_coll.exclude = True

    # Restore the original selection and mode
    restore_selection_and_mode(bpy.context, mode, sel_objs, active_obj, sel_bones, active_bone)

    lock_object_mode(was_locked)


def refresh_all_motion_paths(self, context):
    update_visibility(context)
    bpy.ops.object.paths_update_visible()


def get_active_element(context):
    selected_items = get_selected_items(context)
    if selected_items:
        active_obj = context.view_layer.objects.active
        if context.mode == "POSE" and active_obj and active_obj.type == "ARMATURE":
            active_bone = context.active_pose_bone
            if active_bone:
                return get_element_for_item(active_bone, context.scene.mp_props)
        else:
            if active_obj:
                return get_element_for_item(active_obj, context.scene.mp_props)
    return None


def get_selected_list_empties(context):
    props = context.scene.mp_props
    empties_in_list = []
    for obj in context.selected_objects:
        elem = get_element_for_empty(obj, props)
        if elem:
            empties_in_list.append(elem)
    return empties_in_list


def update_visibility(context):
    global is_updating_visibility
    if is_updating_visibility:
        return
    is_updating_visibility = True
    try:
        props = context.scene.mp_props
        create_temp_collection()
        active_elem = get_active_element(context)
        selected_empties = get_selected_list_empties(context)

        set_collection_exclude("MotionPaths_CustomOrigins", False)

        for elem in props.elements:
            show = False
            if props.show_motion_paths and (elem.always_show or elem == active_elem):
                show = True
            if elem in selected_empties:
                show = True
            if elem.collection_name in bpy.data.collections:
                set_collection_exclude(elem.collection_name, not show)
                if show and elem.empty_ref:
                    set_motion_path_properties(elem.empty_ref)
    finally:
        is_updating_visibility = False


def depsgraph_update_handler(scene):
    global last_active_item
    # only update if show paths is active
    if not bpy.context.scene.mp_props.show_motion_paths:
        return
    current_active_elem = get_active_element(bpy.context)
    current_active_name = current_active_elem.name if current_active_elem else None
    if current_active_name != last_active_item:
        last_active_item = current_active_name
        # if bpy.context.scene.mp_props.show_motion_paths:
        #     ensure_motion_paths_handler()
        update_visibility(bpy.context)


def update_handler_registration(show):
    if show and depsgraph_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_handler)
    elif not show and depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_handler)


class AMP_FMP_PG_Element(PropertyGroup):
    name: StringProperty(
        override={"LIBRARY_OVERRIDABLE"},
    )
    item_type: EnumProperty(
        name="Type",
        items=[
            ("OBJECT", "Object", ""),
            ("BONE", "Bone", ""),
        ],
        override={"LIBRARY_OVERRIDABLE"},
    )
    object_ref: PointerProperty(
        type=bpy.types.Object,
        override={"LIBRARY_OVERRIDABLE"},
    )
    bone_name: StringProperty(
        override={"LIBRARY_OVERRIDABLE"},
    )
    armature_ref: PointerProperty(
        type=bpy.types.Object,
        override={"LIBRARY_OVERRIDABLE"},
    )
    always_show: BoolProperty(
        name="Always Show",
        default=False,
        update=refresh_all_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    relative_matrix: FloatVectorProperty(
        name="Relative Matrix",
        size=16,
        override={"LIBRARY_OVERRIDABLE"},
    )
    empty_ref: PointerProperty(
        type=bpy.types.Object,
        override={"LIBRARY_OVERRIDABLE"},
    )
    collection_name: StringProperty(
        override={"LIBRARY_OVERRIDABLE"},
    )


class AMP_FMP_PG_Properties(PropertyGroup):
    elements: CollectionProperty(type=AMP_FMP_PG_Element)
    active_index: IntProperty(
        name="Active Element Index",
        default=0,
        override={"LIBRARY_OVERRIDABLE"},
    )
    show_motion_paths: BoolProperty(
        name="Show Motion Paths",
        default=False,
        update=lambda s, c: update_handler_registration(s.show_motion_paths),
        override={"LIBRARY_OVERRIDABLE"},
    )
    show_settings: BoolProperty(
        name="Show Settings",
        default=True,
        override={"LIBRARY_OVERRIDABLE"},
    )
    show_list: BoolProperty(
        name="Show Elements List",
        default=True,
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    use_camera_space_bake: BoolProperty(
        name="Bake to Active Camera",
        default=False,
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    show_frame_numbers: BoolProperty(
        name="Frame Numbers",
        default=False,
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    lines: BoolProperty(
        name="Lines",
        default=True,
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    line_thickness: IntProperty(
        name="Thickness",
        default=2,
        min=1,
        max=6,
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    use_custom_color: BoolProperty(
        name="Custom Color",
        default=True,
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    color_before: FloatVectorProperty(
        name="Before",
        subtype="COLOR",
        size=3,
        default=(1.0, 0.0, 0.0),
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    color_after: FloatVectorProperty(
        name="After",
        subtype="COLOR",
        size=3,
        default=(0.0, 1.0, 0.0),
        update=ensure_motion_paths,
        override={"LIBRARY_OVERRIDABLE"},
    )
    quick_path_settings: BoolProperty(
        name="Quick Path Settings",
        default=False,
        override={"LIBRARY_OVERRIDABLE"},
    )


class AMP_FMP_OT_Add_Element(Operator):
    bl_idname = "anim.amp_fmp_add_element"
    bl_label = "Add Element"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Add selected object or bone to the list of elements"

    def execute(self, context):
        props = context.scene.mp_props
        if not props.show_motion_paths:
            ensure_motion_paths_handler()
            props.show_motion_paths = True
        update_visibility(context)

        selected_items = get_selected_items(context)
        if not selected_items:
            self.report({"WARNING"}, "No elements selected")
            return {"CANCELLED"}
        temp_collection = create_temp_collection()
        was_locked = unlock_object_mode()
        try:
            mode, sel_objs, active_obj, sel_bones, active_bone = store_selection_and_mode(context)
            force_object_mode()
            for item in selected_items:
                if is_item_in_list(item, props):
                    self.report({"WARNING"}, f"{item.name} is already in the list")
                    continue
                elem = props.elements.add()
                elem.name = item.name
                if isinstance(item, bpy.types.Object):
                    elem.item_type = "OBJECT"
                    elem.object_ref = item
                elif isinstance(item, bpy.types.PoseBone):
                    elem.item_type = "BONE"
                    elem.armature_ref = item.id_data
                    elem.bone_name = item.name
                elem.relative_matrix = [1.0 if i % 5 == 0 else 0.0 for i in range(16)]
                empty = get_or_create_empty_for_element(elem, temp_collection)

                # Initialize motion paths for the empty
                create_motion_path(empty)

            restore_selection_and_mode(context, mode, sel_objs, active_obj, sel_bones, active_bone)
        finally:
            lock_object_mode(was_locked)

        update_visibility(context)
        return {"FINISHED"}


class AMP_FMP_OT_Remove_Active_Element(Operator):
    bl_idname = "anim.amp_fmp_remove_active_element"
    bl_label = "Remove Active Element"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Remove the active object or bone from the list of elements"

    def execute(self, context):
        props = context.scene.mp_props
        active_obj = context.view_layer.objects.active

        active_bone = None
        if context.mode == "POSE" and active_obj and active_obj.type == "ARMATURE":
            active_bone = context.active_pose_bone

        if active_bone:
            elem = get_element_for_item(active_bone, props)
        else:
            elem = get_element_for_item(active_obj, props)

        if elem:
            index = props.elements.find(elem.name)
            if index != -1:
                was_locked = unlock_object_mode()
                try:
                    elem_to_remove = props.elements[index]
                    if elem_to_remove.empty_ref and elem_to_remove.empty_ref.name in bpy.data.objects:
                        empty = elem_to_remove.empty_ref
                        sub_collection_name = elem_to_remove.collection_name
                        if sub_collection_name and sub_collection_name in bpy.data.collections:
                            sub_collection = bpy.data.collections[sub_collection_name]
                            if empty.name in sub_collection.objects:
                                sub_collection.objects.unlink(empty)
                            if empty.name in bpy.data.objects:
                                bpy.data.objects.remove(empty, do_unlink=True)
                            bpy.data.collections.remove(sub_collection, do_unlink=True)
                    props.elements.remove(index)
                finally:
                    lock_object_mode(was_locked)
                update_visibility(context)
                self.report({"INFO"}, f"Removed active element '{elem.name}'")
                return {"FINISHED"}
            else:
                self.report({"WARNING"}, "Active element not found in the list")
                return {"CANCELLED"}
        else:
            self.report({"WARNING"}, "No active object or bone to remove")
            return {"CANCELLED"}


class AMP_FMP_OT_Remove_Index_Element(Operator):
    bl_idname = "anim.amp_fmp_remove_index_element"
    bl_label = "Remove Active"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Remove the selected element from the list"

    index: IntProperty()

    def execute(self, context):
        was_locked = unlock_object_mode()
        props = context.scene.mp_props

        mode, sel_objs, active_obj, sel_bones, active_bone = store_selection_and_mode(context)

        force_object_mode()
        if 0 <= self.index < len(props.elements):
            elem = props.elements[self.index]
            if elem.empty_ref and elem.empty_ref.name in bpy.data.objects:
                empty = elem.empty_ref
                sub_collection_name = elem.collection_name
                if sub_collection_name and sub_collection_name in bpy.data.collections:
                    sub_collection = bpy.data.collections[sub_collection_name]
                    if empty.name in sub_collection.objects:
                        sub_collection.objects.unlink(empty)
                    if empty.name in bpy.data.objects:
                        bpy.data.objects.remove(empty, do_unlink=True)
                    bpy.data.collections.remove(sub_collection, do_unlink=True)
            props.elements.remove(self.index)
            restore_selection_and_mode(context, mode, sel_objs, active_obj, sel_bones, active_bone)
            update_visibility(context)
            self.report({"INFO"}, f"Removed element at index {elem.name}")
            return {"FINISHED"}

        lock_object_mode(was_locked)


class AMP_FMP_OT_Move_Element_Up(Operator):
    bl_idname = "anim.amp_fmp_move_element_up"
    bl_label = "Move Up"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Move the selected element up in the list"

    index: IntProperty()

    def execute(self, context):
        props = context.scene.mp_props
        index = self.index
        if index > 0 and index < len(props.elements):
            props.elements.move(index, index - 1)
            props.active_index = index - 1
            update_visibility(context)
            self.report({"INFO"}, f"Moved element '{props.elements[props.active_index].name}' up")
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, "Cannot move the element up")
            return {"CANCELLED"}


class AMP_FMP_OT_Move_Element_Down(Operator):
    bl_idname = "anim.amp_fmp_move_element_down"
    bl_label = "Move Down"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Move the selected element down in the list"

    index: IntProperty()

    def execute(self, context):
        props = context.scene.mp_props
        index = self.index
        if index >= 0 and index < len(props.elements) - 1:
            props.elements.move(index, index + 1)
            props.active_index = index + 1
            update_visibility(context)
            self.report({"INFO"}, f"Moved element '{props.elements[props.active_index].name}' down")
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, "Cannot move the element down")
            return {"CANCELLED"}


class AMP_FMP_OT_Toggle_Show_Motion_Paths(Operator):
    bl_idname = "anim.amp_fmp_toggle_show_motion_paths"
    bl_label = "Toggle Show Motion Paths"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Toggle the visibility of the flex motion paths"

    def execute(self, context):
        props = context.scene.mp_props
        props.show_motion_paths = not props.show_motion_paths
        if props.show_motion_paths:
            ensure_motion_paths_handler()
        update_visibility(context)
        return {"FINISHED"}


class AMP_FMP_OT_Select_Element(Operator):
    bl_idname = "anim.amp_fmp_select_element"
    bl_label = "Select Element"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Select the object or bone associated with this element"

    index: IntProperty()

    def execute(self, context):
        props = context.scene.mp_props

        if 0 <= self.index < len(props.elements):
            elem = props.elements[self.index]

            if elem.item_type == "OBJECT" and elem.object_ref:
                if context.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.select_all(action="DESELECT")
                elem.object_ref.select_set(True)
                context.view_layer.objects.active = elem.object_ref

            elif elem.item_type == "BONE" and elem.armature_ref and elem.bone_name:
                armature = elem.armature_ref
                if armature:
                    if context.mode != "OBJECT":
                        bpy.ops.object.mode_set(mode="OBJECT")
                    bpy.ops.object.select_all(action="DESELECT")
                    armature.select_set(True)
                    context.view_layer.objects.active = armature

                    try:
                        bpy.ops.object.mode_set(mode="POSE")
                    except RuntimeError:
                        self.report({"ERROR"}, "Failed to switch to pose mode")
                        return {"CANCELLED"}

                    for bone in armature.pose.bones:
                        bone.bone.select = False

                    target_bone = armature.pose.bones.get(elem.bone_name)
                    if target_bone:
                        target_bone.bone.select = True
                    else:
                        self.report({"WARNING"}, "Bone not found")
                        return {"CANCELLED"}
            else:
                self.report({"WARNING"}, "Invalid element")
                return {"CANCELLED"}

            update_visibility(context)
            if props.show_motion_paths:
                ensure_motion_paths_handler()
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, "Invalid index")
            return {"CANCELLED"}


class AMP_FMP_OT_Select_Empty(Operator):
    bl_idname = "anim.amp_fmp_select_empty"
    bl_label = "Select Empty"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Select the empty associated with this element"

    index: IntProperty()

    def execute(self, context):
        props = context.scene.mp_props

        if 0 <= self.index < len(props.elements):
            elem = props.elements[self.index]

            if elem.empty_ref:
                if context.mode == "POSE":
                    bpy.ops.object.mode_set(mode="OBJECT")

                if context.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")

                bpy.ops.object.select_all(action="DESELECT")

                if elem.collection_name in bpy.data.collections:
                    layer_coll = bpy.context.view_layer.layer_collection
                    sub_coll = find_layer_collection(layer_coll, elem.collection_name)
                    if sub_coll:
                        sub_coll.exclude = False

                if elem.empty_ref.name in context.view_layer.objects:
                    elem.empty_ref.select_set(True)
                    context.view_layer.objects.active = elem.empty_ref
                else:
                    self.report({"ERROR"}, f"Empty '{elem.empty_ref.name}' not in view layer")
                    return {"CANCELLED"}

                update_visibility(context)
                if props.show_motion_paths:
                    ensure_motion_paths_handler()
                return {"FINISHED"}
            else:
                self.report({"WARNING"}, "Empty not found")
                return {"CANCELLED"}
        else:
            self.report({"WARNING"}, "Invalid index")
            return {"CANCELLED"}


class AMP_FMP_OT_Refresh_All_Paths(Operator):
    bl_idname = "anim.amp_fmp_refresh_all_paths"
    bl_label = "Refresh All"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Refresh all motion paths"

    def execute(self, context):
        bpy.ops.object.paths_update_visible()
        update_visibility(context)
        self.report({"INFO"}, "Refreshed all motion paths")
        return {"FINISHED"}


class AMP_FMP_UL_Elements(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            op_select = row.operator("anim.amp_fmp_select_element", text="", icon="RESTRICT_SELECT_OFF")
            op_select_empty = row.operator("anim.amp_fmp_select_empty", text="", icon="EMPTY_AXIS")
            op_select.index = index
            op_select_empty.index = index

            if item.item_type == "OBJECT":
                icon_type = "OBJECT_DATA"
            elif item.item_type == "BONE":
                icon_type = "BONE_DATA"
            else:
                icon_type = "QUESTION"

            row.label(text=item.name, icon=icon_type)
            row.prop(item, "always_show", text="", icon="PINNED" if item.always_show else "UNPINNED", toggle=True)


class AMP_FMP_PT_OffsetMoPathsBase(Panel):

    def draw(self, context):
        draw_offsetmopaths_panel(self, context)
            
def draw_offsetmopaths_panel(self, context):
    layout = self.layout
    props = context.scene.mp_props
    create_temp_collection()

    row = layout.row(align=True)
    row.operator(
        "anim.amp_fmp_toggle_show_motion_paths",
        text="Show Motion Paths" if not props.show_motion_paths else "Hide Motion Paths",
        **get_icon("AMP_omopaths_on" if props.show_motion_paths else "AMP_flexmopaths_off"),
        depress=props.show_motion_paths,
    )

    row.separator(factor=0.5)
    row.operator("anim.amp_fmp_add_element", text="", icon="ADD")
    row.operator("anim.amp_fmp_remove_active_element", text="", icon="REMOVE")
    row.separator(factor=0.5)
    refresh_row = row.row(align=True)
    refresh_row.enabled = len(props.elements) > 0
    refresh_row.operator("anim.amp_fmp_refresh_all_paths", text="", icon="FILE_REFRESH")
    row.separator(factor=0.5)
    row.prop(props, "show_list", text="", icon="DOCUMENTS")
    row.separator(factor=0.5)
    row.prop(props, "show_settings", text="", icon="SETTINGS")

    layout.separator()

    if props.show_settings:
        motion_path_options(layout, props)

    if props.show_list:
        box = layout.box()
        box.label(text="Elements List")
        main_row = box.row()
        main_row.template_list("AMP_FMP_UL_Elements", "", props, "elements", props, "active_index", rows=5)

        button_col = main_row.column(align=True)
        button_col.operator("anim.amp_fmp_add_element", text="", icon="ADD")
        button_col.operator("anim.amp_fmp_remove_index_element", text="", icon="REMOVE").index = props.active_index
        button_col.separator(factor=0.5)
        button_col.operator("anim.amp_fmp_move_element_up", text="", icon="TRIA_UP").index = props.active_index
        button_col.operator("anim.amp_fmp_move_element_down", text="", icon="TRIA_DOWN").index = props.active_index



class AMP_FMP_PT_OffsetMoPathsGraph(AMP_FMP_PT_OffsetMoPathsBase, Panel):
    bl_label = "Offset MoPaths"
    bl_idname = "AMP_FMP_PT_OffsetMoPathsGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_parent_id = "AMP_PT_AniMateProGraph"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        props = context.scene.mp_props
        row.operator(
            "anim.amp_fmp_toggle_show_motion_paths",
            text="",
            **get_icon("AMP_flexmopaths_on" if props.show_motion_paths else "AMP_flexmopaths_off"),
            depress=props.show_motion_paths,
        )
        # row.label(text="Flex Motion Paths")


class AMP_FMP_PT_OffsetMoPathsDope(AMP_FMP_PT_OffsetMoPathsBase, Panel):
    bl_label = "Offset MoPaths"
    bl_idname = "AMP_FMP_PT_OffsetMoPathsDope"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_parent_id = "AMP_PT_AniMateProDope"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        props = context.scene.mp_props
        row.operator(
            "anim.amp_fmp_toggle_show_motion_paths",
            text="",
            **get_icon("AMP_flexmopaths_on" if props.show_motion_paths else "AMP_flexmopaths_off"),
            depress=props.show_motion_paths,
        )


class AMP_FMP_PT_OffsetMoPathsPanel(AMP_FMP_PT_OffsetMoPathsBase, Panel):
    bl_label = "Offset MoPaths"
    bl_idname = "AMP_FMP_PT_OffsetMoPathsPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"


class AMP_FMP_PT_OffsetMoPathsView(AMP_FMP_PT_OffsetMoPathsBase, Panel):
    bl_label = "Offset MoPaths"
    bl_idname = "AMP_FMP_PT_OffsetMoPathsView"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "AMP_PT_AniMateProView"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        props = context.scene.mp_props
        row.operator(
            "anim.amp_fmp_toggle_show_motion_paths",
            text="",
            **get_icon("AMP_flexmopaths_on" if props.show_motion_paths else "AMP_flexmopaths_off"),
            depress=props.show_motion_paths,
        )


classes = (
    AMP_FMP_PG_Element,
    AMP_FMP_PG_Properties,
    AMP_FMP_OT_Add_Element,
    AMP_FMP_OT_Remove_Active_Element,
    AMP_FMP_OT_Remove_Index_Element,
    AMP_FMP_OT_Move_Element_Up,
    AMP_FMP_OT_Move_Element_Down,
    AMP_FMP_OT_Toggle_Show_Motion_Paths,
    AMP_FMP_OT_Refresh_All_Paths,
    AMP_FMP_OT_Select_Element,
    AMP_FMP_OT_Select_Empty,
    AMP_FMP_UL_Elements,
    # AMP_FMP_PT_OffsetMoPathsBase,
    AMP_FMP_PT_OffsetMoPathsPanel,
    # AMP_FMP_PT_OffsetMoPathsGraph,
    # AMP_FMP_PT_OffsetMoPathsDope,
    # AMP_FMP_PT_OffsetMoPathsView,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mp_props = PointerProperty(type=AMP_FMP_PG_Properties)

    if bpy.context.scene.mp_props.show_motion_paths:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_handler)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.mp_props

    if depsgraph_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_handler)


if __name__ == "__main__":
    register()

# ---------------- anim_flex_motion_paths.py ----------------
