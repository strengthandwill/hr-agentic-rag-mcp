"""Deterministic, offline tests for corpus parsing/chunking (no embedding calls needed)."""
from pathlib import Path

from app.rag.chunking import chunk_document, parse_file

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"


def test_parse_markdown_extracts_doc_id_and_sections():
    parsed = parse_file(CORPUS_DIR / "01_pto_leave_policy.md")
    assert parsed.doc_id == "POL-PTO-01"
    assert "Annual Leave" in parsed.title
    section_names = [s[0] for s in parsed.sections]
    assert any("Requesting Annual Leave" in s for s in section_names)


def test_parse_html_extracts_doc_id_and_sections():
    parsed = parse_file(CORPUS_DIR / "05_data_security_acceptable_use.html")
    assert parsed.doc_id == "POL-SEC-05"
    section_names = [s[0] for s in parsed.sections]
    assert any("Device Requirements" in s for s in section_names)


def test_parse_txt_extracts_doc_id_and_sections():
    parsed = parse_file(CORPUS_DIR / "11_hr_case_escalation_process.txt")
    assert parsed.doc_id == "POL-HRTRIAGE-11"
    section_names = [s[0] for s in parsed.sections]
    assert any("Severity Tiers" in s for s in section_names)


def test_chunk_document_produces_unique_ids_with_metadata():
    chunks = chunk_document(CORPUS_DIR / "01_pto_leave_policy.md")
    assert len(chunks) > 0
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    for c in chunks:
        assert c.doc_id == "POL-PTO-01"
        assert c.text.strip() != ""


def test_all_corpus_files_parse_without_unknown_doc_id():
    for path in CORPUS_DIR.iterdir():
        if path.suffix.lower() not in (".md", ".html", ".htm", ".txt"):
            continue
        parsed = parse_file(path)
        assert parsed.doc_id != "unknown", f"{path.name} is missing a Document ID"
        assert parsed.doc_id.startswith("POL-"), f"{path.name} has unexpected doc_id {parsed.doc_id}"
