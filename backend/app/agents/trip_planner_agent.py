from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from app.agents.tools.rag_tool import get_destination_guide_context
from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from app.models.schemas import DayPlan, Itinerary, TripChatRequest, TripEditRequest, TripRequest
from app.services.place_candidate_service import (
    CityCandidatePool,
    PlaceCandidate,
    PlaceCandidateCategory,
)


class LLMServiceError(RuntimeError):
    """LLM 服务不可用的明确错误（如免费额度耗尽、鉴权失败），需要透出给用户。"""


# 命中这些特征的异常属于账号/额度问题，降级无意义，必须明确告知用户。
_LLM_QUOTA_ERROR_MARKERS = (
    "FreeTierOnly",
    "AllocationQuota",
    "Free quota exhausted",
    "Arrearage",
    "quota",
)


def _raise_if_quota_error(exc: Exception) -> None:
    """识别额度/配额类 LLM 异常并转换为 LLMServiceError。"""
    text = str(exc)
    if any(marker.lower() in text.lower() for marker in _LLM_QUOTA_ERROR_MARKERS):
        raise LLMServiceError(
            "模型服务免费额度已用完（403 FreeTierOnly）。"
            "请到阿里云百炼控制台充值或关闭“仅限免费额度”模式后重试。"
        ) from exc


class PlannerDayDraft(BaseModel):
    """LLM 返回的单日最小行程草稿。"""

    day_index: int = Field(..., ge=1)
    theme: str = Field(..., description="当天的简短主题")
    spot_name: str = Field(..., description="当天主要景点名称")
    spot_description: str = Field(..., description="推荐该景点的简短理由")
    meal_name: str = Field(..., description="当天的餐饮或餐厅建议")
    meal_notes: str = Field(..., description="简短的用餐说明")
    daily_note: str = Field(..., description="当天的一条简短规划备注")


class PlannerDraft(BaseModel):
    """提供给 trip_service.py 使用的结构化行程草稿。"""

    summary: str = Field(..., description="整趟旅行的简短概述")
    tips: list[str] = Field(default_factory=list, description="旅行提示")
    days: list[PlannerDayDraft] = Field(default_factory=list)


class DynamicPlannerDayDraft(BaseModel):
    """动态城市 Planner 只通过 POI ID 选择当天实体。"""

    day_index: int = Field(..., ge=1)
    theme: str = Field(..., description="当天主题")
    spot_poi_id: str = Field(..., description="候选池中的景点 POI ID")
    spot_start_time: str = Field(default="10:00", pattern=r"^\d{2}:\d{2}$")
    spot_end_time: str = Field(default="12:00", pattern=r"^\d{2}:\d{2}$")
    spot_reason: str = Field(..., description="选择该景点的简短理由")
    meal_poi_id: str = Field(..., description="候选池中的餐饮 POI ID")
    meal_notes: str = Field(..., description="用餐安排说明")
    daily_note: str = Field(..., description="当天安排说明")


class DynamicPlannerDraft(BaseModel):
    """未沉淀城市的受约束行程草稿。"""

    summary: str = Field(..., description="整趟旅行概述")
    tips: list[str] = Field(default_factory=list)
    hotel_poi_id: str = Field(..., description="候选池中的住宿 POI ID")
    days: list[DynamicPlannerDayDraft] = Field(default_factory=list)


class DayEditDraft(BaseModel):
    """LLM 返回的单日编辑草稿。"""

    theme: str = Field(..., description="编辑后的当天主题")
    spot_name: str = Field(..., description="编辑后的主要景点名称")
    spot_description: str = Field(..., description="编辑后的景点说明")
    meal_name: str = Field(..., description="编辑后的餐饮名称")
    meal_notes: str = Field(..., description="编辑后的餐饮说明")
    daily_note: str = Field(..., description="编辑后的当天备注")


class ChatIntentDraft(BaseModel):
    """对话意图解析结果。

    intent = "adjust_day" 时，service 层会把 edit_instruction 转交
    现有单日编辑链路（generate_day_edit_draft）执行真实修改；
    intent = "general_chat" 时，reply 直接作为对话回答。
    """

    reply: str = Field(..., description="给用户的回复文本（简短、可操作）")
    intent: str = Field(
        ...,
        description="意图类型：adjust_day（要求修改某天行程）或 general_chat（一般问答）",
    )
    day_index: int | None = Field(
        default=None, ge=1, description="intent=adjust_day 时的目标天 day_index"
    )
    edit_instruction: str | None = Field(
        default=None, description="intent=adjust_day 时，转换后的编辑指令"
    )


