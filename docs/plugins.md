# Plugin System

This app includes a local plugin system with a manifest + permission model.

## Plugin Location

Plugins are discovered from:

- `plugins/<plugin_folder>/plugin.json`
- `plugins/<plugin_folder>/plugin.py`

## Manifest Format

`plugin.json`:

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "What this plugin does",
  "permissions": ["file", "network", "ai"]
}
```

Supported permissions:

- `file`: read/write current text or files
- `network`: allows network-capability checks inside plugin API
- `ai`: allows invoking AI from plugin API

## Plugin Class API

`plugin.py` should expose `Plugin`:

```python
class Plugin:
    def __init__(self, api):
        self.api = api

    def on_load(self):
        self.api.notify("Loaded")
```

Available `api` methods:

- `notify(text)`
- `current_text()`
- `replace_text(text)` (`file` permission required)
- `ask_ai(prompt)` (`ai` permission required)
- `network_allowed()` (`network` permission required)

## Example Plugin

See:

- `plugins/example_word_tools/plugin.json`
- `plugins/example_word_tools/plugin.py`
- `plugins/example_hello_network/plugin.json`
- `plugins/example_hello_network/plugin.py`

`example_hello_network` demonstrates the `network` permission by calling `api.network_allowed()` and posting a status message on load.

## UI

Open plugin manager from:

- `Settings -> Plugin Manager...`

Enable/disable plugins and reload them after changes.
