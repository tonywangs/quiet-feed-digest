"""Pinned independent reader adapter. Never imports production code."""
from pathlib import Path
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))
import feedparser
# Keep optional machine-installed encoding detectors out of the experiment.
# All selected well-formed bytes are UTF-8; no repair heuristic is being tested.
feedparser.encodings.lazy_chardet_encoding = None


def extract(data, atom):
    parsed = feedparser.parse(data, sanitize_html=False, resolve_relative_uris=False)
    records = []
    for item in parsed.entries:
        ident = item.get('id', '')
        link = item.get('link', '')
        def date(name):
            raw = item.get(name, '')
            value = item.get(name + '_parsed')
            return {'raw': raw, 'utc': datetime(*value[:6],tzinfo=timezone.utc).isoformat().replace('+00:00','Z') if value else None}
        content = item.get('content', [])
        excerpt = item.get('summary', content[0].get('value','') if content else '')
        records.append({'identity':('atom:' if atom else 'rss:')+ident if ident else 'link:'+link if link.startswith(('http://','https://')) else None,
                        'title':item.get('title',''), 'link':link, 'article_url':link if link.startswith(('http://','https://')) else None,
                        'excerpt':excerpt,'published':date('published'),'updated':date('updated')})
    return {'bozo':bool(parsed.get('bozo')), 'version':parsed.get('version'), 'records':records}
