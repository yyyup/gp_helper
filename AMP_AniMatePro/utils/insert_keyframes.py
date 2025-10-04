def get_3d_view_items(self, context):
    items = [
        ("Available", "Available", ""),
        ("Location", "Location", ""),
        ("Rotation", "Rotation", ""),
        ("Scaling", "Scaling", ""),
        ("BUILTIN_KSI_LocRot", "Location + Rotation", ""),
        ("LocRotScale", "Location + Rotation + Scale", ""),
        ("LocRotScaleCProp", "Location + Rotation + Scale (Include Props)", ""),
        ("BUILTIN_KSI_LocScale", "Location + Scale", ""),
        ("BUILTIN_KSI_RotScale", "Rotation + Scale", ""),
        ("BUILTIN_KSI_VisualLoc", "Visual Location", ""),
        ("BUILTIN_KSI_VisualRot", "Visual Rotation", ""),
        ("BUILTIN_KSI_VisualScaling", "Visual Scaling", ""),
        ("BUILTIN_KSI_VisualLocRot", "Visual Location + Rotation", ""),
        ("BUILTIN_KSI_VisualLocRotScale", "Visual Location + Rotation + Scale", ""),
        ("BUILTIN_KSI_VisualLocScale", "Visual Location + Scale", ""),
        ("BUILTIN_KSI_VisualRotScale", "Visual Rotation + Scale", ""),
        ("BUILTIN_KSI_BendyBones", "Bendy Bones", ""),
        ("WholeCharacter", "Whole Character", ""),
        ("WholeCharacterSelected", "Whole Character (Selected Bones)", ""),
    ]
    return items


def get_graph_editor_items(self, context):
    items = [
        ("ALL", "All Channels", ""),
        ("SEL", "Selected Channels", ""),
        ("ACTIVE", "Active Channel", ""),
        ("CURSOR_ACTIVE", "Cursor Value (Active)", ""),
        ("CURSOR_SEL", "Cursor Value (Selected)", ""),
    ]
    return items


def get_timeline_dopesheet_items(self, context):
    items = [
        ("ALL", "All Channels", ""),
        ("SEL", "Selected Channels", ""),
        ("GROUP", "In Active Group", ""),
    ]
    return items
