# Извлечение омонимов из словарных статей

## Конвертация docx в tei xml

При конвертации DOCX в TEI XML с помощью pandoc пустые строки (пустые абзацы) между статьями теряются:

```bash
pandoc file.docx -f docx -t tei -o output.xml
```

Встроенное расширение +empty_paragraphs для pandoc (начиная с версии 3.0) позволяет сохранить пустые строки - основной разделитель словарных статей.

Команда:

```bash
pandoc file.docx -f docx+empty_paragraphs -t tei -s -o output.xml
```

Pandoc не поддерживает множественный вывод, для разделения output.xml на несколько файлов:

Решение: Python + python-docx

```python
from docx import Document
import subprocess
import os

def split_docx_by_empty_paras(input_docx, output_dir):
    doc = Document(input_docx)
    articles = []
    current = []

    for para in doc.paragraphs:
        if para.text.strip() == '' and current:
            articles.append(current)
            current = []
        else:
            current.append(para)
    if current:
        articles.append(current)

    os.makedirs(output_dir, exist_ok=True)
    for i, article in enumerate(articles, 1):
        temp_docx = f"{output_dir}/temp_{i}.docx"
        new_doc = Document()
        for para in article:
            new_doc.add_paragraph(para.text, para.style)
        new_doc.save(temp_docx)
        subprocess.run(['pandoc', '-s', '-t', 'tei', '-o',
                       f"{output_dir}/article_{i}.xml", temp_docx])
        os.remove(temp_docx)
```

## Скрипт извлечения статей с superscript из TEI XML

### Назначение

Скрипт `extract_sup_articles.py` — выбирает из TEI XML статьи со словами + цифры в `<sup>` и сохраняет каждую в отдельный TEI файл.

### Входные данные

- TEI XML с пустыми `<p></p>` между статьями
- Статьи типа: `А¹`, `А²`, `А³` — слово с надстрочной цифрой

### Алгоритм

```
TEI XML (с пустыми <p></p> между статьями)
         ↓
1. Разделить по пустым <p></p> на блоки
         ↓
2. В каждом блоке найти заголовок с <sup>
         ↓
3. Извлечь статьи с superscript
         ↓
4. Сохранить каждую как отдельный TEI файл
```

### Структура выходных файлов

```
output/
├── А1.xml  (полный TEI документ)
├── А2.xml
├── А3.xml
└── А4.xml
```
