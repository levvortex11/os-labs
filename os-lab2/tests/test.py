import os
import subprocess
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    binary = str(Path(tmp) / 'sort_test')
    subprocess.run([os.environ.get('CC', 'gcc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Wpedantic', '-Wconversion', '-Wshadow', '-Werror', '-pthread', 'tests/sort_test.c', '-o', binary], check=True)
    subprocess.run([binary], check=True)

checks = 0
for threads in (1, 2, 3, 8):
    for pattern in ('random', 'sorted', 'reverse'):
        p = subprocess.run(['./merge', str(threads), '19', pattern], capture_output=True, text=True, check=True)
        before = list(map(int, p.stdout.split('Before:')[1].splitlines()[0].split()))
        after = list(map(int, p.stdout.split('After:')[1].splitlines()[0].split()))
        assert after == sorted(before)
        assert 'Check: OK' in p.stdout
        checks += 1
for args in ([], ['0'], ['-1'], ['257'], ['abc'], ['4', '0'], ['4', '-1'], ['4', '999999999999999999999999'], ['4', '100', 'bad'], ['4', '1', 'random', 'extra']):
    assert subprocess.run(['./merge', *args], capture_output=True).returncode != 0
    checks += 1
print(f'{checks} CLI checks passed')
