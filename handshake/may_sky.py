from __future__ import annotations
import subprocess, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'may_output'; OUT.mkdir(parents=True,exist_ok=True)
VIDEO=OUT/'may.mp4'; FRAMES=OUT/'frames'; FRAMES.mkdir(exist_ok=True); SHEETS=OUT/'sheets'; SHEETS.mkdir(exist_ok=True)
URL='https://news.sky.com/video/may-and-trump-shake-hands-in-front-of-churchill-10745188'

def run(cmd):
    print('+',' '.join(map(str,cmd)),flush=True)
    subprocess.run(cmd,check=True)

def main():
    run(['yt-dlp','--no-playlist','-f','best[height<=720]/best','--merge-output-format','mp4','-o',str(VIDEO),URL])
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(VIDEO)],capture_output=True,text=True,check=True)
    dur=float(p.stdout.strip())
    vf=("fps=10,scale=800:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='%{pts\\:hms}':x=10:y=10:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65")
    run(['ffmpeg','-loglevel','error','-y','-i',str(VIDEO),'-vf',vf,'-q:v','3',str(FRAMES/'%05d.jpg')])
    run(['ffmpeg','-loglevel','error','-y','-framerate','10','-i',str(FRAMES/'%05d.jpg'),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','3',str(SHEETS/'may_%03d.jpg')])
    (OUT/'metadata.json').write_text(json.dumps({'url':URL,'duration':dur},indent=2),encoding='utf-8')
    VIDEO.unlink()
    for f in FRAMES.glob('*.jpg'): f.unlink()
    FRAMES.rmdir()
if __name__=='__main__': main()
