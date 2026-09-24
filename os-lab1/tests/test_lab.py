"""Integration tests: run the real parent and child processes."""
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = '.exe' if os.name == 'nt' else ''
PARENT = ROOT / ('parent' + SUFFIX)
CHILD = ROOT / ('child' + SUFFIX)
RESULTS = []


def run_case(name, commands, expected, success=True, diagnostic=None,
             filename='result.txt', child=None):
    with tempfile.TemporaryDirectory(prefix='os-lab1-') as folder:
        process = subprocess.run(
            [str(PARENT), str(child or CHILD)], cwd=folder,
            input=filename.encode() + b'\n' + commands,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        output_path = Path(folder) / filename
        actual = output_path.read_bytes() if output_path.is_file() else None
        assert actual == expected, (name, actual, expected, process.stderr)
        assert (process.returncode == 0) == success, (name, process.returncode, process.stderr)
        assert process.stdout == b'', (name, process.stdout)
        if diagnostic:
            assert diagnostic.encode() in process.stderr, (name, process.stderr)
        RESULTS.append({'name': name, 'passed': True,
                        'exit_code': process.returncode,
                        'stderr': process.stderr.decode(errors='replace').strip()})
        print('PASS:', name)


def interactive_zero():
    # Keep stdin OPEN. Parent must notice child termination via pipe2.
    with tempfile.TemporaryDirectory(prefix='os-lab1-') as folder:
        p = subprocess.Popen([str(PARENT), str(CHILD)], cwd=folder,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        try:
            p.stdin.write(b'result.txt\n100 2\n9 0\n')
            p.stdin.flush()
            code = p.wait(timeout=10)
            assert code != 0
            assert (Path(folder) / 'result.txt').read_bytes() == b'50\n'
            assert b'Division by zero' in p.stderr.read()
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()
    RESULTS.append({'name': 'zero with stdin still open', 'passed': True,
                    'exit_code': code})
    print('PASS: zero with stdin still open')


def main():
    run_case('sequential integer division', b'100 2 5\n-20 3\n7\n0 5\n',
             b'10\n-6\n7\n0\n')
    run_case('limits and signs', b'-2147483648 1\n+2147483647 -1\n-7 -2\n',
             b'-2147483648\n-2147483647\n3\n')
    run_case('whitespace and CRLF', b'  81\t3 3 \r\n20\v2\f2\n', b'9\n5\n')
    run_case('EOF without newline', b'40 2 4', b'5\n')
    run_case('empty command stream', b'', b'')
    run_case('filename with spaces', b'12 2\n', b'6\n', filename='result file.txt')
    run_case('zero stops all following commands', b'20 2\n9 0\n81 3\n',
             b'10\n', False, 'Division by zero')
    run_case('negative zero divisor', b'1 -0\n', b'', False, 'Division by zero')
    run_case('division overflow', b'-2147483648 -1\n', b'', False, 'overflow')
    run_case('positive input overflow', b'2147483648\n', b'', False, 'out of range')
    run_case('negative input overflow', b'-2147483649\n', b'', False, 'out of range')
    run_case('invalid character', b'12 x\n', b'', False, 'Invalid integer')
    run_case('bare sign', b'1 -\n', b'', False, 'sign')
    run_case('empty line', b'\n', b'', False, 'Empty command')
    run_case('embedded NUL', b'1\x00 2\n', b'', False, 'Invalid integer')
    run_case('missing output directory', b'10 2\n', None, False,
             'open output file', filename='missing/result.txt')
    run_case('exec failure', b'10 2\n', None, False, 'execv', child=ROOT/'missing-child')
    run_case('line larger than pipe capacity', b'42' + b' 1' * 150000 + b'\n', b'42\n')
    rng = random.Random(214)
    lines, answers = [], []
    for _ in range(1000):
        nums = [rng.randint(-2147483647, 2147483647)]
        nums.extend(rng.choice([-9, -3, -1, 1, 2, 7]) for _ in range(rng.randrange(1, 15)))
        answer = nums[0]
        for divisor in nums[1:]:
            negative = (answer < 0) != (divisor < 0)
            answer = abs(answer) // abs(divisor)
            if negative:
                answer = -answer
        lines.append(' '.join(map(str, nums)))
        answers.append(str(answer))
    run_case('1000 random commands', ('\n'.join(lines)+'\n').encode(),
             ('\n'.join(answers)+'\n').encode())
    interactive_zero()
    target = ROOT / 'tests' / 'results.json'
    target.write_text(json.dumps({'environment': 'MSYS2 POSIX / GCC 15.3.0 on Windows'
                                 if os.name == 'nt' else 'POSIX',
                                 'tests': RESULTS}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(RESULTS)} tests passed')


if __name__ == '__main__':
    main()
