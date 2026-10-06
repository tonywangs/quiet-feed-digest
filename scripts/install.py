#!/usr/bin/env python3
"""Install a self-contained CLI zipapp, offline and without pip or a build backend."""
import argparse
from pathlib import Path
import shutil
import tempfile
import zipapp


def install(destination):
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copytree(root / 'quiet_feed', stage / 'quiet_feed', ignore=shutil.ignore_patterns('__pycache__'))
        artifact = stage / 'quiet-feed.pyz'
        source = stage / 'source'
        source.mkdir()
        shutil.move(str(stage / 'quiet_feed'), source)
        # zipapp's generated entrypoint does not propagate an integer exit status.
        # Supply our own entrypoint so incomplete/error outcomes survive installation.
        (source / '__main__.py').write_text('from quiet_feed.cli import main\nraise SystemExit(main())\n')
        zipapp.create_archive(source, artifact, interpreter='/usr/bin/env python3')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as target:
            target.write(artifact.read_bytes())
        destination.chmod(0o755)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New executable file path')
    args = parser.parse_args()
    print(install(args.output))
