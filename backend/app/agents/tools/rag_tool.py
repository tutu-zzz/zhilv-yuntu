import json
import logging
from functools import lru_cache

from app.config import (
    BACKEND_DIR,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)
from app.rag.retriever import retrieve_travel_guide


logger = logging.getLogger(__name__)
RETRIEVAL_RULES_PATH = BACKEND_DIR / "data" / "retrieval_rules.json"


# rag_tool.py 自己不直接检索，
# 它只负责把"旅行规划语义"转成"检索查询"。
def _append_unique(parts: list[str], value: str) -> None:
    normalized = value.strip()
    if not normalized:
        return
    if normalized not in parts:
        parts.append(normalized)


@lru_cache(maxsize=1)
def _load_retrieval_rules() -> dict:
    """读取版本化检索规则；配置损坏时保持空规则，避免阻断主链路。"""
    try:
        raw_data = json.loads(RETRIEVAL_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unable to load retrieval rules from %s: %s", RETRIEVAL_RULES_PATH, exc)
        return {"global_rules": [], "destinations": {}}

    if not isinstance(raw_data, dict):
        logger.warning("Retrieval rules must be a JSON object: %s", RETRIEVAL_RULES_PATH)
        return {"global_rules": [], "destinations": {}}

    return raw_data


def _valid_rules(value: object) -> list[dict[str, list[str]]]:
    """过滤格式错误的单条规则，保证规则配置不会破坏 query fallback。"""
    if not isinstance(value, list):
        return []

    valid_rules: list[dict[str, list[str]]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        triggers = item.get("triggers")
        keywords = item.get("keywords")
        if not isinstance(triggers, list) or not isinstance(keywords, list):
            continue
        if not all(isinstance(term, str) for term in [*triggers, *keywords]):
            continue
        if triggers and keywords:
            valid_rules.append({"triggers": triggers, "keywords": keywords})
    return valid_rules


def _destination_rules(destination: str | None) -> list[dict[str, list[str]]]:
    """返回通用规则及当前目的地规则，兼容“大理市”等输入。"""
    config = _load_retrieval_rules()
    rules = _valid_rules(config.get("global_rules"))
    if not destination:
        return rules

    destinations = config.get("destinations")
    if not isinstance(destinations, dict):
        return rules

    for configured_destination, destination_config in destinations.items():
        if not isinstance(configured_destination, str) or configured_destination not in destination:
            continue
        if not isinstance(destination_config, dict):
            continue
        rules.extend(_valid_rules(destination_config.get("rules")))
    return rules


def _extract_note_keywords(special_notes: str | None, destination: str | None = None) -> list[str]:
    """根据版本化规则，从用户备注中提炼适合检索的关键词。"""
    if not special_notes:
        return []

    keywords: list[str] = []
    note = special_notes.strip()
    for rule in _destination_rules(destination):
        if any(trigger in note for trigger in rule["triggers"]):
            for value in rule["keywords"]:
                _append_unique(keywords, value)

    return keywords


def _build_chat_llm():
    """创建 ChatOpenAI 实例，用于 Query Rewrite。"""
    if not LLM_API_KEY:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.2,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL or None,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
        # qwen3.x 系列为思考型模型，默认会先生成大量内部推理再输出结果，
        # 关闭思考可显著降低 rewrite 延迟（实测 30s -> 秒级）。
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


def llm_rewrite_query(
    destination: str,
    preferences: list[str] | None = None,
    pace: str | None = None,
    special_notes: str | None = None,
) -> tuple[str | None, dict[str, int]]:
    """用 LLM 把用户旅行需求改写成适合向量检索的 query。返回 (query, token_usage)。"""
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    llm = _build_chat_llm()
    if llm is None:
        return None, empty_usage

    system_prompt = (
        "你是一个 RAG 检索 query 改写专家。"
        "你的任务是把用户的旅行需求改写成适合向量检索的关键词组合。"
        "输出要求："
        "1. 只输出一行检索关键词，用空格分隔，总长不超过 20 个字"
        "2. 不要输出解释、标点或任何多余文字"
        "3. 关键词要具体，优先包含景点名称、活动类型、场景特征"
        "4. 包含目的地城市名"
        "示例输出：大理 洱海 拍照 美食 古镇"
    )

    parts = [f"目的地：{destination}"]
    if preferences:
        parts.append(f"偏好：{'、'.join(preferences)}")
    if pace:
        parts.append(f"节奏：{pace}")
    if special_notes:
        parts.append(f"备注：{special_notes}")
    human_prompt = "\n".join(parts)

    try:
        response = llm.invoke([
            ("system", system_prompt),
            ("human", human_prompt),
        ])
        token_usage = _extract_token_usage(response)
        raw_text = getattr(response, "content", "")
        if isinstance(raw_text, list):
            raw_text = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in raw_text
            )
        query = raw_text.strip()
        if query and len(query) <= 60:
            logger.info("llm_rewrite_query: input=%s -> output=%s", human_prompt, query)
            return query, token_usage
        if query:
            # 轻量模型可能无视"只输出关键词"指令输出长篇内容：
            # 超长结果视为无效，回退规则级改写，避免拖慢检索并浪费 token。
            logger.warning(
                "llm_rewrite_query: output too long (%d chars), falling back to rule-based",
                len(query),
            )
    except Exception:
        logger.warning("llm_rewrite_query failed, falling back to rule-based", exc_info=True)

    return None, empty_usage


def _rule_based_query(
    destination: str,
    preferences: list[str] | None = None,
    pace: str | None = None,
    special_notes: str | None = None,
) -> str:
    """规则级 Query Rewrite，作为 LLM Rewrite 的 fallback。"""
    parts: list[str] = [destination]

    if preferences:
        for preference in preferences:
            _append_unique(parts, preference)

    if pace:
        _append_unique(parts, pace)

    for keyword in _extract_note_keywords(special_notes, destination=destination):
        _append_unique(parts, keyword)

    for stable_term in ["景点", "行程", "攻略", "推荐", "餐饮", "住宿"]:
        _append_unique(parts, stable_term)

    return " ".join(part for part in parts if part).strip()


def build_destination_query(
    destination: str,
    preferences: list[str] | None = None,
    pace: str | None = None,
    special_notes: str | None = None,
) -> tuple[str, dict[str, int]]:
    """把目的地、偏好、节奏和备注改写成更贴近检索场景的 query。返回 (query, token_usage)。"""
    llm_query, token_usage = llm_rewrite_query(
        destination=destination,
        preferences=preferences,
        pace=pace,
        special_notes=special_notes,
    )
    if llm_query:
        return llm_query, token_usage

    logger.info("build_destination_query: LLM rewrite unavailable, using rule-based")
    return _rule_based_query(
        destination=destination,
        preferences=preferences,
        pace=pace,
        special_notes=special_notes,
    ), {"prompt_tokens": 0, "completion_tokens": 0}


def _build_destination_query(
    destination: str,
    preferences: list[str] | None = None,
    pace: str | None = None,
    special_notes: str | None = None,
) -> tuple[str, dict[str, int]]:
    """兼容旧调用，内部转到公开的 query 构造函数。"""
    return build_destination_query(
        destination=destination,
        preferences=preferences,
        pace=pace,
        special_notes=special_notes,
    )


def get_destination_guide_context(
    destination: str,
    preferences: list[str] | None = None,
    pace: str | None = None,
    special_notes: str | None = None,
    top_k: int = 5,
) -> tuple[list[str], dict[str, int], dict[str, int], dict[str, int]]:
    """根据目的地和偏好返回本地攻略片段。返回 (contexts, rewrite_usage, rerank_usage, embedding_usage)。"""
    query, rewrite_usage = build_destination_query(
        destination=destination,
        preferences=preferences,
        pace=pace,
        special_notes=special_notes,
    )
    contexts, rerank_usage, embedding_usage = retrieve_travel_guide(
        query=query, top_k=top_k, destination=destination
    )

    # 补充检索住宿和餐饮 chunk，确保 LLM 能获取真实商户名
    existing_set = set(contexts)
    for supplement_query in [f"{destination} 住宿 酒店 民宿", f"{destination} 餐饮 美食 餐厅"]:
        extra_contexts, extra_rerank, extra_embed = retrieve_travel_guide(
            query=supplement_query, top_k=2, destination=destination
        )
        for ctx in extra_contexts:
            if ctx not in existing_set:
                contexts.append(ctx)
                existing_set.add(ctx)
        rerank_usage["prompt_tokens"] += extra_rerank.get("prompt_tokens", 0)
        rerank_usage["completion_tokens"] += extra_rerank.get("completion_tokens", 0)
        embedding_usage["prompt_tokens"] += extra_embed.get("prompt_tokens", 0)
        embedding_usage["completion_tokens"] += extra_embed.get("completion_tokens", 0)

    return contexts, rewrite_usage, rerank_usage, embedding_usage
