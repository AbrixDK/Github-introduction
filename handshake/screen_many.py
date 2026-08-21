from __future__ import annotations
# Triggered after the screening workflow was added to the base branch.
import json, subprocess, time, re, sys
from pathlib import Path
import requests

API='https://commons.wikimedia.org/w/api.php'
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'many_output'; VIDEO=OUT/'video'; FRAMES=OUT/'frames'; SHEETS=OUT/'sheets'
for p in (OUT,VIDEO,FRAMES,SHEETS): p.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Aarhus-University-handshake-study/1.0 (academic research; contact repository owner)'})

# Chronological pool of different visiting political leaders. Selection is later based only on visibility and event type.
CANDIDATES=[
 ('2017-01-27','Theresa May','Trump May White House'),
 ('2017-02-10','Shinzo Abe','Trump Abe White House'),
 ('2017-02-13','Justin Trudeau','Trump Trudeau White House'),
 ('2017-02-15','Benjamin Netanyahu','Trump Netanyahu White House'),
 ('2017-03-17','Angela Merkel','Trump Merkel White House'),
 ('2017-03-30','Lars Lokke Rasmussen','Trump Rasmussen White House'),
 ('2017-04-03','Abdel Fattah el-Sisi','Trump el-Sisi White House'),
 ('2017-04-05','King Abdullah II','Trump King Abdullah White House'),
 ('2017-04-20','Paolo Gentiloni','Trump Gentiloni White House'),
 ('2017-05-03','Mahmoud Abbas','Trump Abbas White House'),
 ('2017-05-16','Recep Tayyip Erdogan','Trump Erdogan White House'),
 ('2017-06-19','Juan Carlos Varela','Trump Varela White House'),
 ('2017-06-20','Petro Poroshenko','Trump Poroshenko White House'),
 ('2017-06-26','Narendra Modi','Trump Modi White House'),
 ('2017-06-30','Moon Jae-in','Trump Moon White House'),
 ('2017-07-25','Saad Hariri','Trump Hariri White House'),
 ('2017-08-28','Sauli Niinisto','Trump Niinisto White House'),
 ('2017-09-26','Mariano Rajoy','Trump Rajoy White House'),
 ('2017-10-02','Prayut Chan-o-cha','Trump Prayut White House'),
 ('2017-10-23','Lee Hsien Loong','Trump Lee Singapore White House'),
 ('2018-04-24','Emmanuel Macron','Trump Macron White House arrival'),
 ('2018-04-30','Muhammadu Buhari','Trump Buhari White House'),
 ('2018-07-30','Giuseppe Conte','Trump Conte White House'),
 ('2018-08-27','Uhuru Kenyatta','Trump Kenyatta White House'),
 ('2018-09-18','Andrzej Duda','Trump Duda White House'),
 ('2019-03-07','Andrej Babis','Trump Babis White House'),
 ('2019-04-02','Jens Stoltenberg','Trump Stoltenberg White House'),
 ('2019-05-16','Ueli Maurer','Trump Ueli Maurer White House'),
 ('2019-06-20','Justin Trudeau second','Trump Trudeau June 2019 White House'),
 ('2019-09-20','Scott Morrison','Trump Morrison arrival ceremony White House'),
]

def get(params,timeout=90):
    last=None
    for i in range(8):
        try:
            r=S.get(API,params=params,timeout=timeout)
            if r.status_code==429:
                wait=max(int(r.headers.get('Retry-After','0') or 0),10*(i+1)); r.close(); time.sleep(wait); continue
            r.raise_for_status(); data=r.json(); r.close(); return data
        except Exception as e:
            last=e; time.sleep(5*(i+1))
    raise RuntimeError(last)

