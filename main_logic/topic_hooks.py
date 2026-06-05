"""Topic-hook prompt helpers for proactive chat.

This module intentionally does not schedule, persist, or deliver anything.
It only turns already-approved proactive candidates into a compact prompt
section that the existing /api/proactive_chat Phase 2 path can consume.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


_HEADER_ZH = """【低频深话题候选】
下面这些不是必须聊的话题，只是更适合聊深一点的切入点。目标是关系深度，不是触发频率；宁可不用，也不要硬聊；这轮最多认真挑 1-2 个最强相关的。
候选里可能夹着寒暄、语气词或还不值得展开的短句；你先判断，没价值就忽略。
开口要求：具体、短、像随口一提，可以轻微调侃；最终只选一个，只抛一个自然钩子，后面交给多轮展开；不要暴露素材来源，也不要像问卷。"""

_HEADER_EN = """[Low-frequency deeper topic candidates]
These are optional hooks for a slightly deeper proactive chat. Use at most 1-2 only if they are clearly the strongest matches; it is better to use none than force it.
Some candidates may be greetings, filler, or too thin to continue; judge first and ignore them if they are not useful.
Opening style: specific, short, casual, lightly teasing if appropriate. Open with one natural hook and leave the rest to multi-turn expansion. Do not say "based on your recent interests" or sound like a survey."""

_LABELS = {
    "zh": {"material": "深话题 hook", "recent": "刚聊到的点", "memory": "可以顺手接的话题", "thread": "刚才没聊完的点"},
    "zh-CN": {"material": "深话题 hook", "recent": "刚聊到的点", "memory": "可以顺手接的话题", "thread": "刚才没聊完的点"},
    "zh-TW": {"material": "深話題 hook", "recent": "剛聊到的點", "memory": "可以順手接的話題", "thread": "剛才沒聊完的點"},
    "en": {"material": "Deep topic hook", "recent": "Recent topic", "memory": "Optional memory hook", "thread": "Open thread"},
}

def _lang_key(lang: str) -> str:
    raw = (lang or "").strip()
    if raw in _LABELS:
        return raw
    if raw.lower().startswith("zh"):
        return "zh"
    return "en"


def _clean_text(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _iter_followup_texts(followup_topics: Iterable[Mapping[str, Any]] | None) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for topic in followup_topics or []:
        if not isinstance(topic, Mapping):
            continue
        text = _clean_text(topic.get("text"))
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
    return texts


def _iter_open_threads(open_threads: Iterable[Any] | None) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for item in open_threads or []:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
    return texts


def _iter_topic_materials(topic_materials: Iterable[Mapping[str, Any]] | None) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for material in topic_materials or []:
        if not isinstance(material, Mapping):
            continue
        interest = _clean_text(material.get("interest"), limit=90)
        hook = _clean_text(material.get("hook"), limit=120)
        opening = _clean_text(material.get("opening_intent"), limit=90)
        deepening = _clean_text(material.get("deepening_hint"), limit=90)
        hint = material.get("material_hint")
        online_angle = _clean_text(material.get("online_angle"), limit=100)
        hint_summary = ""
        hint_links: list[str] = []
        if isinstance(hint, Mapping):
            hint_summary = _clean_text(hint.get("summary"), limit=100)
            for link in hint.get("links") or []:
                if isinstance(link, Mapping):
                    title = _clean_text(link.get("title"), limit=60)
                    link_type = _clean_text(link.get("type"), limit=20)
                    if title:
                        hint_links.append(f"{link_type}:{title}" if link_type else title)

        parts = []
        if interest:
            parts.append(f"关系点={interest}")
        if hook:
            parts.append(f"切入={hook}")
        if opening:
            parts.append(f"开口方向={opening}")
        if deepening:
            parts.append(f"接话后={deepening}")
        if hint_summary:
            parts.append(f"联网素材={hint_summary}")
        if online_angle:
            parts.append(f"联网角度={online_angle}；如果用这个 hook，必须自然借一个具体点")
        if hint_links:
            parts.append(f"素材标题={'; '.join(hint_links[:2])}")
        text = "；".join(parts)
        if text and text not in seen:
            seen.add(text)
            texts.append(text)
    return texts


def build_topic_hook_prompt(
    lang: str,
    *,
    topic_materials: Iterable[Mapping[str, Any]] | None = None,
    recent_topics: Iterable[Any] | None = None,
    followup_topics: Iterable[Mapping[str, Any]] | None = None,
    open_threads: Iterable[Any] | None = None,
    max_items: int = 3,
) -> str:
    """Render optional topic hooks for the existing proactive prompt.

    The output is deliberately a prompt section, not final copy. Phase 2 still
    owns character voice, timing, and whether to pass.
    """
    key = _lang_key(lang)
    labels = _LABELS.get(key, _LABELS["en"])
    header = _HEADER_ZH if key.startswith("zh") else _HEADER_EN

    material_texts = _iter_topic_materials(topic_materials)[:max_items]
    recent_texts = _iter_open_threads(recent_topics)[:max_items]
    memory_texts = _iter_followup_texts(followup_topics)[:max_items]
    thread_texts = _iter_open_threads(open_threads)[:max_items]
    if not material_texts and not recent_texts and not memory_texts and not thread_texts:
        return ""

    lines = [header]
    for text in material_texts:
        lines.append(f"- {labels['material']}: {text}")
    for text in recent_texts:
        lines.append(f"- {labels['recent']}: {text}")
    for text in memory_texts:
        lines.append(f"- {labels['memory']}: {text}")
    for text in thread_texts:
        lines.append(f"- {labels['thread']}: {text}")
    return "\n".join(lines) + "\n"