def _normalize_day_edit_payload(payload: dict) -> dict:
    """兼容模型返回的两种单日编辑格式。"""
    if "spot_name" in payload and "meal_name" in payload and "daily_note" in payload:
        return payload

    normalized = dict(payload)

    spots = payload.get("spots")
    if isinstance(spots, list) and spots:
        first_spot = spots[0] or {}
        normalized.setdefault("spot_name", first_spot.get("name", ""))
        normalized.setdefault("spot_description", first_spot.get("description", ""))

    meals = payload.get("meals")
    if isinstance(meals, list) and meals:
        first_meal = meals[0] or {}
        normalized.setdefault("meal_name", first_meal.get("name", ""))
        normalized.setdefault("meal_notes", first_meal.get("notes", ""))

    notes = payload.get("notes")
    if isinstance(notes, list) and notes:
        normalized.setdefault("daily_note", notes[-1] or "")

    return normalized


def _extract_entity_names(contexts: list[str], pattern: str) -> list[str]:
    """从 RAG 上下文中提取匹配 pattern 的实体名称列表。"""
    names: list[str] = []
    seen: set[str] = set()
    for ctx in contexts:
        for match in re.finditer(pattern, ctx):
            name = match.group(1).strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _extract_json_object(raw_text: str) -> str | None:
    """从模型原始文本中尽量提取 JSON 对象字符串。"""
    text = raw_text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return None

    return text[start_index : end_index + 1]


def collect_trip_context(
    destination: str,
    preferences: list[str] | None = None,
    pace: str | None = None,
    special_notes: str | None = None,
    top_k: int = 5,
) -> tuple[list[str], dict[str, int], dict[str, int], dict[str, int]]:
    """收集本地攻略片段。返回 (contexts, rewrite_usage, rerank_usage, embedding_usage)。"""
    return get_destination_guide_context(
        destination=destination,
        preferences=preferences,
        pace=pace,
        special_notes=special_notes,
        top_k=top_k,
    )


def _build_chat_llm():
    """创建通用 ChatOpenAI 实例。"""
    if not LLM_API_KEY:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.3,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL or None,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
        # qwen3.x 为思考型模型：默认内部推理会消耗大量时间与 token，
        # 行程生成/编辑/对话都要求"只输出 JSON"，关闭思考即可加速。
        extra_body={"enable_thinking": False},
    )


