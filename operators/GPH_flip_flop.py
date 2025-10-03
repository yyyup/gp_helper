import bpy
from bpy.types import Operator

class GPH_OT_flip_flop_toggle(Operator):
    """Toggle between current frame and target frame"""
    bl_idname = "gph.flip_flop_toggle"
    bl_label = "Flip/Flop"
    bl_description = "Toggle between current frame and comparison frame (hotkey recommended: Alt+F)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.gph_flip_flop_props
        current_frame = scene.frame_current

        if props.is_flopped:
            # We're currently flopped, go back to original
            scene.frame_set(props.original_frame)
            props.is_flopped = False
        else:
            # We're at original, flip to target
            target_frame = self.get_target_frame(context, current_frame)

            if target_frame is None:
                self.report({'WARNING'}, "No valid frame to flip to")
                return {'CANCELLED'}

            if target_frame == current_frame:
                self.report({'WARNING'}, "Target frame is same as current frame")
                return {'CANCELLED'}

            # Store original and flip
            props.original_frame = current_frame
            scene.frame_set(target_frame)
            props.is_flopped = True

        # Force viewport update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}

    def get_target_frame(self, context, current_frame):
        """Calculate target frame based on flip mode"""
        props = context.scene.gph_flip_flop_props

        if props.flip_mode == 'STORED':
            return props.stored_frame

        elif props.flip_mode == 'PREVIOUS':
            return max(1, current_frame - 1)

        elif props.flip_mode == 'NEXT':
            return current_frame + 1

        elif props.flip_mode == 'PREVIOUS_KEY':
            return self.find_previous_keyframe(context, current_frame)

        elif props.flip_mode == 'NEXT_KEY':
            return self.find_next_keyframe(context, current_frame)

        return None

    def find_previous_keyframe(self, context, current_frame):
        """Find previous keyframe in active layer"""
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return None

        gp_data = obj.data
        layer = gp_data.layers.active

        if not layer:
            return None

        # Get all keyframes before current
        keyframes = []
        for frame in layer.frames:
            if frame.frame_number < current_frame:
                keyframes.append(frame.frame_number)

        if keyframes:
            return max(keyframes)  # Closest one before current

        return None

    def find_next_keyframe(self, context, current_frame):
        """Find next keyframe in active layer"""
        obj = context.active_object
        if not obj or obj.type != 'GREASEPENCIL':
            return None

        gp_data = obj.data
        layer = gp_data.layers.active

        if not layer:
            return None

        # Get all keyframes after current
        keyframes = []
        for frame in layer.frames:
            if frame.frame_number > current_frame:
                keyframes.append(frame.frame_number)

        if keyframes:
            return min(keyframes)  # Closest one after current

        return None


class GPH_OT_set_flip_frame(Operator):
    """Set current frame as the flip target"""
    bl_idname = "gph.set_flip_frame"
    bl_label = "Set Flip Frame"
    bl_description = "Set current frame as the stored flip target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_flip_flop_props
        current_frame = context.scene.frame_current

        props.stored_frame = current_frame
        props.flip_mode = 'STORED'

        self.report({'INFO'}, f"Flip frame set to {current_frame}")
        return {'FINISHED'}


class GPH_OT_flip_to_previous(Operator):
    """Quick flip to previous frame"""
    bl_idname = "gph.flip_to_previous"
    bl_label = "Flip to Previous"
    bl_description = "Flip to previous frame (frame - 1)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_flip_flop_props
        props.flip_mode = 'PREVIOUS'
        return bpy.ops.gph.flip_flop_toggle()


class GPH_OT_flip_to_next(Operator):
    """Quick flip to next frame"""
    bl_idname = "gph.flip_to_next"
    bl_label = "Flip to Next"
    bl_description = "Flip to next frame (frame + 1)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_flip_flop_props
        props.flip_mode = 'NEXT'
        return bpy.ops.gph.flip_flop_toggle()


class GPH_OT_reset_flip_flop(Operator):
    """Reset flip/flop state"""
    bl_idname = "gph.reset_flip_flop"
    bl_label = "Reset Flip/Flop"
    bl_description = "Reset flip/flop to normal state"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_flip_flop_props

        if props.is_flopped:
            context.scene.frame_set(props.original_frame)

        props.is_flopped = False

        return {'FINISHED'}
