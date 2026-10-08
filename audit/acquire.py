"""Optional network acquisition into a NEW directory, verifying frozen hashes.

Offline replay does not invoke this script. No package install or upstream code
execution occurs here. Downloaded XML comments are never executed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parent


def acquire(destination):
    destination.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((ROOT/'corpus.json').read_text())
    upstream='https://raw.githubusercontent.com/kurtmckee/feedparser/'+manifest['commit']+'/'
    def save(relative,data,expected):
        assert hashlib.sha256(data).hexdigest()==expected,relative
        p=destination/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    for case in manifest['fixtures']:
        with urlopen(upstream+case['upstream_path'],timeout=30) as response:data=response.read(1048577)
        save('fixtures/'+case['file'],data,case['sha256'])
    vendor=json.loads((ROOT/'vendor/provenance.json').read_text())
    hashes=json.loads((ROOT/'vendor/hashes.json').read_text())
    for name,sha in hashes.items():
        if name.startswith('feedparser/') or name=='FEEDPARSER-LICENSE':
            url=upstream+('LICENSE' if name=='FEEDPARSER-LICENSE' else name)
            with urlopen(url,timeout=30) as response:data=response.read(1048577)
        elif name in ('sgmllib.py','SGMLLIB-PKG-INFO'):
            continue
        elif name=='SGMLLIB-LICENSE':
            with urlopen(vendor['sgmllib3k']['license_source'],timeout=30) as response:data=response.read(1048577)
        else:
            data=(ROOT/'vendor'/name).read_bytes()
        save('vendor/'+name,data,sha)
    with urlopen(vendor['sgmllib3k']['url'],timeout=30) as response:data=response.read(1048577)
    assert hashlib.sha256(data).hexdigest()==vendor['sgmllib3k']['sha256']
    archive=tarfile.open(fileobj=io.BytesIO(data))
    for target,source in [('sgmllib.py','sgmllib.py'),('SGMLLIB-PKG-INFO','PKG-INFO')]:
        data=archive.extractfile('sgmllib3k-1.0.0/'+source).read()
        save('vendor/'+target,data,hashes[target])
    print(f'Acquired and hash-verified {len(manifest["fixtures"])} fixtures and {len(hashes)} dependency files')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();acquire(a.output)
