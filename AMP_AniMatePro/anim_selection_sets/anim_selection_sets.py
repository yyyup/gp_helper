import bpy
import re
import uuid
import json
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy.props import (
    BoolProperty,
    FloatVectorProperty,
    StringProperty,
    CollectionProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
)
from mathutils import Vector
from ..utils.customIcons import get_icon
from ..utils import refresh_ui, dprint


from .anim_selection_sets_gui import update_display_gui, register_gui, unregister_gui


from . import floating_panels


icon_map = {
    "BONE": "BONE_DATA",
    "LIGHT": "LIGHT_DATA",
    "CAMERA": "CAMERA_DATA",
    "OBJECT": "OBJECT_DATA",
}


class AMP_PG_AnimSetElement(PropertyGroup):
    object_ref: PointerProperty(type=bpy.types.Object)
    bone_name: StringProperty()


class AMP_PG_AnimSet(PropertyGroup):
    name: StringProperty(default="AMP_Set")
    color: FloatVectorProperty(subtype="COLOR", size=3, default=(1, 0.2, 0.2), min=0.0, max=1.0)
    pinned: BoolProperty(default=True)
    elements: CollectionProperty(type=AMP_PG_AnimSetElement)
    set_type: EnumProperty(
        name="Set Type",
        items=[
            ("BONE", "Bones", ""),
            ("LIGHT", "Lights", ""),
            ("CAMERA", "Cameras", ""),
            ("OBJECT", "Objects", ""),
        ],
        default="OBJECT",
    )
    row: IntProperty(name="Row", default=1, description="Row in the pinned UI")
    priority: IntProperty(name="Priority", default=1, description="Ordering priority within each row")
    uid: StringProperty(default="", description="Unique ID for this Anim Set")

    def get_set_icon(self):
        if not self.elements:
            return "SELECT_SET"
        return icon_map.get(self.set_type, "QUESTION")


class AMP_PG_RegionState(PropertyGroup):
    """Property group to store GUI state for each region"""

    region_key: StringProperty(default="", description="Unique key for this region (based on WINDOW region ID)")
    window_region_id: StringProperty(default="", description="ID of the WINDOW region for stable identification")

    # Corner-based positioning instead of absolute coordinates
    corner_type: EnumProperty(
        name="Corner Type",
        items=[
            ("top_left", "Top Left", "Distance from top-left corner"),
            ("top_right", "Top Right", "Distance from top-right corner"),
            ("bottom_left", "Bottom Left", "Distance from bottom-left corner"),
            ("bottom_right", "Bottom Right", "Distance from bottom-right corner"),
        ],
        default="bottom_right",
        description="Corner to measure distances from",
    )
    corner_distance_x: IntProperty(default=50, description="Distance from corner in X direction")
    corner_distance_y: IntProperty(default=50, description="Distance from corner in Y direction")

    # Legacy properties for backward compatibility (will be gradually phased out)
    gui_position_x: IntProperty(default=50, description="GUI X position (legacy)")
    gui_position_y: IntProperty(default=50, description="GUI Y position (legacy)")

    collapsed: BoolProperty(default=False, description="Whether the GUI is collapsed")
    area_type: StringProperty(default="", description="Area type for this region")
    alignment: EnumProperty(
        name="Alignment",
        items=[
            ("left", "Left", "Selection sets appear to the left of the grabber"),
            ("right", "Right", "Selection sets appear to the right of the grabber"),
        ],
        default="right",
        description="Direction where selection sets are aligned relative to the grabber",
    )
    vertical_alignment: EnumProperty(
        name="Vertical Alignment",
        items=[
            ("bottom", "Bottom", "Rows grow upward from the grabber"),
            ("top", "Top", "Rows grow downward from the grabber"),
        ],
        default="bottom",
        description="Vertical direction where rows grow relative to the grabber",
    )


def update_display_gui_wrapper(self, context):
    """Update function for display_gui property."""
    try:
        from . import floating_panels

        if floating_panels:
            floating_panels.update_gui_state(context, self.display_gui)
    except ImportError:
        pass
    refresh_ui(context)


class AMP_PG_AnimSetPreset(PropertyGroup):
    name: StringProperty(default="AnimSet_Preset")
    # Each preset now contains its own sets list.
    sets: CollectionProperty(type=AMP_PG_AnimSet)
    pinned: BoolProperty(default=True)


class AMP_PG_SceneAnimSets(PropertyGroup):
    display_settings: BoolProperty(name="Display Settings", default=False)
    display_colors: BoolProperty(name="Display Colors", default=True)
    display_icons: BoolProperty(name="Display Icons", default=True)
    simple_order: BoolProperty(name="Simple Order", default=True)
    display_presets: BoolProperty(name="Display Presets", default=False)
    display_gui: BoolProperty(name="Display GUI", default=True, update=update_display_gui_wrapper)
    # Removed the scene-level "sets" collection.
    # Instead, each preset (in presets) holds its own sets.
    presets: CollectionProperty(type=AMP_PG_AnimSetPreset)
    active_preset_index: IntProperty(default=-1, update=lambda s, c: None)
    # Store the active set index for the active preset.
    active_set_index: IntProperty(default=-1)
    # For move-with-keys, we still keep an active_move_set_index.
    active_move_set_index: IntProperty(default=-1)
    # Region states for storing GUI position and collapse state per region
    region_states: CollectionProperty(type=AMP_PG_RegionState)


