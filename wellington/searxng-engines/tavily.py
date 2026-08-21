# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine to search using the Tavily Search API.

.. _Tavily Search API: https://docs.tavily.com/documentation/api-reference/endpoint/search

Configuration
=============

The engine has the following mandatory setting:

- :py:obj:`api_key`

Optional settings are:

- :py:obj:`max_results`
- :py:obj:`search_depth`

.. code:: yaml

  - name: tavily
    engine: tavily
    api_key: 'YOUR-API-KEY'  # required
    max_results: 10          # optional (1-20)
    search_depth: basic      # optional: basic | advanced

The API returns ranked web results with a title, URL, content snippet,
and a relevance score per result.
"""

import typing as t

from searx.exceptions import SearxEngineAPIException
from searx.result_types import EngineResults
from searx.utils import html_to_text

if t.TYPE_CHECKING:
    from searx.extended_types import SXNG_Response
    from searx.search.processors import OnlineParams

about = {
    "website": "https://tavily.com/",
    "wikidata_id": None,
    "official_api_documentation": "https://docs.tavily.com/documentation/api-reference/endpoint/search",
    "use_official_api": True,
    "require_api_key": True,
    "results": "JSON",
}

api_key: str = ""
"""API key for the Tavily Search API (required)."""

categories = ["general", "web"]
paging = False
safesearch = False
time_range_support = False

max_results: int = 10
"""Maximum number of results to request (1-20, default 10)."""

search_depth: str = "basic"
"""Tavily search depth: 'basic' (fast, 1 credit) or 'advanced' (deeper, higher cost)."""

base_url = "https://api.tavily.com/search"
"""Tavily Search API endpoint."""


def init(_):
    """Initialize the engine."""
    if not api_key:
        raise SearxEngineAPIException("No API key provided")


def request(query: str, params: "OnlineParams") -> None:
    """Create the API request."""
    search_args: dict[str, t.Any] = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": False,
    }

    params["url"] = base_url
    params["method"] = "POST"
    params["json"] = search_args
    params["headers"]["Authorization"] = "Bearer " + api_key


def response(resp: "SXNG_Response") -> EngineResults:
    """Process the API response and return results."""
    res = EngineResults()
    data = resp.json()

    for result in data.get("results", []):
        url = result.get("url")
        if not url:
            continue
        res.add(
            res.types.MainResult(
                url=url,
                title=html_to_text(result.get("title", "")),
                content=html_to_text(result.get("content", "")),
            ),
        )

    return res
