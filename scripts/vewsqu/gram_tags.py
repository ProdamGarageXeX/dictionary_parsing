import re
from bs4 import BeautifulSoup

# Список грамматических помет
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
    "условн.", "уступит.", "ч.", "числ.", "кн.-слав.", "союз.", "част."
]

tags_pattern = "|".join(map(re.escape, GRAMMAR_TAGS))


PATTERN_POMETA = rf"(?<!\()(?<![А-Яа-яЁёA-Za-z\-])({tags_pattern})(?![А-Яа-яЁёA-Za-z])(?!\))"

class UniversalCorpusParser:
    def __init__(self):
        self.re_roman = re.compile(r'^(I{1,3}|IV|V|VI{0,3}|IX|X)\.?$')
        self.re_arabic = re.compile(r'^\d+\.?$')

    def _extract_text_and_styles(self, html_node):
        full_text = ""
        italic_flags = []
        bold_flags = []

        for elem in html_node.descendants:
            if isinstance(elem, str):
                text = elem
                if not text:
                    continue

                is_italic = False
                is_bold = False
                parent = elem.parent

                while parent and parent.name not in ['p', 'div', 'body']:
                    style = parent.get('style', '').lower()
                    if 'italic' in style: is_italic = True
                    if 'bold' in style: is_bold = True
                    if parent.name in ['b', 'strong']: is_bold = True
                    if parent.name in ['i', 'em']: is_italic = True
                    parent = parent.parent

                full_text += text
                italic_flags.extend([is_italic] * len(text))
                bold_flags.extend([is_bold] * len(text))

        return full_text, italic_flags, bold_flags

    def _get_bold_phrases(self, full_text, bold_flags):
        phrases = []
        current_phrase = ""
        start_idx = -1

        for i, char in enumerate(full_text):
            if bold_flags[i]:
                if not current_phrase:
                    start_idx = i
                current_phrase += char
            else:
                if current_phrase.strip():
                    phrases.append((current_phrase.strip(), start_idx))
                current_phrase = ""

        if current_phrase.strip():
            phrases.append((current_phrase.strip(), start_idx))

        return phrases

    def _extract_pomety(self, text_chunk, start_offset, italic_flags):
        found = []
        matches = re.finditer(PATTERN_POMETA, text_chunk)

        for match in matches:
            tag_text = match.group(1)
            # Игнорируем заглавные
            if tag_text[0].isupper():
                continue

            match_start_in_full = start_offset + match.start()
            match_end_in_full = start_offset + match.end()

            # Если хотя бы часть пометы выделена курсивом
            if any(italic_flags[match_start_in_full:match_end_in_full]):
                if tag_text not in found:
                    found.append(tag_text)

        return found

    def parse(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        dictionary_data = []
        current_article = None
        current_node = None

        for p_tag in soup.find_all('p'):
            full_text, italic_flags, bold_flags = self._extract_text_and_styles(p_tag)
            if not full_text.strip():
                continue

            bold_phrases = self._get_bold_phrases(full_text, bold_flags)

            chunks = []
            if not bold_phrases:
                chunks.append((full_text, 0, None))
            else:
                for i, (phrase, b_start) in enumerate(bold_phrases):
                    text_start = b_start
                    text_end = bold_phrases[i+1][1] if i + 1 < len(bold_phrases) else len(full_text)
                    chunks.append((full_text[text_start:text_end], text_start, phrase))

            for chunk_text, offset, bold_marker in chunks:
                if bold_marker:
                    clean_marker = bold_marker.replace('́', '').strip('.,')

                    # 1. Заголовочное слово
                    if clean_marker.isupper() and len(clean_marker) > 1 and not self.re_roman.match(clean_marker):
                        if not current_article or current_article["sections"] or current_article["derivatives"]:
                            current_article = {
                                "headwords": [bold_marker],
                                "main_pomety": [],
                                "sections": [],
                                "derivatives": []
                            }
                            dictionary_data.append(current_article)
                            current_node = current_article["main_pomety"]
                        else:
                            current_article["headwords"].append(bold_marker)

                    # 2. Сохраняем логику разделов (1., 2., I., II.)
                    elif self.re_roman.match(bold_marker) or self.re_arabic.match(bold_marker):
                        if current_article:
                            section = {"id": bold_marker, "pomety": []}
                            current_article["sections"].append(section)
                            current_node = section["pomety"]

                    # 3. Производные 
                    elif clean_marker and clean_marker[0].isupper() and not self.re_roman.match(bold_marker) and not self.re_arabic.match(bold_marker):
                        if current_article:
                            derivative = {"word": bold_marker, "pomety": []}
                            current_article["derivatives"].append(derivative)
                            current_node = derivative["pomety"]

                # Собственно извлечение помет
                if current_node is not None:
                    pomety = self._extract_pomety(chunk_text, offset, italic_flags)
                    for p in pomety:
                        if p not in current_node:
                            current_node.append(p)

        return dictionary_data


# Запуск, вывод части результатов в консоль и полностью в виде файла 
if __name__ == "__main__":
    import os
    import json
    import glob
    
    def process_files(input_dir, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        html_files = glob.glob(os.path.join(input_dir, "**", "*.html"), recursive=True)
        print(f"Найдено {len(html_files)} HTML файлов для обработки.")
        
        parser = UniversalCorpusParser()
        processed_count = 0
        
        for filepath in html_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html = f.read()
                
                result = parser.parse(html)
                if result:
                    filename = os.path.basename(filepath)
                    json_filename = os.path.splitext(filename)[0] + '.json'
                    output_filepath = os.path.join(output_dir, json_filename)
                    
                    with open(output_filepath, 'w', encoding='utf-8-sig') as f:
                        json.dump(result, f, ensure_ascii=False, indent=4)
                    processed_count += 1
            except Exception as e:
                pass
                
        print(f"Успешно обработано {processed_count} файлов.")

    INPUT_DIR = r'F:\dictionary_parsing\data\samples_html\Output_1-23_html'
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
    
    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {OUTPUT_DIR}")
    
    process_files(INPUT_DIR, OUTPUT_DIR)