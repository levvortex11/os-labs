"""Generate DOCX from the supplied template and a PDF with the same content."""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import os

from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted,
    Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'report'
OUT.mkdir(exist_ok=True)
NAME = '214_Вихарев_Лаб1'
DATE = '24.09.2026'
results = json.loads((ROOT / 'tests/results.json').read_text(encoding='utf-8'))
assert len(results['tests']) == 20 and all(t['passed'] for t in results['tests'])

# All body content is shared between the editable document and PDF.
blocks = []
def heading(text): blocks.append(('heading', text))
def para(text): blocks.append(('paragraph', text))
def code(text): blocks.append(('code', text))
def table(rows): blocks.append(('table', rows))
def page(): blocks.append(('page', None))

heading('Постановка задачи')
para('Лабораторная работа №1. Управление процессами и межпроцессное взаимодействие. Вариант 3.')
para('Студент: Вихарев Лев Александрович. Группа: М8О-214БВ-25. '
     'Порядковый номер в списке — 3, число вариантов — 22. '
     'Вариант вычислен по формуле ((3 − 1) % 22) + 1 = 3. '
     'Численность группы 24 человека на этот результат не влияет.')
para('Цель работы: приобрести практические навыки создания и завершения процессов, '
     'перенаправления стандартных потоков и обмена данными через неименованные каналы.')
para('Родительский процесс создаёт дочерний процесс. Первой строкой пользователь '
     'вводит имя файла, передаваемое дочернему процессу при запуске. Родитель и ребёнок '
     'представлены разными программами. Команды передаются через pipe1, связанный со '
     'стандартным вводом ребёнка; обратная связь осуществляется через pipe2. '
     'Дочерний процесс записывает результаты в созданный им файл.')
para('Каждая команда — строка целых чисел типа int. Ребёнок последовательно делит '
     'первое число на все последующие и записывает результат в файл. Количество чисел '
     'может быть произвольным. Проверка деления на ноль выполняется дочерним процессом; '
     'при нулевом делителе дочерний и родительский процессы завершаются. '
     'Необходимо обрабатывать системные ошибки.')
para('Реализация выполнена на C11 для Linux/POSIX. Ввод-вывод и взаимодействие с ОС '
     'выполняются через POSIX-интерфейсы. Заголовки stdio.h, threads.h и stdatomic.h '
     'не используются. Разбор и форматирование чисел реализованы вручную.')

heading('Общий метод и алгоритм решения')
para('Родитель читает имя файла, создаёт два канала и вызывает fork. В дочерней ветви '
     'закрываются ненужные концы каналов, stdin и stdout перенаправляются через dup2. '
     'Вызов execv запускает отдельную программу child, получающую имя файла в argv[1]. '
     'Оба процесса сохраняют stderr для диагностических сообщений.')
code('Пользователь -> parent -> pipe1 -> stdin child\n'
     '                                  child -> файл\n'
     '               parent <- pipe2 <- stdout child\n'
     '               parent --waitpid--> завершение child')
para('Ребёнок открывает файл с O_WRONLY | O_CREAT | O_TRUNC и правами 0600. '
     'Существующий файл перезаписывается. Данные читаются блоками по 4096 байт, '
     'но состояние разбора сохраняется между блоками: длина строки и количество '
     'чисел не ограничиваются размером буфера. Дополнительная память не зависит '
     'от длины команды. Время обработки линейно по числу входных байтов.')
para('Парсер хранит знак, модуль текущего числа и промежуточный результат. '
     'Перед добавлением очередной цифры проверяется диапазон int. Первое число '
     'становится результатом; каждое следующее используется как делитель. '
     'До операции проверяются нулевой делитель и случай INT_MIN / −1. '
     'Деление выполняется слева направо с усечением к нулю. '
     'После окончания строки результат преобразуется в десятичную запись '
     'и записывается в файл с символом перевода строки.')
para('При ошибке ребёнок выводит диагностику в stderr, закрывает файл, отправляет '
     'байт E в pipe2 и завершается с кодом 1. При успехе закрытие pipe2 даёт родителю '
     'EOF. Родитель одновременно наблюдает stdin и pipe2 через poll; '
     'обратный канал проверяется первым. Поэтому для завершения после деления '
     'на ноль не требуется следующий ввод пользователя или Ctrl+D. '
     'После закрытия каналов родитель вызывает waitpid и проверяет статус ребёнка.')
