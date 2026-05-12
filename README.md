# Misfit Podcast Transcript Repo

Public, ChatGPT-friendly transcript repository for the last 6 months of **Misfit Podcast** by **Misfit Athletics**.

Source show: https://open.spotify.com/show/77ZHkfmEtIzTgySTJDUoFn

RSS source: https://feeds.buzzsprout.com/588502.rss

## What Is Included

- 27 episodes from 2025-11-18 through 2026-05-05.
- 196 transcript chunks, split into small Markdown files.
- Episode summaries, topic indexes, and a question-routing guide.
- Automatic transcripts generated locally with `mlx-community/whisper-small.en-mlx`.

## How To Use With ChatGPT

Give ChatGPT the GitHub repo link and say:

> Read `START_HERE.md` first. Then use the topic index and episode summaries to answer my question. Only open transcript chunks when you need exact wording or timestamp citations.

Best model-facing files:

- `START_HERE.md`
- `summaries/question-routing.md`
- `summaries/topic-index.md`
- `summaries/show-level.md`
- `manifest.json`

## Important Notes

- Transcripts are automatic and may contain errors.
- Speaker labels are not included in v1.
- Audio files and raw working artifacts are intentionally excluded from the repo.
