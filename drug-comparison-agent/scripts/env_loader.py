#!/usr/bin/env python3
"""从 skill 根目录读取 .env，注入 os.environ（纯标准库，零依赖）。

启动时由 pipeline 调用一次。仅当 .env 存在时加载；已被系统 env 设过的键不覆盖
（系统 env 可临时覆盖 .env）。.env 位置：skill 根目录（scripts/ 的上一级），
按脚本 __file__ 定位，与运行时 cwd 无关。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def _skill_root() -> Path:
    # scripts/env_loader.py → scripts/ → skill 根
    return Path(__file__).resolve().parent.parent


def load_skill_env(env_path: Optional[Path] = None) -> Dict[str, str]:
    """读取 .env 并注入 os.environ（不覆盖已存在值）。返回本次实际加载的键值。"""
    path = env_path or (_skill_root() / ".env")
    loaded: Dict[str, str] = {}
    if not path.exists():
        return loaded
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded
