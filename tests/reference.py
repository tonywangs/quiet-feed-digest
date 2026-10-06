"""Independent quadratic oracle over generated publisher records, not parser output.

The generator marks which links are valid; the oracle never calls production URL,
identity, indexing, parsing or comparison functions. Keep it simple, not fast.
"""


def key(record, atom):
    if record['id'] and record['id'].strip():
        return ('atom:' if atom else 'rss:') + record['id']
    if record['valid_link']:
        return 'link:' + record['link']
    return None


def payload(record):
    return tuple(record[name] for name in ('title', 'link', 'excerpt', 'published', 'updated'))


def compare(old, new, atom):
    identities = sorted(set(key(r, atom) for r in old + new) - {None})
    results = []
    for identity in identities:
        a = [r for r in old if key(r, atom) == identity]
        b = [r for r in new if key(r, atom) == identity]
        if any(len(set(payload(r) for r in group)) > 1 for group in (a, b)):
            continue
        state = 'new' if not a else 'absent' if not b else 'unchanged' if payload(a[0]) == payload(b[0]) else 'revised'
        results.append((identity, state, payload(a[0]) if a else None, payload(b[0]) if b else None))
    return results
