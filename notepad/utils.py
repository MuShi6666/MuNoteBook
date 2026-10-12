"""通用工具函数"""
from __future__ import annotations

from pathlib import Path

# 读取文件时依次尝试的编码（UTF-8 优先，兼容中文 Windows 上的 GBK 文件）
CANDIDATE_ENCODINGS = ("utf-8-sig", "utf-8", "gbk")


def decodeText(data: bytes) -> tuple[str, str]:
    """把字节流按候选编码解码为文本，返回 (文本, 实际编码名)"""
    for enc in CANDIDATE_ENCODINGS:
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    # 都失败时按 UTF-8 容错解码，保证不崩
    return data.decode("utf-8", errors="replace"), "utf-8"


def readFile(path: str) -> tuple[str, str]:
    """读取文本文件，返回 (文本, 编码)"""
    return decodeText(Path(path).read_bytes())


def writeText(path: str, text: str) -> None:
    """以 UTF-8 无 BOM 写出，保持 LF 换行不做转换"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def displayName(path: str | None) -> str:
    """用于标题 / 提示的文件名，无路径时显示“未命名”"""
    return Path(path).name if path else "未命名"
