import json
import urllib.request

BASE = "http://127.0.0.1:8085"


def fetch(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.load(r)


def rename(spec, renames):
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            if op.get("operationId") in renames:
                op["operationId"] = renames[op["operationId"]]


# --- searxng ---
sx = fetch("/searxng/openapi.json")
rename(sx, {"tool_searxng_web_search_post": "search_web"})

op = sx["paths"]["/searxng_web_search"]["post"]
op["summary"] = "Search Web"
op["description"] = (
    "Search the web via SearXNG. Returns up to 10 results, each with a title, URL, and a snippet. "
    "The required parameter is exactly `query` (not `prompt` or `q`). "
    "Optional: `num_results` (1-10), `time_range` (day/week/month/year), `language`, "
    "`safesearch` (0/1/2), `min_score` (0.0-1.0), `pageno` (pagination), "
    "`categories`/`engines` (narrow the search), `result_detail` (full/compact). "
    "To read a result page in full, follow up with the `md` tool (Crawl4AI)."
)

schema = sx["components"]["schemas"]["searxng_web_search_form_model"]
props = schema["properties"]
props["categories"]["description"] = (
    "Comma-separated SearXNG categories to restrict the search "
    "(e.g. general, news, images, science, it). If omitted, the instance default is used."
)
props["engines"]["description"] = (
    "Comma-separated SearXNG engine names to query (e.g. google, bing, duckduckgo). "
    "If omitted, the instance default is used."
)

with open("tools/web_search.spec.json", "w", encoding="utf-8") as f:
    json.dump(sx, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("wrote tools/web_search.spec.json")

# --- crawl4ai ---
c4 = fetch("/crawl4ai/openapi.json")
rename(c4, {"tool_md_post": "md", "tool_crawl_post": "crawl"})

with open("tools/crawl4ai.spec.json", "w", encoding="utf-8") as f:
    json.dump(c4, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("wrote tools/crawl4ai.spec.json")
