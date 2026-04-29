import argparse
import glob
import html
import importlib.util
import json
import os
import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "samples_html" / "Output_1-23_html"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().with_name("output")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DOCS_DIR = PROJECT_ROOT / "docs"

LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
ROMAN_RE = re.compile(r"^[IVXLCDM]+\.?$")
ARABIC_RE = re.compile(r"^\d+\.?$")
HEADWORD_RE = re.compile(r"^[А-ЯЁ][А-ЯЁа-яё0-9ІѢѲѴ́'’\- ,]+$")
SPACE_RE = re.compile(r"\s+")
SUBMEANING_RE = re.compile(r"^(\d+\)|[а-яё]\))$", re.IGNORECASE)
SOURCE_HINT_RE = re.compile(r"(?:\[[^\]]+:\]|[А-ЯЁA-Z][а-яёa-z]+\. ?[IVXLC\d])")
INLINE_SPLIT_RE = re.compile(
    r"(\|\||\||(?<![A-Za-zА-Яа-яЁё0-9])\d+\)(?=\s)|(?<![A-Za-zА-Яа-яЁё0-9])[а-яё]\)(?=\s))",
    re.IGNORECASE,
)
TAG_TEXT_RE = re.compile(
    r"(?:⸢|â¸¢|Ã¢Â¸Â¢|ÃƒÂ¢Ã‚Â¸Ã‚Â¢)SYM_[A-Z0-9_]+(?:⸣|â¸£|Ã¢Â¸Â£|ÃƒÂ¢Ã‚Â¸Ã‚Â£)"
)

GRAMMAR_TAGS = [
    "абсолют.", "адверб.", "адъект.", "без доп.", "безл.", "буд.", "в.",
    "вводн. сл.", "возвр.", "вопрос.", "восклиц.", "вр.", "гл.", "д.",
    "дв.", "деепр.", "доп.", "ед.", "ж.", "зв.", "изъяснит.", "им.",
    "имперф.", "инф.", "колич.", "кратк. ф.", "л.", "личн.", "м.",
    "межд.", "мест.", "мн.", "многокр.", "накл.", "нареч.", "нариц.",
    "наст.", "начинат.", "неизм.", "неопр.", "нескл.", "несов.",
    "однокр.", "определ.", "относ.", "отриц.", "п.", "повел.",
    "полн. ф.", "порядк.", "пр.", "превосх.", "предикат.", "предл.",
    "придат.", "прил.", "присоединит.", "притяж.", "прич.", "противит.",
    "прош.", "р.", "разделит.", "род.", "сказ.", "собир.", "собств.",
    "сов.", "соединит.", "соотносит.", "сопоставит.", "ср.", "сравн.",
    "сравнит.", "страд.", "субст.", "сущ.", "тв.", "указ.", "усилит.",
    "условн.", "уступит.", "ч.", "числ.", "кн.-слав.", "союз.", "част.",
]
GRAMMAR_TAG_PATTERN = re.compile(
    rf"(?<!\()(?<![А-Яа-яЁёA-Za-z\-])({'|'.join(map(re.escape, GRAMMAR_TAGS))})(?![А-Яа-яЁёA-Za-z])(?!\))"
)


class RichHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts = []
        self.in_title = False
        self.stack = []
        self.current_paragraph = []
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)
        style = (attrs_dict.get("style") or "").lower()

        italic = tag in {"i", "em"} or "italic" in style
        bold = tag in {"b", "strong"} or "bold" in style
        sup = tag == "sup"

        if tag == "title":
            self.in_title = True
        elif tag == "p":
            self.current_paragraph = []

        self.stack.append((tag, italic, bold, sup))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "p":
            if self.current_paragraph:
                self.paragraphs.append(self.current_paragraph)
            self.current_paragraph = []

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack.pop(index)
                break

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

        if not data:
            return
        if not self.current_paragraph and not data.strip():
            return

        italic = any(item[1] for item in self.stack)
        bold = any(item[2] for item in self.stack)
        sup = any(item[3] for item in self.stack)
        self._append_segment(data, italic=italic, bold=bold, sup=sup)

    def _append_segment(self, text, italic, bold, sup):
        if not text:
            return
        if (
            self.current_paragraph
            and self.current_paragraph[-1]["italic"] == italic
            and self.current_paragraph[-1]["bold"] == bold
            and self.current_paragraph[-1]["sup"] == sup
        ):
            self.current_paragraph[-1]["text"] += text
        else:
            self.current_paragraph.append(
                {"text": text, "italic": italic, "bold": bold, "sup": sup}
            )


