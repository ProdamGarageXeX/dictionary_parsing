import os
import json
import re
import html as html_lib
import docx
import glob

LETTER_CHARS = r"A-Za-zА-Яа-яЁё"
ROMAN_OR_DIGIT_RE = re.compile(r"(?:[IVXLCDM]+|\d+)\b")


def get_source_ciphers(sources_path):
    """Извлекает шифры из указателя источников."""
    doc = docx.Document(sources_path)
    ciphers = set()
    cipher_split = re.compile(r"\s+[—–-]\s+")
    for para in doc.paragraphs:
        text = para.text.strip()
        parts = cipher_split.split(text)
        if len(parts) > 1:
            cipher = parts[0].replace("*", "").strip()
            if 0 < len(cipher) < 40:
                ciphers.add(cipher)
    return sorted(list(ciphers), key=len, reverse=True)


def build_cipher_re(ciphers_regex_str):
    """Не даёт короткому шифру совпасть внутри длинного, например `АР` внутри `САР`."""
    return re.compile(rf"(?<![{LETTER_CHARS}])(?:{ciphers_regex_str})(?![{LETTER_CHARS}])")


def find_source_block_end(text, start_pos, cipher_re, initial_end=None):
    """Ищет конец цельного блока ссылок, не обрываясь на `Тв. I 314.`."""
    search_pos = initial_end if initial_end is not None else start_pos

    while True:
        period_pos = text.find(".", search_pos)
        if period_pos == -1:
            return None

        next_pos = period_pos + 1
        while next_pos < len(text) and text[next_pos].isspace():
            next_pos += 1

        if next_pos >= len(text):
            return period_pos + 1

        tail = text[next_pos:]

        if ROMAN_OR_DIGIT_RE.match(tail):
            search_pos = period_pos + 1
            continue

        if cipher_re.match(tail):
            search_pos = period_pos + 1
            continue

        return period_pos + 1


def find_source_blocks(text, ciphers_regex_str):
    """Склеивает подряд идущие шифры и их библиографические хвосты в один source."""
    cipher_re = build_cipher_re(ciphers_regex_str)
    blocks = []
    search_pos = 0

    while True:
        match = cipher_re.search(text, search_pos)
        if not match:
            break

        block_end = find_source_block_end(
            text,
            match.start(),
            cipher_re,
            initial_end=match.end(),
        )
        if block_end is None:
            break

        blocks.append((match.start(), block_end))
        search_pos = block_end

    return blocks


def parse_html_article(html_path, ciphers_regex_str):
    """Парсит один HTML-файл и выделяет цитаты и источники."""
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        html = re.sub(r"<\s*i\b[^>]*>", "[_I_]", html, flags=re.IGNORECASE)
        html = re.sub(r"<\s*/\s*i\s*>", "[/_I_]", html, flags=re.IGNORECASE)
        html = re.sub(r"<\s*b\b[^>]*>", "[_B_]", html, flags=re.IGNORECASE)
        html = re.sub(r"<\s*/\s*b\s*>", "[/_B_]", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = html_lib.unescape(text)
        text = re.sub(r"\s+", " ", text)

        first_definition_match = re.search(r"\[_B_\](?:[IVXLCDM]+|\d+)\.\[/_B_\]", text)
        if first_definition_match:
            text = text[first_definition_match.start():]

        matches = find_source_blocks(text, ciphers_regex_str)
        results = []
        last_end = 0

        for start, end in matches:
            quote_part = text[last_end:start].strip()

            note = None
            note_match = re.search(r"\|\|?\s*\[_I_\](.*?)\[/_I_\]\s*(?=[A-ZА-ЯЁ\[<«])", quote_part)
            if note_match:
                note_text = note_match.group(1).strip()
                if note_text:
                    note_text = re.sub(r"\[/?_[BI]_\]", "", note_text).strip()
                    note = f"[ {note_text} ]"
                quote_part = quote_part[:note_match.start()] + quote_part[note_match.end():]

            parts = re.split(r"\[/_[BI]_\][\s.,;:\-()]*?(?=[A-ZА-ЯЁ\[<«])", quote_part)
            if len(parts) > 1:
                quote_part = parts[-1]

            quote_part = re.sub(r"^[\s\|]+", "", quote_part)
            quote_part = re.sub(r"^[,\.;\s]+|[,\s]+$", "", quote_part)
            quote_part = re.sub(r"^(?:[IVXLCDM]+\.|\d+\.)\s*", "", quote_part)
            quote_part = re.sub(r"\[/?_[BI]_\]", "", quote_part).strip()

            item = {
                "quote": quote_part,
                "source": text[start:end].strip(),
            }
            if note:
                item["syntactic_grammatic_sign"] = note

            results.append(item)
            last_end = end

        return results
    except Exception as e:
        print(f"Ошибка в файле {html_path}: {e}")
        return []


def process_files(input_dir, output_dir, sources_path):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Загрузка шифров из {sources_path}...")
    ciphers_list = get_source_ciphers(sources_path)
    escaped_ciphers = [re.escape(cipher) for cipher in ciphers_list]
    ciphers_regex_str = "|".join(escaped_ciphers)
    print(f"Загружено {len(ciphers_list)} шифров.")

    html_files = glob.glob(os.path.join(input_dir, "**", "*.html"), recursive=True)
    print(f"Найдено {len(html_files)} HTML файлов для обработки.")

    processed_count = 0
    for filepath in html_files:
        try:
            result = parse_html_article(filepath, ciphers_regex_str)
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
    SOURCES_PATH = r"F:\dictionary_parsing\docs\Указатель_источников_Сл_XVIII_16_04_2025.docx"

    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {OUTPUT_DIR}")

    process_files(INPUT_DIR, OUTPUT_DIR, SOURCES_PATH)
