#!/usr/bin/env python3
import csv
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED_URL = "https://feeds.buzzsprout.com/588502.rss"
SPOTIFY_SHOW = "https://open.spotify.com/show/77ZHkfmEtIzTgySTJDUoFn"
CUTOFF = dt.datetime(2025, 11, 12, tzinfo=dt.timezone.utc)
MODEL = "mlx-community/whisper-small.en-mlx"
PROMPT = (
    "Misfit Podcast by Misfit Athletics. Speakers include Drew and Paige. "
    "CrossFit, Open, Quarterfinals, Semifinals, Games, Zone 2, affiliate "
    "programming, gymnastics weaknesses, athlete IQ, competition mindset."
)

PUBLIC_DIRS = ["episodes", "indexes", "summaries"]
WORKING_DIRS = ["working/audio", "working/json", "working/logs"]

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def clean_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def slugify(value: str, max_len: int = 70) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:max_len].strip("-") or "episode"


def episode_number(title: str) -> str:
    m = re.search(r"\bE\.?\s*(\d+(?:\.\d+)?)\b", title, flags=re.I)
    return m.group(1) if m else ""


def parse_duration_seconds(value: str) -> int:
    if not value:
        return 0
    parts = [int(p) for p in value.split(":") if p.isdigit()]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return 0


def ts(seconds: float) -> str:
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def yaml_escape(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def fetch_feed() -> list[dict]:
    xml = subprocess.check_output(["curl", "-L", "-s", FEED_URL])
    root = ET.fromstring(xml)
    episodes = []
    for item in root.find("channel").findall("item"):
        pub = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=dt.timezone.utc)
        if pub < CUTOFF:
            continue
        title = item.findtext("title") or ""
        enc = item.find("enclosure")
        if enc is None or not enc.attrib.get("url"):
            continue
        desc = clean_text(item.findtext("description") or "")
        duration = item.findtext(ITUNES + "duration") or ""
        ep_no = episode_number(title)
        date = pub.date().isoformat()
        slug_prefix = f"e{ep_no.replace('.', '-')}-" if ep_no else ""
        slug = f"{date}-{slug_prefix}{slugify(title)}"
        guid = item.findtext("guid") or hashlib.sha1(title.encode()).hexdigest()[:12]
        episodes.append(
            {
                "title": title,
                "episode_number": ep_no,
                "published": date,
                "published_iso": pub.isoformat(),
                "duration": duration,
                "duration_seconds": parse_duration_seconds(duration),
                "description": desc,
                "audio_url": enc.attrib["url"],
                "audio_length": enc.attrib.get("length", ""),
                "audio_type": enc.attrib.get("type", ""),
                "guid": guid,
                "slug": slug,
                "spotify_show": SPOTIFY_SHOW,
            }
        )
    return sorted(episodes, key=lambda e: e["published_iso"], reverse=True)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def download_audio(ep: dict) -> Path:
    out = ROOT / "working/audio" / f"{ep['slug']}.mp3"
    if out.exists() and out.stat().st_size > 100_000:
        return out
    print(f"download {ep['published']} {ep['title']}")
    subprocess.check_call(["curl", "-L", "--fail", "-s", "-o", str(out), ep["audio_url"]])
    return out


def transcribe(ep: dict, audio: Path) -> Path:
    out = ROOT / "working/json" / f"{ep['slug']}.json"
    if out.exists() and out.stat().st_size > 10_000:
        return out
    print(f"transcribe {ep['published']} {ep['title']}")
    subprocess.check_call(
        [
            "uvx",
            "--from",
            "mlx-whisper",
            "mlx_whisper",
            str(audio),
            "--model",
            MODEL,
            "--language",
            "en",
            "--output-dir",
            str(out.parent),
            "--output-name",
            ep["slug"],
            "--output-format",
            "json",
            "--verbose",
            "False",
            "--condition-on-previous-text",
            "False",
            "--initial-prompt",
            PROMPT,
        ]
    )
    return out


