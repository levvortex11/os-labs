import csv
import re
import statistics
import subprocess
from pathlib import Path

out = Path('report/measurements.csv')
with out.open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['size', 'pattern', 'threads', 'seconds_median', 'speedup', 'efficiency', 'runs_seconds'])
    for n in (10000, 1000000, 5000000):
        for pattern in ('random', 'sorted', 'reverse'):
            baseline = None
            for threads in (1, 2, 4, 8):
                runs = []
                for _ in range(3):
                    p = subprocess.run(['./merge', '--size', str(n), '--pattern', pattern, '--seed', '42', '--threads', str(threads), '--quiet'], capture_output=True, text=True, check=True)
                    runs.append(float(re.search(r'seconds=([\d.]+)', p.stderr).group(1)))
                t = statistics.median(runs)
                if baseline is None:
                    baseline = t
                speedup = baseline / t
                writer.writerow([n, pattern, threads, f'{t:.6f}', f'{speedup:.3f}', f'{speedup / threads:.3f}', ';'.join(map(str, runs))])
                f.flush()
                print(n, pattern, threads, f'{t:.6f}', flush=True)
