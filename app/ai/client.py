"""Ollama 客户端封装：模型名可配置，失败时返回清晰错误。"""
from __future__ import annotations

import logging
from typing import Optional

from .. import config

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3.5:4b"


def get_model_name() -> str:
    """从配置文件读取模型名，缺省 qwen3.5:4b。"""
    cfg = config.data_dir() / "settings.txt"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("model="):
                return line.split("=", 1)[1].strip() or DEFAULT_MODEL
    return DEFAULT_MODEL


def set_model_name(name: str) -> None:
    cfg = config.data_dir() / "settings.txt"
    lines = []
    if cfg.exists():
        lines = [l for l in cfg.read_text(encoding="utf-8").splitlines() if not l.startswith("model=")]
    lines.append(f"model={name}")
    cfg.write_text("\n".join(lines), encoding="utf-8")


def is_available() -> bool:
    """检测本地 Ollama 是否在运行。"""
    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434")
        client.list()
        return True
    except Exception as e:
        logger.info("Ollama 不可用：%s", e)
        return False


def chat(prompt: str, images: Optional[list[str]] = None, json_mode: bool = True) -> str:
    """调用本地模型，返回文本。失败抛异常。"""
    import ollama

    client = ollama.Client(host="http://localhost:11434")
    model = get_model_name()
    opts = {"temperature": 0.1}
    fmt = "json" if json_mode else None
    resp = client.generate(
        model=model,
        prompt=prompt,
        images=images or [],
        format=fmt,
        options=opts,
    )
    return resp["response"]
