from pathlib import Path
import sys

from fastapi.testclient import TestClient


# 允许测试文件直接导入 backend/app 下的模块。
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.trip_planner_agent import ChatIntentDraft, LLMServiceError  # noqa: E402
from app.api.main import app  # noqa: E402
import app.services.trip_service as trip_service  # noqa: E402
from app.models.schemas import (  # noqa: E402
    BudgetBreakdown,
    DayPlan,
    Itinerary,
    MealItem,
    SpotItem,
)

client = TestClient(app)


def build_itinerary() -> Itinerary:
    """构造一个最小合法的 itinerary。"""
    return Itinerary(
        trip_id="trip_chat_test",
        destination="大理",
        summary="测试行程",
        days=[
            DayPlan(
                day_index=1,
                theme="轻松游",
                spots=[SpotItem(name="大理古城")],
                meals=[MealItem(name="烤乳扇", meal_type="午餐")],
                notes=[],
            )
        ],
        estimated_budget=1000,
        budget_breakdown=BudgetBreakdown(
            transport=100, hotel=400, meals=300, tickets=100, other=0, total=1000
        ),
        tips=[],
        source_notes=[],
    )


def build_chat_payload(itinerary: Itinerary, messages: list[dict]) -> dict:
    return {
        "trip_id": itinerary.trip_id,
        "current_itinerary": itinerary.model_dump(mode="json"),
        "messages": messages,
        "context": {"active_panel": "itinerary", "selected_day": 1},
    }


def test_chat_general_reply_without_change(monkeypatch) -> None:
    """一般问答意图：只返回 reply，不修改行程。"""

    def fake_chat_reply(request):
        return (
            ChatIntentDraft(
                reply="第 1 天主要安排是大理古城，建议早点出发避开人流。",
                intent="general_chat",
                day_index=None,
                edit_instruction=None,
            ),
            {"prompt_tokens": 12, "completion_tokens": 8},
        )

    monkeypatch.setattr(trip_service, "generate_chat_reply", fake_chat_reply)

    response = client.post(
        "/trip/chat",
        json=build_chat_payload(
            build_itinerary(),
            [{"role": "user", "content": "第一天有什么好玩的？"}],
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["changed"] is False
    assert data["itinerary"] is None
    assert "大理古城" in data["reply"]


def test_chat_adjust_day_applies_edit(monkeypatch) -> None:
    """调整意图：复用单日编辑链路，返回更新后的 itinerary。"""

    def fake_chat_reply(request):
        return (
            ChatIntentDraft(
                reply="好的，我来把第 1 天调整得更轻松。",
                intent="adjust_day",
                day_index=1,
                edit_instruction="第 1 天节奏更轻松，减少固定安排。",
            ),
            {"prompt_tokens": 15, "completion_tokens": 10},
        )

    def fake_edit(edit_request):
        updated = edit_request.current_itinerary.model_copy(deep=True)
        updated.days[0].theme = "轻松漫游"
        return updated

    monkeypatch.setattr(trip_service, "generate_chat_reply", fake_chat_reply)
    monkeypatch.setattr(trip_service, "edit_trip_itinerary", fake_edit)

    response = client.post(
        "/trip/chat",
        json=build_chat_payload(
            build_itinerary(),
            [{"role": "user", "content": "第一天太赶了，轻松一点"}],
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["changed"] is True
    assert data["itinerary"] is not None
    assert data["itinerary"]["days"][0]["theme"] == "轻松漫游"
    assert "第 1 天" in data["reply"]
    assert data["token_usage"]["planner_prompt_tokens"] >= 15


def test_chat_empty_messages_returns_400() -> None:
    """空对话消息应返回 400。"""
    response = client.post(
        "/trip/chat",
        json=build_chat_payload(build_itinerary(), []),
    )

    assert response.status_code == 400


def test_chat_quota_exhausted_returns_403(monkeypatch) -> None:
    """模型额度耗尽应返回 403 并透出明确提示，而不是模糊失败。"""

    def fake_chat_reply(request):
        raise LLMServiceError(
            "模型服务免费额度已用完（403 FreeTierOnly）。"
            "请到阿里云百炼控制台充值或关闭“仅限免费额度”模式后重试。"
        )

    monkeypatch.setattr(trip_service, "generate_chat_reply", fake_chat_reply)

    response = client.post(
        "/trip/chat",
        json=build_chat_payload(
            build_itinerary(),
            [{"role": "user", "content": "第一天轻松一点"}],
        ),
    )

    assert response.status_code == 403
    assert "免费额度" in response.json()["detail"]
