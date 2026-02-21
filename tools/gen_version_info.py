from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION_TXT = ROOT / "assets" / "version.txt"
OUT_PATH = ROOT / "assets" / "version_info.txt"


def _parse_version(raw: str) -> tuple[int, int, int, int, str]:
    text = raw.strip()
    match = re.match(r"^\s*(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        raise ValueError(f"Invalid version format in {VERSION_TXT}: {text!r}")
    major, minor, patch = (int(x) for x in match.groups())
    filever = f"{major}.{minor}.{patch}.0"
    return major, minor, patch, 0, filever


def main() -> None:
    raw = VERSION_TXT.read_text(encoding="utf-8")
    major, minor, patch, build, filever = _parse_version(raw)
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [
        StringStruct('CompanyName', 'ne0gl1tch20'),
        StringStruct('FileDescription', 'Pypad'),
        StringStruct('FileVersion', '{filever}'),
        StringStruct('InternalName', 'pypad'),
        StringStruct('OriginalFilename', 'run.exe'),
        StringStruct('ProductName', 'Pypad'),
        StringStruct('ProductVersion', '{filever}')
        ])
      ]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""
    OUT_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
