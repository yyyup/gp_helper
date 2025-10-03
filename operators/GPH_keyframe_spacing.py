import bpy
from bpy.types import Operator

class GPH_OT_keyframe_spacing(Operator):
    """Evenly space selected GP keyframes with specified number of frames between them"""
    bl_idname = "gph.keyframe_spacing"
    bl_label = "Space Keyframes Evenly"
    bl_options = {'REGISTER', 'UNDO'}

    spacing_frames: bpy.props.IntProperty(
        name="Frame Interval",
        description="Frame interval between keyframes (e.g., 10 = frames at 0, 10, 20, 30...)",
        default=10,
        min=1,
        max=100
    )
    
    ripple_edit: bpy.props.BoolProperty(
        name="Ripple Edit",
        description="Move subsequent keyframes proportionally to preserve all frames",
        default=True
    )

    def execute(self, context):
        if context.area.type != 'DOPESHEET_EDITOR':
            self.report({'ERROR'}, "This operator only works in the Dope Sheet editor.")
            return {'CANCELLED'}

        # Get selected keyframes per layer
        layers_data = self.get_selected_gp_keyframes_per_layer(context)

        if not layers_data:
            self.report({'ERROR'}, "At least 2 GP keyframes must be selected on at least one layer.")
            return {'CANCELLED'}

        total_layers_processed = 0

        # Process each layer independently
        for layer, selected_frames in layers_data.items():
            if len(selected_frames) < 2:
                continue

            selected_frames.sort()
            
            # Get ALL frames on this layer before any operations
            all_frames = sorted(self.get_all_gp_keyframes_for_layer(context, layer))
            
            print("\n=== KEYFRAME SPACING (NON-DESTRUCTIVE) ===")
            print(f"Layer: {layer.name if hasattr(layer, 'name') else 'Unknown'}")
            print(f"Total frames BEFORE: {len(all_frames)}")
            print(f"All frames: {all_frames}")
            print(f"Selected frames: {selected_frames}")
            
            # Calculate new positions for selected frames
            start_frame = selected_frames[0]
            spacing = self.spacing_frames
            
            selected_new_positions = {}
            for i, old_frame in enumerate(selected_frames):
                new_frame = start_frame + (i * spacing)
                selected_new_positions[old_frame] = new_frame
            
            print(f"Selected frames new positions: {selected_new_positions}")
            
            # Calculate new positions for ALL frames (selected + unselected)
            all_new_positions = {}
            
            first_selected_orig = selected_frames[0]
            last_selected_orig = selected_frames[-1]
            last_selected_new = selected_new_positions[last_selected_orig]
            
            for frame_num in all_frames:
                if frame_num in selected_new_positions:
                    # This is a selected frame - use calculated position
                    all_new_positions[frame_num] = selected_new_positions[frame_num]
                elif frame_num < first_selected_orig:
                    # Before selection - don't move
                    all_new_positions[frame_num] = frame_num
                elif frame_num > last_selected_orig:
                    # After selection - shift by how much last selected frame moved
                    shift = last_selected_new - last_selected_orig
                    all_new_positions[frame_num] = frame_num + shift
                else:
                    # Between selected frames - interpolate proportionally
                    # Find surrounding selected frames
                    prev_selected = first_selected_orig
                    next_selected = last_selected_orig
                    
                    for i in range(len(selected_frames) - 1):
                        if selected_frames[i] < frame_num < selected_frames[i + 1]:
                            prev_selected = selected_frames[i]
                            next_selected = selected_frames[i + 1]
                            break
                    
                    # Calculate proportional position
                    prev_selected_new = selected_new_positions[prev_selected]
                    next_selected_new = selected_new_positions[next_selected]
                    
                    original_range = next_selected - prev_selected
                    new_range = next_selected_new - prev_selected_new
                    proportion = (frame_num - prev_selected) / original_range
                    
                    new_pos = prev_selected_new + (proportion * new_range)
                    all_new_positions[frame_num] = round(new_pos)
            
            print(f"\nAll frames repositioning plan:")
            for old, new in sorted(all_new_positions.items())[:10]:
                if old != new:
                    print(f"  {old} -> {new}")
            if len(all_new_positions) > 10:
                print(f"  ... and {len(all_new_positions) - 10} more")
            
            # Now move all frames using a safe three-pass method
            # This preserves ALL frames - no deletions
            temp_offset = 100000
            
            # Pass 1: Copy all frames to temporary positions
            print("\n--- PASS 1: Copying all frames to temp ---")
            for old_pos in all_frames:
                temp_pos = old_pos + temp_offset
                layer.frames.copy(old_pos, temp_pos)
            
            # Pass 2: Delete all original frames
            print("\n--- PASS 2: Removing original frames ---")
            for old_pos in all_frames:
                layer.frames.remove(old_pos)
            
            # Pass 3: Move from temp to final positions
            print("\n--- PASS 3: Moving to final positions ---")
            for old_pos, new_pos in all_new_positions.items():
                temp_pos = old_pos + temp_offset
                
                # Check for collision at destination
                existing = None
                for frame in layer.frames:
                    if frame.frame_number == new_pos:
                        existing = frame
                        break
                
                if existing:
                    print(f"  WARNING: Collision at {new_pos}, removing duplicate")
                    layer.frames.remove(existing.frame_number)
                
                layer.frames.copy(temp_pos, new_pos)
                layer.frames.remove(temp_pos)
            
            # Verify frame count
            all_frames_after = sorted(self.get_all_gp_keyframes_for_layer(context, layer))
            print(f"\n=== RESULTS ===")
            print(f"Frames BEFORE: {len(all_frames)}")
            print(f"Frames AFTER: {len(all_frames_after)}")
            
            if len(all_frames_after) != len(all_frames):
                print(f"ERROR: Lost {len(all_frames) - len(all_frames_after)} frames!")
                self.report({'ERROR'}, f"Frame count mismatch! Started with {len(all_frames)}, ended with {len(all_frames_after)}")
            else:
                print("SUCCESS: All frames preserved!")
            
            print("=== END ===\n")
            
            total_layers_processed += 1

        self.report({'INFO'}, f"Spaced keyframes on {total_layers_processed} layer(s) with {self.spacing_frames} frame intervals")
        return {'FINISHED'}

    def get_selected_gp_keyframes_per_layer(self, context):
        """Get dictionary of layers with their selected keyframe frame numbers."""
        layers_data = {}

        if (context.active_object and
            context.active_object.type == 'GREASEPENCIL' and
            context.active_object.data and
            context.active_object.data.layers):

            gpencil_data = context.active_object.data

            for layer in gpencil_data.layers:
                if not layer.lock and not layer.hide:
                    selected_frames = []
                    for frame in layer.frames:
                        if hasattr(frame, 'select') and frame.select:
                            selected_frames.append(frame.frame_number)

                    if selected_frames:
                        layers_data[layer] = sorted(selected_frames)

        return layers_data

    def get_all_gp_keyframes_for_layer(self, context, target_layer):
        """Get list of all GP keyframe frame numbers for a specific layer."""
        all_frames = []

        if (context.active_object and
            context.active_object.type == 'GREASEPENCIL' and
            context.active_object.data and
            context.active_object.data.layers):

            if not target_layer.lock and not target_layer.hide:
                for frame in target_layer.frames:
                    all_frames.append(frame.frame_number)

        return sorted(all_frames)