"""POSIX command line with deadline and exclusive output directory ownership."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import signal
import sys

from . import __version__
from .core import InputError, MAX_REPORT_BYTES, compare
from .report import render


@contextmanager
def deadline(seconds):
    def expired(signum, frame):
        raise InputError('Processing time limit exceeded')
    def cancelled(signum, frame):
        raise KeyboardInterrupt
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGALRM, signal.SIGTERM)}
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, expired)
    signal.signal(signal.SIGTERM, cancelled)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        signal.setitimer(signal.ITIMER_REAL, *old_timer)


def serialize(report):
    data = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    html = render(report).encode('utf-8')
    if any(len(blob) > MAX_REPORT_BYTES for blob in (data, html)):
        raise InputError('Report size limit exceeded')
    return {'report.json': data, 'index.html': html}


def write_bundle(output: Path, blobs):
    # mkdir is exclusive even against symlinks and concurrent CLI writers.
    output.mkdir(mode=0o700)
    try:
        (output / 'INCOMPLETE').write_text('Do not use until this marker is removed.\n')
        for name, data in blobs.items():
            with (output / name).open('xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        (output / 'INCOMPLETE').unlink()
    except BaseException:
        shutil.rmtree(output)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare saved RSS/Atom snapshots without network access.')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--previous', required=True, type=Path)
    parser.add_argument('--current', required=True, type=Path)
    parser.add_argument('--start', required=True, help='Exclusive observation-window start, ISO 8601 with timezone')
    parser.add_argument('--end', required=True, help='Inclusive observation-window end, ISO 8601 with timezone')
    parser.add_argument('--output', required=True, type=Path, help='New directory; existing destinations are never overwritten')
    parser.add_argument('--max-items', type=int, default=100)
    parser.add_argument('--timeout', type=float, default=30, help='Processing seconds (0 < timeout <= 30)')
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 30:
        parser.error('timeout must be > 0 and <= 30 seconds')
    try:
        with deadline(args.timeout):
            report = compare(args.previous, args.current, args.start, args.end, args.max_items)
            blobs = serialize(report)
            write_bundle(args.output, blobs)
        print(f"{report['outcome']}: {report['digest']['shown']} selected, {report['digest']['omitted']} omitted; {args.output}")
        return 2 if report['outcome'] == 'incomplete' else 0
    except KeyboardInterrupt:
        print('Cancelled; no completed report produced.', file=sys.stderr)
        return 130
    except (InputError, OSError, ValueError, RecursionError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
