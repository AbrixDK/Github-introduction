from __future__ import annotations

# Screening run: public-domain White House greeting videos.
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SRC = OUT / "source"
PREVIEW = OUT / "preview"
SHEETS = OUT / "sheets"
FRAMES = OUT / "frames_1s"
for directory in (OUT, SRC, PREVIEW, SHEETS, FRAMES):
    directory.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    {"id": "01_kuczynski_2017-02-24", "leader": "Pedro Pablo Kuczynski", "date": "2017-02-24", "title": "President Trump Meets With President Pedro Pablo Kuczynski of Peru.webm"},
    {"id": "02_rasmussen_2017-03-30", "leader": "Lars Lokke Rasmussen", "date": "2017-03-30", "title": "President Trump Meets with Prime Minister Rasmussen.webm"},
    {"id": "03_el_sisi_2017-04-03", "leader": "Abdel Fattah el-Sisi", "date": "2017-04-03", "title": "President Trump Meets With President el-Sisi.webm"},
    {"id": "04_abdullah_2017-04-05", "leader": "King Abdullah II", "date": "2017-04-05", "title": "President Donald Trump Meets with King Abdullah II.webm"},
    {"id": "05_gentiloni_2017-04-20", "leader": "Paolo Gentiloni", "date": "2017-04-20", "title": "President Donald Trump Meets with Prime Minister Paolo Gentiloni.webm"},
    {"id": "06_abbas_2017-05-03", "leader": "Mahmoud Abbas", "date": "2017-05-03", "title": "President Trump Meets with President Abbas.webm"},
    {"id": "07_poroshenko_2017-06-20", "leader": "Petro Poroshenko", "date": "2017-06-20", "title": "President Trump Meets with President Petro Poroshenko of Ukraine.webm"},
    {"id": "08_modi_2017-06-26", "leader": "Narendra Modi", "date": "2017-06-26", "title": "President Trump Meets with Prime Minister Modi, 26 June 2017.webm"},
    {"id": "09_hariri_2017-07-25", "leader": "Saad Hariri", "date": "2017-07-25", "title": "President Trump Meets with Prime Minister Hariri.webm"},
    {"id": "10_varadkar_2018-03-15", "leader": "Leo Varadkar", "date": "2018-03-15", "title": "President Donald Trump Meets with Prime Minister Leo Varadkar.webm"},
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Academic-handshake-observation/1.0 (Aarhus University student project; contact via GitHub repository owner)"})


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def get_with_retry(url: str, *, params: dict[str, str] | None = None, stream: bool = False, timeout: int = 180) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(7):
        try:
            response = SESSION.get(url, params=params, stream=stream, timeout=timeout)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "0") or 0)
                wait = max(retry_after, 12 * (attempt + 1))
                response.close()
                print(f"Wikimedia rate limit; waiting {wait}s before retry {attempt + 2}", flush=True)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt == 6:
                break
            wait = 5 * (attempt + 1)
            print(f"Request failed ({exc}); waiting {wait}s before retry", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Request failed after retries: {last_error}")


def resolve_commons(title: str) -> str:
    response = get_with_retry(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "titles": f"File:{title}",
            "iiprop": "url|size|mime|mediatype",
        },
        timeout=60,
    )
    try:
        pages = response.json().get("query", {}).get("pages", {})
    finally:
        response.close()
    page = next(iter(pages.values()))
    if "missing" in page or not page.get("imageinfo"):
        raise RuntimeError(f"Commons file not found: {title}")
    return page["imageinfo"][0]["url"].split("?", 1)[0]


def download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 100_000:
        return
    response = get_with_retry(url, stream=True, timeout=300)
    try:
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    finally:
        response.close()
    time.sleep(4)


def probe(path: Path) -> dict[str, object]:
    process = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_name", "-of", "json", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(process.stdout)


def make_outputs(source: Path, item_id: str) -> None:
    preview = PREVIEW / f"{item_id}.mp4"
    run([
        "ffmpeg", "-y", "-i", str(source), "-t", "180",
        "-vf", "scale='min(960,iw)':-2,fps=15", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
        "-movflags", "+faststart", str(preview),
    ])

    frame_dir = FRAMES / item_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-i", str(preview), "-t", "180",
        "-vf",
        "fps=1,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='%{pts\\:hms}':x=12:y=12:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.65",
        "-q:v", "3", str(frame_dir / "%04d.jpg"),
    ])
    run([
        "ffmpeg", "-y", "-framerate", "1", "-i", str(frame_dir / "%04d.jpg"),
        "-vf", "scale=384:-2,tile=5x5:padding=4:margin=4",
        "-q:v", "3", str(SHEETS / f"{item_id}_%02d.jpg"),
    ])


def main() -> int:
    records: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for candidate in CANDIDATES:
        item_id = candidate["id"]
        try:
            print(f"Processing {item_id}: {candidate['title']}", flush=True)
            url = resolve_commons(candidate["title"])
            extension = Path(url).suffix or ".webm"
            source = SRC / f"{item_id}{extension}"
            download(url, source)
            metadata = probe(source)
            make_outputs(source, item_id)
            records.append({**candidate, "commons_original_url": url, "probe": metadata})
        except Exception as exc:
            print(f"ERROR {item_id}: {exc}", file=sys.stderr, flush=True)
            errors.append({"id": item_id, "error": str(exc)})
        time.sleep(2)

    (OUT / "metadata.json").write_text(json.dumps({"candidates": records, "errors": errors}, indent=2), encoding="utf-8")
    print(f"Completed: {len(records)} downloads; {len(errors)} errors", flush=True)
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
