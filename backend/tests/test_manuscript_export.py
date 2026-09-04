import io
import zipfile
from types import SimpleNamespace

from app.utils.manuscript_export import (
    build_bibliography,
    build_docx,
    build_submission_package,
    markdown_to_latex,
)


def _paper(pid, title, authors, year, doi=""):
    return SimpleNamespace(id=pid, title=title, authors=authors, publication_year=year, venue="Journal", doi=doi)


def test_bibliography_uses_stable_unique_keys_and_keeps_ids():
    entries, bibtex, markdown = build_bibliography([
        _paper("p1", "Paper A", "Jane Doe", 2024, "10.1/a"),
        _paper("p2", "Paper B", "John Doe", 2024),
    ])
    assert {item["paper_id"] for item in entries} == {"p1", "p2"}
    assert len({item["citation_key"] for item in entries}) == 2
    assert bibtex.count("@article{") == 2
    assert "https://doi.org/10.1/a" in markdown


def test_latex_and_docx_exports_are_valid_containers():
    latex = markdown_to_latex("研究题目", "# 引言\n\n- 第一项 [@doe2024]")
    assert "\\documentclass[UTF8]{ctexart}" in latex
    assert "\\section{引言}" in latex
    assert "\\cite{doe2024}" in latex
    docx = build_docx("研究题目", "# 引言\n正文")
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        assert "word/document.xml" in archive.namelist()
        assert "研究题目" in archive.read("word/document.xml").decode()


def test_submission_package_contains_reproducible_sources_and_audit():
    payload = build_submission_package("Paper", "# Intro", "@article{x}", "# Audit")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) >= {
            "manuscript.md", "manuscript.tex", "manuscript.docx",
            "references.bib", "audit-report.md", "MANIFEST.txt",
        }
