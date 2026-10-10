import random
import subprocess

random.seed(42)
cases = [[], [1], [3, 1, 2, 1, -4], [2147483647, -2147483648, 0], list(range(129)), list(range(127, -1, -1))]
cases += [[random.randint(-100, 100) for _ in range(n)] for n in (2, 3, 31, 128, 999, 10000)]
for threads in (1, 2, 3, 8):
    for a in cases:
        data = f'{len(a)}\n' + ' '.join(map(str, a)) + '\n'
        p = subprocess.run(['./merge', '--threads', str(threads)], input=data, text=True, capture_output=True, check=True)
        assert list(map(int, p.stdout.split())) == sorted(a), (threads, a)
for args, data in [(['--threads', '0'], ''), (['--threads', '257'], ''), ([], '2\n1\n'), (['--pattern', 'bad'], '0\n')]:
    assert subprocess.run(['./merge', *args], input=data, text=True, capture_output=True).returncode != 0
print(f'{len(cases) * 4 + 4} checks passed')