def detect_element_types_in_selection(context):
    st = set()
    mode = context.mode
    obj = context.active_object

    if mode == "POSE" and obj and obj.type == "ARMATURE":
        for b in obj.data.bones:
            if b.select:
                st.add("BONE")
                break  # Only need to know if there are bones
    elif mode == "OBJECT":
        for o in context.selected_objects:
            if o.type == "CAMERA":
                st.add("CAMERA")
            elif o.type == "LIGHT":
                st.add("LIGHT")
            else:
                st.add("OBJECT")
    return st


def deselect_bones(arm_obj):
    if arm_obj and arm_obj.type == "ARMATURE":
        for b in arm_obj.data.bones:
            b.select = False


def evaluate_set_type(anim_set):
    has_cam, has_light, has_other = False, False, False
    for e in anim_set.elements:
        if e.bone_name:
            anim_set.set_type = "BONE"
            return
        
        if e.object_ref and e.object_ref.type == "CAMERA":
            has_cam = True

        elif e.object_ref and e.object_ref.type == "LIGHT":
            has_light = True
        else:
            has_other = True

    if not anim_set.elements:
        if anim_set.set_type == "BONE":
            anim_set.set_type = "BONE"
        else:
            anim_set.set_type = "OBJECT"
        return

    if has_cam and not has_light and not has_other:
        anim_set.set_type = "CAMERA"
    elif has_light and not has_cam and not has_other:
        anim_set.set_type = "LIGHT"
    else:
        anim_set.set_type = "OBJECT"


class AMP_OT_AnimSetSelect(Operator):
    bl_idname = "anim.amp_anim_set_select"
    bl_label = "Select Anim Set"
    bl_description = (
        "Select all objects/bones in this set.\n"
        "SHIFT: Add selection\n"
        "CTRL: Toggle selection\n"
        "If SHIFT/CTRL are pressed, swapping Pose/Object modes is restricted."
    )

    set_index: IntProperty()
    selection_mode: EnumProperty(
        items=[("REPLACE", "Replace", ""), ("ADD", "Add", ""), ("TOGGLE", "Toggle", "")],
        default="REPLACE",
    )

    def invoke(self, context, event):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            self.report({"WARNING"}, "No active preset.")
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        sets = preset.sets

        if 0 <= self.set_index < len(sets):
            anim_set = sets[self.set_index]
            if context.mode == "OBJECT" and anim_set.set_type == "BONE":
                if event.shift or event.ctrl:
                    self.report({"WARNING"}, "Cannot add/toggle bone selection in OBJECT mode.")
                    return {"CANCELLED"}
            if context.mode == "POSE" and anim_set.set_type != "BONE":
                if event.shift or event.ctrl:
                    self.report({"WARNING"}, "Cannot add/toggle object selection in POSE mode.")
                    return {"CANCELLED"}

        # Determine selection mode based on SHIFT and CTRL keys
        if event.shift and not event.ctrl:
            self.selection_mode = "ADD"
        elif event.ctrl and not event.shift:
            self.selection_mode = "TOGGLE"
        else:
            self.selection_mode = "REPLACE"
        return self.execute(context)

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        sets = preset.sets
        if not (0 <= self.set_index < len(sets)):
            return {"CANCELLED"}
        anim_set = sets[self.set_index]

        if not context.active_object:
            if context.scene.objects:
                context.view_layer.objects.active = context.scene.objects[0]
            else:
                self.report({"WARNING"}, "No objects in scene.")
                return {"CANCELLED"}

        if anim_set.set_type == "BONE":
            arm = None

            # Remove unreachable references
            for i in reversed(range(len(anim_set.elements))):
                e = anim_set.elements[i]
                obj = e.object_ref
                if not obj or obj.name not in bpy.data.objects or obj.users == 0:
                    self.report({"WARNING"}, f"Element {e.bone_name} not found. Removed from set.")
                    anim_set.elements.remove(i)
                elif obj.name not in {o.name for o in context.view_layer.objects}:
                    self.report({"WARNING"}, f"Could not select {e.bone_name} because it is hidden.")
                    # keep in set
                    continue

            if self.selection_mode == "REPLACE":
                bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.select_all(action="DESELECT")

            for e in anim_set.elements:
                if e.object_ref and e.object_ref.type == "ARMATURE":
                    arm = e.object_ref
                    try:
                        arm.select_set(True)
                        context.view_layer.objects.active = arm
                    except RuntimeError:
                        self.report({"WARNING"}, f"Could not select {arm.name}. It may be hidden or unavailable.")
                        continue

            if arm:
                bpy.ops.object.mode_set(mode="POSE")

                for i in reversed(range(len(anim_set.elements))):
                    e_item = anim_set.elements[i]
                    if not arm or not arm.data.bones.get(e_item.bone_name):
                        self.report({"WARNING"}, f"Bone {e_item.bone_name} not found. Removed from set.")
                        anim_set.elements.remove(i)

                evaluate_set_type(anim_set)

                for i in reversed(range(len(anim_set.elements))):
                    e_item = anim_set.elements[i]
                    if not arm.data.bones.get(e_item.bone_name):
                        self.report({"WARNING"}, f"Bone {e_item.bone_name} not found. Removed from set.")
                        anim_set.elements.remove(i)

                if self.selection_mode == "REPLACE":
                    deselect_bones(arm)

                if self.selection_mode == "TOGGLE":
                    any_selected = False
                    for e in anim_set.elements:
                        bone = arm.data.bones.get(e.bone_name)
                        if bone and bone.select:
                            any_selected = True
                            break
                    # guard missing bones
                    for i in reversed(range(len(anim_set.elements))):
                        e = anim_set.elements[i]
                        bone = arm.data.bones.get(e.bone_name)
                        if not bone:
                            self.report({"WARNING"}, f"Bone {e.bone_name} was deleted. Removed from set.")
                            anim_set.elements.remove(i)
                            continue
                        bone.select = not any_selected
                else:
                    # ADD/REPLACE mode
                    for i in reversed(range(len(anim_set.elements))):
                        e = anim_set.elements[i]
                        bone = arm.data.bones.get(e.bone_name)
                        if not bone:
                            self.report({"WARNING"}, f"Bone {e.bone_name} was deleted. Removed from set.")
                            anim_set.elements.remove(i)
                            continue
                        bone.select = True

        else:
            # Remove unreachable references
            for i in reversed(range(len(anim_set.elements))):
                e = anim_set.elements[i]
                obj = e.object_ref
                if not obj or obj.name not in bpy.data.objects or obj.users == 0:
                    self.report({"WARNING"}, f"Element {obj.name if obj else '<unknown>'} not found. Removed from set.")
                    anim_set.elements.remove(i)
                elif obj.name not in {o.name for o in context.view_layer.objects}:
                    self.report({"WARNING"}, f"{obj.name} is not selectable.")
                    # keep in set
                    continue

            bpy.ops.object.mode_set(mode="OBJECT")
            if self.selection_mode == "REPLACE":
                bpy.ops.object.select_all(action="DESELECT")
            if self.selection_mode == "TOGGLE":
                any_selected = False
                for e in anim_set.elements:
                    obj = e.object_ref
                    if obj and obj.select_get():
                        any_selected = True
                        break
                for e in anim_set.elements:
                    obj = e.object_ref
                    if obj:
                        try:
                            obj.select_set(not any_selected)
                            if not any_selected:
                                context.view_layer.objects.active = obj
                        except RuntimeError:
                            self.report({"WARNING"}, f"{obj.name} is not selectable.")
                            continue
            else:
                for e in anim_set.elements:
                    obj = e.object_ref
                    if obj:
                        try:
                            obj.select_set(True)
                            context.view_layer.objects.active = obj
                        except RuntimeError:
                            self.report({"WARNING"}, f"{obj.name} is not selectable.")
                            continue

        return {"FINISHED"}


