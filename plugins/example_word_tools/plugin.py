from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class Plugin:
    def __init__(self, api) -> None:
        self.api = api
        self.stats_label = None

    def on_load(self) -> None:
        self.api.notify("Example Word Tools loaded.")
        self.api.add_menu_action("Plugins/Word Tools", "Uppercase Document", self.uppercase_document, "Ctrl+Alt+U")
        self.api.add_menu_action("Plugins/Word Tools", "Summarize with AI", self.summarize_document_with_ai)
        self.api.add_toolbar_action("Main", "Uppercase", self.uppercase_document)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.stats_label = QLabel("Words: 0 | Chars: 0")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._update_stats)
        layout.addWidget(self.stats_label)
        layout.addWidget(refresh_btn)
        self.api.add_panel("Word Stats", panel)
        self.api.start_timer(15000, self._update_stats)
        self._update_stats()

    def on_change(self, _event) -> None:
        self._update_stats()

    def uppercase_document(self) -> None:
        text = self.api.current_text()
        self.api.replace_text(text.upper())
        self.api.notify("Document converted to uppercase.")

    def summarize_document_with_ai(self) -> None:
        text = self.api.current_text().strip()
        if not text:
            self.api.notify("Nothing to summarize.")
            return
        prompt = "Summarize this text in bullet points:\\n\\n" + text[:20000]
        self.api.ask_ai(prompt)

    def _update_stats(self) -> None:
        if self.stats_label is None:
            return
        text = self.api.current_text()
        words = len([w for w in text.split() if w.strip()])
        self.stats_label.setText(f"Words: {words} | Chars: {len(text)}")
