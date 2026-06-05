from main_logic.topic_hooks import build_topic_hook_prompt


def test_build_topic_hook_prompt_combines_memory_and_open_threads():
    prompt = build_topic_hook_prompt(
        lang="zh-CN",
        recent_topics=[
            "我的车是白色的，不会给我用差漆吧，有色差就不好看了",
        ],
        followup_topics=[
            {"id": "r1", "text": "用户最近在纠结直播里的角色风格和吐槽尺度"},
        ],
        open_threads=[
            "用户刚才还没回答：更想要会接梗，还是更想要敢吐槽",
        ],
    )

    assert "低频深话题候选" in prompt
    assert "刚聊到的点" in prompt
    assert "白色的，不会给我用差漆" in prompt
    assert "直播里的角色风格" in prompt
    assert "更想要会接梗" in prompt
    assert "只选一个" in prompt
    assert "先判断" in prompt
    assert "寒暄" in prompt
    assert "强相关" in prompt
    assert "关系深度" in prompt
    assert "宁可不用" in prompt
    assert "多轮" in prompt
    assert "根据你的近期兴趣" not in prompt
    assert "我注意到你最近" not in prompt
    assert "我们来聊聊" not in prompt


def test_build_topic_hook_prompt_returns_empty_without_candidates():
    assert build_topic_hook_prompt(
        lang="zh-CN",
        recent_topics=[],
        followup_topics=[],
        open_threads=[],
    ) == ""


def test_build_topic_hook_prompt_renders_topic_materials_with_online_hints():
    prompt = build_topic_hook_prompt(
        lang="zh-CN",
        topic_materials=[
            {
                "hook_id": "topic_car_paint",
                "interest": "用户担心白车补漆有色差",
                "hook": "从白车补漆切入，轻轻吐槽一下补漆笔翻车",
                "opening_intent": "一句话抛钩子，不做教程",
                "deepening_hint": "如果用户接话，再聊预算和如何避免被坑",
                "material_hint": {
                    "summary": "找到了白车补漆避坑指南，可以借一个具体点开口。",
                    "links": [
                        {
                            "type": "video",
                            "title": "白车补漆避坑指南",
                            "url": "https://example.test/video",
                        }
                    ],
                },
            }
        ],
    )

    assert "深话题 hook" in prompt
    assert "用户担心白车补漆有色差" in prompt
    assert "白车补漆避坑指南" in prompt
    assert "一句话抛钩子" in prompt
    assert "如果用户接话" in prompt
