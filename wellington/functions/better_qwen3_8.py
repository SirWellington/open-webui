"""
title: Better Qwen3.8
author: Wellington Moreno
author_url: https://github.com/SirWellington
funding_url: https://github.com/SirWellington
version: 1.0

Heuristic Logic — 3-Tier Request Difficulty Classifier (Qwen3.8 thinking control)
=======================================================================================
Replaces the external assessor model with instant rule-based classification.
Zero latency, zero VRAM, zero network call.

Qwen3.8 thinking control (official, per the Qwen/Qwen3.8-27B model card):
  Qwen3.8 thinks BY DEFAULT. It ships three first-class controls:
    - enable_thinking    (bool)   per-request on/off switch for thinking
    - reasoning_effort   (level)  "xhigh" (default) | "medium" | "low"
    - preserve_thinking  (bool)   keep historical thinking blocks (default: true)

  How to set them:
    * Self-hosted (LM Studio / vLLM / llama.cpp / SGLang):
        enable_thinking / preserve_thinking go in "chat_template_kwargs",
        reasoning_effort goes top-level. (This is exactly how the official
        model-card examples do it.)
    * Qwen Cloud / hosted APIs:
        "enable_thinking" and "preserve_thinking" are passed top-level
        (NOT wrapped in chat_template_kwargs).

  To cover both worlds this filter sends enable_thinking in BOTH places and
  reasoning_effort top-level. They are documented as compatible (the official
  examples combine them in one request).

  IMPORTANT DIFFERENCES vs the old Qwen3 approach:
    - Qwen3.8 has NO reasoning_effort="none" level (levels: xhigh/medium/low).
    - Qwen3.8 has NO reasoning_budget_tokens / thinking_budget for this purpose;
      the official off-switch is enable_thinking=false.
    - So the "no thinking" tier = enable_thinking=false (instruct mode),
      with an optional reasoning_effort="low" safety net in case a backend
      ignores the off-switch (set easy_effort_fallback=None to disable).

Input: full message history + latest user message text.

Step 1 — Extract text from latest user message
  - Handle string content and list/multimodal content.

Step 2 — Check "HARD" triggers (any single match returns "hard")
  a) Attachments detected (image, PDF, document, etc.)
  b) Latest message word count > 50
  c) Code detected: backticks or programming keywords
  d) Reasoning keywords: why, explain, solve, determine, step by step, etc.
  e) Total conversation word count > 1000 (full history)

Step 3 — Check "EASY" triggers (any match returns "easy")
  a) Greeting / small talk: hi, hello, hey, thanks, etc.
  b) Simple factual lookup: "capital of X", "define X", "who wrote X"
  c) Yes/no question under 15 words: "is water wet?"
  d) Simple conversion: "convert 5km to miles"
  e) Short translation: "translate hello to spanish"

Step 4 — Default → "medium" (moderate reasoning effort)
  - Anything not caught by hard or easy gets medium reasoning effort.

Output mapping (Qwen3.8 parameters, as live-verified):
  easy   → reasoning_effort="none" + enable_thinking=false   (0 reasoning tokens)
  medium → reasoning_effort="medium" + enable_thinking=true  (+ optional budget cap)
  hard   → reasoning_effort="xhigh" + enable_thinking=true   (+ optional budget cap)
"""

