import json
from pathlib import Path
import pymupdf as fitz
from pypdf import PdfReader

path = Path(r"c:\document_assistant\data\8th class science.pdf")
print("FILE", path.name, path.stat().st_size)

doc = fitz.open(path)
print("PAGES", doc.page_count)
print("META", doc.metadata)
print("encrypted", doc.is_encrypted, "needs_pass", doc.needs_pass)
print("xref_length", doc.xref_length())

def span_stats(blocks):
    spans = chars = 0
    fonts = set()
    for b in blocks.get("blocks") or []:
        if b.get("type") != 0:
            continue
        for line in b.get("lines") or []:
            for s in line.get("spans") or []:
                spans += 1
                t = s.get("text") or ""
                chars += len(t.strip())
                if s.get("font"):
                    fonts.add(s["font"])
    return spans, chars, sorted(fonts)[:10]

samples = sorted({0, 1, 2, doc.page_count // 4, doc.page_count // 2, 3 * doc.page_count // 4, doc.page_count - 1})
for idx in samples:
    if idx >= doc.page_count:
        continue
    p = doc.load_page(idx)
    plain = (p.get_text("text") or "").strip()
    d = p.get_text("dict")
    r = p.get_text("rawdict")
    ds, dc, df = span_stats(d)
    rs, rc, rf = span_stats(r)
    imgs = p.get_images(full=True)
    print("--- page", idx + 1, "---")
    print(" plain_chars", len(plain), "preview", plain[:100].replace("\n", " "))
    print(" dict spans/chars", ds, dc, "fonts", df[:5])
    print(" rawdict spans/chars", rs, rc, "fonts", rf[:5])
    print(" images", len(imgs), "drawings", len(p.get_drawings()))

print("=== scan first 30 pages for any text ===")
found = False
for idx in range(min(30, doc.page_count)):
    p = doc.load_page(idx)
    plain = (p.get_text("text") or "").strip()
    ds, dc, _ = span_stats(p.get_text("dict"))
    if plain or dc:
        print("first text page", idx + 1, "plain", len(plain), "dict_chars", dc)
        found = True
        break
if not found:
    print("NO text in first 30 pages via pymupdf")

print("=== block type breakdown page 10 ===")
if doc.page_count >= 10:
    raw = doc.load_page(9).get_text("rawdict")
    types = {}
    for b in raw.get("blocks") or []:
        types[b.get("type")] = types.get(b.get("type"), 0) + 1
    print("block types", types)

doc.close()

r = PdfReader(str(path), strict=False)
print("PYPDF pages", len(r.pages))
for idx in [0, 1, 2, len(r.pages) // 2, len(r.pages) - 1]:
    pg = r.pages[idx]
    try:
        t = pg.extract_text() or ""
    except Exception as e:
        t = ""
        terr = type(e).__name__
    else:
        terr = None
    try:
        l = pg.extract_text(extraction_mode="layout") or ""
    except Exception as e:
        l = ""
        lerr = type(e).__name__
    else:
        lerr = None
    print("pypdf page", idx + 1, "plain", len(t.strip()), "layout", len(l.strip()), "errors", terr, lerr)
