from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SRC = OUT / "source"
SHEETS = OUT / "sheets"
FRAMES = OUT / "frames"
for directory in (OUT, SRC, SHEETS, FRAMES):
    directory.mkdir(parents=True, exist_ok=True)

# Fine windows cover the visible handshake sequences found in the initial 1-fps screening.
FINE = [
    {"id":"02_rasmussen","title":"President Trump Meets with Prime Minister Rasmussen.webm","start":8.0,"duration":10.0},
    {"id":"04_abdullah","title":"President Donald Trump Meets with King Abdullah II.webm","start":22.0,"duration":9.0},
    {"id":"05_gentiloni","title":"President Donald Trump Meets with Prime Minister Paolo Gentiloni.webm","start":6.0,"duration":11.0},
    {"id":"06_abbas","title":"President Trump Meets with President Abbas.webm","start":19.0,"duration":9.0},
    {"id":"07_poroshenko","title":"President Trump Meets with President Petro Poroshenko of Ukraine.webm","start":21.0,"duration":10.0},
]

# Tail windows test whether two longer recordings contain a later handshake.
TAIL = [
    {"id":"03_el_sisi_tail","title":"President Trump Meets With President el-Sisi.webm","start":175.0,"duration":127.0},
    {"id":"10_varadkar_tail","title":"President Donald Trump Meets with Prime Minister Leo Varadkar.webm","start":175.0,"duration":46.0},
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent":"Academic-handshake-observation/1.0 (Aarhus University student project)"})


def run(cmd:list[str])->None:
    print('+',' '.join(cmd),flush=True)
    subprocess.run(cmd,check=True)


def get(url:str,*,params:dict[str,str]|None=None,stream:bool=False,timeout:int=300)->requests.Response:
    last=None
    for attempt in range(7):
        try:
            r=SESSION.get(url,params=params,stream=stream,timeout=timeout)
            if r.status_code==429:
                wait=max(int(r.headers.get('Retry-After','0') or 0),12*(attempt+1))
                r.close(); time.sleep(wait); continue
            r.raise_for_status(); return r
        except Exception as exc:
            last=exc
            if attempt==6: break
            time.sleep(5*(attempt+1))
    raise RuntimeError(last)


def resolve(title:str)->str:
    r=get('https://commons.wikimedia.org/w/api.php',params={
        'action':'query','format':'json','prop':'imageinfo','titles':f'File:{title}','iiprop':'url'
    },timeout=60)
    try: page=next(iter(r.json()['query']['pages'].values()))
    finally: r.close()
    if not page.get('imageinfo'): raise RuntimeError(f'File not found: {title}')
    return page['imageinfo'][0]['url'].split('?',1)[0]


def download(title:str,item_id:str)->Path:
    url=resolve(title)
    ext=Path(url).suffix or '.webm'
    path=SRC/f'{item_id}{ext}'
    r=get(url,stream=True)
    try:
        with path.open('wb') as f:
            for chunk in r.iter_content(1024*1024):
                if chunk: f.write(chunk)
    finally: r.close()
    time.sleep(3)
    return path


def extract_fine(item:dict[str,object],source:Path)->None:
    frame_dir=FRAMES/item['id']; frame_dir.mkdir(parents=True,exist_ok=True)
    start=float(item['start']); dur=float(item['duration'])
    # Ten frames per second. Timestamp shows absolute source time to 0.1 s.
    vf=("fps=10,scale=480:-2,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='%{{eif\\:({start}+t)*10\\:d}}':x=8:y=8:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.7")
    run(['ffmpeg','-y','-ss',str(start),'-i',str(source),'-t',str(dur),'-vf',vf,'-q:v','3',str(frame_dir/'%04d.jpg')])
    # 20 images per sheet = two seconds; read left-to-right, top-to-bottom.
    run(['ffmpeg','-y','-framerate','10','-i',str(frame_dir/'%04d.jpg'),'-vf','tile=5x4:padding=3:margin=3','-q:v','3',str(SHEETS/f"{item['id']}_%02d.jpg")])


def extract_tail(item:dict[str,object],source:Path)->None:
    frame_dir=FRAMES/item['id']; frame_dir.mkdir(parents=True,exist_ok=True)
    start=float(item['start']); dur=float(item['duration'])
    vf=("fps=2,scale=400:-2,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='%{{eif\\:({start}+t)*2\\:d}}':x=8:y=8:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.7")
    run(['ffmpeg','-y','-ss',str(start),'-i',str(source),'-t',str(dur),'-vf',vf,'-q:v','3',str(frame_dir/'%04d.jpg')])
    run(['ffmpeg','-y','-framerate','2','-i',str(frame_dir/'%04d.jpg'),'-vf','tile=5x5:padding=3:margin=3','-q:v','3',str(SHEETS/f"{item['id']}_%02d.jpg")])


def main()->int:
    results=[]; errors=[]
    for item in FINE+TAIL:
        try:
            source=download(str(item['title']),str(item['id']))
            if item in FINE: extract_fine(item,source)
            else: extract_tail(item,source)
            results.append(item)
        except Exception as exc:
            print(f"ERROR {item['id']}: {exc}",file=sys.stderr)
            errors.append({'id':item['id'],'error':str(exc)})
    (OUT/'metadata.json').write_text(json.dumps({'completed':results,'errors':errors},indent=2),encoding='utf-8')
    return 0 if results else 1


if __name__=='__main__':
    raise SystemExit(main())
