"""Format-aware parsing and heading-aware chunking for the policy corpus.

Strategy (documented in design-and-evaluation.md):
  1. Each source file is parsed into (title, metadata, [(heading, text), ...]) sections using a
     format-specific splitter (Markdown '## ' headings, HTML '<h2>' tags, plain-text numbered
     '<N>. HEADING' lines). Splitting on headings keeps a retrieval unit aligned with a single
     policy topic, which is what a citation should point to.
  2. Any section whose body still exceeds CHUNK_TOKEN_SIZE words is further split into
     overlapping windows (CHUNK_TOKEN_OVERLAP words of overlap) so no single chunk is too large
     for the embedding model's effective context and so retrieval granularity stays consistent.
  3. Word counts are used as a lightweight proxy for token counts to avoid an extra tokenizer
     dependency; this is documented as an approximation.

Chunking is fully deterministic (no randomness), which is what "fixed seed" means for this stage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from app.config import CHUNK_TOKEN_OVERLAP, CHUNK_TOKEN_SIZE


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    category: str
    section: str
    source_file: str
    format: str
    text: str


@dataclass
class ParsedDoc:
    doc_id: str
    title: str
    category: str
    sections: list[tuple[str, str]] = field(default_factory=list)


def _extract_metadata_field(text: str, field_name: str, default: str = "unknown") -> str:
    match = re.search(rf"\**{re.escape(field_name)}\**:\**\s*([^\n|]+)", text)
    return match.group(1).strip().rstrip("*").strip() if match else default


def _parse_markdown(text: str, filename: str) -> ParsedDoc:
    lines = text.splitlines()
    title = filename
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    doc_id = _extract_metadata_field(text, "Document ID")
    category = _extract_metadata_field(text, "Category")

    # Split body on level-2 headings ('## ...'); everything before the first '## ' is treated
    # as a single "Overview" section (title + metadata + purpose paragraph).
    parts = re.split(r"^##\s+(.*)$", text, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []
    overview = parts[0].strip()
    if overview:
        sections.append(("Overview", overview))
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if body:
            sections.append((heading, body))
    return ParsedDoc(doc_id=doc_id, title=title, category=category, sections=sections)


def _parse_html(text: str, filename: str) -> ParsedDoc:
    soup = BeautifulSoup(text, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else filename
    meta_p = soup.find("p")
    meta_text = meta_p.get_text("\n", strip=True) if meta_p else ""
    doc_id = _extract_metadata_field(meta_text, "Document ID")
    category = _extract_metadata_field(meta_text, "Category")

    sections: list[tuple[str, str]] = []
    overview_bits = []
    if meta_p:
        overview_bits.append(meta_p.get_text(" ", strip=True))
    em = soup.find("em")
    if em:
        overview_bits.append(em.get_text(" ", strip=True))
    if overview_bits:
        sections.append(("Overview", "\n".join(overview_bits)))

    for h2 in soup.find_all("h2"):
        heading = h2.get_text(strip=True)
        body_parts = []
        for sib in h2.find_next_siblings():
            if sib.name == "h2":
                break
            body_parts.append(sib.get_text(" ", strip=True))
        body = "\n".join(p for p in body_parts if p)
        if body:
            sections.append((heading, body))
    return ParsedDoc(doc_id=doc_id, title=title, category=category, sections=sections)


def _parse_txt(text: str, filename: str) -> ParsedDoc:
    lines = text.splitlines()
    title = next((l.strip() for l in lines if l.strip()), filename)
    doc_id = _extract_metadata_field(text, "Document ID")
    category = _extract_metadata_field(text, "Category")

    pattern = re.compile(r"^\d+\.\s+([A-Z][A-Z0-9 &/'\-]+)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: list[tuple[str, str]] = []
    if matches:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("Overview", preamble))
        for idx, m in enumerate(matches):
            heading = m.group(1).strip().title()
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append((heading, body))
    else:
        sections.append(("Overview", text.strip()))
    return ParsedDoc(doc_id=doc_id, title=title, category=category, sections=sections)


def parse_file(path: Path) -> ParsedDoc:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".md":
        return _parse_markdown(text, path.name)
    if suffix in (".html", ".htm"):
        return _parse_html(text, path.name)
    if suffix == ".txt":
        return _parse_txt(text, path.name)
    raise ValueError(f"Unsupported corpus file format: {path}")


def _window_split(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [text]
    windows = []
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        window_words = words[start : start + size]
        if not window_words:
            break
        windows.append(" ".join(window_words))
        if start + size >= len(words):
            break
    return windows


def chunk_document(path: Path) -> list[Chunk]:
    parsed = parse_file(path)
    chunks: list[Chunk] = []
    for heading, body in parsed.sections:
        windows = _window_split(body, CHUNK_TOKEN_SIZE, CHUNK_TOKEN_OVERLAP)
        section_slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") or "section"
        for idx, window_text in enumerate(windows):
            chunk_id = f"{parsed.doc_id}::{section_slug}::{idx}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=parsed.doc_id,
                    doc_title=parsed.title,
                    category=parsed.category,
                    section=heading,
                    source_file=path.name,
                    format=path.suffix.lstrip("."),
                    text=window_text,
                )
            )
    return chunks
