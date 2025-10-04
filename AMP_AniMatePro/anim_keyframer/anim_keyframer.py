import bpy
from .. import utils
from ..anim_euler.anim_euler import AnimEulerFilterButton, AnimEulerGimbalButton
from ..anim_curves.anim_curves import AnimResetKeyframeValueButtons


class AMP_PT_AnimKeyframerPopover(bpy.types.Panel):
    bl_label = "Anim Keyframer"
    bl_idname = "AMP_PT_AnimKeyframerPopover"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_context = ""
    bl_order = 0
    bl_options = {"HIDE_HEADER"}
    bl_ui_units_x = 10

    def draw(self, context):
        layout = self.layout
        draw_keyframer_panel(self, context)


class AMP_PT_AnimKeyframerGraph(bpy.types.Panel):
    bl_label = "Anim Keyframer"
    bl_idname = "AMP_PT_AnimKeyframerGraph"
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation"
    bl_parent_id = "AMP_PT_AniMateProGraph"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon_value=utils.customIcons.get_icon_id("AMP_keyframer"))  # icon="KEYTYPE_KEYFRAME_VEC")

    def draw(self, context):
        layout = self.layout
        draw_keyframer_panel(self, context)


def draw_keyframer_panel(self, context):
    layout = self.layout

    box = layout.box()
    box.label(text="Smooth")

    row = box.row(align=True)
    row.separator()

    col = row.column(align=True)
    row = col.row()

    row.operator("graph.gaussian_smooth", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.smooth", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.butterworth_smooth", emboss=True, icon="BLANK1")

    col.separator()

    box = layout.box()
    box.label(text="Blend")

    row = box.row(align=True)
    row.separator()

    col = row.column(align=True)

    row = col.row()

    row.operator("graph.breakdown", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.blend_to_neighbor", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.blend_to_default", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.ease", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.blend_offset", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.blend_to_ease", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.match_slope", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.push_pull", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.shear", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.scale_average", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.scale_from_neighbor", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.time_offset", emboss=True, icon="BLANK1")

    col.separator()

    box = layout.box()
    box.label(text="Cleanup")

    row = box.row(align=True)
    row.separator()

    col = row.column(align=True)
    row = col.row()

    row.operator("graph.clean", text="Clean Keyframes", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.clean", text="Clean Channels", emboss=True, icon="BLANK1").channels = True
    row = col.row()

    row.operator("graph.decimate", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("graph.bake_keys", emboss=True, icon="BLANK1")
    row = col.row()

    row.operator("anim.channels_bake", emboss=True, icon="BLANK1")
    row = col.row()

    # row.operator(
    #     "anim.amp_cleanup_keyframes_from_locked_transforms",
    #     text="Smart Cleanup (locked trans.)",
    #     icon_value=utils.customIcons.get_icon_id("AMP_curves_cleanup"),
    #     emboss=True,
    # )
    
    AnimResetKeyframeValueButtons(col, context)

    box = layout.box()

    box.label(text="Rotation")

    row = box.row(align=True)
    row.separator()

    col = row.column(align=True)
    row = col.row()

    row.operator(
        "graph.euler_filter",
        text="Euler Filter (action)",
        icon="BLANK1",
        emboss=True,
    )
    # row = col.row()
    #
    # row.operator(
    #     "anim.amp_euler_filter",
    #     text="Euler Filter (local)",
    #     icon_value=utils.customIcons.get_icon_id("AMP_curves_euler"),
    #     emboss=True,
    # )
    # row = col.row()
    #

    # row.operator(
    #     "anim.amp_euler_rotation_recommendations",
    #     text="Euler (Gimbal un-lock)",
    #     icon_value=utils.customIcons.get_icon_id("AMP_curves_gimbal"),
    #     emboss=True,
    # )


# class AMP_PT_AnimKeyPoserDope(bpy.types.Panel):
#     bl_label = "Anim KeyPoser"
#     bl_idname = "AMP_PT_AnimKeyPoserDope"
#     bl_space_type = "DOPESHEET_EDITOR"
#     bl_region_type = "UI"
#     bl_category = "Animation"
#     bl_parent_id = "AMP_PT_TimelineToolsDope"
#     bl_options = {"DEFAULT_CLOSED"}

#     def draw_header(self, context):
#         layout = self.layout
#         layout.label(text="", icon="ARMATURE_DATA")

#     def draw(self, context):
#         layout = self.layout
#         draw_anim_keyposer_panel(self, context)


# class AMP_PT_AnimKeyPoserNLA(bpy.types.Panel):
#     bl_label = "Anim KeyPoser"
#     bl_idname = "AMP_PT_AnimKeyPoserNLA"
#     bl_space_type = "NLA_EDITOR"
#     bl_region_type = "UI"
#     bl_category = "Animation"
#     bl_parent_id = "AMP_PT_TimelineToolsNLA"
#     bl_options = {"DEFAULT_CLOSED"}

#     def draw_header(self, context):
#         layout = self.layout
#         layout.label(text="", icon="ARMATURE_DATA")

#     def draw(self, context):
#         layout = self.layout
#         draw_anim_keyposer_panel(self, context)

classes = [
    AMP_PT_AnimKeyframerGraph,
    AMP_PT_AnimKeyframerPopover,
]


def register_properties():
    pass


def unregister_properties():
    pass


def register():
    register_properties()
    # try:
    #     for cls in classes:
    #         bpy.utils.register_class(cls)
    # except:
    #     utils.dutils.dprint(f"{cls} already registered, skipping...")


def unregister():

    # try:
    #     for cls in reversed(classes):
    #         bpy.utils.unregister_class(cls)
    # except:
    #     utils.dutils.dprint(f"{cls} not found, skipping...")
    unregister_properties()


if __name__ == "__main__":
    register()
