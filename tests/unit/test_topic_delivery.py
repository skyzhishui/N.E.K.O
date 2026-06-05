from unittest.mock import AsyncMock, MagicMock

import pytest

from main_logic.topic_delivery import (
    build_topic_hook_callback,
    clear_topic_session_manager_getter,
    register_topic_session_manager_getter,
    trigger_topic_hook_once,
)


def test_build_topic_hook_callback_contains_natural_opening_instruction():
    callback = build_topic_hook_callback(
        {
            "hook_id": "topic_car",
            "interest": "用户把买车当成新阶段",
            "hook": "从买车背后的生活阶段感切入",
            "opening_intent": "轻轻调侃，不要像问卷",
            "deepening_hint": "用户接话后再聊现实需求",
        },
        lang="zh-CN",
    )

    assert callback["channel"] == "topic_hook"
    assert callback["source_kind"] == "topic"
    assert callback["delivery_mode"] == "proactive"
    assert callback["priority"] == -20
    assert callback["metadata"]["hook_id"] == "topic_car"
    assert "只生成一句自然开场" in callback["detail"]
    assert "根据你的近期兴趣" in callback["detail"]


def test_build_topic_hook_callback_requires_visible_online_angle_when_available():
    callback = build_topic_hook_callback(
        {
            "hook_id": "topic_car_cost",
            "interest": "用户把买车和生活自由感联系在一起",
            "hook": "先接住不想被人生流程推着走",
            "opening_intent": "像朋友随口一提",
            "online_used": True,
            "online_query": "年轻人 买车 通勤 养车 成本",
            "online_angle": "有搜索结果提到年轻人买车会先看通勤半径和养车成本",
        },
        lang="zh-CN",
    )

    assert "联网补充" in callback["detail"]
    assert "通勤半径和养车成本" in callback["detail"]
    assert "必须自然用上其中一个具体信息" in callback["detail"]


@pytest.mark.asyncio
async def test_trigger_topic_hook_once_enqueues_existing_manager_callback(monkeypatch):
    mgr = MagicMock()
    mgr.enqueue_agent_callback = MagicMock()
    mgr.trigger_agent_callbacks = AsyncMock(return_value=True)

    clear_topic_session_manager_getter()
    register_topic_session_manager_getter(lambda name: mgr)

    delivered = await trigger_topic_hook_once(
        lanlan_name="妮可",
        material={
            "hook_id": "topic_car",
            "interest": "用户把买车当成新阶段",
            "hook": "从买车背后的生活阶段感切入",
        },
        lang="zh-CN",
    )

    assert delivered is True
    mgr.enqueue_agent_callback.assert_called_once()
    callback = mgr.enqueue_agent_callback.call_args.args[0]
    assert callback["task_id"] == "topic_car"
    assert callback["channel"] == "topic_hook"
    mgr.trigger_agent_callbacks.assert_awaited_once()
    clear_topic_session_manager_getter()


@pytest.mark.asyncio
async def test_trigger_topic_hook_once_returns_false_when_manager_defers(monkeypatch):
    mgr = MagicMock()
    mgr.enqueue_agent_callback = MagicMock()
    mgr.trigger_agent_callbacks = AsyncMock(return_value=False)

    clear_topic_session_manager_getter()
    register_topic_session_manager_getter(lambda name: mgr)

    delivered = await trigger_topic_hook_once(
        lanlan_name="妮可",
        material={"hook_id": "topic_car", "interest": "买车"},
        lang="zh-CN",
    )

    assert delivered is False
    mgr.enqueue_agent_callback.assert_called_once()
    mgr.trigger_agent_callbacks.assert_awaited_once()
    clear_topic_session_manager_getter()


@pytest.mark.asyncio
async def test_trigger_topic_hook_once_removes_callback_when_delivery_defers(monkeypatch):
    class FakeManager:
        def __init__(self):
            self.pending_agent_callbacks = []
            self.pending_extra_replies = []

        def enqueue_agent_callback(self, callback):
            callback["_callback_delivery_id"] = "topic_delivery_id"
            self.pending_agent_callbacks.append(callback)
            self.pending_extra_replies.append({"_callback_delivery_id": "topic_delivery_id"})

        async def trigger_agent_callbacks(self):
            return False

    mgr = FakeManager()
    clear_topic_session_manager_getter()
    register_topic_session_manager_getter(lambda name: mgr)

    delivered = await trigger_topic_hook_once(
        lanlan_name="妮可",
        material={"hook_id": "topic_car", "interest": "买车"},
        lang="zh-CN",
    )

    assert delivered is False
    assert mgr.pending_agent_callbacks == []
    assert mgr.pending_extra_replies == []
    clear_topic_session_manager_getter()


@pytest.mark.asyncio
async def test_trigger_topic_hook_once_returns_false_without_manager(monkeypatch):
    clear_topic_session_manager_getter()
    register_topic_session_manager_getter(lambda name: None)

    delivered = await trigger_topic_hook_once(
        lanlan_name="妮可",
        material={"hook_id": "topic_car", "interest": "买车"},
        lang="zh-CN",
    )

    assert delivered is False
    clear_topic_session_manager_getter()


@pytest.mark.asyncio
async def test_trigger_topic_hook_once_does_not_import_main_server(monkeypatch):
    clear_topic_session_manager_getter()

    delivered = await trigger_topic_hook_once(
        lanlan_name="妮可",
        material={"hook_id": "topic_car", "interest": "买车"},
        lang="zh-CN",
    )

    assert delivered is False
