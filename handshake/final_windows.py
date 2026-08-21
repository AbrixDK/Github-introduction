from __future__ import annotations
# Trigger the final-window workflow after it was added to the base branch.
import json, subprocess, time, sys
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'final_windows_output'; VIDEO=OUT/'video'; SHEETS=OUT/'sheets'; TMP=OUT/'tmp'
for p in (OUT,VIDEO,SHEETS,TMP): p.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})
FILES=[
 {'key':'merkel_2018-04-27','title':'President Trump Meets with Chancellor Merkel of Germany.webm','segments':[(0,30,10)]},
 {'key':'stoltenberg_2019-04-02','title':'President Trump Meets with the Secretary General of the North Atlantic Treaty Organization.webm','segments':[(0,45,10)]},
 {'key':'solberg_2018-01-10','title':'President Donald Trump Meets with Prime Minister Erna Solberg.webm','segments':[(35,72,5)]},
 {'key':'felipe_2018-06-19','title':'President Trump Meets with Their Majesties King Felipe VI and Queen Letizia of Spain.webm','segments':[(55,34,5)]},
 {'key':'rutte_2018-07-02','title':'President Donald Trump Meets with the Prime Minister of the Netherlands.webm','segments':[(55,70,5)]},
 {'key':'may_expanded','title':'President Donald J. Trump Participates in an Expanded Meeting with Prime Minister Theresa May.webm','segments':[(0,120,2)]},
 {'key':'mbs_2018-03-20','title':'President Trump Meets with Crown Prince Mohammad bin Salman of the Kingdom of Saudi Arabia.webm','segments':[(90,35,5)]},
]

def get_info(title):
    for a in range(10):
        r=S.get(API,params={'action':'query','prop':'imageinfo','titles':'File:'+title,'iiprop':'url|size|mime|mediatype|derivatives','format':'json'},timeout=90)
        if r.status_code==429:
            r.close(); time.sleep(12*(a+1)); continue
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
        if any(u.split('?',1)[0].endswith(e) for e in ('.webm','.mp4','.ogv')): opts.append((rank,u,key))
    return sorted(opts)[0][1] if opts else ii['url'].split('?',1)[0]

def download(url,path):
    last=None
    for a in range(10):
        try:
            r=S.get(url.split('?',1)[0],stream=True,timeout=600)
            if r.status_code==429:
                r.close(); time.sleep(15*(a+1)); continue
            r.raise_for_status()
            with path.open('wb') as f:
                for c in r.iter_content(1024*1024):
                    if c: f.write(c)
            r.close(); return
        except Exception as e:
            last=e; time.sleep(8*(a+1))
    raise RuntimeError(last)

def run(cmd): subprocess.run(cmd,check=True)

def main():
    rows=[]
    for rec0 in FILES:
        rec={k:v for k,v in rec0.items() if k!='segments'}
        title=rec0['title']; key=rec0['key']; rec['page_url']='https://commons.wikimedia.org/wiki/File:'+title.replace(' ','_')
        try:
            ii=get_info(title); url=choose(ii); rec['download_url']=url; rec['original_url']=ii.get('url')
            ext=Path(url.split('?',1)[0]).suffix or '.webm'; path=VIDEO/(key+ext); download(url,path)
            p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True); rec['duration']=float(p.stdout.strip())
            for n,(start,length,fps) in enumerate(rec0['segments'],1):
                pat=TMP/f'{key}_{n}_%05d.jpg'
                vf=(f"fps={fps},scale=800:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"text='{start:.1f}+%{{pts\\:hms}}':x=10:y=10:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65")
                run(['ffmpeg','-loglevel','error','-y','-ss',str(start),'-i',str(path),'-t',str(length),'-vf',vf,'-q:v','3',str(pat)])
                run(['ffmpeg','-loglevel','error','-y','-framerate',str(fps),'-i',str(pat),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','3',str(SHEETS/f'{key}_{n}_%03d.jpg')])
                for f in TMP.glob(f'{key}_{n}_*.jpg'): f.unlink()
            path.unlink(); rec['status']='processed'
        except Exception as e:
            rec['status']='error'; rec['error']=str(e); print('ERROR',key,e,file=sys.stderr)
        rows.append(rec); (OUT/'metadata.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8'); time.sleep(4)
    print(json.dumps(rows,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
