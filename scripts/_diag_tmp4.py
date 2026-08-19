import pymupdf as fitz
from pathlib import Path

path = Path(r"c:\document_assistant\data\8th class science.pdf")
doc = fitz.open(path)
page = doc.load_page(49)  # page 50

print("=== XObject inspection page 50 ===")
xrefs = page.get_images(full=True)
print("image xrefs", len(xrefs))

# Try get_text with different flags
for mode in ["text", "html", "xml", "xhtml"]:
    try:
        t = page.get_text(mode) or ""
        print(mode, "len", len(t.strip()))
    except Exception as e:
        print(mode, "error", e)

# Search for any font in any page
font_pages = 0
for i in range(doc.page_count):
    if doc.get_page_fonts(i):
        font_pages += 1
        print("page with fonts", i+1, doc.get_page_fonts(i)[:3])
print("pages with any font", font_pages)

# File size vs image-only estimate
total_img_bytes = 0
seen = set()
for i in range(min(10, doc.page_count)):
    for img in doc.load_page(i).get_images(full=True):
        xref = img[0]
        if xref in seen: continue
        seen.add(xref)
        info = doc.extract_image(xref)
        total_img_bytes += len(info.get("image", b""))
print("unique image bytes (first 10 pages sample)", total_img_bytes)

doc.close()
