"""Deterministic manuscript bibliography and export helpers."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from html import escape as xml_escape
from typing import Any, Iterable


def _authors(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if item)
    return str(value or "").strip()


def _citation_base(paper: Any) -> str:
    authors = _authors(paper.authors)
    first = re.sub(r"[^A-Za-z0-9]", "", (authors.split(",")[0].split()[-1] if authors else "source"))
    return f"{(first or 'source').lower()}{paper.publication_year or 'nd'}"


def build_bibliography(papers: Iterable[Any]) -> tuple[list[dict[str, Any]], str, str]:
    """Return normalized entries, BibTeX, and readable Markdown with stable unique keys."""
    entries: list[dict[str, Any]] = []
    used: dict[str, int] = {}
    for paper in sorted(papers, key=lambda item: (str(item.publication_year or ""), str(item.title or ""))):
        base = _citation_base(paper)
        used[base] = used.get(base, 0) + 1
        key = base if used[base] == 1 else f"{base}{chr(96 + min(used[base], 26))}"
        entry = {
            "paper_id": str(paper.id), "citation_key": key, "title": str(paper.title or ""),
            "authors": _authors(paper.authors), "year": paper.publication_year,
            "venue": str(paper.venue or ""), "doi": str(paper.doi or ""),
        }
        entries.append(entry)
    bib_blocks: list[str] = []
    markdown = ["# 参考文献", ""]
    for index, item in enumerate(entries, 1):
        fields = [f"  title = {{{item['title']}}}", f"  author = {{{item['authors']}}}"]
        if item["venue"]:
            fields.append(f"  journal = {{{item['venue']}}}")
        if item["year"]:
            fields.append(f"  year = {{{item['year']}}}")
        if item["doi"]:
            fields.append(f"  doi = {{{item['doi']}}}")
        bib_blocks.append(f"@article{{{item['citation_key']},\n" + ",\n".join(fields) + "\n}")
        readable = ". ".join(value for value in (item["authors"], item["title"], item["venue"], str(item["year"] or "")) if value)
        if item["doi"]:
            readable += f". https://doi.org/{item['doi']}"
        markdown.append(f"{index}. {readable} `[@{item['citation_key']}]`")
    return entries, "\n\n".join(bib_blocks), "\n".join(markdown)


def markdown_to_latex(title: str, markdown: str, bibliography_file: str = "references.bib") -> str:
    """Convert common manuscript Markdown constructs to a self-contained LaTeX source."""
    def esc(text: str) -> str:
        replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
        escaped = "".join(replacements.get(char, char) for char in text)
        return re.sub(r"\[@([A-Za-z0-9_-]+)\]", lambda match: rf"\cite{{{match.group(1)}}}", escaped)

    body: list[str] = []
    in_list = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            if not in_list:
                body.append(r"\begin{itemize}")
                in_list = True
            body.append(r"\item " + esc(line[2:]))
            continue
        if in_list:
            body.append(r"\end{itemize}")
            in_list = False
        if line.startswith("### "):
            body.append(r"\subsubsection{" + esc(line[4:]) + "}")
        elif line.startswith("## "):
            body.append(r"\subsection{" + esc(line[3:]) + "}")
        elif line.startswith("# "):
            body.append(r"\section{" + esc(line[2:]) + "}")
        elif line:
            body.append(esc(line) + "\n")
        else:
            body.append("")
    if in_list:
        body.append(r"\end{itemize}")
    return "\n".join([
        r"\documentclass[UTF8]{ctexart}", r"\usepackage{geometry}", r"\usepackage{hyperref}",
        r"\usepackage[backend=biber,style=numeric]{biblatex}", rf"\addbibresource{{{bibliography_file}}}",
        r"\geometry{a4paper,margin=2.5cm}", r"\begin{document}", rf"\title{{{esc(title)}}}",
        r"\maketitle", *body, r"\printbibliography", r"\end{document}", "",
    ])


def build_docx(title: str, markdown: str) -> bytes:
    """Build a minimal standards-compliant DOCX using only the standard library."""
    paragraphs = [title] + [re.sub(r"^#{1,6}\s+", "", line).strip() for line in markdown.splitlines() if line.strip()]
    document_xml = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r></w:p>' for text in paragraphs
    )
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + document_xml + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def build_submission_package(title: str, markdown: str, bibtex: str, audit_markdown: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manuscript.md", markdown)
        archive.writestr("manuscript.tex", markdown_to_latex(title, markdown))
        archive.writestr("manuscript.docx", build_docx(title, markdown))
        archive.writestr("references.bib", bibtex)
        archive.writestr("audit-report.md", audit_markdown)
        archive.writestr("MANIFEST.txt", f"PaperAI submission package\nGenerated: {datetime.now(timezone.utc).isoformat()}\n")
    return output.getvalue()