class AMP_OT_AnimSetAdd(Operator):
    bl_idname = "anim.amp_anim_set_add"
    bl_label = "Add Anim Set"
    bl_description = "Create a new Anim Set with the currently selected elements"

    def execute(self, context):
        distinct = detect_element_types_in_selection(context)
        if len(distinct) == 0:
            self.report({"WARNING"}, "No elements selected. Canceled.")
            return {"CANCELLED"}

        scene_props = context.scene.amp_anim_set
        if not scene_props.presets:
            new_preset = scene_props.presets.add()
            new_preset.name = "AnimSet_Preset.001"
            scene_props.active_preset_index = 0
        preset = scene_props.presets[scene_props.active_preset_index]

        new_set = preset.sets.add()
        new_set.uid = str(uuid.uuid4())
        # update the active set index to the new one
        scene_props.active_set_index = len(preset.sets) - 1

        if context.mode == "POSE":
            arm = context.active_object
            if arm and arm.type == "ARMATURE":
                for b in arm.data.bones:
                    if b.select:
                        e = new_set.elements.add()
                        e.bone_name = b.name
                        e.object_ref = arm
        else:
            bpy.ops.anim.amp_anim_set_add_members(set_index=len(preset.sets) - 1)

        base_name = "object_set"
        if len(distinct) == 1:
            st = list(distinct)[0].lower()
            base_name = f"{st}_set"
            new_set.set_type = st.upper()
        else:
            new_set.set_type = "OBJECT"

        new_set.name = base_name

        if new_set.set_type == "BONE":
            new_set.color = (0.2, 1.0, 0.2)
        elif new_set.set_type == "CAMERA":
            new_set.color = (0.2, 0.2, 1.0)
        elif new_set.set_type == "LIGHT":
            new_set.color = (0.5, 0.5, 0.0)
        else:
            new_set.color = (1.0, 0.2, 0.2)

        # For ordering in the pinned UI
        if preset.sets:
            max_row = max(s.row for s in preset.sets) if preset.sets else 0
            new_set.row = max_row + 1
            new_set.priority = 1

        return {"FINISHED"}


class AMP_OT_AnimSetRemove(Operator):
    bl_idname = "anim.amp_anim_set_remove"
    bl_label = "Remove Anim Set"
    bl_description = "Delete this set from the list"

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        idx = scene_props.active_set_index
        if 0 <= idx < len(preset.sets):
            preset.sets.remove(idx)
            scene_props.active_set_index = min(idx, len(preset.sets) - 1)
        return {"FINISHED"}


class AMP_OT_AnimSetMove(Operator):
    bl_idname = "anim.amp_anim_set_move"
    bl_label = "Move Anim Set"
    bl_description = "Move set up/down in the UI list"

    direction: StringProperty()

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        idx = scene_props.active_set_index
        if self.direction == "UP" and idx > 0:
            preset.sets.move(idx, idx - 1)
            scene_props.active_set_index -= 1
        elif self.direction == "DOWN" and idx < len(preset.sets) - 1:
            preset.sets.move(idx, idx + 1)
            scene_props.active_set_index += 1
        return {"FINISHED"}


