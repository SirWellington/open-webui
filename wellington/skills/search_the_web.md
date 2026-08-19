# Skill: search_the_web

Create this skill in OWUI: **Admin → Skills → New** (or the user Skills page).

- **Name:** `search_the_web`
- **Description:** Web research workflow — search the web (SearXNG) and read pages as clean Markdown (Crawl4AI).
- **Content:** paste everything below the line.

---

Use this workflow whenever you need current or external information from the web.

## Tools available to you

- `search_web` — web search via SearXNG. Parameters: `query` (required — the exact parameter name), `num_results` (optional, 1–10; pass `10` for the full list), `time_range` (optional: day, week, month, year), `language` (optional), `safesearch` (optional: 0, 1, 2), `min_score` (optional, 0.0–1.0), `pageno` (optional, 1-based), `categories` (optional, comma-separated), `engines` (optional, comma-separated), `result_detail` (optional: `full` default, `compact`). Returns up to 10 results, each with **Title, URL, and Snippet** (plus relevance score and source metadata) — no full page content. Fetching page content is `md`'s job.
- `md` — Crawl4AI. Converts one web page to clean Markdown. Parameters: `url` (required), `f` (optional filter: `fit` default, `raw`, `bm25`, `llm`), `q` (optional query, required with `bm25`/`llm`), `c` (optional context). **Prefer `f: "llm"` + `q: <question>`** to get clean, simplified, query-focused Markdown — the LLM condenses the page to just the relevant parts (best for answering a specific question; note: local LLM, ~15–60s depending on page size). For a full clean read with no specific question, use `f: "fit"` (default, fast).
- `crawl` — Crawl4AI. Fetches a list of `urls` in one call. Use only when you must fetch several pages at once.

## Workflow

1. **Search** — call `search_web` with a concise query and `num_results: 10`. It returns up to 10 candidate links (title, URL, snippet) — no page content.
2. **Evaluate** — pick the 2–5 most promising URLs from the snippets. If the results are poor or off-topic, reformulate the query (different keywords, `time_range` for recency) and search again — at most 1–2 reformulations.
3. **Read** — call `md` on each selected URL to get clean Markdown. For a specific question, prefer `f: "llm"` with `q: <the user's actual question>` to get a clean, simplified, query-focused answer (note: local LLM, ~15–60s depending on page size). If `f: "llm"` errors or times out, fall back to `f: "fit"` (full clean read). Base your answer strictly on the returned content; never invent page content. If `md` fails for a URL, skip it and try the next candidate.
4. **Synthesize** — answer the user's question using the retrieved content. Cite sources as inline Markdown links. If sources conflict, say so. For time-sensitive topics, prefer recent sources and mention the source date when known.

## Rules

- Do not rely on just a search snippet. ALWAYS use `md` on at least 3 search results to get a detailed answer.
- Do not use `crawl` for a single URL — use `md`.
- Prefer primary sources (official docs, original publications); ignore ads, aggregators, and redirect links.
- If no page can be read, tell the user which URLs failed instead of guessing the content.
- Keep the final answer grounded in what the tools returned, with URLs cited.
