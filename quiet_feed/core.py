"""Strict input parsing and versioned identity comparison. No network operations."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from xml.parsers import expat

MAX_FEEDS = 20
MAX_MANIFEST_BYTES = 65536
MAX_FEED_BYTES = 1048576
MAX_TOTAL_BYTES = 16 * 1048576
MAX_ENTRIES = 2000
MAX_TOTAL_ENTRIES = 10000
MAX_EXCERPT = 8192
MAX_FIELD = 2048
MAX_NODES = 50000
MAX_DEPTH = 32
MAX_REPORT_BYTES = 8 * 1048576
MAX_VISIBLE = 200
ATOM = '{http://www.w3.org/2005/Atom}'
XHTML = '{http://www.w3.org/1999/xhtml}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'


class InputError(ValueError):
    pass


def read_bounded(path: Path, limit: int) -> bytes:
    # O_NONBLOCK prevents a FIFO from hanging before we can inspect its type.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise InputError(f'Not a regular file: {path}')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise InputError(f'Input byte limit ({limit}) exceeded: {path}')
    return data


def instant(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)', value
    ):
        raise InputError('Expected an ISO 8601 timestamp with explicit timezone')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise InputError('Invalid timestamp') from exc


def utc(dt: datetime) -> str:
    return dt.isoformat().replace('+00:00', 'Z')


def safe_url(value: str) -> str | None:
    """A deliberately conservative absolute HTTP(S) URL policy, without rewriting."""
    if not value or len(value) > MAX_FIELD or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        return None
    if any(c in value for c in '\\<>"\'`') or re.search(r'%(?![0-9A-Fa-f]{2})', value):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.netloc or not parts.hostname:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        if parts.port is not None and not 1 <= parts.port <= 65535:
            return None
        host = parts.hostname
        if ':' in host:
            ipaddress.IPv6Address(host)
        elif not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host):
            return None
        elif any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-')
                 for label in host.split('.')):
            return None
        return value
    except ValueError:
        return None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def manifest(path: Path) -> dict:
    data = read_bounded(path, MAX_MANIFEST_BYTES)
    try:
        obj = json.loads(data, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InputError(f'Invalid manifest: {path}: {exc}') from exc
    if not isinstance(obj, dict) or set(obj) != {'version', 'observed_at', 'feeds'} or type(obj['version']) is not int or obj['version'] != 1:
        raise InputError('Manifest requires version=1, observed_at, feeds only')
    instant(obj['observed_at'])
    if not isinstance(obj['feeds'], list) or not 1 <= len(obj['feeds']) <= MAX_FEEDS:
        raise InputError(f'Manifest requires 1..{MAX_FEEDS} feeds')
    seen = set()
    for feed in obj['feeds']:
        if not isinstance(feed, dict) or set(feed) != {'id', 'label', 'path'}:
            raise InputError('Each feed requires id, label, path only')
        if any(not isinstance(feed[key], str) or not feed[key] or len(feed[key]) > 256
               or any(ord(c) < 32 for c in feed[key]) for key in feed):
            raise InputError('Invalid feed metadata')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', feed['id']) or feed['id'] in seen:
            raise InputError('Feed IDs must be unique stable ASCII identifiers')
        seen.add(feed['id'])
        rel = Path(feed['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise InputError('Snapshot paths must be relative without ..')
        root = path.resolve().parent
        resolved = (root / rel).resolve()
        if not resolved.is_relative_to(root):
            raise InputError('Snapshot symlink escapes manifest directory')
    return obj


def xml_tree(data: bytes) -> ET.Element:
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate(namespace_separator='}')
    depth = nodes = 0

    def expanded(name):
        return '{' + name if '}' in name else name

    def start(name, attrs):
        nonlocal depth, nodes
        depth += 1
        nodes += 1
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            raise InputError('XML depth or node limit exceeded')
        builder.start(expanded(name), {expanded(k): v for k, v in attrs.items()})

    def end(name):
        nonlocal depth
        builder.end(expanded(name))
        depth -= 1

    def forbidden(*args):
        raise InputError('DTD and entity declarations/references are forbidden')

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = builder.data
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(data, True)
        return builder.close()
    except (expat.ExpatError, LookupError) as exc:
        raise InputError(f'Malformed XML: {exc}') from exc


def single(parent, tag):
    found = parent.findall(tag)
    if len(found) > 1:
        raise InputError(f'Repeated singleton field: {tag}')
    return found[0] if found else None


def literal(node, *, rich=False):
    if node is None:
        return ''
    if len(node) and not rich:
        raise InputError('Nested markup requires Atom XHTML text type')
    if len(node):
        # XML namespaces/prefixes may be reserialized. Text is never paraphrased.
        return (node.text or '') + ''.join(ET.tostring(c, encoding='unicode') for c in node)
    return node.text or ''


def parse_feed(data: bytes) -> tuple[list[dict], list[dict]]:
    root = xml_tree(data)
    if root.tag == 'rss' and root.get('version') == '2.0':
        channel = single(root, 'channel')
        if channel is None:
            raise InputError('RSS 2.0 requires one channel')
        entries, atom = channel.findall('item'), False
    elif root.tag == ATOM + 'feed':
        entries, atom = root.findall(ATOM + 'entry'), True
    else:
        raise InputError('Supported formats: unnamespaced RSS 2.0 and Atom 1.0 only')
    if len(entries) > MAX_ENTRIES:
        raise InputError('Per-feed entry limit exceeded')
    records, issues = [], []
    for index, entry in enumerate(entries):
        def issue(code):
            issues.append({'entry': index + 1, 'code': code})

        def text_field(tag):
            node = single(entry, ATOM + tag if atom else tag)
            if atom and node is not None and tag in ('title', 'summary', 'content'):
                kind = node.get('type', 'text')
                if node.get('src') is not None:
                    issue('external_content_not_loaded')
                    return ''
                if kind not in ('text', 'html', 'xhtml'):
                    issue('unsupported_text_type')
                    return ''
                if kind == 'xhtml':
                    if len(node) != 1 or node[0].tag != XHTML + 'div':
                        raise InputError('Atom XHTML requires one XHTML div')
                    return literal(node, rich=True)
            return literal(node)

        ident = text_field('id' if atom else 'guid')
        title = text_field('title')
        if atom:
            links = [el for el in entry.findall(ATOM + 'link') if el.get('rel', 'alternate') == 'alternate']
            if len(links) > 1:
                issue('multiple_alternate_links')
                link = ''
            else:
                link = links[0].get('href', '') if links else ''
            excerpt = text_field('summary') if single(entry, ATOM + 'summary') is not None else text_field('content')
            excerpt_kind = 'summary' if single(entry, ATOM + 'summary') is not None else 'content'
            published, updated = text_field('published'), text_field('updated')
        else:
            link, excerpt = text_field('link'), text_field('description')
            excerpt_kind = 'description'
            published, updated = text_field('pubDate'), ''
            if not excerpt and entry.find(CONTENT) is not None:
                issue('unsupported_content_encoded')
        if len(excerpt) > MAX_EXCERPT or any(len(v) > MAX_FIELD for v in (ident, title, link, published, updated)):
            raise InputError('Entry field or excerpt length limit exceeded')
        clickable = safe_url(link)
        if link and not clickable:
            issue('non_clickable_link')
        # No normalization, case folding, URL rewriting, or cross-feed merging.
        key = ('atom:' if atom else 'rss:') + ident if ident.strip() else ('link:' + link if clickable else None)
        if key is None:
            issue('missing_identity')
        dates = {}
        for name, raw in [('published', published), ('updated', updated)]:
            normalized = None
            if raw:
                try:
                    dt = instant(raw) if atom else parsedate_to_datetime(raw)
                    if dt.tzinfo is None:
                        raise ValueError('Missing timezone')
                    normalized = utc(dt.astimezone(timezone.utc))
                except (ValueError, TypeError, OverflowError):
                    issue('invalid_' + name)
            dates[name] = {'raw': raw, 'utc': normalized}
        records.append({'identity': key, 'title': title, 'link': link, 'article_url': clickable,
                        'excerpt': excerpt, 'excerpt_kind': excerpt_kind, **dates})
    return records, issues


def index_records(records, side, issues):
    indexed, conflicts = {}, set()
    for item in records:
        key = item['identity']
        if key is None:
            continue
        if key in indexed:
            same = indexed[key] == item
            issues.append({'snapshot': side, 'code': 'identical_duplicate' if same else 'conflicting_duplicate', 'identity': key})
            if not same:
                conflicts.add(key)
        else:
            indexed[key] = item
    return indexed, conflicts


def compare(previous: Path, current: Path, start: str, end: str, max_items: int = 100) -> dict:
    if type(max_items) is not int or not 1 <= max_items <= MAX_VISIBLE:
        raise InputError(f'max_items must be 1..{MAX_VISIBLE}')
    a, b = manifest(previous), manifest(current)
    t0, t1 = instant(start), instant(end)
    if not instant(a['observed_at']) <= t0 < instant(b['observed_at']) <= t1:
        raise InputError('Require previous.observed_at <= start < current.observed_at <= end')
    af, bf = {f['id']: f for f in a['feeds']}, {f['id']: f for f in b['feeds']}
    if af.keys() != bf.keys():
        raise InputError('Both manifests must name exactly the same stable feed IDs')
    total_bytes = total_entries = 0
    sources, changes, issues = [], [], []
    for fid in sorted(af):
        versions, conflicts, provenance = {}, set(), {}
        local_issues = []
        for side, m, p, metadata in [('previous', a, previous, af[fid]), ('current', b, current, bf[fid])]:
            path = p.resolve().parent / metadata['path']
            data = read_bounded(path, MAX_FEED_BYTES)
            total_bytes += len(data)
            if total_bytes > MAX_TOTAL_BYTES:
                raise InputError('Total snapshot byte limit exceeded')
            records, parsed_issues = parse_feed(data)
            total_entries += len(records)
            if total_entries > MAX_TOTAL_ENTRIES:
                raise InputError('Total snapshot entry limit exceeded')
            local_issues.extend({'snapshot': side, **i} for i in parsed_issues)
            versions[side], bad = index_records(records, side, local_issues)
            conflicts |= bad
            provenance[side] = {'path': metadata['path'], 'sha256': hashlib.sha256(data).hexdigest(),
                                'bytes': len(data), 'entries': len(records), 'observed_at': utc(instant(m['observed_at']))}
        issues.extend({'feed_id': fid, **i} for i in local_issues)
        sources.append({'id': fid, 'label': bf[fid]['label'], 'previous_label': af[fid]['label'], **provenance})
        old, new = versions['previous'], versions['current']
        for key in sorted((old.keys() | new.keys()) - conflicts):
            before, after = old.get(key), new.get(key)
            status = 'new' if before is None else 'absent' if after is None else 'unchanged' if before == after else 'revised'
            changes.append({'feed_id': fid, 'identity': key, 'status': status, 'before': before, 'after': after})
    priority = {'new': 0, 'revised': 1, 'absent': 2, 'unchanged': 3}
    changes.sort(key=lambda c: (priority[c['status']], c['feed_id'], c['identity']))
    counts = dict.fromkeys(priority, 0)
    counts.update(Counter(c['status'] for c in changes))
    selected = [c for c in changes if c['status'] in ('new', 'revised')][:max_items]
    # Identical duplicates and blocked article links are warnings; uncertain data is incomplete.
    incomplete = any(i['code'] not in ('identical_duplicate', 'non_clickable_link') for i in issues)
    return {'schema_version': 1, 'identity_version': 1, 'outcome': 'incomplete' if incomplete else 'complete',
            'window': {'start_exclusive': utc(t0), 'end_inclusive': utc(t1)},
            'sources': sources, 'counts': counts, 'issues': issues, 'items': changes,
            'digest': {'max_items': max_items, 'shown': len(selected), 'omitted': len(changes) - len(selected),
                       'omitted_by_status': dict(Counter(c['status'] for c in changes[len(selected):])),
                       'selection': [{'feed_id': c['feed_id'], 'identity': c['identity']} for c in selected]},
            'input_totals': {'bytes': total_bytes, 'entries': total_entries}}
