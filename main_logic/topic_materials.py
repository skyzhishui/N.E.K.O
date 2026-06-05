"""Low-frequency topic material helpers for proactive chat.

This module does not trigger proactive chat and does not own long-term memory.
It only turns existing memory/recent candidates into compact hook materials,
optionally enriching the top hooks with existing lightweight online fetchers.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any


Fetcher = Callable[[str, int], Awaitable[Mapping[str, Any]]]


def _clean_text(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _parse_now(now_iso: str | None) -> datetime:
    if now_iso:
        return datetime.fromisoformat(now_iso)
    return datetime.now().astimezone()


def _hook_id(source: str, interest: str) -> str:
    import hashlib

    digest = hashlib.sha1(f"{source}:{interest}".encode("utf-8")).hexdigest()[:12]
    return f"topic_{digest}"


def _iter_candidate_texts(
    *,
    recent_topics: Iterable[Any] | None = None,
    followup_topics: Iterable[Mapping[str, Any]] | None = None,
    open_threads: Iterable[Any] | None = None,
) -> Iterable[tuple[str, str]]:
    for text in recent_topics or []:
        cleaned = _clean_text(text)
        if cleaned:
            yield "recent", cleaned
    for topic in followup_topics or []:
        if not isinstance(topic, Mapping):
            continue
        cleaned = _clean_text(topic.get("text"))
        if cleaned:
            yield "memory", cleaned
    for text in open_threads or []:
        cleaned = _clean_text(text)
        if cleaned:
            yield "thread", cleaned


def _infer_media_intent(text: str) -> list[str]:
    lower = text.lower()
    if any(token in lower for token in ("表情包", "梗图", "meme", "gif")):
        return ["meme"]
    if any(token in lower for token in ("音乐", "歌", "music", "song")):
        return ["music"]
    if any(token in lower for token in ("热点", "新闻", "微博", "twitter", "news")):
        return ["news"]
    return ["news"]


def build_topic_materials(
    *,
    recent_topics: Iterable[Any] | None = None,
    followup_topics: Iterable[Mapping[str, Any]] | None = None,
    open_threads: Iterable[Any] | None = None,
    max_items: int = 2,
    now_iso: str | None = None,
) -> list[dict[str, Any]]:
    """Build a small set of high-signal hook materials from existing candidates."""
    now = _parse_now(now_iso)
    expires_at = (now + timedelta(days=1)).isoformat()
    materials: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source, interest in _iter_candidate_texts(
        recent_topics=recent_topics,
        followup_topics=followup_topics,
        open_threads=open_threads,
    ):
        if interest in seen:
            continue
        seen.add(interest)
        priority = max(10, 90 - len(materials) * 8)
        materials.append({
            "hook_id": _hook_id(source, interest),
            "source": source,
            "interest": interest,
            "hook": f"围绕「{interest}」自然接住，不做总结报告，只抛一个轻钩子。",
            "opening_intent": "具体、短、像随口一提；可以轻微调侃，不要像问卷。",
            "deepening_hint": "如果用户接话，再顺着用户反应聊偏好、原因、选择或情绪。",
            "media_intent": _infer_media_intent(interest),
            "priority": priority,
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": expires_at,
        })
        if len(materials) >= max_items:
            break
    return materials


def _is_zh_lang(lang: str | None) -> bool:
    return str(lang or "").strip().lower().startswith("zh")


async def _default_fetchers(lang: str | None = None) -> dict[str, Fetcher]:
    from utils.meme_fetcher import fetch_meme_content
    from utils.music_crawlers import fetch_music_content
    from utils.web_scraper import (
        search_baidu,
        search_google,
    )

    async def search(keyword: str, limit: int) -> Mapping[str, Any]:
        if _is_zh_lang(lang):
            result = await search_baidu(keyword, limit=limit)
        else:
            result = await search_google(keyword, limit=limit)
        return {
            "success": bool(result.get("success")),
            "region": "china" if _is_zh_lang(lang) else "non-china",
            "search": result,
        }

    async def video(keyword: str, limit: int) -> Mapping[str, Any]:
        return await search(keyword, limit)

    async def news(keyword: str, limit: int) -> Mapping[str, Any]:
        return await search(keyword, limit)

    async def meme(keyword: str, limit: int) -> Mapping[str, Any]:
        return await fetch_meme_content(
            keyword=keyword,
            limit=limit,
            prefer_china=True if _is_zh_lang(lang) else None,
        )

    async def music(keyword: str, limit: int) -> Mapping[str, Any]:
        return await fetch_music_content(
            keyword=keyword,
            limit=limit,
            prefer_china=True if _is_zh_lang(lang) else None,
        )

    return {
        "video": video,
        "news": news,
        "meme": meme,
        "music": music,
    }


def _query_for_material(material: Mapping[str, Any]) -> str:
    query = _clean_text(material.get("search_query"), limit=80)
    if query:
        return query
    interest = _clean_text(material.get("interest"), limit=32)
    if interest:
        return interest
    return _clean_text(material.get("hook"), limit=32)


def _items_from_result(kind: str, result: Mapping[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    def add(title: Any, url: Any = "") -> None:
        title_text = _clean_text(title, limit=80)
        if not title_text:
            return
        items.append({
            "type": kind,
            "title": title_text,
            "url": str(url or ""),
        })

    if kind == "meme":
        for item in result.get("data") or result.get("results") or []:
            if isinstance(item, Mapping):
                add(item.get("title"), item.get("url") or item.get("image_url"))
        return items

    if kind == "music":
        for item in result.get("data") or result.get("tracks") or result.get("results") or []:
            if isinstance(item, Mapping):
                add(item.get("title") or item.get("name"), item.get("url"))
        return items

    search = result.get("search")
    if isinstance(search, Mapping):
        for item in search.get("results") or []:
            if isinstance(item, Mapping):
                add(item.get("title"), item.get("url"))
        return items

    nested = result.get(kind)
    if isinstance(nested, Mapping):
        buckets = (
            nested.get("videos")
            or nested.get("items")
            or nested.get("posts")
            or nested.get("trending")
            or nested.get("topics")
            or []
        )
        for item in buckets:
            if isinstance(item, Mapping):
                add(item.get("title") or item.get("word"), item.get("url"))
    return items


_ZH_STOP_CHARS = set("的一是在不了和就都而及与着或吗呢啊吧呀也很还再又")


def _topic_units(text: str) -> set[str]:
    text = _clean_text(text, limit=120).lower()
    units = {
        token
        for token in __import__("re").findall(r"[a-z0-9]{3,}", text)
        if token
    }
    units.update(
        char
        for char in text
        if "\u4e00" <= char <= "\u9fff" and char not in _ZH_STOP_CHARS
    )
    return units


def _is_related_link(query: str, link: Mapping[str, str]) -> bool:
    query_units = _topic_units(query)
    if not query_units:
        return False
    title_units = _topic_units(link.get("title", ""))
    if not title_units:
        return False
    overlap = query_units & title_units
    if any(len(unit) >= 3 for unit in overlap):
        return True
    return len(overlap) >= 2


def _filter_related_links(query: str, links: list[dict[str, str]]) -> list[dict[str, str]]:
    return [link for link in links if _is_related_link(query, link)]


async def _safe_fetch(kind: str, fetcher: Fetcher, query: str, limit: int, timeout_s: float) -> tuple[str, Mapping[str, Any] | None]:
    try:
        result = await asyncio.wait_for(fetcher(query, limit), timeout=timeout_s)
    except Exception:
        return kind, None
    if not isinstance(result, Mapping) or not result.get("success"):
        return kind, None
    return kind, result


async def enrich_topic_materials_online(
    materials: Iterable[Mapping[str, Any]],
    *,
    fetchers: Mapping[str, Fetcher] | None = None,
    lang: str | None = None,
    max_materials: int = 2,
    fetch_limit: int = 3,
    timeout_s: float = 4.0,
) -> list[dict[str, Any]]:
    """Enrich top materials with lightweight online hints via existing fetchers."""
    available_fetchers = dict(fetchers or await _default_fetchers(lang))
    enriched = [deepcopy(dict(material)) for material in materials]

    for material in enriched[:max_materials]:
        if material.get("material_hint"):
            continue
        query = _query_for_material(material)
        if not query:
            continue
        intents = [
            intent for intent in material.get("media_intent", [])
            if intent in available_fetchers
        ][:2]
        if not intents:
            intents = [kind for kind in ("video", "meme") if kind in available_fetchers]

        results = await asyncio.gather(*[
            _safe_fetch(kind, available_fetchers[kind], query, fetch_limit, timeout_s)
            for kind in intents
        ])
        links: list[dict[str, str]] = []
        for kind, result in results:
            if result is None:
                continue
            links.extend(_items_from_result(kind, result)[:2])
        links = _filter_related_links(query, links)

        if links:
            titles = "、".join(link["title"] for link in links[:3])
            material["material_hint"] = {
                "summary": f"找到了和「{query}」有关的素材：{titles}。必须自然借一个具体点开口，别把联网结果讲成报告。",
                "links": links[:4],
                "meme_keyword": query if "meme" in intents else "",
                "music_keyword": query if "music" in intents else "",
            }
            material["online_used"] = True
            material["online_query"] = query
            material["online_angle"] = titles
    return enriched
