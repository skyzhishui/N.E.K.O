import pytest

from main_logic.topic_materials import (
    build_topic_materials,
    enrich_topic_materials_online,
)


def test_build_topic_materials_limits_to_two_high_quality_hooks():
    materials = build_topic_materials(
        recent_topics=[
            "我的车是白色的，不会给我用差漆吧，有色差就不好看了",
            "周末想去看车，但是还没定去哪家店",
            "外卖酸得离谱，吃完嘴里还怪怪的",
        ],
        followup_topics=[
            {"text": "用户最近在纠结直播里的角色风格和吐槽尺度"},
        ],
        max_items=2,
        now_iso="2026-06-04T10:00:00+08:00",
    )

    assert len(materials) == 2
    assert materials[0]["status"] == "pending"
    assert materials[0]["hook_id"].startswith("topic_")
    assert materials[0]["source"] == "recent"
    assert "白色的" in materials[0]["interest"]
    assert "自然接住" in materials[0]["hook"]
    assert materials[0]["expires_at"] == "2026-06-05T10:00:00+08:00"


@pytest.mark.asyncio
async def test_enrich_topic_materials_online_defaults_to_search_fetcher():
    calls = []

    async def fake_news(keyword, limit):
        calls.append(("news", keyword, limit))
        return {
            "success": True,
            "search": {
                "results": [
                    {"title": "白车补漆避坑指南", "url": "https://example.test/news"}
                ]
            },
        }

    async def fake_meme(keyword, limit):
        calls.append(("meme", keyword, limit))
        return {
            "success": True,
            "data": [
                {"title": "补漆翻车表情包", "url": "https://example.test/meme.jpg"}
            ],
            "keyword_used": keyword,
        }

    materials = build_topic_materials(
        recent_topics=["我的车是白色的，不会给我用差漆吧，有色差就不好看了"],
        max_items=1,
        now_iso="2026-06-04T10:00:00+08:00",
    )

    enriched = await enrich_topic_materials_online(
        materials,
        fetchers={"news": fake_news, "meme": fake_meme},
        max_materials=1,
    )

    assert [call[0] for call in calls] == ["news"]
    hint = enriched[0]["material_hint"]
    assert "白车补漆避坑指南" in hint["summary"]
    assert hint["links"][0]["type"] == "news"
    assert not hint["meme_keyword"]


@pytest.mark.asyncio
async def test_enrich_topic_materials_online_uses_model_search_query_and_marks_online_angle():
    calls = []

    async def fake_news(keyword, limit):
        calls.append(keyword)
        return {
            "success": True,
            "search": {
                "results": [
                    {
                        "title": "年轻人买车先看通勤半径和养车成本",
                        "url": "https://example.test/car-cost",
                    }
                ]
            },
        }

    materials = [
        {
            "interest": "用户把买车和生活自由感联系在一起",
            "hook": "不要硬讲车，先接住不想被人生流程推着走",
            "search_query": "年轻人 买车 通勤 养车 成本",
            "media_intent": ["news"],
        }
    ]

    enriched = await enrich_topic_materials_online(
        materials,
        fetchers={"news": fake_news},
        max_materials=1,
    )

    assert calls == ["年轻人 买车 通勤 养车 成本"]
    assert enriched[0]["online_used"] is True
    assert enriched[0]["online_query"] == "年轻人 买车 通勤 养车 成本"
    assert "通勤半径和养车成本" in enriched[0]["online_angle"]
    assert "必须自然借一个具体点" in enriched[0]["material_hint"]["summary"]


@pytest.mark.asyncio
async def test_enrich_topic_materials_online_drops_unrelated_online_titles():
    async def fake_news(keyword, limit):
        return {
            "success": True,
            "search": {
                "results": [
                    {"title": "全球最神秘超市卖什么", "url": "https://example.test/offtopic"},
                    {"title": "吉利银河混动纯电怎么选", "url": "https://example.test/car"},
                ]
            },
        }

    materials = build_topic_materials(
        recent_topics=["吉利银河混动和纯电选择纠结"],
        max_items=1,
        now_iso="2026-06-04T10:00:00+08:00",
    )

    enriched = await enrich_topic_materials_online(
        materials,
        fetchers={"news": fake_news},
        max_materials=1,
    )

    hint = enriched[0]["material_hint"]
    assert "吉利银河混动纯电怎么选" in hint["summary"]
    assert "全球最神秘超市" not in hint["summary"]
