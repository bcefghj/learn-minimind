# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**learn-minimind** is a Chinese-language LLM learning tutorial + interview prep handbook built around the [MiniMind](https://github.com/jingyaogong/minimind) project (64M-parameter GPT). It contains:

- `docs/` — 24 lesson Markdown files (L01–L24)
- `interview/` — 10 interview Q&A Markdown files (190+ questions)
- `assets/comics/` — 15 original Doraemon-style illustration PNGs
- `scripts/` — Python build scripts for HTML/PDF output
- `web/` — Next.js interactive learning website
- `dist/` — Generated HTML/PDF output (not committed)

## Commands

### Web (Next.js) — run from `web/`

```bash
cd web
npm install        # install dependencies
npm run dev        # dev server at http://localhost:3000
npm run build      # static export to web/out/
npm run start      # serve production build
```

The Next.js app is configured as a static export (`output: "export"` in `next.config.ts`). It reads Markdown files from the parent repo at runtime via `web/src/lib/readMarkdown.ts`.

### HTML generation — run from repo root

```bash
pip install markdown pygments
python scripts/build_html.py
# Output: dist/html/index.html + per-lesson HTML files
```

### PDF generation — run from repo root

```bash
pip install markdown weasyprint
python scripts/build_pdf.py
# Output: dist/pdf/
```

## Web Architecture

The Next.js app (`web/`) reads Markdown content directly from the parent directory:

- `web/src/lib/readMarkdown.ts` — reads `docs/` and `interview/` files at build time using `fs`; the `REPO_ROOT` is `path.join(process.cwd(), "..")` (one level up from `web/`)
- `web/src/lib/lessons-data.ts` and `interview-data.ts` — slug-to-filename mappings; **must be updated when adding new lessons or interview files**
- Routes: `/lesson/[slug]` and `/interview/[slug]` use these mappings to serve Markdown rendered via `react-markdown` + `remark-gfm`

### Key components

| Component | Purpose |
|-----------|---------|
| `Hero.tsx` | Landing page with code typewriter animation |
| `TokenFlow.tsx` | Animated token data flow visualization |
| `LearningPath.tsx` | 24-lesson scroll card grid |
| `Architecture.tsx` | Collapsible Transformer block diagram |
| `MarkdownArticle.tsx` | Shared Markdown renderer for lessons and interview pages |

## Content Structure

Lesson files in `docs/` follow the naming pattern `L##-<title>.md`. Interview files in `interview/` follow `##-<title>.md`. When adding new content files, update the slug mappings in `web/src/lib/lessons-data.ts` or `web/src/lib/interview-data.ts` accordingly.

Image paths in Markdown use relative `../assets/comics/` paths (relative to `docs/`). The HTML build script normalizes these to `assets/` in the output directory.
