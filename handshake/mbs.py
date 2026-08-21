from __future__ import annotations
# Trigger the Crown Prince workflow after it was added to the base branch.
import json, subprocess, time
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
TITLE='President Trump Meets with Crown Prince Mohammad bin Salman of the Kingdom of Saudi Arabia.webm'
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mbs_output'; VIDEO=OUT/'video'; SHEETS=OUT/'sheets'; TMP=OUT/'tmp'
for p in (OUT,VIDEO,SHEETS,TMP): p.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})

def info():
    for a in range(8):
        r=S.get(API,params={'action':'query','prop':'imageinfo','titles':'File:'+TITLE,'iiprop':'url|size|mime|mediatype|derivatives','format':'json'},timeout=90)
        if r.status_code==429:
            r.close(); time.sleep(12*(a+1)); continue
        r.raise_for_status(); d=r.json(); r.close(); return next(iter(d['query']['pages'].values()))['imageinfo'][0]
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
            r.close(); time.sleep(15*(a+1)); continue
        r.raise_for_status()
        with path.open('wb') as f:
            for c in r.iter_content(1024*1024):
                if c: f.write(c)
        r.close(); return
    raise RuntimeError('download rate limit')

def run(cmd): subprocess.run(cmd,check=True)

def main():
    ii=info(); url=choose(ii); ext=Path(url.split('?',1)[0]).suffix or '.webm'; path=VIDEO/('mbs'+ext); download(url,path)
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True); dur=float(p.stdout.strip())
    pat=TMP/'screen_%04d.jpg'; vf=("fps=1,scale=640:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\\:hms}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65")
    run(['ffmpeg','-loglevel','error','-y','-i',str(path),'-t',str(min(90,dur)),'-vf',vf,'-q:v','4',str(pat)])
    run(['ffmpeg','-loglevel','error','-y','-framerate','1','-i',str(pat),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','4',str(SHEETS/'mbs_screen_%02d.jpg')])
    for f in TMP.glob('screen_*.jpg'): f.unlink()
    pat2=TMP/'fine_%05d.jpg'; vf2=("fps=10,scale=800:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='%{pts\\:hms}':x=10:y=10:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65")
    run(['ffmpeg','-loglevel','error','-y','-i',str(path),'-t',str(min(35,dur)),'-vf',vf2,'-q:v','3',str(pat2)])
    run(['ffmpeg','-loglevel','error','-y','-framerate','10','-i',str(pat2),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','3',str(SHEETS/'mbs_fine_%03d.jpg')])
    for f in TMP.glob('fine_*.jpg'): f.unlink()
    path.unlink(); (OUT/'metadata.json').write_text(json.dumps({'title':TITLE,'page_url':'https://commons.wikimedia.org/wiki/File:'+TITLE.replace(' ','_'),'download_url':url,'original_url':ii.get('url'),'duration':dur},indent=2),encoding='utf-8')
if __name__=='__main__': main()
