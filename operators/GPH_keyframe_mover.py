import bpy
from bpy.types import Operator

class GPH_OT_keyframe_mover_forward(Operator):
    """Move all keyframes from playhead onward by the specified number of frames to the right"""
    bl_idname = "gph.keyframe_mover_forward"
    bl_label = "Move Keyframes Forward"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.area.type != 'DOPESHEET_EDITOR':
            self.report({'ERROR'}, "This operator only works in the Dope Sheet editor.")
            return {'CANCELLED'}

        # Get the frame offset from properties
        frame_offset = context.scene.gph_keyframe_props.frame_offset

        bpy.ops.action.select_all(action='DESELECT')
        bpy.ops.action.select_leftright(mode='RIGHT', extend=False)
        bpy.ops.transform.transform(mode='TIME_TRANSLATE', value=(frame_offset, 0, 0, 0))

        return {'FINISHED'}

class GPH_OT_keyframe_mover_backward(Operator):
    """Move all keyframes from playhead onward by the specified number of frames to the left, clamped to playhead position"""
    bl_idname = "gph.keyframe_mover_backward"
    bl_label = "Move Keyframes Backward"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.area.type != 'DOPESHEET_EDITOR':
            self.report({'ERROR'}, "This operator only works in the Dope Sheet editor.")
            return {'CANCELLED'}

        scene = context.scene
        current_frame = scene.frame_current
        frame_offset = context.scene.gph_keyframe_props.frame_offset

        # Get all keyframes that will be affected (keyframes after current frame)
        affected_keyframes = self.get_keyframes_after_frame(context, current_frame)

        if not affected_keyframes:
            self.report({'INFO'}, "No keyframes found after playhead to move")
            return {'CANCELLED'}

        # Calculate the safe maximum offset to avoid collisions
        safe_offset = self.calculate_safe_backward_offset(context, current_frame, frame_offset, affected_keyframes)

        if safe_offset == 0:
            self.report({'WARNING'}, "Cannot move backwards - would cause keyframe collision")
            return {'CANCELLED'}

        if safe_offset < frame_offset:
            self.report({'WARNING'}, f"Reduced offset from {frame_offset} to {safe_offset} frames to avoid collision")

        # Check if there's ANY keyframe at the playhead position (original check)
        keyframe_at_playhead = False

        print(f"DEBUG: Checking for GP keyframes at frame {current_frame}")

        # Check GP object specifically
        if (context.active_object and
            context.active_object.type == 'GREASEPENCIL' and
            context.active_object.data and
            context.active_object.data.layers):

            gpencil_data = context.active_object.data
            print(f"DEBUG: GP object '{context.active_object.name}' has {len(gpencil_data.layers)} layers")

            # Check all layers in the active GP object
            for layer in gpencil_data.layers:
                print(f"DEBUG: Checking layer '{layer.name}' (locked: {layer.lock}, hidden: {layer.hide})")

                # Only check layers that are not locked and are visible
                if not layer.lock and not layer.hide:
                    # Check drawing keyframes
                    print(f"DEBUG: Layer '{layer.name}' has {len(layer.frames)} drawing frames")
                    for frame in layer.frames:
                        print(f"DEBUG: Drawing frame at {frame.frame_number}")
                        if frame.frame_number == current_frame:
                            keyframe_at_playhead = True
                            print(f"DEBUG: FOUND GP drawing keyframe at frame {current_frame}")
                            break

                    # Check if layer has any animated properties
                    print(f"DEBUG: Checking layer '{layer.name}' for animated properties...")
                    print(f"DEBUG: Layer opacity: {layer.opacity}")
                    print(f"DEBUG: Layer tint_color: {layer.tint_color}")
                    print(f"DEBUG: Layer tint_factor: {layer.tint_factor}")

                    # Check if the GP object has animation data that affects this layer
                    if context.active_object.animation_data and context.active_object.animation_data.action:
                        print(f"DEBUG: GP object has animation data")
                        action = context.active_object.animation_data.action
                        for fcurve in action.fcurves:
                            print(f"DEBUG: FCurve: {fcurve.data_path}")
                            if f'layers["{layer.name}"]' in fcurve.data_path:
                                print(f"DEBUG: Found layer-specific fcurve: {fcurve.data_path}")
                                for keyframe in fcurve.keyframe_points:
                                    print(f"DEBUG: Layer attribute keyframe at {keyframe.co[0]}")
                                    if abs(keyframe.co[0] - current_frame) < 0.01:
                                        keyframe_at_playhead = True
                                        print(f"DEBUG: FOUND GP layer attribute keyframe at frame {current_frame} ({fcurve.data_path})")
                                        break
                    else:
                        print(f"DEBUG: No animation data found on GP object")

                    # Check if the GP data itself has animation data
                    if gpencil_data.animation_data and gpencil_data.animation_data.action:
                        print(f"DEBUG: GP data has animation data")
                        action = gpencil_data.animation_data.action
                        for fcurve in action.fcurves:
                            print(f"DEBUG: GP Data FCurve: {fcurve.data_path}")
                            if f'layers["{layer.name}"]' in fcurve.data_path:
                                print(f"DEBUG: Found GP data layer-specific fcurve: {fcurve.data_path}")
                                for keyframe in fcurve.keyframe_points:
                                    print(f"DEBUG: GP data layer attribute keyframe at {keyframe.co[0]}")
                                    if abs(keyframe.co[0] - current_frame) < 0.01:
                                        keyframe_at_playhead = True
                                        print(f"DEBUG: FOUND GP data layer attribute keyframe at frame {current_frame} ({fcurve.data_path})")
                                        break
                    else:
                        print(f"DEBUG: No animation data found on GP data")

                    if keyframe_at_playhead:
                        break

            # Also check GP materials for animated properties
            if not keyframe_at_playhead and gpencil_data.materials:
                print(f"DEBUG: Checking {len(gpencil_data.materials)} GP materials")
                for i, material in enumerate(gpencil_data.materials):
                    if material and material.animation_data and material.animation_data.action:
                        print(f"DEBUG: Material '{material.name}' has animation data")
                        action = material.animation_data.action
                        for fcurve in action.fcurves:
                            print(f"DEBUG: Material FCurve: {fcurve.data_path}")
                            for keyframe in fcurve.keyframe_points:
                                print(f"DEBUG: Material keyframe at {keyframe.co[0]}")
                                if abs(keyframe.co[0] - current_frame) < 0.01:
                                    keyframe_at_playhead = True
                                    print(f"DEBUG: FOUND GP material keyframe at frame {current_frame} - Material: '{material.name}' ({fcurve.data_path})")
                                    break
                            if keyframe_at_playhead:
                                break
                    else:
                        print(f"DEBUG: Material '{material.name if material else 'None'}' has no animation data")
                    if keyframe_at_playhead:
                        break

            # Check GP modifiers for animated properties (stored in object animation_data)
            if not keyframe_at_playhead and context.active_object.modifiers and context.active_object.animation_data and context.active_object.animation_data.action:
                print(f"DEBUG: Checking {len(context.active_object.modifiers)} modifiers")
                action = context.active_object.animation_data.action

                for modifier in context.active_object.modifiers:
                    modifier_path_prefix = f'modifiers["{modifier.name}"]'
                    print(f"DEBUG: Looking for modifier '{modifier.name}' keyframes with path: {modifier_path_prefix}")

                    for fcurve in action.fcurves:
                        if fcurve.data_path.startswith(modifier_path_prefix):
                            print(f"DEBUG: Found modifier FCurve: {fcurve.data_path}")
                            for keyframe in fcurve.keyframe_points:
                                print(f"DEBUG: Modifier keyframe at {keyframe.co[0]}")
                                if abs(keyframe.co[0] - current_frame) < 0.01:
                                    keyframe_at_playhead = True
                                    print(f"DEBUG: FOUND GP modifier keyframe at frame {current_frame} - Modifier: '{modifier.name}' ({fcurve.data_path})")
                                    break
                            if keyframe_at_playhead:
                                break
                    if keyframe_at_playhead:
                        break

            # Check GP shader effects for animated properties (stored in object animation_data)
            if not keyframe_at_playhead and context.active_object.shader_effects and context.active_object.animation_data and context.active_object.animation_data.action:
                print(f"DEBUG: Checking {len(context.active_object.shader_effects)} GP shader effects")
                action = context.active_object.animation_data.action

                for effect in context.active_object.shader_effects:
                    effect_path_prefix = f'shader_effects["{effect.name}"]'
                    print(f"DEBUG: Looking for effect '{effect.name}' keyframes with path: {effect_path_prefix}")

                    for fcurve in action.fcurves:
                        if fcurve.data_path.startswith(effect_path_prefix):
                            print(f"DEBUG: Found effect FCurve: {fcurve.data_path}")
                            for keyframe in fcurve.keyframe_points:
                                print(f"DEBUG: Effect keyframe at {keyframe.co[0]}")
                                if abs(keyframe.co[0] - current_frame) < 0.01:
                                    keyframe_at_playhead = True
                                    print(f"DEBUG: FOUND GP effect keyframe at frame {current_frame} - Effect: '{effect.name}' ({fcurve.data_path})")
                                    break
                            if keyframe_at_playhead:
                                break
                    if keyframe_at_playhead:
                        break

        # If there's a keyframe at the playhead, stop and show warning
        if keyframe_at_playhead:
            self.report({'WARNING'}, "Cannot move backwards - keyframe detected at playhead")
            return {'CANCELLED'}

        # No keyframe at playhead, proceed with backward movement using safe offset
        bpy.ops.action.select_all(action='DESELECT')
        bpy.ops.action.select_leftright(mode='RIGHT', extend=False)
        bpy.ops.transform.transform(mode='TIME_TRANSLATE', value=(-safe_offset, 0, 0, 0))

        return {'FINISHED'}

    def get_keyframes_after_frame(self, context, frame):
        """Get all keyframes that come after the specified frame."""
        keyframes = []

        # Check GP object specifically
        if (context.active_object and
            context.active_object.type == 'GREASEPENCIL' and
            context.active_object.data and
            context.active_object.data.layers):

            gpencil_data = context.active_object.data

            # Check drawing keyframes in all layers
            for layer in gpencil_data.layers:
                if not layer.lock and not layer.hide:
                    for gp_frame in layer.frames:
                        if gp_frame.frame_number > frame:
                            keyframes.append(gp_frame.frame_number)

            # Check object-level animation keyframes
            if context.active_object.animation_data and context.active_object.animation_data.action:
                action = context.active_object.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if kf_frame > frame:
                            keyframes.append(kf_frame)

            # Check GP data-level animation keyframes
            if gpencil_data.animation_data and gpencil_data.animation_data.action:
                action = gpencil_data.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if kf_frame > frame:
                            keyframes.append(kf_frame)

        return sorted(list(set(keyframes)))

    def get_all_keyframes_in_range(self, context, start_frame, end_frame):
        """Get all keyframes in the specified range (inclusive)."""
        keyframes = []

        # Check GP object specifically
        if (context.active_object and
            context.active_object.type == 'GREASEPENCIL' and
            context.active_object.data and
            context.active_object.data.layers):

            gpencil_data = context.active_object.data

            # Check drawing keyframes in all layers
            for layer in gpencil_data.layers:
                if not layer.lock and not layer.hide:
                    for gp_frame in layer.frames:
                        if start_frame <= gp_frame.frame_number <= end_frame:
                            keyframes.append(gp_frame.frame_number)

            # Check object-level animation keyframes
            if context.active_object.animation_data and context.active_object.animation_data.action:
                action = context.active_object.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if start_frame <= kf_frame <= end_frame:
                            keyframes.append(kf_frame)

            # Check GP data-level animation keyframes
            if gpencil_data.animation_data and gpencil_data.animation_data.action:
                action = gpencil_data.animation_data.action
                for fcurve in action.fcurves:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if start_frame <= kf_frame <= end_frame:
                            keyframes.append(kf_frame)

        return sorted(list(set(keyframes)))

    def calculate_safe_backward_offset(self, context, current_frame, desired_offset, affected_keyframes):
        """Calculate the maximum safe offset to avoid keyframe collisions."""
        if not affected_keyframes:
            return desired_offset

        # Find the minimum distance from current frame to any affected keyframe
        min_distance = min(kf - current_frame for kf in affected_keyframes)

        print(f"DEBUG: Current frame: {current_frame}, Desired offset: {desired_offset}")
        print(f"DEBUG: Affected keyframes: {affected_keyframes}")
        print(f"DEBUG: Minimum distance to keyframe: {min_distance}")

        # Check what keyframes exist in the target collision zone
        # When moving backwards by offset, keyframes will land at (original_position - offset)
        # We need to check if any keyframes will land in the "forbidden zone"
        # between current_frame and the closest existing keyframe to the left

        # Get all existing keyframes before current frame to find collision boundaries
        all_existing_keyframes = self.get_all_keyframes_in_range(context, 1, current_frame)

        # Find the closest existing keyframe to the left of current frame
        closest_left_keyframe = None
        if all_existing_keyframes:
            closest_left_keyframe = max(all_existing_keyframes)

        print(f"DEBUG: Existing keyframes before current: {all_existing_keyframes}")
        print(f"DEBUG: Closest left keyframe: {closest_left_keyframe}")

        # Calculate safe offset
        if min_distance <= desired_offset:
            # The desired offset would cause collision
            # Reduce offset to the maximum safe distance minus 1
            safe_offset = min_distance - 1
            if safe_offset < 1:
                return 0  # No safe movement possible
            return safe_offset

        # Check if any affected keyframe would land on existing keyframes
        max_safe_offset = desired_offset
        for kf in affected_keyframes:
            target_position = kf - desired_offset

            # If target position would be at or before current frame, that's invalid
            if target_position <= current_frame:
                # Calculate maximum offset that keeps this keyframe after current frame
                max_safe_for_this_kf = kf - current_frame - 1
                if max_safe_for_this_kf > 0:
                    max_safe_offset = min(max_safe_offset, max_safe_for_this_kf)
                else:
                    return 0  # No safe movement possible

        return max(1, max_safe_offset)


