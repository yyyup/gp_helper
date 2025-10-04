import bpy
import math
from bpy.props import BoolProperty, StringProperty, PointerProperty, IntProperty  # noqa
from ..utils.customIcons import get_icon
from ..utils import get_prefs
from ..operators import draw_toggle_button, toggles
from .. import __package__ as base_package


def redraw(self, context):
    if context.area:
        context.area.tag_redraw()


class AMP_SWAPPER_OT_new_action(bpy.types.Operator):
    """Create a new blank action and assign it to the active object"""

    bl_idname = "anim.amp_swapper_new_action"
    bl_label = "New Action"

    def execute(self, context):
        new_action = bpy.data.actions.new(name="Action")
        active = context.object
        if active:
            if not active.animation_data:
                active.animation_data_create()
            active.animation_data.action = new_action
        self.report({"INFO"}, f"Created new action: {new_action.name}")
        return {"FINISHED"}


class AMP_SWAPPER_OT_duplicate_action(bpy.types.Operator):
    """Duplicate the chosen action"""

    bl_idname = "anim.amp_swapper_duplicate_action"
    bl_label = "Duplicate Action"

    action_name: bpy.props.StringProperty()

    def execute(self, context):
        old_action = bpy.data.actions.get(self.action_name)
        if not old_action:
            self.report({"WARNING"}, "No valid action to duplicate")
            return {"CANCELLED"}
        new_action = old_action.copy()
        new_action.name = f"{old_action.name}"
        self.report({"INFO"}, f"Duplicated action: {new_action.name}")
        active = context.object
        if active:
            if not active.animation_data:
                active.animation_data_create()
            active.animation_data.action = new_action
        return {"FINISHED"}


class AMP_SWAPPER_OT_unlink_action(bpy.types.Operator):
    """Unlink (clear) the chosen action from the active object"""

    bl_idname = "anim.amp_swapper_unlink_action"
    bl_label = "Unlink Action"

    action_name: bpy.props.StringProperty()

    def execute(self, context):
        active = context.object
        if active and active.animation_data and active.animation_data.action:
            if active.animation_data.action.name == self.action_name:
                active.animation_data.action = None
                self.report({"INFO"}, "Action unlinked")
        return {"FINISHED"}


class AMP_SWAPPER_OT_delete_action(bpy.types.Operator):

    bl_idname = "anim.amp_swapper_delete_action"
    bl_label = "Delete Action"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Delete the selected action permanently from the file.
