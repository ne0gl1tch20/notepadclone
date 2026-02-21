class Plugin:
    def __init__(self, api) -> None:
        self.api = api

    def on_load(self) -> None:
        self.say_hello_network()

    def say_hello_network(self) -> None:
        # This validates that the plugin has the `network` permission.
        if self.api.network_allowed():
            self.api.notify("Hello from network-enabled plugin.")