class GPH_OT_refresh_layers(Operator):
    """Refresh the list of Grease Pencil layers"""
    bl_idname = "gph.refresh_layers"
    bl_label = "Refresh Layers"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.gph_keyframe_props

        # Clear existing layer settings
        props.layer_settings.clear()

        # Find active GP object
        gp_obj = None
        if context.active_object and context.active_object.type == 'GREASEPENCIL':
            gp_obj = context.active_object
        else:
            # Look for any GP object in selection
            for obj in context.selected_objects:
                if obj.type == 'GREASEPENCIL':
                    gp_obj = obj
                    break

        if not gp_obj:
            # Look for any GP object in scene
            for obj in context.scene.objects:
                if obj.type == 'GREASEPENCIL':
                    gp_obj = obj
                    break

        if not gp_obj:
            self.report({'WARNING'}, "No Grease Pencil object found")
            return {'CANCELLED'}

        # Populate layer settings in reverse order to match GP layers panel display order
        for layer in reversed(gp_obj.data.layers):
            layer_setting = props.layer_settings.add()
            layer_setting.layer_name = layer.info if hasattr(layer, 'info') else layer.name
            layer_setting.is_enabled = True

        self.report({'INFO'}, f"Found {len(props.layer_settings)} GP layers")
        return {'FINISHED'}


