"""Build exportable scientific plots from actual benchmark CSV."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader((root / 'report/measurements.csv').open(encoding='utf-8')))
fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), layout='constrained')
names = {'random': 'Случайные', 'sorted': 'По возрастанию', 'reverse': 'По убыванию'}
for pattern, name in names.items():
    data = [r for r in rows if r['size'] == '5000000' and r['pattern'] == pattern]
    x = [int(r['threads']) for r in data]
    for ax, key in zip(axes, ('parallel_ms', 'speedup', 'efficiency')):
        ax.plot(x, [float(r[key]) for r in data], marker='o', markersize=4, label=name)
for ax, title, ylabel in zip(axes, ('Время', 'Ускорение', 'Эффективность'), ('Миллисекунды', 'S = Tseq / Tpar', 'E = S / P')):
    ax.set(title=title, xlabel='Предел потоков P', ylabel=ylabel)
    ax.set_xscale('log', base=2)
    ax.set_xticks([1, 2, 4, 8, 12, 32, 64, 128], ['1', '2', '4', '8', '12', '32', '64', '128'], rotation=45)
    ax.axvline(12, color='grey', linestyle='--', linewidth=1)
    ax.grid(alpha=0.25)
axes[0].legend(fontsize=8)
fig.suptitle('5 000 000 целых чисел · 12 логических процессоров · медианы трёх запусков')
for extension in ('png', 'svg', 'pdf'):
    fig.savefig(root / f'report/scaling.{extension}', dpi=220)
plt.close(fig)