class AMP_OT_AnimSetAddMembers(Operator):
    bl_idname = "anim.amp_anim_set_add_members"
    bl_label = "Add Members"
    bl_description = "Add selected elements to this set.\nIf the set ends up mixed, it becomes MULTI."

    set_index: IntProperty()

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        sets = preset.sets
        if not (0 <= self.set_index < len(sets)):
            return {"CANCELLED"}

        anim_set = sets[self.set_index]
        distinct = detect_element_types_in_selection(context)

        if not distinct:
            self.report({"WARNING"}, "No valid elements selected.")
            return {"CANCELLED"}

        if "BONE" in distinct and anim_set.set_type != "BONE":
            self.report({"WARNING"}, "Can't add bones to a non-bone set.")
            return {"CANCELLED"}

        if context.mode == "POSE":
            arm = context.active_object
            if arm and arm.type == "ARMATURE":
                for b in arm.data.bones:
                    if b.select:
                        if anim_set.set_type in {"OBJECT", ""}:
                            anim_set.set_type = "BONE"
                        if anim_set.set_type != "BONE":
                            return {"CANCELLED"}
                        if not any(e.bone_name == b.name and e.object_ref == arm for e in anim_set.elements):
                            ne = anim_set.elements.add()
                            ne.bone_name = b.name
                            ne.object_ref = arm
        else:
            for o in context.selected_objects:
                if not any(e.object_ref == o for e in anim_set.elements):
                    ne = anim_set.elements.add()
                    ne.object_ref = o

        evaluate_set_type(anim_set)
        return {"FINISHED"}


class AMP_OT_AnimSetRemoveMembers(Operator):
    bl_idname = "anim.amp_anim_set_remove_members"
    bl_label = "Remove Members"
    bl_description = (
        "Remove selected elements from this set.\n"
        "If all remaining elements are a single type, set switches to that type."
    )

    set_index: IntProperty()

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        sets = preset.sets
        if not (0 <= self.set_index < len(sets)):
            return {"CANCELLED"}
        anim_set = sets[self.set_index]

        if anim_set.set_type == "BONE" and context.mode == "POSE":
            arm = context.active_object
            if arm and arm.type == "ARMATURE":
                for b in arm.data.bones:
                    if b.select:
                        for i in reversed(range(len(anim_set.elements))):
                            e = anim_set.elements[i]
                            if e.bone_name == b.name and e.object_ref == arm:
                                anim_set.elements.remove(i)
        elif anim_set.set_type in {"LIGHT", "CAMERA", "OBJECT"} and context.mode == "OBJECT":
            for o in context.selected_objects:
                for i in reversed(range(len(anim_set.elements))):
                    e = anim_set.elements[i]
                    if e.object_ref == o:
                        anim_set.elements.remove(i)

        evaluate_set_type(anim_set)
        return {"FINISHED"}


class AMP_OT_AnimSetPresetAdd(Operator):
    bl_idname = "anim.amp_anim_set_preset_add"
    bl_label = "New Preset"
    bl_description = "Create a new blank preset"

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if len(scene_props.presets) >= 9:
            self.report({"WARNING"}, "Max 9 presets reached.")
            return {"CANCELLED"}

        new_preset = scene_props.presets.add()
        new_preset.name = f"AnimSet_Preset.{len(scene_props.presets):03d}"
        scene_props.active_preset_index = len(scene_props.presets) - 1
        # Reset the active set index when switching presets.
        scene_props.active_set_index = 0
        return {"FINISHED"}


class AMP_OT_AnimSetPresetRemove(Operator):
    bl_idname = "anim.amp_anim_set_preset_remove"
    bl_label = "Remove Preset"

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        idx = scene_props.active_preset_index
        if 0 <= idx < len(scene_props.presets):
            scene_props.presets.remove(idx)
            scene_props.active_preset_index = min(idx, len(scene_props.presets) - 1)
            # Reset active set index if no presets remain.
            if len(scene_props.presets) == 0:
                scene_props.active_set_index = -1
            else:
                scene_props.active_set_index = 0
        return {"FINISHED"}


class AMP_OT_AnimSetPresetMove(Operator):
    bl_idname = "anim.amp_anim_set_preset_move"
    bl_label = "Move Preset"
    direction: StringProperty()

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        idx = scene_props.active_preset_index
        if self.direction == "UP" and idx > 0:
            scene_props.presets.move(idx, idx - 1)
            scene_props.active_preset_index = idx - 1
        elif self.direction == "DOWN" and idx < len(scene_props.presets) - 1:
            scene_props.presets.move(idx, idx + 1)
            scene_props.active_preset_index = idx + 1
        return {"FINISHED"}


class AMP_OT_AnimSetPresetCopy(Operator):
    bl_idname = "anim.amp_anim_set_preset_copy"
    bl_label = "Copy Preset"

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        idx = scene_props.active_preset_index
        if 0 <= idx < len(scene_props.presets):
            preset = scene_props.presets[idx]
            preset_data = {"name": preset.name, "sets": []}
            for s in preset.sets:
                preset_data["sets"].append(
                    {
                        "name": s.name,
                        "color": list(s.color),
                        "pinned": s.pinned,
                        "set_type": s.set_type,
                        "row": s.row,
                        "priority": s.priority,
                        "uid": s.uid,
                        "elements": [
                            {"bone_name": e.bone_name, "object_ref": e.object_ref.name if e.object_ref else ""}
                            for e in s.elements
                        ],
                    }
                )
            bpy.context.window_manager.clipboard = json.dumps(preset_data)
        return {"FINISHED"}


