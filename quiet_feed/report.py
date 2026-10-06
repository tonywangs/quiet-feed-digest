"""All imported strings become escaped text. Only validated article URLs are links."""
import base64
import hashlib
from html import escape
from .core import safe_url

CSS = '''
:root {color-scheme:light; font:17px/1.6 system-ui,sans-serif; color:#203832; background:#f5f3ec}
* {box-sizing:border-box} body {max-width:900px; margin:auto; padding:24px; overflow-wrap:anywhere}
a {color:#135548; text-underline-offset:3px} a:hover {text-decoration-thickness:3px}
:focus-visible {outline:3px solid #ad4900; outline-offset:4px}
h1 {font:700 clamp(2rem,6vw,3.5rem)/1.1 Georgia,serif; margin:.3em 0}
h2,h3 {line-height:1.3} .eyebrow {text-transform:uppercase; letter-spacing:.12em; font-size:.8rem}
.intro {max-width:70ch} .muted {color:#475d55} .notice {border-left:5px solid #ad4900; padding:12px;background:#fff4dd}
.controls {display:flex; gap:16px; flex-wrap:wrap; margin:24px 0; padding:16px; background:#e4e9df}
label {display:flex;flex-direction:column;gap:4px;min-width:0} select {font:inherit;max-width:100%;min-width:0;padding:8px;background:white;color:inherit}
article {padding:24px;margin:20px 0;background:#fffefa;border:1px solid #c9d0c6;border-radius:8px}
article h2 {margin:.4em 0}.badge {font-size:.85rem;font-weight:700}.excerpt {white-space:pre-wrap;overflow-wrap:anywhere; font-family:inherit}
p, h2, h3, dd, li, summary, a {overflow-wrap:anywhere} dl {font-size:.9rem} dt {font-weight:600} dd {margin:0 0 8px}
summary {cursor:pointer;padding:10px 0;font-weight:650} details {border-top:1px solid #ccd2c8;margin-top:16px}
.before {border-left:3px solid #929c8a;padding-left:16px} .skip {position:absolute;left:-10000px}.skip:focus {position:static}
[hidden] {display:none!important} footer {border-top:1px solid #c9d0c6;margin-top:32px;padding-top:16px}
@media(max-width:480px) {body{padding:16px}article{padding:16px}.controls{display:block}label{margin-bottom:12px}}
@media print {.controls,.skip{display:none}article{break-inside:avoid}}
'''
JS = '''
'use strict';
const source = document.getElementById('source');
const status = document.getElementById('status');
const articles = Array.from(document.querySelectorAll('article'));
function filter() {
  let count = 0;
  for (const article of articles) {
    article.hidden = !!((source.value && article.dataset.source !== source.value) ||
      (status.value && article.dataset.status !== status.value));
    if (!article.hidden) count++;
  }
  document.getElementById('visible').textContent = count + ' of ' + articles.length + ' selected items visible';
}
source.addEventListener('change', filter);
status.addEventListener('change', filter);
filter();
'''


def csp_hash(text):
    return base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()


def e(value):
    return escape(str(value), quote=True)


def fields(item):
    url = safe_url(item['link'])
    link = f'<a href="{e(url)}" rel="noreferrer noopener" referrerpolicy="no-referrer">Open publisher article</a>' if url else '<span>No validated HTTP(S) article link</span>'
    dates = ''.join(f'<dt>{name.capitalize()} (publisher)</dt><dd>{e(item[name]["raw"] or "Not supplied")}</dd>' for name in ('published', 'updated'))
    return f'''<p>{link}</p><p class="muted">Publisher-provided excerpt ({e(item['excerpt_kind'])}); markup shown literally.</p>
<div class="excerpt">{e(item['excerpt']) if item['excerpt'] else 'No excerpt supplied.'}</div>
<dl>{dates}<dt>Original link</dt><dd>{e(item['link'] or 'Not supplied')}</dd></dl>'''


