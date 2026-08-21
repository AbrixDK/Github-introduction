from __future__ import annotations
# Trigger title search after workflow was added to base branch.
import json, time
from pathlib import Path
import requests
API='https://commons.wikimedia.org/w/api.php'
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
queries=['Trump Moon White House','Trump Theresa May White House','Trump Niinisto White House','Trump Lee Hsien Loong White House','Trump Erdogan White House','Trump Varela White House','Trump Rajoy White House','Trump Prayut White House','Trump Buhari White House','Trump Kenyatta White House','Trump Duda White House','Trump Babis White House','Trump Ueli Maurer White House','Trump Scott Morrison White House','Trump Moon Jae-in Oval Office','Trump Prime Minister May Oval Office']

def get(params):
    for i in range(8):
        r=S.get(API,params=params,timeout=90)
        if r.status_code==429: r.close(); time.sleep(10*(i+1)); continue
        r.raise_for_status(); d=r.json(); r.close(); return d
    raise RuntimeError('rate limit')
rows=[]
for q in queries:
    d=get({'action':'query','list':'search','srsearch':q,'srnamespace':6,'srlimit':50,'format':'json'})
    hits=d.get('query',{}).get('search',[]); titles=[h['title'] for h in hits]
    vids=[]
    for start in range(0,len(titles),40):
        info=get({'action':'query','prop':'imageinfo','titles':'|'.join(titles[start:start+40]),'iiprop':'mime|mediatype|url|size','format':'json'})
        for p in info.get('query',{}).get('pages',{}).values():
            ii=(p.get('imageinfo') or [{}])[0]
            if ii.get('mediatype')=='VIDEO' or str(ii.get('mime','')).startswith('video/'):
                vids.append({'title':p.get('title'),'url':ii.get('url'),'size':ii.get('size')})
    rows.append({'query':q,'videos':vids}); time.sleep(1)
out=Path('handshake/title_output'); out.mkdir(parents=True,exist_ok=True)
(out/'target_titles.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
for row in rows:
    print('\nQUERY',row['query'])
    for v in row['videos']: print(v['title'])
