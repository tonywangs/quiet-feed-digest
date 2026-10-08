"""Reconstruct the catalog parser from its Git tree and check before evidence.

Requires the catalog tree object locally. No checkout, index mutation, network,
credential access or production-code replacement is performed.
"""
from pathlib import Path
import argparse
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
ROOT=Path(__file__).resolve().parents[1]
TREE='01c0ae3592ee77d8b4aa1bb62929ba2de6b33ab8'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tree',default=TREE);args=parser.parse_args()
    # git archive reads a fixed tree; filenames are additionally constrained.
    data=subprocess.check_output(['git','archive',args.tree],cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='quiet-feed-baseline-replay-') as tmp:
        stage=Path(tmp)
        archive=tarfile.open(fileobj=io.BytesIO(data))
        for member in archive.getmembers():
            assert not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            assert member.isfile() or member.isdir()
            if member.isfile():
                target=stage/member.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.extractfile(member).read())
        shutil.copytree(ROOT/'audit',stage/'audit',ignore=shutil.ignore_patterns('__pycache__'))
        output=stage/'before.json'
        from scripts.verify import GUARD
        subprocess.run([sys.executable,'-c',GUARD,str(stage/'audit/run.py'),'--baseline','--output',str(output)],cwd=stage,check=True)
        expected=json.loads((ROOT/'results/compatibility/before.json').read_text())
        actual=json.loads(output.read_text())
        # Diagnostic wording/counter improvements are allowed; every observed
        # production/reader value and oracle outcome must reconstruct exactly.
        def project(cases):
            return [{k:r[k] for k in ('group','file','expected','actual','independent_reader','expectation_passed')} for r in cases]
        assert project(expected['cases'])==project(actual['cases'])
    print('Reconstructed all 51 before-audit observations from catalog tree '+args.tree)

if __name__=='__main__':
    sys.path.insert(0,str(ROOT));main()