para('При EOF пользовательского ввода родитель закрывает пишущий конец pipe1, '
     'после чего ребёнок завершает последнюю команду и закрывает файл. '
     'Результаты предшествующих успешных команд сохраняются при последующей ошибке. '
     'Результат ошибочной команды не записывается.')
para('Дополнительные правила: строка из одного числа возвращает это число; '
     'пустой поток команд допустим, а пустая команда считается ошибкой. '
     'Поддерживаются знак числа, пробельные разделители, CRLF и последняя строка '
     'без перевода строки. Имя файла ограничено 4095 байтами. '
     'Пример: −20 / 3 даёт −6; 100 / 2 / 5 даёт 10.')

para('Использованные системные вызовы и POSIX-интерфейсы:')
table([
    ['Интерфейс', 'Назначение в программе'],
    ['fork', 'Создание дочернего процесса.'],
    ['execv', 'Замена образа дочернего процесса программой child.'],
    ['pipe', 'Создание канала команд и обратного канала статуса.'],
    ['dup2', 'Подключение каналов к stdin и stdout ребёнка.'],
    ['open', 'Создание или очистка выходного файла ребёнком.'],
    ['read / write', 'Чтение имени и команд, передача по каналам, запись результата.'],
    ['poll', 'Ожидание готовности stdin или обратного канала.'],
    ['sigaction', 'Игнорирование SIGPIPE для обработки ошибки записи в закрытый канал.'],
    ['close', 'Закрытие файлов и ненужных концов каналов.'],
    ['waitpid', 'Ожидание ребёнка и получение статуса без процесса-зомби.'],
    ['_exit', 'Немедленное завершение дочерней ветви при ошибке до exec.'],
])
para('Сигнальная маска инициализируется вспомогательной функцией sigemptyset. '
     'Каждый основной системный вызов проверяется. Операции read, write, poll '
     'и waitpid повторяются после EINTR. Короткие записи дописываются циклом. '
     'Повтор close после ошибки не выполняется, поскольку в Linux дескриптор '
     'уже мог освободиться. Системная диагностика содержит имя операции и errno. '
     'Ошибка самого вывода диагностики не вызывает рекурсивного сообщения.')

page()
heading('Код программы')
for filename in ['common.h', 'parent.c', 'child.c']:
    heading(filename)
    code((ROOT / filename).read_text(encoding='utf-8').rstrip())
    if filename != 'child.c': page()

page()
heading('Протокол работы программы')
para('Фактическая среда проверки: ' + results['environment'] + '. '
     'Дата проверки: ' + DATE + '. Программа собрана и запущена в POSIX-среде '
     'MSYS2; непосредственная проверка под ядром Linux не выполнялась. '
     'Для повторения проверки на Linux предусмотрены Makefile и интеграционные тесты.')
code('gcc -std=c11 -O2 -Wall -Wextra -Wpedantic \\\n'
     '    -Wconversion -Wshadow -Werror parent.c -o parent\n'
     'gcc -std=c11 -O2 -Wall -Wextra -Wpedantic \\\n'
     '    -Wconversion -Wshadow -Werror child.c -o child\n'
     'python3 tests/test_lab.py\n'
     '20 tests passed')
para('Сборка завершилась без предупреждений и ошибок. Тесты запускают отдельные '
     'процессы parent и child, проверяют выходной файл, код завершения и диагностические '
     'сообщения. Ниже приведены входы и фактически подтверждённые результаты.')
