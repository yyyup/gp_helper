import bpy


def motion_path_options(layout, props):
    box = layout.box()
    box.use_property_split = True
    box.use_property_decorate = False
    box.label(text="Motion Paths Options")
    col = box.column(align=True)

    if bpy.app.version >= (4, 2, 0):
        col.prop(props, "use_camera_space_bake")

    col.prop(props, "lines")
    col.prop(props, "line_thickness", text="Thickness")

    if bpy.app.version >= (4, 2, 0):
        col.prop(props, "use_custom_color")
        sub = col.column(align=True)
        sub.enabled = props.use_custom_color
        sub.prop(props, "color_before", text="Before")
        sub.prop(props, "color_after", text="After")