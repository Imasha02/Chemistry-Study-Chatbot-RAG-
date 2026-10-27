
import json
import re
import statistics

INPUT_FILE = "pages.json"
CHUNKS_FILE = "chunks.json"
PREVIEW_FILE = "chunks_preview.txt"

FRONT_MATTER_LAST_PDF_PAGE = 10   
PAGE_OFFSET = 10                 

MAX_WORDS = 220                   # split a section if it is longer than this
OVERLAP_WORDS = 30                # words repeated between split pieces
MIN_WORDS = 25                    # tiny leftovers get merged into the previous chunk

UNIT_TITLES = {
    1: "Atomic Structure",
    2: "Structure and Bonding",
    3: "Chemical Calculations",
    6: "Chemistry of s, p and d Block Elements",
}
# Unit 6 uses section numbers 4.x in the book (4.1, 4.2 ... 4.10).
UNIT_SECTION_PREFIX = {1: 1, 2: 2, 3: 3, 6: 4}

# A page with at least this many "maths-font" characters is treated as garbled.
GARBLE_THRESHOLD = 10


# Small helpers
HEADER_RE = re.compile(r"G\.\s*C\.\s*E\..*CHEMISTRY", re.IGNORECASE)
UNIT_RE = re.compile(r"UNIT\s*(\d+)", re.IGNORECASE)
# Unicode "mathematical alphanumeric" block: the broken bold/italic formula characters.
MATH_GLYPH_RE = re.compile(r"[\U0001D400-\U0001D7FF]+")
# lone section number, e.g. "1.1" or "2.3.1" (title is on the next line)
LONE_NUMBER_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?$")
# number and title on the same line, e.g. "1.1.1 Properties of cathode rays"
NUMBER_TITLE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?\s+([A-Z].{3,})$")


def detect_unit(text):
    """Look for 'UNIT n' in the header lines at the top of a page."""
    for line in text.splitlines()[:4]:
        if HEADER_RE.search(line):
            m = UNIT_RE.search(line)
            if m:
                return int(m.group(1))
    return None


def is_unit_opening_page(lines):
    """The first page of each unit is just a contents list - we skip it."""
    return any(l.strip().lower() == "content" for l in lines[:10])


def strip_header_and_page_number(text, unit, printed_page):
    """Remove the running header, the unit title line and the page number."""
    lines = text.splitlines()
    title = UNIT_TITLES.get(unit, "").lower()
    out = []
    for i, raw in enumerate(lines):
        line = raw.strip()
        if i < 6:
            if HEADER_RE.search(line):
                continue
            if title and line.lower() == title:
                continue
            if line == str(printed_page):
                continue
        out.append(raw)
    return out


def restore_arrows(line):
    """Replace a few broken reaction arrows with '->'."""
    if "+" not in line:
        return line, 0
    parts = re.split(r"( {5,})", line)
    if len(parts) == 1:
        return line, 0
    added = 0
    for i in range(1, len(parts), 2):
        left = parts[i - 1].rstrip()
        right = parts[i + 1].lstrip() if i + 1 < len(parts) else ""
        if not left or not right:
            parts[i] = " "                       # leading/trailing gap: just whitespace
        elif re.search(r"(^|\s)\+$", left) or re.match(r"^\+(\s|$)", right):
            parts[i] = " "                       # spacing around a stand-alone plus sign
            # (an ion charge like "2H+" does NOT count - that gap is a lost arrow)
        else:
            parts[i] = " -> "
            added += 1
    return "".join(parts), added


def tidy_line(line):
    return re.sub(r"[ \t]+", " ", line).strip()



def load_clean_lines(pages):
    """
    Returns a list of (unit, printed_page, line_text) for the whole book,
    plus a report dictionary for things worth warning the user about.
    """
    report = {"empty_pages": [], "garbled_pages": [], "arrows_added": 0, "skipped_unit_openers": []}
    all_lines = []
    current_unit = None

    for page in pages:
        pdf_page = page["pdf_page"]
        text = page["text"]
        if pdf_page <= FRONT_MATTER_LAST_PDF_PAGE:
            continue

        printed = pdf_page - PAGE_OFFSET
        unit = detect_unit(text) or current_unit   # keep the last unit if a header is missing
        current_unit = unit

        if not text.strip():
            report["empty_pages"].append((pdf_page, printed))
            continue

        lines = text.splitlines()
        if is_unit_opening_page(lines):
            report["skipped_unit_openers"].append((pdf_page, printed))
            continue

        math_count = sum(len(m) for m in MATH_GLYPH_RE.findall(text))
        if math_count >= GARBLE_THRESHOLD:
            report["garbled_pages"].append((pdf_page, printed))

        body = strip_header_and_page_number(text, unit, printed)
        for raw in body:
            # replace broken maths-font characters with a visible marker
            raw = MATH_GLYPH_RE.sub("[?]", raw)
            raw, n = restore_arrows(raw)
            report["arrows_added"] += n
            line = tidy_line(raw)
            if line:
                all_lines.append((unit, printed, line))

    return all_lines, report


# find section headings and cut into chunks
def is_plausible_heading(unit, major, minor, last_key):
    """Section numbers must belong to this unit and only ever go forward."""
    if unit not in UNIT_SECTION_PREFIX or major != UNIT_SECTION_PREFIX[unit]:
        return False
    if minor < 1 or minor > 12:
        return False
    return True


