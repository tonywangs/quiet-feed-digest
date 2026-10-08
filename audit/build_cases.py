"""Deterministic local probes derived from pinned upstream regression patterns.

These are separately labeled; they are NOT externally authored fixtures.
Expectations are literal values prescribed before parser corrections.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
A = 'http://www.w3.org/2005/Atom'

def build():
    cases = []
    folder = ROOT / 'derived'
    folder.mkdir(exist_ok=True)
    def add(name, xml, changes=None, codes=(), error=None, atom=True):
        data = xml.encode()
        (folder / (name + '.xml')).write_bytes(data)
        record = dict(identity='atom:urn:test:1' if atom else 'rss:urn:test:1', title='', link='', article_url=None,
                      excerpt='', excerpt_kind='content' if atom else 'description',
                      published={'raw':'','utc':None}, updated={'raw':'','utc':None})
        record.update(changes or {})
        cases.append({'file':name+'.xml','sha256':hashlib.sha256(data).hexdigest(),
                      'expected':{'error':error} if error else {'records':[record], 'issues':[{'entry':1,'code':c} for c in codes]}})
    def atom(body, root='', entry=''):
        return f'<feed xmlns="{A}" {root}><entry {entry}><id>urn:test:1</id>{body}</entry></feed>'
    add('base-inherited',atom('<link href="article"/>', 'xml:base="https://example.org/news/"'),
        {'link':'article','article_url':'https://example.org/news/article'})
    add('base-nested',atom('<link xml:base="../stories/" href="article?x=1&amp;y=2"/>',
        'xml:base="https://example.org/news/"','xml:base="2026/"'),
        {'link':'article?x=1&y=2','article_url':'https://example.org/news/stories/article?x=1&y=2'})
    add('base-overridden',atom('<link xml:base="https://other.example/" href="a"/>','xml:base="https://example.org/"'),
        {'link':'a','article_url':'https://other.example/a'})
    add('base-unresolved',atom('<link href="article"/>'),{'link':'article'}, ['unresolved_relative_link','non_clickable_link'])
    add('base-hostile',atom('<link href="article"/>','xml:base="javascript:alert(1)"'),
        {'link':'article'}, ['unresolved_relative_link','non_clickable_link'])
    add('base-no-identity',f'<feed xmlns="{A}" xml:base="https://example.org/"><entry><link href="a"/></entry></feed>',
        {'identity':None,'link':'a','article_url':'https://example.org/a'},['missing_identity'])
    add('summary-external',atom('<summary>Summary</summary><content src="https://example.org/movie"/>'),
        {'excerpt':'Summary','excerpt_kind':'summary'}, ['external_content_not_loaded'])
    add('summary-binary',atom('<summary>Summary</summary><content type="image/png">AA==</content>'),
        {'excerpt':'Summary','excerpt_kind':'summary'}, ['unsupported_text_type'])
    add('summary-duplicate-content',atom('<summary>Summary</summary><content>A</content><content>B</content>'),error='Repeated singleton field:')
    add('summary-invalid-xhtml',atom('<summary>Summary</summary><content type="xhtml"><bad/></content>'),error='Atom XHTML requires one XHTML div')
    add('summary-oversize-content',atom('<summary>Summary</summary><content>'+'x'*8193+'</content>'),error='Entry field or excerpt length limit exceeded')
    for field,code in [('dc:title','unsupported_rss_extension'),('dc:date','unsupported_rss_extension'),('content:encoded','unsupported_content_encoded')]:
        add('rss-hidden-'+field.replace(':','-'), '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item><guid>urn:test:1</guid><description>Summary</description><'+field+'>Unexamined</'+field+'></item></channel></rss>',
            {'excerpt':'Summary'},[code],atom=False)
    add('unicode-date',atom('<title>日本語 café 🌱</title><published>2026-10-05T09:30:00+02:00</published><updated>2026-10-05T10:00:00Z</updated>'),
        {'title':'日本語 café 🌱','published':{'raw':'2026-10-05T09:30:00+02:00','utc':'2026-10-05T07:30:00Z'},'updated':{'raw':'2026-10-05T10:00:00Z','utc':'2026-10-05T10:00:00Z'}})
    (ROOT/'derived.json').write_text(json.dumps({'origin':'Locally authored transformations of corpus base, content/summary, and RSS extension patterns. Not external fixtures.', 'cases':cases},ensure_ascii=False,indent=2)+'\n')

if __name__ == '__main__':
    build()
