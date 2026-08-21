from __future__ import annotations
import json, time
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
queries=[
    '"President Trump Welcomes"',
    '"President Donald Trump Welcomes"',
    '"President Trump Greets" "White House"',
    '"President Trump Participates in an Arrival Ceremony"',
    '"President Trump and First Lady" welcomes',
    '"President Trump" "Arrival Ceremony"',
    '"Donald Trump" "White House" handshake',
    '"Donald Trump" welcomes "Prime Minister"',
    '"Donald Trump" welcomes president',
]

def get(params):
    for i in range(6):
        r=S.get(API,params=params,timeout=90)
        if r.status_code==429:
            time.sleep(10*(i+1)); continue
        r.raise_for_status(); return r.json()
    raise RuntimeError('rate limit')

all_titles={}
for q in queries:
    cont=None
    while True:
        params={'action':'query','list':'search','srsearch':q,'srnamespace':6,'srlimit':50,'format':'json'}
        if cont: params['sroffset']=cont
        data=get(params)
        for x in data.get('query',{}).get('search',[]):
            all_titles[x['title']]={'search_query':q,'snippet':x.get('snippet',''),'timestamp':x.get('timestamp')}
        c=data.get('continue',{}).get('sroffset')
        if c is None or c>=200: break
        cont=c
        time.sleep(1)

items=[]
titles=list(all_titles)
for start in range(0,len(titles),40):
    batch=titles[start:start+40]
    data=get({'action':'query','prop':'imageinfo|categories','titles':'|'.join(batch),'iiprop':'url|size|mime|mediatype|timestamp','cllimit':'max','format':'json'})
    for p in data.get('query',{}).get('pages',{}).values():
        title=p.get('title')
        ii=(p.get('imageinfo') or [{}])[0]
        cats=[c['title'] for c in p.get('categories',[])]
        rec={'title':title,**all_titles.get(title,{}),'imageinfo':ii,'categories':cats}
        if ii.get('mediatype') in ('VIDEO','AUDIO') or str(ii.get('mime','')).startswith('video/'):
            items.append(rec)
    time.sleep(1)

cat_data=get({'action':'query','list':'search','srsearch':'Trump White House video','srnamespace':14,'srlimit':100,'format':'json'})
categories=[x['title'] for x in cat_data.get('query',{}).get('search',[])]

out=Path('handshake/search_output'); out.mkdir(parents=True,exist_ok=True)
(out/'commons_search_results.json').write_text(json.dumps({'queries':queries,'count':len(items),'items':items,'category_hits':categories},ensure_ascii=False,indent=2),encoding='utf-8')
(out/'titles.txt').write_text('\n'.join(sorted(x['title'] for x in items)),encoding='utf-8')
print('video items',len(items))
for x in sorted(items,key=lambda r:r['title']): print(x['title'])