def render(report):
    source_map = {s['id']: s for s in report['sources']}
    selected = {(x['feed_id'], x['identity']) for x in report['digest']['selection']}
    cards = []
    for item in report['items']:
        if (item['feed_id'], item['identity']) not in selected:
            continue
        src = source_map[item['feed_id']]
        after = item['after']
        revision = ''
        if item['status'] == 'revised':
            revision = f'''<details><summary>Before revision: {e(item['before']['title'] or '(Untitled)')}</summary>
<div class="before"><h3>Previous snapshot</h3>{fields(item['before'])}</div></details>'''
        cards.append(f'''<article data-source="{e(item['feed_id'])}" data-status="{item['status']}">
<span class="badge">{'Newly observed' if item['status'] == 'new' else 'Revised'} · {e(src['label'])}</span>
<h2>{e(after['title'] or '(Untitled)')}</h2>{fields(after)}{revision}
<details><summary>Identity and snapshot provenance</summary><dl><dt>Feed-scoped identity</dt><dd>{e(item['identity'])}</dd>
<dt>Current snapshot</dt><dd>{e(src['current']['path'])} · {e(src['current']['observed_at'])}</dd>
<dt>Current SHA-256</dt><dd>{src['current']['sha256']}</dd>
<dt>Previous snapshot</dt><dd>{e(src['previous']['path'])} · {e(src['previous']['observed_at'])}</dd>
<dt>Previous SHA-256</dt><dd>{src['previous']['sha256']}</dd></dl></details></article>''')
    options = ''.join(f'<option value="{e(s["id"])}">{e(s["label"])}</option>' for s in report['sources'])
    counts = ' · '.join(f'{n} {status}' for status, n in report['counts'].items())
    issue_counts = {}
    for issue in report['issues']:
        code = issue['code']
        issue_counts[code] = issue_counts.get(code, 0) + 1
    issue_html = '<ul>' + ''.join(f'<li>{e(k)}: {v}</li>' for k, v in sorted(issue_counts.items())) + '</ul>' if issue_counts else '<p>No input issues reported.</p>'
    outcome = '<p class="notice"><strong>Incomplete analysis.</strong> Some entries could not be compared reliably. Review issue counts below and report.json for details.</p>' if report['outcome'] == 'incomplete' else ''
    policy = f"default-src 'none'; script-src 'sha256-{csp_hash(JS)}'; style-src 'sha256-{csp_hash(CSS)}'; img-src 'none'; font-src 'none'; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{e(policy)}">
<meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quiet Feed · Snapshot digest</title><style>{CSS}</style></head><body>
<a class="skip" href="#digest">Skip to digest</a><header><p class="eyebrow">Quiet Feed / a finite reading list</p><h1>Your snapshot digest</h1>
<p class="intro">Newly observed and revised items, in publisher wording. Newly observed does not necessarily mean newly published; absence does not prove deletion.</p>
<p class="muted">Observation window: after {e(report['window']['start_exclusive'])}, through {e(report['window']['end_inclusive'])}.</p>
<p>{e(counts)}</p>{outcome}</header>
<noscript><p>JavaScript is disabled. All selected items remain readable; filters require JavaScript.</p></noscript>
<div class="controls" role="group" aria-label="Filter selected items"><label>Source<select id="source"><option value="">All sources</option>{options}</select></label>
<label>Change<select id="status"><option value="">New and revised</option><option value="new">Newly observed</option><option value="revised">Revised</option></select></label></div>
<p id="visible" role="status" aria-live="polite">{len(cards)} selected items</p>
<main id="digest" tabindex="-1">{''.join(cards) if cards else '<p>No new or revised items were selected. Check the outcome and issue counts before interpreting this result.</p>'}</main>
<footer><h2>End of digest</h2><p>{report['digest']['shown']} selected; {report['digest']['omitted']} comparable items omitted from this HTML report.
Omitted by status: {e(', '.join(f'{k}: {v}' for k,v in sorted(report['digest']['omitted_by_status'].items())) or 'none')}.</p>
<p>Selection is deterministic: new, then revised; within each group, feed ID and exact identity. This order does not rank importance. Filters apply only to selected items. All comparable records, including unchanged and absent, are in report.json.</p>
<h2>Input issues</h2>{issue_html}<p>Missing identities and conflicting duplicates are excluded from comparison counts and listed in JSON. Imported markup is inert literal text. No article, image, or other remote asset has been fetched.</p></footer>
<script>{JS}</script></body></html>
'''
