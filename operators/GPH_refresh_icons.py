"""
GP Helper - Refresh Icons Operator
Force reload custom icons without disabling/enabling addon
"""

import bpy
from ..utils.icon_loader import load_icons


class GPH_OT_refresh_icons(bpy.types.Operator):
    """Force reload custom icons (Shift-click to reload icons)"""
    bl_idname = "gph.refresh_icons"
    bl_label = "Refresh Icons"
    bl_description = "Shift-click to reload custom icons"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        # Only reload icons if shift is held
        if event.shift:
            load_icons()
            self.report({'INFO'}, "GP Helper icons reloaded")
        return {'FINISHED'}

    def execute(self, context):
        # Direct execution (no event) - just reload
        load_icons()
        self.report({'INFO'}, "GP Helper icons reloaded")
        return {'FINISHED'}