class AMP_OT_AnimSetPresetPaste(Operator):
    bl_idname = "anim.amp_anim_set_preset_paste"
    bl_label = "Paste Preset"

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        idx = scene_props.active_preset_index
        if 0 <= idx < len(scene_props.presets):
            preset = scene_props.presets[idx]
            try:
                preset_data = json.loads(bpy.context.window_manager.clipboard)
                preset.sets.clear()
                for s_dict in preset_data.get("sets", []):
                    new_s = preset.sets.add()
                    new_s.name = s_dict["name"]
                    new_s.color = s_dict["color"]
                    new_s.pinned = s_dict["pinned"]
                    new_s.set_type = s_dict["set_type"]
                    new_s.row = s_dict["row"]
                    new_s.priority = s_dict["priority"]
                    new_s.uid = s_dict["uid"]
                    for e_dict in s_dict["elements"]:
                        ne = new_s.elements.add()
                        ne.bone_name = e_dict["bone_name"]
                        if e_dict["object_ref"]:
                            obj = bpy.data.objects.get(e_dict["object_ref"])
                            ne.object_ref = obj
            except Exception:
                self.report({"WARNING"}, "Invalid data in clipboard.")
        return {"FINISHED"}


class AMP_OT_AnimSetPresetActivate(Operator):
    bl_idname = "anim.amp_anim_set_preset_activate"
    bl_label = "Activate Preset"

    index: IntProperty()

    def execute(self, context):
        scene_props = context.scene.amp_anim_set
        if 0 <= self.index < len(scene_props.presets):
            scene_props.active_preset_index = self.index
            scene_props.active_set_index = 0
        return {"FINISHED"}


def can_add(context, anim_set):
    if anim_set.set_type == "BONE":
        if context.mode not in {"POSE", "OBJECT"}:
            return False
    elif anim_set.set_type in {"LIGHT", "CAMERA", "OBJECT"}:
        if context.mode != "OBJECT":
            return False
    selected_types = detect_element_types_in_selection(context)
    if anim_set.set_type == "BONE":
        if any(t != "BONE" for t in selected_types):
            return False
        if context.mode not in {"POSE", "OBJECT"}:
            return False
    else:
        if context.mode != "OBJECT":
            return False
        if "BONE" in selected_types:
            return False
    if not context.selected_objects and context.mode != "POSE":
        return False
    all_in_set = True
    if context.mode == "POSE":
        arm = context.active_object
        if arm and arm.type == "ARMATURE":
            for b in arm.data.bones:
                if b.select:
                    if not any(e.bone_name == b.name for e in anim_set.elements):
                        all_in_set = False
                        break
    else:
        for o in context.selected_objects:
            if not any(e.object_ref == o for e in anim_set.elements):
                all_in_set = False
                break
    return not all_in_set


def can_remove(context, anim_set):
    if anim_set.set_type == "BONE":
        arm = context.active_object
        if arm and arm.type == "ARMATURE":
            for b in arm.data.bones:
                if b.select and any(e.bone_name == b.name and e.object_ref == arm for e in anim_set.elements):
                    return True
    else:
        for o in context.selected_objects:
            if any(e.object_ref == o for e in anim_set.elements):
                return True
    return False


class AMP_UL_AnimSets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        sel_op = row.operator("anim.amp_anim_set_select", text="", icon=item.get_set_icon())
        sel_op.set_index = index
        sel_op.selection_mode = "REPLACE"
        row.separator(factor=0.5)
        row.prop(item, "name", text="", emboss=False)
        row.separator(factor=0.5)
        clr = row.row(align=True)
        clr.active = False
        clr.prop(item, "color", text="", icon="BLANK1")
        row2 = row.row(align=True)
        sub21 = row2.row()
        sub21.enabled = can_add(context, item)
        add_op = sub21.operator("anim.amp_anim_set_add_members", text="", icon="ADD")
        add_op.set_index = index
        sub22 = row2.row()
        sub22.enabled = can_remove(context, item)
        rem_op = sub22.operator("anim.amp_anim_set_remove_members", text="", icon="REMOVE")
        rem_op.set_index = index
        row3 = row.row(align=True)
        row3.prop(item, "pinned", text="", icon="PINNED" if item.pinned else "UNPINNED", emboss=False)


