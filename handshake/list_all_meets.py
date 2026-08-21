from __future__ import annotations
import json, time
from pathlib import Path
import requests
API='https://commons.wikimedia.org/w/api.php'
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
prefixes=['President Trump Meets with','President Donald Trump Meets with','President Trump Meets With','President Donald Trump Meets With']

def get(params):
    for a in range(8):
        r=S.get(API,params=params,timeout=90)
        if r.status_code==429:
            r.close(); time.sleep(10*(a+1)); continue
        r.raise_for_status(); d=r.json(); r.close(); return d
    raise RuntimeError('rate limit')
rows=[]
for prefix in prefixes:
    cont=None
    while True:
        params={'action':'query','list':'allimages','aiprefix':prefix,'ailimit':'500','aiprop':'url|mime|size|timestamp','format':'json'}
        if cont: params['aicontinue']=cont
        d=get(params)
        for x in d.get('query',{}).get('allimages',[]):
            if str(x.get('mime','')).startswith('video/'):
                rows.append({'prefix':prefix,**x})
        cont=d.get('continue',{}).get('aicontinue')
        if not cont: break
        time.sleep(1)
# deduplicate
seen=set(); outrows=[]
for r in rows:
    if r['name'] not in seen:
        seen.add(r['name']); outrows.append(r)
out=Path('handshake/all_meets_output'); out.mkdir(parents=True,exist_ok=True)
(out/'all_meets.json').write_text(json.dumps(outrows,indent=2,ensure_ascii=False),encoding='utf-8')
(out/'all_meets.txt').write_text('\n'.join(r['name'] for r in outrows),encoding='utf-8')
print('video files',len(outrows))
for r in outrows: print(r['name'])
