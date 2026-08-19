import pymupdf as fitz
from pathlib import Path
from pypdf import PdfReader

path = Path(r"c:\document_assistant\data\8th class science.pdf")
doc = fitz.open(path)

whole = 0
for i in range(doc.page_count):
    whole += len((doc.load_page(i).get_text("text") or "").strip())
print("whole_doc_text_len", whole)
print("embedded_file_count", doc.embfile_count())
doc.close()

r = PdfReader(str(path), strict=False)
pg = r.pages[0]
res = pg.get("/Resources")
print("Resources keys", list(res.keys()) if res else None)
if res and "/Font" in res:
    print("Font dict", res["/Font"])
else:
    print("NO /Font in page resources")

for name in ["football_rules.pdf", "MACHINE LEARNING.pdf"]:
    p = Path(r"c:\document_assistant\data") / name
    d = fitz.open(p)
    print(name, "p1_text", len(d.load_page(0).get_text().strip()), "fonts", len(d.get_page_fonts(0)), "producer", d.metadata.get("producer"))
    d.close()
