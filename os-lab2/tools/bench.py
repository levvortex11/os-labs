import csv
import re
import statistics
import subprocess
from pathlib import Path

with Path('report/measurements.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['size', 'pattern', 'threads', 'sequential_median', 'parallel_median', 'speedup', 'efficiency', 'sequential_runs', 'parallel_runs'])
    for n in (10000, 1000000, 5000000):
        for pattern in ('random', 'sorted', 'reverse'):
            for threads in (1, 2, 4, 8):
                sequential = []
                parallel = []
                for _ in range(3):
                    p = subprocess.run(['./merge', str(threads), str(n), pattern], capture_output=True, text=True, check=True)
                    sequential.append(float(re.search(r'Sequential time: ([\d.]+)', p.stdout).group(1)))
                    parallel.append(float(re.search(r'Parallel time: ([\d.]+)', p.stdout).group(1)))
                t1, tp = statistics.median(sequential), statistics.median(parallel)
                speedup = t1 / tp
                writer.writerow([n, pattern, threads, f'{t1:.9f}', f'{tp:.9f}', f'{speedup:.3f}', f'{speedup / threads:.3f}', ';'.join(map(str, sequential)), ';'.join(map(str, parallel))])
                f.flush()
                print(n, pattern, threads, f'S={speedup:.3f}', flush=True)
