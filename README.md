# OpenReMouse

*[version française](README.fr.md)*

Open-source (MIT) mouse + keyboard macro recorder / player for Windows.
Written from scratch based on ReMouse's observable behavior; no ReMouse code is reused.

## Getting started

```
pip install -r requirements.txt
python -m openremouse
```

Python 3.10+ (tested on 3.12). Only dependency: `pynput`.

**Standalone version (.exe)**: run `build.bat` (installs PyInstaller and produces `dist\OpenReMouse.exe`, ~12 MB, no console,
no Python required to use it). An unsigned PyInstaller .exe may be wrongly flagged by some antivirus tools / SmartScreen.

**Dark mode**: "Dark mode" checkbox at the bottom right (follows the Windows theme on first launch, then remembers your choice in
`%APPDATA%\OpenReMouse\settings.json`).

**Language**: "Language" list next to dark mode (Français / English). On first launch the Windows display language is used.

## "Macro" tab

- **F10**: start / stop recording. **F9**: start / stop playback.
- **Editor**: *Add ▾* (menu by category), *Edit* (or double-click), *Duplicate*, *Delete*, *Move up / down*, Ctrl+S.
- In dialogs with coordinates, **"Aim on screen…"** lets you click on the screen to fill in X, Y (and the pixel color).
- Recorded movements can be edited in bulk: X/Y offset and duration multiplier.

## Available actions

| Category | Actions |
|---|---|
| Mouse | click (left/right/middle), recorded movements |
| Keyboard | key, combination (`ctrl+shift+s`), text input |
| Time | delay |
| Color | wait for a pixel to take (or leave) a color, with tolerance and max timeout |
| Windows | activate, close, flash, wait for open / activate / deactivate / close |
| Controls | click, enable, disable, focus, show, hide a button / checkbox… by its text or `class:Button` |
| Files | copy, delete, open a program or file |
| Internet | open a website, download, check connection |
| System | message, kill a process, wait for a process, shut down / restart / log off / cancel |

Windows are identified by part of their title (case-insensitive) or `class:ClassName`.
A failing action (window not found, missing file…) **stops** the macro and shows the error in the status bar,
so that steps depending on the previous one are not chained. Waits have the option *On timeout: stop / continue*.
`Shutdown` has a 30 s default delay and a `cancel` action.

## "Scheduled tasks" tab

A task = a macro + one or more of:

- **Hotkey** specific to the macro (`ctrl+alt+1`, `f5`, `shift+a`, `ctrl+num5`…), active even when OpenReMouse is in the background.
  Several tasks can each have their own hotkey; pressing the hotkey of a running macro again stops it.
  Hotkeys are matched by physical key code, so they work on AZERTY as well as QWERTY
  (`ctrl+alt+1` = the "&/1" key). F9 and F10 are reserved; a hotkey that is already taken is ignored with a message.
- **Schedule**: `once` (one time, then the task disables itself), `daily` (every day at HH:MM), `interval` (every N seconds).
- **Trigger**: when a window (title) or a process (name) appears.

Rules: only one macro runs at a time (a task firing in the meantime is skipped, with a message);
`once` / `daily` only fire if OpenReMouse was already open before the time (launching the app at 3 pm does not replay the 9 am task);
triggers only fire on appearance (not if the window was already there at startup).
Everything only works while OpenReMouse is open (minimizing the window is enough). Configuration: `%APPDATA%\OpenReMouse\tasks.json`.

## `.rms` format

Plain text, one action per line. Compatible with ReMouse mouse macros.

```
{Delay 0.50}
{RMouse down (225,202)}
{Movements (0.36:226:192|0.05:254:192)}      delay:x:y
{Key down a}                                 OpenReMouse's own keyboard syntax
{WaitColor x=100 y=200 color=FF0000 tolerance=10 until=present timeout=30 on_timeout=stop}
{WinActivate title="Notepad"}
```

Extended actions are `{Name key=value ...}` lines (values in quotes if they contain spaces; `\"`, `\\`, `\n` escaped).
Unknown lines are preserved as-is and ignored when reading.

## Tests

```
python -m unittest discover tests
```

## Known limitations

- "Controls" are native Windows controls (buttons, checkboxes, standard fields). Applications that draw their own
  interface (browsers, Electron, custom Qt/WPF) do not expose controls: use clicks + color waits instead.
- To drive a window launched as administrator, run OpenReMouse as administrator.
- The `.rms` keyboard syntax has not been verified against ReMouse's (the demos contain none).
