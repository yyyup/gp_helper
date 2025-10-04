import bpy
from .. import utils

from .. import __package__ as base_package


def dprint(*args):
    if bpy.context.preferences.addons[base_package].preferences.debug:
        print(*args)


def evaluate_amp_triggers(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences

    if prefs.jump_to_first_selected_keyframe and not prefs.jump_already_made:
        bpy.ops.anim.amp_move_playhead_to_first_selected_keyframe()
        prefs.jump_already_made = True
        dprint(f"Jumped to keyframe.")
