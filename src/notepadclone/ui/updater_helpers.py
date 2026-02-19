from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    title: str
    changelog: str
    download_url: str
    pub_date: str


def parse_update_feed(xml_text: str) -> UpdateInfo | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _parse_plaintext_feed(xml_text)

    item = None
    for node in root.iter():
        if _local(node.tag) in {"item", "update", "entry"}:
            item = node
            break
    if item is None:
        item = root

    title = _first_text(item, {"title"}) or "Update"
    changelog = _first_text(item, {"description", "changelog", "releaseNotes", "summary"}) or ""
    pub_date = _first_text(item, {"pubDate", "published", "updated", "date"}) or ""
    version = _extract_version(item) or _extract_version(root) or ""
    download_url = _extract_download_url(item) or _extract_download_url(root) or ""

    if not version and not download_url:
        return None
    return UpdateInfo(
        version=version.strip(),
        title=title.strip(),
        changelog=changelog.strip(),
        download_url=download_url.strip(),
        pub_date=pub_date.strip(),
    )


def _parse_plaintext_feed(text: str) -> UpdateInfo | None:
    raw = (text or "").strip()
    if not raw:
        return None

    version_match = re.search(r"\b\d+\.\d+(?:\.\d+)+\b", raw)
    version = version_match.group(0).strip() if version_match else ""
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", raw)
    pub_date = date_match.group(0).strip() if date_match else ""
    url_match = re.search(r"https?://[^\s<>\"']+", raw)
    download_url = url_match.group(0).strip() if url_match else ""

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    title = "Update"
    changelog = ""
    if lines:
        if version and version in lines[0]:
            title = lines[0]
        elif len(lines) > 1 and version and version in lines[1]:
            title = f"{lines[0]} {lines[1]}".strip()
        else:
            title = lines[0]
        changelog_lines = [line for line in lines if line.startswith("-")]
        if changelog_lines:
            changelog = "\n".join(changelog_lines)

    if not version and not download_url:
        return None
    return UpdateInfo(
        version=version,
        title=title,
        changelog=changelog,
        download_url=download_url,
        pub_date=pub_date,
    )


def is_newer_version(remote: str, current: str) -> bool:
    if not remote.strip():
        return False
    return _version_tuple(remote) > _version_tuple(current)


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _first_text(parent: ET.Element, candidates: set[str]) -> str | None:
    lowered = {name.lower() for name in candidates}
    for child in parent.iter():
        if _local(child.tag).lower() in lowered:
            value = (child.text or "").strip()
            if value:
                return value
    return None


def _extract_version(node: ET.Element) -> str | None:
    for child in node.iter():
        local = _local(child.tag).lower()
        if local in {"version", "shortversionstring", "appversion"}:
            text = (child.text or "").strip()
            if text:
                return text
        for key, value in child.attrib.items():
            key_local = _local(key).lower()
            if key_local in {"version", "shortversionstring"} and value.strip():
                return value.strip()
    return None


def _extract_download_url(node: ET.Element) -> str | None:
    for child in node.iter():
        local = _local(child.tag).lower()
        if local == "enclosure":
            candidate = child.attrib.get("url", "").strip()
            if candidate:
                return candidate
        if local in {"download", "url", "link"}:
            candidate = (child.text or "").strip()
            if candidate.startswith(("http://", "https://")):
                return candidate
    return None




def _version_tuple(version: str) -> tuple[int, ...]:
    parts = [int(piece) for piece in re.findall(r"\d+", version)]
    return tuple(parts) if parts else (0,)
