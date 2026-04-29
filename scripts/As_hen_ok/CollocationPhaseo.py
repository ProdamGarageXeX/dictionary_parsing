import glob
import html
import json
import os
import re
from html.parser import HTMLParser

COLLOCATION_MARKERS = ("⸢SYM_COLLOCATION⸣", "â¸¢SYM_COLLOCATIONâ¸£")
PHRASEOLOGY_MARKERS = ("~",)
ALL_MARKERS = COLLOCATION_MARKERS + PHRASEOLOGY_MARKERS
PARA_BREAK = "\uE000"

ITALIC_OPEN_RE = re.compile(r"<\s*i\b[^>]*>", re.IGNORECASE)
ITALIC_CLOSE_RE = re.compile(r"<\s*/\s*i\s*>", re.IGNORECASE)
BOLD_OPEN_RE = re.compile(r"<\s*b\b[^>]*>", re.IGNORECASE)
BOLD_CLOSE_RE = re.compile(r"<\s*/\s*b\s*>", re.IGNORECASE)
PARA_OPEN_RE = re.compile(r"<\s*p\b[^>]*>", re.IGNORECASE)
PARA_CLOSE_RE = re.compile(r"<\s*/\s*p\s*>", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")
MARKER_SPLIT_RE = re.compile(r"(⸢SYM_COLLOCATION⸣|â¸¢SYM_COLLOCATIONâ¸£|~)")
ITALIC_LEAD_RE = re.compile(r"^(?:\s*\[_I_\][^[]*?\[/_I_\][\s,;:()\-]*)+")
SOURCE_TAIL_RE = re.compile(
    r"(?:[A-ZА-ЯЁ][^.!?]{0,60}\s(?:[IVXLCDM]+|\d+)[^.!?]{0,20}\.)$"
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ<\[])")
EXPRESSION_BOUNDARY_RE = re.compile(
    r"([.!?])\s+(?=(?:\[_I_\]|См\.|см\.|\d+\)|[A-ZА-ЯЁ«\[]))"
)


class InlineTextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "p":
            self.parts.append(PARA_BREAK)
        elif tag == "i":
            self.parts.append("[_I_]")
        elif tag == "b":
            self.parts.append("[_B_]")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "p":
            self.parts.append(PARA_BREAK)
        elif tag == "i":
            self.parts.append("[/_I_]")
        elif tag == "b":
            self.parts.append("[/_B_]")

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        return "".join(self.parts)


def normalize_text(text):
    text = text.replace("\xa0", " ")
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def strip_style_markers(text):
    text = text.replace("[_I_]", "").replace("[/_I_]", "")
    text = text.replace("[_B_]", "").replace("[/_B_]", "")
    return normalize_text(text)


def html_to_text_paragraphs(html_content):
    parser = InlineTextHTMLParser()
    parser.feed(html_content)
    html_content = html.unescape(parser.get_text())

    paragraphs = []
    for raw_line in html_content.split(PARA_BREAK):
        line = normalize_text(raw_line.replace("\r", " ").replace("\n", " "))
        if line:
            paragraphs.append(line)
    return paragraphs


def first_sentence(text):
    text = normalize_text(text)
    if not text:
        return "", ""

    match = EXPRESSION_BOUNDARY_RE.search(text)
    if match:
        end = match.end(1)
        head = text[:end].strip()
        tail = text[end:].strip()
        return head, tail

    return text, ""


def extract_leading_definition(text):
    match = ITALIC_LEAD_RE.match(text)
    if not match:
        return "", text

    definition = strip_style_markers(match.group(0))
    rest = text[match.end():].strip()
    return definition, rest


def split_illustrations(text):
    text = strip_style_markers(text)
    if not text:
        return []

    chunks = SENTENCE_SPLIT_RE.split(text)
    if len(chunks) == 1:
        return [text]

    illustrations = []
    buffer = []

    for chunk in chunks:
        piece = normalize_text(chunk)
        if not piece:
            continue

        buffer.append(piece)
        combined = " ".join(buffer).strip()
        if SOURCE_TAIL_RE.search(combined):
            illustrations.append(combined)
            buffer = []

    if buffer:
        tail = " ".join(buffer).strip()
        if tail:
            illustrations.append(tail)

    return illustrations


def parse_segment_content(segment_text):
    segment_text = normalize_text(segment_text)
    if not segment_text:
        return {
            "expression": "",
            "definition": "",
            "illustration_text": "",
            "illustrations": [],
        }

    expression, remainder = first_sentence(segment_text)
    expression = strip_style_markers(expression)
    remainder = remainder.strip()

    definition = ""
    if remainder.startswith("[_I_]"):
        definition, remainder = extract_leading_definition(remainder)
    elif remainder.startswith("См.") or remainder.startswith("см."):
        definition = strip_style_markers(remainder)
        remainder = ""

    illustration_text = strip_style_markers(remainder)
    illustrations = split_illustrations(remainder)

    return {
        "expression": expression,
        "definition": definition,
        "illustration_text": illustration_text,
        "illustrations": illustrations,
    }


def parse_marker_segments(paragraph_text):
    segments = []
    parts = MARKER_SPLIT_RE.split(paragraph_text)

    for i in range(1, len(parts), 2):
        marker = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        content = content.strip()
        if not content:
            continue

        entry_type = "collocation" if marker in COLLOCATION_MARKERS else "phraseology"
        parsed = parse_segment_content(content)
        parsed["marker"] = marker
        parsed["type"] = entry_type
        segments.append(parsed)

    return segments


def scan_collocations(html_content):
    results = []
    for paragraph in html_to_text_paragraphs(html_content):
        if not any(marker in paragraph for marker in ALL_MARKERS):
            continue
        results.extend(parse_marker_segments(paragraph))
    return results


def process_files(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    html_files = glob.glob(os.path.join(input_dir, "**", "*.html"), recursive=True)
    print(f"Найдено {len(html_files)} HTML файлов для обработки.")

    processed_count = 0
    for filepath in html_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                html_content = f.read()

            result = scan_collocations(html_content)
            if result:
                filename = os.path.basename(filepath)
                json_filename = os.path.splitext(filename)[0] + ".json"
                output_filepath = os.path.join(output_dir, json_filename)

                with open(output_filepath, "w", encoding="utf-8-sig") as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)
                processed_count += 1
        except Exception:
            pass

    print(f"Успешно обработано {processed_count} файлов.")


if __name__ == "__main__":
    INPUT_DIR = r"F:\dictionary_parsing\data\samples_html\Output_1-23_html"
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {OUTPUT_DIR}")

    process_files(INPUT_DIR, OUTPUT_DIR)
