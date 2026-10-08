"""Build corpus-derived snapshots with explicit, reproducible local mutations."""
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from tests.test_digest import START, END
ROOT=Path(__file__).resolve().parent
A='{http://www.w3.org/2005/Atom}'
EVIL='<script>window.PWNED=1</script><img src="https://evil.invalid/pixel" onerror="window.PWNED=1">'


def upstream(name):
    return ET.fromstring((ROOT/'fixtures'/name).read_bytes())


def build(folder):
    folder.mkdir(parents=True,exist_ok=True)
    rss=upstream('wellformed-rss--item_guid_conflict_link.xml').find('channel/item')
    rss.append(copy.deepcopy(upstream('wellformed-rss--item_title.xml').find('channel/item/title')))
    rss.append(copy.deepcopy(upstream('wellformed-rss--item_description_escaped_markup.xml').find('channel/item/description')))
    atom=upstream('wellformed-atom10--entry_link_no_rel.xml').find(A+'entry')
    atom.append(copy.deepcopy(upstream('wellformed-atom10--entry_title.xml').find(A+'entry/'+A+'title')))
    atom.append(copy.deepcopy(upstream('wellformed-atom10--entry_summary_escaped_markup.xml').find(A+'entry/'+A+'summary')))
    ET.SubElement(atom,A+'id').text='urn:corpus:atom:1'
    rss_new=copy.deepcopy(rss);rss_new.find('description').text += ' Revised locally.'
    rss_added=copy.deepcopy(rss);rss_added.find('guid').text='urn:corpus:rss:2';rss_added.find('title').text='Added corpus-derived item'
    hostile=copy.deepcopy(atom);hostile.find(A+'id').text='urn:corpus:hostile';hostile.find(A+'title').text=EVIL;hostile.find(A+'summary').text=EVIL;hostile.find(A+'link').set('href','javascript:alert(1)')
    relative=copy.deepcopy(atom);relative.find(A+'id').text='urn:corpus:relative';relative.find(A+'link').set('href','story');relative.find(A+'title').text='Relative corpus-derived article'
    for side,rs,ats,date in [('previous',[rss],[atom],START),('current',[rss_new,rss_added],[atom,hostile,relative],END)]:
        rroot=ET.Element('rss',version='2.0');channel=ET.SubElement(rroot,'channel');channel.extend(rs)
        aroot=ET.Element(A+'feed',{'{http://www.w3.org/XML/1998/namespace}base':'https://example.org/corpus/'});aroot.extend(ats)
        for fid,root in [('rss',rroot),('atom',aroot)]:
            (folder/f'{side}-{fid}.xml').write_bytes(ET.tostring(root,encoding='utf-8'))
        (folder/f'{side}.json').write_text(json.dumps({'version':1,'observed_at':date,'feeds':[
            {'id':fid,'label':'Corpus-derived '+fid,'path':f'{side}-{fid}.xml'} for fid in ['rss','atom']]},sort_keys=True)+'\n')
    return folder/'previous.json',folder/'current.json'
