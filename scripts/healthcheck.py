# -*- coding: utf-8 -*-
"""平台「全功能体检」脚本：逐个接口冒烟测试，输出 PASS/FAIL 表。

前置：先把后端跑起来（默认 127.0.0.1:8010），例如：
    cd server && python -m uvicorn app.main:app --port 8010

然后（在项目根目录下）执行：
    python scripts/healthcheck.py
    python scripts/healthcheck.py --base http://127.0.0.1:8010/api

脚本会：
  1. 检查所有只读接口（健康、元信息、题库检索、刷题抽题、错题本、收藏夹、统计、导入日志、档案）
  2. 在一个「临时档案」里跑写入类流程（作答判分、简答自评、收藏、移出错题本、模式切换）
  3. 临时新建/编辑/删除一道题目，验证题库增删改查
  4. 结束时恢复原档案并删除临时档案，尽量不留副作用
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

RESULTS: List[Tuple[str, bool, str]] = []


def _request(method: str, url: str, payload: Optional[dict] = None) -> Tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "ignore")
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw
        return exc.code, body


def check(name: str, method: str, url: str, payload: Optional[dict] = None,
          expect: Tuple[int, ...] = (200, 201)) -> Optional[Any]:
    try:
        status, body = _request(method, url, payload)
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False, f"异常：{exc}"))
        print(f"[FAIL] {name} -> {exc}")
        return None
    ok = status in expect
    detail = f"{method} {url} -> {status}"
    if not ok:
        detail += f" | {str(body)[:200]}"
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  ({status})")
    return body if ok else None


def main() -> None:
    parser = argparse.ArgumentParser(description="平台全功能体检")
    parser.add_argument("--base", default="http://127.0.0.1:8010/api", help="API 根地址")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print("=" * 70)
    print(f"ikao 刷题平台 · 全功能体检   base={base}")
    print("=" * 70)

    t0 = time.time()

    # ---------------------------------------------------------- 只读接口
    health = check("健康检查 /health", "GET", f"{base}/health")
    meta = check("基础元信息 /meta", "GET", f"{base}/meta")
    check("题库分页 /questions", "GET", f"{base}/questions?page=1&page_size=5")
    check("题库题型统计 /questions/stats", "GET", f"{base}/questions/stats")
    check("导入日志 /import/logs", "GET", f"{base}/import/logs?page=1&page_size=5")
    check("Excel 模板 /import/template", "GET", f"{base}/import/template")
    check("题库导出 /questions/export", "GET", f"{base}/questions/export")
    check("档案列表 /profiles", "GET", f"{base}/profiles")
    check("当前档案 /profiles/current", "GET", f"{base}/profiles/current")

    # 找一个真实题目 id 供后续测试
    listing = _request("GET", f"{base}/questions?page=1&page_size=20")[1] or {}
    sample = (listing.get("items") or [{}])[0]
    sample_id = sample.get("id")
    if sample_id:
        check(f"题目详情 /questions/{sample_id}", "GET", f"{base}/questions/{sample_id}")
    else:
        RESULTS.append(("题目详情", True, "题库为空，跳过"))

    check("题干查重 /questions/check-duplicate", "POST", f"{base}/questions/check-duplicate",
          {"title": "这是一道用于查重测试的题干"})

    # ---------------------------------------------------------- 临时档案
    temp_name = f"体检临时档案-{int(time.time())}"
    original = _request("GET", f"{base}/profiles/current")[1] or {}
    temp = check("新建档案 /profiles", "POST", f"{base}/profiles", {"name": temp_name})
    temp_id = (temp or {}).get("id")
    if temp_id:
        check("切换档案 /profiles/{id}/switch", "POST", f"{base}/profiles/{temp_id}/switch")

    check("刷题概览 /practice/stats", "GET", f"{base}/practice/stats")
    for mode in ("sequence", "recite", "random", "wrong", "favorite"):
        check(f"抽题[{mode}] /practice/questions", "GET",
              f"{base}/practice/questions?mode={mode}&count=10&page=1")

    # ---------------------------------------------------------- 作答判分
    page = _request("GET", f"{base}/practice/questions?mode=sequence&count=20&page=1")[1] or {}
    items = page.get("items") or []
    answered_id = None
    if items:
        q = items[0]
        qid = q["id"]
        answered_id = qid
        guess = {"single": "A", "multiple": ["A"], "judge": True, "short": "测试作答"}[q["type"]]
        check("提交作答 /practice/answer", "POST", f"{base}/practice/answer",
              {"question_id": qid, "user_answer": guess, "mode": "sequence", "duration_ms": 1000})
        # 背题模式：验证下发了 answer / analysis
        recite = _request("GET", f"{base}/practice/questions?mode=recite&count=1&page=1")[1] or {}
        first = (recite.get("items") or [{}])[0]
        has_answer = "answer" in first and first.get("answer") is not None
        RESULTS.append(("背题模式下发答案", has_answer, f"answer={first.get('answer')!r}"))
        print(f"[{'PASS' if has_answer else 'FAIL'}] 背题模式下发答案")
        # 非背题模式：不应下发答案
        seq = _request("GET", f"{base}/practice/questions?mode=sequence&count=1&page=1")[1] or {}
        seq_first = (seq.get("items") or [{}])[0]
        no_answer = seq_first.get("answer") is None
        RESULTS.append(("普通模式不下发答案", no_answer, f"answer={seq_first.get('answer')!r}"))
        print(f"[{'PASS' if no_answer else 'FAIL'}] 普通模式不下发答案")
    else:
        RESULTS.append(("提交作答", True, "题库为空，跳过"))

    # 简答题自评（找到简答题才测）
    short_q = _request("GET", f"{base}/practice/questions?mode=sequence&type=short&count=1&page=1")[1] or {}
    short_items = short_q.get("items") or []
    if short_items:
        sid = short_items[0]["id"]
        _request("POST", f"{base}/practice/answer",
                 {"question_id": sid, "user_answer": "自评测试", "mode": "sequence"})
        check("简答自评 /practice/self-evaluate", "POST", f"{base}/practice/self-evaluate",
              {"question_id": sid, "is_correct": True, "mode": "sequence"})
        check("移出错题本 /practice/wrong/{id}", "DELETE", f"{base}/practice/wrong/{sid}",
              expect=(200, 404))
    else:
        RESULTS.append(("简答自评", True, "题库无简答题，跳过"))

    if answered_id:
        check("收藏切换 /practice/favorites/{id}/toggle", "POST",
              f"{base}/practice/favorites/{answered_id}/toggle")
        check("收藏夹 /practice/favorites", "GET", f"{base}/practice/favorites?page=1&page_size=5")
        check("错题本 /practice/wrong", "GET", f"{base}/practice/wrong?page=1&page_size=5")
        check("移出错题本(再次) /practice/wrong/{id}", "DELETE", f"{base}/practice/wrong/{answered_id}",
              expect=(200, 404))

    check("统计看板 /stats/board", "GET", f"{base}/stats/board?trend_days=14")

    # ---------------------------------------------------------- 题库增删改
    created = check("新增题目 /questions", "POST", f"{base}/questions", {
        "type": "single",
        "title": "【体检】以下哪个端口号是 HTTPS 默认端口？",
        "options": [
            {"key": "A", "text": "80"},
            {"key": "B", "text": "443"},
            {"key": "C", "text": "22"},
            {"key": "D", "text": "3389"},
        ],
        "answer": "B",
        "analysis": "HTTPS 默认端口为 443。",
    })
    new_id = (created or {}).get("id")
    if new_id:
        check("编辑题目 /questions/{id}", "PUT", f"{base}/questions/{new_id}", {
            "type": "single",
            "title": "【体检】HTTPS 默认端口是哪个？",
            "options": [
                {"key": "A", "text": "80"},
                {"key": "B", "text": "443"},
                {"key": "C", "text": "22"},
                {"key": "D", "text": "3389"},
            ],
            "answer": "B",
            "analysis": "443。",
        })
        check("删除题目 /questions/{id}", "DELETE", f"{base}/questions/{new_id}")

    # ---------------------------------------------------------- 收尾
    if original.get("id"):
        _request("POST", f"{base}/profiles/{original['id']}/switch")
    if temp_id:
        check("删除临时档案 /profiles/{id}", "DELETE", f"{base}/profiles/{temp_id}")

    # ---------------------------------------------------------- 汇总
    failed = [r for r in RESULTS if not r[1]]
    print("=" * 70)
    print(f"共 {len(RESULTS)} 项：通过 {len(RESULTS) - len(failed)}，失败 {len(failed)}，耗时 {time.time() - t0:.1f}s")
    if failed:
        print("---------- 失败项 ----------")
        for name, _, detail in failed:
            print(f"  ✗ {name}: {detail}")
    print("=" * 70)
    if meta:
        print(f"题库题量：{meta.get('question_count')} | 版本：{meta.get('version')}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
