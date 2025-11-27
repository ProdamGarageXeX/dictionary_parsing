import json

from bs4 import BeautifulSoup
#текст статьи лежит в body в div

headline_word = ""
rest_of_the_article = ""

with open("БЕЗЦВЕТНЫЙ.html", 'r', encoding='utf-8') as f:
    html_content = f.read()
soup = BeautifulSoup(html_content, 'html.parser')
for tag in soup.find_all():
    if tag.name == 'body':
        s = str(tag)
        break;
soup2 = BeautifulSoup(s, 'html.parser')
for tag2 in soup2.find_all():
    if tag2.name == 'div':
        s2 = str(tag2) #один большой див
        break;
spans = []
soup3 = BeautifulSoup(s2, 'html.parser')
for tag3 in soup3.find_all():
    if tag3.name == 'p': #пэ, в которых лежат спаны с текстом
        s3 = str(tag3)
        soup4 = BeautifulSoup(s3, 'html.parser')
        for tag4 in soup4.find_all():
            if tag4.name == 'span': #все спаны с текстом
                spans.append(tag4)
print(spans)

check = 0
for span in spans:
    style_attr = span['style']
    if check == 0:
        headline_word = headline_word + str(span)
    if check == 1:
        rest_of_the_article = rest_of_the_article + str(span)
    if 'font-family:\'Times New Roman\'; font-weight:bold' in style_attr: #заголовочное слово -- первый жирный спан
        check = 1


dic = {
    "headline": headline_word,
    "rest": rest_of_the_article
}
json = json.dumps(dic, indent=4, ensure_ascii=False)
print(json)
