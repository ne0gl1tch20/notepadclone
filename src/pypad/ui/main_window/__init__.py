from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .window import Notepad as Notepad

__all__ = ["Notepad"]


def __getattr__(name: str):
    if name == "Notepad":
        from .window import Notepad as _Notepad

        return _Notepad
    raise AttributeError(name)
