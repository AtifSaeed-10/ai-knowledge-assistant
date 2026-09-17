"""One-off PDF diagnostics — run: .venv\\Scripts\\python.exe scripts/diagnose_pdf.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf as fitz
from pypdf import PdfReader


def sample_pages(total: int) -> list[int]:
    if total <= 0:
        return []
    picks = {0, 1, 2, total // 4, total // 2, (3 * total) // 4, total - 1}
    return sorted(i for i in picks if 0 <= i < total)


def count_dict_spans(blocks: dict) -> tuple[int, int, list[str]]:
    """Return (span_count, char_count, sample_fonts)."""
    spans = 0
    chars = 0
    fonts: set[str] = set()
    for block in blocks.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            for span in line.get("spans") or []:
                spans += 1
                text = span.get("text") or ""
                chars += len(text.strip())
                font = span.get("font")
                if font:
                    fonts.add(str(font))
    return spans, chars, sorted(fonts)[:8]


def diagnose_pymupdf(path: Path) -> dict:
    doc = fitz.open(path)
    try:
        total = doc.page_count
        meta = doc.metadata or {}
        is_encrypted = doc.is_encrypted
        needs_pass = doc.needs_pass
        xref_len = doc.xref_length()

        page_reports = []
        for idx in sample_pages(total):
            page = doc.load_page(idx)
            plain = page.get_text("text") or ""
            blocks = page.get_text("dict") or {}
            raw = page.get_text("rawdict") or {}
            span_n, dict_chars, fonts = count_dict_spans(blocks)
            raw_span_n, raw_chars, raw_fonts = count_dict_spans(raw)

            images = page.get_images(full=True)
            drawings = len(page.get_drawings())

            page_reports.append(
                {
                    "page_index": idx,
                    "page_number": idx + 1,
                    "plain_chars": len(plain.strip()),
                    "plain_preview": plain.strip()[:120].replace("\n", " "),
                    "dict_spans": span_n,
                    "dict_chars": dict_chars,
                    "rawdict_spans": raw_span_n,
                    "rawdict_chars": raw_chars,
                    "image_objects": len(images),
                    "drawing_ops": drawings,
                    "fonts_sample": fonts or raw_fonts,
                }
            )

        return {
            "engine": "pymupdf",
            "path": str(path),
            "file_bytes": path.stat().st_size,
            "page_count": total,
            "metadata": dict(meta),
            "is_encrypted": is_encrypted,
            "needs_pass": needs_pass,
            "xref_length": xref_len,
            "pages": page_reports,
        }
    finally:
        doc.close()


def diagnose_pypdf(path: Path) -> dict:
    reader = PdfReader(str(path), strict=False)
    total = len(reader.pages)
    page_reports = []
    for idx in sample_pages(total):
        page = reader.pages[idx]
        text = ""
        layout = ""
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = f"<error: {exc.__class__.__name__}>"
        try:
            layout = page.extract_text(extraction_mode="layout") or ""
        except Exception as exc:
            layout = f"<error: {exc.__class__.__name__}>"

        page_reports.append(
            {
                "page_index": idx,
                "page_number": idx + 1,
                "plain_chars": len(text.strip()) if not text.startswith("<error") else 0,
                "plain_preview": text.strip()[:120].replace("\n", " "),
                "layout_chars": len(layout.strip()) if not layout.startswith("<error") else 0,
                "layout_preview": layout.strip()[:120].replace("\n", " "),
            }
        )

    return {
        "engine": "pypdf",
        "page_count": total,
        "pages": page_reports,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / "data" / "8th class science.pdf",
        root / "data" / "(ustad360.com) General Science  8 SNC 2023-24.pdf",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        print("No textbook PDF found in data/", file=sys.stderr)
        sys.exit(1)

    print(f"=== Diagnosing: {path.name} ({path.stat().st_size:,} bytes) ===\n")

    pymupdf_report = diagnose_pymupdf(path)
    pypdf_report = diagnose_pypdf(path)

    print(json.dumps({"pymupdf": pymupdf_report, "pypdf": pypdf_report}, indent=2))

    # Deep dive first content-looking page
    doc = fitz.open(path)
    try:
        print("\n=== First page with any dict span (deep) ===")
        for idx in range(min(doc.page_count, 30)):
            page = doc.load_page(idx)
            d = page.get_text("dict")
            spans, chars, fonts = count_dict_spans(d)
            if spans > 0 or chars > 0:
                print(f"Page {idx + 1}: spans={spans} chars={chars} fonts={fonts}")
                break
        else:
            print("No dict spans in first 30 pages.")

        print("\n=== Page 10 rawdict block types (first 5 blocks) ===")
        if doc.page_count >= 10:
            page = doc.load_page(9)
            raw = page.get_text("rawdict")
            for i, block in enumerate((raw.get("blocks") or [])[:5]):
                print(
                    f"  block[{i}] type={block.get('type')} "
                    f"keys={list(block.keys())[:6]}"
                )
            imgs = page.get_images(full=True)
            print(f"  images on page 10: {len(imgs)}")
            if imgs:
                print(f"  first image xref: {imgs[0][:3]}")
    finally:
        doc.close()


if __name__ == "__main__":
    main()
