from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

MAX_BYTES_DEFAULT = 100_000
MAX_DIR_ENTRIES = 200
BINARY_SNIFF_BYTES = 8192

_TOKEN_RE = re.compile(r"@([^\s]+)")
_TRAILING_PUNCT = ",.;:?!)]}"


@dataclass(frozen=True)
class Attachment:
    path: Path
    kind: Literal["file", "dir"]
    size_bytes: int


@dataclass(frozen=True)
class ExpandedMessage:
    content: str
    attachments: list[Attachment] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def expand_references(raw: str, cwd: Path, max_bytes: int = MAX_BYTES_DEFAULT) -> ExpandedMessage:
    cwd_resolved = cwd.resolve()
    attachments: list[Attachment] = []
    skipped: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        token_raw = match.group(0)
        path_str = match.group(1)
        stripped = path_str.rstrip(_TRAILING_PUNCT)
        trailing = path_str[len(stripped) :]
        if not stripped:
            return token_raw

        candidate = (cwd_resolved / stripped).resolve()
        if not _is_within(candidate, cwd_resolved):
            skipped.append((f"@{stripped}", "outside cwd"))
            return token_raw
        if not candidate.exists():
            skipped.append((f"@{stripped}", "not found"))
            return token_raw

        if candidate.is_dir():
            rendered, size = _render_dir(candidate, cwd_resolved)
            attachments.append(Attachment(candidate, "dir", size))
            return rendered + trailing

        size = candidate.stat().st_size
        if size > max_bytes:
            skipped.append((f"@{stripped}", f"too large ({size} bytes > {max_bytes})"))
            return token_raw
        if _looks_binary(candidate):
            skipped.append((f"@{stripped}", "binary file"))
            return token_raw

        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append((f"@{stripped}", "not valid UTF-8"))
            return token_raw

        rel = candidate.relative_to(cwd_resolved)
        attachments.append(Attachment(candidate, "file", size))
        return f"\n```{rel}\n{text}\n```\n" + trailing

    content = _TOKEN_RE.sub(replace, raw)
    return ExpandedMessage(content=content, attachments=attachments, skipped=skipped)


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _looks_binary(path: Path) -> bool:
    with path.open("rb") as f:
        chunk = f.read(BINARY_SNIFF_BYTES)
    return b"\x00" in chunk


def _render_dir(path: Path, cwd_root: Path) -> tuple[str, int]:
    entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    truncated = False
    if len(entries) > MAX_DIR_ENTRIES:
        entries = entries[:MAX_DIR_ENTRIES]
        truncated = True

    lines = []
    total = 0
    for entry in entries:
        if entry.is_dir():
            lines.append(f"{entry.name}/")
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            total += size
            lines.append(f"{entry.name}  ({size} bytes)")
    if truncated:
        lines.append(f"... (truncated to {MAX_DIR_ENTRIES} entries)")

    rel = path.relative_to(cwd_root) if path != cwd_root else Path(".")
    body = "\n".join(lines)
    return f"\n```{rel}/\n{body}\n```\n", total
