"""Run in Linux/WSL: real wall times in ms and OS-observed thread counts."""
import csv
import json
import os
import platform
import re
import statistics
import subprocess
import time
from pathlib import Path

cpus = os.cpu_count()
limits = [1, 2, 4, 8, cpus, 32, 64, 128]
assert len([p for p in limits if p < cpus]) >= 4
assert len([p for p in limits if p > cpus]) >= 3
cpu_model = next((s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')), 'unknown')
metadata = dict(logical_cpus=cpus, limits=limits, repeats=3,
                cpu_model=cpu_model, platform=platform.platform(),
                compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                clock='CLOCK_MONOTONIC', unit='ms', sequential_first=True)
Path('report/environment.json').write_text(json.dumps(metadata, indent=2) + '\n')

with Path('report/measurements.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['size', 'pattern', 'threads', 'sequential_ms', 'parallel_ms', 'speedup', 'efficiency', 'created_incl_main', 'observed_peak', 'sequential_runs_ms', 'parallel_runs_ms', 'created_runs', 'observed_runs'])
    for n in (10000, 1000000, 5000000):
        for pattern in ('random', 'sorted', 'reverse'):
            for threads in limits:
                sequential, parallel, created, peaks = [], [], [], []
                for _ in range(3):
                    p = subprocess.Popen(['./merge', str(threads), str(n), pattern], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    peak = 1
                    while p.poll() is None:
                        try:
                            status = Path(f'/proc/{p.pid}/status').read_text()
                            peak = max(peak, int(status.split('Threads:')[1].splitlines()[0]))
                        except FileNotFoundError:
                            pass
                        time.sleep(0.001)
                    stdout, stderr = p.communicate()
                    if p.returncode:
                        raise RuntimeError(f'{n=} {threads=}: {stderr}')
                    assert 'Check: OK' in stdout
                    count = int(re.search(r'Threads created incl main: (\d+)', stdout).group(1))
                    assert peak <= count <= threads, (threads, count, peak)
                    assert peak <= threads, (threads, peak)
                    sequential.append(float(re.search(r'Sequential ms: ([\d.]+)', stdout).group(1)))
                    parallel.append(float(re.search(r'Parallel ms: ([\d.]+)', stdout).group(1)))
                    peaks.append(peak)
                    created.append(count)
                t1, tp = statistics.median(sequential), statistics.median(parallel)
                speedup = t1 / tp
                writer.writerow([n, pattern, threads, f'{t1:.6f}', f'{tp:.6f}', f'{speedup:.3f}', f'{speedup / threads:.6f}', max(created), max(peaks), ';'.join(map(str, sequential)), ';'.join(map(str, parallel)), ';'.join(map(str, created)), ';'.join(map(str, peaks))])
                f.flush()
                print(n, pattern, threads, f'{tp:.3f} ms', f'S={speedup:.3f}', f'observed={max(peaks)}', flush=True)
