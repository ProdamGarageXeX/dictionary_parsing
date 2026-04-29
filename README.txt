ПАРСЕР СЛОВАРЯ РУССКОГО ЯЗЫКА XVIII ВЕКА
========================================

Цель проекта: преобразование HTML файлов, содержащих словарные статьи в
структурированный JSON с выделением лексикографических зон.

Исходные данные: выпуски словаря русского языка XVIII века в формате HTML.
Каждый выпуск содержит несколько тысяч словарных статей.

------------------------------------------------------------------------------------
DICTIONARY_PIPELINE.PY
------------------------------------------------------------------------------------
Скрипт представляет собой комплексный пайплайн для автоматического парсинга HTML-файлов словарных статей. Он извлекает информацию из HTML-файлов и сохраняет её в формате JSON. 

Структура скрипта
-----------------
dictionary_pipeline.py
├── Конфигурационные константы
├── HTML-парсер (RichHTMLParser) # разбор форматирования
├── Функции обработки текста 
├── Извлечение информации из заголовков
├── Разбор определений и значений
├── Выделение грамматических помет
├── Обработка смысловых кластеров
├── Внешние модули (цитаты, коллокации, этимология)
└── Основной пайплайн (build_article_json) # сборка JSON

Конфигурационные константы
--------------------------
PROJECT_ROOT — корневая директория проекта
DEFAULT_INPUT_DIR — папка с входными HTML-файлами 
DEFAULT_OUTPUT_DIR — папка для выходных JSON-файлов

Внешние модули
--------------
separate_citations.py — извлечение цитат и ссылок на источники
CollocationPhaseo.py — извлечение цитат и ссылок на источники
find_etymologies_in_pipeline.py — извлечение цитат и ссылок на источники
dynamic_tags.py — извлечение цитат и ссылок на источники

Зависимости
-----------
Python 3.8+
BeautifulSoup4
Библиотеки: html, json, re, pathlib, argparse, functools, glob, typing, tkinter, threading

Запуск
------
Через gui.py (Подробная документация: (scripts/ulia_pav/README.md)
При запуске открывается окно с предустановленными путями из dictionary_pipeline.DEFAULT_INPUT_DIR и DEFAULT_OUTPUT_DIR.



---------------------
СТРУКТУРА РЕПОЗИТОРИЯ
---------------------
/MVP
  dictionary_pipeline.py — пайплайн для автоматического парсинга HTML 
  gui.py — графический интерфейс для запуска парсинга 

/data
  /samples_html — примеры HTML-статей
  /sources_docx_tags — выпуски в формате docx
  /sources_html_tags — выпуски в формате html

/docs
  parsing_zones.json — целевая структура зон
  slovar_russkogo_yazyka_18_veka_pravila_polzovaniya_ukazatel_istochnikov.pdf
  Пометы_замена_на_теги_v3.docx — графические знаки и соответствующие им теги
  Список_условных_сокращений.docx — список сокращений
  Указатель_источников_Сл_XVIII_16_04_2025.docx

/scripts
  /As_hen_ok
    CollocationPhaseo.py      — выделение устойчивых сочетаний и прилежащих цитат
    html2json_batch.py        — парсер HTML в JSON с поддержкой пакетной обработки словарных статей
  /Htotyktoya
    separate_citations.py     — выделение грамматических и стилистических помет при цитатах
  /ProdamGarageXeX 
    dynamic_tags.py           — выделение динамических помет
    split.articles.py         — разделение словарных статей
    tei2html.py               — конвертация TEI в HTML
  /SoykaGolubaya          
    titleandtags.py           — разделение заголовочных слов и их помет
  /almighty_architect
    separate_citations.py     — отделение цитат от источников
  /butterfly_catastrophe
    extract_definitions.py    — разделение кластеров значений
    html2json_demo.py         — базовый парсер HTML в JSON
  /melitinie
    gram_tags.py              — выделение грамматических помет
  /pedrobirq
    find_etymologies.py       — выделение этимологических сведений 
    find_etymologies_in_pipeline.py
  /ulia_pav
    /up-homonyms           
      extract_sup_articles.py — различение омонимов (надписные индексы)
  /vewsqu
    gram_tags.py              — выделение грамматических помет

README.txt                    — описание пайплайна
