import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape, quoteattr

from quiet_feed import core
from quiet_feed.cli import deadline, main, serialize, write_bundle
from quiet_feed.report import render
from tests.reference import compare as oracle

START = '2026-10-05T12:00:00Z'
END = '2026-10-06T12:00:00Z'
ROOT = Path(__file__).resolve().parents[1]


def feed(records, atom=False):
    entries = []
    for r in records:
        if atom:
            entries.append('<entry><id>' + escape(r['id']) + '</id><title>' + escape(r['title']) + '</title>'
                           + '<link href=' + quoteattr(r['link']) + '/><summary type="html">' + escape(r['excerpt'])
                           + '</summary><published>' + escape(r['published']) + '</published><updated>' + escape(r['updated']) + '</updated></entry>')
        else:
            entries.append('<item><guid>' + escape(r['id']) + '</guid><title>' + escape(r['title']) + '</title><link>'
                           + escape(r['link']) + '</link><description>' + escape(r['excerpt']) + '</description><pubDate>'
                           + escape(r['published']) + '</pubDate></item>')
    return ('<feed xmlns="http://www.w3.org/2005/Atom">' + ''.join(entries) + '</feed>' if atom else
            '<rss version="2.0"><channel>' + ''.join(entries) + '</channel></rss>').encode()


def record(i, atom=False):
    return {'id': f'id-{i}', 'title': f'Note {i} — 日本語 café 🌱', 'link': f'https://example.org/{i}', 'valid_link': True,
            'excerpt': 'Publisher <b>wording</b> & spacing\nsecond line',
            'published': '2026-10-05T09:30:00+02:00' if atom else 'Mon, 05 Oct 2026 09:30:00 +0200',
            'updated': '2026-10-05T10:00:00Z' if atom else ''}


def inputs(directory, old, new, atom=False):
    for side, records, date in [('previous', old, START), ('current', new, END)]:
        (directory / (side + '.xml')).write_bytes(feed(records, atom))
        (directory / (side + '.json')).write_text(json.dumps({'version': 1, 'observed_at': date,
            'feeds': [{'id': 'sample', 'label': 'Synthetic source', 'path': side + '.xml'}]}))
    return directory / 'previous.json', directory / 'current.json'


