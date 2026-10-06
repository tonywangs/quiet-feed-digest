#!/usr/bin/env python3
"""One-command offline verification. Optional browser tests require preinstalled Playwright/Chromium."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import xml.parsers.expat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.install import install
from tests.test_digest import START, END, feed, inputs, record

GUARD = '''import runpy, sys
network_attempts = []
def audit(event, args):
    if event.startswith("socket.") or event in ("urllib.Request", "http.client.connect"):
        network_attempts.append(event)
        raise RuntimeError("Offline verification blocked network: " + event)
sys.addaudithook(audit)
sys.argv = sys.argv[1:]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
finally:
    if network_attempts:
        raise RuntimeError("Unexpected network attempts: " + repr(network_attempts))
'''


def run_installed(exe, previous, current, output, cwd, max_items=100, expected=0):
    command = [sys.executable, '-I', '-c', GUARD, str(exe), '--previous', str(previous), '--current', str(current),
               '--start', START, '--end', END, '--output', str(output), '--max-items', str(max_items)]
    # RUSAGE_CHILDREN on a dedicated fork records only this CLI, in KiB on Linux.
    metrics_file = cwd / ('metrics-' + output.name + '.json')
    pid = os.fork()
    if pid == 0:
        try:
            begin = time.perf_counter()
            result = subprocess.run(command, cwd=cwd, env={'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8'},
                                    capture_output=True, text=True, timeout=35)
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            metrics_file.write_text(json.dumps({'elapsed_seconds': time.perf_counter() - begin,
                'peak_rss_kib': usage.ru_maxrss, 'exit_code': result.returncode,
                'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}))
            os._exit(0)
        except BaseException:
            os._exit(1)
    _, status = os.waitpid(pid, 0)
    assert status == 0, 'Measurement subprocess failed'
    metrics = json.loads(metrics_file.read_text())
    assert metrics['exit_code'] == expected, metrics
    # Absolute temp paths are not useful reproducible evidence.
    metrics.pop('stdout')
    metrics.pop('stderr')
    if output.exists() and expected in (0, 2):
        assert not (output / 'INCOMPLETE').exists()
        metrics['artifacts'] = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in sorted(output.iterdir())}
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true', help='Require real Chromium checks; fail if unavailable')
    parser.add_argument('--results', type=Path, default=ROOT / 'results')
    args = parser.parse_args()
    results = args.results.resolve()
    results.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-v'], cwd=ROOT, capture_output=True, text=True)
    (results / 'tests.log').write_text(test.stdout + test.stderr)
    if test.returncode:
        print(test.stdout + test.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix='quiet-feed-verify-') as tmp:
        base = Path(tmp)
        isolated = base / 'empty-working-directory'
        isolated.mkdir()
        exe = install(base / 'bin/quiet-feed')
        snapshots = base / 'snapshots'
        shutil.copytree(ROOT / 'examples', snapshots)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshots.iterdir()}
        sample = base / 'sample'
        sample_metrics = run_installed(exe, snapshots / 'previous.json', snapshots / 'current.json', sample, isolated)
        report = json.loads((sample / 'report.json').read_text())
        assert report['counts'] == {'absent': 1, 'new': 2, 'revised': 1, 'unchanged': 1}
        repeat = base / 'repeat'
        run_installed(exe, snapshots / 'previous.json', snapshots / 'current.json', repeat, isolated)
        assert all((sample / name).read_bytes() == (repeat / name).read_bytes() for name in ('report.json', 'index.html'))
        assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshots.iterdir()}
        run_installed(exe, snapshots / 'previous.json', snapshots / 'current.json', sample, isolated, expected=1)
        # Stress all 200 displayed records with before and after views, plus 50 omitted.
        bounded_inputs = base / 'bounded-inputs'
        bounded_inputs.mkdir()
        old = [record(i) for i in range(250)]
        new = [dict(r, excerpt=r['excerpt'] + '\nRevised sample wording.') for r in old]
        a, b = inputs(bounded_inputs, old, new)
        bounded = base / 'bounded'
        bounded_metrics = run_installed(exe, a, b, bounded, isolated, max_items=200)
        # Hostile text across metadata, titles, excerpts, and article URLs.
        evil_inputs = base / 'evil-inputs'
        evil_inputs.mkdir()
        evil = '</script><script>window.PWNED=1</script><img src="https://evil.invalid/pixel" onerror="window.PWNED=1"><iframe src="https://evil.invalid/">'
        evil_records = [dict(record(1), title=evil, excerpt=evil, link='javascript:alert(1)'),
                        dict(record(2), title='A' * 2048, excerpt=evil, link='https://example.org/safe?a=1&b=2'),
                        dict(record(3), id='', link='', valid_link=False)]
        a, b = inputs(evil_inputs, [], evil_records)
        for path in (a, b):
            obj = json.loads(path.read_text())
            obj['feeds'][0]['label'] = evil[:256]
            path.write_text(json.dumps(obj))
        hostile = base / 'hostile'
        hostile_metrics = run_installed(exe, a, b, hostile, isolated, expected=2)
        browser = {'performed': False, 'reason': 'Run with --browser and provision the documented development tools'}
        if args.browser:
            evidence = results / 'browser.json'
            command = ['node', str(ROOT / 'scripts/browser_test.cjs'), str(sample / 'index.html'),
                       str(hostile / 'index.html'), str(bounded / 'index.html'), str(evidence)]
            subprocess.run(command, check=True, timeout=90, cwd=ROOT)
            browser = {'performed': True, **json.loads(evidence.read_text())}
        # Keep small, reproducible normal example artifacts for inspection.
        example = results / 'example'
        example.mkdir(exist_ok=True)
        for name in ('report.json', 'index.html'):
            shutil.copyfile(sample / name, example / name)
        evidence = {'python': platform.python_version(), 'platform': platform.platform(),
                    'expat': xml.parsers.expat.EXPAT_VERSION, 'runtime_dependencies': 'Python standard library only',
                    'verification_elapsed_seconds': time.perf_counter() - started,
                    'seeded_pairs': 240, 'unit_test_exit_code': test.returncode,
                    'installed_cli_offline': 'zipapp; isolated Python (-I); empty cwd; socket/HTTP audit hooks reject network',
                    'sample': sample_metrics, 'bounded_250_revisions': bounded_metrics, 'hostile': hostile_metrics,
                    'deterministic_repeat': True, 'input_hashes_unchanged': True, 'browser': browser}
        (results / 'verification.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    print(f'Verification passed; evidence in {results}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