def _extract_token_usage(response) -> dict[str, int]:
    """从 LangChain AIMessage 中提取 token 使用量。"""
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    metadata = getattr(response, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage", {})
    if token_usage:
        usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
        usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
    return usage


def generate_planner_draft(
    request: TripRequest,
    rag_contexts: list[str],
    day_count: int,
) -> tuple[PlannerDraft | None, dict[str, int]]:
    """
    使用 LangChain 生成结构化行程草稿。返回 (draft, token_usage)。

    如果当前环境还没有准备好模型调用条件，就返回 None，
    这样 service 层还能回退到规则版实现。
    """
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    llm = _build_chat_llm()
    if llm is None:
        return None, empty_usage

    guide_context = "\n\n".join(rag_contexts) if rag_contexts else "暂无本地攻略上下文。"

    # 从上下文中提取真实商户名，强制 LLM 使用
    hotel_names = _extract_entity_names(rag_contexts, r"【([^】]*(?:酒店|民宿|客栈|宾馆|饭店|旅馆|旅店)[^】]*)】")
    restaurant_names = _extract_entity_names(rag_contexts, r"【([^】]*(?:餐厅|小吃|火锅|菜|饭|面|汤|粥|粉|私房菜)[^】]*)】")
    hotel_list = "、".join(hotel_names[:6]) if hotel_names else "暂无"
    restaurant_list = "、".join(restaurant_names[:6]) if restaurant_names else "暂无"

    system_prompt = (
        "你是一名旅行规划助手。"
        "请用中文生成简洁的结构化旅行草稿。"
        "需要遵守用户给出的目的地、预算、节奏和本地攻略上下文。"
        "你必须只输出一个 JSON 对象，不要输出 Markdown，不要输出解释文字，不要输出代码块。"
        "输出内容必须严格符合给定的结构化字段要求。"
        "餐饮和住宿必须使用上下文中提供的真实商户名称，禁止使用泛称。"
        "如果用户在额外备注里提出了明确诉求，例如看日落、不想早起、少辣、拍照等，你要优先把这些诉求落实到具体某一天的主要景点或当天安排里，而不是只写成泛泛的提示。"
        "如果用户明确提到想看日落，请优先把适合看日落的地点安排为某一天的主要景点，或至少让当天主景点与日落安排保持强关联。"
    )

    human_prompt = f"""
目的地：{request.destination}
出发日期：{request.start_date.isoformat()}
结束日期：{request.end_date.isoformat()}
天数：{day_count}
人数：{request.travelers}
预算：{request.budget}
偏好：{'、'.join(request.preferences) if request.preferences else '无特别偏好'}
节奏：{request.pace or '适中'}
饮食偏好：{'、'.join(request.dietary_preferences) if request.dietary_preferences else '无'}
酒店档次：{request.hotel_level or '舒适型'}
额外备注：{request.special_notes or '无'}

本地攻略上下文：
{guide_context}

可选的真实酒店名称（住宿安排必须从中选择）：
{hotel_list}

可选的真实餐厅名称（餐饮建议必须从中选择）：
{restaurant_list}

要求：
1. 输出一个整体 summary。
2. 输出 {day_count} 天的 daily draft。
3. 每天只给一个主要景点、一个餐饮建议和一条当天备注。
4. tips 保持简洁。
5. day_index 必须从 1 到 {day_count}。
6. 如果额外备注里有”想看日落””不想早起”这类明确要求，必须在 days 中体现，不要只放到 tips。
7. 如果安排了看日落，当天的 spot_name 应尽量就是适合看日落的地点，或与 daily_note 中的日落安排保持一致，避免”主景点”和”日落地点”完全割裂。
8. 每天的安排要符合”轻松”节奏，避免过满、避免太早出发。
9. meal_name 必须从”可选的真实餐厅名称”列表中选择，不要用泛称。例如用”泸州幺妹私房菜(望花路店)”而不要用”当地私房菜”。
10. 住宿安排必须从”可选的真实酒店名称”列表中选择，严禁使用”舒适型住宿””当地酒店””XX 舒适型住宿 1”等泛称。例如用”北京中关村皇冠假日酒店”而不要用”北京 舒适型住宿 1”。
11. 只返回 JSON 对象，不要返回任何额外说明，不要使用 ```json 代码块。

JSON 结构示例：
{{
  "summary": "整体概述",
  "tips": ["提示1", "提示2"],
  "days": [
    {{
      "day_index": 1,
      "theme": "当天主题",
      "spot_name": "主要景点",
      "spot_description": "景点推荐理由",
      "meal_name": "餐饮名称",
      "meal_notes": "餐饮说明",
      "daily_note": "当天备注"
    }}
  ]
}}
"""

    print("[trip_planner_agent] 准备调用大模型...")
    print(f"[trip_planner_agent] model = {LLM_MODEL}")
    print(f"[trip_planner_agent] base_url = {LLM_BASE_URL or '<DEFAULT>'}")
    print(f"[trip_planner_agent] timeout = {LLM_TIMEOUT_SECONDS}s")
    print(f"[trip_planner_agent] max_retries = {LLM_MAX_RETRIES}")

    try:
        response = llm.invoke(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )
    except Exception as exc:
        print(f"[trip_planner_agent] 大模型调用失败: {type(exc).__name__}: {exc}")
        return None, empty_usage

    token_usage = _extract_token_usage(response)
    print(f"[trip_planner_agent] 大模型调用完成。token: prompt={token_usage['prompt_tokens']}, completion={token_usage['completion_tokens']}")

    raw_text = getattr(response, "content", "")
    if isinstance(raw_text, list):
        raw_text = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in raw_text
        )

    json_text = _extract_json_object(str(raw_text))
    if json_text is None:
        print("[trip_planner_agent] 未能从模型返回中提取 JSON。")
        print(f"[trip_planner_agent] 原始返回预览: {str(raw_text)[:300]}")
        return None, token_usage

    try:
        result = PlannerDraft.model_validate(json.loads(json_text))
    except Exception as exc:
        print(f"[trip_planner_agent] JSON 解析失败: {type(exc).__name__}: {exc}")
        print(f"[trip_planner_agent] 原始返回预览: {str(raw_text)[:300]}")
        return None, token_usage

    if len(result.days) != day_count:
        print(
            "[trip_planner_agent] 结构化结果天数不匹配，"
            f"expected={day_count}, actual={len(result.days)}"
        )
        return None, token_usage

    return result, token_usage


