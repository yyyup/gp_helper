import bpy
from .. import __package__ as base_package
from .customIcons import reload_icons


# --- Icon reload scheduling state ---
_ICON_RELOAD_MAX_ATTEMPTS = 3
_ICON_RELOAD_RETRY_INTERVAL = 0.5  # seconds
_icon_reload_attempts = 0
_icon_reload_done = False


def schedule_icon_reload(initial_delay: float = 1.0) -> None:
    """Register the delayed icon reload timer if not already registered.

    Does nothing if the reload has already completed.
    """
    global _icon_reload_attempts, _icon_reload_done
    if _icon_reload_done:
        return
    try:
        if not bpy.app.timers.is_registered(delayed_icon_reload):
            _icon_reload_attempts = 0
            bpy.app.timers.register(
                delayed_icon_reload,
                first_interval=initial_delay,
                persistent=True,
            )
    except Exception:
        # Safe to ignore in environments where timers aren't available yet
        pass


@bpy.app.handlers.persistent
def amp_on_file_load(dummy):
    schedule_icon_reload(initial_delay=1.0)


# Run at Blender startup (even when no file is loaded) where supported
@bpy.app.handlers.persistent
def amp_on_startup(dummy):
    schedule_icon_reload(initial_delay=1.0)


def delayed_icon_reload():
    """Try to reload icons and keep retrying briefly to resist user interaction timing.

    Returning a float schedules the next attempt; returning None stops the timer.
    """
    global _icon_reload_attempts, _icon_reload_done

    if _icon_reload_done:
        return None

    try:
        reload_icons()
        # Ensure UI refresh
        for screen in bpy.data.screens:
            for area in screen.areas:
                area.tag_redraw()
        # Success: mark done and stop further retries
        _icon_reload_done = True
        _icon_reload_attempts = 0
        return None
    except Exception:
        # Retry on error a few times with a short interval
        _icon_reload_attempts += 1
        if _icon_reload_attempts < _ICON_RELOAD_MAX_ATTEMPTS:
            return _ICON_RELOAD_RETRY_INTERVAL
        else:
            _icon_reload_attempts = 0
            return None


@bpy.app.handlers.persistent
# This function is called on each frame change after the scene has reached the end frame.
# It is registered as a persistent handler that checks conditions and potentially stops playback.
def amp_on_frame_change_post(dummy):
    screen = bpy.context.screen
    prefs = bpy.context.preferences.addons[base_package].preferences
    scene = bpy.context.scene

    if not screen or not screen.is_animation_playing or scene.frame_current != scene.frame_end:
        return

    active_obj = bpy.context.active_object

    should_stop = False

    if prefs.playback_loop_at_the_end:
        if prefs.playback_loop_only_if_cyclical:
            if active_obj and active_obj.animation_data:
                action = active_obj.animation_data.action
                if action and getattr(action, "use_cyclic", False):
                    return
                else:
                    should_stop = True
            else:
                should_stop = True
    else:  # playback_loop_at_the_end is off
        if prefs.playback_loop_only_if_cyclical:
            if active_obj and active_obj.animation_data:
                action = active_obj.animation_data.action
                if action and getattr(action, "use_cyclic", False):
                    return
                else:
                    should_stop = True
            else:
                should_stop = True
        else:
            should_stop = True

    if should_stop:
        bpy.ops.screen.animation_play()


def draw_playback_loop_at_the_end(self, context):
    prefs = bpy.context.preferences.addons[base_package].preferences
    layout = self.layout
    layout.use_property_split = True
    layout.use_property_decorate = False
    row = layout.row(align=True)
    row.prop(prefs, "playback_loop_at_the_end")
    loop_row = layout.row(align=True)
    loop_row.enabled = not prefs.playback_loop_at_the_end
    loop_row.prop(prefs, "playback_loop_only_if_cyclical")


def register() -> None:
    try:
        bpy.app.handlers.frame_change_post.remove(amp_on_frame_change_post)
        bpy.app.handlers.load_post.remove(amp_on_file_load)
    except ValueError:
        pass

    try:
        bpy.app.handlers.frame_change_post.append(amp_on_frame_change_post)
        bpy.app.handlers.load_post.append(amp_on_file_load)
    except ValueError:
        pass

    # Also register for factory startup if available (Blender triggers this on app start)
    if hasattr(bpy.app.handlers, "load_factory_startup_post"):
        try:
            bpy.app.handlers.load_factory_startup_post.remove(amp_on_startup)
        except ValueError:
            pass
        try:
            bpy.app.handlers.load_factory_startup_post.append(amp_on_startup)
        except ValueError:
            pass

    # Fallback: schedule an icon reload shortly after addon registers (covers cases where
    # startup handlers don't fire because the addon loads after the event or in dev setups)
    schedule_icon_reload(initial_delay=1.0)

    bpy.types.TIME_PT_playback.prepend(draw_playback_loop_at_the_end)


def unregister() -> None:

    bpy.types.TIME_PT_playback.remove(draw_playback_loop_at_the_end)

    try:
        bpy.app.handlers.frame_change_post.remove(amp_on_frame_change_post)
        bpy.app.handlers.load_post.remove(amp_on_file_load)
    except ValueError:
        pass

    # Unregister startup handler if present
    if hasattr(bpy.app.handlers, "load_factory_startup_post"):
        try:
            bpy.app.handlers.load_factory_startup_post.remove(amp_on_startup)
        except ValueError:
            pass

    # Attempt to unregister the timer to avoid lingering retries on addon disable
    try:
        if bpy.app.timers.is_registered(delayed_icon_reload):
            bpy.app.timers.unregister(delayed_icon_reload)
    except Exception:
        pass