class AMP_UL_AnimSetPresets(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        icon_str = f"AMP_COLORS_0{index+1}" if index < 9 else "NONE"
        op = row.operator(
            "anim.amp_anim_set_preset_activate",
            text="",
            **get_icon(icon_str),
            emboss=False,
        )
        op.index = index
        row.prop(item, "name", text="", emboss=False)
        row.prop(item, "pinned", text="", icon="PINNED" if item.pinned else "UNPINNED", emboss=False)


def draw_toggles_row(self, context):
    layout = self.layout
    row = layout.row(align=True)
    box = row.box()
    box.scale_y = 0.65
    box.label(text="Selection Sets")
    if context.scene.amp_anim_set.display_settings:
        row.separator(factor=0.25)
        row.prop(context.scene.amp_anim_set, "display_colors", text="", **get_icon("COLOR"))
        row.separator(factor=0.25)
        row.prop(context.scene.amp_anim_set, "display_icons", text="", **get_icon("OBJECT_DATA"))
        row.separator(factor=0.25)
        row.prop(context.scene.amp_anim_set, "simple_order", text="", **get_icon("PRESET"))
        row.separator(factor=0.25)
        row.prop(context.scene.amp_anim_set, "display_presets", text="", **get_icon("OPTIONS"))
        row.separator(factor=0.25)
        row.prop(context.scene.amp_anim_set, "display_gui", text="", **get_icon("WINDOW"))
        row.separator(factor=0.25)
    row.prop(context.scene.amp_anim_set, "display_settings", text="", icon="SETTINGS")


def draw_preset_list(self, context):
    layout = self.layout
    scene_props = context.scene.amp_anim_set
    box = layout.box()
    box.label(text="Presets")
    row = box.row()
    row.template_list("AMP_UL_AnimSetPresets", "", scene_props, "presets", scene_props, "active_preset_index")
    col = row.column(align=True)
    col.operator("anim.amp_anim_set_preset_add", icon="ADD", text="")
    col.operator("anim.amp_anim_set_preset_remove", icon="REMOVE", text="")
    col.separator()
    up_op = col.operator("anim.amp_anim_set_preset_move", icon="TRIA_UP", text="")
    up_op.direction = "UP"
    down_op = col.operator("anim.amp_anim_set_preset_move", icon="TRIA_DOWN", text="")
    down_op.direction = "DOWN"
    col.separator()
    col.operator("anim.amp_anim_set_preset_copy", icon="COPYDOWN", text="")
    col.operator("anim.amp_anim_set_preset_paste", icon="PASTEDOWN", text="")


def draw_config_panel(self, context):
    layout = self.layout
    scene_props = context.scene.amp_anim_set
    if scene_props.display_settings:
        row = layout.row()
        # Use the active preset's sets for the UIList.
        if scene_props.active_preset_index >= 0 and scene_props.active_preset_index < len(scene_props.presets):
            preset = scene_props.presets[scene_props.active_preset_index]
            row.template_list("AMP_UL_AnimSets", "", preset, "sets", scene_props, "active_set_index", rows=4)
        else:
            row.label(text="No preset active.")
        col = row.column(align=True)
        col.operator("anim.amp_anim_set_add", icon="ADD", text="")
        col.operator("anim.amp_anim_set_remove", icon="REMOVE", text="")
        col.separator()
        move_up = col.operator("anim.amp_anim_set_move", icon="TRIA_UP", text="")
        move_up.direction = "UP"
        move_down = col.operator("anim.amp_anim_set_move", icon="TRIA_DOWN", text="")
        move_down.direction = "DOWN"
        if scene_props.display_presets:
            draw_preset_list(self, context)


def draw_main_panel(self, context):
    scene_props = context.scene.amp_anim_set

    if scene_props.display_settings:
        draw_toggles_row(self, context)
        draw_config_panel(self, context)

    layout = self.layout
    col = layout.column(align=True)

    if scene_props.display_presets and not scene_props.display_settings:
        presets_row = col.row(align=True)
        box = presets_row.box()
        box.scale_y = 0.65
        if scene_props.active_preset_index >= 0 and scene_props.active_preset_index < len(scene_props.presets):
            preset_name = scene_props.presets[scene_props.active_preset_index].name
        else:
            preset_name = "Presets"
        box.label(text=preset_name)
        col.separator(factor=0.2)
        pinned_presets = [(idx, p) for idx, p in enumerate(scene_props.presets) if p.pinned][:9]
        presets_row.separator(factor=0.2)
        for idx, preset in pinned_presets:
            btn = presets_row.operator(
                "anim.amp_anim_set_preset_activate",
                text="",
                **get_icon(f"AMP_COLORS_0{idx+1}"),
                depress=preset == scene_props.presets[scene_props.active_preset_index],
            )
            btn.index = idx
            presets_row.separator(factor=0.2)

        presets_row.separator(factor=0.2)
        config_row = presets_row.row(align=True)
        config_row.alignment = "RIGHT"
        config_row.prop(scene_props, "display_settings", text="", icon="SETTINGS")

    elif not scene_props.display_settings:
        presets_row = col.row(align=True)
        box = presets_row.box()
        box.scale_y = 0.65
        row = box.row()
        row.label(text="Selection Sets")

        presets_row.separator(factor=0.2)
        config_row = presets_row.row(align=True)
        config_row.alignment = "RIGHT"
        config_row.prop(scene_props, "display_settings", text="", icon="SETTINGS")

    col.separator()

    if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
        col.label(text="No sets created yet.")
        return

    preset = scene_props.presets[scene_props.active_preset_index]

    if scene_props.simple_order:
        for i, s in enumerate(preset.sets):
            if s.pinned:
                draw_set_button(col, context, i, s, True)
            col.separator(factor=0.2)
    else:
        pinned_sets = [s for s in preset.sets if s.pinned]
        sets_by_row = {}
        for s in pinned_sets:
            sets_by_row.setdefault(s.row, []).append((s, s.priority))
        for row_number in sorted(sets_by_row.keys()):
            row_layout = col.row(align=True)
            for the_set, prio in sorted(sets_by_row[row_number], key=lambda x: x[1]):
                # Find the correct index by matching the uid instead of name to handle duplicate names
                i = next((idx for idx, s in enumerate(preset.sets) if s.uid == the_set.uid), -1)
                if i >= 0:  # Only draw if we found the set
                    draw_set_button(row_layout, context, i, the_set, False)
                    if prio != max(p[1] for p in sets_by_row[row_number]):
                        row_layout.separator(factor=0.2)
            col.separator(factor=0.2)


def draw_set_button(layout, context, i, s, simple_order=True):
    row = layout.row(align=True)
    if context.scene.amp_anim_set.active_move_set_index == i:
        row.alert = True
    else:
        row.alert = False
    if context.scene.amp_anim_set.display_settings and not simple_order:
        move_op = row.operator("anim.amp_anim_set_move_element", text="", icon="EMPTY_ARROWS", emboss=False)
        move_op.set_index = i
        move_op.set_uid = s.uid  # Pass the uid to ensure we move the correct element
        row.separator(factor=0.25)

    if context.scene.amp_anim_set.display_colors:
        sub = row.row(align=True)
        sub.scale_x = 0.7
        sub.enabled = False
        sub.prop(s, "color", text="", icon="BLANK1")

    icon = s.get_set_icon() if context.scene.amp_anim_set.display_icons else "BLANK1"
    select_op = row.operator("anim.amp_anim_set_select", text=s.name, icon=icon)
    select_op.set_index = i


class AMP_PT_AnimSetsPanelBase(Panel):
    bl_label = "Selection Sets"
    bl_category = "AniMatePro"
    bl_region_type = "UI"

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", **get_icon("AMP_select_sets"))

    def draw(self, context):
        # draw_toggles_row(self, context)
        # draw_config_panel(self, context)
        draw_main_panel(self, context)


class AMP_PT_AnimSetsPanelView(AMP_PT_AnimSetsPanelBase):
    bl_idname = "AMP_PT_AnimSetsPanelView"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "AMP_PT_AniMateProView"
    bl_options = {"DEFAULT_CLOSED"}


class AMP_PT_AnimSetsPanelDope(AMP_PT_AnimSetsPanelBase):
    bl_idname = "AMP_PT_AnimSetsPanelDope"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_parent_id = "AMP_PT_AniMateProDope"
    bl_options = {"DEFAULT_CLOSED"}


class AMP_PT_AnimSetsPanelGraph(AMP_PT_AnimSetsPanelBase):
    bl_idname = "AMP_PT_AnimSetsPanelGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_parent_id = "AMP_PT_AniMateProGraph"
    bl_options = {"DEFAULT_CLOSED"}


class AMP_PT_AnimSetsPanelPop(Panel):
    bl_label = "Selection Sets"
    bl_idname = "AMP_PT_AnimSetsPanelPop"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 20

    def draw(self, context):
        draw_main_panel(self, context)


class AMP_OT_AnimSetMoveElement(Operator):
    bl_idname = "anim.amp_anim_set_move_element"
    bl_label = "Move Set with Arrow Keys"

    set_index: IntProperty()
    set_uid: StringProperty()

    def invoke(self, context, event):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]

        # Verify that the set_index is valid and matches the expected uid
        if self.set_index < 0 or self.set_index >= len(preset.sets):
            return {"CANCELLED"}

        target = preset.sets[self.set_index]

        # If we have a uid specified, verify it matches the target at this index
        # This ensures we're moving the correct element even if names are duplicate
        if self.set_uid and target.uid != self.set_uid:
            # Find the correct element by uid
            correct_index = next((idx for idx, s in enumerate(preset.sets) if s.uid == self.set_uid), -1)
            if correct_index == -1:
                return {"CANCELLED"}
            self.set_index = correct_index
            target = preset.sets[self.set_index]

        self.set_uid = target.uid
        scene_props.active_move_set_index = self.set_index
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        scene_props = context.scene.amp_anim_set
        if scene_props.active_preset_index < 0 or scene_props.active_preset_index >= len(scene_props.presets):
            scene_props.active_move_set_index = -1
            refresh_ui(context)
            return {"CANCELLED"}
        preset = scene_props.presets[scene_props.active_preset_index]
        sets = preset.sets
        this_set = next((s for s in sets if s.uid == self.set_uid), None)
        if not this_set:
            scene_props.active_move_set_index = -1
            refresh_ui(context)
            return {"CANCELLED"}

        if event.type in {"ESC", "RIGHTMOUSE", "LEFTMOUSE", "RET"}:
            scene_props.active_move_set_index = -1
            refresh_ui(context)
            return {"CANCELLED"}

        if event.value == "PRESS":
            if event.type in {"UP_ARROW", "W"}:
                handle_vertical_movement(this_set, "up", sets)
            elif event.type in {"DOWN_ARROW", "S"}:
                handle_vertical_movement(this_set, "down", sets)
            elif event.type in {"LEFT_ARROW", "A"}:
                handle_horizontal_movement(this_set, "left", sets)
            elif event.type in {"RIGHT_ARROW", "D"}:
                handle_horizontal_movement(this_set, "right", sets)
            context.area.tag_redraw()

        refresh_ui(context)
        return {"RUNNING_MODAL"}


