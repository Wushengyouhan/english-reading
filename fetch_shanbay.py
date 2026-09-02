#!/usr/bin/env python3
"""从扇贝短文网址抓取标题和正文，保存为同名 txt。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

API_URL = "https://apiv3.shanbay.com/news/articles/{article_id}"
ARTICLE_ID_RE = re.compile(r"/articles/([A-Za-z0-9]+)")
SHARE_ID_RE = re.compile(r"/news/([A-Za-z0-9]+)")
BARE_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
INVALID_FILENAME_RE = re.compile(r'[\\/:*?"<>|]+')


def parse_article_id(url_or_id: str) -> str:
    text = url_or_id.strip()
    match = ARTICLE_ID_RE.search(text)
    if match:
        return match.group(1)
    match = SHARE_ID_RE.search(text)
    if match:
        return match.group(1)
    if BARE_ID_RE.fullmatch(text):
        return text
    raise ValueError(f"无法从输入中解析文章 ID: {url_or_id}")


def fetch_article(article_id: str) -> dict:
    request = urllib.request.Request(
        API_URL.format(article_id=article_id),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"请求失败 HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络错误: {exc.reason}") from exc

    if not payload.get("title_en") or not payload.get("content"):
        raise RuntimeError("接口返回缺少标题或正文")
    return payload


def extract_paragraphs(content: str) -> list[str]:
    root = ET.fromstring(content)
    paragraphs: list[str] = []
    for para in root.findall("para"):
        sentences = [
            "".join(sent.itertext()).strip()
            for sent in para.findall("sent")
        ]
        sentences = [s for s in sentences if s]
        if sentences:
            paragraphs.append(" ".join(sentences))
    return paragraphs


def safe_filename(number: int, title: str) -> str:
    name = INVALID_FILENAME_RE.sub(" ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        raise ValueError("标题为空，无法生成文件名")
    return f"{number:02d}_{name}.txt"


def save_article(payload: dict, number: int, output_dir: Path) -> Path:
    title = payload["title_en"].strip()
    paragraphs = extract_paragraphs(payload["content"])
    if not paragraphs:
        raise RuntimeError("正文解析为空")

    path = output_dir / safe_filename(number, title)
    path.write_text("\n\n".join(paragraphs) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="把扇贝短文保存为 序号_英文标题.txt")
    parser.add_argument("url", help="扇贝短文网址，或文章 ID")
    parser.add_argument("number", type=int, help="序号，例如 1 会生成 01_标题.txt")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="保存目录，默认当前目录",
    )
    args = parser.parse_args()

    if args.number < 1:
        print("错误: 序号必须是大于 0 的整数", file=sys.stderr)
        return 1

    try:
        article_id = parse_article_id(args.url)
        payload = fetch_article(article_id)
        path = save_article(
            payload,
            args.number,
            Path(args.output_dir).expanduser().resolve(),
        )
    except (ValueError, RuntimeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    print(f"已保存: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
