"""Sample actual OS thread counts; also print a ps snapshot with four threads."""
import subprocess
import time
from pathlib import Path

for limit in (1, 2, 3, 4, 8):
    p = subprocess.Popen(['./merge', str(limit), '5000000'], stdout=subprocess.DEVNULL)
    peak = 0
    shown = False
    while p.poll() is None:
        try:
            text = Path(f'/proc/{p.pid}/status').read_text()
        except FileNotFoundError:
            break
        count = int(text.split('Threads:')[1].splitlines()[0])
        peak = max(peak, count)
        if limit == 4 and count == 4 and not shown:
            subprocess.run(['ps', '-T', '-p', str(p.pid)], check=True)
            shown = True
        time.sleep(0.001)
    assert p.wait() == 0
    assert 1 <= peak <= limit, (limit, peak)
    print(f'limit={limit}, observed peak={peak}', flush=True)
