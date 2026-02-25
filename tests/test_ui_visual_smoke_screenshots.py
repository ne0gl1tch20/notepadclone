import os
import sys
import unittest
import json
import hashlib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMainWindow

try:
    from pypad.app_settings.defaults import build_default_settings
    from pypad.ui.autosave import AutoSaveEntry, AutoSaveRecoveryDialog
    from pypad.ui.ai_chat_dock import AIChatDock
    from pypad.ui.ai_edit_preview_dialog import AIEditPreviewDialog
    from pypad.ui.debug_logs_dialog import DebugLogsDialog
    from pypad.ui.main_window.settings_dialog import SettingsDialog
    from pypad.ui.quick_open_dialog import QuickOpenDialog, QuickOpenEntry
    from pypad.ui.tutorial_dialog import InteractiveTutorialDialog
except ModuleNotFoundError:
    from notepadclone.app_settings.defaults import build_default_settings
    from notepadclone.ui.autosave import AutoSaveEntry, AutoSaveRecoveryDialog
    from notepadclone.ui.ai_chat_dock import AIChatDock
    from notepadclone.ui.ai_edit_preview_dialog import AIEditPreviewDialog
    from notepadclone.ui.debug_logs_dialog import DebugLogsDialog
    from notepadclone.ui.main_window.settings_dialog import SettingsDialog
    from notepadclone.ui.quick_open_dialog import QuickOpenDialog, QuickOpenEntry
    from notepadclone.ui.tutorial_dialog import InteractiveTutorialDialog


class _Parent(QMainWindow):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings

    def show_status_message(self, _message: str, _timeout: int = 0) -> None:
        return

    def save_settings_to_disk(self) -> None:
        return


class _FakeAIController:
    def __init__(self, window: _Parent) -> None:
        self.window = window

    def ask_ai_chat(self, *_args, **_kwargs) -> None:
        return

    def cancel_active_chat_request(self) -> None:
        return


class VisualSmokeScreenshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.out_dir = ROOT / "tests_tmp" / "visual_smoke_phase2"
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.baseline_path = ROOT / "tests" / "visual_smoke_phase2_baseline.json"
        cls.manifest_path = cls.out_dir / "index.html"
        cls.latest_metrics_path = cls.out_dir / "metrics_latest.json"

    def _variant_settings(self, variant: str) -> dict:
        s = build_default_settings(default_style="Windows", font_family="Segoe UI", font_size=11)
        if variant == "dark":
            s["dark_mode"] = True
            s["accent_color"] = "#4a90e2"
        elif variant == "custom":
            s["dark_mode"] = False
            s["use_custom_colors"] = True
            s["custom_chrome_bg"] = "#dcecff"
            s["custom_editor_bg"] = "#f7fbff"
            s["custom_editor_fg"] = "#1a2b3c"
            s["accent_color"] = "#0d7ccf"
        return s

    def _image_metrics(self, image: QImage) -> dict:
        img = image.convertToFormat(QImage.Format.Format_RGB32)
        raw = memoryview(img.bits())[: img.sizeInBytes()].tobytes()
        sha = hashlib.sha256(raw).hexdigest()
        small = img.scaled(8, 8, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        grays: list[int] = []
        for y in range(8):
            for x in range(8):
                c = small.pixelColor(x, y)
                grays.append(int(round(c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114)))
        avg = sum(grays) / max(1, len(grays))
        bits = "".join("1" if v >= avg else "0" for v in grays)
        ahash_hex = f"{int(bits, 2):016x}"
        return {"width": img.width(), "height": img.height(), "sha256": sha, "ahash64": ahash_hex}

    @staticmethod
    def _hamming_hex(a: str, b: str) -> int:
        try:
            return (int(a, 16) ^ int(b, 16)).bit_count()
        except Exception:
            return 9999

    def _capture_dialog(self, dialog, name: str) -> dict:
        dialog.show()
        self.app.processEvents()
        pix = dialog.grab()
        path = self.out_dir / f"{name}.png"
        ok = pix.save(str(path), "PNG")
        self.assertTrue(ok, f"failed saving screenshot {path}")
        self.assertTrue(path.exists(), f"missing screenshot {path}")
        self.assertGreater(path.stat().st_size, 0)
        metrics = self._image_metrics(pix.toImage())
        metrics["file"] = path.name
        dialog.close()
        self.app.processEvents()
        return metrics

    def _write_manifest(self, rows: list[dict]) -> None:
        lines = [
            "<!doctype html>",
            "<html><head><meta charset='utf-8'><title>PyPad Visual Smoke Phase 2</title>",
            "<style>body{font-family:Segoe UI,sans-serif;margin:16px;background:#f3f5f8;color:#111} .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px} .card{background:#fff;border:1px solid #d0d7e2;border-radius:12px;padding:12px} img{max-width:100%;border:1px solid #d0d7e2;border-radius:8px;background:#fff} .meta{font:12px monospace;white-space:pre-wrap;color:#334}</style>",
            "</head><body>",
            "<h1>Phase 2 Visual Smoke Screenshots</h1>",
            "<div class='grid'>",
        ]
        for row in sorted(rows, key=lambda r: r["name"]):
            lines.append(
                f"<div class='card'><h3>{row['name']}</h3><img src='{row['file']}' alt='{row['name']}'/>"
                f"<div class='meta'>{row['width']}x{row['height']}\nsha256={row['sha256'][:16]}...\nahash64={row['ahash64']}</div></div>"
            )
        lines.extend(["</div></body></html>"])
        self.manifest_path.write_text("\n".join(lines), encoding="utf-8")

    def _compare_or_update_baseline(self, rows: list[dict]) -> None:
        mode = str(os.getenv("PYPAD_VISUAL_BASELINE_MODE", "compare_if_exists")).strip().lower()
        threshold = int(os.getenv("PYPAD_VISUAL_AHASH_THRESHOLD", "6"))
        current = {row["name"]: {k: row[k] for k in ("width", "height", "sha256", "ahash64", "file")} for row in rows}
        self.latest_metrics_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        if mode in {"update", "write"}:
            self.baseline_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
            return
        if mode in {"off", "none", "skip"}:
            return
        if not self.baseline_path.exists():
            if mode == "compare":
                self.fail(f"Baseline file missing: {self.baseline_path}")
            return
        baseline = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        failures: list[str] = []
        for name, now in sorted(current.items()):
            base = baseline.get(name)
            if not isinstance(base, dict):
                failures.append(f"{name}: missing in baseline")
                continue
            if (base.get("width"), base.get("height")) != (now["width"], now["height"]):
                failures.append(f"{name}: size changed {base.get('width')}x{base.get('height')} -> {now['width']}x{now['height']}")
                continue
            if str(base.get("sha256")) == now["sha256"]:
                continue
            dist = self._hamming_hex(str(base.get("ahash64", "")), now["ahash64"])
            if dist > threshold:
                failures.append(f"{name}: visual hash distance {dist} > {threshold}")
        missing_current = sorted(set(baseline.keys()) - set(current.keys()))
        for name in missing_current:
            failures.append(f"{name}: exists in baseline but not current capture set")
        if failures:
            self.fail(
                "Visual regression baseline check failed.\n"
                f"Baseline: {self.baseline_path}\nManifest: {self.manifest_path}\n"
                + "\n".join(failures)
            )

    def test_generate_visual_smoke_screenshots_for_key_dialogs(self) -> None:
        variants = ["light", "dark", "custom"]
        rows: list[dict] = []
        for variant in variants:
            parent = _Parent(self._variant_settings(variant))

            settings_dlg = SettingsDialog(parent, dict(parent.settings))
            rows.append({"name": f"settings_{variant}", **self._capture_dialog(settings_dlg, f"settings_{variant}")})

            tutorial_dlg = InteractiveTutorialDialog(parent)
            rows.append({"name": f"tutorial_{variant}", **self._capture_dialog(tutorial_dlg, f"tutorial_{variant}")})

            entries = [
                AutoSaveEntry(
                    autosave_id="a1",
                    autosave_path="",
                    original_path="",
                    title="Draft Note",
                    saved_at="2026-02-25 10:30:00",
                )
            ]
            autosave_dlg = AutoSaveRecoveryDialog(parent, entries)
            rows.append({"name": f"autosave_{variant}", **self._capture_dialog(autosave_dlg, f"autosave_{variant}")})

            debug_logs = DebugLogsDialog(parent)
            debug_logs.set_lines(["[Info] startup", "[Info] theme applied", "[Warn] sample line"])
            rows.append({"name": f"debug_logs_{variant}", **self._capture_dialog(debug_logs, f"debug_logs_{variant}")})

            quick_items = [
                QuickOpenEntry(kind="workspace", label="README.md", subtitle="Project readme", path="README.md", source="workspace"),
                QuickOpenEntry(
                    kind="workspace",
                    label="src/pypad/ui/main_window/misc.py",
                    subtitle="Workspace file",
                    path="src/pypad/ui/main_window/misc.py",
                    source="workspace",
                ),
            ]
            quick_symbols = [
                QuickOpenEntry(kind="symbol", label="apply_settings", subtitle="misc.py:4500", path="misc.py", line=4500, source="current")
            ]
            quick_dlg = QuickOpenDialog(
                parent,
                quick_items,
                current_tab_label="misc.py",
                current_symbols=quick_symbols,
                workspace_symbols=quick_symbols,
                status_provider=lambda: "Indexing workspace... 128 files",
            )
            quick_dlg.search_edit.setText("@@misc apply")
            rows.append({"name": f"quick_open_{variant}", **self._capture_dialog(quick_dlg, f"quick_open_{variant}")})

            ai_preview = AIEditPreviewDialog(parent, "line1\nline2\n", "line1\nline2 updated\n")
            rows.append({"name": f"ai_edit_preview_{variant}", **self._capture_dialog(ai_preview, f"ai_edit_preview_{variant}")})

            ai_controller = _FakeAIController(parent)
            ai_dock = AIChatDock(parent, ai_controller)
            parent.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, ai_dock)
            ai_dock._add_bubble("Summarize this file quickly.", "user", persist=False)  # type: ignore[attr-defined]
            ai_dock._add_bubble("Here is a short summary with an action plan.", "assistant", persist=False)  # type: ignore[attr-defined]
            rows.append({"name": f"ai_chat_dock_{variant}", **self._capture_dialog(ai_dock, f"ai_chat_dock_{variant}")})
            ai_dock.setParent(None)

        self._write_manifest(rows)
        self._compare_or_update_baseline(rows)
        self.assertTrue(self.manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