Hold shift to skip the confitrmation"""

    action_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400) if not event.shift else self.execute(context)

    def execute(self, context):
        action = bpy.data.actions.get(self.action_name)
        if not action:
            self.report({"WARNING"}, "Action not found.")
            return {"CANCELLED"}
        bpy.data.actions.remove(action)
        self.report({"INFO"}, f"Deleted action '{self.action_name}'.")
        active = context.object
        if active and active.animation_data and active.animation_data.action:
            if active.animation_data.action.name == self.action_name:
                active.animation_data.action = None
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Are you sure you want to permanently delete '{self.action_name}'?", icon="TRASH")


class AMP_SWAPPER_OT_add_custom_property(bpy.types.Operator):
    bl_idname = "anim.amp_swapper_add_custom_property"
    bl_label = "Add Custom Property"

    def execute(self, context):
        action = context.object.animation_data.action

        # Find an available property name.
        for i in range(100):
            candidate = "prop" if i == 0 else f"prop{i}"
            if candidate not in action.keys():
                new_prop_name = candidate
                break
        else:
            self.report({"WARNING"}, "No available property name found")
            return {"CANCELLED"}

        # Create the custom property with a default value.
        action[new_prop_name] = 1.00

        # Get the UI manager for the new property and update its limits.
        ui = action.id_properties_ui(new_prop_name)
        ui.update(default=1.00, min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)

        self.report({"INFO"}, f"Added custom property '{new_prop_name}' with limits")
        return {"FINISHED"}


class AMP_SWAPPER_OT_custom_property_edit_wrapper(bpy.types.Operator):
    """Edit the values of the custom property directly from here.
    If the action is hidden or in a hidden collection, unhide before trying to edit the property."""

    bl_idname = "anim.select_actionproperties_edit_wrapper"
    bl_label = "Edit Action Custom Property"

    property_name: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.animation_data and context.object.animation_data.action

    def execute(self, context):
        action = context.object.animation_data.action
        if self.property_name not in action.keys():
            self.report({"ERROR"}, f"Property '{self.property_name}' not found in action '{action.name}'")
            return {"CANCELLED"}
        try:
            bpy.ops.anim.select_actionproperties_edit_invoke("INVOKE_DEFAULT", property_name=self.property_name)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Error: {str(e)}")
            return {"CANCELLED"}


class AMP_SWAPPER_OT_custom_property_edit_invoke(bpy.types.Operator):
    """Invoke editing for the custom property of the action."""

    bl_idname = "anim.select_actionproperties_edit_invoke"
    bl_label = "Invoke Edit Action Custom Property"

    property_name: StringProperty()

    def execute(self, context):
        bpy.ops.wm.properties_edit(
            "INVOKE_DEFAULT",
            data_path="object.animation_data.action",
            property_name=self.property_name,
        )
        return {"FINISHED"}


class AMP_SWAPPER_OT_delete_custom_property(bpy.types.Operator):
    bl_idname = "anim.amp_swapper_delete_custom_property"
    bl_label = "Delete Custom Property"
    bl_options = {"REGISTER", "UNDO"}

    property_name: bpy.props.StringProperty()

    def execute(self, context):
        action = context.object.animation_data.action
        if self.property_name not in action.keys():
            self.report({"WARNING"}, f"Property '{self.property_name}' not found")
            return {"CANCELLED"}
        del action[self.property_name]
        self.report({"INFO"}, f"Deleted property '{self.property_name}'")
        return {"FINISHED"}


class AMP_SWAPPER_OT_select_action_popup(bpy.types.Operator):
    """Popup to select an action from all scene actions"""

    bl_idname = "anim.amp_swapper_select_action_popup"
    bl_label = "Select Action"

    def invoke(self, context, event):
        wm = context.window_manager
        props = context.scene.amp_anim_swapper_props

        # Reset Filter and Options toggle on open so the experience is consistent
        props.options = False
        # props.filter = False

        return wm.invoke_popup(self, width=props.column_width * props.columns)

    def draw(self, context):
        import math

        layout = self.layout
        props = context.scene.amp_anim_swapper_props
        # Title and filter
        row = layout.row(align=True)
        if props.filter:
            row.column().prop(props, "filter_text", text="")
        else:
            row.column().label(text="Actions", icon="ACTION")
        buttons = row.column(align=True)
        buttons.prop(props, "filter", text="", icon="FILTER")
        buttons.separator(factor=0.25)
        buttons.prop(props, "options", text="", icon="SETTINGS")
        # Collect actions
        acts = [a for a in bpy.data.actions if not props.filter or (props.filter_text.lower() in a.name.lower())]
        total = len(acts)
        cols = props.columns
        per = math.ceil(total / cols) if total else 0

        # Draw options panel
        if props.options:
            opts = layout.box().column()
            opts.use_property_split = True
            opts.use_property_decorate = False
            opts.label(text="Action Swapper Options", icon="SETTINGS")
            opts.separator()
            opts.prop(props, "column_width", text="Width", icon="ARROW_LEFTRIGHT", slider=False)
            opts.prop(props, "columns", text="Columns", icon="GRID")
            prefs = bpy.context.preferences.addons[base_package].preferences
            opts.prop(prefs, "scene_range_to_action_range")
            opts.prop(prefs, "start_from_first_frame")
            opts.prop(prefs, "zoom_to_action_range")
            opts.prop(prefs, "action_swapper_button")
            layout.separator()

        # Draw actions in columns
        main = layout.row(align=True)

        current = getattr(context.object.animation_data, "action", None)

        for ci in range(cols):
            col = main.column(align=True)
            for act in acts[ci * per : ci * per + per]:
                dr = col.row(align=True)
                sel = act == current
                play = bpy.context.screen.is_animation_playing and sel
                icon = "PAUSE" if play else "PLAY"
                op = dr.operator("anim.amp_swapper_set_active_action", text="", icon=icon, depress=sel)
                op.action_name = act.name
                op.playback = True
                dr.separator(factor=0.25)
                op2 = dr.operator(
                    "anim.amp_swapper_set_active_action",
                    text=act.name,
                    icon=("ASSET_MANAGER" if act.library else "ACTION"),
                    depress=sel,
                )
                op2.action_name = act.name
                op2.playback = False
                dr.prop(act, "use_fake_user", text="", icon="FAKE_USER_OFF")
                if act.library:
                    loc = dr.operator("anim.amp_swapper_make_local_action", text="", icon="LINKED")
                    loc.action_name = act.name
                else:
                    dup = dr.operator("anim.amp_swapper_duplicate_action", text="", icon="DUPLICATE")
                    dup.action_name = act.name
                dr.separator(factor=0.25)

                del_row = dr.row(align=True)
                del_row.alert = True
                del_op = del_row.operator("anim.amp_swapper_delete_action", text="", icon="TRASH")
                del_op.action_name = act.name
                dr.separator()

                col.separator(factor=0.25)

    def execute(self, context):
        return {"FINISHED"}


class AMP_SWAPPER_OT_set_active_action(bpy.types.Operator):
    """Set the selected action as active"""

    bl_idname = "anim.amp_swapper_set_active_action"
    bl_label = "Set Active Action"

    action_name: bpy.props.StringProperty()
    playback: BoolProperty(name="Playback", default=False)

    def init(self):
        self.action_name = ""
        self.playback = False

    def execute(self, context):
        prefs = bpy.context.preferences.addons[base_package].preferences

        active = context.object
        current = active.animation_data.action if active and active.animation_data else None
        act = bpy.data.actions.get(self.action_name)
        is_playing = context.screen.is_animation_playing

        same_action = True if act == current else False

        if not act:
            self.report({"WARNING"}, "Action not found")
            return {"CANCELLED"}

        if active and not same_action:
            if not active.animation_data:
                active.animation_data_create()
            active.animation_data.action = act
            self.report({"INFO"}, f"Active action set to {act.name}")

        if prefs.scene_range_to_action_range:
            context.scene.frame_start = int(act.frame_range[0])
            context.scene.frame_end = int(act.frame_range[1])

        if prefs.zoom_to_action_range:
            bpy.ops.anim.amp_zoom_frame_editors(ignore_selected=True)

        if prefs.start_from_first_frame and not same_action:
            context.scene.frame_current = int(act.frame_range[0])

        if (self.playback and not same_action and not is_playing) or (self.playback and same_action):
            bpy.ops.screen.animation_play()

        if not self.playback:
            context.window.screen = context.window.screen
            context.area.tag_redraw()

        return {"FINISHED"}


class AMP_SWAPPER_OT_make_local_action(bpy.types.Operator):
    bl_idname = "anim.amp_swapper_make_local_action"
    bl_label = "Make Action Local"
    bl_description = "Make the action local to the current blend file"

    action_name: StringProperty()

    def execute(self, context):
        action = bpy.data.actions.get(self.action_name)
        if not action:
            self.report({"WARNING"}, "Action not found")
            return {"CANCELLED"}
        if action.library:
            new_action = action.copy()
            new_action.name = action.name
            if action.use_fake_user:
                new_action.use_fake_user = True
            active = context.object
            if active:
                if not active.animation_data:
                    active.animation_data_create()
                active.animation_data.action = new_action
            self.report({"INFO"}, f"Localized action: {new_action.name}")
            return {"FINISHED"}
        self.report({"INFO"}, "Action is already local")
        return {"CANCELLED"}


class AMP_SWAPPER_OT_edit_action_name(bpy.types.Operator):
    """Edit the name of the current action"""

    bl_idname = "anim.amp_swapper_edit_action_name"
    bl_label = "Edit Action Name"
    bl_options = {"REGISTER", "UNDO"}

    action_name: StringProperty(
        name="Action Name",
        description="Name of the action",
        default="",
    )

    @classmethod
    def poll(cls, context):
        return context.object and context.object.animation_data and context.object.animation_data.action

    def invoke(self, context, event):
        action = context.object.animation_data.action
        if action:
            self.action_name = action.name
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "action_name", text="Name")

    def execute(self, context):
        action = context.object.animation_data.action
        if not action:
            self.report({"WARNING"}, "No action found")
            return {"CANCELLED"}

        if not self.action_name.strip():
            self.report({"WARNING"}, "Action name cannot be empty")
            return {"CANCELLED"}

        old_name = action.name
        action.name = self.action_name.strip()
        self.report({"INFO"}, f"Action renamed from '{old_name}' to '{action.name}'")
        return {"FINISHED"}


def draw_action_swapper(layout, context):
    active = context.object
    selected = context.selected_objects
    current = active.animation_data.action if active and active.animation_data else None

    # If NLA tweak mode is enabled disable the rest of the UI
    nla_tweak = active and active.animation_data and active.animation_data.use_tweak_mode

    container = layout.column()
    container.enabled = not nla_tweak

    if current and selected:
        draw_active_action(container, context)

        if bpy.app.version >= (4, 4):
            draw_active_action_slots(container, context)

        container.separator(factor=0.25)
        extras_box = container.box()
        draw_action_swapper_extras(extras_box, context)

        container.separator(factor=0.25)
        cp_box = container.box()
        draw_action_custom_properties(cp_box, context)

    elif current and not selected:
        layout.label(text="Action Swapper", icon="ACTION")

    else:
        row = container.row(align=True)
        row.row().operator("anim.amp_swapper_select_action_popup", text="", icon="ACTION")
        row.operator("anim.amp_swapper_new_action", text="New", icon="ADD")


def draw_active_action(layout, context):
    active = context.object
    current = active.animation_data.action if active and active.animation_data else None
    prefs = get_prefs()

    if not active:
        layout.label(text="Action Swapper", icon="ACTION")
        return

    # If NLA tweak mode is enabled disable the rest of the UI
    nla_tweak = active and active.animation_data and active.animation_data.use_tweak_mode

    if nla_tweak:
        layout.label(text="NLA in Tweak Mode", icon="NLA")
        return

    row = layout.row(align=True)
    row.operator("anim.amp_swapper_select_action_popup", text="", icon="ACTION")

    if not current:
        row.operator("anim.amp_swapper_new_action", text="New", icon="ADD")
        return

    actual_users = current.users - (1 if current.use_fake_user else 0)

    if actual_users > 1:
        split = row.split(factor=0.9, align=True)
    else:
        split = row.split(factor=1, align=True)

    if prefs.action_swapper_button:
        split.operator("anim.amp_swapper_edit_action_name", text=current.name, emboss=True)
    else:
        split.prop(current, "name", text="", emboss=True)

    if actual_users > 1:
        dup_op = split.operator("anim.amp_swapper_duplicate_action", text=str(actual_users))
        dup_op.action_name = current.name

    row.prop(current, "use_fake_user", text="", icon="FAKE_USER_OFF")

    # Duplicate or make local
    if current.library:
        loc_op = row.operator("anim.amp_swapper_make_local_action", text="", icon="LINKED")
        loc_op.action_name = current.name
    else:
        dup_op = row.operator("anim.amp_swapper_duplicate_action", text="", icon="DUPLICATE")
        dup_op.action_name = current.name

    unlink_op = row.operator("anim.amp_swapper_unlink_action", text="", icon="X")
    unlink_op.action_name = current.name
    row.separator(factor=0.25)
    del_row = row.row(align=True)
    # del_row.alert = True
    op_del = del_row.operator("anim.amp_swapper_delete_action", text="", icon="TRASH")
    op_del.action_name = current.name


def draw_active_action_slots(layout, context):

    animated_id = context.object
    adt = animated_id.animation_data
    if not adt or not adt.action:
        return

    slot_row = layout.row(align=True)

    # Only show the slot selector when a layered Action is assigned.
    if adt.action.is_action_layered:
        slot_row.context_pointer_set("animated_id", animated_id)
        slot_row.template_search(
            adt,
            "action_slot",
            adt,
            "action_suitable_slots",
            new="anim.slot_new_for_id",
            unlink="anim.slot_unassign_from_id",
        )
    slot_row.separator(factor=0.25)
    slot_row.operator("anim.merge_animation", text="", icon="IMPORT")
    slot_row.operator("anim.separate_slots", text="", icon="EXPORT")


def draw_action_swapper_extras(layout, context):
    action = context.object.animation_data.action

    title_row = layout.row(align=True)
    # Draw the toggle arrow by simply passing the toggle name.
    draw_toggle_button(title_row, "action_extras", "Arrow")

    if toggles.get("action_extras", False or None):
        title_row.label(text="Properties", **get_icon("AMP_action_extras"))
        pass
    else:
        frame_range_text = f" ({int(action.frame_start)}/{int(action.frame_end)})" if action.use_frame_range else ""
        title_row.label(text=f"Properties{frame_range_text}", **get_icon("AMP_action_extras"))
        title_row.prop(action, "use_cyclic", text="", icon="RECOVER_LAST")
        title_row.separator(factor=0.25)
        title_row.prop(action, "use_frame_range", text="", icon="PREVIEW_RANGE")

    # visibility control from toggle
    if toggles.get("action_extras", False):
        row = layout.row(align=True)
        col1 = row.column()
        col1.label(text="", icon="BLANK1")
        col2 = row.column()
        col2.prop(action, "use_cyclic")

        col2.prop(action, "use_frame_range")

        row = col2.row(align=True)
        row.active = action.use_frame_range
        row.prop(action, "frame_start", text="Start")
        row.prop(action, "frame_end", text="End")


def draw_action_custom_properties(layout, context):
    action = context.object.animation_data.action
    filter_keys = {"name", "use_fake_user", "frame_start", "frame_end", "use_frame_range", "use_cyclic"}

    def prop_sort_key(key):
        if key == "prop":
            return 0
        elif key.startswith("prop"):
            try:
                return int(key[4:])
            except Exception:
                return float("inf")
        else:
            return float("inf")

    keys = [key for key in action.keys() if key not in filter_keys]
    sorted_keys = sorted(keys, key=prop_sort_key)

    header_row = layout.row(align=True)
    draw_toggle_button(header_row, "action_custom_properties", "Arrow")

    if toggles.get("action_custom_properties", False or None):
        number_of_cps = ""
    else:
        number_of_cps = f"({len(sorted_keys)})"

    header_row.label(text=f"Custom Properties {number_of_cps}", **get_icon("AMP_action_properties"))

    header_row.operator("anim.amp_swapper_add_custom_property", text="", icon="ADD")

    if toggles.get("action_custom_properties", False):

        for key in sorted_keys:
            # row = layout.row(align=True)
            # col1 = row.column()
            # col1.label(text="", icon="BLANK1")
            col2 = layout.column()
            col2.use_property_split = True
            col2.use_property_decorate = False

            row = col2.row(align=True)
            col1 = row.column(align=True)

            row.separator(factor=0.25)

            col1.prop(action, '["{}"]'.format(key), text=key, slider=False)

            col2 = row.column(align=True)

            props_row = col2.row(align=True)
            op_edit = props_row.operator("anim.select_actionproperties_edit_wrapper", text="", icon="SETTINGS")
            op_edit.property_name = key

            props_row.separator(factor=0.25)

            op_delete = props_row.operator("anim.amp_swapper_delete_custom_property", text="", icon="X", emboss=False)
            op_delete.property_name = key


# ----------------------------------------------------------
# New Property Group for filter settings
# ----------------------------------------------------------
class AMP_SWAPPER_PG_Props(bpy.types.PropertyGroup):
    filter: BoolProperty(name="Filter", description="Enable filtering of actions", default=False, update=redraw)
    options: BoolProperty(name="Options", description="Action Swapper Options", default=False, update=redraw)
    column_width: IntProperty(
        name="Column Width",
        description="Width of each column of the picker panel, it will refresh when opening again",
        default=300,
        min=200,
        max=800,
    )
    columns: IntProperty(
        name="Columns",
        description="Number of columns in the action picker popup",
        default=1,
        min=1,
        max=4,
        update=redraw,
    )
    filter_text: StringProperty(
        name="Filter Text", description="Text to filter actions (case insensitive)", default="", update=redraw
    )


# ----------------------------------------------------------
# Panel: The Action Picker row in the 3D View sidebar
# ----------------------------------------------------------
class AMP_SWAPPER_PT_action_picker(bpy.types.Panel):
    bl_label = "Action Picker"
    bl_idname = "AMP_PT_action_picker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AniMatePro"

    def draw(self, context):
        draw_action_swapper(self.layout, context)


# ----------------------------------------------------------
# Registration
# ----------------------------------------------------------
classes = (
    AMP_SWAPPER_OT_new_action,
    AMP_SWAPPER_OT_duplicate_action,
    AMP_SWAPPER_OT_unlink_action,
    AMP_SWAPPER_OT_delete_action,
    AMP_SWAPPER_OT_select_action_popup,
    AMP_SWAPPER_OT_set_active_action,
    AMP_SWAPPER_OT_add_custom_property,
    AMP_SWAPPER_OT_custom_property_edit_wrapper,
    AMP_SWAPPER_OT_custom_property_edit_invoke,
    AMP_SWAPPER_OT_delete_custom_property,
    AMP_SWAPPER_OT_make_local_action,
    AMP_SWAPPER_OT_edit_action_name,
    AMP_SWAPPER_PG_Props,
    # AMP_SWAPPER_PT_action_picker,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.amp_anim_swapper_props = PointerProperty(type=AMP_SWAPPER_PG_Props)


def unregister():
    del bpy.types.Scene.amp_anim_swapper_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
