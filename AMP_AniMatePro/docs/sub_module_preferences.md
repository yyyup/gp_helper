# Sub-Module Preferences Integration System

This system allows sub-modules within the AniMate Pro addon to define their own preferences that are automatically integrated into the main addon preferences. This provides a centralized place to access all preferences while allowing modules to define their own settings.

## How It Works

1. **Automatic Scanning**: During addon registration, the system scans through all directories looking for `preferences.py` files
2. **Property Integration**: Properties from sub-module preferences are extracted and added to the main `AMP_Preferences` class with a module prefix
3. **Centralized Access**: All preferences can be accessed through the main addon preferences, but with helper functions for easy sub-module access

## Creating Sub-Module Preferences

To create preferences for a sub-module, create a `preferences.py` file in your module directory:

```python
# Example: forge_modules/my_module/preferences.py
import bpy
from bpy.types import AddonPreferences
from bpy.props import FloatVectorProperty, BoolProperty

class AMP_Preferences(AddonPreferences):
    bl_idname = __package__

    my_color: FloatVectorProperty(
        name="My Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 0.0, 0.0),
        description="A color setting for my module",
    )

    my_enabled: BoolProperty(
        name="Enable Feature",
        description="Enable this module's feature",
        default=True,
    )
```

## Accessing Sub-Module Preferences

### From Sub-Module Code

Use the helper functions from `utils.submodule_preferences`:

```python
from ...utils.submodule_preferences import get_submodule_preference, set_submodule_preference

# Get a preference value
my_color = get_submodule_preference('my_module', 'my_color', (1.0, 0.0, 0.0))
my_enabled = get_submodule_preference('my_module', 'my_enabled', True)

# Set a preference value  
set_submodule_preference('my_module', 'my_enabled', False)
```

### From Main Addon Code

Access directly through the main preferences:

```python
from .utils import get_prefs

prefs = get_prefs()
# Access with module prefix
my_color = prefs.my_module_my_color
my_enabled = prefs.my_module_my_enabled
```

## Property Naming Convention

When properties are integrated, they are prefixed with the module name to avoid conflicts:

- Original property: `my_color`  
- Integrated property: `my_module_my_color`

The module name is derived from the directory structure. For example:
- `forge_modules/anim_onionskinning/preferences.py` → prefix: `anim_onionskinning`
- `modules/my_feature/preferences.py` → prefix: `my_feature`

## Helper Functions

### `get_submodule_preference(module_name, property_name, default=None)`
Get a preference value with automatic prefix handling.

### `set_submodule_preference(module_name, property_name, value)`
Set a preference value with automatic prefix handling.

### `has_submodule_preference(module_name, property_name)`  
Check if a preference exists.

### `list_submodule_preferences(module_name)`
List all preferences for a specific module.

## Example Usage in UI

```python
def draw_my_module_ui(self, context, layout):
    from ...utils.submodule_preferences import get_submodule_preference
    
    # Get current values
    my_color = get_submodule_preference('my_module', 'my_color', (1.0, 0.0, 0.0))
    my_enabled = get_submodule_preference('my_module', 'my_enabled', True)
    
    # Draw UI elements
    # Access main prefs directly for UI binding
    prefs = context.preferences.addons[__package__].preferences
    layout.prop(prefs, "my_module_my_color")
    layout.prop(prefs, "my_module_my_enabled")
```

## Benefits

1. **Modular**: Each module can define its own preferences
2. **Centralized**: All preferences are accessible from one place
3. **Conflict-Free**: Automatic prefixing prevents naming conflicts
4. **Easy Integration**: Just create a `preferences.py` file in your module
5. **Backwards Compatible**: Existing code continues to work

## Implementation Details

The system consists of:

- `utils/preferences_scanner.py`: Core scanning and integration logic
- `utils/submodule_preferences.py`: Helper functions for accessing preferences
- Modified `preferences.py`: Calls integration during registration

The integration happens during addon registration, before the preference classes are registered with Blender.
