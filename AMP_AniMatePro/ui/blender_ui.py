###########
## ui.py ##
###########

import bpy
import bpy.utils.previews
from ..anim_curves.anim_curves import AMP_OT_isolate_selected_fcurves
from .. import utils

from .. import __package__ as base_package
from rna_prop_ui import PropertyPanel
import bl_ui

# ** from bl_ui.space_dopesheet import dopesheet_filter
# ** from bl_ui.space_graph import GRAPH_HT_header, GRAPH_MT_editor_menus
# ** from bl_ui.space_dopesheet import DOPESHEET_HT_editor_buttons


# Blender Native UI


class GRAPH_HT_header(bpy.types.Header):
    bl_space_type = "GRAPH_EDITOR"

    def draw(self, context):
        layout = self.layout
        tool_settings = context.tool_settings

        st = context.space_data

        layout.template_header()

        # Now a exposed as a sub-space type
        # layout.prop(st, "mode", text="")

        bl_ui.space_graph.GRAPH_MT_editor_menus.draw_collapsible(context, layout)

        # row = layout.row(align=True)
        # row.prop(st, "use_normalization", icon="NORMALIZE_FCURVES", text="", toggle=True)
        # sub = row.row(align=True)
        # sub.active = st.use_normalization
        # sub.prop(st, "use_auto_normalization", icon="FILE_REFRESH", text="", toggle=True)

        # layout.separator_spacer()

        bl_ui.space_dopesheet.dopesheet_filter(layout, context)

        row = layout.row(align=True)
        if st.has_ghost_curves:
            row.operator("graph.ghost_curves_clear", text="", icon="X")
        else:
            row.operator("graph.ghost_curves_create", text="", icon="FCURVE_SNAPSHOT")

        layout.popover(
            panel="GRAPH_PT_filters",
            text="",
            icon="FILTER",
        )

        layout.prop(st, "pivot_point", icon_only=True)

        row = layout.row(align=True)
        row.prop(tool_settings, "use_snap_anim", text="")
        sub = row.row(align=True)
        sub.popover(
            panel="GRAPH_PT_snapping",
            text="",
        )

        row = layout.row(align=True)
        row.prop(tool_settings, "use_proportional_fcurve", text="", icon_only=True)
        sub = row.row(align=True)
        sub.active = tool_settings.use_proportional_fcurve
        sub.prop_with_popover(
            tool_settings,
            "proportional_edit_falloff",
            text="",
            icon_only=True,
            panel="GRAPH_PT_proportional_edit",
        )


# class GRAPH_MT_editor_menus(bpy.types.Menu):
#     bl_idname = "GRAPH_MT_editor_menus"
#     bl_label = ""

#     def draw(self, context):
#         st = context.space_data
#         layout = self.layout
#         layout.menu("GRAPH_MT_view")
#         layout.menu("GRAPH_MT_select")
#         if st.mode != "DRIVERS" and st.show_markers:
#             layout.menu("GRAPH_MT_marker")
#         layout.menu("GRAPH_MT_channel")
#         layout.menu("GRAPH_MT_key")


class DOPESHEET_HT_header(bpy.types.Header):
    bl_space_type = "DOPESHEET_EDITOR"

    def draw(self, context):
        layout = self.layout

        st = context.space_data

        layout.template_header()

        if st.mode == "TIMELINE":
            from bl_ui.space_time import (
                TIME_MT_editor_menus,
                TIME_HT_editor_buttons,
            )

            TIME_MT_editor_menus.draw_collapsible(context, layout)
            TIME_HT_editor_buttons.draw_header(context, layout)
        else:
            layout.prop(st, "ui_mode", text="")

            DOPESHEET_MT_editor_menus.draw_collapsible(context, layout)
            DOPESHEET_HT_editor_buttons.draw_header(context, layout)


class DOPESHEET_MT_editor_menus(bpy.types.Menu):
    bl_idname = "DOPESHEET_MT_editor_menus"
    bl_label = ""

    def draw(self, context):
        layout = self.layout
        st = context.space_data

        layout.menu("DOPESHEET_MT_view")
        layout.menu("DOPESHEET_MT_select")
        if st.show_markers:
            layout.menu("DOPESHEET_MT_marker")

        if st.mode == "DOPESHEET" or (st.mode == "ACTION" and st.action is not None):
            layout.menu("DOPESHEET_MT_channel")
        elif st.mode == "GPENCIL":
            layout.menu("DOPESHEET_MT_gpencil_channel")

        layout.menu("DOPESHEET_MT_key")

        if st.mode in {"ACTION", "SHAPEKEY"} and st.action is not None:
            if context.preferences.experimental.use_animation_baklava:
                layout.menu("DOPESHEET_MT_action")


