from __future__ import annotations
# Trigger the backup-candidate workflow after it was added to the base branch.
import json, subprocess, time, re, sys
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'backup_output'; VIDEO=OUT/'video'; SHEETS=OUT/'sheets'; TMP=OUT/'tmp'
for p in (OUT,VIDEO,SHEETS,TMP): p.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
FILES=[
 ('nazarbayev_2018-01-16','President Trump Meets with President Nursultan Nazarbayev.webm'),
 ('felipe_2018-06-19','President Trump Meets with Their Majesties King Felipe VI and Queen Letizia of Spain.webm'),
 ('rutte_2018-07-02','President Donald Trump Meets with the Prime Minister of the Netherlands.webm'),
]

def get_info(title):
    for a in range(8):
        r=S.get(API,params={'action':'query','prop':'imageinfo','titles':'File:'+title,'iiprop':'url|size|mime|mediatype|derivatives','format':'json'},timeout=90)
        if r.status_code==429:
            r.close(); time.sleep(10*(a+1)); continue
        r.raise_for_status(); d=r.json(); r.close(); p=next(iter(d['query']['pages'].values()))
        if 'missing' in p or not p.get('imageinfo'): raise RuntimeError('file not found')
        return p['imageinfo'][0]
    raise RuntimeError('rate limit')

def choose(ii):
    opts=[]
    for d in ii.get('derivatives') or []:
        u=d.get('src') or d.get('url'); key=(d.get('transcodekey') or d.get('type') or '').lower()
        if not u: continue
        rank=99
        if '360p' in key: rank=0
        elif '480p' in key: rank=1
        elif '240p' in key: rank=2
        elif '720p' in key: rank=3
        if any(u.split('?',1)[0].endswith(e) for e in ('.webm','.mp4','.ogv')): opts.append((rank,u,key))
    return sorted(opts)[0][1] if opts else ii['url'].split('?',1)[0]

def download(url,path):
    for a in range(8):
        r=S.get(url.split('?',1)[0],stream=True,timeout=600)
        if r.status_code==429:
            r.close(); time.sleep(12*(a+1)); continue
        r.raise_for_status()
        with path.open('wb') as f:
            for c in r.iter_content(1024*1024):
                if c: f.write(c)
        r.close(); return
    raise RuntimeError('download rate limit')

def run(cmd): subprocess.run(cmd,check=True)

def main():
    rows=[]
    for key,title in FILES:
        rec={'key':key,'title':title,'page_url':'https://commons.wikimedia.org/wiki/File:'+title.replace(' ','_')}
        try:
            ii=get_info(title); url=choose(ii); rec['download_url']=url; rec['original_url']=ii.get('url')
            ext=Path(url.split('?',1)[0]).suffix or '.webm'; path=VIDEO/(key+ext); download(url,path)
            p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True); dur=float(p.stdout.strip()); rec['duration']=dur
            length=min(60,dur); pat=TMP/f'{key}_%05d.jpg'; vf=("fps=10,scale=800:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\\:hms}':x=10:y=10:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65")
            run(['ffmpeg','-loglevel','error','-y','-i',str(path),'-t',str(length),'-vf',vf,'-q:v','3',str(pat)])
            run(['ffmpeg','-loglevel','error','-y','-framerate','10','-i',str(pat),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','3',str(SHEETS/f'{key}_%03d.jpg')])
            for f in TMP.glob(f'{key}_*.jpg'): f.unlink()
            path.unlink(); rec['status']='processed'
        except Exception as e:
            rec['status']='error'; rec['error']=str(e); print('ERROR',key,e,file=sys.stderr)
        rows.append(rec); (OUT/'metadata.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8'); time.sleep(3)
if __name__=='__main__': main()
