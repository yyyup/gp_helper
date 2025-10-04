# licence
"""
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

"""
CREDITS:

Original code for anim_offset from Ares Deveaux

Adaptation, fork  and maintenance to AniMate Pro by Nacho de Andres

"""

import bpy
from . import props, ops
from .support import (
    subscribe_to_autokeying_changes_anim_offset,
    unsubscribe_from_property_anim_offset,
)

classes = ops.classes + props.classes


# Register classes and properties
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    subscribe_to_autokeying_changes_anim_offset()


# Unregister classes and properties
def unregister():
    unsubscribe_from_property_anim_offset()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