class DOPESHEET_HT_editor_buttons(bpy.types.Header):

    @classmethod
    def draw_header(cls, context, layout):
        st = context.space_data
        tool_settings = context.tool_settings

        if st.mode in {"ACTION", "SHAPEKEY"}:
            # TODO: These buttons need some tidying up -
            # Probably by using a popover, and bypassing the template_id() here
            row = layout.row(align=True)
            row.operator("action.layer_prev", text="", icon="TRIA_DOWN")
            row.operator("action.layer_next", text="", icon="TRIA_UP")

            row = layout.row(align=True)
            row.operator("action.push_down", text="Push Down", icon="NLA_PUSHDOWN")
            row.operator("action.stash", text="Stash", icon="FREEZE")

            if context.object:
                layout.separator_spacer()
                cls._draw_action_selector(context, layout)

        # Layer management
        if st.mode == "GPENCIL":
            ob = context.active_object

            enable_but = ob is not None and ob.type == "GREASEPENCIL"

            row = layout.row(align=True)
            row.enabled = enable_but
            row.operator("grease_pencil.layer_add", icon="ADD", text="")
            row.operator("grease_pencil.layer_remove", icon="REMOVE", text="")
            row.menu("GREASE_PENCIL_MT_grease_pencil_add_layer_extra", icon="DOWNARROW_HLT", text="")

            row = layout.row(align=True)
            row.enabled = enable_but
            row.operator("anim.channels_move", icon="TRIA_UP", text="").direction = "UP"
            row.operator("anim.channels_move", icon="TRIA_DOWN", text="").direction = "DOWN"

            row = layout.row(align=True)
            row.enabled = enable_but
            row.operator("grease_pencil.layer_isolate", icon="RESTRICT_VIEW_ON", text="").affect_visibility = True
            row.operator("grease_pencil.layer_isolate", icon="LOCKED", text="").affect_visibility = False

        layout.separator_spacer()

        if st.mode == "DOPESHEET":
            bl_ui.space_dopesheet.dopesheet_filter(layout, context)
        elif st.mode == "ACTION":
            bl_ui.space_dopesheet.dopesheet_filter(layout, context)
        elif st.mode == "GPENCIL":
            row = layout.row(align=True)
            row.prop(st.dopesheet, "show_only_selected", text="")
            row.prop(st.dopesheet, "show_hidden", text="")

        layout.popover(
            panel="DOPESHEET_PT_filters",
            text="",
            icon="FILTER",
        )

        # Grease Pencil mode doesn't need snapping, as it's frame-aligned only
        if st.mode != "GPENCIL":
            row = layout.row(align=True)
            row.prop(tool_settings, "use_snap_anim", text="")
            sub = row.row(align=True)
            sub.popover(
                panel="DOPESHEET_PT_snapping",
                text="",
            )

        row = layout.row(align=True)
        row.prop(tool_settings, "use_proportional_action", text="", icon_only=True)
        sub = row.row(align=True)
        sub.active = tool_settings.use_proportional_action
        sub.prop_with_popover(
            tool_settings,
            "proportional_edit_falloff",
            text="",
            icon_only=True,
            panel="DOPESHEET_PT_proportional_edit",
        )

    @classmethod
    def _draw_action_selector(cls, context, layout):
        animated_id = cls._get_animated_id(context)
        if not animated_id:
            return

        row = layout.row()
        if animated_id.animation_data and animated_id.animation_data.use_tweak_mode:
            row.enabled = False

        row.template_action(animated_id, new="action.new", unlink="action.unlink")

        if not context.preferences.experimental.use_animation_baklava:
            return

        adt = animated_id and animated_id.animation_data
        if not adt or not adt.action or not adt.action.is_action_layered:
            return

        # Store the animated ID in the context, so that the new/unlink operators
        # have access to it.
        row.context_pointer_set("animated_id", animated_id)
        row.template_search(
            adt,
            "action_slot",
            adt,
            "action_slots",
            new="anim.slot_new_for_id",
            unlink="anim.slot_unassign_from_id",
        )

    @staticmethod
    def _get_animated_id(context):
        st = context.space_data
        match st.mode:
            case "ACTION":
                return context.object
            case "SHAPEKEY":
                return getattr(context.object.data, "shape_keys", None)
            case _:
                print("Dope Sheet mode '{:s}' not expected to have an Action selector".format(st.mode))
                return context.object


amp_graph_classes = (
    GRAPH_HT_header,
    # GRAPH_MT_editor_menus,
)

bl_graph_classes = (
    bl_ui.space_graph.GRAPH_HT_header,
    # bl_ui.space_graph.GRAPH_MT_editor_menus,
)

amp_dope_classes = (
    # DOPESHEET_MT_editor_menus,
    DOPESHEET_HT_header,
)


bl_dope_classes = (
    # bl_ui.space_dopesheet.DOPESHEET_MT_editor_menus,
    bl_ui.space_dopesheet.DOPESHEET_HT_header,
)


# def register_blender_dope_top_right_bar():


def toggle_amp_graph_top_right_bar(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.toggle_amp_graph_top_right_bar_active:
        try:
            for cls in bl_graph_classes:
                bpy.utils.unregister_class(cls)
            for cls in amp_graph_classes:
                bpy.utils.register_class(cls)
        except RuntimeError or AttributeError:
            pass
    else:
        try:
            for cls in amp_graph_classes:
                bpy.utils.unregister_class(cls)
            for cls in bl_graph_classes:
                bpy.utils.register_class(cls)
        except RuntimeError or AttributeError:
            pass


def toggle_blender_dope_top_right_bar(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    if prefs.toggle_blender_dope_top_right_bar_active:
        try:
            for cls in bl_dope_classes:
                bpy.utils.unregister_class(cls)
            for cls in amp_dope_classes:
                bpy.utils.register_class(cls)
        except RuntimeError or AttributeError:
            pass

    else:
        try:
            for cls in amp_dope_classes:
                bpy.utils.unregister_class(cls)
            for cls in bl_dope_classes:
                bpy.utils.register_class(cls)
        except RuntimeError or AttributeError:
            pass


def register():
    # Register native UI replacements
    # toggle_amp_graph_top_right_bar(None, bpy.context)
    # toggle_blender_dope_top_right_bar(None, bpy.context)

    # Register top panels in their initial positions
    from .addon_ui_default_top_panels import reload_top_bars_position

    reload_top_bars_position(None, bpy.context)


def unregister():
    # Unregister all top panels
    from .addon_ui_default_top_panels import _unregister_all_top_panels

    _unregister_all_top_panels()