import re
from pydantic import BaseModel, Field
from typing import Optional


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=999,
            description="Priority level — set high so this runs last and is not overridden.",
        )
        model_pattern: str = Field(
            default=r"qwen3\.?8|qwen\.latest",
            description="Regex pattern to match model names that should use auto-thinking (default: qwen3.8-* and the qwen.latest workspace model).",
        )
        hard_word_threshold: int = Field(
            default=50,
            description="If the latest message exceeds this many words, classify as hard.",
        )
        conversation_word_threshold: int = Field(
            default=1000,
            description="If total conversation exceeds this many words, classify as hard.",
        )
        easy_max_words: int = Field(
            default=20,
            description="Maximum words for a message to qualify as easy.",
        )
        yes_no_max_words: int = Field(
            default=15,
            description="Maximum words for a yes/no question to qualify as easy.",
        )
        hard_effort: str = Field(
            default="xhigh",
            description='reasoning_effort for hard-tier prompts (Qwen3.8 levels: xhigh, medium, low).',
        )
        medium_effort: str = Field(
            default="medium",
            description='reasoning_effort for medium-tier prompts (Qwen3.8 levels: xhigh, medium, low).',
        )
        easy_effort: str = Field(
            default="none",
            description='reasoning_effort for easy-tier prompts. "none" = zero thinking (live-verified on LM Studio). Use "low" if your backend rejects "none".',
        )
        medium_budget: Optional[int] = Field(
            default=None,
            description="Optional thinking_budget (token cap) for medium tier, in addition to reasoning_effort. Empty = don't send.",
        )
        hard_budget: Optional[int] = Field(
            default=None,
            description="Optional thinking_budget (token cap) for hard tier, in addition to reasoning_effort. Empty = don't send. (Some Qwen Cloud models reject reasoning_effort + thinking_budget together.)",
        )
        preserve_thinking: bool = Field(
            default=True,
            description="Qwen3.8 preserve_thinking — keep reasoning content from previous turns (default: true).",
        )
        apply_sampling_recs: bool = Field(
            default=False,
            description="Apply Qwen3.8 official sampling recommendations per mode (overrides the request's sampling params). Instruct: temp 0.7, top_p 0.8, presence_penalty 1.5. Thinking: temp 1.0, top_p 0.95, presence_penalty 0.0.",
        )

    class UserValves(BaseModel):
        pass

    def __init__(self):
        self.valves = self.Valves()
        self._model_regex = re.compile(self.valves.model_pattern, re.IGNORECASE)

        # Pre-compiled patterns
        self._code_pattern = re.compile(
            r"(?:`+|"
            r"\b(import|def\s|function\s|class\s|const\s|let\s|var\s|fn\s|pub\s)\b"
            r")",
            re.IGNORECASE,
        )
        self._hard_keywords = re.compile(
            r"\b(?:why|explain|solve|determine|step\s*by\s*step|"
            r"compare|analyze|debug|design|implement|architect)\b",
            re.IGNORECASE,
        )
        self._greeting_pattern = re.compile(
            r"^\s*(hi|hello|hey|howdy|greetings|good\s*(morning|afternoon|evening|day)|"
            r"thanks?|thank\s*you|appreciate|bye|see\s*you|cya|t\.?b\.?|have\s*a|nice\b|"
            r"cool|great|awesome|ok(?:ay)?|sure|yeah|yep|nope|right|correct)\s*[,.!?]*\s*$",
            re.IGNORECASE,
        )
        self._yes_no_pattern = re.compile(
            r"^\s*(is\s|does\s|can\s|will\s|could\s|would\s|should\s|do\s|has\s|have\s)\b",
            re.IGNORECASE,
        )
        self._factual_lookup_pattern = re.compile(
            r"^\s*(what(?:'s)?\s+(the\s+)?(?:capital|population|meaning|definition|opposite|abbreviation)\b.*|"
            r"what\s+is\s+(the\s+)?(?:capital|population|meaning|definition|opposite|abbreviation)\b.*|"
            r"capital\s+of\s\w+\b.*|"
            r"who\s+(wrote|invented|created|discovered|founded|is)\s+\w+\b.*|"
            r"when\s+(was|were|did)\s.*|"
            r"where\s+(is|are|was|were|can|do)\s.*|"
            r"define\s+\w+\b.*)"
            r"\s*[\?]?\s*$",
            re.IGNORECASE,
        )
        self._conversion_pattern = re.compile(
            r"^\s*(convert\s+[\d\w]+\s+(?:\w+\s+)?to\s+\w+|"
            r"\d+\s+(celsius|fahrenheit|kelvin|km|miles|meters|feet|inches|cm|lb|kg|grams|ounces)\s+in\s+"
            r"\w+|"
            r"how\s+many\s+\w+\s+in\s+(?:a\s+)?\w+)"
            r"\s*[\.!?,]?\s*$",
            re.IGNORECASE,
        )
        self._translation_pattern = re.compile(
            r"^\s*(translate\s+.+?to\s+\w+|"
            r".+?\s+in\s+(english|spanish|french|german|japanese|chinese|korean|portuguese|italian|arabic|russian|hindi)\b)"
            r"\s*[\.!?,]?\s*$",
            re.IGNORECASE,
        )

    def _extract_text(self, content) -> str:
        """Extract plain text from message content (str or multimodal list)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)

    def _count_words(self, text: str) -> int:
        """Count words in a string."""
        return len(text.split())

    def _has_attachments(self, messages: list) -> bool:
        """Check if any message contains attachments (images, files, etc.)."""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") != "text":
                        return True
        return False

    def classify(self, messages: list, latest_user_text: str) -> str:
        """Return 'hard', 'medium', or 'easy' based on heuristic rules."""
        latest_lower = latest_user_text.lower().strip()
        latest_word_count = self._count_words(latest_user_text)

        # --- STEP 2: HARD triggers (any match → hard) ---

        if self._has_attachments(messages):
            return "hard"

        if latest_word_count > self.valves.hard_word_threshold:
            return "hard"

        if self._code_pattern.search(latest_user_text):
            return "hard"

        if self._hard_keywords.search(latest_lower):
            return "hard"

        total_words = sum(
            self._count_words(self._extract_text(m.get("content", "")))
            for m in messages
        )
        if total_words > self.valves.conversation_word_threshold:
            return "hard"

        # --- STEP 3: EASY triggers (any match → easy) ---
        # All easy checks require under the word limit
        if latest_word_count > self.valves.easy_max_words:
            return "medium"

        if self._greeting_pattern.match(latest_lower):
            return "easy"

        if self._factual_lookup_pattern.search(latest_lower):
            return "easy"

        if (
            self._yes_no_pattern.search(latest_lower)
            and latest_word_count <= self.valves.yes_no_max_words
        ):
            return "easy"

        if self._conversion_pattern.match(latest_lower):
            return "easy"

        if self._translation_pattern.match(latest_lower):
            return "easy"

        # --- STEP 4: Default → medium ---
        return "medium"

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[callable] = None,
    ) -> dict:
        model_id = body.get("model", "")
        if not self._model_regex.search(model_id):
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        latest_user_msg = next(
            (msg for msg in reversed(messages) if msg.get("role") == "user"), None
        )
        if not latest_user_msg:
            return body

        latest_user_text = self._extract_text(latest_user_msg.get("content", ""))
        if not latest_user_text.strip():
            return body

        result = self.classify(messages, latest_user_text)

        # --- Remove stale / legacy params that could interfere ---
        body.pop("reasoning_budget_tokens", None)  # Qwen3-era param
        body.pop("thinking_budget", None)          # Qwen Cloud budget param (conflicts with reasoning_effort on some models)
        body.pop("think", None)                    # Qwen3-era OpenWebUI toggle
        body.pop("reasoning_effort", None)
        body.pop("enable_thinking", None)

        # Preserve any existing chat_template_kwargs (e.g. from another filter)
        kwargs = body.get("chat_template_kwargs")
        if not isinstance(kwargs, dict):
            kwargs = {}

        if result == "hard":
            body["enable_thinking"] = True
            body["reasoning_effort"] = self.valves.hard_effort
            if self.valves.hard_budget is not None:
                body["thinking_budget"] = self.valves.hard_budget
            kwargs["enable_thinking"] = True
            kwargs["preserve_thinking"] = self.valves.preserve_thinking
            body["chat_template_kwargs"] = kwargs
            if self.valves.apply_sampling_recs:
                body.update(
                    temperature=1.0, top_p=0.95, top_k=20,
                    presence_penalty=0.0, repetition_penalty=1.0,
                )
            status = (
                f"\U0001f9e0 Thinking enabled (Qwen3.8, effort={self.valves.hard_effort})"
            )
        elif result == "medium":
            body["enable_thinking"] = True
            body["reasoning_effort"] = self.valves.medium_effort
            if self.valves.medium_budget is not None:
                body["thinking_budget"] = self.valves.medium_budget
            kwargs["enable_thinking"] = True
            kwargs["preserve_thinking"] = self.valves.preserve_thinking
            body["chat_template_kwargs"] = kwargs
            if self.valves.apply_sampling_recs:
                body.update(
                    temperature=1.0, top_p=0.95, top_k=20,
                    presence_penalty=0.0, repetition_penalty=1.0,
                )
            status = (
                f"\U0001f9e0 Thinking enabled (Qwen3.8, effort={self.valves.medium_effort})"
            )
        else:
            # Live-verified off-switch on LM Studio: reasoning_effort="none"
            # (measured: 0 reasoning tokens). enable_thinking=false is also sent
            # because it is the documented switch on Qwen Cloud and may work on
            # future LM Studio builds — but on current LM Studio it alone is
            # IGNORED (measured: 33-50 reasoning tokens; LM Studio bug #1990).
            body["enable_thinking"] = False
            body["reasoning_effort"] = self.valves.easy_effort
            kwargs["enable_thinking"] = False
            kwargs["preserve_thinking"] = self.valves.preserve_thinking
            body["chat_template_kwargs"] = kwargs
            if self.valves.apply_sampling_recs:
                body.update(
                    temperature=0.7, top_p=0.8, top_k=20,
                    presence_penalty=1.5, repetition_penalty=1.0,
                )
            status = "\u26a1 Thinking disabled (Qwen3.8, effort=none)"

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": status, "done": True},
                }
            )

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
