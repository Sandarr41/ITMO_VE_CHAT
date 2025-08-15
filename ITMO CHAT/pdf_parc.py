import pdfplumber
import re

def extract_courses_from_pdf(file_stream):
    """
    Принимает file_stream с pdf, возвращает множество дисциплин.
    """
    with pdfplumber.open(file_stream) as pdf:
        text = ''
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'

    # Ищем строки с названием дисциплин (где есть буквы и нет большого количества цифр)
    discipline_lines = []
    for line in text.splitlines():
        line = line.strip()
        # предусматриваем кириллицу и латиницу
        if len(line) < 3:
            continue
        if (re.search(r'[а-яА-Яa-zA-Z]', line) and
            not (re.fullmatch(r'[\d\s]+', line) or sum(c.isdigit() for c in line) > len(line)/2)):
            discipline_lines.append(line)
    return set(discipline_lines)