def load_segments(json_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return [s for s in data.get("segments", []) if (s.get("text") or "").strip()]


def chunk_segments(segments: list[dict], max_seconds=600, max_chars=12000) -> list[dict]:
    chunks, cur, cur_chars, start = [], [], 0, None
    for seg in segments:
        text = " ".join((seg.get("text") or "").split())
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", seg_start))
        if start is None:
            start = seg_start
        should_split = cur and ((seg_end - start) >= max_seconds or cur_chars + len(text) > max_chars)
        if should_split:
            chunks.append({"start": cur[0]["start"], "end": cur[-1]["end"], "segments": cur})
            cur, cur_chars, start = [], 0, seg_start
        cur.append({"start": seg_start, "end": seg_end, "text": text})
        cur_chars += len(text) + 1
    if cur:
        chunks.append({"start": cur[0]["start"], "end": cur[-1]["end"], "segments": cur})
    return chunks


TOPIC_PATTERNS = {
    "Open": r"\bopen\b|26\.[123]",
    "Quarterfinals": r"quarterfinal",
    "Semifinals": r"semifinal|semi-final",
    "Games": r"\bgames\b",
    "Affiliate Programming": r"affiliate|phase|programming|rushmore|mad jack|wanjiru|compound",
    "Zone 2": r"zone 2|zone two|aerobic",
    "Accessory Work": r"accessory",
    "Gymnastics": r"gymnastics|muscle-up|pull-up|toes-to-bar|handstand",
    "Competition Mindset": r"mindset|competing|competition|debrief|athlete iq|pressure",
    "Weaknesses": r"weakness|weaknesses",
    "Nutrition": r"nutrition|supplement|gorilla mind",
}


def tag_episode(ep: dict, text: str) -> list[str]:
    hay = f"{ep['title']}\n{ep['description']}\n{text[:20000]}".lower()
    tags = [topic for topic, pattern in TOPIC_PATTERNS.items() if re.search(pattern, hay, flags=re.I)]
    return tags or ["CrossFit Training"]


def extract_summary(ep: dict, text: str, tags: list[str]) -> str:
    desc = ep["description"]
    lead = desc.split("\n\n")[0] if desc else ""
    bullets = []
    for sentence in re.split(r"(?<=[.!?])\s+", desc):
        s = sentence.strip()
        if len(s) > 40 and len(bullets) < 6:
            bullets.append(s)
    if not bullets and lead:
        bullets = [lead]
    return "\n".join(
        [
            f"# Summary - {ep['title']}",
            "",
            "## Short Summary",
            "",
            lead or f"This episode of Misfit Podcast covers {', '.join(tags[:4]).lower()}.",
            "",
            "## Main Points",
            "",
            *[f"- {b}" for b in bullets[:6]],
            "",
            "## Topic Tags",
            "",
            ", ".join(tags),
            "",
            "## Use This Episode For Questions About",
            "",
            *[f"- {tag}" for tag in tags],
            "",
            "## Transcript Access",
            "",
            "Use `episode.md` for the chunk table and open transcript chunks only when exact wording or citations are needed.",
        ]
    )


def write_episode(ep: dict, segments: list[dict]) -> dict:
    text = " ".join(s["text"].strip() for s in segments)
    tags = tag_episode(ep, text)
    chunks = chunk_segments(segments)
    ep_dir = ROOT / "episodes" / ep["slug"]
    chunk_dir = ep_dir / "chunks"
    chunk_paths = []
    for i, chunk in enumerate(chunks, 1):
        name = f"{i:02d}-{ts(chunk['start']).replace(':','-')}.md"
        rel = f"episodes/{ep['slug']}/chunks/{name}"
        chunk_paths.append(rel)
        body = [
            "---",
            f"show: {yaml_escape('Misfit Podcast')}",
            f"episode_title: {yaml_escape(ep['title'])}",
            f"published: {ep['published']}",
            f"episode_number: {yaml_escape(ep['episode_number'])}",
            f"chunk_index: {i}",
            f"chunk_start: {yaml_escape(ts(chunk['start']))}",
            f"chunk_end: {yaml_escape(ts(chunk['end']))}",
            f"topics: {json.dumps(tags, ensure_ascii=False)}",
            "---",
            "",
            f"# {ep['title']} - Chunk {i}",
            "",
            f"Episode: [[../episode|{ep['title']}]]",
            "",
            "## Transcript",
            "",
        ]
        for seg in chunk["segments"]:
            body.append(f"**[{ts(seg['start'])}]** {seg['text']}")
            body.append("")
        write(ROOT / rel, "\n".join(body))
    chunk_table = "\n".join(
        f"| {i+1} | {ts(chunks[i]['start'])} - {ts(chunks[i]['end'])} | [chunk]({Path(chunk_paths[i]).relative_to('episodes/'+ep['slug'])}) |"
        for i in range(len(chunks))
    )
    ep_md = [
        "---",
        f"show: {yaml_escape('Misfit Podcast')}",
        f"publisher: {yaml_escape('Misfit Athletics')}",
        f"episode_title: {yaml_escape(ep['title'])}",
        f"episode_number: {yaml_escape(ep['episode_number'])}",
        f"published: {ep['published']}",
        f"duration: {yaml_escape(ep['duration'])}",
        f"topics: {json.dumps(tags, ensure_ascii=False)}",
        f"source_rss: {yaml_escape(FEED_URL)}",
        f"spotify_show: {yaml_escape(SPOTIFY_SHOW)}",
        "---",
        "",
        f"# {ep['title']}",
        "",
        "## Summary",
        "",
        f"See [summary.md](summary.md).",
        "",
        "## Source Notes",
        "",
        ep["description"] or "No RSS description available.",
        "",
        "## Transcript Chunks",
        "",
        "| # | Time Range | File |",
        "|---|---|---|",
        chunk_table,
        "",
        "## Transcript Quality",
        "",
        f"Automatic transcript generated locally with `{MODEL}`. Speaker labels are not included in v1.",
    ]
    write(ep_dir / "episode.md", "\n".join(ep_md))
    write(ep_dir / "summary.md", extract_summary(ep, text, tags))
    return {
        **ep,
        "topics": tags,
        "episode_path": f"episodes/{ep['slug']}/episode.md",
        "summary_path": f"episodes/{ep['slug']}/summary.md",
        "chunk_paths": chunk_paths,
        "chunk_count": len(chunk_paths),
        "transcript_chars": len(text),
    }


def write_indexes(records: list[dict]):
    manifest_public = [
        {k: r[k] for k in ["title", "episode_number", "published", "duration", "topics", "episode_path", "summary_path", "chunk_paths", "chunk_count", "transcript_chars", "spotify_show"]}
        for r in records
    ]
    write(ROOT / "manifest.json", json.dumps(manifest_public, indent=2, ensure_ascii=False))
    with (ROOT / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["published", "episode_number", "duration", "title", "topics", "episode_path", "summary_path", "chunk_count", "transcript_chars"])
        writer.writeheader()
        for r in records:
            writer.writerow({**{k: r[k] for k in writer.fieldnames if k in r}, "topics": "; ".join(r["topics"])})
    by_date = ["# Episodes By Date", ""]
    for r in records:
        by_date.append(f"- {r['published']} - [{r['title']}]({r['episode_path']})")
    write(ROOT / "indexes/by-date.md", "\n".join(by_date))
    by_episode = ["# Episodes By Number", ""]
    for r in sorted(records, key=lambda x: float(x["episode_number"] or 0), reverse=True):
        num = f"E.{r['episode_number']}" if r["episode_number"] else "No episode number"
        by_episode.append(f"- {num} - {r['published']} - [{r['title']}]({r['episode_path']})")
    write(ROOT / "indexes/by-episode.md", "\n".join(by_episode))
    topic_map: dict[str, list[dict]] = {}
    for r in records:
        for topic in r["topics"]:
            topic_map.setdefault(topic, []).append(r)
    topic_lines = ["# Topic Index", "", "Use this file first when asking ChatGPT questions. Open the summaries listed under the topic, then transcript chunks only for exact citations.", ""]
    for topic in sorted(topic_map):
        topic_lines.extend([f"## {topic}", ""])
        for r in topic_map[topic]:
            topic_lines.append(f"- {r['published']} - [{r['title']}]({r['summary_path']})")
        topic_lines.append("")
    write(ROOT / "indexes/by-topic.md", "\n".join(topic_lines))
    routing = [
        "# Question Routing Guide",
        "",
        "Start here after `START_HERE.md`. Match the user's question to a topic, read the listed summaries, then inspect transcript chunks only when exact wording is needed.",
        "",
    ]
    for topic in sorted(topic_map):
        routing.append(f"- If the question is about **{topic}**, start with `indexes/by-topic.md#{slugify(topic)}` and the episode summaries listed there.")
    write(ROOT / "summaries/question-routing.md", "\n".join(routing))
    show_summary = [
        "# Show-Level Summary",
        "",
        "This repository covers the last 6 months of Misfit Podcast episodes from Misfit Athletics. The material centers on competitive CrossFit training, programming phases, Open and Quarterfinals preparation, athlete IQ, competition execution, affiliate programming, Zone 2, weaknesses, and mindset.",
        "",
        "## Recurring Themes",
        "",
        "- Competitive CrossFit progress depends on training, testing, and competing with different intent.",
        "- Programming phases are used to organize the year and direct athletes toward specific adaptations.",
        "- Athlete IQ, pacing, debriefing, and movement choices matter alongside raw fitness.",
        "- Community and affiliate context are treated as part of the training ecosystem, not a distraction from performance.",
        "- Weakness work, Zone 2, gymnastics, and accessories appear as tools to support long-term competitive development.",
        "",
        "## Best Entry Points",
        "",
        "- `indexes/by-topic.md` for topic-based questions.",
        "- `summaries/question-routing.md` for deciding what to read.",
        "- `manifest.json` for machine-readable episode and chunk paths.",
    ]
    write(ROOT / "summaries/show-level.md", "\n".join(show_summary))
    topic_summary = ["# Key Themes", ""]
    for topic in sorted(topic_map):
        topic_summary.append(f"- **{topic}**: appears in {len(topic_map[topic])} episode(s).")
    write(ROOT / "indexes/key-themes.md", "\n".join(topic_summary))


def write_root_docs(records: list[dict]):
    total_chunks = sum(r["chunk_count"] for r in records)
    readme = f"""# Misfit Podcast Transcript Repo

Public, ChatGPT-friendly transcript repository for the last 6 months of **Misfit Podcast** by **Misfit Athletics**.

Source show: {SPOTIFY_SHOW}

RSS source: {FEED_URL}

## What Is Included

- {len(records)} episodes from {records[-1]['published']} through {records[0]['published']}.
- {total_chunks} transcript chunks, split into small Markdown files.
- Episode summaries, topic indexes, and a question-routing guide.
- Automatic transcripts generated locally with `{MODEL}`.

## How To Use With ChatGPT

Give ChatGPT the GitHub repo link and say:

> Read `START_HERE.md` first. Then use the topic index and episode summaries to answer my question. Only open transcript chunks when you need exact wording or timestamp citations.

## Important Notes

- Transcripts are automatic and may contain errors.
- Speaker labels are not included in v1.
- Audio files and raw working artifacts are intentionally excluded from the repo.
"""
    write(ROOT / "README.md", readme)
    start = """# START HERE For ChatGPT

You are reading a public repo of Misfit Podcast transcripts and summaries.

## Read Order

1. Use `manifest.json` for the complete episode list and file paths.
2. Use `indexes/by-topic.md` to find relevant episodes.
3. Read episode `summary.md` files before transcript chunks.
4. Open transcript chunks only for exact wording or timestamp evidence.

## Answering Rules

- Prefer concise answers grounded in the repo.
- Cite file paths and timestamps when using transcript chunks.
- State when a transcript is automatic and may contain errors.
- Do not assume speaker identity unless the transcript text makes it clear.
"""
    write(ROOT / "START_HERE.md", start)
    usage = """# ChatGPT Usage Examples

## General Question

Read `START_HERE.md`, then answer: What does Misfit say about building athlete IQ?

## Topic Question

Use `indexes/by-topic.md` and answer: How do they think about Zone 2 for CrossFit athletes?

## Citation Question

Find transcript chunks relevant to competition mindset and cite timestamps.
"""
    write(ROOT / "CHATGPT_USAGE.md", usage)


def main():
    for d in PUBLIC_DIRS + WORKING_DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    episodes = fetch_feed()
    print(f"episodes={len(episodes)} cutoff={CUTOFF.date()}")
    records = []
    for ep in episodes:
        audio = download_audio(ep)
        json_path = transcribe(ep, audio)
        records.append(write_episode(ep, load_segments(json_path)))
    write_indexes(records)
    write_root_docs(records)
    print(f"done episodes={len(records)} chunks={sum(r['chunk_count'] for r in records)}")


if __name__ == "__main__":
    main()

