import bpy
from bpy.types import Operator
from ..utils import get_all_keyframes

class GPH_OT_marker_spacing(Operator):
    bl_idname = "gph.marker_spacing"
    bl_label = "Apply Marker Spacing"
    bl_description = "Add spacing between keyframes at timeline marker positions"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.area.type != 'DOPESHEET_EDITOR':
            self.report({'ERROR'}, "This operator only works in the Dope Sheet editor.")
            return {'CANCELLED'}

        props = context.scene.gph_marker_spacing_props

        # Get GP spacing markers only
        gp_spacing_markers = self.get_gp_spacing_markers(context)
        if not gp_spacing_markers:
            self.report({'WARNING'}, "No GP spacing markers found. Place markers at frames where you want to add spacing.")
            return {'CANCELLED'}

        # Get marker frames and sort them right-to-left for processing
        marker_frames = sorted([marker.frame for marker in gp_spacing_markers], reverse=True)

        # Validate GP objects
        gp_objects = self.get_target_gp_objects(context, props.target_selected_only)
        if not gp_objects:
            self.report({'ERROR'}, "No Grease Pencil objects found to process.")
            return {'CANCELLED'}

        # Check if any GP objects have keyframes
        total_keyframes = 0
        for obj in gp_objects:
            keyframes = self.get_gp_keyframes(obj)
            total_keyframes += len(keyframes)
            print(f"DEBUG: {obj.name} has {len(keyframes)} keyframes")

        if total_keyframes == 0:
            self.report({'ERROR'}, "No keyframes found in Grease Pencil objects. Make sure your GP objects have animation data.")
            return {'CANCELLED'}

        # Store original frame and active object
        original_frame = context.scene.frame_current
        original_active = context.active_object

        try:
            # Process each marker from right to left
            total_shifts = 0
            keyframes_moved = 0

            for marker_frame in marker_frames:
                print(f"DEBUG: Processing marker at frame {marker_frame}")

                # Calculate spacing to add at this marker
                spacing_to_add = self.calculate_spacing_to_add(context, marker_frame, props)
                print(f"DEBUG: Spacing to add: {spacing_to_add}")

                if spacing_to_add <= 0:
                    continue

                # Process each GP object
                for obj in gp_objects:
                    # Make this object active
                    context.view_layer.objects.active = obj

                    # Get keyframes after marker
                    keyframes_after_marker = self.get_keyframes_after_frame(obj, marker_frame)
                    print(f"DEBUG: Found {len(keyframes_after_marker)} keyframes after marker in {obj.name}")

                    if keyframes_after_marker:
                        # Use the tried-and-true select/transform method that works for GP
                        try:
                            # Set current frame to marker position
                            context.scene.frame_set(marker_frame)

                            # Deselect all first
                            bpy.ops.action.select_all(action='DESELECT')

                            # Select all keyframes to the right of the marker
                            bpy.ops.action.select_leftright(mode='RIGHT', extend=False)

                            # Transform them
                            bpy.ops.transform.transform(
                                mode='TIME_TRANSLATE',
                                value=(spacing_to_add, 0, 0, 0)
                            )

                            keyframes_moved += len(keyframes_after_marker)
                            print(f"DEBUG: Used select/transform method for {len(keyframes_after_marker)} keyframes in {obj.name}")

                        except Exception as e:
                            print(f"DEBUG: Select/transform method failed: {e}")
                            # Fallback to direct API if needed
                            moved_count = self.move_keyframes_directly(obj, keyframes_after_marker, spacing_to_add)
                            keyframes_moved += moved_count
                            print(f"DEBUG: Fallback moved {moved_count} keyframes in {obj.name}")

                total_shifts += spacing_to_add

            # Restore original state
            context.scene.frame_set(original_frame)
            if original_active:
                context.view_layer.objects.active = original_active

            if keyframes_moved > 0:
                # Auto-cleanup GP spacing markers if enabled
                if props.auto_cleanup_markers:
                    removed_count = 0
                    for marker in gp_spacing_markers:
                        context.scene.timeline_markers.remove(marker)
                        removed_count += 1

                    self.report({'INFO'}, f"Successfully moved {keyframes_moved} keyframes, added {total_shifts} frames of spacing at {len(marker_frames)} markers. Cleaned up {removed_count} GP spacing markers.")
                else:
                    self.report({'INFO'}, f"Successfully moved {keyframes_moved} keyframes, added {total_shifts} frames of spacing at {len(marker_frames)} markers")
            else:
                self.report({'WARNING'}, "No keyframes were found after the markers to move")

        except Exception as e:
            # Restore original state on error
            context.scene.frame_set(original_frame)
            if original_active:
                context.view_layer.objects.active = original_active
            self.report({'ERROR'}, f"Error during spacing operation: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def get_gp_spacing_markers(self, context):
        """Get markers specifically created for GP spacing (with 'GP_' prefix)."""
        markers = context.scene.timeline_markers
        gp_spacing_markers = []

        for marker in markers:
            if marker.name.startswith("GP_"):
                gp_spacing_markers.append(marker)

        return gp_spacing_markers

    def get_target_gp_objects(self, context, selected_only):
        """Get the Grease Pencil objects to process."""
        if selected_only:
            return [obj for obj in context.selected_objects if obj.type == 'GREASEPENCIL']
        else:
            return [obj for obj in context.scene.objects if obj.type == 'GREASEPENCIL']

    def calculate_spacing_to_add(self, context, marker_frame, props):
        """Calculate how much spacing to add at this marker."""
        if props.spacing_method == 'FIXED':
            return props.fixed_spacing

        # For multiplier method, we need to detect existing spacing
        if props.auto_detect_spacing:
            existing_spacing = self.detect_spacing_around_marker(context, marker_frame)
            if existing_spacing > 0:
                # Calculate additional spacing needed
                target_spacing = existing_spacing * props.spacing_multiplier
                return int(target_spacing - existing_spacing)

        # Fallback: use multiplier on a default spacing of 10 frames
        default_spacing = 10
        target_spacing = default_spacing * props.spacing_multiplier
        return int(target_spacing - default_spacing)

    def detect_spacing_around_marker(self, context, marker_frame):
        """Detect the existing spacing pattern around a marker."""
        # This is a simplified detection - looks for keyframes before and after marker
        keyframes = self.get_nearby_keyframes(context, marker_frame, search_range=50)

        if len(keyframes) < 2:
            return 0

        # Find keyframes immediately before and after marker
        before_kf = None
        after_kf = None

        for kf in keyframes:
            if kf < marker_frame:
                if before_kf is None or kf > before_kf:
                    before_kf = kf
            elif kf > marker_frame:
                if after_kf is None or kf < after_kf:
                    after_kf = kf

        if before_kf is not None and after_kf is not None:
            return after_kf - before_kf

        # Fallback: calculate average spacing from available keyframes
        if len(keyframes) >= 2:
            spacings = []
            for i in range(1, len(keyframes)):
                spacings.append(keyframes[i] - keyframes[i-1])
            return sum(spacings) / len(spacings)

        return 0

    def get_nearby_keyframes(self, context, marker_frame, search_range=50):
        """Get keyframes near the marker for spacing analysis."""
        keyframes = []

        # Look through all GP objects for keyframes
        for obj in context.scene.objects:
            if obj.type == 'GREASEPENCIL' and obj.animation_data and obj.animation_data.action:
                for fcurve in obj.animation_data.action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        frame = int(keyframe.co[0])
                        if abs(frame - marker_frame) <= search_range:
                            keyframes.append(frame)

        return sorted(list(set(keyframes)))  # Remove duplicates and sort

    def get_gp_keyframes(self, obj):
        """Get all keyframe positions from a GP object - uses wrapper."""
        if obj.type != 'GREASEPENCIL':
            return []

        # Use the centralized wrapper function
        keyframes = get_all_keyframes(obj)
        print(f"DEBUG: Total unique keyframes found: {len(keyframes)} - {keyframes}")
        return keyframes

    def get_keyframes_after_frame(self, obj, frame):
        """Get all keyframes that come after the specified frame."""
        all_keyframes = self.get_gp_keyframes(obj)
        return [kf for kf in all_keyframes if kf > frame]

    def move_keyframes_directly(self, obj, keyframe_frames, offset):
        """Move specific keyframes by the given offset using direct API."""
        moved_count = 0

        if obj.type != 'GREASEPENCIL':
            return 0

        print(f"DEBUG: Moving keyframes {keyframe_frames} by {offset} in {obj.name}")

        # Method 1: Move object-level animation keyframes
        if obj.animation_data and obj.animation_data.action:
            action = obj.animation_data.action
            for fcurve in action.fcurves:
                keyframes_to_move = []

                # Find keyframes that match our target frames
                for i, keyframe_point in enumerate(fcurve.keyframe_points):
                    frame = int(keyframe_point.co[0])
                    if frame in keyframe_frames:
                        keyframes_to_move.append((i, keyframe_point))

                # Move the keyframes
                for i, keyframe_point in keyframes_to_move:
                    old_frame = keyframe_point.co[0]
                    new_frame = old_frame + offset
                    keyframe_point.co[0] = new_frame
                    keyframe_point.handle_left[0] += offset
                    keyframe_point.handle_right[0] += offset
                    moved_count += 1
                    print(f"DEBUG: Moved object fcurve keyframe from {old_frame} to {new_frame}")

                # Update the fcurve
                if keyframes_to_move:
                    fcurve.update()

        # Method 2: Move GP data-level animation keyframes
        gp_data = obj.data
        if gp_data.animation_data and gp_data.animation_data.action:
            action = gp_data.animation_data.action
            for fcurve in action.fcurves:
                keyframes_to_move = []

                # Find keyframes that match our target frames
                for i, keyframe_point in enumerate(fcurve.keyframe_points):
                    frame = int(keyframe_point.co[0])
                    if frame in keyframe_frames:
                        keyframes_to_move.append((i, keyframe_point))

                # Move the keyframes
                for i, keyframe_point in keyframes_to_move:
                    old_frame = keyframe_point.co[0]
                    new_frame = old_frame + offset
                    keyframe_point.co[0] = new_frame
                    keyframe_point.handle_left[0] += offset
                    keyframe_point.handle_right[0] += offset
                    moved_count += 1
                    print(f"DEBUG: Moved GP data fcurve keyframe from {old_frame} to {new_frame}")

                # Update the fcurve
                if keyframes_to_move:
                    fcurve.update()

        # Method 3: Move GP layer frames (GP-specific)
        # Collect all frames to move across all layers first
        all_frames_to_move = []
        for layer in gp_data.layers:
            for frame in layer.frames:
                if frame.frame_number in keyframe_frames:
                    all_frames_to_move.append((layer, frame, frame.frame_number))

        if all_frames_to_move:
            print(f"DEBUG: Found {len(all_frames_to_move)} GP frames to move")

            # Sort by frame number in reverse order to avoid conflicts
            all_frames_to_move.sort(key=lambda x: x[2], reverse=True)

            # Use a different approach: duplicate frames and remove originals
            for layer, frame, old_frame_num in all_frames_to_move:
                new_frame_num = old_frame_num + offset

                try:
                    # Check if target frame already exists
                    existing_frames = {f.frame_number for f in layer.frames}
                    if new_frame_num not in existing_frames:
                        # Create new frame at target position
                        new_frame = layer.frames.new(new_frame_num)

                        # Copy frame data using Blender's internal methods
                        # This approach works with Blender 4.x
                        if hasattr(frame, 'copy_to'):
                            frame.copy_to(new_frame)
                        else:
                            # Alternative method for different Blender versions
                            bpy.context.scene.frame_set(old_frame_num)
                            layer.active_frame = frame

                            # Use duplicate operator which is more reliable
                            try:
                                bpy.ops.gpencil.frame_duplicate()
                                # Find the duplicated frame and move it
                                duplicated_frame = None
                                for f in layer.frames:
                                    if f.frame_number == old_frame_num and f != frame:
                                        duplicated_frame = f
                                        break

                                if duplicated_frame:
                                    # This is a hack but may work: remove and recreate
                                    layer.frames.remove(new_frame)  # Remove empty frame
                                    new_frame = layer.frames.new(new_frame_num)
                                    # The duplicated frame becomes our new frame
                                    layer.frames.remove(duplicated_frame)

                            except Exception as e:
                                print(f"DEBUG: Frame duplicate failed: {e}")
                                # Last resort: just create empty frame
                                pass

                        # Remove the original frame
                        layer.frames.remove(frame)
                        moved_count += 1
                        print(f"DEBUG: Moved GP frame from {old_frame_num} to {new_frame_num}")

                    else:
                        print(f"DEBUG: Target frame {new_frame_num} already exists")

                except Exception as e:
                    print(f"DEBUG: Failed to move frame {old_frame_num}: {e}")
                    continue

        print(f"DEBUG: Total keyframes moved: {moved_count}")
        return moved_count


class GPH_OT_clear_markers(Operator):
    bl_idname = "gph.clear_markers"
    bl_label = "Clear GP Spacing Markers"
    bl_description = "Clear all GP spacing markers (markers starting with 'GP_')"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        markers = context.scene.timeline_markers

        if not markers:
            self.report({'INFO'}, "No markers to clear")
            return {'FINISHED'}

        # Get GP spacing markers to remove
        gp_spacing_markers = []
        for marker in markers:
            if marker.name.startswith("GP_"):
                gp_spacing_markers.append(marker)

        if not gp_spacing_markers:
            self.report({'INFO'}, "No GP spacing markers found")
            return {'FINISHED'}

        # Remove the GP spacing markers
        removed_count = 0
        for marker in gp_spacing_markers:
            markers.remove(marker)
            removed_count += 1

        self.report({'INFO'}, f"Removed {removed_count} GP spacing markers")
        return {'FINISHED'}


class GPH_OT_add_gp_marker(Operator):
    bl_idname = "gph.add_gp_marker"
    bl_label = "Add GP Spacing Marker"
    bl_description = "Add a GP spacing marker at the current frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_frame = context.scene.frame_current
        markers = context.scene.timeline_markers

        # Check if a GP marker already exists at this frame
        existing_marker = None
        for marker in markers:
            if marker.frame == current_frame and marker.name.startswith("GP_"):
                existing_marker = marker
                break

        if existing_marker:
            self.report({'INFO'}, f"GP spacing marker already exists at frame {current_frame}")
            return {'FINISHED'}

        # Create a new GP spacing marker
        marker_name = f"GP_{current_frame:04d}"
        new_marker = markers.new(marker_name, frame=current_frame)

        self.report({'INFO'}, f"Added GP spacing marker '{marker_name}' at frame {current_frame}")
        return {'FINISHED'}


