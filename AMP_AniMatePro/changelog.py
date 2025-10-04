# ICONS
# **KEYTYPE_KEYFRAME_VEC** Highlights
# —————————————————
# **FUND** New features
# —————————————————
# **USER** Feature Improvements
# —————————————————
# **CHECKBOX_HLT** Fixed
# —————————————————

# ***AMP_anim_baker***
# ***AMP_anim_cam_step***
# ***AMP_anim_keyposer***
# ***AMP_anim_lattice***
# ***AMP_anim_loop***
# ***AMP_anim_mopaths_off***
# ***AMP_anim_mopaths_on***
# ***AMP_anim_nudge_L***
# ***AMP_anim_nudge_R***
# ***AMP_anim_offset_mask_on***
# ***AMP_anim_offset_mask_tweak***
# ***AMP_anim_offset_mask***
# ***AMP_anim_offset_start_on***
# ***AMP_anim_offset_start***
# ***AMP_anim_retimer***
# ***AMP_anim_sculpt***
# ***AMP_anim_shift***
# ***AMP_anim_slice***
# ***AMP_anim_step***
# ***AMP_anim_timewarper***
# ***AMP_curves_cleanup***
# ***AMP_curves_euler***
# ***AMP_curves_gimbal***
# ***AMP_frame_action***
# ***AMP_handles_all***
# ***AMP_handles_off***
# ***AMP_handles_on***
# ***AMP_handles_selected***
# ***AMP_keyframer***
# ***AMP_markers_delete_all***
# ***AMP_markers_lock***
# ***AMP_markers_tools***
# ***AMP_markers_unlock***
# ***AMP_match_keys_L***
# ***AMP_match_keys_R***
# ***AMP_next_keyframe***
# ***AMP_pose_range_copy***
# ***AMP_pose_range_paste***
# ***AMP_prev_keyframe***
# ***AMP_scrubber_on***
# ***AMP_scrubber***
# ***AMP_select_curves_all***
# ***AMP_select_curves_const***
# ***AMP_select_curves_loc***
# ***AMP_select_curves_others***
# ***AMP_select_curves_rot***
# ***AMP_select_curves_scale***
# ***AMP_select_curves_shapes***
# ***AMP_share_keyframes***
# ***AMP_solo_curve_off***
# ***AMP_solo_curve_on***
# ***AMP_zoom_curve_all***
# ***AMP_zoom_curve_selecte***


