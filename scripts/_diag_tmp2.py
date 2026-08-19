import pymupdf as fitz
from pathlib import Path

path = Path(r"c:\document_assistant\data\8th class science.pdf")
doc = fitz.open(path)
print("=== FULL DOCUMENT TEXT SCAN (169 pages) ===")
total_plain = total_dict = pages_with_text = 0
for idx in range(doc.page_count):
    p = doc.load_page(idx)
    plain = len((p.get_text("text") or "").strip())
    dchars = 0
    for b in (p.get_text("dict").get("blocks") or []):
        if b.get("type") != 0: continue
        for line in b.get("lines") or []:
            for s in line.get("spans") or []:
                dchars += len((s.get("text") or "").strip())
    total_plain += plain
    total_dict += dchars
    if plain or dchars:
        pages_with_text += 1
        print("page with text:", idx+1, "plain", plain, "dict", dchars)
print("SUMMARY pages_with_text", pages_with_text, "total_plain", total_plain, "total_dict", total_dict)

print("\n=== FONT LIST (document) ===")
try:
    fl = doc.get_page_fonts(0)
    print("page0 fonts count", len(fl))
    for f in fl[:15]:
        print(" ", f)
except Exception as e:
    print("get_page_fonts error", e)

print("\n=== PAGE 50 IMAGE COVERAGE ===")
p = doc.load_page(49)
rect = p.rect
print("page size", rect.width, rect.height)
for i, img in enumerate(p.get_images(full=True)[:3]):
    xref = img[0]
    info = doc.extract_image(xref)
    print(" image", i, "xref", xref, "w", info.get("width"), "h", info.get("height"), "ext", info.get("ext"), "bytes", len(info.get("image", b"")))

print("\n=== BLOCK TYPES ALL PAGES (sample every 20th) ===")
for idx in range(0, doc.page_count, 20):
    raw = doc.load_page(idx).get_text("rawdict")
    types = {}
    for b in raw.get("blocks") or []:
        types[b.get("type")] = types.get(b.get("type"), 0) + 1
    print("page", idx+1, types)

doc.close()

# compare working pdf
good = Path(r"c:\document_assistant\data\MACHINE LEARNING.pdf")
g = fitz.open(good)
p = g.load_page(0)
print("\n=== COMPARE: MACHINE LEARNING page 1 ===")
print("plain chars", len((p.get_text("text") or "").strip()))
print("images", len(p.get_images(full=True)))
types = {}
for b in (p.get_text("rawdict").get("blocks") or []):
    types[b.get("type")] = types.get(b.get("type"), 0) + 1
print("block types", types)
print("producer", g.metadata.get("producer"))
g.close()
