import os
from xml.etree import ElementTree as ET

def extract_sup_articles(input_xml, output_dir):
    tree = ET.parse(input_xml)
    root = tree.getroot()
    ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

    # 1. Найти все абзацы
    all_elements = list(root.iter())
    paragraphs = [e for e in all_elements if e.tag.endswith('p')]

    # 2. Разделить на блоки по пустым <p></p>
    blocks = []
    current_block = []

    for elem in paragraphs:
        if is_empty_paragraph(elem):
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(elem)

    if current_block:
        blocks.append(current_block)

    # 3. Обработать каждый блок
    os.makedirs(output_dir, exist_ok=True)

    for i, block in enumerate(blocks, 1):
        headword = extract_headword_with_sup(block)
        if headword:
            save_tei_file(headword, block, output_dir, i)

def is_empty_paragraph(elem):
    """Проверяет, пустой ли параграф (<p></p>)"""
    text = ''.join(elem.itertext())
    return text.strip() == ''

def extract_headword_with_sup(block):
    """Найти заголовок со superscript в блоке"""
    for elem in block:
        bold_with_sup = find_bold_with_superscript(elem)
        if bold_with_sup is not None:
            return get_text_with_sup(bold_with_sup)
    return None

def find_bold_with_superscript(elem):
    """Найти <hi rendition="simple:bold"> с вложенным <sup>"""
    for child in elem.iter():
        if child.tag.endswith('hi'):
            rendition = child.get('rendition', '')
            if 'bold' in rendition:
                for descendant in child.iter():
                    if descendant.tag.endswith('hi'):
                        if 'superscript' in descendant.get('rendition', ''):
                            return child
    return None

def get_text_with_sup(elem):
    """Получить текст с сохранением superscript"""
    result = ''
    for node in elem.iter():
        if node.tag.endswith('hi'):
            rendition = node.get('rendition', '')
            if 'superscript' in rendition:
                result += f'<sup>{node.text}</sup>'
            else:
                result += node.text or ''
        elif node.tag.endswith('t'):
            result += node.text or ''
    return result

def sanitize_filename(name):
    """Нормализовать имя для использования в качестве имени файла"""
    import re
    name = name.replace('<sup>', '').replace('</sup>', '')
    name = re.sub(r'[^\w\s\-]', '', name)
    name = name.strip()
    return name

def save_tei_file(headword, block, output_dir, index):
    """Сохранить статью как TEI файл"""
    safe_name = sanitize_filename(headword)
    output_path = os.path.join(output_dir, f"{safe_name}.xml")
    
    root = ET.Element('TEI', xmlns='http://www.tei-c.org/ns/1.0')
    tei_header = ET.SubElement(root, 'teiHeader')
    file_desc = ET.SubElement(tei_header, 'fileDesc')
    title_stmt = ET.SubElement(file_desc, 'titleStmt')
    ET.SubElement(title_stmt, 'title').text = headword
    profile_desc = ET.SubElement(tei_header, 'profileDesc')
    
    text = ET.SubElement(root, 'text')
    body = ET.SubElement(text, 'body')
    
    for elem in block:
        p = ET.SubElement(body, 'p')
        copy_element(elem, p)
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    tree.write(output_path, encoding='utf-8', xml_declaration=True)

def copy_element(src, dst):
    """Копировать содержимое элемента src в dst"""
    if src.text:
        dst.text = src.text
    for child in src:
        new_child = ET.SubElement(dst, child.tag.split('}')[-1])
        new_child.set('rendition', child.get('rendition', ''))
        copy_element(child, new_child)
        if child.tail:
            new_child.tail = child.tail

if __name__ == "__main__":
    extract_sup_articles('output.xml', 'temp')
