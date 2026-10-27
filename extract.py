import fitz  # this is PyMuPDF
import json

doc = fitz.open("chemistry_inorganic.pdf")

pages = []
for number, page in enumerate(doc, start=1):
    pages.append({"pdf_page": number, "text": page.get_text()})

with open("pages.json", "w", encoding="utf-8") as f:
    json.dump(pages, f, ensure_ascii=False, indent=2)

print(len(pages), "pages saved")
 