def normalize_text(text: str) -> str:
    text = html.unescape(text.replace("\xa0", " "))
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = TAG_TEXT_RE.sub("", text)
    text = normalize_text(text)
    text = re.sub(r"\s+([,.;:?!\)])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text.strip()


def normalize_marker(text: str) -> str:
    return re.sub(r"\s+", "", clean_text(text))


def parse_html_document(html_content: str):
    parser = RichHTMLParser()
    parser.feed(html_content)
    title = clean_text("".join(parser.title_parts))
    return title, parser.paragraphs


def paragraph_plain_text(segments: list[dict]) -> str:
    return clean_text(" ".join(segment["text"] for segment in segments))


def raw_join(segments: list[dict], start: int = 0, end: int | None = None) -> str:
    return "".join(segment["text"] for segment in segments[start:end])


def update_parenthesis_level(level: int, text: str) -> int:
    for char in text:
        if char == "(":
            level += 1
        elif char == ")" and level > 0:
            level -= 1
    return level


def read_bold_run(segments: list[dict], start_index: int):
    end_index = start_index
    while end_index < len(segments) and segments[end_index]["bold"]:
        end_index += 1

    run_segments = segments[start_index:end_index]
    display_text = clean_text(raw_join(run_segments))
    core_text = clean_text(
        "".join(segment["text"] for segment in run_segments if not segment["sup"])
    )
    sup_text = clean_text(
        "".join(segment["text"] for segment in run_segments if segment["sup"])
    )
    return {
        "display": display_text,
        "core": core_text,
        "sup": sup_text,
        "start": start_index,
        "end": end_index,
    }


def extract_file_superscript_index(filename: str) -> str:
    stem = Path(filename).stem
    tail = stem.split("_", 1)[-1]
    match = re.search(r"(\d+)$", tail)
    return match.group(1) if match else ""


def extract_title_superscript_index(title: str) -> str:
    match = re.search(r"(\d+)$", title)
    return match.group(1) if match else ""


def split_headword_and_superscript(headword: str, superscript_index: str):
    text = headword.strip(" ,.;:")
    if not superscript_index:
        match = re.match(r"^(.*?)(\d+)$", text)
        if match and LETTER_RE.search(match.group(1)):
            return match.group(1).strip(" ,.;:"), match.group(2)
    return text, superscript_index


def extract_title_info(title: str, paragraphs: list[list[dict]], filename: str):
    result = {
        "display_title": title,
        "headwords": [],
        "notes": [],
    }
    if not paragraphs:
        return result

    segments = paragraphs[0]
    stop_index = len(segments)
    parenthesis_level = 0
    index = 0

    while index < len(segments):
        segment = segments[index]
        if segment["bold"]:
            run = read_bold_run(segments, index)
            run_marker = normalize_marker(run["display"]).rstrip(".")
            if parenthesis_level == 0 and (
                ROMAN_RE.fullmatch(run_marker) or ARABIC_RE.fullmatch(run_marker)
            ):
                stop_index = index
                break

            for item in segments[index:run["end"]]:
                parenthesis_level = update_parenthesis_level(parenthesis_level, item["text"])
            index = run["end"]
            continue

        if segment["italic"] and parenthesis_level == 0:
            stop_index = index
            break

        parenthesis_level = update_parenthesis_level(parenthesis_level, segment["text"])
        index += 1

    prefix_segments = segments[:stop_index]
    prefix_text = raw_join(prefix_segments)
    result["notes"] = [clean_text(match) for match in re.findall(r"\([^)]*\)", prefix_text)]

    index = 0
    while index < len(prefix_segments):
        if prefix_segments[index]["bold"]:
            run = read_bold_run(prefix_segments, index)
            marker = normalize_marker(run["display"]).rstrip(".")
            if ROMAN_RE.fullmatch(marker) or ARABIC_RE.fullmatch(marker):
                break

            headword = run["core"]
            superscript_index = run["sup"]
            headword, superscript_index = split_headword_and_superscript(
                headword, superscript_index
            )

            if LETTER_RE.search(headword):
                result["headwords"].append(
                    {
                        "headword": headword,
                        "superscript_index": superscript_index,
                        "raw_bold": run["display"],
                    }
                )

            index = run["end"]
            continue

        index += 1

    fallback_superscript_index = (
        extract_title_superscript_index(title) or extract_file_superscript_index(filename)
    )
    if result["headwords"] and fallback_superscript_index:
        if not any(item["superscript_index"] for item in result["headwords"]):
            result["headwords"][0]["superscript_index"] = fallback_superscript_index

    return result


def read_definition_marker(segments: list[dict], index: int):
    if index >= len(segments) or not segments[index]["bold"]:
        return None

    run = read_bold_run(segments, index)
    candidate = normalize_marker(run["display"])
    if ROMAN_RE.fullmatch(candidate):
        return ("roman", candidate.rstrip("."), run["end"])
    if ARABIC_RE.fullmatch(candidate):
        return ("arabic", candidate.rstrip("."), run["end"])
    return None


def paragraph_has_definition_marker(segments: list[dict]) -> bool:
    index = 0
    while index < len(segments):
        marker = read_definition_marker(segments, index)
        if marker:
            return True
        index += 1
    return False


def has_any_definition_marker(paragraphs: list[list[dict]]) -> bool:
    return any(paragraph_has_definition_marker(paragraph) for paragraph in paragraphs)


def ignorable_prefix(text: str) -> bool:
    text = clean_text(text)
    if not text:
        return True
    text = re.sub(r"[—–\-|,:;()\[\]{}<>]+", "", text)
    return not text or not LETTER_RE.search(text)


def create_definition_group(label: str | None = None):
    return {"label": label, "definition": "", "meanings": []}


def create_meaning(label: str | None = None):
    return {"label": label, "definition": ""}


def append_definition_text(target: dict, text: str):
    piece = clean_text(text)
    if not piece:
        return
    if target["definition"]:
        target["definition"] += " " + piece
    else:
        target["definition"] = piece


def extract_definitions_from_paragraphs(paragraphs: list[list[dict]]):
    numbered_article = has_any_definition_marker(paragraphs)
    result = {"groups": []}

    current_group = None
    current_meaning = None
    collecting = None
    article_started = False

    for paragraph in paragraphs:
        segments = [segment for segment in paragraph if clean_text(segment["text"])]
        if not segments:
            continue

        paragraph_text = paragraph_plain_text(segments)
        if paragraph_text.startswith("~"):
            break

        first_bold = None
        index = 0
        while index < len(segments):
            if segments[index]["bold"]:
                first_bold = read_bold_run(segments, index)["display"]
                break
            if LETTER_RE.search(clean_text(segments[index]["text"])):
                break
            index += 1

        if article_started and first_bold:
            joined = normalize_marker(first_bold)
            if not ROMAN_RE.fullmatch(joined) and not ARABIC_RE.fullmatch(joined):
                if "," in first_bold and LETTER_RE.search(first_bold):
                    break

        paragraph_has_marker = paragraph_has_definition_marker(segments)
        prefix_is_ignorable = True

        index = 0
        while index < len(segments):
            segment = segments[index]
            text = segment["text"]
            marker = read_definition_marker(segments, index)

            if marker:
                kind, label, next_index = marker
                article_started = True
                if kind == "roman":
                    current_group = create_definition_group(label)
                    result["groups"].append(current_group)
                    current_meaning = None
                    collecting = "group"
                else:
                    if current_group is None:
                        current_group = create_definition_group(None)
                        result["groups"].append(current_group)
                    current_meaning = create_meaning(label)
                    current_group["meanings"].append(current_meaning)
                    collecting = "meaning"

                prefix_is_ignorable = False
                index = next_index
                continue

            if collecting == "group" and segment["italic"]:
                append_definition_text(current_group, text)
                article_started = True
                prefix_is_ignorable = False
                index += 1
                continue

            if collecting == "meaning" and segment["italic"]:
                append_definition_text(current_meaning, text)
                article_started = True
                prefix_is_ignorable = False
                index += 1
                continue

            if collecting is None and segment["italic"]:
                can_open_implicit = (not numbered_article) or (
                    not paragraph_has_marker and prefix_is_ignorable
                )
                if can_open_implicit:
                    if current_group is None:
                        current_group = create_definition_group(None)
                        result["groups"].append(current_group)
                    current_meaning = create_meaning(None)
                    current_group["meanings"].append(current_meaning)
                    collecting = "meaning"
                    append_definition_text(current_meaning, text)
                    article_started = True
                    prefix_is_ignorable = False
                    index += 1
                    continue

            if collecting is not None and (not segment["italic"]) and LETTER_RE.search(text):
                collecting = None

            if not ignorable_prefix(text):
                prefix_is_ignorable = False

            index += 1

    cleaned_groups = []
    for group in result["groups"]:
        group["definition"] = clean_text(group["definition"])
        group["meanings"] = [
            {"label": meaning["label"], "definition": clean_text(meaning["definition"])}
            for meaning in group["meanings"]
            if clean_text(meaning["definition"])
        ]
        if group["definition"] or group["meanings"]:
            cleaned_groups.append(group)

    result["groups"] = cleaned_groups
    return result


def extract_grammar_tags(text: str):
    found = []
    for match in GRAMMAR_TAG_PATTERN.finditer(text):
        tag = match.group(1)
        if tag and tag not in found:
            found.append(tag)
    return found


def is_uppercase_headword(text: str) -> bool:
    plain = text.replace("́", "").strip(".,;: ")
    return bool(plain and plain == plain.upper() and LETTER_RE.search(plain))


def looks_like_derivative(text: str) -> bool:
    plain = text.strip(".,;: ")
    return bool(plain and plain[0].isupper() and LETTER_RE.search(plain))


def add_unique(target: list[str], items: list[str]):
    for item in items:
        if item not in target:
            target.append(item)


def ensure_section(sections: list[dict], section_id: str):
    for section in sections:
        if section["id"] == section_id:
            return section
    section = {"id": section_id, "tags": []}
    sections.append(section)
    return section


def ensure_derivative(derivatives: list[dict], word: str):
    for derivative in derivatives:
        if derivative["word"] == word:
            return derivative
    derivative = {"word": word, "tags": []}
    derivatives.append(derivative)
    return derivative


def extract_grammatical_tags_from_paragraphs(
    title_info: dict, paragraphs: list[list[dict]]
):
    result = {
        "main_tags": [],
        "sections": [],
        "derivatives": [],
    }

    known_headwords = {item["headword"].replace("́", "").strip() for item in title_info["headwords"]}
    current_node = result["main_tags"]
    current_section = None
    first_paragraph = True

    for paragraph in paragraphs:
        segments = [segment for segment in paragraph if segment["text"]]
        if not segments:
            continue

        index = 0
        while index < len(segments):
            segment = segments[index]

            if segment["bold"]:
                run = read_bold_run(segments, index)
                display = clean_text(run["display"])
                plain = display.replace("́", "").strip(".,;: ")
                marker = normalize_marker(display).rstrip(".")

                if ROMAN_RE.fullmatch(marker) or ARABIC_RE.fullmatch(marker):
                    current_section = ensure_section(result["sections"], marker)
                    current_node = current_section["tags"]
                    index = run["end"]
                    continue

                if plain in known_headwords and first_paragraph:
                    current_node = result["main_tags"]
                    index = run["end"]
                    continue

                if is_uppercase_headword(display) and first_paragraph:
                    current_node = result["main_tags"]
                    index = run["end"]
                    continue

                if looks_like_derivative(display):
                    derivative = ensure_derivative(result["derivatives"], display.strip())
                    current_node = derivative["tags"]
                    index = run["end"]
                    continue

            if segment["italic"]:
                tags = extract_grammar_tags(clean_text(segment["text"]))
                add_unique(current_node, tags)

            index += 1

        first_paragraph = False

    return result


def explode_segments(segments: list[dict]):
    exploded = []
    for segment in segments:
        parts = [part for part in INLINE_SPLIT_RE.split(segment["text"]) if part]
        if not parts:
            continue
        for part in parts:
            exploded.append(
                {
                    "text": part,
                    "italic": segment["italic"],
                    "bold": segment["bold"],
                }
            )
    return exploded


def is_submeaning_segment(text: str) -> bool:
    return bool(SUBMEANING_RE.fullmatch(clean_text(text)))


def is_meaning_marker_segment(segment: dict) -> bool:
    if not segment["bold"]:
        return False
    marker = normalize_marker(segment["text"])
    return bool(ROMAN_RE.fullmatch(marker) or ARABIC_RE.fullmatch(marker))


def is_headword_segment(segment: dict) -> bool:
    if not segment["bold"]:
        return False
    text = clean_text(segment["text"]).rstrip(",")
    return bool(
        text
        and HEADWORD_RE.fullmatch(text)
        and not ROMAN_RE.fullmatch(text)
        and not ARABIC_RE.fullmatch(text)
    )


def is_punctuation_only(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return True
    cleaned = cleaned.replace("..", "")
    return not LETTER_RE.search(cleaned)


def prefix_can_open_description(prefix_text: str) -> bool:
    prefix = clean_text(prefix_text)
    if not prefix:
        return True

    prefix = re.sub(r"\[[^\]]+\]", "", prefix)
    prefix = re.sub(r"\([^)]*\)", "", prefix)
    prefix = re.sub(r"\b\d{3,4}(?:-е)?\b", "", prefix)
    prefix = re.sub(r"[|—–,:;.\-]", " ", prefix)
    words = [word for word in prefix.split() if LETTER_RE.search(word)]
    if not words:
        return True

    long_lower_words = [
        word for word in words if word[:1].islower() and len(word.strip(".,")) > 3
    ]
    return not long_lower_words


def looks_like_meta_segment(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return True

    lowered = cleaned.lower()
    if lowered.startswith(
        (
            "употр.",
            "в сравнит.",
            "в вопрос.",
            "в ритор.",
            "в придат.",
            "в знач.",
            "в сочетании",
            "в функции",
            "в вводн.",
        )
    ):
        return True

    if lowered in GRAMMAR_TAGS:
        return True

    compact = lowered.replace(",", " ").replace(";", " ").split()
    if compact and all(token in GRAMMAR_TAGS for token in compact):
        return True

    if re.fullmatch(r"(?:[а-яё-]{1,4}\.|[а-яё-]{1,3})(?:\s+(?:[а-яё-]{1,4}\.|[а-яё-]{1,3}))*", lowered):
        return True

    return False


def extract_cluster(segments: list[dict], start_index: int):
    items = []
    index = start_index
    seen_italic = False

    while index < len(segments):
        segment = segments[index]
        if segment["bold"] and is_meaning_marker_segment(segment):
            break

        if segment["italic"]:
            items.append({"text": segment["text"], "italic": True})
            seen_italic = True
            index += 1
            continue

        if seen_italic and is_punctuation_only(segment["text"]):
            items.append({"text": segment["text"], "italic": False})
            index += 1
            continue

        break

    return items, index


def split_cluster(items: list[dict]):
    italic_positions = [index for index, item in enumerate(items) if item["italic"]]
    if not italic_positions:
        return [], ""

    first_description_pos = None
    for position in italic_positions:
        if not looks_like_meta_segment(items[position]["text"]):
            first_description_pos = position
            break

    if first_description_pos is None:
        lead_tags = [
            clean_text(items[position]["text"])
            for position in italic_positions
            if clean_text(items[position]["text"])
        ]
        return lead_tags, ""

    lead_tags = []
    for position in italic_positions:
        if position < first_description_pos:
            text = clean_text(items[position]["text"])
            if text:
                lead_tags.append(text)

    description = clean_text("".join(item["text"] for item in items[first_description_pos:]))
    return lead_tags, description


def is_morphology_only_description(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return True

    lowered = cleaned.lower()
    pieces = [part.strip() for part in lowered.split(",") if part.strip()]
    if pieces and all(part in GRAMMAR_TAGS for part in pieces):
        return True

    if re.fullmatch(r"[а-яё]{1,3}\.,?\s*[а-яё]{1,3}\.?", lowered):
        return True

    if re.fullmatch(r"[а-яё]{1,3},\s*[а-яё]{1,3}\.", lowered):
        return True

    return False


def filter_meaning_descriptions(records: list[dict]):
    filtered = []
    seen = set()

    for record in records:
        description = clean_text(record.get("verbal_description", ""))
        if not description or is_morphology_only_description(description):
            continue

        normalized_tags = tuple(clean_text(tag) for tag in record.get("lead_tags", []))
        key = (
            record.get("paragraph_index"),
            record.get("group_label"),
            record.get("meaning_label"),
            record.get("submeaning_label"),
            normalized_tags,
            description,
        )
        if key in seen:
            continue
        seen.add(key)

        item = dict(record)
        item["verbal_description"] = description
        item["lead_tags"] = list(normalized_tags)
        filtered.append(item)

    return filtered


def extract_meaning_descriptions_local(paragraphs: list[list[dict]], title: str):
    results = []
    current_group_label = None
    current_meaning_label = None
    current_submeaning_label = None

    for paragraph_index, raw_segments in enumerate(paragraphs, start=1):
        segments = explode_segments(raw_segments)
        plain_paragraph = paragraph_plain_text(segments)
        if not plain_paragraph:
            continue

        prefix_parts = []
        after_marker = False
        index = 0

        while index < len(segments):
            segment = segments[index]
            text = clean_text(segment["text"])
            if not text:
                index += 1
                continue

            if is_meaning_marker_segment(segment):
                marker = normalize_marker(segment["text"]).rstrip(".")
                if ROMAN_RE.fullmatch(marker):
                    current_group_label = marker
                    current_meaning_label = None
                    current_submeaning_label = None
                else:
                    current_meaning_label = marker
                    current_submeaning_label = None
                prefix_parts = []
                after_marker = True
                index += 1
                continue

            if is_headword_segment(segment):
                prefix_parts.append(text)
                index += 1
                continue

            if is_submeaning_segment(text):
                current_submeaning_label = text
                prefix_parts = []
                after_marker = True
                index += 1
                continue

            if text in {"|", "||"}:
                prefix_parts = []
                after_marker = True
                index += 1
                continue

            if segment["italic"]:
                can_open = after_marker or prefix_can_open_description(" ".join(prefix_parts))
                if can_open:
                    cluster_items, next_index = extract_cluster(segments, index)
                    lead_tags, description = split_cluster(cluster_items)
                    if description and not SOURCE_HINT_RE.search(description):
                        results.append(
                            {
                                "paragraph_index": paragraph_index,
                                "group_label": current_group_label,
                                "meaning_label": current_meaning_label,
                                "submeaning_label": current_submeaning_label,
                                "lead_tags": lead_tags,
                                "verbal_description": description,
                                "paragraph_text": plain_paragraph,
                            }
                        )
                    prefix_parts = []
                    after_marker = False
                    index = next_index
                    continue

            prefix_parts.append(text)
            if LETTER_RE.search(text):
                after_marker = False
            index += 1

    return {"title": title, "meaning_descriptions": results}


@lru_cache(maxsize=1)
def load_external_helpers():
    module_specs = {
        "citations": SCRIPTS_DIR / "almighty_architect" / "separate_citations.py",
        "collocations": SCRIPTS_DIR / "As_hen_ok" / "CollocationPhaseo.py",
        "etymology": SCRIPTS_DIR / "pedrobirq" / "find_etymologies_in_pipeline.py",
        "dynamic_tags": SCRIPTS_DIR / "ProdamGarageXeX" / "dynamic_tags.py",
    }

    modules = {}
    for name, path in module_specs.items():
        spec = importlib.util.spec_from_file_location(f"mvp_{name}", path)
        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise RuntimeError(f"Не удалось загрузить модуль: {path}")
        spec.loader.exec_module(module)
        modules[name] = module

    return modules


@lru_cache(maxsize=1)
def build_citation_regex():
    helpers = load_external_helpers()
    source_docs = sorted(DOCS_DIR.glob("Указатель_источников*.docx"))
    if not source_docs:
        raise FileNotFoundError("Не найден DOCX-указатель источников в папке docs")

    ciphers = helpers["citations"].get_source_ciphers(str(source_docs[0]))
    return "|".join(re.escape(cipher) for cipher in ciphers)


def trim_redundant_fields(records: list[dict], keys_to_drop: tuple[str, ...]):
    cleaned = []
    for record in records:
        item = {}
        for key, value in record.items():
            if key not in keys_to_drop:
                item[key] = value
        cleaned.append(item)
    return cleaned


def build_article_json(html_path: str | Path, source_root: str | Path):
    html_path = Path(html_path)
    source_root = Path(source_root)
    relative_path = html_path.relative_to(source_root)

    with open(html_path, "r", encoding="utf-8") as handle:
        html_content = handle.read()

    title, paragraphs = parse_html_document(html_content)
    title_info = extract_title_info(title, paragraphs, html_path.name)
    definitions = extract_definitions_from_paragraphs(paragraphs)
    grammar_tags = extract_grammatical_tags_from_paragraphs(title_info, paragraphs)

    helpers = load_external_helpers()

    citations = helpers["citations"].parse_html_article(
        str(html_path), build_citation_regex()
    )
    collocations = helpers["collocations"].scan_collocations(html_content)
    etymology_data = helpers["etymology"].parse_etymology(html_content, html_path.name)
    dynamic_tags = helpers["dynamic_tags"].parse_dynamic_tags(html_content, html_path.name)

    article = {
        "file": html_path.name,
        "release": relative_path.parts[0] if relative_path.parts else "",
        "title": title,
        "title_info": title_info,
        "definitions": definitions,
        "grammar_tags": grammar_tags,
        "citations": citations,
        "collocations": collocations,
        "etymology": {
            "paragraph_index": etymology_data.get("paragraph_index"),
            "text": etymology_data.get("etymology", ""),
            "paragraph_text": etymology_data.get("paragraph_text", ""),
        },
        "dynamic_tags": trim_redundant_fields(
            dynamic_tags,
            ("file", "title", "left_context", "right_context", "paragraph_text"),
        ),
    }
    return article


def list_html_files(source_root: str | Path):
    source_root = Path(source_root)
    return sorted(source_root.glob("**/*.html"))


def process_corpus(
    source_root: str | Path,
    output_root: str | Path,
    logger: Callable[[str], None] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    stop_event=None,
):
    source_root = Path(source_root)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    html_files = list_html_files(source_root)
    total = len(html_files)

    if logger:
        logger(f"Найдено {total} HTML-файлов")

    processed = 0
    written = 0
    errors = 0

    for html_path in html_files:
        if stop_event is not None and stop_event.is_set():
            if logger:
                logger("Обработка остановлена пользователем")
            break

        try:
            article_json = build_article_json(html_path, source_root)
            output_path = output_root / html_path.relative_to(source_root)
            output_path = output_path.with_suffix(".json")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8-sig") as handle:
                json.dump(article_json, handle, ensure_ascii=False, indent=4)
            written += 1
        except Exception as exc:
            errors += 1
            if logger:
                logger(f"Ошибка в {html_path.name}: {exc}")

        processed += 1
        if progress_callback:
            progress_callback(
                processed,
                total,
                str(html_path.relative_to(source_root)).replace("/", "\\"),
            )

    if logger:
        logger(
            f"Готово: обработано {processed}, записано {written}, ошибок {errors}"
        )

    return {
        "processed": processed,
        "written": written,
        "errors": errors,
        "total": total,
        "stopped": bool(stop_event is not None and stop_event.is_set()),
    }


def main():
    parser = argparse.ArgumentParser(description="MVP-пайплайн парсинга словарных статей")
    parser.add_argument("--source", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    process_corpus(
        source_root=args.source,
        output_root=args.output,
        logger=print,
        progress_callback=lambda current, total, relative: None,
    )


if __name__ == "__main__":
    main()