def _dynamic_candidate_payload(candidates: list[PlaceCandidate]) -> list[dict[str, str]]:
    """只把 Planner 做选择所需的稳定字段放入提示词。"""
    return [
        {
            "poi_id": candidate.poi_id,
            "name": candidate.name,
            "district": candidate.district or "",
            "address": candidate.address or "",
            "type": candidate.type_name or "",
        }
        for candidate in candidates
    ]


def generate_dynamic_planner_draft(
    request: TripRequest,
    candidate_pool: CityCandidatePool,
    day_count: int,
) -> tuple[DynamicPlannerDraft | None, dict[str, int]]:
    """让模型只能通过 POI ID 从动态候选池中选择行程实体。"""
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    llm = _build_chat_llm()
    if llm is None:
        return None, empty_usage

    candidate_payload = {
        category.value: _dynamic_candidate_payload(
            candidate_pool.candidates_for(category)
        )
        for category in PlaceCandidateCategory
    }
    system_prompt = (
        "你是旅行规划助手。请根据用户需求从给定的高德 POI 候选中编排行程。"
        "景点、餐饮和住宿只能通过候选中的 poi_id 选择，禁止输出候选池外的地点，"
        "禁止自行创造或改写 poi_id。不得编造价格、开放时间、星级、评分或实时营业状态。"
        "只输出一个 JSON 对象，不要输出 Markdown 或解释。"
    )
    human_prompt = f"""
目的地：{request.destination}
出发日期：{request.start_date.isoformat()}
结束日期：{request.end_date.isoformat()}
天数：{day_count}
人数：{request.travelers}
预算：{request.budget}
偏好：{'、'.join(request.preferences) if request.preferences else '常规旅行体验'}
节奏：{request.pace or '适中'}
饮食偏好：{'、'.join(request.dietary_preferences) if request.dietary_preferences else '无'}
酒店档次：{request.hotel_level or '舒适型'}
额外要求：{request.special_notes or '无'}

候选池：
{json.dumps(candidate_payload, ensure_ascii=False, separators=(',', ':'))}

要求：
1. 返回 {day_count} 天，day_index 必须从 1 连续到 {day_count}。
2. 每天选择一个 spot_poi_id 和一个 meal_poi_id，整趟行程选择一个 hotel_poi_id。
3. 所有 ID 必须逐字来自对应类别候选；不要在名称字段中返回地点。
4. 尽量避免重复景点和餐饮，并结合区域、偏好、节奏与额外要求安排。
5. 只返回以下 JSON 结构：
{{
  "summary": "整体概述",
  "tips": ["旅行提示"],
  "hotel_poi_id": "住宿候选 ID",
  "days": [
    {{
      "day_index": 1,
      "theme": "当天主题",
      "spot_poi_id": "景点候选 ID",
      "spot_start_time": "10:00",
      "spot_end_time": "12:00",
      "spot_reason": "选择理由",
      "meal_poi_id": "餐饮候选 ID",
      "meal_notes": "用餐说明",
      "daily_note": "当天说明"
    }}
  ]
}}
"""

    print("[trip_planner_agent] 准备调用动态城市 Planner...")
    try:
        response = llm.invoke(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )
    except Exception as exc:
        print(
            "[trip_planner_agent] 动态城市 Planner 调用失败: "
            f"{type(exc).__name__}: {exc}"
        )
        return None, empty_usage

    token_usage = _extract_token_usage(response)
    raw_text = getattr(response, "content", "")
    if isinstance(raw_text, list):
        raw_text = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in raw_text
        )

    json_text = _extract_json_object(str(raw_text))
    if json_text is None:
        print("[trip_planner_agent] 未能从动态城市 Planner 返回中提取 JSON。")
        return None, token_usage

    try:
        result = DynamicPlannerDraft.model_validate(json.loads(json_text))
    except Exception as exc:
        print(
            "[trip_planner_agent] 动态城市 Planner JSON 解析失败: "
            f"{type(exc).__name__}: {exc}"
        )
        return None, token_usage

    expected_indexes = list(range(1, day_count + 1))
    actual_indexes = sorted(day.day_index for day in result.days)
    if len(result.days) != day_count or actual_indexes != expected_indexes:
        print(
            "[trip_planner_agent] 动态城市 Planner 天数或 day_index 不匹配: "
            f"expected={expected_indexes}, actual={actual_indexes}"
        )
        return None, token_usage

    return result, token_usage


