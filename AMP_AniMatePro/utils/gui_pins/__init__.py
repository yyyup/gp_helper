"""
GUI Pins Module for AniMate Pro

This module provides the ScopeGUI system for creating interactive
scope interfaces with influence pins and blending controls.
"""

from .gui_pins import (
    ScopeGUI,
    ScopePin,
    IntensityHandler,
    BlendSelector,
    BlendType,
    OperationSelector,
    StandaloneFactor,
)
from .example_operator import create_scope_gui, AMP_OT_scope_gui_example
from .gui_roundedbox import RoundedBoxDrawer

__all__ = [
    "ScopeGUI",
    "ScopePin",
    "IntensityHandler",
    "BlendSelector",
    "BlendType",
    "OperationSelector",
    "StandaloneFactor",
    "graph_to_screen",
    "screen_to_graph",
    "create_scope_gui",
    "AMP_OT_scope_gui_example",
    "RoundedBoxDrawer",
]


# Registration for the example operator
def register():
    """Register the gui_pins module."""
    from . import example_operator

    example_operator.register()


def unregister():
    """Unregister the gui_pins module."""
    from . import example_operator

    example_operator.unregister()
