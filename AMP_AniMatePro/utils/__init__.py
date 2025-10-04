from .general import *
from .api import *
from . import (
    key,
    curve,
    insert_keyframes,
    operators,
    handlers,
    panel_picker,
    gui_pins,
    version_manager,
    test_sub_preferences,
)


modules = (operators, handlers, panel_picker, gui_pins, test_sub_preferences)


def register():
    for module in modules:
        # try:
        module.register()
        # except:
        #     pass


def unregister():
    for module in reversed(modules):
        try:
            module.unregister()
        except:
            pass


if __name__ == "__main__":
    register()
