from bs4 import BeautifulSoup, NavigableString, Tag
import re
import json

ROMAN_RE = re.compile(r'^[IVXLCDM]+\.?$')
ARABIC_RE = re.compile(r'^\d+\.?$')
LETTER_RE = re.compile(r'[A-Za-zА-Яа-яЁё]')
HEADWORD_RE = re.compile(r'^[А-ЯЁ][А-Яа-яЁё́\-]+,$')

def norm_fragment(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def norm_output(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([,.;:?!])', r'\1', text)
    text = re.sub(r'([«(])\s+', r'\1', text)
    text = re.sub(r'\s+([»)])', r'\1', text)
    return text.strip()

def is_bold(node) -> bool:
    cur = node.parent
    while isinstance(cur, Tag):
        if cur.name in ('b', 'strong'):
            return True
        cur = cur.parent
    return False

def is_italic(node) -> bool:
    cur = node.parent
    while isinstance(cur, Tag):
        if cur.name in ('i', 'em'):
            return True
        style = (cur.get('style') or '').lower()
        if 'italic' in style:
            return True
        cur = cur.parent
    return False

def paragraph_segments(p):

    segments = []

    for node in p.descendants:
        if not isinstance(node, NavigableString):
            continue

        text = norm_fragment(str(node))
        if not text:
            continue

        seg = {
            "text": text,
            "bold": is_bold(node),
            "italic": is_italic(node),
        }

        if segments and segments[-1]["bold"] == seg["bold"] and segments[-1]["italic"] == seg["italic"]:
            segments[-1]["text"] += " " + seg["text"]
        else:
            segments.append(seg)

    return segments

def read_marker(segments, i):
    if i >= len(segments) or not segments[i]["bold"]:
        return None

    buf = ""
    j = i

    while j < len(segments) and segments[j]["bold"]:
        buf += segments[j]["text"]
        candidate = re.sub(r'\s+', '', buf)

        if ROMAN_RE.fullmatch(candidate):
            return ("roman", candidate.rstrip('.'), j + 1)

        if ARABIC_RE.fullmatch(candidate):
            return ("arabic", candidate.rstrip('.'), j + 1)

        j += 1

    return None

def has_any_marker(all_paragraphs):
    for p in all_paragraphs:
        segs = paragraph_segments(p)
        i = 0
        while i < len(segs):
            marker = read_marker(segs, i)
            if marker:
                return True
            i += 1
    return False

def paragraph_has_marker(segs):
    i = 0
    while i < len(segs):
        if read_marker(segs, i):
            return True
        i += 1
    return False

def ignorable_prefix(text: str) -> bool:
    text = norm_fragment(text)
    if not text:
        return True

    text = re.sub(r'⸢[^⸣]+⸣', '', text)
    text = re.sub(r'[—–\-|,:;()\[\]{}<>]+', '', text)
    text = text.strip()

    return text == "" or not LETTER_RE.search(text)

def create_group(label=None):
    return {
        "label": label,
        "definition": "",
        "meanings": []
    }

def create_meaning(label=None):
    return {
        "label": label,
        "definition": ""
    }

def append_text(obj, piece):
    piece = norm_fragment(piece)
    if not piece:
        return
    if obj["definition"]:
        obj["definition"] += " " + piece
    else:
        obj["definition"] = piece

def extract_definitions(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")

    numbered_article = has_any_marker(paragraphs)

    result = {"groups": []}

    current_group = None
    current_meaning = None
    collecting = None

    article_started = False

    for p_index, p in enumerate(paragraphs):
        segs = paragraph_segments(p)
        if not segs:
            continue

        para_text = norm_output(" ".join(seg["text"] for seg in segs))

        if para_text.startswith("~"):
            break

        first_bold = None
        for seg in segs:
            if seg["bold"]:
                first_bold = seg["text"]
                break
            elif LETTER_RE.search(seg["text"]):
                break

        if article_started and first_bold:
            joined = re.sub(r'\s+', '', first_bold)
            if not ROMAN_RE.fullmatch(joined) and not ARABIC_RE.fullmatch(joined):
                if "," in first_bold and LETTER_RE.search(first_bold):
                    break

        para_has_num = paragraph_has_marker(segs)
        prefix_is_ignorable = True

        i = 0
        while i < len(segs):
            seg = segs[i]
            text = seg["text"]

            marker = read_marker(segs, i)
            if marker:
                kind, label, next_i = marker
                article_started = True

                if kind == "roman":
                    current_group = create_group(label)
                    result["groups"].append(current_group)
                    current_meaning = None
                    collecting = "group"

                elif kind == "arabic":
                    if current_group is None:
                        current_group = create_group(None)
                        result["groups"].append(current_group)

                    current_meaning = create_meaning(label)
                    current_group["meanings"].append(current_meaning)
                    collecting = "meaning"

                prefix_is_ignorable = False
                i = next_i
                continue

            if collecting == "group" and seg["italic"]:
                append_text(current_group, text)
                article_started = True
                prefix_is_ignorable = False
                i += 1
                continue

            if collecting == "meaning" and seg["italic"]:
                append_text(current_meaning, text)
                article_started = True
                prefix_is_ignorable = False
                i += 1
                continue


            if collecting is None and seg["italic"]:
                can_open_implicit = (
                    (not numbered_article) or
                    (not para_has_num and prefix_is_ignorable)
                )

                if can_open_implicit:
                    if current_group is None:
                        current_group = create_group(None)
                        result["groups"].append(current_group)

                    current_meaning = create_meaning(None)
                    current_group["meanings"].append(current_meaning)
                    collecting = "meaning"

                    append_text(current_meaning, text)
                    article_started = True
                    prefix_is_ignorable = False
                    i += 1
                    continue


            if collecting is not None and (not seg["italic"]) and LETTER_RE.search(text):
                collecting = None

            if not ignorable_prefix(text):
                prefix_is_ignorable = False

            i += 1

    for group in result["groups"]:
        group["definition"] = norm_output(group["definition"])
        for meaning in group["meanings"]:
            meaning["definition"] = norm_output(meaning["definition"])

    cleaned_groups = []
    for group in result["groups"]:
        group["meanings"] = [m for m in group["meanings"] if m["definition"]]
        if group["definition"] or group["meanings"]:
            cleaned_groups.append(group)

    result["groups"] = cleaned_groups
    return result

import os
import glob

def process_files(input_dir, output_dir):
    """
    Обрабатывает все HTML файлы в подпапках input_dir и сохраняет результаты в output_dir.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    html_files = glob.glob(os.path.join(input_dir, "**", "*.html"), recursive=True)
    print(f"Найдено {len(html_files)} HTML файлов для обработки.")
    
    processed_count = 0
    for filepath in html_files:
        try:
            result = extract_definitions(filepath)
            if result:
                filename = os.path.basename(filepath)
                json_filename = os.path.splitext(filename)[0] + '.json'
                output_filepath = os.path.join(output_dir, json_filename)
                
                with open(output_filepath, 'w', encoding='utf-8-sig') as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)
                processed_count += 1
        except Exception as e:
            pass # ignore parse errors for now
            
    print(f"Успешно обработано {processed_count} файлов.")

if __name__ == "__main__":
    INPUT_DIR = r'F:\dictionary_parsing\data\samples_html\Output_1-23_html'
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
    
    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {OUTPUT_DIR}")
    
    process_files(INPUT_DIR, OUTPUT_DIR)

