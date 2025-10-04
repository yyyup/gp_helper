"""
AniMate Pro - Animation Modifiers Module

This module provides a system for managing multiple F-curve modifiers as groups
with a unified interface using the GUI pins system.

Main Components:
- Property groups for storing modifier group data
- Operators for managing groups and modifiers
- UI components for user interaction
- Modal editing with GUI pins interface
"""

import bpy
from . import anim_modifiers
from . import anim_modifiers_operators
from . import anim_modifiers_ui

modules = (
    anim_modifiers,
    anim_modifiers_operators,
    anim_modifiers_ui,
)


# Register classes and properties
def register():
    for module in modules:
        module.register()


# Unregister classes and properties
def unregister():
    for module in reversed(modules):
        module.unregister()
