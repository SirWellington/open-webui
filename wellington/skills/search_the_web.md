Use this workflow whenever you need current or external information from the web.

## Tools available to you

- `search_web` — web search via SearXNG. Parameters: `query` (required — the exact parameter name), `num_results` (optional, 1–10; pass `10` for the full list), `time_range` (optional: day, week, month, year), `language` (optional), `safesearch` (optional: 0, 1, 2), `min_score` (optional, 0.0–1.0), `pageno` (optional, 1-based), `categories` (optional, comma-separated), `engines` (optional, comma-separated), `result_detail` (optional: `full` default, `compact`). Returns up to 10 results, each with **Title, URL, and Snippet** (plus relevance score and source metadata) — no full page content. Fetching page content is `md`'s job.
- `md` — Crawl4AI. Converts one web page to clean Markdown. Parameters: `url` (required), `f` (optional filter: `fit` default, `raw`, `bm25`, `llm`), `q` (optional query, required with `bm25`/`llm`), `c` (optional context). **Prefer `f: "llm"` + `q: <question>`** to get clean, simplified, query-focused Markdown — the LLM condenses the page to just the relevant parts (best for answering a specific question; note: local LLM, ~15–60s depending on page size). For a full clean read with no specific question, use `f: "fit"` (default, fast). If you get an `"error": 500` message, it most likely means the URL you provided does not exist or returned a 404 to crawl4ai.
- `crawl` — Crawl4AI. Fetches a list of `urls` in one call and returns a `results[]` array, one entry per URL with `markdown.raw_markdown` and `markdown.fit_markdown` (empty unless requested). Use when you must fetch several pages at once, or to batch fit-Markdown reads. It can produce the same fit Markdown as `md` with `f: "fit"` — see "Fit Markdown via `crawl`" below for the required `crawler_config`.

## Workflow

1. **Search** — call `search_web` with a concise query and `num_results: 10`. It returns up to 10 candidate links (title, URL, snippet) — no page content.
2. **Evaluate** — pick the 2–5 most promising URLs from the snippets. If the results are poor or off-topic, reformulate the query (different keywords, `time_range` for recency) and search again — at most 1–2 reformulations.
3. **Read** — call `md` on each selected URL to get clean Markdown. For a specific question, prefer `f: "llm"` with `q: <the user's actual question>` to get a clean, simplified, query-focused answer (note: local LLM, ~15–60s depending on page size). If `f: "llm"` errors or times out, fall back to `f: "fit"` (full clean read). Alternatively, batch all selected URLs in one `crawl` call with the fit-Markdown `crawler_config` (see "Fit Markdown via `crawl`") and read each page from `results[i].markdown.fit_markdown`. Base your answer strictly on the returned content; never invent page content. If a read fails for a URL, skip it and try the next candidate.
4. **Synthesize** — answer the user's question using the retrieved content. Cite sources as inline Markdown links. If sources conflict, say so. For time-sensitive topics, prefer recent sources and mention the source date when known.

## Fit Markdown via `crawl`

By default `crawl` leaves `results[i].markdown.fit_markdown` empty — Crawl4AI only generates fit Markdown when the Markdown generator has a content filter attached. To get it, pass this `crawler_config` (this is exactly what `md` does server-side with `f: "fit"`):

```json
{
  "urls": ["https://example.com/page-a", "https://example.com/page-b"],
  "crawler_config": {
    "markdown_generator": {
      "type": "DefaultMarkdownGenerator",
      "params": {
        "content_filter": {
          "type": "PruningContentFilter",
          "params": {}
        }
      }
    }
  }
}
```

How it works:
- `PruningContentFilter` scores the page and prunes the HTML down to the main content; Crawl4AI then renders that pruned HTML into `fit_markdown` (and `fit_html`). That is the fit view, versus `raw_markdown`, which is the full page conversion.
- Every nested object in `crawler_config` MUST use Crawl4AI's serializable-dict shape `{"type": "<ClassName>", "params": {...}}` — including `markdown_generator` itself. A plain nested dict (e.g. `"markdown_generator": {"content_filter": {...}}`) is accepted at parse time and then fails with a 500.
- All filter params are optional — `"params": {}` is valid (default: `threshold: 0.48`). `PruningContentFilter` scoring is purely structural (text density, link density, tag importance, text length, compared against `threshold`) — `user_query` is accepted by the constructor but **ignored** in this build, so do not pass it. Tune `threshold` to prune more aggressively (higher) or keep more (lower). For question-focused extraction use `BM25ContentFilter` instead: it scores chunks against `user_query`, so put a concise natural-language question or topic there (e.g. `"how do I configure authentication tokens"`) — or just use `md` with `f: "bm25"`/`f: "llm"` + `q: <question>`, which does the same server-side.
- Read each page from `results[i].markdown.fit_markdown`; treat an empty value as "no readable main content" (usually a 404) and fall back to that URL's `raw_markdown` or the next candidate.
- `crawl` responses are large (each result includes full `html`, `cleaned_html`, `media`, `links`) — extract only the `markdown` fields you need.

## Rules

- Do not rely on just a search snippet. ALWAYS use `md` on at least 3 search results to get a detailed answer.
- Do not use `crawl` for a single URL — use `md`.
- Prefer primary sources (official docs, original publications); ignore ads, aggregators, and redirect links.
- If no page can be read, tell the user which URLs failed instead of guessing the content.
- Keep the final answer grounded in what the tools returned, with URLs cited.
