#!/usr/bin/env python3
"""Regenerate synthetic, non-news example snapshots."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1] / 'examples'


def rss(items):
    return '<rss version="2.0"><channel><title>Sample workshop</title><link>https://example.org/</link><description>Synthetic examples</description>' + ''.join(
        '<item>' + ''.join(f'<{tag}>{escape(value)}</{tag}>' for tag, value in item.items()) + '</item>' for item in items
    ) + '</channel></rss>\n'


def main():
    ROOT.mkdir(exist_ok=True)
    old = [
        {'guid': 'bench-1', 'title': 'Workshop opening hours', 'link': 'https://example.org/workshop', 'description': 'The workshop opens at 09:00.', 'pubDate': 'Mon, 05 Oct 2026 09:00:00 +0000'},
        {'guid': 'bench-2', 'title': 'A stable note', 'link': 'https://example.org/note', 'description': 'This wording has not changed.'},
        {'guid': 'bench-3', 'title': 'A note no longer in the snapshot', 'description': 'Absence is not proof of deletion.'},
    ]
    new = [dict(old[0], description='The workshop opens at 10:00. Bring your own notebook.'), old[1],
           {'guid': 'bench-4', 'title': 'A small repair café', 'link': 'https://example.org/cafe', 'description': 'A fictional café for repairing small things. No registration is needed.'}]
    (ROOT / 'workshop-before.xml').write_text(rss(old))
    (ROOT / 'workshop-after.xml').write_text(rss(new))
    atom_start = '<feed xmlns="http://www.w3.org/2005/Atom"><id>urn:sample:field-notes</id><title>Sample field notes</title><updated>2026-10-06T09:00:00Z</updated>'
    entry = '<entry><id>urn:sample:fern</id><title>A fern by the window 🌿</title><link href="https://example.net/fern"/><summary type="html">&lt;p&gt;A sample observation, preserved verbatim.&lt;/p&gt;</summary><updated>2026-10-06T11:00:00+02:00</updated></entry>'
    (ROOT / 'notes-before.xml').write_text(atom_start + '</feed>\n')
    (ROOT / 'notes-after.xml').write_text(atom_start + entry + '</feed>\n')
    for side, day, suffix in [('previous', '05', 'before'), ('current', '06', 'after')]:
        manifest = {'version': 1, 'observed_at': f'2026-10-{day}T12:00:00Z', 'feeds': [
            {'id': 'workshop', 'label': 'Sample workshop', 'path': f'workshop-{suffix}.xml'},
            {'id': 'notes', 'label': 'Sample field notes', 'path': f'notes-{suffix}.xml'}]}
        (ROOT / f'{side}.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