def split_into_sections(all_lines):
    """
    Walk through the lines and start a new section at every real heading.
    Handles both 'number + title on one line' and 'number alone, title on next line'.
    """
    sections = []
    cur = None
    last_key = {}   # unit -> last (major, minor, sub) seen, to reject out-of-order numbers
    i = 0

    def start_section(unit, number, title, page):
        nonlocal cur
        cur = {"unit": unit, "section_id": number, "section_title": title,
               "lines": [], "pages": set()}
        sections.append(cur)

    # an opening section for text before the first heading of each unit
    while i < len(all_lines):
        unit, page, line = all_lines[i]
        heading = None

        m = NUMBER_TITLE_RE.match(line)
        if m:
            major, minor, sub, title = int(m[1]), int(m[2]), m[3], m[4]
            number = f"{major}.{minor}" + (f".{sub}" if sub else "")
            heading = (major, minor, int(sub) if sub else 0, number, title, 1)
        else:
            m = LONE_NUMBER_RE.match(line)
            if m and i + 1 < len(all_lines):
                nxt_unit, _, nxt = all_lines[i + 1]
                if nxt_unit == unit and re.match(r"^[A-Z]", nxt) and len(nxt) >= 4:
                    major, minor, sub = int(m[1]), int(m[2]), m[3]
                    number = f"{major}.{minor}" + (f".{sub}" if sub else "")
                    heading = (major, minor, int(sub) if sub else 0, number, nxt, 2)

        if heading:
            major, minor, sub, number, title, consumed = heading
            key = (major, minor, sub)
            ok = is_plausible_heading(unit, major, minor, last_key.get(unit))
            
            if ok and unit in last_key and key < last_key[unit]:
                ok = False
            if ok:
                last_key[unit] = key
                start_section(unit, number, title, page)
                cur["pages"].add(page)
                i += consumed
                continue

    
        if cur is None or cur["unit"] != unit:
            start_section(unit, "intro", "Introduction", page)
        cur["lines"].append((page, line))
        cur["pages"].add(page)
        i += 1

    return sections


def words_of(text):
    return text.split()


def chunk_section(sec):
    """Turn one section into one or more chunks (with a little overlap if split)."""
    # Build paragraphs of (page, text) - here each non-empty line is a unit of text
    pieces = sec["lines"]
    if not pieces:
        return []

    chunks = []
    cur_words, cur_pages = [], []

    def flush():
        if cur_words:
            chunks.append({"text": " ".join(cur_words),
                           "page_start": min(cur_pages), "page_end": max(cur_pages)})

    for page, line in pieces:
        w = words_of(line)
        if cur_words and len(cur_words) + len(w) > MAX_WORDS:
            flush()
            tail = cur_words[-OVERLAP_WORDS:]
            cur_words = list(tail)
            cur_pages = [page]
        cur_words.extend(w)
        cur_pages.append(page)
    flush()

    # merge a tiny last chunk into the previous one
    if len(chunks) >= 2 and len(words_of(chunks[-1]["text"])) < MIN_WORDS:
        last = chunks.pop()
        chunks[-1]["text"] += " " + last["text"]
        chunks[-1]["page_end"] = max(chunks[-1]["page_end"], last["page_end"])
    return chunks


def build_chunks(sections, garbled_printed_pages):
    result = []
    n = 0
    for sec in sections:
        unit = sec["unit"]
        unit_title = UNIT_TITLES.get(unit, "Unknown")
        for piece in chunk_section(sec):
            n += 1
            breadcrumb = f"Unit {unit}: {unit_title} > {sec['section_id']} {sec['section_title']}"
            has_marker = "[?]" in piece["text"]
            touches_bad_page = any(p in garbled_printed_pages
                                   for p in range(piece["page_start"], piece["page_end"] + 1))
            result.append({
                "chunk_id": f"c{n:03d}",
                "unit": unit,
                "unit_title": unit_title,
                "section_id": sec["section_id"],
                "section_title": sec["section_title"],
                "page_start": piece["page_start"],
                "page_end": piece["page_end"],
                "needs_vision_check": bool(has_marker or touches_bad_page),
                "text": f"{breadcrumb}\n{piece['text']}",
            })
    return result



# Main
def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        pages = json.load(f)

    all_lines, report = load_clean_lines(pages)
    sections = split_into_sections(all_lines)
    garbled_printed = {printed for _, printed in report["garbled_pages"]}
    chunks = build_chunks(sections, garbled_printed)

    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
        for c in chunks:
            flag = "  [CHECK: garbled text]" if c["needs_vision_check"] else ""
            pages_txt = (f"p.{c['page_start']}" if c["page_start"] == c["page_end"]
                         else f"pp.{c['page_start']}-{c['page_end']}")
            f.write(f"=== {c['chunk_id']} | Unit {c['unit']} | {c['section_id']} | {pages_txt}{flag}\n")
            f.write(c["text"] + "\n\n")

    sizes = [len(c["text"].split()) for c in chunks]
    flagged = sum(c["needs_vision_check"] for c in chunks)
    print(f"Chunks created      : {len(chunks)}")
    print(f"Words per chunk     : min {min(sizes)}, median {int(statistics.median(sizes))}, max {max(sizes)}")
    print(f"Arrows restored     : {report['arrows_added']} (best guess)")
    print(f"Unit-opening pages skipped (printed page): {[p for _, p in report['skipped_unit_openers']]}")
    print(f"Empty pages (printed page)               : {[p for _, p in report['empty_pages']]}")
    print(f"Garbled pages (printed page)             : {[p for _, p in report['garbled_pages']]}")
    print(f"Chunks flagged for a vision check        : {flagged}")
    print(f"\nSaved {CHUNKS_FILE} and {PREVIEW_FILE}. Open the preview file and proofread a few chunks.")


if __name__ == "__main__":
    main()