def handle_vertical_movement(anim_set, direction, all_sets):
    row = anim_set.row
    same_row = [s for s in all_sets if s.row == row]
    is_only_in_row = len(same_row) == 1
    if direction == "up" and row > 0:
        if not is_only_in_row:
            for s in all_sets:
                if s.row < row:
                    s.row -= 2
            anim_set.row -= 1
            anim_set.priority = -1
        else:
            anim_set.row -= 1
            anim_set.priority = -1
            for s in all_sets:
                if s.row < anim_set.row:
                    s.row -= 1
    elif direction == "down":
        max_row = max(s.row for s in all_sets) if all_sets else 0
        if not (row == max_row and is_only_in_row):
            if not is_only_in_row:
                for s in all_sets:
                    if s.row > row:
                        s.row += 2
                anim_set.row += 1
                anim_set.priority = -1
            else:
                anim_set.row += 1
                anim_set.priority = -1
                for s in all_sets:
                    if s.row > anim_set.row:
                        s.row += 1
    reorganize_sets(all_sets)


def handle_horizontal_movement(anim_set, direction, all_sets):
    same_row = [s for s in all_sets if s.row == anim_set.row]
    if not same_row:
        return
    max_priority = max(s.priority for s in same_row)
    if direction == "left" and anim_set.priority > 1:
        for s in same_row:
            s.priority *= 3
        anim_set.priority -= 4
    elif direction == "right" and anim_set.priority < max_priority:
        for s in same_row:
            s.priority *= 3
        anim_set.priority += 4
    reorganize_sets(all_sets)


