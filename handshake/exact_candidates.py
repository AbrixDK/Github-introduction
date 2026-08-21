from __future__ import annotations
import json, re, subprocess, time, sys
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'exact_output'; VIDEOS=OUT/'videos'; SHEETS=OUT/'sheets'; TMP=OUT/'tmp'
for p in (OUT,VIDEOS,SHEETS,TMP): p.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
FILES=[
 ('abe_2017-02-10','President Trump and Prime Minister Shinzō Abe.webm'),
 ('trudeau_2017-02-13','President Trump and Prime Minister Trudeau.webm'),
 ('macron_2018-04-24','The Arrival Ceremony of the President of France and Mrs. Macron.webm'),
 ('stoltenberg_2019-04-02','President Trump Meets with the Secretary General of the North Atlantic Treaty Organization.webm'),
]

def api(title):
    for attempt in range(8):
        r=S.get(API,params={'action':'query','prop':'imageinfo','titles':'File:'+title,'iiprop':'url|size|mime|mediatype|derivatives','format':'json'},timeout=90)
        if r.status_code==429:
            r.close(); time.sleep(12*(attempt+1)); continue
        r.raise_for_status(); data=r.json(); r.close(); return next(iter(data['query']['pages'].values()))['imageinfo'][0]
    raise RuntimeError('API rate limit')

def choose(ii):
    opts=[]
    for d in ii.get('derivatives') or []:
        u=d.get('src') or d.get('url'); key=(d.get('transcodekey') or d.get('type') or '').lower()
        if not u: continue
        s=20
        if '360p' in key: s=0
        elif '480p' in key: s=1
        elif '240p' in key: s=2
        elif '720p' in key: s=3
        if any(u.split('?',1)[0].endswith(x) for x in ('.webm','.mp4','.ogv')): opts.append((s,u,key))
    return sorted(opts)[0][1] if opts else ii['url'].split('?',1)[0]

def download(url,path):
    last=None
    for attempt in range(8):
        try:
            r=S.get(url.split('?',1)[0],stream=True,timeout=300)
            if r.status_code==429:
                r.close(); time.sleep(15*(attempt+1)); continue
            r.raise_for_status()
            with path.open('wb') as f:
                for c in r.iter_content(1024*1024):
                    if c: f.write(c)
            r.close(); return
        except Exception as e:
            last=e; time.sleep(8*(attempt+1))
    raise RuntimeError(last)

def probe(path):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True)
    return float(p.stdout.strip())

def run(cmd): subprocess.run(cmd,check=True)

def extract(path,key,dur):
    segments=[('head',0,min(120,dur))]
    if dur>130: segments.append(('tail',max(0,dur-60),min(60,dur)))
    for label,start,length in segments:
        pat=TMP/f'{key}_{label}_%04d.jpg'
        vf=("fps=1,scale=640:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{start:.1f}+%{{pts\\:hms}}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65")
        run(['ffmpeg','-loglevel','error','-y','-ss',str(start),'-i',str(path),'-t',str(length),'-vf',vf,'-q:v','4',str(pat)])
        run(['ffmpeg','-loglevel','error','-y','-framerate','1','-i',str(pat),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','4',str(SHEETS/f'{key}_{label}_%02d.jpg')])
        for f in TMP.glob(f'{key}_{label}_*.jpg'): f.unlink()

def main():
    out=[]
    for key,title in FILES:
        rec={'key':key,'title':title,'page_url':'https://commons.wikimedia.org/wiki/File:'+title.replace(' ','_')}
        try:
            ii=api(title); url=choose(ii); rec['download_url']=url; rec['original_url']=ii.get('url')
            ext=Path(url.split('?',1)[0]).suffix or '.webm'; path=VIDEOS/f'{key}{ext}'
            download(url,path); dur=probe(path); rec['duration']=dur; extract(path,key,dur); path.unlink(); rec['status']='processed'
        except Exception as e:
            rec['status']='error'; rec['error']=str(e); print('ERROR',key,e,file=sys.stderr)
        out.append(rec); (OUT/'metadata.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
        time.sleep(4)
    print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