def search_video(query):
    data=get({'action':'query','list':'search','srsearch':query,'srnamespace':6,'srlimit':30,'format':'json'})
    hits=data.get('query',{}).get('search',[])
    if not hits: return None,[]
    titles=[h['title'] for h in hits]
    info=get({'action':'query','prop':'imageinfo','titles':'|'.join(titles[:30]),'iiprop':'url|size|mime|mediatype|derivatives','format':'json'})
    candidates=[]
    for p in info.get('query',{}).get('pages',{}).values():
        ii=(p.get('imageinfo') or [{}])[0]
        if ii.get('mediatype')=='VIDEO' or str(ii.get('mime','')).startswith('video/'):
            title=p.get('title','')
            low=title.lower(); score=0
            for token in re.findall(r'[a-z]+',query.lower()):
                if len(token)>3 and token in low: score+=2
            if 'trump' in low: score+=3
            if any(x in low for x in ('meet','welcome','arrival','remarks')): score+=2
            candidates.append((score,title,ii))
    candidates.sort(key=lambda x:(-x[0],x[1]))
    return (candidates[0] if candidates else None),[(s,t) for s,t,_ in candidates]

def choose_url(ii):
    deriv=ii.get('derivatives') or []
    opts=[]
    for d in deriv:
        src=d.get('src') or d.get('url'); key=(d.get('transcodekey') or d.get('type') or '').lower()
        if not src: continue
        score=99
        if '360p' in key: score=0
        elif '480p' in key: score=1
        elif '240p' in key: score=2
        elif '720p' in key: score=3
        if src.endswith(('.webm','.mp4','.ogv')): opts.append((score,len(src),src,key))
    if opts: return sorted(opts)[0][2]
    return ii.get('url')

def download(url,path):
    r=S.get(url,stream=True,timeout=300); r.raise_for_status()
    with path.open('wb') as f:
        for chunk in r.iter_content(1024*1024):
            if chunk: f.write(chunk)
    r.close(); time.sleep(2)

def probe(path):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],capture_output=True,text=True,check=True)
    return float(json.loads(p.stdout)['format']['duration'])

def run(cmd): subprocess.run(cmd,check=True)

def sheets_for(path,item_id,duration):
    # First 120 seconds and last 45 seconds. Full source timestamps are burned in.
    segments=[('head',0,min(duration,120.0))]
    if duration>125: segments.append(('tail',max(0,duration-45),min(45,duration)))
    for label,start,length in segments:
        fd=FRAMES/f'{item_id}_{label}'; fd.mkdir(parents=True,exist_ok=True)
        vf=("fps=1,scale=640:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{start:.1f}+%{{pts\\:hms}}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65")
        run(['ffmpeg','-loglevel','error','-y','-ss',str(start),'-i',str(path),'-t',str(length),'-vf',vf,'-q:v','4',str(fd/'%04d.jpg')])
        run(['ffmpeg','-loglevel','error','-y','-framerate','1','-i',str(fd/'%04d.jpg'),'-vf','scale=320:-2,tile=5x5:padding=4:margin=4','-q:v','4',str(SHEETS/f'{item_id}_{label}_%02d.jpg')])
        for f in fd.glob('*.jpg'): f.unlink()
        fd.rmdir()

def main():
    records=[]
    for n,(date,leader,query) in enumerate(CANDIDATES,1):
        item_id=f'{n:02d}_{date}_{re.sub("[^a-z0-9]+","_",leader.lower()).strip("_")}'
        rec={'number':n,'date':date,'leader':leader,'query':query}
        try:
            hit,alternatives=search_video(query); rec['alternatives']=alternatives
            if not hit: raise RuntimeError('no Commons video result')
            score,title,ii=hit; rec.update({'file_title':title,'search_score':score,'commons_page':'https://commons.wikimedia.org/wiki/'+title.replace(' ','_'),'original_url':ii.get('url')})
            url=choose_url(ii); rec['download_url']=url
            ext=Path(url.split('?',1)[0]).suffix or '.webm'; path=VIDEO/f'{item_id}{ext}'
            download(url,path); duration=probe(path); rec['duration_seconds']=duration
            sheets_for(path,item_id,duration); path.unlink()
            rec['status']='processed'
        except Exception as e:
            rec['status']='error'; rec['error']=str(e)
            print('ERROR',leader,e,file=sys.stderr)
        records.append(rec); (OUT/'metadata.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
        time.sleep(2)
    print('processed',sum(r['status']=='processed' for r in records),'of',len(records))

if __name__=='__main__': main()