table([
    ['Проверка', 'Вход / сценарий', 'Результат'],
    ['Последовательное деление', '100 2 5; −20 3; 7; 0 5', '10; −6; 7; 0; код 0'],
    ['Границы int', '−2147483648 1; +2147483647 −1; −7 −2', '−2147483648; −2147483647; 3'],
    ['Пробельные разделители', 'Табуляция, CRLF, VT, FF', '9; 5; код 0'],
    ['Последняя строка без LF', '40 2 4 и EOF', '5; код 0'],
    ['Пустой поток команд', 'EOF после имени файла', 'Пустой файл; код 0'],
    ['Пробелы в имени файла', 'result file.txt; 12 2', '6; код 0'],
    ['Нулевой делитель', '20 2; 9 0; 81 3', 'Только 10; Division by zero; код 1'],
    ['Отрицательный ноль', '1 −0', 'Division by zero; код 1'],
    ['Переполнение деления', '−2147483648 −1', 'Integer division overflow; код 1'],
    ['Переполнение ввода (+)', '2147483648', 'Integer is out of range; код 1'],
    ['Переполнение ввода (−)', '−2147483649', 'Integer is out of range; код 1'],
    ['Посторонний символ', '12 x', 'Invalid integer; код 1'],
    ['Знак без цифр', '1 −', 'A sign must be followed by digits; код 1'],
    ['Пустая строка', 'LF', 'Empty command; код 1'],
    ['Нулевой байт', '1, байт NUL, 2', 'Invalid integer; код 1'],
    ['Ошибка открытия', 'Несуществующий каталог', 'open output file: errno; код 1'],
    ['Ошибка exec', 'Отсутствующий child', 'execv: errno; код 1'],
    ['Длинная строка', '42 и 150000 делителей 1', '42; без зависания; код 0'],
    ['Случайные команды', '1000 строк, seed 214', 'Все результаты совпали с эталоном'],
    ['Открытый stdin', '100 2; 9 0; stdin не закрыт', '50; оба процесса завершились с ошибкой'],
])
para('Тест открытого stdin ждёт завершения родителя не более 10 секунд, '
     'не закрывая его входной поток. Это проверяет реакцию на pipe2, '
     'а не завершение вследствие EOF. Длинная строка содержит более 300 Кбайт '
     'и проверяет работу за пределами буфера и ёмкости канала.')
para('Эквивалентный обычный запуск в Linux (Ctrl+D завершает ввод):')
code('$ ./parent\nresult.txt\n100 2 5\n-20 3\n7\n[Ctrl+D]\n'
     '$ cat result.txt\n10\n-6\n7')
para('Пример аварийного сценария, также проверенного тестом:')
code('Имя файла: result.txt\nКоманды:\n20 2\n9 0\n81 3\n'
     'stderr: Division by zero.\nКод завершения: 1\n'
     'Содержимое result.txt:\n10')
para('Код тестов и машиночитаемый протокол находятся в tests/test_lab.py и '
     'tests/results.json. Для Linux: make && make test. В MSYS2 используется '
     '/usr/bin/gcc, а не MinGW/UCRT GCC.')

heading('Вывод')
para('В работе реализовано взаимодействие двух отдельных программ через '
     'неименованные каналы и освоены создание, запуск и ожидание дочернего процесса. '
     'Потоковый разбор позволяет обрабатывать произвольное количество целых чисел '
     'без накопления всей строки в памяти. Основное внимание уделено корректному '
     'закрытию дескрипторов, завершению обоих процессов при ошибке и защите '
     'целочисленных операций от неопределённого поведения. '
     'Все 20 интеграционных проверок прошли в MSYS2; повторная проверка '
     'непосредственно в Linux остаётся отдельным шагом при переносе программы.')

heading('Материалы')
para('1. Предоставленное задание «Лабораторная работа №1», вариант 3 (materials/lab-1.pdf).')
para('2. Предоставленный шаблон отчёта (materials/report-template.docx).')
para('3. Пример преподавателя: '
     'https://gist.github.com/vladeemerr/dcf8ef920361e3f5a7aa6eaaeea77a4e. '
     'Пример использован как справочный материал по организации процессов; '
     'ограничения на библиотеки взяты из сообщения преподавателя.')

# Preserve the original title page's paragraphs and formatting.
doc = Document(ROOT / 'materials/report-template.docx')
body = doc.element.body
cut = False
for item in list(body):
    if item.tag.endswith('}sectPr'):
        continue
    text = ''.join(item.itertext())
    if 'Постановка задачи' in text:
        cut = True
    if cut:
        body.remove(item)
replacements = {
    'Лабораторная работа №X по курсу': 'Лабораторная работа №1 по курсу',
    'Группа: М8О-2ХХБВ-2Y': 'Группа: М8О-214БВ-25',
    'Студент: Фамилия И.О.': 'Студент: Вихарев Лев Александрович',
    'Дата: XX.XX.26': 'Дата: ' + DATE,
}
for p in doc.paragraphs:
    if p.text in replacements:
        p.text = replacements[p.text]
    for run in p.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
doc.paragraphs[-1].paragraph_format.page_break_after = True
normal = next(style for style in doc.styles if style.style_id == 'Normal')
normal.font.name = 'Times New Roman'
normal.font.size = Pt(12)
normal.paragraph_format.space_after = Pt(6)
for style_name in ['Heading 1', 'Heading 2']:
    style = doc.styles[style_name]
    style.font.name = 'Times New Roman'
    style.font.size = Pt(14)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.font.bold = True
