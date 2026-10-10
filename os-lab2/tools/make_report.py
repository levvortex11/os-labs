from pathlib import Path
import csv
from docx import Document
from docx.shared import Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer

root = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader((root / 'report/measurements.csv').open(encoding='utf-8')))
blocks = []
def heading(s): blocks.append(('h', s))
def para(s): blocks.append(('p', s))
def table(rows): blocks.append(('t', rows))

heading('Лабораторная работа №2. Управление потоками')
para('Вихарев Лев Александрович, М8О-214БВ-25. Вариант 3.')
heading('Цель и задание')
para('Приобрести навыки управления потоками и их синхронизации. Отсортировать массив целых чисел параллельной сортировкой слиянием на языке C, ограничив количество потоков ключом программы. Исследовать ускорение и эффективность при изменении входных данных и числа потоков.')
heading('Алгоритм и синхронизация')
para('Реализована итеративная сортировка слиянием. На первом проходе сливаются пары отрезков длины 1, затем длина удваивается до тех пор, пока не будет отсортирован весь массив. Проходы попеременно читают исходный и вспомогательный массивы. На каждом проходе независимые пары отрезков распределяются между потоками циклически. Каждый поток записывает только свой участок выходного массива.')
para('Главный поток тоже выполняет работу. Создаётся не больше P−1 дополнительных потоков, поэтому общее число потоков процесса не превышает P, заданного ключом --threads. Если задач меньше, потоков используется меньше. pthread_join завершает каждый проход до начала следующего и тем самым обеспечивает синхронизацию и видимость записей. При ошибке создания все уже созданные потоки дожидаются завершения, программа сообщает об ошибке.')
para('Время алгоритма O(n log n), дополнительная память O(n + P). На последних проходах количество независимых слияний уменьшается до одного; это ограничивает ускорение. На каждом проходе потоки создаются заново, что добавляет накладные расходы.')
heading('Запуск и проверка')
para('Сборка в Linux: make. Пример: printf "5\\n3 1 2 1 -4\\n" | ./merge --threads 4. Программа читает размер и элементы из стандартного ввода; результат печатается в stdout, время — в stderr. Для генерации данных: ./merge --size 1000000 --pattern random --seed 42 --threads 4 --quiet. Ключ --quiet отключает вывод массива.')
para('Для демонстрации потоков запустить ./merge --threads 4 --size 10000 --hold 15 --quiet в фоне, затем ps -T -p PID, где PID — номер процесса, выведенный оболочкой. --hold задерживает первый проход на указанное число секунд и включается во время измерения, поэтому для исследования не используется. Проверка: make test. Выполнено 52 проверки, включая пустой массив, дубликаты, границы int, нечетные длины, случайные данные и неверные аргументы.')
heading('Исследование')
para('Среда: Ubuntu 24.04 в WSL2, ядро Linux 6.18.54.1, Intel Core i5-13420H, системе доступно 12 логических процессоров. Сборка GCC с оптимизацией -O2. Для каждой комбинации выполнены три запуска; приведена медиана времени сортировки по CLOCK_MONOTONIC. Генерация, вывод и проверка результата в это время не входят. Ускорение S = T1/Tp, эффективность E = S/p. В качестве T1 использована медиана того же алгоритма при одном потоке. Полные результаты и отдельные замеры сохранены в measurements.csv.')
for n in ('10000', '1000000', '5000000'):
    heading('Размер массива: ' + n)
    data = [['Данные', 'Потоки', 'Время, с', 'S', 'E']]
    names = {'random': 'случайные', 'sorted': 'по возрастанию', 'reverse': 'по убыванию'}
    for r in rows:
        if r['size'] == n:
            data.append([names[r['pattern']], r['threads'], r['seconds_median'], r['speedup'], r['efficiency']])
    table(data)
heading('Анализ и вывод')
para('На 10 000 случайных чисел восемь потоков работают медленнее одного: 0,002799 с против 0,000560 с. Работа слишком мала относительно стоимости создания потоков и ожидания. На 1 000 000 случайных чисел ускорение при восьми потоках составляет 3,032, эффективность 0,379. На 5 000 000 случайных чисел — 3,871 и 0,484 соответственно.')
para('На пяти миллионах упорядоченных элементов четыре потока дают ускорение 1,469, восемь — 1,203. При обратном порядке значения составляют 1,961 и 1,942. Время зависит от порядка данных, в том числе из-за различий в поведении ветвлений при сравнении. При большем числе потоков накладные расходы, пропускная способность памяти и уменьшение числа параллельных задач ограничивают выигрыш. Результаты относятся к конкретному запуску и зависят от загрузки системы; три повтора не дают строгой статистической оценки.')

doc = Document(root.parent / 'os-lab1/materials/report-template.docx')
body = doc._element.body
for item in list(body):
    if not item.tag.endswith('sectPr'): body.remove(item)
style = doc.styles['Normal']; style.font.name = 'Times New Roman'; style.font.size = Pt(12)
for typ, val in blocks:
    if typ == 'h': doc.add_heading(val, level=1)
    elif typ == 'p': doc.add_paragraph(val)
    else:
        t = doc.add_table(rows=0, cols=len(val[0]))
        for row in val:
            cells = t.add_row().cells
            for c, text in zip(cells, row): c.text = text
doc.save(root / 'report/214_Вихарев_Лаб2.docx')

pdfmetrics.registerFont(TTFont('DejaVu', r'C:\Windows\Fonts\arial.ttf'))
styles = getSampleStyleSheet()
normal = ParagraphStyle('ru', parent=styles['Normal'], fontName='DejaVu', fontSize=10, leading=14)
head = ParagraphStyle('ruh', parent=normal, fontSize=13, leading=17, spaceBefore=12, spaceAfter=6)
story = []
for typ, val in blocks:
    if typ == 'h': story.append(Paragraph(val, head))
    elif typ == 'p': story += [Paragraph(val.replace('&', '&amp;').replace('<', '&lt;'), normal), Spacer(1, 6)]
    else:
        t = Table(val, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), 'DejaVu'), ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), .4, colors.grey), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)]))
        story.append(t)
SimpleDocTemplate(str(root / 'report/214_Вихарев_Лаб2.pdf'), pagesize=A4).build(story)