changelog = {
    "Next Release": """
**KEYTYPE_KEYFRAME_VEC** Highlights
—————————————————
- New UI overhaul for AniMate Pro.
- New Action Swapper UI.
- New Selection Sets GUI.
- Anim Offset mask GUI.
- New Time Blocker.
- New Time Visualizer.
- New Curve Tools.
- Support for NLA and offset tracks.

**FUND** New Features
—————————————————
- UI Overhaul:
    - New completely customizable To bar buttons and side panels.
        - Independent suppoport for the 3D View, Graph Editor, Dopesheet and NLA side panels, as well as for the corresponding top bars of the editors.
        - Introducing categories and sections to btter organize the differnt UI elements.
        - Full copy, share, and paste configurations for the UI.
        - Support for custom script.
    - Popup panels: create them with the same tools that you use to create the rest of the UI.
        - Same display language and configuration as the side panels.
        - You can copy and paste the categories from the normal UI to the pie menu.

- New Action Swapper UI:
    A better UX to assign and manage actions on the selected objects. Can be found on the Side Panels (View3d, Graph and Dope Editors).
    - Action swapper UI (change active aciton, manage slots, merge or separate slots, zoom to aciton on all editors...)
    - Change name, Number of users, Fake User flag, duplicate, unlink, delete from scene.
    - Manage the main Properties of the action (Cyclic, Manual frame range...)
    - Action Custom Properties.

- New Time Blocker:
    Manage the timing of your keyframes in the graph editor as easily as if you were in the dopesheet.

- New Time Visualizer:
    Visualize the time in any editor even when displaying only the frames.
    - Smart view that will display time in seconds or minutes based on the zoom level.
    - Fully customizable positioning, colors, size, and elements.
    - Available as a toggle and visible in the Graph, Dopesheet, NLA, and VSE.
    
- New GUI for Selection Sets:
    Selection sets can now have a draggable GUI directly on the animation editors or the 3D viewport.

-  New Curve Tools:
    - All existing modes and some more from the animaide addon brought to AniMate Pro.
    - New UI interface to control blending of the curves.

- New NLA offset strips support:
    Included support for offset strips in the NLA when editing them in tweak mode. All operators should work while editing tracks that are offset (scaled tracks may not work for all scenarios). The supported tools now are: Anim Slicer, Anim Shifter, Anim Sculpt, Anim Lattice, Anim TimeWarper, Jump to Keyframe, AnimNudger, and AnimPusher.

**USER** Feature Improvements
—————————————————
- Anim Slicer and Anim Shifter will now pop up the operator dialogues by default.
- Anim Slicer "Frame Start" renamed to "Start Offset" so it is clearer that it will shift that number of frames from the start of the range.
- Anim Slicer now supports presets.
- While using the Isolate Transform curves will cycle trhough the channels in a predictable order ( X > Y > Z (> W) ).
- Loop only if cyclical preference can now be easily toggled on/off on the action menu header.
- Selection sets can now be configured directly from the popover menu.
- Flex MoPaths is now called by the much more sensible name of Offset MoPaths.
- ALT  A during timewarper will add pins on every selected keyframe ( and clear current ones ), if no keyframes selected add keyframe at the playhead.
- The Isolate F-Curves preference in the selection curves dropdown will correctly determine if the curves should be isolated or not when using the selection operators.



**CHECKBOX_HLT** Fixed
—————————————————
- Icons should not appear as blank if the grap editor is not open while opening a new file.
- Action dropdown was not displaying on the Graph editor in Blender versions earlier than 4.2 so I reworked the feature and implemented a whole new system.
- The Scrubbing preferences display properly now even if the default scene has a different name than "Scene".
- Some keyframe types were not being offset correctly in the anim Shifter.
- GUI text on TimeWarper tweaks.
- Operations that used frame_set are not using a different method to avoid scrubbing breaking under certain scene circumstances.
- Pressing the delete key while scrubbing (X by default) during Markers (hold CTRL) or Keyframes (hold SHIFT) modes will correctly delete all keyframes or markers in the current frame.
- Isolate Character will now correctly isolate the armature and all the meshes associated with it even in more complex files and scenes. Exiting isolation will restore the previous outliner state.
- Convert rotation to Euler will now work correctly and not return an error.
- Anim Slicer will not return an error when using it and deselecting fcurves in the dopesheet editor.
- Subdivide timeline by markers will aproximate values to full frames to avoid having markers on subframes or errors.
- Easings are not correctly storing an undo buffer during timewarper.
- When using nudger or pusher during scrubbing with no object or bones selected it should inform the user instead of returning an error.
- Realtime looper will not interfere with anim offset when it is active.

""",
    "0.25.10318": """
**KEYTYPE_KEYFRAME_VEC** Highlights
—————————————————
- Initial implementation for support for 4.4 slotted actions and backwards compatibility.

**FUND** New features
—————————————————
- Support for 4.4 slotted actions and backwards compatibility down to 4.0

**USER** Feature Improvements
—————————————————
***AMP_silhouette_on*** Silhouette and Isolate character:
    - Improvements to the logic to isolate the character and all the associated objects.
    - Due to some limitations in Blender when entering the isolation state a new temporary view layer will be created, that will be removed on exiting the isolation (through Silhouette or Isolate Character).

***AMP_curves_gimbal*** Recommended Rotation Mode:
    - Ranked recommendations.
    - Euler recommendations even when in quaternion.
    - Keeping the frame position after calculated and baking modes.
    - Discontinuity filter after Euler bake for good measure.

**Action** 
- Improvements to the action panel and how the action slots are displayed from Blender 4.0 to 4.4

**CHECKBOX_HLT** Fixed
—————————————————
- Improvements on how some functions interact with NLA strips that have an offset.

""",
    "0.25.10318": """
**KEYTYPE_KEYFRAME_VEC** Highlights
—————————————————
- Selection Sets to store and recall selections of bones, objects, lights, or cameras.
- New Buttons to change between the animation editors.
- Realtime Looper will ensure continuity within fcurves start and end keyframes and handles.

**FUND** New features
—————————————————
***AMP_select_sets*** Selection Sets:
    - New feature to save and load selection sets for the selected elements (bones, objects, lights or cameras).
    - Store and recall the selections with a simple click. 

***AMP_realtimelooper_off*** Realtime Looper:
    - When enabled it will maintain the continuity of the fcurves within the start and end keyframes and handles.
    - Should work with all other tools but it may conflict with some of them if they try to compete for updating the keyframe or handle values as they are changed.

**GRAPH** Animation Editors:
    - New buttons to change between the animation editors (Graph, Dopesheet, Timeline, NLA, Drivers, Mask...)
    - Fully configurable and customizable in the preferences or top bar buttons.
    - Highlighted the current editor in the corresponding button.

***AMP_anim_timewarper*** Time Warper:
    - By default markers will move with the keyframes while dragging pins and bars.
    - If the existing markers have the frame number as a suffix they will be updated to the new frame number.
    
**NLA** NLA Editor:
    - AnimSculpt and Anim Lattice will correctly take into account the offset of the NLA strip if it is not on frame 0.

**USER** Feature Improvements
—————————————————
***AMP_anim_sculpt*** Anim Sculpt:
    - The average function (CTRL SHIFT) will now work as originally intended:
        - If visible keyframes selected it will smooth to the verage value.
        - if no keyframes are selected it will smooth to each individual's curve default value.
        
***AMP_anim_slice*** Anim Slicer:
    - The logic for full frame slicing has been improved and overcomes the rounding errors that Blender has when trying to slice a frame that is too close to a full frame.
    - General improvements to the range calculation when "selected range" is chosen.

***AMP_share_keyframes*** Share Keyframes:
    - New shared keyframes will be of type bezier and autoclamped by default.

***AMP_silhouette_on*** Silhouette:
    - New smart behaviour: when armatures are selected or in pose mode pressing the button will isolate the armature and all the meshes associated with it. Exiting isolation will restore the previous outliner state.


**CHECKBOX_HLT** Fixed
—————————————————
- Some panels from Realtime MoPaths and Flex Mopaths will now be correctly assigned to the correct sections in the 3d viewport.
- Improvements to the undo system in timwarper and anim lattice to be more reliable and don't double stack.
- Some panels were returning errors in 4.1, now the blender features that were introduced in 4.2+ will only be displaying on the correct version.
- Some fixes to AnimStepper though it will be deprecated when StepMotionator is released.
- Changing to the Dopesheet editor while in the middle of a lattice operation will not end up in an error.

""",
    "0.24.1224": """

**KEYTYPE_KEYFRAME_VEC** Highlights
—————————————————
- Anim sculpt: improved smoothing behaviour.
- New: Anim Flex MoPaths.
- New: Silhouette viewport toggle.

**FUND** New features
—————————————————
***AMP_silhouette_on*** Silhouette:
    - New feature to toggle the silhouette of the objects in the viewport. This will help to see the shapes of the objects in the viewport without the need to go to the viewport settings.
    - Users can choose to hide the button and or change the foreground and background colors in the preferences.
    
***AMP_flexmopaths_on*** Flex MoPaths:
    - New feature to choose selected bones or objects and create mopaths from Empties to be able to ofset the motion paths dynamically from any point in the scene relative to the element.

**USER** Feature Improvements
—————————————————
***AMP_anim_sculpt*** Anim Sculpt:
    - Improvements to the smoothing algorithm to better acount for keyframes that are further appart when smoothing achieving much more accurate results.
    - The new smoothing factor lowers or doubles the smoothing effect. Default to 1.0.
    
***AMP_inbetween_add*** Anim Inbetween rebranded to Anim Pusher:
    - THe Inbetweener name was misleading as it adds space between keyframes but not inbetween keyframes. So it was rebranded to Anim Pusher. The name is more intuitive because it "pushes" the keyframes around generating space.

***AMP_isolate_char_on*** Isolate Character:
    - Only visible objects when entering pose mode that fulfill the conditions will be isolated.
    - In an upcomming build users will be able to decide which objects that are pointing to the armature as children, modifiers, or constrains, will be included. No plans to expand selections for this beyond that level of complexity for now.

UI Arrangements:
    - All modules that perform actions on animations are consolidated under the Actions section (Sculpt, Lattice, TimeWarper, Loop, Slice, Shift, Step, Camera Step).
    - New section called Motion (Isolate Character, Flex MoPaths and Realtime Mopaths).

**CHECKBOX_HLT** Fixed
—————————————————
    - General optimizations in the code.
    - Clean up of several parts of the Preferences and UI.
    - When the sections or buttons are rearranged they should now correctly display in the right section or be correctly removed without displaing an error icon.

""",
    "0.24.1216": """

***AMP_isolate_char_on*** Isolate Character:
    - New feature that adds a toggle to automatically isolate the armatures and all meshes associated with them through modifiers or constraints when entering pose mode. This will greatly improve performance when animating and working in complex scenes. You can still toggle the visibility of the rest of the collections on or off as needed in this mode, but when you leave pose mode the previous state will be restored.
    - If you want o add some elements to always display with the character in isolation you can add a modifier or constraint to the objects and point it to the armature.

***AMP_inbetween_add*** Anim Inbetween:
    - New operator to add inbetween frames shifting keyframes around.
    - Add will always shift the animation right by one frame per press. And increase the range of the scene acordingly so you dont have to do this manually when blocking.
    - Remove will shift all the frames to the right of the playhead left, unless the current frame has keyframes, and then it will tell you that it cant do that to not destroy the animation. This will shift the end of the scene range as well to match the change.

***AMP_anim_timewarper*** Time Warper:
    - Time Warper will change the color of the graph editor / dopesheet bar when active. Configurable in the preferences.
    - Time Warper operations can now be undoed and redone while is active.

***AMP_anim_slice*** Anim Slicer:
    - Several improvements on how the operator works internally.
    - New slicing methods:
        - Slice to closest full frame: will remove all subframes keeping the curve values exactly as they are in the current frames.
        - Slice to stored slice frames:
            - CTRL click the operator with any number of Fcurves selected to store the current frames where they have keyframes.
            - when slicing to stored frames all other curves affected will get keyframes on the stored frames.
            - This is great to share frames between different curves, optionally removing the other keyframes.

***AMP_anim_shift*** Anim Shifter:
    - When shifting frames the scene range will expand to include the new frames (limited by frame 0 when adding them negatively if the option to allow negative frames in blender is not enabled).

***AMP_anim_loop*** Anim Loop:
    - Hold SHIFT to pop up the options before the operator is executed.
    - The default handles and interpolation for the looped keyframes in the interval are now set to no change.
    - Option to turn on cycle aware.
    - Ability to choose range:
        - "Active": manual frame range > preview > scene
        - Min/max action.
        - Mix/Max per fcurve.
    - Option to insert frames on the start and end of the range.

***AMP_anim_sculpt*** Anim Sculpt:
    - Changed the behabiour and UX when scaling the Brush or Blend radius or tweaking the strength. Now the brush will not move when adjusting and will be more responsive.
    - The smooth and average brushes now have a clearer Strength reduction factor in %. Default to 1% (almost no reduction) and max of 90% (almost no smoothing). This is done to preserve the strength as it is shared amongst the three existing modes (Tweak, Smooth, Average). Default reduction to 25%.
    - Anim Sculpt will not return an error in certain cases when sculptin on an NLA action.
    
**USER** UX/UI improvements:
    - Most operators now will accept the SHIFT key to pop up the options before executing the operator.
    - The top bar buttons will now properly update keeping the preferences if the definitions are changed by the developer (if a button that was not allowed in the dopesheet but now the functionality is expanded the button will be refreshed without resetting the preferences of the user).
    - Delete markers will not delete selected markers if any, if not it will delete all markers. Optionally, and by default, the camera markers will be preserved.
    - Anim Lattice will change to nor normalized view if the view was normalized, zoom to the selected keyframes and give some padding for the edits. It will automatically return to normalized view when is done if it was active before.

***AMP_anim_step*** Anim Stepper:
    - Anim Stepper and Anim Camera Stepper are branching out to its own addon to continue to grown into their own Stop Motion full solution. If you are interested in beta access request it in Discord to me in a PM.
    - Some tweaks and fixes were implemented on the latest version that remains in the addon for now.

**CHECKBOX_HLT** Fixed:
    - Fixed an issue with Anim Sculpt when using it with setups on layers in the NLA.
    - Fixed an issue with Realtime Motion Paths where sometimes attempted to insert a keyframe on a locked transform.
    - When toggling autokey even through the native blender button the autokeying extra alerts on the different views should display immediately now.
    - Dozens of other small fixes and improvements.
    
""",
    "0.24.1203": """
    ***AMP_anim_sculpt*** Anim Sculpt:
    - 2-10x performance boost on the sculpting of keyframes (migrated the code to numpy).
    - Improved handling of rotation keyframes ixn Radians. Now they should perform exacly as any other type of curve regardless of them being euler rotations (works as well with other types of curves).
    - Improved the user experience when scaling the Radius, Blend and Strength sizes dynamically. Now the brush doesnt move and is much more responsive while adjusting.
    
    ***AMP_anim_shift*** Anim Shifter:
    - Improved the way hold frames are handled and introduced a new option to add or not frames on the slice frame.
    - When neither add keyframe on slice or add hold keyframe are on you will simply shift the afected animations (object, selected, or whole scene).
    - When add keyrame on slice is on: the frame that is being pushed will get a keyframe.
    - When add hold keyframe, the frame that is being kept will get a keyframe.
    - Now works with animated materials and Grease pencil frames when shifting frames.
    
    ***AMP_share_keyframes*** Share Keyframes:
    - Improved the efficiency of the operator and fixed a small issue when sharing keyframes between objects and armatures.
    ***AMP_anim_mopaths_on*** Realtime Motion Paths:
    - Small imrpovements to the quick buttons, now behaving as expected.
    - Realtime motion paths now work while Anim Offset without inserting new keyframes.
    
""",
    "0.24.1130": """
***AMP_anim_offset_start*** Anim Offset:
    - Quick Anim Offset Mask: When Scrubbing and pressing the Quick Anim Offset hotkey (G by default) anim offset will be toggled on and off. When is on, holding the Mask Range (M) will create the quick range left and right, after that you can create the quick blend range holding B.

**USER** UX/UI improvements:
    - Fixed an issue with the icons on the Timeline scrubbing preferences.

**CHECKBOX_HLT** Fixed:
    - Fixed the mask Range for Anim Offset during quick mask. Now it can be correctly dragged to create an offset left and right of the current frame.
    - Minor Fixed on Realtime Motion Paths toggle paths buttons.
    
""",
    "0.2.5": """
**FUND** New features:

    ***AMP_anim_baker*** Anim Baker (sleved):
        - A tool to bake the animation from the current shape of  the F-Curves of selected channels.
        - Bake channels based on the selected scope:
            - All Visible Channels.
            - Selected Channels.
            - Active object.
            - NLA Strips (WIP)

  ***AMP_anim_retimer*** Anim Retimer:
    - A tool to retime the animation from one frame rate to another.

  ***AMP_anim_cam_step*** Camera Stepper:
    - A tool to programatically add and update as needed the step animation of individual objects or the whole scene, non destructive animation in 2s, 3s, 4s...
    - Works for objects or armatures.

    - New panels in the View, Graph and Dope editors.

**USER** UX improvements:
    - Match to left and right will now match to the nearest keyframe instead of the first or last keyframe from the selected range.Match to left and right will now match to the nearest keyframe instead of the first or last keyframe from the selected range.Match to left and right will now match to the nearest keyframe instead of the first or last keyframe from the selected range.

**CHECKBOX_HLT** Fixed:
    - Countless elusive pesky bugs have been squashed.
""",
    "0.2.4": """
**FUND** New features:
***AMP_anim_sculpt*** Anim Sculpt:
    - Renamed from the keyframe sculptor for naming consistency.
    - Full implementation working for all kinds of curves (including EULER)
    
***AMP_anim_shift*** Anim Shifter:
  - Shift the current animation by a certain amount of frames (positive or negative):
    - Shift all scene or only selected objects.
    - Shift all curves or only selected.
    - Add a hold frame at both ends of the shift to keep the animation still on the shift frames.
        
***AMP_anim_poser*** Anim Poser:
  - Propagate a pose over a certain range of keyframes or copy values to all keyframes matching the furthest left or keyframe from the selected.
    - Two new operators with three different options:
        - Paste Pose to Range:
            - It will paste the copied pose in the selected range (preview, selected keyframes, all)
        - Propagate values (left or right)
            - it will paste the value of the left or right most keyframe from the selected keyframes to all the curves with selected keyframes.
        
***AMP_anim_step*** Anim Stepper:
- A tool to programatically add and update as needed the step animation of individual objects or the whole scene, non destructive animation in 2s, 3s, 4s...
  
- Marker Tools:
  Insert markers based for a chosen range with different criterias.
    Within a chosen range:
    - Divide chosen range in the timeline in  a number of spaces divided by markers.
    - Add a marker every X frames.
  
UX improvements:
- Added the abilty to need LMB for scrubbing.

UI improvements:
- Added buttons for most tools on the top bar of the editors. This will be configurable in a future release.
  
Bug Fixed:
- Fixed an issue with isolating mode crashing blender.
  
""",
    "0.2.2": """
New features:
- Anim Slicer:
  A tool to add “cuts” in  a range of frames for the current action given a given criteria for the selected transform channels or available.
    - Range:
        - Limit to selected preview range.
        - Use the whole action regardless of the preview range.
        - Use only the keyframes in between the keyframes selected.
    - Criteria:
        - Add keyframes to markers only.
        - Add keyframes to every X frames only.
        - Add keyframes to every X frames AND markers.
        - Clear all other frames WITHIN the selected range that are not
        Markers or Step frames (or both, depending on what you choose).
    - You can key:
        - Available if nothing is selected in the toggles
        - Loc
        - Rot
        - Scale
        - Custom Props
""",
    "0.2.1": """
New features:
- Keyframe Sculpt:
    - Tweak keyframes with a very similar experience to how you sculpt on a mesh.
    - Works in the graph editor, default key Y.
    - Control Radius, Strength, and Falloff.
    - Hold shift to smooth the keyframes (experimental).

- Autokeying addon has been fully merged into Timeline Tools.
    - Hotkey: configurable hotkey to toggle autokeying.
    - Display visual aids to show when autokeying is active.
    - Text: configurable text in the 3D View.
    - Frame: configurable frame in the 3D View, Dopesheet,
      Graph Editor and NLA.
""",
    "0.2.0": """
New features:
- AnimOffset from AnimAide has been revived and reworked.
    - AnimOffset with or without mask.
    - Blend ranges for mask.
    - if keyframes are selected the mask will automatically be applied to the selected keyframes.
    
- Quick AnimOffset (directly in scrubbing mode)
    - Press "G" to enable / exit.
    - Drag mouse left and right to move mask.
    - Shift + drag mouse left and right to move blend range.
    - Note: scrubbing is disabled during this mode.
    
- The Insert keyframe has been reworked (4.1+ only):
    - Holding "I" or pressing "I" and "Shift" will now display a menu.
    - In this menu you can select the current key insertion mode.
    - When pressing "I" you will insert a keyframe with the chosen mode.
    - Separate seetings for 3D View, Graph Editor and Dopesheet.

- Magic Clean-up (reworked from Clear Locked Transforms):
    - Delete Locked: deletes all fcurves from locked transform channels.
    - Reset to default values: will restore the locked transform channels to default values.
    - Delete Unchanged: deletes all the redundant keyframes that do not contribute to the animation.
    - Cleanup Keyframes: deletes any channel that contains keys but is on default values.
    
Bug Fixed:
    - Scrubbing now works in multi window setups, though the graphics at the cursor in the 3D View are only displayed in the window that has focus.
    - Insert keyframe whilw scrubbing will only insert available keyframes on visible and not locked curves.

Known issues:
    - If AnimOffset is on modifying keys in the graph editor instead of editing objects in the 3D View may cause crashes.

""",
    "0.1.9": """
New features:
    - Now you can toggle scrubbing, transform locks and jump to keyframe (for now only from the Graph Editor).
    - A complete rewrite of the keymaps system for being able to dybamically turn them on or off.
    - Added an new button to clean up keyframes from bones with locked transforms.

    - New exciting operators and hotkeys (Dopesheet and Graph Editor):
        Always active: 
            Shift + (1 or G) toggle visibility location fcurves
            Shift + (2 or R) toggle visibility rotation fcurves
            Shift + (3 or S) toggle visibility scale fcurves

            1 select / deselect all location fcurves
            2 select / deselct all rotation fcurves
            3 select / deselect all scale fcurves

        With no keyframes selected:
            G select only location fcurves
            R select only rotation fcurves
            S select only scale fcurves 

UX improvements:
    - The top buttons now display on the top bar of the Graph, Dopesheet, Timeline and NLA editors. Only the relevant buttons will displayed depending on the editor.

Bug Fixed:
    - Keymaps for some keys were not displaying in the preferences.
    - Fixed errors when loading the preferences. 
    - Menus were registering each time the addon was re-enabled.

""",
    "0.1.8": """
New features:
    - Added support for the NLA editor.
    - Added preferences sections for configuration, changelog, and support.
    - Added changelog to preferences.
    - Inserting a keyframe while scrubbing (F) in the editors will now deselect all and select the keyframe.
    - Navigating to Prev/Next keyframe in the editors will now deselect all
        and select the keyframe.
    - ALT Left Click on a keyframe in the editors will now deselect all,
        select the keyframe, and move the playhead to that keyframe.

UX Improvements:
- If the timeline is playing scrubbing will stop it.

Bug Fixed:
    - New Prev and Next keyframe operator that works on all editors.
""",
    "0.1.7": """
New features:
    - Added support for all editors (VIEW3D, GRAPH, DOPESHEET, TIMELINE)
""",
}


