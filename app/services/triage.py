"""AI 智能分诊：独立提示词模板、10 秒超时、固定输出结构、失败兜底。"""
import json
import os

import httpx

from app import config

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "triage.txt"
)
DISCLAIMER = "本建议由 AI 生成，仅供参考，需医生确认"
VALID_URGENCY = ("普通", "尽快", "急诊")


def load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def fallback(reason: str = ""):
    data = {
        "department": "全科门诊",
        "urgency": "普通",
        "advice": ["请到门诊导诊台补充症状持续时间、体温等信息", "如症状加重请立即就医"],
        "disclaimer": DISCLAIMER,
        "source": "fallback",
    }
    if reason:
        data["note"] = reason
    return data


def _normalize(payload: dict):
    department = str(payload.get("department", "")).strip()
    urgency = str(payload.get("urgency", "")).strip()
    advice = payload.get("advice", [])
    if not department:
        raise ValueError("缺少 department")
    if urgency not in VALID_URGENCY:
        urgency = "普通"
    if isinstance(advice, str):
        advice = [advice]
    if not isinstance(advice, list):
        advice = []
    advice = [str(x).strip() for x in advice if str(x).strip()][:5]
    return {
        "department": department,
        "urgency": urgency,
        "advice": advice,
        "disclaimer": DISCLAIMER,
        "source": "ai",
    }


def triage(symptoms: str):
    symptoms = (symptoms or "").strip()
    if len(symptoms) < 2:
        return fallback("症状描述过短，已给出兜底建议")
    if not config.DEEPSEEK_API_KEY:
        return fallback("未配置 AI 服务密钥，当前使用兜底建议")

    try:
        response = httpx.post(
            config.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer " + config.DEEPSEEK_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "model": config.DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": load_prompt()},
                    {"role": "user", "content": "患者症状：" + symptoms},
                ],
                "temperature": 0.2,
            },
            timeout=config.TRIAGE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.lower().startswith("json"):
                content = content[4:]
        return _normalize(json.loads(content.strip()))
    except Exception:
        return fallback("AI 服务暂时不可用，已降级为兜底建议")