for kind, content in blocks:
    if kind == 'heading':
        doc.add_heading(content, level=1)
    elif kind == 'paragraph':
        doc.add_paragraph(content)
    elif kind == 'code':
        for line in content.splitlines():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1
            run = p.add_run(line)
            run.font.name = 'Courier New'
            run.font.size = Pt(8)
    elif kind == 'page':
        doc.add_page_break()
    elif kind == 'table':
        t = doc.add_table(rows=0, cols=len(content[0]))
        borders = OxmlElement('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            border = OxmlElement('w:' + side)
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '4')
            border.set(qn('w:color'), '888888')
            borders.append(border)
        t._tbl.tblPr.append(borders)
        for index, row in enumerate(content):
            cells = t.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = value
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(10)
                        run.bold = index == 0
doc.core_properties.title = 'Лабораторная работа №1. Вариант 3'
doc.core_properties.author = 'Вихарев Лев Александрович'
doc.save(OUT / (NAME + '.docx'))

# PDF embeds Cyrillic fonts and includes the same complete source listings.
font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
pdfmetrics.registerFont(TTFont('ReportTimes', str(font_dir / 'times.ttf')))
pdfmetrics.registerFont(TTFont('ReportTimesBold', str(font_dir / 'timesbd.ttf')))
pdfmetrics.registerFont(TTFont('ReportMono', str(font_dir / 'cour.ttf')))
styles = {
    'paragraph': ParagraphStyle('Body', fontName='ReportTimes', fontSize=12,
                                leading=16, alignment=TA_JUSTIFY, spaceAfter=8),
    'heading': ParagraphStyle('Heading', fontName='ReportTimesBold', fontSize=14,
                              leading=18, spaceBefore=10, spaceAfter=9, keepWithNext=True),
    'code': ParagraphStyle('Code', fontName='ReportMono', fontSize=8,
                           leading=9.5, spaceAfter=8),
    'cell': ParagraphStyle('Cell', fontName='ReportTimes', fontSize=10, leading=12),
    'center': ParagraphStyle('Center', fontName='ReportTimes', fontSize=13,
                             leading=18, alignment=TA_CENTER),
    'title': ParagraphStyle('Title', fontName='ReportTimesBold', fontSize=17,
                            leading=24, alignment=TA_CENTER),
    'right': ParagraphStyle('Right', fontName='ReportTimes', fontSize=13,
                            leading=21, alignment=TA_RIGHT),
}
story = []
for line in ['Московский Авиационный Институт',
             '(Национальный Исследовательский Университет)',
             'Институт №8 «Компьютерные науки и прикладная математика»',
             'Кафедра №806 «Вычислительная математика и программирование»']:
    story.append(Paragraph(escape(line), styles['center']))
story.append(Spacer(1, 80))
story.append(Paragraph('Лабораторная работа №1 по курсу<br/>«Операционные системы»', styles['title']))
story.append(Spacer(1, 140))
for line in ['Группа: М8О-214БВ-25', 'Студент: Вихарев Лев Александрович',
             'Преподаватель: Бахарев В.Д.', 'Оценка: ____________________', 'Дата: ' + DATE]:
    story.append(Paragraph(escape(line), styles['right']))
story.append(Spacer(1, 115))
story.append(Paragraph('Москва, 2026', styles['center']))
story.append(PageBreak())
for kind, content in blocks:
    if kind in ('heading', 'paragraph'):
        story.append(Paragraph(escape(content), styles[kind]))
    elif kind == 'code':
        story.append(Preformatted(content, styles['code']))
    elif kind == 'page':
        story.append(PageBreak())
    elif kind == 'table':
        rows = [[Paragraph(escape(value), styles['cell']) for value in row] for row in content]
        widths = [115, 380] if len(rows[0]) == 2 else [123, 185, 187]
        t = Table(rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

def page_number(canvas, document):
    if document.page > 1:
        canvas.saveState()
        canvas.setFont('ReportTimes', 10)
        canvas.drawCentredString(A4[0] / 2, 22, str(document.page))
        canvas.restoreState()

pdf = SimpleDocTemplate(str(OUT / (NAME + '.pdf')), pagesize=A4,
                        rightMargin=50, leftMargin=50, topMargin=32, bottomMargin=38,
                        title='Лабораторная работа №1. Вариант 3',
                        author='Вихарев Лев Александрович')
pdf.build(story, onFirstPage=page_number, onLaterPages=page_number)
print(OUT / (NAME + '.docx'))
print(OUT / (NAME + '.pdf'))
