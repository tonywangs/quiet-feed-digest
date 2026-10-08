"""Corpus regression expectations and independent-reader snapshot comparisons."""
import copy
import hashlib
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from quiet_feed import core
from quiet_feed.cli import serialize
from audit.run import run
from audit.reader import extract
from tests.test_digest import record, inputs, START, END
from tests.reference import compare as oracle


def publisher_records(data, atom):
    """Bridge only the agreed generated subset to the independent quadratic oracle."""
    found = extract(data, atom)
    assert not found['bozo']
    return [dict(id=r['identity'].split(':',1)[1],title=r['title'],link=r['link'],valid_link=True,
                 excerpt=r['excerpt'],published=r['published']['raw'],
                 updated=r['updated']['raw'] if atom else '') for r in found['records']]


class CompatibilityTests(unittest.TestCase):
    def test_frozen_corpus_and_explicit_outcomes(self):
        result = run()
        self.assertEqual(result['totals']['upstream']['fixtures'], 36)
        self.assertEqual(result['totals']['derived']['fixtures'], 15)

    def test_240_seeded_pairs_against_pinned_reader(self):
        # Separate from the historical 240-pair oracle. Restrict reader agreement
        # to stable IDs, safe absolute links, supported literal text and dates.
        # Missing identities and unsupported fields are tested by frozen probes.
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for seed in range(240):
                with self.subTest(seed=seed):
                    rng=random.Random(91000+seed); atom=bool(seed%2)
                    old=[record(i,atom) for i in range(rng.randint(5,18))]
                    for r in old:
                        r['id']='urn:sample:'+r['id']
                        # Feedparser collapses line breaks in HTML. That policy is
                        # audited separately; this generator uses agreed one-line text.
                        r['excerpt']='Publisher <b>wording</b> & spacing'
                    old[0].update(published='',updated='')
                    new=copy.deepcopy(old)
                    for r in new:
                        if rng.random()<.4:r['title']+=' revised'
                        if rng.random()<.3:r['excerpt']+=' café'
                    del new[rng.randrange(len(new))]
                    extra=record(100+seed,atom);extra.update(id='urn:new:'+str(seed),excerpt='New wording')
                    new.append(extra)
                    if seed%3==0:old.append(dict(old[2],title='Conflict'))
                    if seed%5==0:new.append(dict(new[2],excerpt='Conflict'))
                    if seed%7==0:new.append(dict(new[0]))
                    rng.shuffle(old);rng.shuffle(new)
                    a,b=inputs(folder,old,new,atom)
                    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
                    left=publisher_records((folder/'previous.xml').read_bytes(),atom)
                    right=publisher_records((folder/'current.xml').read_bytes(),atom)
                    result=core.compare(a,b,START,END)
                    def projection(r):
                        return None if r is None else (r['title'],r['link'],r['excerpt'],r['published']['raw'],r['updated']['raw'])
                    actual=sorted((r['identity'],r['status'],projection(r['before']),projection(r['after'])) for r in result['items'])
                    self.assertEqual(actual,oracle(left,right,atom))
                    self.assertEqual(serialize(result),serialize(core.compare(a,b,START,END)))
                    self.assertEqual(hashes,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()})

    def test_base_resolution_keeps_identity_and_raw_href(self):
        xml=b'<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://example.org/a/"><entry><id> raw ID </id><link href="../story"/></entry></feed>'
        records,issues=core.parse_feed(xml)
        self.assertEqual(issues,[])
        self.assertEqual(records[0]['identity'],'atom: raw ID ')
        self.assertEqual(records[0]['link'],'../story')
        self.assertEqual(records[0]['article_url'],'https://example.org/story')
        for base in ['https://example.org/&#10;', 'https://user:pass@example.org/', 'https://[broken/', 'file:///tmp/']:
            altered=xml.replace(b'https://example.org/a/',base.encode())
            records,issues=core.parse_feed(altered)
            self.assertIsNone(records[0]['article_url'])
            self.assertIn('unresolved_relative_link',[i['code'] for i in issues])

    def test_bases_and_hidden_content_remain_bounded(self):
        xml=b'<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://example.org/"><entry><id>x</id><link href="a"/></entry></feed>'
        with patch.object(core,'MAX_FIELD',5):
            records,issues=core.parse_feed(xml)
            self.assertIsNone(records[0]['article_url'])
            self.assertIn('unresolved_relative_link',[i['code'] for i in issues])
        data=(Path(__file__).resolve().parents[1]/'audit/derived/summary-oversize-content.xml').read_bytes()
        with self.assertRaises(core.InputError):core.parse_feed(data)

    def test_unsupported_cases_propagate_incomplete_and_never_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            a,b=inputs(folder,[],[],True)
            corpus=Path(__file__).resolve().parents[1]/'audit/derived'
            for name in ['summary-external','summary-binary','rss-hidden-dc-title','rss-hidden-dc-date','rss-hidden-content-encoded','base-unresolved','base-no-identity']:
                (folder/'current.xml').write_bytes((corpus/(name+'.xml')).read_bytes())
                self.assertEqual(core.compare(a,b,START,END)['outcome'],'incomplete',name)
