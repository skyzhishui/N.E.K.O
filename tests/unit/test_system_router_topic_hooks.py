from types import SimpleNamespace

from main_routers.system_router import _allow_open_threads_for_topic_hooks


def test_topic_hooks_open_threads_respect_restricted_screen_only():
    restricted = SimpleNamespace(propensity="restricted_screen_only", unfinished_thread=None)
    restricted_with_thread = SimpleNamespace(
        propensity="restricted_screen_only",
        unfinished_thread={"text": "刚才没聊完的问题"},
    )
    normal = SimpleNamespace(propensity="open", unfinished_thread=None)

    assert _allow_open_threads_for_topic_hooks(None) is True
    assert _allow_open_threads_for_topic_hooks(normal) is True
    assert _allow_open_threads_for_topic_hooks(restricted) is False
    assert _allow_open_threads_for_topic_hooks(restricted_with_thread) is True
