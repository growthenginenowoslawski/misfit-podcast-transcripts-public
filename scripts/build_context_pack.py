#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").strip()


def strip_transcript_access(text: str) -> str:
    return re.sub(r"\n## Transcript Access\n.*", "", text, flags=re.S).strip()


def root_links(text: str) -> str:
    return text.replace("](../episodes/", "](episodes/").replace("](../indexes/", "](indexes/").replace("](../summaries/", "](summaries/")


def short_summary(text: str) -> str:
    match = re.search(r"## Short Summary\n\n(.*?)(?:\n## |\Z)", text, flags=re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def use_topics(text: str) -> list[str]:
    match = re.search(r"## Use This Episode For Questions About\n\n(.*?)(?:\n## |\Z)", text, flags=re.S)
    if not match:
        return []
    return [line.strip()[2:] for line in match.group(1).splitlines() if line.strip().startswith("- ")]


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    manifest = json.loads(read("manifest.json"))
    total_chunks = sum(ep["chunk_count"] for ep in manifest)

    sections = [
        "# Misfit Podcast AI Context Pack",
        "",
        "Copy this whole file into ChatGPT, Claude, Gemini, or another AI chat before asking a question.",
        "This file is intentionally compact: it includes the show-level guidance, topic routing, and every episode summary.",
        "Use the full transcript chunks in the repo only when you need exact wording or timestamp evidence.",
        "",
        "## How The AI Should Answer",
        "",
        "- Answer from this context first.",
        "- If the answer needs exact wording, say which episode/chunk file to inspect in the GitHub repo.",
        "- Mention that transcripts are automatic and may contain errors when quoting or citing timestamps.",
        "- Do not invent speaker identity; speaker labels are not available in this repo.",
        "",
        "## Repository Facts",
        "",
        f"- Episodes covered: {len(manifest)}",
        f"- Transcript chunks available for exact lookup: {total_chunks}",
        f"- Date range: {manifest[-1]['published']} through {manifest[0]['published']}",
        "- Source show: https://open.spotify.com/show/77ZHkfmEtIzTgySTJDUoFn",
        "- RSS source: https://feeds.buzzsprout.com/588502.rss",
        "",
        "## Show-Level Summary",
        "",
        root_links(read("summaries/show-level.md")),
        "",
        "## Question Routing",
        "",
        root_links(read("summaries/question-routing.md")),
        "",
        "## Curated Topic Index",
        "",
        root_links(read("summaries/topic-index.md")),
        "",
        "## Episode Summaries",
        "",
    ]

    for ep in manifest:
        summary = root_links(strip_transcript_access(read(ep["summary_path"])))
        sections.extend(
            [
                f"### {ep['published']} - {ep['title']}",
                "",
                f"- Episode file: `{ep['episode_path']}`",
                f"- Summary file: `{ep['summary_path']}`",
                f"- Transcript chunks: {ep['chunk_count']}",
                "",
                summary,
                "",
            ]
        )

    sections.extend(
        [
            "## Transcript Lookup Instructions",
            "",
            "If a user needs exact wording or timestamps, use `manifest.json` to find the episode path, open that episode's `episode.md`, and then open the relevant chunk file listed in its chunk table.",
            "Each chunk has timestamped transcript lines like `**[12:54]** ...`.",
        ]
    )

    write("AI_CONTEXT_PACK.md", "\n".join(sections))

    lite = [
        "# Misfit Podcast AI Context Lite",
        "",
        "Copy this file into ChatGPT if the full `AI_CONTEXT_PACK.md` is too large.",
        "It contains the show-level themes, routing guidance, and compact episode map.",
        "",
        "## How The AI Should Answer",
        "",
        "- Answer from this context first.",
        "- If the answer needs exact wording, ask the user to open the relevant transcript chunk in the repo.",
        "- Do not invent speaker identity; speaker labels are not available.",
        "",
        "## Show-Level Summary",
        "",
        root_links(read("summaries/show-level.md")),
        "",
        "## Question Routing",
        "",
        root_links(read("summaries/question-routing.md")),
        "",
        "## Compact Episode Map",
        "",
    ]
    for ep in manifest:
        summary_text = read(ep["summary_path"])
        topics = ", ".join(use_topics(summary_text))
        lite.extend(
            [
                f"### {ep['published']} - {ep['title']}",
                "",
                f"- Summary: {short_summary(summary_text)}",
                f"- Use for: {topics}",
                f"- Files: `{ep['summary_path']}`, `{ep['episode_path']}`",
                "",
            ]
        )
    write("AI_CONTEXT_LITE.md", "\n".join(lite))


if __name__ == "__main__":
    main()