def generate_day_edit_draft(
    request: TripEditRequest,
    target_day: DayPlan,
) -> tuple[DayEditDraft | None, dict[str, int]]:
    """
    使用 LLM 生成单日编辑草稿。返回 (draft, token_usage)。

    这个函数只负责产出目标那一天的编辑结果，
    最终如何合并回完整 itinerary 由 service 层处理。
    """
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    llm = _build_chat_llm()
    if llm is None:
        return None, empty_usage

    current_day_payload = {
        "day_index": target_day.day_index,
        "date": target_day.date.isoformat() if target_day.date else None,
        "theme": target_day.theme,
        "spots": [spot.model_dump(mode="json") for spot in target_day.spots],
        "meals": [meal.model_dump(mode="json") for meal in target_day.meals],
        "notes": list(target_day.notes),
    }

    current_itinerary_payload = request.current_itinerary.model_dump(mode="json")

    system_prompt = (
        "你是一名旅行行程编辑助手。"
        "请根据用户编辑指令，只重写目标那一天的核心安排。"
        "你必须只输出一个 JSON 对象，不要输出 Markdown，不要输出解释文字，不要输出代码块。"
        "编辑结果要尽量保留原 itinerary 的整体风格、预算结构和轻松程度。"
    )

    human_prompt = f"""
当前完整 itinerary：
{json.dumps(current_itinerary_payload, ensure_ascii=False, indent=2)}

需要重点编辑的目标 day：
{json.dumps(current_day_payload, ensure_ascii=False, indent=2)}

用户编辑指令：{request.user_instruction}
编辑范围：{request.edit_scope or '未指定'}
需要尽量保留的约束：{', '.join(request.preserve_constraints) if request.preserve_constraints else '无'}

要求：
1. 只输出目标那一天编辑后的结果。
2. 如果用户要求“更轻松”“不要安排太满”，请减少固定景点压力，让备注更自然。
3. 尽量延续原 itinerary 的城市、风格、餐饮语气和预算结构。
4. 不要输出额外字段。
5. 只返回 JSON 对象。

JSON 结构示例：
{{
  "theme": "编辑后的当天主题",
  "spot_name": "编辑后的主要景点",
  "spot_description": "编辑后的景点说明",
  "meal_name": "编辑后的餐饮名称",
  "meal_notes": "编辑后的餐饮说明",
  "daily_note": "编辑后的当天备注"
}}
"""

    print("[trip_planner_agent] 准备调用大模型进行单日编辑...")
    print(f"[trip_planner_agent] model = {LLM_MODEL}")
    print(f"[trip_planner_agent] base_url = {LLM_BASE_URL or '<DEFAULT>'}")

    try:
        response = llm.invoke(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )
    except Exception as exc:
        print(f"[trip_planner_agent] 单日编辑调用失败: {type(exc).__name__}: {exc}")
        _raise_if_quota_error(exc)
        return None, empty_usage

    token_usage = _extract_token_usage(response)
    print(f"[trip_planner_agent] 单日编辑调用完成。token: prompt={token_usage['prompt_tokens']}, completion={token_usage['completion_tokens']}")

    raw_text = getattr(response, "content", "")
    if isinstance(raw_text, list):
        raw_text = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in raw_text
        )

    json_text = _extract_json_object(str(raw_text))
    if json_text is None:
        print("[trip_planner_agent] 未能从单日编辑结果中提取 JSON。")
        print(f"[trip_planner_agent] 原始返回预览: {str(raw_text)[:300]}")
        return None, token_usage

    try:
        payload = json.loads(json_text)
        if not isinstance(payload, dict):
            raise ValueError("单日编辑结果不是 JSON 对象。")
        normalized_payload = _normalize_day_edit_payload(payload)
        return DayEditDraft.model_validate(normalized_payload), token_usage
    except Exception as exc:
        print(f"[trip_planner_agent] 单日编辑 JSON 解析失败: {type(exc).__name__}: {exc}")
        print(f"[trip_planner_agent] 原始返回预览: {str(raw_text)[:300]}")
        return None, token_usage