def reorganize_sets(all_sets):
    if not all_sets:
        return
    unique_rows = sorted({s.row for s in all_sets})
    row_map = {old: new for new, old in enumerate(unique_rows, start=1)}
    for s in all_sets:
        s.row = row_map[s.row]
    for row_val in set(s.row for s in all_sets):
        row_items = [st for st in all_sets if st.row == row_val]
        row_items.sort(key=lambda x: x.priority)
        for i, st in enumerate(row_items, start=1):
            st.priority = i


class AMP_OT_AnimSetToggleGUI(Operator):
    """Toggle the floating GUI for selection sets"""

    bl_idname = "anim.amp_anim_set_toggle_gui"
    bl_label = "Toggle Selection Sets GUI"
    bl_description = "Toggle the floating GUI for selection sets in this region"

    def execute(self, context):
        dprint(f"[TOGGLE_OP] Called from {context.area.type if context.area else 'No Area'}")

        # Check if area is supported
        supported_area_types = ["VIEW_3D", "GRAPH_EDITOR", "DOPESHEET_EDITOR"]
        if not context.area or context.area.type not in supported_area_types:
            self.report({"ERROR"}, f"Unsupported area type: {context.area.type if context.area else 'None'}")
            return {"CANCELLED"}

        scene_props = context.scene.amp_anim_set

        # Toggle the GUI state
        scene_props.display_gui = not scene_props.display_gui

        # Import and use the new floating panels system
        try:
            from .anim_selection_sets_gui import update_display_gui
            from .floating_panels import ensure_tracker_running, toggle_gui

            if scene_props.display_gui:
                dprint("[TOGGLE_OP] Enabling floating selection sets GUI")
                # Start the simplified tracker
                ensure_tracker_running(context)
                # Enable GUI rendering
                toggle_gui(context)
                dprint("[TOGGLE_OP] Floating panels system activated")
            else:
                dprint("[TOGGLE_OP] Disabling floating selection sets GUI")
                # The tracker will continue running for debugging, just disable GUI
                # toggle_gui will handle the state change

            # Trigger GUI update
            update_display_gui(scene_props, context)

        except ImportError as e:
            dprint(f"[TOGGLE_OP] Import error: {e}")
            self.report({"ERROR"}, f"Failed to import floating panels: {e}")
            return {"CANCELLED"}
        except Exception as e:
            dprint(f"[TOGGLE_OP] Error: {e}")
            self.report({"ERROR"}, f"Error: {e}")
            return {"CANCELLED"}

        status = "enabled" if scene_props.display_gui else "disabled"
        debug_info = "(Ctrl+Alt+D to toggle debug, mouse tracking active)"
        self.report({"INFO"}, f"Selection sets floating GUI {status} {debug_info}")
        return {"FINISHED"}


class AMP_OT_AnimSetCancelTracker(Operator):
    """Cancel the floating panels tracker (for testing purposes)"""

    bl_idname = "anim.amp_anim_set_cancel_tracker"
    bl_label = "Cancel Tracker"
    bl_description = "Cancel the floating panels tracker (for testing purposes)"

    def execute(self, context):
        try:
            from . import floating_panels

            if floating_panels:
                success = floating_panels.cancel_tracker(context)
                if success:
                    self.report({"INFO"}, "Tracker cancelled successfully")
                else:
                    self.report({"INFO"}, "No tracker was running")
            else:
                self.report({"ERROR"}, "Floating panels module not available")
        except ImportError:
            self.report({"ERROR"}, "Failed to import floating panels")

        return {"FINISHED"}


classes = (
    AMP_PG_AnimSetElement,
    AMP_PG_AnimSet,
    AMP_PG_RegionState,
    AMP_PG_AnimSetPreset,
    AMP_PG_SceneAnimSets,
    AMP_OT_AnimSetSelect,
    AMP_OT_AnimSetAdd,
    AMP_OT_AnimSetRemove,
    AMP_OT_AnimSetMove,
    AMP_OT_AnimSetAddMembers,
    AMP_OT_AnimSetRemoveMembers,
    AMP_UL_AnimSets,
    AMP_OT_AnimSetMoveElement,
    AMP_OT_AnimSetPresetAdd,
    AMP_OT_AnimSetPresetRemove,
    AMP_OT_AnimSetPresetMove,
    AMP_OT_AnimSetPresetCopy,
    AMP_OT_AnimSetPresetPaste,
    AMP_OT_AnimSetPresetActivate,
    AMP_UL_AnimSetPresets,
    AMP_OT_AnimSetToggleGUI,
    AMP_OT_AnimSetCancelTracker,
    # AMP_PT_AnimSetsPanelView,
    # AMP_PT_AnimSetsPanelDope,
    # AMP_PT_AnimSetsPanelGraph,
    AMP_PT_AnimSetsPanelPop,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.amp_anim_set = PointerProperty(type=AMP_PG_SceneAnimSets)

    # Register floating panels system
    if floating_panels:
        try:
            floating_panels.register()
            dprint("Registered floating panels system")
        except Exception as e:
            dprint(f"Failed to register floating panels system: {e}")

    register_gui()
    # Initialize scene properties and create default preset
    scene_props = bpy.context.scene.amp_anim_set
    if not scene_props.presets:
        new_preset = scene_props.presets.add()
        new_preset.name = "AnimSet_Preset.001"
        scene_props.active_preset_index = 0
    # Let the default value from the property definition handle the initial state


def unregister():
    # Unregister floating panels system first
    if floating_panels:
        try:
            floating_panels.unregister()
            dprint("Unregistered floating panels system")
        except Exception as e:
            dprint(f"Failed to unregister floating panels system: {e}")

    unregister_gui()
    del bpy.types.Scene.amp_anim_set
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