import re
import textwrap
from .utils.customIcons import get_icon_id, get_icon

panels_visibility = {}


def draw_changelog(layout, context):
    versions = list(changelog.keys())
    # changelog_container = layout.split(factor=0.5)
    col1 = layout.column()
    # col2 = changelog_container.column(align=True)

    archive_start_index = 5

    for index, version in enumerate(versions):
        changes = changelog[version]
        if index < archive_start_index:
            draw_version_section(col1, version, changes)
        else:
            if index == archive_start_index:
                archive_box = col1.box()
                archive_row = archive_box.row()
                archive_icon = "DOWNARROW_HLT" if panels_visibility.get("Archive", False) else "RIGHTARROW"
                archive_prop = archive_row.operator(
                    "ui.amp_toggle_panels_visibility",
                    text="Archive",
                    icon=archive_icon,
                    emboss=False,
                )
                archive_prop.version = "Archive"
                if panels_visibility.get("Archive", False):
                    for archived_index in range(archive_start_index, len(versions)):
                        archived_version = versions[archived_index]
                        archived_changes = changelog[archived_version]
                        draw_version_section(archive_box, archived_version, archived_changes)

    layout.separator(factor=2)


def parse_and_format_changes(changes, wrap_length=85):
    formatted_changes = []
    lines = changes.strip().split("\n")
    icon_pattern_double = re.compile(r"\*\*(.*?)\*\*")
    icon_pattern_triple = re.compile(r"\*\*\*(.*?)\*\*\*")

    for line in lines:
        indent = len(line) - len(line.lstrip(" "))

        if line.strip() == "":
            formatted_changes.append(("NONE", " " * indent))
            continue

        triple_match = icon_pattern_triple.search(line)
        if triple_match:
            icon_value = get_icon_id(triple_match.group(1))
            clean_line = icon_pattern_triple.sub("", line)
            icon_name = icon_value
            icon_offset = " " * (indent - len(triple_match.group(0)))
        else:
            double_match = icon_pattern_double.search(line)
            if double_match:
                icon_name = double_match.group(1).upper()
                clean_line = icon_pattern_double.sub("", line)
                icon_offset = " " * (indent - len(double_match.group(0)))
            else:

                icon_name = "NONE"
                clean_line = line
                icon_offset = " " * indent

        if clean_line.strip():
            wrapped_lines = textwrap.wrap(
                clean_line.strip(), width=wrap_length, initial_indent=icon_offset, subsequent_indent=" " * (indent + 2)
            )
            first = True
            for wrapped_line in wrapped_lines:
                if first:
                    formatted_changes.append((icon_name, wrapped_line))
                    first = False
                else:
                    formatted_changes.append(("NONE", wrapped_line))
        else:
            formatted_changes.append(("NONE", icon_offset))
            formatted_changes.append((icon_name, clean_line.strip()))

    return formatted_changes


def draw_version_section(layout, version, changes):
    box = layout.box()
    row = box.row()
    icon = "DOWNARROW_HLT" if panels_visibility.get(version, False) else "RIGHTARROW"
    prop = row.operator(
        "ui.amp_toggle_panels_visibility",
        text="",
        icon=icon,
        emboss=False,
    )
    prop.version = version
    row = row.row()
    row.alignment = "LEFT"
    prop = row.operator(
        "ui.amp_toggle_panels_visibility",
        text=f"Version {version}",
        icon="INFO",
        emboss=False,
    )
    prop.version = version

    if panels_visibility.get(version, False):
        col = box.column(align=True)
        formatted_changes = parse_and_format_changes(changes)
        for icon, text in formatted_changes:
            if icon != "NONE":
                if isinstance(icon, int):
                    col.label(text=text, icon_value=icon)
                else:
                    col.label(text=text, icon=icon)
            else:
                col.label(text=text)