def _summarize_itinerary_for_chat(itinerary: Itinerary) -> str:
    """把完整 itinerary 压缩成对话上下文友好的摘要，控制 token 消耗。"""
    payload = itinerary.model_dump(mode="json")
    days_summary = []
    for day in payload.get("days", []):
        spots = "、".join(spot.get("name", "") for spot in day.get("spots", []) if spot.get("name"))
        meals = "、".join(meal.get("name", "") for meal in day.get("meals", []) if meal.get("name"))
        hotel = day.get("hotel") or {}
        days_summary.append(
            {
                "day": day.get("day_index"),
                "date": day.get("date"),
                "theme": day.get("theme"),
                "spots": spots or "未安排",
                "meals": meals or "未安排",
                "hotel": hotel.get("name") or "未安排",
            }
        )
    summary = {
        "destination": payload.get("destination"),
        "summary": payload.get("summary"),
        "estimated_budget": payload.get("estimated_budget"),
        "days": days_summary,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def generate_chat_reply(
    request: TripChatRequest,
) -> tuple[ChatIntentDraft | None, dict[str, int]]:
    """
    对话式行程助手：解析用户消息意图并生成回复。

    返回 (intent_draft, token_usage)。
    - intent = "adjust_day"：service 层将 edit_instruction 转交单日编辑链路
    - intent = "general_chat"：直接返回 reply
    """
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    llm = _build_chat_llm()
    if llm is None:
        return None, empty_usage

    conversation_text = "\n".join(
        f"{'用户' if message.role == 'user' else '助手'}：{message.content}"
        for message in request.messages[-10:]
    )
    context = request.context
    context_text = (
        f"用户当前所在面板：{context.active_panel or '未知'}；"
        f"当前选中的天：第 {context.selected_day or 1} 天"
    )

    system_prompt = (
        "你是旅行工作台的 AI 行程助手。用户会和你对话来调整旅行计划。"
        "你的回复必须简短、可操作（不超过 5 行），符合产品语气。"
        "判断用户意图："
        "- 如果用户要求修改行程（调整节奏、换景点、增减安排、改预算侧重等），"
        "intent 填 adjust_day，并从消息中推断目标天（未指明时用当前选中的天），"
        "把用户诉求改写成一句明确的编辑指令放入 edit_instruction。"
        "- 如果只是提问或闲聊（问景点信息、天气、注意事项等），intent 填 general_chat，"
        "reply 直接回答（可基于行程摘要）。"
        "你必须只输出一个 JSON 对象，不要输出 Markdown，不要输出解释文字。"
    )

    human_prompt = f"""
当前行程摘要：
{_summarize_itinerary_for_chat(request.current_itinerary)}

{context_text}

最近对话：
{conversation_text or '（无）'}

用户新消息：{request.messages[-1].content if request.messages else ''}

要求：
1. 只返回 JSON 对象，结构如下：
{{
  "reply": "给用户的回复",
  "intent": "adjust_day 或 general_chat",
  "day_index": 目标天数字（general_chat 时可为 null）,
  "edit_instruction": "编辑指令字符串（general_chat 时可为 null）"
}}
2. intent=adjust_day 时，reply 简要确认你要做什么调整（例如：好的，我来把第 3 天调整得更轻松）。
3. 如果用户要求修改的目标天不存在，intent 填 general_chat，reply 里说明可调整的天数范围。
"""

    print("[trip_planner_agent] 准备调用大模型进行对话意图解析...")
    try:
        response = llm.invoke(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )
    except Exception as exc:
        print(f"[trip_planner_agent] 对话意图解析调用失败: {type(exc).__name__}: {exc}")
        _raise_if_quota_error(exc)
        return None, empty_usage

    token_usage = _extract_token_usage(response)
    raw_text = getattr(response, "content", "")
    if isinstance(raw_text, list):
        raw_text = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in raw_text
        )

    json_text = _extract_json_object(str(raw_text))
    if json_text is None:
        print("[trip_planner_agent] 未能从对话意图解析结果中提取 JSON。")
        print(f"[trip_planner_agent] 原始返回预览: {str(raw_text)[:300]}")
        return None, token_usage

    try:
        payload = json.loads(json_text)
        if not isinstance(payload, dict):
            raise ValueError("对话意图解析结果不是 JSON 对象。")
        return ChatIntentDraft.model_validate(payload), token_usage
    except Exception as exc:
        print(f"[trip_planner_agent] 对话意图 JSON 解析失败: {type(exc).__name__}: {exc}")
        print(f"[trip_planner_agent] 原始返回预览: {str(raw_text)[:300]}")
        return None, token_usage
