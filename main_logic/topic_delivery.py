"""One-shot delivery bridge for prepared topic hooks."""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any


logger = logging.getLogger("N.E.K.O.Main.topic_delivery")

_SessionManagerGetter = Callable[[str], Any]
_session_manager_getter: _SessionManagerGetter | None = None


def register_topic_session_manager_getter(getter: _SessionManagerGetter | None) -> None:
    """Install the runtime session-manager lookup used by topic delivery.

    ``topic_delivery`` lives below the app entrypoint layer, so it must not
    import ``app.main_server`` for state: running ``python app/main_server.py``
    stores the real state under ``__main__`` and importing ``app.main_server``
    creates a second, empty module copy.
    """
    global _session_manager_getter
    _session_manager_getter = getter


def clear_topic_session_manager_getter() -> None:
    """Test helper: remove the runtime session-manager lookup."""
    register_topic_session_manager_getter(None)


def build_topic_hook_callback(material: Mapping[str, Any], *, lang: str) -> dict[str, Any]:
    hook_id = str(material.get("hook_id") or "")
    interest = str(material.get("interest") or "").strip()
    hook = str(material.get("hook") or "").strip()
    opening = str(material.get("opening_intent") or "").strip()
    deepening = str(material.get("deepening_hint") or "").strip()
    why_now = str(material.get("why_now") or "").strip()
    online_angle = str(material.get("online_angle") or "").strip()
    online_query = str(material.get("online_query") or material.get("search_query") or "").strip()
    hint = material.get("material_hint")
    hint_summary = ""
    if isinstance(hint, Mapping):
        hint_summary = str(hint.get("summary") or "").strip()

    detail_parts = [
        "这是一个已经筛好的低频深话题 hook。",
        f"关系点：{interest}" if interest else "",
        f"切入角度：{hook}" if hook else "",
        f"开口方向：{opening}" if opening else "",
        f"接话后展开：{deepening}" if deepening else "",
        f"为什么现在适合：{why_now}" if why_now else "",
        f"可借素材：{hint_summary}" if hint_summary else "",
        (
            f"联网补充：查询「{online_query}」后得到的具体角度：{online_angle}。"
            "必须自然用上其中一个具体信息；如果这轮用不上，就不要触发这个 hook。"
        ) if online_angle else "",
        "请只生成一句自然开场，像随口想起来，不要说“根据你的近期兴趣”，不要像问卷。",
    ]
    detail = "\n".join(part for part in detail_parts if part)
    return {
        "event": "agent_task_callback",
        "origin": "event",
        "task_id": hook_id or "topic_hook",
        "channel": "topic_hook",
        "status": "completed",
        "success": True,
        "summary": hook or interest,
        "detail": detail,
        "source_kind": "topic",
        "source_name": "deep_topic_hook",
        "delivery_mode": "proactive",
        "priority": -20,
        "coalesce_key": hook_id or interest,
        "timestamp": "",
        "metadata": {
            "context_type": "topic_hook",
            "hook_id": hook_id,
            "lang": lang,
        },
        "context_type": "topic_hook",
    }


def _remove_callback_from_manager(mgr: Any, callback: Mapping[str, Any]) -> None:
    delivery_id = callback.get("_callback_delivery_id")
    callback_obj_id = id(callback)

    pending = getattr(mgr, "pending_agent_callbacks", None)
    if isinstance(pending, list):
        mgr.pending_agent_callbacks = [
            item for item in pending
            if (
                id(item) != callback_obj_id
                and (
                    not delivery_id
                    or not isinstance(item, Mapping)
                    or item.get("_callback_delivery_id") != delivery_id
                )
            )
        ]

    extras = getattr(mgr, "pending_extra_replies", None)
    if delivery_id and isinstance(extras, list):
        mgr.pending_extra_replies = [
            item for item in extras
            if not isinstance(item, Mapping) or item.get("_callback_delivery_id") != delivery_id
        ]


async def trigger_topic_hook_once(
    *,
    lanlan_name: str,
    material: Mapping[str, Any],
    lang: str,
) -> bool:
    """Queue one prepared topic hook into the existing character delivery path."""
    if _session_manager_getter is None:
        logger.info("[%s] topic hook delivery skipped: no session manager getter", lanlan_name)
        return False

    mgr = _session_manager_getter(lanlan_name)
    if mgr is None:
        logger.info("[%s] topic hook delivery skipped: no session manager", lanlan_name)
        return False

    callback = build_topic_hook_callback(material, lang=lang)
    enqueue = getattr(mgr, "enqueue_agent_callback", None)
    trigger = getattr(mgr, "trigger_agent_callbacks", None)
    if not callable(enqueue) or not callable(trigger):
        logger.info("[%s] topic hook delivery skipped: manager cannot deliver callbacks", lanlan_name)
        return False

    enqueue(callback)
    try:
        delivered = bool(await trigger())
    except Exception:
        _remove_callback_from_manager(mgr, callback)
        raise
    if not delivered:
        # ``trigger_agent_callbacks`` keeps callbacks queued on many retriable
        # False paths. Topic hooks need stricter accounting: only
        # TopicHookPool may retry and mark used/quota. Remove this queued copy so
        # it cannot surface later outside the topic pool's one-shot bookkeeping.
        _remove_callback_from_manager(mgr, callback)
    return delivered