def projection(item):
    if item is None:
        return None
    return (item['title'], item['link'], item['excerpt'], item['published']['raw'], item['updated']['raw'])


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def pair(self, old=None, new=None, atom=False):
        return inputs(self.path, old or [], new or [], atom)

    def compare(self, *args, **kwargs):
        return core.compare(*args, START, END, **kwargs)

    def test_240_seeded_pairs_against_independent_oracle(self):
        for seed in range(240):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                atom = bool(seed % 2)
                old = [record(i, atom) for i in range(rng.randint(8, 25))]
                # Missing identity, exact-link fallback, hostile links, missing dates.
                old[0].update(id='', link='', valid_link=False)
                old[1].update(id='')
                old[2].update(link='javascript:alert(1)', valid_link=False)
                old[3].update(published='', updated='')
                old[4].update(excerpt='<img src="https://invalid.example/pixel" onerror="alert(1)"><script>window.PWNED=1</script>')
                new = copy.deepcopy(old)
                for r in new:
                    if rng.random() < .4:
                        r['excerpt'] += f' — revision {seed}'
                    if rng.random() < .2:
                        r['title'] += ' (changed)'
                del new[rng.randrange(len(new))]
                new.extend(record(i, atom) for i in range(30, 30 + rng.randrange(1, 5)))
                # Duplicate conflicts sometimes exist in only one snapshot.
                if seed % 3 == 0:
                    old.append(dict(old[5], title='Conflicting prior record'))
                if seed % 5 == 0:
                    new.append(dict(new[6], excerpt='Conflicting current record'))
                if seed % 7 == 0:
                    new.append(copy.deepcopy(new[1]))
                rng.shuffle(old)
                rng.shuffle(new)
                a, b = self.pair(old, new, atom)
                before_hashes = [hashlib.sha256(p.read_bytes()).digest() for p in self.path.iterdir()]
                actual = self.compare(a, b, max_items=3)
                found = sorted((r['identity'], r['status'], projection(r['before']), projection(r['after'])) for r in actual['items'])
                self.assertEqual(oracle(old, new, atom), found)
                self.assertEqual(serialize(actual), serialize(self.compare(a, b, max_items=3)))
                self.assertEqual(before_hashes, [hashlib.sha256(p.read_bytes()).digest() for p in self.path.iterdir()])
                self.assertLessEqual(actual['digest']['shown'], 3)
                self.assertEqual(sum(actual['counts'].values()), actual['digest']['shown'] + actual['digest']['omitted'])
                self.assertEqual(sum(actual['digest']['omitted_by_status'].values()), actual['digest']['omitted'])

    def test_example_core_workflow(self):
        report = self.compare(ROOT / 'examples/previous.json', ROOT / 'examples/current.json')
        self.assertEqual(report['outcome'], 'complete')
        self.assertEqual(report['counts'], {'new': 2, 'revised': 1, 'absent': 1, 'unchanged': 1})
        self.assertEqual(report['digest']['shown'], 3)
        atom = next(i['after'] for i in report['items'] if i['feed_id'] == 'notes')
        self.assertEqual(atom['updated']['utc'], '2026-10-06T09:00:00Z')

    def test_missing_and_conflicting_identity_never_guessed(self):
        old = [record(1), dict(record(1), title='Conflict'), record(2)]
        new = [record(1), dict(record(3), id='', link='', valid_link=False)]
        report = self.compare(*self.pair(old, new))
        self.assertEqual(report['outcome'], 'incomplete')
        self.assertEqual([(x['identity'], x['status']) for x in report['items']], [('rss:id-2', 'absent')])
        self.assertEqual({i['code'] for i in report['issues']}, {'conflicting_duplicate', 'missing_identity'})

    def test_identical_duplicates_collapse(self):
        report = self.compare(*self.pair([], [record(1), record(1)]))
        self.assertEqual(report['outcome'], 'complete')
        self.assertEqual(report['counts']['new'], 1)
        self.assertEqual(report['issues'][0]['code'], 'identical_duplicate')

    def test_id_is_feed_scoped_and_guid_is_not_url(self):
        a, b = self.pair([], [dict(record(1), id='urn:sample:id', link='')])
        for manifest in (a, b):
            obj = json.loads(manifest.read_text())
            obj['feeds'].append(dict(obj['feeds'][0], id='another', label='Other'))
            manifest.write_text(json.dumps(obj))
        report = self.compare(a, b)
        self.assertEqual(report['counts']['new'], 2)
        self.assertIsNone(report['items'][0]['after']['article_url'])

    def test_exact_links_and_ids_are_not_normalized(self):
        old = dict(record(1), id='', link='https://example.org/a?x=1&y=2')
        new = dict(old, link='https://example.org/a?y=2&x=1')
        report = self.compare(*self.pair([old], [new]))
        self.assertEqual(report['counts']['new'], 1)
        self.assertEqual(report['counts']['absent'], 1)
        report = self.compare(*self.pair([dict(record(1), id=' x ')], [dict(record(1), id='x')]))
        self.assertEqual(report['counts']['new'], 1)

    def test_date_only_revision_and_offset_equivalence(self):
        old = record(1, atom=True)
        new = dict(old, published='2026-10-05T07:30:00Z')
        report = self.compare(*self.pair([old], [new], atom=True))
        item = report['items'][0]
        self.assertEqual(item['status'], 'revised')
        self.assertEqual(item['before']['published']['utc'], item['after']['published']['utc'])
        for timestamp in ['2026-10-05T07:30:00+00:60', '2026-10-05T07:30:00+24:00',
                          '2026-10-05T07:30:60Z', '2026-02-30T07:30:00Z']:
            with self.subTest(timestamp=timestamp), self.assertRaises(core.InputError):
                core.instant(timestamp)

    def test_invalid_date_preserved(self):
        report = self.compare(*self.pair([], [dict(record(1), published='tomorrow')]))
        self.assertEqual(report['outcome'], 'incomplete')
        self.assertEqual(report['items'][0]['after']['published'], {'raw': 'tomorrow', 'utc': None})

    def test_atom_xhtml_is_literal(self):
        xml = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id><title>T</title><summary type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>A <b>bold</b> word</p></div></summary></entry></feed>'
        records, issues = core.parse_feed(xml)
        self.assertIn('bold', records[0]['excerpt'])
        self.assertIn('http://www.w3.org/1999/xhtml', records[0]['excerpt'])
        self.assertFalse(issues)

    def test_unsupported_atom_content_is_explicit(self):
        for extra, code in [('src="https://example.org/content"', 'external_content_not_loaded'), ('type="image/png"', 'unsupported_text_type')]:
            records, issues = core.parse_feed(f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id><content {extra}/></entry></feed>'.encode())
            self.assertEqual(issues[0]['code'], code)
            self.assertEqual(records[0]['excerpt'], '')

    def test_xml_rejects_dtd_entities_and_unsupported_formats(self):
        documents = [b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss version="2.0"><channel>&x;</channel></rss>',
                     b'<!DOCTYPE rss SYSTEM "file:///etc/passwd"><rss version="2.0"><channel/></rss>',
                     b'<!DOCTYPE rss [<!ENTITY % x SYSTEM "https://example.org/evil">%x;]><rss version="2.0"><channel/></rss>',
                     '<!DOCTYPE rss><rss version="2.0"><channel/></rss>'.encode('utf-16'),
                     b'<rss version="1.0"/>', b'<feed/>', b'<rdf:RDF xmlns:rdf="urn:rdf"/>', b'<rss>', b'<rss version="2.0"/>',
                     b'<rss version="2.0"><channel/><channel/></rss>']
        for xml in documents:
            with self.subTest(xml=xml), self.assertRaises(core.InputError):
                core.parse_feed(xml)

    def test_xml_limits_and_ambiguous_fields(self):
        xmls = [b'<a>' * 33 + b'</a>' * 33,
                b'<rss version="2.0"><channel>' + b'<item/>' * (core.MAX_ENTRIES + 1) + b'</channel></rss>',
                feed([dict(record(1), excerpt='x' * (core.MAX_EXCERPT + 1))]),
                feed([dict(record(1), title='x' * (core.MAX_FIELD + 1))]),
                b'<rss version="2.0"><channel><item><guid>x</guid><guid>y</guid></item></channel></rss>',
                b'<rss version="2.0"><channel><item><description><b>nested</b></description></item></channel></rss>']
        for xml in xmls:
            with self.subTest(size=len(xml)), self.assertRaises(core.InputError):
                core.parse_feed(xml)
        with patch.object(core, 'MAX_NODES', 3), self.assertRaises(core.InputError):
            core.parse_feed(feed([record(1)]))

    def test_url_policy(self):
        invalid = ['javascript:alert(1)', 'data:text/html,hello', '//example.org/a', '/relative', 'file:///tmp/a',
                   'https://user:pass@example.org/', 'https://example.org:99999/', 'https://example.org\\@evil.test/',
                   'https://example.org/\nhello', 'https://example.org/ a', 'https://example.org/%xx',
                   'https://%65xample.org/', 'https://example..org/', 'https://[broken/', 'https://éxample.org/']
        for url in invalid:
            with self.subTest(url=url):
                self.assertIsNone(core.safe_url(url))
        for url in ['https://example.org/a?x=1&y=2#f', 'http://localhost:8000/', 'https://[::1]/', 'https://xn--bcher-kva.example/a%20b']:
            self.assertEqual(core.safe_url(url), url)

    def test_hostile_html_is_inert(self):
        evil = '<script>window.PWNED=1</script><img src="https://evil.example/pixel">'
        report = self.compare(*self.pair([], [dict(record(1), title=evil, excerpt=evil, link='javascript:alert(1)')]))
        html = render(report)
        self.assertNotIn('<script>window.PWNED', html)
        self.assertNotIn('<img', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Content-Security-Policy', html)
        self.assertIn("connect-src &#x27;none&#x27;", html)

    def test_manifest_and_window_errors(self):
        a, b = self.pair([], [record(1)])
        original = json.loads(b.read_text())
        mutations = [dict(original, version=True), dict(original, feeds=[]), dict(original, observed_at='2026-10-06'),
                     dict(original, feeds=original['feeds'] * 2), dict(original, typo=1),
                     dict(original, feeds=[dict(original['feeds'][0], path='../outside')]),
                     dict(original, feeds=[dict(original['feeds'][0], path='/etc/passwd')]),
                     dict(original, feeds=[dict(original['feeds'][0], id='new-id')])]
        for obj in mutations:
            b.write_text(json.dumps(obj))
            with self.subTest(obj=obj), self.assertRaises(core.InputError):
                self.compare(a, b)
        b.write_text('{"version":1,"version":1}')
        with self.assertRaises(core.InputError):
            self.compare(a, b)
        b.write_text(json.dumps(original))
        for start, end in [(END, START), (END, END), (START, START), ('bad', END)]:
            with self.assertRaises(core.InputError):
                core.compare(a, b, start, end)
        for limit in [0, -1, 201, True]:
            with self.assertRaises(core.InputError):
                self.compare(a, b, max_items=limit)

    def test_byte_total_and_entry_limits(self):
        a, b = self.pair([], [record(1)])
        for name, maximum in [('MAX_MANIFEST_BYTES', 10), ('MAX_FEED_BYTES', 10), ('MAX_TOTAL_BYTES', 10), ('MAX_TOTAL_ENTRIES', 0)]:
            with patch.object(core, name, maximum), self.assertRaises(core.InputError):
                self.compare(a, b)
        with patch('quiet_feed.cli.MAX_REPORT_BYTES', 10), self.assertRaises(core.InputError):
            serialize(self.compare(a, b))
        obj = json.loads(b.read_text())
        obj['feeds'] = [dict(obj['feeds'][0], id=f'feed-{i}') for i in range(21)]
        b.write_text(json.dumps(obj))
        with self.assertRaises(core.InputError):
            self.compare(a, b)

    def test_fifo_and_symlink_escape_rejected(self):
        a, b = self.pair()
        os.mkfifo(self.path / 'fifo')
        with self.assertRaises(core.InputError):
            core.read_bounded(self.path / 'fifo', 100)
        (self.path / 'current.xml').unlink()
        (self.path / 'current.xml').symlink_to('/etc/passwd')
        with self.assertRaises(core.InputError):
            self.compare(a, b)

    def test_output_collision_and_cleanup(self):
        output = self.path / 'report'
        write_bundle(output, {'index.html': b'ok', 'report.json': b'{}'})
        with self.assertRaises(FileExistsError):
            write_bundle(output, {'index.html': b'changed'})
        self.assertEqual((output / 'index.html').read_bytes(), b'ok')
        alias = self.path / 'alias'
        alias.symlink_to(output)
        with self.assertRaises(FileExistsError):
            write_bundle(alias, {})
        for error in [OSError('disk failure'), KeyboardInterrupt(), RuntimeError('unexpected')]:
            failed = self.path / 'failed'
            with patch('quiet_feed.cli.os.fsync', side_effect=error), self.assertRaises(type(error)):
                write_bundle(failed, {'report.json': b'{}'})
            self.assertFalse(failed.exists())

    def test_concurrent_output_reservation(self):
        output = self.path / 'race'
        def attempt(number):
            try:
                write_bundle(output, {'report.json': str(number).encode(), 'index.html': b'finished'})
                return 'won'
            except FileExistsError:
                return 'collision'
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(attempt, range(4)))
        self.assertEqual(outcomes.count('won'), 1)
        self.assertEqual(outcomes.count('collision'), 3)
        self.assertEqual((output / 'index.html').read_bytes(), b'finished')
        self.assertFalse((output / 'INCOMPLETE').exists())

    def test_cli_serialization_failure_cancel_timeout_and_exit_codes(self):
        a, b = self.pair([], [record(1)])
        output = self.path / 'out'
        argv = ['--previous', str(a), '--current', str(b), '--start', START, '--end', END, '--output', str(output)]
        with patch('quiet_feed.cli.serialize', side_effect=ValueError('serialization failed')):
            self.assertEqual(main(argv), 1)
        self.assertFalse(output.exists())
        with patch('quiet_feed.cli.serialize', side_effect=KeyboardInterrupt):
            self.assertEqual(main(argv), 130)
        self.assertFalse(output.exists())
        self.assertEqual(main(argv + ['--timeout', '0.000001']), 1)
        self.assertFalse(output.exists())
        self.assertEqual(main(argv), 0)
        self.assertEqual(main(argv), 1)
        a, b = self.pair([], [dict(record(1), id='', link='', valid_link=False)])
        argv[-1] = str(self.path / 'incomplete')
        self.assertEqual(main(argv), 2)
        self.assertTrue((self.path / 'incomplete/index.html').exists())

    def test_sigterm_cleanup_during_write(self):
        output = self.path / 'signal'
        with deadline(10):
            def terminate(fd):
                os.kill(os.getpid(), signal.SIGTERM)
            with patch('quiet_feed.cli.os.fsync', side_effect=terminate), self.assertRaises(KeyboardInterrupt):
                write_bundle(output, {'report.json': b'{}'})
        self.assertFalse(output.exists())

    def test_empty_valid_snapshots_are_distinct_from_malformed(self):
        report = self.compare(*self.pair())
        self.assertEqual(report['outcome'], 'complete')
        self.assertEqual(report['digest']['shown'], 0)
        (self.path / 'current.xml').write_bytes(b'not XML')
        with self.assertRaises(core.InputError):
            self.compare(self.path / 'previous.json', self.path / 'current.json')


if __name__ == '__main__':
    unittest.main()
