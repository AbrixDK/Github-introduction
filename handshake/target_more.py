from __future__ import annotations
import json, subprocess, time, sys
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'more_output'; VIDEO=OUT/'video'; SHEETS=OUT/'sheets'; TMP=OUT/'tmp'
for p in (OUT,VIDEO,SHEETS,TMP): p.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
FILES=[
 ('turnbull_2017-05-04','President Trump Meets with Prime Minister Malcolm Turnbull of Australia.webm'),
 ('macron_2018-04-24','The Arrival Ceremony of the President of France and Mrs. Macron.webm'),
]

def get_info(title):
    for a in range(8):
        r=S.get(API,params={'action':'query','prop':'imageinfo','titles':'File:'+title,'iiprop':'url|size|mime|mediatype|derivatives','format':'json'},timeout=90)
        if r.status_code==429: r.close(); time.sleep(12*(a+1)); continue
        r.raise_for_status(); d=r.json(); r.close(); p=next(iter(d['query']['pages'].values()))
        if 'missing' in p or not p.get('imageinfo'): raise RuntimeError('file not found')
        return p['imageinfo'][0]
    raise RuntimeError('API rate limit')

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
        if any(u.split('?',1)[0].endswith(e) for e in ('.webm','.mp4','.ogv')): opts.append((rank,u))
    return sorted(opts)[0][1] if opts else ii['url'].split('?',1)[0]

def download(url,path):
    last=None
    for a in range(8):
        try:
            r=S.get(url.split('?',1)[0],stream=True,timeout=600)
            if r.status_code==429: r.close(); time.sleep(15*(a+1)); continue
            r.raise_for_status()
            with path.open('wb') as f:
                for c in r.iter_content(1024*1024):
                    if c: f.write(c)
            r.close(); return
        except Exception as e: last=e; time.sleep(8*(a+1))
    raise RuntimeError(last)

def probe(path):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True)
    return float(p.stdout.strip())

def run(cmd): subprocess.run(cmd,check=True)

def extract(path,key,dur):
    if key.startswith('turnbull'):
        start=0; length=dur; fps='1'
    else:
        start=0; length=min(900,dur); fps='1/2'
    pat=TMP/f'{key}_%04d.jpg'
    vf=(f"fps={fps},scale=640:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='%{pts\\:hms}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65")
    run(['ffmpeg','-loglevel','error','-y','-ss',str(start),'-i',str(path),'-t',str(length),'-vf',vf,'-q:v','4',str(pat)])
    run(['ffmpeg','-loglevel','error','-y','-framerate','1','-i',str(pat),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','4',str(SHEETS/f'{key}_%02d.jpg')])
    for f in TMP.glob(f'{key}_*.jpg'): f.unlink()

def main():
    rows=[]
    for key,title in FILES:
        r={'key':key,'title':title,'page_url':'https://commons.wikimedia.org/wiki/File:'+title.replace(' ','_')}
        try:
            ii=get_info(title); u=choose(ii); r['download_url']=u; r['original_url']=ii.get('url')
            ext=Path(u.split('?',1)[0]).suffix or '.webm'; p=VIDEO/f'{key}{ext}'
            download(u,p); dur=probe(p); r['duration']=dur; extract(p,key,dur); p.unlink(); r['status']='processed'
        except Exception as e: r['status']='error'; r['error']=str(e); print('ERROR',key,e,file=sys.stderr)
        rows.append(r); (OUT/'metadata.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8'); time.sleep(5)
    print(json.dumps(rows,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
