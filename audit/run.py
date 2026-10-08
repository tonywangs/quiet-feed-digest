"""Offline frozen-corpus audit; discrepancies are data, oracle regressions fail."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from quiet_feed.core import parse_feed, InputError
from audit.reader import extract


def run(strict=True):
    rows=[]
    for group, manifest, key, folder in [('upstream','corpus.json','fixtures','fixtures'),('derived','derived.json','cases','derived')]:
        for case in json.loads((ROOT/'audit'/manifest).read_text())[key]:
            data=(ROOT/'audit'/folder/case['file']).read_bytes()
            assert hashlib.sha256(data).hexdigest()==case['sha256'], case['file']
            try:
                records,issues=parse_feed(data)
                actual={'records':records,'issues':issues}
            except InputError as e:
                actual={'error':str(e)}
            expected=case['expected']
            match = actual['error'].startswith(expected['error']) if 'error' in actual and 'error' in expected else actual==expected
            other=extract(data, b'2005/Atom' in data)
            diffs=[]
            if 'error' in actual:
                diffs.append({'field':'parse','quiet_feed':actual,'feedparser':{'bozo':other['bozo'],'entries':len(other['records'])},'interpretation':'Strict rejection; permissive recovery is not a specification requirement.'})
            else:
                if len(actual['records'])!=len(other['records']):
                    diffs.append({'field':'entry_count','quiet_feed':len(actual['records']),'feedparser':len(other['records'])})
                for i,(a,b) in enumerate(zip(actual['records'],other['records'])):
                    for field in b:
                        if a[field]!=b[field]:
                            diffs.append({'entry':i+1,'field':field,'quiet_feed':a[field],'feedparser':b[field],
                                'interpretation':interpretation(case['file'],field)})
            rows.append({'group':group,'file':case['file'],'expectation_passed':match,'expected':expected,'actual':actual,'independent_reader':other,'discrepancies':diffs})
    totals={g:{'fixtures':sum(r['group']==g for r in rows),
               'expectation_passes':sum(r['group']==g and r['expectation_passed'] for r in rows),
               'strict_rejections':sum(r['group']==g and 'error' in r['actual'] for r in rows),
               'extracted_without_issues':sum(r['group']==g and r['actual'].get('issues')==[] for r in rows),
               'extracted_with_issues':sum(r['group']==g and bool(r['actual'].get('issues')) for r in rows),
               'fixtures_with_reader_discrepancies':sum(r['group']==g and bool(r['discrepancies']) for r in rows),
               'reader_field_discrepancies':sum(len(r['discrepancies']) for r in rows if r['group']==g),
               'compared_entry_fields':sum(7*min(len(r['actual'].get('records',[])),len(r['independent_reader']['records'])) for r in rows if r['group']==g)} for g in ['upstream','derived']}
    result={'reader':'feedparser 6.0.11; sanitize_html=False; resolve_relative_uris=False (only affects embedded HTML)',
            'comparison':'Entry order; exact identity, title, raw link, article URL, excerpt, raw and UTC published/updated. Excerpt kind is Quiet Feed policy, not a reader field. All mismatches retained.',
            'totals':totals,'cases':rows}
    for group, total in totals.items():
        total['differing_entry_fields'] = sum(d['field'] not in ('parse', 'entry_count') for r in rows if r['group']==group for d in r['discrepancies'])
        total['matching_entry_fields'] = total['compared_entry_fields'] - total['differing_entry_fields']
        total['reader_parse_differences'] = sum(d['field']=='parse' for r in rows if r['group']==group for d in r['discrepancies'])
    if strict:
        failures=[r['file'] for r in rows if not r['expectation_passed']]
        assert not failures, failures
    return result


def interpretation(name,field):
    if field in ('link', 'article_url') and ('entry_id' in name or name.startswith(('summary-', 'rss-hidden-', 'unicode-date'))):
        return 'Reader supplies ID/GUID as a missing link (even URNs in some cases); Quiet Feed preserves absence of an explicit article link.'
    if 'pubDate' in name and field=='updated':
        return 'Pinned reader backward-compatibility alias exposes published as updated; Quiet Feed keeps RSS published separate.'
    if 'dc_' in name or 'dc-' in name: return 'Unsupported Dublin Core field explicitly marks analysis incomplete; reader maps extension.'
    if 'encoded' in name or 'base64' in name or 'binary' in name: return 'Unsupported content explicitly marks analysis incomplete; reader decodes or maps it.'
    if 'application_xml' in name: return 'Quiet Feed preserves the XHTML div and serialized namespaces; reader strips wrapper/prefixes.'
    if 'item_guid' in name: return 'Reader promotes permalink GUID to link; Quiet Feed keeps GUID identity separate. RSS permits this reader behavior, does not require it.'
    if name.startswith('base-'): return 'Raw href and raw absolute-link identity policy retained; only article_url resolves xml:base. Missing safe base remains incomplete.'
    return 'Reader mapping/normalization differs from literal supported-field policy; inspect exact values. Not evidence of specification nonconformance by itself.'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',action='store_true');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=run(not args.baseline);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print(json.dumps(result['totals'],sort_keys=True))
