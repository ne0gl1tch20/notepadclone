class Plugin:
    def __init__(self, api) -> None:
        self.api = api

    def on_load(self) -> None:
        self.api.add_menu_action("Plugins/Network", "Say Hello (Network)", self.say_hello_network)
        self.api.start_timer(30000, self._heartbeat)
        self.say_hello_network()

    def say_hello_network(self) -> None:
        # This validates that the plugin has the `network` permission.
        if self.api.network_allowed():
            self.api.notify("Hello from network-enabled plugin.")

    def on_save(self, event) -> None:
        title = event.get("title", "Untitled")
        self.api.notify(f"Saved: {title}")

    def _heartbeat(self) -> None:
        if self.api.network_allowed():
            self.api.notify("Network permission check: ok.")
