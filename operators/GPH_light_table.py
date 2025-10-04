import bpy
from bpy.types import Operator

class GPH_OT_toggle_light_table(Operator):
    """Toggle light table visibility"""
    bl_idname = "gph.toggle_light_table"
    bl_label = "Toggle Light Table"
    bl_description = "Enable/disable reference frame light table"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'GREASEPENCIL'

    def execute(self, context):
        props = context.scene.gph_light_table_props
        print(f"Light table toggle execute - currently enabled: {props.enabled}")

        if props.enabled:
            # Disable light table
            print("Disabling light table...")
            self.disable_light_table(context)
            props.enabled = False
            self.report({'INFO'}, "Light table disabled")
        else:
            # Enable light table
            print("Enabling light table...")
            success = self.enable_light_table(context)
            if success:
                props.enabled = True
                self.report({'INFO'}, "Light table enabled")
                print("Light table enabled successfully")
            else:
                self.report({'ERROR'}, "Failed to enable light table")
                print("Light table enable failed")
                return {'CANCELLED'}

        return {'FINISHED'}

    def enable_light_table(self, context):
        """Create and show light table reference"""
        props = context.scene.gph_light_table_props
        source_obj = context.active_object

        # Store reference frame if lock_to_current
        if props.lock_to_current:
            props.reference_frame = context.scene.frame_current

        print(f"Enabling light table with reference_frame = {props.reference_frame}")

        # Create reference object
        return self.create_reference_object(context, source_obj)

    def disable_light_table(self, context):
        """Remove light table reference"""
        source_obj = context.active_object

        # Find and remove reference object
        ref_obj_name = source_obj.get("gph_light_table_ref")

        if ref_obj_name and ref_obj_name in bpy.data.objects:
            ref_obj = bpy.data.objects[ref_obj_name]
            bpy.data.objects.remove(ref_obj, do_unlink=True)

            if "gph_light_table_ref" in source_obj:
                del source_obj["gph_light_table_ref"]

    def create_reference_object(self, context, source_obj):
        """Create duplicate GP object for reference"""
        props = context.scene.gph_light_table_props
        
        # Remove old reference if exists
        self.disable_light_table(context)
        
        try:
            # Duplicate the GP object
            ref_obj = source_obj.copy()
            ref_obj.data = source_obj.data  # Link to same data
            ref_obj.name = f"{source_obj.name}_LIGHT_TABLE_REF"
            
            # Link to collection
            context.collection.objects.link(ref_obj)
            
            # Clear all modifiers from the duplicate for a clean reference
            ref_obj.modifiers.clear()
            print(f"Cleared {len(source_obj.modifiers)} modifiers from reference object")
            
            # Add Time Offset modifier
            try:
                time_mod = ref_obj.modifiers.new(name="Light Table Lock", type='GREASE_PENCIL_TIME')
                time_mod.mode = 'FIX'

                # For Grease Pencil v3 Time Offset modifier, use 'offset' attribute
                time_mod.offset = props.reference_frame
                
                print(f"Created Time Offset modifier locked to frame {props.reference_frame}")
                print(f"Time modifier offset value: {time_mod.offset}")
                
            except Exception as e:
                print(f"Warning: Could not create Time Offset modifier: {e}")
                import traceback
                traceback.print_exc()

            # Add Tint modifier if enabled
            if props.use_tint:
                try:
                    tint_mod = ref_obj.modifiers.new(name="Light Table Tint", type='GREASE_PENCIL_TINT')
                    tint_mod.color = props.tint_color
                    tint_mod.factor = 1.0
                    print("Created Tint modifier")
                except Exception as e:
                    print(f"Warning: Could not create Tint modifier: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Set opacity
            ref_obj.color[3] = props.opacity
            
            # Set display properties
            ref_obj.show_in_front = props.show_in_front
            ref_obj.hide_render = True
            ref_obj.hide_select = True
            
            # Store reference
            source_obj["gph_light_table_ref"] = ref_obj.name
            
            # Tag for redraw
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            return True
            
        except Exception as e:
            print(f"Error creating light table reference: {e}")
            import traceback
            traceback.print_exc()
            return False


class GPH_OT_set_reference_frame(Operator):
    """Set current frame as reference"""
    bl_idname = "gph.set_reference_frame"
    bl_label = "Set Reference Frame"
    bl_description = "Set current frame as the light table reference"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_light_table_props
        props.reference_frame = context.scene.frame_current

        # Update if already enabled
        if props.enabled:
            bpy.ops.gph.update_light_table()

        self.report({'INFO'}, f"Reference frame set to {props.reference_frame}")
        return {'FINISHED'}


class GPH_OT_update_light_table(Operator):
    """Update light table display"""
    bl_idname = "gph.update_light_table"
    bl_label = "Update Light Table"
    bl_description = "Update light table reference with current settings"

    def execute(self, context):
        props = context.scene.gph_light_table_props
        source_obj = context.active_object

        if not props.enabled or not source_obj:
            return {'CANCELLED'}

        # Find reference object
        ref_obj_name = source_obj.get("gph_light_table_ref")

        if not ref_obj_name or ref_obj_name not in bpy.data.objects:
            # Reference doesn't exist, recreate
            bpy.ops.gph.toggle_light_table()
            bpy.ops.gph.toggle_light_table()
            return {'FINISHED'}

        ref_obj = bpy.data.objects[ref_obj_name]

        # Update opacity
        ref_obj.color[3] = props.opacity

        # Update show in front
        ref_obj.show_in_front = props.show_in_front

        # Update time offset modifier - use 'offset' attribute
        for mod in ref_obj.modifiers:
            if mod.type == 'GREASE_PENCIL_TIME' and mod.name == "Light Table Lock":
                mod.offset = props.reference_frame
                print(f"Updated Time Offset modifier to frame {props.reference_frame}")
                print(f"Time modifier offset value: {mod.offset}")

        # Update tint modifier
        for mod in ref_obj.modifiers:
            if mod.type == 'GREASE_PENCIL_TINT' and mod.name == "Light Table Tint":
                if props.use_tint:
                    mod.color = props.tint_color
                    mod.show_viewport = True
                else:
                    mod.show_viewport = False

        # Force viewport update
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}


class GPH_OT_clear_reference(Operator):
    """Clear light table reference"""
    bl_idname = "gph.clear_reference"
    bl_label = "Clear Reference"
    bl_description = "Disable and clear light table reference"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_light_table_props

        if props.enabled:
            bpy.ops.gph.toggle_light_table()

        props.reference_frame = 1

        self.report({'INFO'}, "Light table cleared")
        return {'FINISHED'}


class GPH_OT_jump_to_reference(Operator):
    """Jump to reference frame"""
    bl_idname = "gph.jump_to_reference"
    bl_label = "Jump to Reference"
    bl_description = "Jump timeline to reference frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_light_table_props
        context.scene.frame_set(props.reference_frame)
        return {'FINISHED'}