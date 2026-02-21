class Plugin:
    def __init__(self, api) -> None:
        self.api = api

    def on_load(self) -> None:
        self.api.notify("Example Word Tools loaded.")

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
