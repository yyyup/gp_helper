import bpy
from bpy.types import Operator

class GPH_OT_dissolve_setup(Operator):
    bl_idname = "gph.dissolve_setup"
    bl_label = "Setup Dissolve Keyframes"
    bl_description = "Automatically setup opacity keyframes for dissolve effect"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gph_dissolve_props

        print("=== DEBUGGING GP OBJECT DETECTION ===")
        print(f"Active object: {context.active_object}")
        if context.active_object:
            print(f"Active object type: {context.active_object.type}")

        print(f"Selected objects: {context.selected_objects}")
        print(f"Scene objects: {[obj.name + '(' + obj.type + ')' for obj in context.scene.objects]}")

        gp_obj = None

        if context.active_object and context.active_object.type == 'GREASEPENCIL':
            gp_obj = context.active_object
            print(f"Found GP object via active: {gp_obj.name}")

        if not gp_obj:
            for obj in context.selected_objects:
                if obj.type == 'GREASEPENCIL':
                    gp_obj = obj
                    print(f"Found GP object via selection: {gp_obj.name}")
                    break

        if not gp_obj and hasattr(context, 'object') and context.object:
            if context.object.type == 'GREASEPENCIL':
                gp_obj = context.object
                print(f"Found GP object via context.object: {gp_obj.name}")

        if not gp_obj:
            gp_objects = [obj for obj in context.scene.objects if obj.type == 'GREASEPENCIL']
            print(f"All GP objects in scene: {[obj.name for obj in gp_objects]}")
            if gp_objects:
                gp_obj = gp_objects[0]
                self.report({'WARNING'}, f"Using first GP object found: {gp_obj.name}")

        if not gp_obj:
            self.report({'ERROR'}, "No Grease Pencil object found. Check console for debug info.")
            return {'CANCELLED'}

        print(f"Using GP object: {gp_obj.name}")
        print("=== END DEBUG ===")

        gp_data = gp_obj.data

        layer1 = None
        layer2 = None

        for layer in gp_data.layers:
            if layer.name == props.layer1_name:
                layer1 = layer
            elif layer.name == props.layer2_name:
                layer2 = layer

        if not layer1:
            self.report({'ERROR'}, f"Could not find layer '{props.layer1_name}'")
            return {'CANCELLED'}

        if not layer2:
            self.report({'ERROR'}, f"Could not find layer '{props.layer2_name}'")
            return {'CANCELLED'}

        if not gp_data.animation_data:
            gp_data.animation_data_create()
        if not gp_data.animation_data.action:
            gp_data.animation_data.action = bpy.data.actions.new(name="GPencilDissolveAction")

        action = gp_data.animation_data.action
        fcurves_to_remove = []

        for fcurve in action.fcurves:
            if (fcurve.data_path == f'layers["{props.layer1_name}"].opacity' or
                fcurve.data_path == f'layers["{props.layer2_name}"].opacity'):
                fcurves_to_remove.append(fcurve)

        for fcurve in fcurves_to_remove:
            action.fcurves.remove(fcurve)

        layer1_fcurve = action.fcurves.new(
            data_path=f'layers["{props.layer1_name}"].opacity'
        )
        layer2_fcurve = action.fcurves.new(
            data_path=f'layers["{props.layer2_name}"].opacity'
        )

        frame = 0
        while frame <= props.total_frames:
            if frame % props.cycle_length == 0:
                layer1_fcurve.keyframe_points.insert(frame, 0.0)
                layer2_fcurve.keyframe_points.insert(frame, 1.0)
            elif frame % props.cycle_length == (props.cycle_length - 1):
                layer1_fcurve.keyframe_points.insert(frame, 1.0)
                layer2_fcurve.keyframe_points.insert(frame, 0.0)

            frame += 1

        for fcurve in [layer1_fcurve, layer2_fcurve]:
            fcurve.update()
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = 'LINEAR'

        self.report({'INFO'}, f"Successfully set up dissolve keyframes for {len(layer1_fcurve.keyframe_points)} frames")
        return {'FINISHED'}


class GPH_OT_dissolve_refresh(Operator):
    bl_idname = "gph.dissolve_refresh"
    bl_label = "Refresh Layer Names"
    bl_description = "Auto-populate layer names from active Grease Pencil object"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.gph_dissolve_props

        gp_obj = None

        if context.active_object and context.active_object.type == 'GREASEPENCIL':
            gp_obj = context.active_object

        if not gp_obj:
            for obj in context.selected_objects:
                if obj.type == 'GREASEPENCIL':
                    gp_obj = obj
                    break

        if not gp_obj:
            for obj in context.scene.objects:
                if obj.type == 'GREASEPENCIL':
                    gp_obj = obj
                    self.report({'WARNING'}, f"Using GP object: {obj.name}")
                    break

        if not gp_obj:
            self.report({'WARNING'}, "Please select a Grease Pencil object")
            return {'CANCELLED'}

        layers = list(reversed(gp_obj.data.layers))  # Reverse to match GP layers panel display order
        if len(layers) >= 1:
            props.layer2_name = layers[0].name  # Base Layer (top in UI) gets top GP layer
        if len(layers) >= 2:
            props.layer1_name = layers[1].name  # Dissolve Layer (bottom in UI) gets second GP layer

        self.report({'INFO'}, f"Found {len(layers)} layer(s)")
        return {'FINISHED'}