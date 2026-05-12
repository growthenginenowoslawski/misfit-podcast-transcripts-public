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

Most AI chats do not reliably read a whole GitHub repo from a link. For normal users, use this path:

1. Open `ASK_CHATGPT.md`.
2. Open `AI_CONTEXT_PACK.md`.
3. Copy all of `AI_CONTEXT_PACK.md` into ChatGPT.
4. Ask your question underneath it.

That gives ChatGPT the summaries, topic routing, and episode map in one paste.
If the chat window says the file is too long, use `AI_CONTEXT_LITE.md` instead.

If your AI tool can browse GitHub directly, give ChatGPT the GitHub repo link and say:

> Read `START_HERE.md` first. Then use the topic index and episode summaries to answer my question. Only open transcript chunks when you need exact wording or timestamp citations.

Best model-facing files:

- `ASK_CHATGPT.md`
- `AI_CONTEXT_PACK.md`
- `AI_CONTEXT_LITE.md`
- `START_HERE.md`
- `summaries/question-routing.md`
- `summaries/topic-index.md`
- `summaries/show-level.md`
- `manifest.json`

## Important Notes

- Transcripts are automatic and may contain errors.
- Speaker labels are not included in v1.
- Audio files and raw working artifacts are intentionally excluded from the repo.
