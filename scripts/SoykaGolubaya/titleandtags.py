import os
import glob
import re
import json
from bs4 import BeautifulSoup, NavigableString

def parse_html(filepath):
    """
    Парсит HTML-файл и извлекает заголовочные слова и их пометы.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла {filepath}: {e}")
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    p = soup.find('p')
    if not p:
        return {"headwords": [], "notes": []}
        
    # Разворачиваем все span и a теги, чтобы текст был плоским
    for tag in p.find_all(['span', 'a']):
        tag.unwrap()
        
    headwords = []
    notes = []
    in_parens = False
    current_note_parts = []
    
    for child in p.contents:
        if isinstance(child, NavigableString):
            text = str(child)
            for char in text:
                if char == '(':
                    in_parens = True
                    current_note_parts.append(char)
                elif char == ')':
                    current_note_parts.append(char)
                    in_parens = False
                    notes.append("".join(current_note_parts).strip())
                    current_note_parts = []
                else:
                    if in_parens:
                        current_note_parts.append(char)
                    else:
                        pass # Игнорируем текст вне скобок (обычно пунктуация, "и", "или")
        elif child.name == 'b':
            if in_parens:
                current_note_parts.append(child.get_text())
            else:
                hw = child.get_text(strip=True).strip(',.')
                # Прерываем блок заголовочных слов, если встретили номер (например, 1., I)
                if re.match(r'^([IVXLCDM]+|\d+)\.?$', hw):
                    break
                
                # Отделяем цифры омонимов в конце (например, КОНСУЛЬСКИЙ2 -> КОНСУЛЬСКИЙ)
                hw_match = re.match(r'^([А-Яа-яЁёA-Za-z\-]+)(\d*)$', hw)
                if hw_match:
                    headwords.append(hw_match.group(1))
                elif re.search(r'[А-Яа-яЁё]', hw): # Добавляем только если есть буквы
                    headwords.append(hw)
        elif child.name == 'i':
            if in_parens:
                current_note_parts.append(child.get_text())
            else:
                # Первый курсив вне скобок означает начало грамматических помет или определения
                break
                
    # Очищаем пометы от лишних пробелов/переносов строк
    cleaned_notes = [re.sub(r'\s+', ' ', n).strip() for n in notes]
    
    return {
        "headwords": headwords,
        "notes": cleaned_notes
    }

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
        result = parse_html(filepath)
        if result:
            filename = os.path.basename(filepath)
            json_filename = os.path.splitext(filename)[0] + '.json'
            output_filepath = os.path.join(output_dir, json_filename)
            
            with open(output_filepath, 'w', encoding='utf-8-sig') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            processed_count += 1
            
    print(f"Успешно обработано {processed_count} файлов.")

if __name__ == "__main__":
    # Папка с исходными данными
    INPUT_DIR = r'C:\dictionary_parsing\data\samples_html\Output_1-23_html'
    
    # Папка для сохранения результатов рядом со скриптом
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
    
    print(f"Начинаем обработку...")
    print(f"Входная папка: {INPUT_DIR}")
    print(f"Выходная папка: {OUTPUT_DIR}")
    
    process_files(INPUT_DIR, OUTPUT_DIR)