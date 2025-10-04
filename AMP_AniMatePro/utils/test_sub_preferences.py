"""
Test operator to demonstrate sub-module preferences integration
"""

import bpy
from bpy.types import Operator


class AMP_OT_TestSubPreferences(Operator):
    """Test operator to demonstrate sub-module preferences access"""

    bl_idname = "amp.test_sub_preferences"
    bl_label = "Test Sub-Module Preferences"
    bl_description = "Test accessing sub-module preferences from the main addon"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from ..utils.submodule_preferences import (
            get_submodule_preference,
            set_submodule_preference,
            list_submodule_preferences,
            has_submodule_preference,
        )
        from ..utils import get_prefs

        # Test accessing onion skinning preferences (if they exist)
        module_name = "anim_onionskinning"

        # Check if the preferences were integrated
        if has_submodule_preference(module_name, "before_color"):
            before_color = get_submodule_preference(module_name, "before_color", (1.0, 0.0, 0.0))
            after_color = get_submodule_preference(module_name, "after_color", (0.0, 0.0, 1.0))

            self.report({"INFO"}, f"Onion Skinning Before Color: {before_color}")
            self.report({"INFO"}, f"Onion Skinning After Color: {after_color}")

            # List all preferences for this module
            all_prefs = list_submodule_preferences(module_name)
            self.report({"INFO"}, f"All {module_name} preferences: {all_prefs}")

            # Test direct access through main preferences
            main_prefs = get_prefs()
            if hasattr(main_prefs, f"{module_name}_before_color"):
                direct_before = getattr(main_prefs, f"{module_name}_before_color")
                self.report({"INFO"}, f"Direct access before_color: {direct_before}")

        else:
            self.report({"WARNING"}, f"Sub-module preferences for {module_name} not found")

            # List all available properties to see what was integrated
            main_prefs = get_prefs()
            integrated_props = [
                attr
                for attr in dir(main_prefs)
                if not attr.startswith("_") and "_" in attr and not attr in ["bl_idname", "bl_rna", "rna_type"]
            ]

            if integrated_props:
                self.report({"INFO"}, f"Found integrated properties: {integrated_props[:10]}...")  # Show first 10
            else:
                self.report({"INFO"}, "No integrated sub-module properties found")

        return {"FINISHED"}


# Test panel to access the operator
class AMP_PT_TestSubPreferences(bpy.types.Panel):
    """Panel to test sub-module preferences"""

    bl_label = "Sub-Module Preferences Test"
    bl_idname = "AMP_PT_test_sub_preferences"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AMP Test"

    def draw(self, context):
        layout = self.layout

        # Button to test preferences access
        layout.operator("amp.test_sub_preferences")

        # Show some integrated preferences if they exist
        from ..utils import get_prefs

        prefs = get_prefs()

        # Try to show onion skinning preferences
        if hasattr(prefs, "anim_onionskinning_before_color"):
            box = layout.box()
            box.label(text="Onion Skinning Preferences:")
            box.prop(prefs, "anim_onionskinning_before_color", text="Before Color")
            box.prop(prefs, "anim_onionskinning_after_color", text="After Color")


classes = [
    AMP_OT_TestSubPreferences,
    AMP_PT_TestSubPreferences,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass


if __name__ == "__main__":
    register()
