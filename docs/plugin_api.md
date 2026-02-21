# Plugin API

This document describes the built-in plugin system: permissions, hooks, and the runtime API.

## Permissions

Plugins declare permissions in `plugin.json`. The app user can allow/deny any requested permission in the Plugin Manager.

- `file`: read/write active tab, open files, workspace index access.
- `network`: opt-in for any network use.
- `ai`: access the AI controller.
- `ui`: access the app window object.
- `menu`: add menu actions.
- `toolbar`: add toolbar actions.
- `panel`: add dockable panels.
- `background`: start background threads/timers.
- `hooks`: receive lifecycle events.

## Hook Events

Hooks are delivered to plugins that have the `hooks` permission.

Supported hook names (add `on_` prefix):
- `on_change`
- `on_selection_changed`
- `on_open`
- `on_close`
- `on_tab_changed`
- `on_before_save`
- `on_before_save_text`
- `on_before_save_export`
- `on_after_save`
- `on_after_save_text`
- `on_after_save_export`
- `on_save`
- `on_window_focus`
- `on_window_blur`

Each hook receives a single `event` dictionary. For example:

```python
def on_before_save(self, event) -> None:
    path = event.get("path", "")
    title = event.get("title", "")
    mode = event.get("save_mode", "text")
```

`on_save` includes the same `save_mode` field.

Save-specific events include format/path data:

```python
def on_before_save_text(self, event) -> None:
    path = event.get("save_path", "")
    fmt = event.get("save_format", "")
```

Plugins may also implement a generic handler:

```python
def on_event(self, name, event) -> None:
    pass
```

## PluginAPI Surface

Available methods (permission required):

- `notify(text)` → show status message.
- `app_window()` → the main window (`ui`).
- `active_tab()` → current `EditorTab` (`ui`).
- `current_text()` / `selection_text()` / `selection_range()`.
- `open_tabs()` → list of open tabs.
- `replace_text(text)` / `insert_text(text)` / `replace_selection(text)` (`file`).
- `open_file(path)` / `save_active()` (`file`).
- `workspace_root()` / `workspace_files()` / `workspace_index_status()` / `refresh_workspace_index()` (`file`).
- `ask_ai(prompt)` (`ai`).
- `network_allowed()` (`network`).
- `run_background(fn)` / `start_timer(interval_ms, fn)` (`background`).
- `add_menu_action(menu_path, label, callback, shortcut=None)` (`menu` or `ui`).
- `add_toolbar_action(toolbar_name, label, callback, shortcut=None)` (`toolbar` or `ui`).
- `add_panel(title, widget, area=Qt.RightDockWidgetArea)` (`panel` or `ui`).

## Minimal Example

```python
class Plugin:
    def __init__(self, api) -> None:
        self.api = api

    def on_load(self) -> None:
        self.api.add_menu_action("Plugins/Demo", "Notify", self.say_hi)

    def say_hi(self) -> None:
        self.api.notify("Hello from plugin!")
```
