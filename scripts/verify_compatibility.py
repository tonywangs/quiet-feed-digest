#!/usr/bin/env python3
"""One-command offline compatibility replay, including isolated installed CLI.

Use --browser to require provisioned Playwright and Chromium as well.
Historical results are never overwritten. All new evidence is kept separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.parsers.expat
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from audit.run import run
from audit.scenarios import build
from scripts.install import install
from scripts.verify import run_installed, GUARD


def hashes(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def deny_network(event,args):
    if event.startswith('socket.') or event in ('urllib.Request','http.client.connect'):
        raise RuntimeError('Offline replay blocked network: '+event)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',action='store_true')
    parser.add_argument('--results',type=Path,default=ROOT/'results/compatibility')
    args=parser.parse_args();results=args.results.resolve();results.mkdir(parents=True,exist_ok=True)
    sys.addaudithook(deny_network)
    start=time.perf_counter()
    for name,sha in json.loads((ROOT/'audit/vendor/hashes.json').read_text()).items():
        assert hashlib.sha256((ROOT/'audit/vendor'/name).read_bytes()).hexdigest()==sha,name
    corpus_before=hashes(ROOT/'audit')
    audit=run()
    (results/'after.json').write_text(json.dumps(audit,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='quiet-feed-compatibility-') as tmp:
        base=Path(tmp)
        # Retains original seeded tests, resource/collision/cleanup checks, and
        # historical installed sample + hostile + bounded browser regressions.
        original=base/'historical-checks'
        command=[sys.executable,'-c',GUARD,str(ROOT/'scripts/verify.py'),'--results',str(original)]
        if args.browser:command.append('--browser')
        checked=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=180)
        if (original/'tests.log').exists():(results/'tests.txt').write_bytes((original/'tests.log').read_bytes())
        assert checked.returncode==0,checked.stdout+checked.stderr
        historical=json.loads((original/'verification.json').read_text())
        assert hashes(original/'example') == hashes(ROOT/'results/example'), 'Historical example bytes changed'
        exe=install(base/'bin/quiet-feed')
        isolated=base/'empty';isolated.mkdir()
        snapshots=base/'snapshots';previous,current=build(snapshots)
        inputs_before=hashes(snapshots)
        first=base/'first';second=base/'second'
        metrics=run_installed(exe,previous,current,first,isolated)
        repeat=run_installed(exe,previous,current,second,isolated)
        report=json.loads((first/'report.json').read_text())
        assert report['outcome']=='complete'
        assert report['counts']=={'new':3,'revised':1,'unchanged':1,'absent':0},report['counts']
        assert any(i['after'] and i['after']['article_url']=='https://example.org/corpus/story' for i in report['items'])
        assert hashes(first)==hashes(second)
        assert inputs_before==hashes(snapshots)
        run_installed(exe,previous,current,first,isolated,expected=1)
        # Installed incomplete and strict failure paths using acquired corpus.
        (snapshots/'current-atom.xml').write_bytes((ROOT/'audit/fixtures/wellformed-atom10--entry_content_src.xml').read_bytes())
        incomplete=base/'incomplete'
        incomplete_metrics=run_installed(exe,previous,current,incomplete,isolated,expected=2)
        assert json.loads((incomplete/'report.json').read_text())['outcome']=='incomplete'
        (snapshots/'current-atom.xml').write_bytes((ROOT/'audit/fixtures/illformed--aaa_illformed.xml').read_bytes())
        failed=base/'failed';run_installed(exe,previous,current,failed,isolated,expected=1);assert not failed.exists()
        browser={'performed':False,'reason':'--browser required to exercise Chromium'}
        if args.browser:
            subprocess.run(['node',str(ROOT/'scripts/browser_compatibility.cjs'),str(first/'index.html'),str(first/'report.json'),str(results/'browser.json')],check=True,cwd=ROOT,timeout=90)
            browser={'performed':True,**json.loads((results/'browser.json').read_text())}
        artifact=results/'corpus-example';artifact.mkdir(exist_ok=True)
        for p in first.iterdir():shutil.copyfile(p,artifact/p.name)
        evidence={'python':platform.python_version(),'platform':platform.platform(),'expat':xml.parsers.expat.EXPAT_VERSION,
                  'dependencies':json.loads((ROOT/'audit/vendor/provenance.json').read_text()),'totals':audit['totals'],
                  'historical_checks':historical,'seeded_pairs_against_pinned_reader':240,'seed_range':[91000,91239],
                  'installed_corpus_cli':metrics,'repeated_corpus_cli':repeat,'installed_incomplete_cli':incomplete_metrics,
                  'repeated_output_hashes_equal':True,'snapshot_input_hashes_unchanged':True,
                  'offline':'Python audit hooks reject socket/HTTP operations in audit and installed CLI; Chromium offline and routing enforced when requested',
                  'corpus_browser':browser,'elapsed_seconds':time.perf_counter()-start}
    assert corpus_before==hashes(ROOT/'audit'),'Audit inputs changed'
    (results/'verification.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'totals':audit['totals'],'elapsed_seconds':evidence['elapsed_seconds'],'browser':args.browser},sort_keys=True))

if __name__=='__main__':main()