class GPH_OT_keyframe_mover_layer_forward(Operator):
    """Move keyframes forward for a specific Grease Pencil layer"""
    bl_idname = "gph.keyframe_mover_layer_forward"
    bl_label = "Move Layer Keyframes Forward"
    bl_options = {'REGISTER', 'UNDO'}

    layer_name: bpy.props.StringProperty(name="Layer Name")

    def execute(self, context):
        if context.area.type != 'DOPESHEET_EDITOR':
            self.report({'ERROR'}, "This operator only works in the Dope Sheet editor.")
            return {'CANCELLED'}

        # Find the layer setting
        props = context.scene.gph_keyframe_props
        layer_setting = None
        for setting in props.layer_settings:
            if setting.layer_name == self.layer_name:
                layer_setting = setting
                break

        if not layer_setting:
            self.report({'ERROR'}, f"Layer setting not found for '{self.layer_name}'")
            return {'CANCELLED'}

        if not layer_setting.is_enabled:
            self.report({'INFO'}, f"Layer '{self.layer_name}' is disabled")
            return {'CANCELLED'}

        # Use master frame offset
        frame_offset = props.frame_offset

        # Set the GP object as active and ensure we're working with the right layer
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            self.report({'ERROR'}, f"No active Grease Pencil object found")
            return {'CANCELLED'}

        # Find and make the target layer active
        target_layer = None
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id == self.layer_name:
                target_layer = layer
                break

        if not target_layer:
            self.report({'ERROR'}, f"Layer '{self.layer_name}' not found")
            return {'CANCELLED'}

        # Store original active layer
        original_active_layer = gp_obj.data.layers.active

        try:
            # Same master behavior but filtered to this layer
            bpy.ops.action.select_all(action='DESELECT')
            bpy.ops.action.select_leftright(mode='RIGHT', extend=False)

            # Filter selection to only this layer's keyframes
            self.filter_selection_to_layer(context, self.layer_name)

            # Move using same transform as master
            bpy.ops.transform.transform(mode='TIME_TRANSLATE', value=(frame_offset, 0, 0, 0))

            self.report({'INFO'}, f"Moved '{self.layer_name}' keyframes forward by {frame_offset} frames")

        finally:
            # Restore original active layer
            if original_active_layer:
                gp_obj.data.layers.active = original_active_layer

        return {'FINISHED'}

    def filter_selection_to_layer(self, context, layer_name):
        """Filter selection to only GP frames and attribute keyframes from the specified layer."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return

        print(f"DEBUG: Filtering to layer '{layer_name}' - GP frames and attributes only")

        # Deselect drawing frames from other layers
        drawing_frames_deselected = 0
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id != layer_name:
                # Deselect all drawing frames from other layers
                for frame in layer.frames:
                    if hasattr(frame, 'select') and frame.select:
                        frame.select = False
                        drawing_frames_deselected += 1

        # Deselect attribute keyframes from other layers
        attribute_keyframes_deselected = 0

        # Check both object-level and GP data-level animation data
        animation_data_sources = []
        if gp_obj.animation_data and gp_obj.animation_data.action:
            animation_data_sources.append(gp_obj.animation_data.action)
        if gp_obj.data.animation_data and gp_obj.data.animation_data.action:
            animation_data_sources.append(gp_obj.data.animation_data.action)

        for action in animation_data_sources:
            for fcurve in action.fcurves:
                # Check if this fcurve affects a different layer
                if 'layers[' in fcurve.data_path:
                    # Extract layer name from data path like 'layers["LayerName"].opacity'
                    is_target_layer = f'layers["{layer_name}"]' in fcurve.data_path

                    if not is_target_layer:
                        # Deselect all keyframes in this fcurve
                        for keyframe in fcurve.keyframe_points:
                            if keyframe.select_control_point:
                                keyframe.select_control_point = False
                                attribute_keyframes_deselected += 1
                            if keyframe.select_left_handle:
                                keyframe.select_left_handle = False
                            if keyframe.select_right_handle:
                                keyframe.select_right_handle = False

        print(f"DEBUG: Deselected {drawing_frames_deselected} drawing frames and {attribute_keyframes_deselected} attribute keyframes from other layers")

    def move_layer_keyframes(self, context, layer_name, offset):
        """Move keyframes for a specific layer forward."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return False

        current_frame = context.scene.frame_current
        moved_any = False

        # Find the specific layer
        target_layer = None
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id == layer_name:
                target_layer = layer
                break

        if not target_layer:
            return False

        # Move GP frames for this layer
        frames_to_move = []
        for frame in target_layer.frames:
            if frame.frame_number > current_frame:
                frames_to_move.append(frame)

        # Sort by frame number in reverse order to avoid conflicts
        frames_to_move.sort(key=lambda f: f.frame_number, reverse=True)

        for frame in frames_to_move:
            old_frame_num = frame.frame_number
            new_frame_num = old_frame_num + offset

            # Check if target frame already exists
            existing_frames = {f.frame_number for f in target_layer.frames}
            if new_frame_num not in existing_frames:
                # Create new frame at target position
                new_frame = target_layer.frames.new(new_frame_num)

                # Copy frame data
                try:
                    if hasattr(frame, 'copy_to'):
                        frame.copy_to(new_frame)
                    else:
                        # Alternative copying method
                        new_frame.strokes.clear()
                        for stroke in frame.strokes:
                            new_stroke = new_frame.strokes.new()
                            new_stroke.copy_from(stroke)
                except:
                    pass  # If copying fails, at least create empty frame

                # Remove original frame using frame number
                try:
                    # Create a list of frames to check since we modified the collection
                    frames_to_check = [f for f in target_layer.frames if f.frame_number == old_frame_num and f != new_frame]
                    if frames_to_check:
                        # Remove by frame number - this is the correct API
                        del target_layer.frames[old_frame_num]
                except:
                    # Alternative removal method if del doesn't work
                    try:
                        target_layer.frames.remove(old_frame_num)
                    except:
                        pass  # If removal fails, at least we have the new frame
                moved_any = True

        # Also move layer attribute keyframes
        moved_any |= self.move_layer_attribute_keyframes(context, layer_name, current_frame, offset)

        return moved_any

    def move_layer_attribute_keyframes(self, context, layer_name, current_frame, offset):
        """Move layer attribute keyframes (opacity, tint, etc.) forward."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return False

        moved_any = False

        # Check both object-level and GP data-level animation data
        animation_data_sources = []
        if gp_obj.animation_data and gp_obj.animation_data.action:
            animation_data_sources.append(gp_obj.animation_data.action)
        if gp_obj.data.animation_data and gp_obj.data.animation_data.action:
            animation_data_sources.append(gp_obj.data.animation_data.action)

        for action in animation_data_sources:
            # Find fcurves that affect this specific layer
            layer_fcurves = []
            for fcurve in action.fcurves:
                if f'layers["{layer_name}"]' in fcurve.data_path:
                    layer_fcurves.append(fcurve)

            # Move keyframes in layer-specific fcurves
            for fcurve in layer_fcurves:
                keyframes_to_move = []
                for keyframe in fcurve.keyframe_points:
                    if keyframe.co[0] > current_frame:
                        keyframes_to_move.append(keyframe)

                # Sort by frame in reverse order to avoid conflicts
                keyframes_to_move.sort(key=lambda kf: kf.co[0], reverse=True)

                for keyframe in keyframes_to_move:
                    old_frame = keyframe.co[0]
                    new_frame = old_frame + offset

                    # Move the keyframe
                    keyframe.co[0] = new_frame
                    keyframe.handle_left[0] += offset
                    keyframe.handle_right[0] += offset
                    moved_any = True

                # Update the fcurve if we moved any keyframes
                if keyframes_to_move:
                    fcurve.update()

        return moved_any


class GPH_OT_keyframe_mover_layer_backward(Operator):
    """Move keyframes backward for a specific Grease Pencil layer"""
    bl_idname = "gph.keyframe_mover_layer_backward"
    bl_label = "Move Layer Keyframes Backward"
    bl_options = {'REGISTER', 'UNDO'}

    layer_name: bpy.props.StringProperty(name="Layer Name")

    def execute(self, context):
        if context.area.type != 'DOPESHEET_EDITOR':
            self.report({'ERROR'}, "This operator only works in the Dope Sheet editor.")
            return {'CANCELLED'}

        # Find the layer setting
        props = context.scene.gph_keyframe_props
        layer_setting = None
        for setting in props.layer_settings:
            if setting.layer_name == self.layer_name:
                layer_setting = setting
                break

        if not layer_setting:
            self.report({'ERROR'}, f"Layer setting not found for '{self.layer_name}'")
            return {'CANCELLED'}

        if not layer_setting.is_enabled:
            self.report({'INFO'}, f"Layer '{self.layer_name}' is disabled")
            return {'CANCELLED'}

        # Use master frame offset
        frame_offset = props.frame_offset
        current_frame = context.scene.frame_current

        # Get keyframes for this layer after current frame
        affected_keyframes = self.get_layer_keyframes_after_frame(context, self.layer_name, current_frame)

        if not affected_keyframes:
            self.report({'INFO'}, f"No keyframes found after playhead for layer '{self.layer_name}'")
            return {'CANCELLED'}

        # Calculate safe offset using the same logic as master backward
        safe_offset = self.calculate_safe_backward_offset_for_layer(context, self.layer_name, current_frame, frame_offset, affected_keyframes)

        if safe_offset == 0:
            self.report({'WARNING'}, f"Cannot move layer '{self.layer_name}' backwards - would cause collision")
            return {'CANCELLED'}

        if safe_offset < frame_offset:
            self.report({'WARNING'}, f"Reduced layer '{self.layer_name}' offset from {frame_offset} to {safe_offset} frames to avoid collision")

        # Set the GP object as active and ensure we're working with the right layer
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            self.report({'ERROR'}, f"No active Grease Pencil object found")
            return {'CANCELLED'}

        # Find and make the target layer active
        target_layer = None
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id == self.layer_name:
                target_layer = layer
                break

        if not target_layer:
            self.report({'ERROR'}, f"Layer '{self.layer_name}' not found")
            return {'CANCELLED'}

        # Store original active layer
        original_active_layer = gp_obj.data.layers.active

        try:
            # Same master behavior but filtered to this layer
            bpy.ops.action.select_all(action='DESELECT')
            bpy.ops.action.select_leftright(mode='RIGHT', extend=False)

            # Filter selection to only this layer's keyframes
            self.filter_selection_to_layer(context, self.layer_name)

            # Move using same transform as master with safe offset
            bpy.ops.transform.transform(mode='TIME_TRANSLATE', value=(-safe_offset, 0, 0, 0))

            self.report({'INFO'}, f"Moved '{self.layer_name}' keyframes backward by {safe_offset} frames")

        finally:
            # Restore original active layer
            if original_active_layer:
                gp_obj.data.layers.active = original_active_layer

        return {'FINISHED'}

    def filter_selection_to_layer(self, context, layer_name):
        """Filter selection to only GP frames and attribute keyframes from the specified layer."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return

        print(f"DEBUG: Filtering to layer '{layer_name}' - GP frames and attributes only")

        # Deselect drawing frames from other layers
        drawing_frames_deselected = 0
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id != layer_name:
                # Deselect all drawing frames from other layers
                for frame in layer.frames:
                    if hasattr(frame, 'select') and frame.select:
                        frame.select = False
                        drawing_frames_deselected += 1

        # Deselect attribute keyframes from other layers
        attribute_keyframes_deselected = 0

        # Check both object-level and GP data-level animation data
        animation_data_sources = []
        if gp_obj.animation_data and gp_obj.animation_data.action:
            animation_data_sources.append(gp_obj.animation_data.action)
        if gp_obj.data.animation_data and gp_obj.data.animation_data.action:
            animation_data_sources.append(gp_obj.data.animation_data.action)

        for action in animation_data_sources:
            for fcurve in action.fcurves:
                # Check if this fcurve affects a different layer
                if 'layers[' in fcurve.data_path:
                    # Extract layer name from data path like 'layers["LayerName"].opacity'
                    is_target_layer = f'layers["{layer_name}"]' in fcurve.data_path

                    if not is_target_layer:
                        # Deselect all keyframes in this fcurve
                        for keyframe in fcurve.keyframe_points:
                            if keyframe.select_control_point:
                                keyframe.select_control_point = False
                                attribute_keyframes_deselected += 1
                            if keyframe.select_left_handle:
                                keyframe.select_left_handle = False
                            if keyframe.select_right_handle:
                                keyframe.select_right_handle = False

        print(f"DEBUG: Deselected {drawing_frames_deselected} drawing frames and {attribute_keyframes_deselected} attribute keyframes from other layers")

    def get_layer_keyframes_after_frame(self, context, layer_name, frame):
        """Get keyframes for a specific layer after the specified frame."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return []

        keyframes = []

        # Get drawing keyframes
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id == layer_name:
                for gp_frame in layer.frames:
                    if gp_frame.frame_number > frame:
                        keyframes.append(gp_frame.frame_number)
                break

        # Get layer attribute keyframes
        animation_data_sources = []
        if gp_obj.animation_data and gp_obj.animation_data.action:
            animation_data_sources.append(gp_obj.animation_data.action)
        if gp_obj.data.animation_data and gp_obj.data.animation_data.action:
            animation_data_sources.append(gp_obj.data.animation_data.action)

        for action in animation_data_sources:
            for fcurve in action.fcurves:
                if f'layers["{layer_name}"]' in fcurve.data_path:
                    for keyframe in fcurve.keyframe_points:
                        kf_frame = int(keyframe.co[0])
                        if kf_frame > frame:
                            keyframes.append(kf_frame)

        return sorted(list(set(keyframes)))

    def calculate_safe_backward_offset_for_layer(self, context, layer_name, current_frame, desired_offset, affected_keyframes):
        """Calculate safe backward offset for a specific layer."""
        if not affected_keyframes:
            return desired_offset

        min_distance = min(kf - current_frame for kf in affected_keyframes)

        if min_distance <= desired_offset:
            safe_offset = min_distance - 1
            if safe_offset < 1:
                return 0
            return safe_offset

        return desired_offset

    def move_layer_keyframes_backward(self, context, layer_name, offset):
        """Move keyframes for a specific layer backward."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return False

        current_frame = context.scene.frame_current
        moved_any = False

        # Find the specific layer
        target_layer = None
        for layer in gp_obj.data.layers:
            layer_id = layer.info if hasattr(layer, 'info') else layer.name
            if layer_id == layer_name:
                target_layer = layer
                break

        if not target_layer:
            return False

        # Move GP frames for this layer
        frames_to_move = []
        for frame in target_layer.frames:
            if frame.frame_number > current_frame:
                frames_to_move.append(frame)

        # Sort by frame number to avoid conflicts
        frames_to_move.sort(key=lambda f: f.frame_number)

        for frame in frames_to_move:
            old_frame_num = frame.frame_number
            new_frame_num = old_frame_num - offset

            if new_frame_num > current_frame:  # Only move if still after playhead
                # Check if target frame already exists
                existing_frames = {f.frame_number for f in target_layer.frames}
                if new_frame_num not in existing_frames:
                    # Create new frame at target position
                    new_frame = target_layer.frames.new(new_frame_num)

                    # Copy frame data
                    try:
                        if hasattr(frame, 'copy_to'):
                            frame.copy_to(new_frame)
                        else:
                            # Alternative copying method
                            new_frame.strokes.clear()
                            for stroke in frame.strokes:
                                new_stroke = new_frame.strokes.new()
                                new_stroke.copy_from(stroke)
                    except:
                        pass  # If copying fails, at least create empty frame

                    # Remove original frame using frame number
                    try:
                        # Create a list of frames to check since we modified the collection
                        frames_to_check = [f for f in target_layer.frames if f.frame_number == old_frame_num and f != new_frame]
                        if frames_to_check:
                            # Remove by frame number - this is the correct API
                            del target_layer.frames[old_frame_num]
                    except:
                        # Alternative removal method if del doesn't work
                        try:
                            target_layer.frames.remove(old_frame_num)
                        except:
                            pass  # If removal fails, at least we have the new frame
                    moved_any = True

        # Also move layer attribute keyframes
        moved_any |= self.move_layer_attribute_keyframes_backward(context, layer_name, current_frame, offset)

        return moved_any

    def move_layer_attribute_keyframes_backward(self, context, layer_name, current_frame, offset):
        """Move layer attribute keyframes (opacity, tint, etc.) backward."""
        gp_obj = context.active_object
        if not gp_obj or gp_obj.type != 'GREASEPENCIL':
            return False

        moved_any = False

        # Check both object-level and GP data-level animation data
        animation_data_sources = []
        if gp_obj.animation_data and gp_obj.animation_data.action:
            animation_data_sources.append(gp_obj.animation_data.action)
        if gp_obj.data.animation_data and gp_obj.data.animation_data.action:
            animation_data_sources.append(gp_obj.data.animation_data.action)

        for action in animation_data_sources:
            # Find fcurves that affect this specific layer
            layer_fcurves = []
            for fcurve in action.fcurves:
                if f'layers["{layer_name}"]' in fcurve.data_path:
                    layer_fcurves.append(fcurve)

            # Move keyframes in layer-specific fcurves
            for fcurve in layer_fcurves:
                keyframes_to_move = []
                for keyframe in fcurve.keyframe_points:
                    if keyframe.co[0] > current_frame:
                        keyframes_to_move.append(keyframe)

                # Sort by frame in forward order to avoid conflicts when moving backward
                keyframes_to_move.sort(key=lambda kf: kf.co[0])

                for keyframe in keyframes_to_move:
                    old_frame = keyframe.co[0]
                    new_frame = old_frame - offset

                    # Only move if the new position is still after the playhead
                    if new_frame > current_frame:
                        # Move the keyframe
                        keyframe.co[0] = new_frame
                        keyframe.handle_left[0] -= offset
                        keyframe.handle_right[0] -= offset
                        moved_any = True

                # Update the fcurve if we moved any keyframes
                if keyframes_to_move:
                    fcurve.update()

        return moved_any


# Keep old class for backward compatibility
class GPH_OT_keyframe_mover(GPH_OT_keyframe_mover_forward):
    """Move all keyframes from playhead onward one frame to the right (deprecated, use GPH_OT_keyframe_mover_forward)"""
    bl_idname = "gph.keyframe_mover"