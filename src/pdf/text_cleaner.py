from __future__ import annotations

import re
import unicodedata

CHARACTER_REPLACEMENTS = {
    "\u00A0": " ",
    "\u200B": "",
    "\uFEFF": "",
    "\u2022": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\x00": "",
}

MULTISPACE_PATTERN = re.compile(r"[ \t]+")
MULTIBLANK_PATTERN = re.compile(r"\n{3,}")


def normalize_pdf_text(raw_text: str | None) -> str:
    if raw_text is None:
        return ""

    normalized = unicodedata.normalize("NFKC", raw_text)

    for original, replacement in CHARACTER_REPLACEMENTS.items():
        normalized = normalized.replace(original, replacement)

    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(MULTISPACE_PATTERN.sub(" ", line).strip() for line in normalized.split("\n"))
    normalized = MULTIBLANK_PATTERN.sub("\n\n", normalized)

    return normalized.strip()


def split_clean_lines(text: str | None, keep_empty: bool = False) -> list[str]:
    normalized = normalize_pdf_text(text)
    if normalized == "":
        return []

    lines = [line.strip() for line in normalized.split("\n")]
    if keep_empty:
        return lines

    return [line for line in lines if line != ""]


def compact_text(text: str | None) -> str:
    lines = split_clean_lines(text)
    return " ".join(lines).strip()