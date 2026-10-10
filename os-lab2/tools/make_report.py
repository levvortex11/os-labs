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
para('Реализована рекурсивная сортировка слиянием. Функция merge_sort делит диапазон пополам, сортирует обе половины и объединяет их функцией merge. Границы диапазона задаются полуинтервалом [left, right). Вспомогательный массив выделяется один раз. Результат слияния сначала записывается во вспомогательный массив, затем копируется в исходный.')
para('В parallel_sort левая половина может передаваться новому потоку, а правая обрабатывается текущим. После pthread_join выполняется слияние. Счётчик free_threads изначально равен P−1; перед созданием потока слот резервируется под защитой pthread_mutex, после его завершения и ожидания слот освобождается. Ожидающий родитель тоже считается потоком, его слот не освобождается. Поэтому одновременно существует не больше P потоков, включая главный. Для диапазона короче 16384 элементов и при отсутствии свободного слота используется последовательная сортировка. Ошибки pthread завершают весь процесс с диагностикой.')
para('Разные потоки обрабатывают непересекающиеся участки обоих массивов. Мьютекс защищает только счётчик слотов, а pthread_join обеспечивает готовность половины перед слиянием. Время сортировки O(n log n), дополнительная память O(n) для буфера и O(P log n) для стеков потоков в верхней оценке. Финальное слияние выполняется одним потоком, что ограничивает ускорение.')
heading('Запуск и проверка')
para('Сборка в Linux: make. Запуск: ./merge THREADS [SIZE] [random|sorted|reverse]. Пример: ./merge 4 1000000. Если размер не задан, создаются 5 000 000 элементов. Данные генерируются автоматически с srand(42); два одинаковых массива сортируются последовательно и параллельно. При размере не больше 20 выводятся исходные и отсортированные элементы. Размер и число потоков задаются положительными целыми числами; верхняя граница числа потоков — 256. Ручной ввод элементов не используется.')
para('Для демонстрации потоков: python3 tools/check_threads.py. Скрипт наблюдает число потоков через /proc и выводит снимок ps -T. При лимитах 1, 2, 3, 4 и 8 наблюдались соответствующие максимумы без превышений. Проверка make test: 45 сравнений с независимой qsort, включая пустой массив на уровне функций, границы int и размеры вокруг порога распараллеливания; 22 проверки CLI, включая неверные аргументы. Все проверки прошли.')
heading('Исследование')
para('Среда: Ubuntu 24.04 в WSL2, Intel Core i5-13420H, системе доступно 12 логических процессоров. Сборка GCC с оптимизацией -O2. Для каждой комбинации выполнены три запуска; отдельно взяты медианы времени последовательной и параллельной сортировки по CLOCK_MONOTONIC. Генерация, выделение памяти, вывод и проверка результата в это время не входят. Ускорение S = median(Tseq)/median(Tpar), эффективность E = S/p. В каждом запуске последовательная сортировка выполняется первой; прогрев и нагрузка системы могут влиять на результаты. Полные замеры сохранены в measurements.csv, повторный запуск: python3 tools/bench.py.')
for n in ('10000', '1000000', '5000000'):
    heading('Размер массива: ' + n)
    data = [['Данные', 'Потоки', 'Tseq, с', 'Tpar, с', 'S', 'E']]
    names = {'random': 'случайные', 'sorted': 'по возрастанию', 'reverse': 'по убыванию'}
    for r in rows:
        if r['size'] == n:
            data.append([names[r['pattern']], r['threads'], f"{float(r['sequential_median']):.6f}", f"{float(r['parallel_median']):.6f}", r['speedup'], r['efficiency']])
    table(data)
heading('Анализ и вывод')
large = next(r for r in rows if r['size'] == '5000000' and r['pattern'] == 'random' and r['threads'] == '8')
para(f"На пяти миллионах случайных чисел при восьми потоках получено ускорение {large['speedup']} и эффективность {large['efficiency']}. На 10 000 элементов дополнительные потоки не создаются из-за порога 16384; отклонения отношения времён от единицы связаны с малой длительностью, прогревом и шумом измерений.")
para('На больших массивах параллельная обработка половин позволяет сократить время. Линейное ускорение ограничивается последовательным финальным слиянием, созданием и ожиданием потоков, доступом к памяти и разным числом свободных слотов в момент рекурсивного вызова. Упорядоченные и случайные данные отличаются поведением ветвлений при сравнении. Три повтора дают предварительную оценку; результаты зависят от машины и фоновой нагрузки. При одном потоке отдельный замер последовательной сортировки не обязан точно совпадать со временем parallel_sort, которая вызывает тот же последовательный алгоритм.')

doc = Document(root.parent / 'os-lab1/materials/report-template.docx')
body = doc._element.body
for item in list(body):
    if not item.tag.endswith('sectPr'): body.remove(item)
style = next(s for s in doc.styles if s.style_id == 'Normal')
style.font.name = 'Times New Roman'; style.font.size = Pt(12)
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
head = ParagraphStyle('ruh', parent=normal, fontSize=13, leading=17, spaceBefore=12, spaceAfter=6, keepWithNext=True)
story = []
for typ, val in blocks:
    if typ == 'h': story.append(Paragraph(val, head))
    elif typ == 'p': story += [Paragraph(val.replace('&', '&amp;').replace('<', '&lt;'), normal), Spacer(1, 6)]
    else:
        t = Table(val, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), 'DejaVu'), ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), .4, colors.grey), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)]))
        story.append(t)
SimpleDocTemplate(str(root / 'report/214_Вихарев_Лаб2.pdf'), pagesize=A4).build(story)
