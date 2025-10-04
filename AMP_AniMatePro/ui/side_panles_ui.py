import bpy
from .. import __package__ as base_package
from ..utils.customIcons import get_icon
from ..anim_swapper.anim_swapper import draw_action_swapper
from bpy.types import Panel, Menu
from rna_prop_ui import PropertyPanel


def get_override_context_for_template():
    # Prefer the ACTION_EDITOR for template_ID.
    valid_area = None
    for area in bpy.context.screen.areas:
        if area.type == "ACTION_EDITOR":
            valid_area = area
            break
    # If no ACTION_EDITOR found, try DOPESHEET_EDITOR.
    if valid_area is None:
        for area in bpy.context.screen.areas:
            if area.type == "DOPESHEET_EDITOR":
                valid_area = area
                break
    if valid_area:
        # Assume the last region is the 'WINDOW' region.
        valid_region = valid_area.regions[-1]
        return {
            "window": bpy.context.window,
            "screen": bpy.context.screen,
            "area": valid_area,
            "region": valid_region,
            "space_data": valid_area.spaces.active,
        }
    return None


class ActionPickerPanelBase:
    bl_label = "Action"
    bl_region_type = "UI"
    bl_category = "Action Extras"

    @staticmethod
    def _get_animated_id(context):
        st = context.space_data
        match st.mode:
            case "ACTION":
                return context.object
            case "DOPESHEET":
                return context.object
            case "SHAPEKEY":
                return getattr(context.object.data, "shape_keys", None)
            case _:
                return context.object

    @classmethod
    def _draw_action_selector(self, context, layout):
        if context.active_object is None:
            layout.label(text="No active object")
            return

        draw_action_swapper(layout, context)

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", **get_icon("AMP_action"))
        prefs = bpy.context.preferences.addons[base_package].preferences
        layout.prop(prefs, "playback_loop_only_if_cyclical", text="", icon="LOOP_BACK")

    def draw(self, context):
        layout = self.layout

        if context.active_object is None:
            layout.label(text="No active object")
            return

        if context.object:
            self._draw_action_selector(bpy.context, layout)


# class AMP_PT_action_extras(PropertyPanel, Panel):
#     bl_idname = "AMP_PT_action_extras"
#     bl_label = "Action Extras"
#     bl_region_type = "UI"

#     @classmethod
#     def poll(cls, context):
#         return context.object and context.object.animation_data and context.object.animation_data.action

#     def draw_header(self, context):
#         layout = self.layout
#         layout.label(text="", **get_icon("AMP_action_extras"))

#     def draw(self, context):
#         layout = self.layout
#         action = context.object.animation_data.action

#         layout.prop(action, "use_frame_range")

#         col = layout.column()
#         col.active = action.use_frame_range

#         row = col.row(align=True)
#         row.prop(action, "frame_start", text="Start")
#         row.prop(action, "frame_end", text="End")

#         col.prop(action, "use_cyclic")


# class AMP_PT_action_custom_properties(PropertyPanel, Panel):
#     bl_idname = "AMP_PT_action_custom_properties"
#     bl_label = "Action Custom Properties"
#     bl_region_type = "UI"
#     _context_path = "object.animation_data.action"
#     _property_type = bpy.types.Action

#     def draw_header(self, context):
#         layout = self.layout
#         layout.label(text="", **get_icon("AMP_action_properties"))

#     @classmethod
#     def poll(cls, context):
#         return context.object and context.object.animation_data and context.object.animation_data.action


# -------------------------------------------------------------------


class AMP_PT_action_picker_dope(ActionPickerPanelBase, Panel):
    bl_idname = "AMP_PT_action_picker_dope"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_parent_id = "AMP_PT_AniMateProDope"
    bl_options = {"DEFAULT_CLOSED"}


class AMP_PT_action_picker_graph(ActionPickerPanelBase, Panel):
    bl_idname = "AMP_PT_action_picker_graph"
    bl_space_type = "GRAPH_EDITOR"
    bl_parent_id = "AMP_PT_AniMateProGraph"
    bl_options = {"DEFAULT_CLOSED"}


class AMP_PT_action_picker_view(ActionPickerPanelBase, Panel):
    bl_idname = "AMP_PT_action_picker_view"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "AMP_PT_AniMateProView"
    bl_options = {"DEFAULT_CLOSED"}


# -------------------------------------------------------------------


# class AMP_PT_action_custom_properties_view(AMP_PT_action_custom_properties):
#     bl_idname = "AMP_PT_action_custom_properties_view"
#     bl_parent_id = "AMP_PT_action_picker_view"
#     bl_space_type = "VIEW_3D"


# class AMP_PT_action_custom_properties_dope(AMP_PT_action_custom_properties):
#     bl_idname = "AMP_PT_action_custom_properties_dope"
#     bl_parent_id = "AMP_PT_action_picker_dope"
#     bl_space_type = "DOPESHEET_EDITOR"


# class AMP_PT_action_custom_properties_graph(AMP_PT_action_custom_properties):
#     bl_idname = "AMP_PT_action_custom_properties_graph"
#     bl_parent_id = "AMP_PT_action_picker_graph"
#     bl_space_type = "GRAPH_EDITOR"


# -------------------------------------------------------------------


# class AMP_PT_action_extras_view(AMP_PT_action_extras):
#     bl_idname = "AMP_PT_action_extras_view"
#     bl_parent_id = "AMP_PT_action_picker_view"
#     bl_space_type = "VIEW_3D"


# class AMP_PT_action_extras_dope(AMP_PT_action_extras):
#     bl_idname = "AMP_PT_action_extras_dope"
#     bl_parent_id = "AMP_PT_action_picker_dope"
#     bl_space_type = "DOPESHEET_EDITOR"


# class AMP_PT_action_extras_graph(AMP_PT_action_extras):
#     bl_idname = "AMP_PT_action_extras_graph"
#     bl_parent_id = "AMP_PT_action_picker_graph"
#     bl_space_type = "GRAPH_EDITOR"


# -------------------------------------------------------------------


classes = (
    AMP_PT_action_picker_dope,
    AMP_PT_action_picker_graph,
    AMP_PT_action_picker_view,
    #     AMP_PT_action_extras_view,
    #     AMP_PT_action_extras_dope,
    #     AMP_PT_action_extras_graph,
    #     AMP_PT_action_custom_properties_view,
    #     AMP_PT_action_custom_properties_dope,
    #     AMP_PT_action_custom_properties_graph,
)


# def register():
#     for cls in classes:
#         try:
#             bpy.utils.register_class(cls)
#         except:
#             pass


# def unregister():
#     for cls in reversed(classes):
#         try:
#             bpy.utils.unregister_class(cls)
#         except AttributeError:
#             pass
