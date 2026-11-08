"""Ollama 客户端封装：模型名可配置，失败时返回清晰错误。"""
from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3.5:4b"


def get_model_name() -> str:
    from ..settings import load_settings
    return load_settings().get("model") or DEFAULT_MODEL


def set_model_name(name: str) -> None:
    from ..settings import save_settings
    if not name.strip():
        raise ValueError("模型名不能为空")
    save_settings(model=name.strip())


def is_available() -> bool:
    """检测本地 Ollama 是否在运行。"""
    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434", timeout=3, trust_env=False)
        client.list()
        return True
    except Exception as e:
        logger.info("Ollama 不可用：%s", e)
        return False


def chat(prompt: str, images: Optional[list[str]] = None, json_mode: bool = True, schema=None) -> str:
    """调用本地模型，返回文本。失败抛异常。"""
    import ollama

    client = ollama.Client(host="http://localhost:11434", timeout=120, trust_env=False)
    model = get_model_name()
    opts = {"temperature": 0}
    fmt = schema if schema is not None else ("json" if json_mode else None)
    if schema is not None:
        import json
        prompt += "\n输出格式JSON Schema（日期YYYY-MM-DD，时间HH:MM）：\n" + json.dumps(schema, ensure_ascii=False)
    resp = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt, "images": images or []}],
        format=fmt,
        options=opts,
        think=False,
    )
    return resp["message"]["content"]
