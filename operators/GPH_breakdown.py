import bpy
from bpy.types import Operator
import math

class GPH_OT_add_breakdown(Operator):
    """Add breakdown frame between selected keyframes"""
    bl_idname = "gph.add_breakdown"
    bl_label = "Add Breakdown"
    bl_description = "Create breakdown frame(s) between selected keyframes at specified position"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Check if operator can run"""
        obj = context.active_object
        return obj and obj.type == 'GREASEPENCIL'

    def execute(self, context):
        props = context.scene.gph_breakdown_props
        obj = context.active_object
        gp_data = obj.data

        # Get selected frames per layer
        selected_frames = self.get_selected_frames_per_layer(context)

        if not selected_frames:
            self.report({'ERROR'}, "No keyframes selected. Select at least 2 keyframes.")
            return {'CANCELLED'}

        total_breakdowns = 0
        layers_processed = 0

        # Process each layer
        for layer, frames in selected_frames.items():
            if len(frames) < 2:
                continue

            # Process each pair of consecutive frames
            pairs = []
            for i in range(len(frames) - 1):
                first_frame = frames[i]
                last_frame = frames[i + 1]

                # Calculate breakdown position
                if props.use_custom_offset:
                    breakdown_frame = first_frame + props.custom_offset
                    # Ensure it's between first and last
                    if breakdown_frame >= last_frame:
                        continue
                else:
                    frame_range = last_frame - first_frame
                    breakdown_frame = first_frame + int(frame_range * props.position)

                # Skip if breakdown is same as first or last
                if breakdown_frame == first_frame or breakdown_frame == last_frame:
                    continue

                pairs.append((first_frame, breakdown_frame, last_frame))

            if not pairs:
                continue

            # If shift_subsequent, we need to shift frames forward first
            if props.shift_subsequent:
                self.shift_frames_forward(layer, pairs)

            # Create breakdowns
            for first_frame, breakdown_frame, last_frame in pairs:
                success = self.create_breakdown(
                    layer,
                    first_frame,
                    breakdown_frame,
                    last_frame,
                    props.copy_mode
                )

                if success:
                    total_breakdowns += 1

            layers_processed += 1

        if total_breakdowns > 0:
            self.report({'INFO'},
                       f"Created {total_breakdowns} breakdown(s) on {layers_processed} layer(s)")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No breakdowns created")
            return {'CANCELLED'}

    def get_selected_frames_per_layer(self, context):
        """Get dictionary of selected frames per layer"""
        obj = context.active_object
        props = context.scene.gph_breakdown_props
        selected = {}

        for layer in obj.data.layers:
            # Skip locked/hidden unless apply_to_all_layers
            if not props.apply_to_all_layers:
                if layer.lock or layer.hide:
                    continue

            layer_frames = []
            for frame in layer.frames:
                if hasattr(frame, 'select') and frame.select:
                    layer_frames.append(frame.frame_number)

            if len(layer_frames) >= 2:
                selected[layer] = sorted(layer_frames)

        return selected

    def create_breakdown(self, layer, first_frame, breakdown_frame, last_frame, copy_mode):
        """Create a breakdown frame"""
        try:
            # Check if breakdown frame already exists
            existing = None
            for frame in layer.frames:
                if frame.frame_number == breakdown_frame:
                    existing = frame
                    break

            if existing:
                print(f"Frame {breakdown_frame} already exists, skipping")
                return False

            # Create breakdown based on copy mode
            if copy_mode == 'BLANK':
                # Create empty frame
                layer.frames.new(breakdown_frame)

            elif copy_mode == 'FIRST':
                # Copy first frame
                layer.frames.copy(layer.frames[first_frame], breakdown_frame)

            elif copy_mode == 'LAST':
                # Copy last frame
                layer.frames.copy(layer.frames[last_frame], breakdown_frame)

            elif copy_mode == 'INTERPOLATE':
                # Experimental: Try to interpolate
                # For now, just copy first frame (interpolation is complex)
                layer.frames.copy(layer.frames[first_frame], breakdown_frame)
                print("Interpolate mode: Currently copies first frame (interpolation not yet implemented)")

            return True

        except Exception as e:
            print(f"Error creating breakdown at frame {breakdown_frame}: {e}")
            return False

    def shift_frames_forward(self, layer, pairs):
        """Shift frames forward to make room for breakdowns"""
        # Get all breakdown positions
        breakdown_positions = [bd for _, bd, _ in pairs]

        # Get all frames that need shifting (after any breakdown)
        min_breakdown = min(breakdown_positions)
        frames_to_shift = []

        for frame in layer.frames:
            if frame.frame_number > min_breakdown:
                frames_to_shift.append(frame.frame_number)

        # Sort in reverse to avoid collisions
        frames_to_shift.sort(reverse=True)

        # Shift each frame forward by number of breakdowns before it
        for frame_num in frames_to_shift:
            breakdowns_before = sum(1 for bd in breakdown_positions if bd < frame_num)
            new_position = frame_num + breakdowns_before

            # Use safe copy method
            temp_offset = 100000
            layer.frames.copy(layer.frames[frame_num], frame_num + temp_offset)
            layer.frames.remove(layer.frames[frame_num])
            layer.frames.copy(layer.frames[frame_num + temp_offset], new_position)
            layer.frames.remove(layer.frames[frame_num + temp_offset])


class GPH_OT_breakdown_preset(Operator):
    """Add breakdown at preset position"""
    bl_idname = "gph.breakdown_preset"
    bl_label = "Breakdown Preset"
    bl_description = "Quick breakdown at preset position"
    bl_options = {'REGISTER', 'UNDO'}

    position: bpy.props.FloatProperty(default=0.5)

    def execute(self, context):
        props = context.scene.gph_breakdown_props

        # Temporarily set position
        old_position = props.position
        old_use_custom = props.use_custom_offset

        props.position = self.position
        props.use_custom_offset = False

        # Execute main breakdown operator
        result = bpy.ops.gph.add_breakdown()

        # Restore settings
        props.position = old_position
        props.use_custom_offset = old_use_custom

        return result


class GPH_OT_breakdown_favor_first(Operator):
    """Add breakdown favoring first keyframe (25%)"""
    bl_idname = "gph.breakdown_favor_first"
    bl_label = "Favor First (25%)"
    bl_description = "Create breakdown at 25% position (closer to first keyframe)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.gph.breakdown_preset(position=0.25)
        return {'FINISHED'}


class GPH_OT_breakdown_middle(Operator):
    """Add breakdown in middle (50%)"""
    bl_idname = "gph.breakdown_middle"
    bl_label = "Middle (50%)"
    bl_description = "Create breakdown at 50% position (exactly between keyframes)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.gph.breakdown_preset(position=0.5)
        return {'FINISHED'}


class GPH_OT_breakdown_favor_last(Operator):
    """Add breakdown favoring last keyframe (75%)"""
    bl_idname = "gph.breakdown_favor_last"
    bl_label = "Favor Last (75%)"
    bl_description = "Create breakdown at 75% position (closer to last keyframe)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.gph.breakdown_preset(position=0.75)
        return {'FINISHED'}
