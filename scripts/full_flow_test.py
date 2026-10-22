# -*- coding: utf-8 -*-
"""ikao 全流程测试：在「临时数据库 + 独立端口」上跑完整业务流程。

特点：
- 使用一次性临时 SQLite 库，不污染正式数据，跑完自动删除；
- 真实启动一个 uvicorn 服务，全部通过 HTTP 调用接口，等价于真人操作；
- 覆盖：导入去重 -> 题库检索 -> 各模式抽题 -> 判分 -> 错题本 -> 收藏 -> 简答自评 -> 统计看板 -> 题库增删改 -> 档案切换 -> 幂等导入。

用法（在项目根目录下，无需先启动后端）：
    python scripts/full_flow_test.py
    python scripts/full_flow_test.py --keep     # 保留临时目录，便于排查
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "server"
SAMPLE_JSON = ROOT / "data" / "sample_questions.json"

BASE = ""  # 由 main() 按临时端口填充
CHECKS: List[Tuple[str, bool, str]] = []


# ------------------------------------------------------------------ 断言
def expect(name: str, ok: bool, detail: Any = "") -> bool:
    ok = bool(ok)
    CHECKS.append((name, ok, str(detail)))
    mark = "PASS" if ok else "FAIL"
    suffix = f"  -> {detail}" if (detail != "" and not ok) else ""
    print(f"[{mark}] {name}{suffix}")
    return ok


# ------------------------------------------------------------------ HTTP
def _request(method: str, path: str, payload: Optional[dict] = None,
             form: Optional[dict] = None, timeout: int = 30) -> Tuple[int, Any]:
    url = BASE + path
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "ignore")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def api(method: str, path: str, payload: Optional[dict] = None, form: Optional[dict] = None) -> Any:
    status, body = _request(method, path, payload, form)
    if status >= 400:
        raise RuntimeError(f"{method} {path} -> {status}: {str(body)[:200]}")
    return body


def status_of(method: str, path: str) -> int:
    return _request(method, path)[0]


# ------------------------------------------------------------------ 服务
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    raise SystemExit("服务启动超时，请检查端口是否被占用或依赖是否安装完整。")


def main() -> None:
    global BASE

    parser = argparse.ArgumentParser(description="ikao 全流程测试")
    parser.add_argument("--keep", action="store_true", help="保留临时数据目录")
    args = parser.parse_args()

    if not SAMPLE_JSON.is_file():
        raise SystemExit(f"缺少样例题库：{SAMPLE_JSON}")

    workdir = Path(tempfile.mkdtemp(prefix="ikao_flow_"))
    db_file = workdir / "ikao.db"

    # 必须在导入 app 之前设置，Settings 才会读到（临时库，绝对不碰正式数据）
    os.environ["IKAO_DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["IKAO_DATA_DIR"] = str(workdir)
    sys.path.insert(0, str(SERVER_DIR))

    import uvicorn

    from app.main import app  # noqa: WPS433  (需在设置环境变量之后导入)

    port = _free_port()
    BASE = f"http://127.0.0.1:{port}/api"

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
        http="h11",
        ws="none",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_ready(port)

    print("=" * 70)
    print(f"ikao 全流程测试   （临时库：{db_file}）")
    print("=" * 70)

    try:
        run_flow()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if args.keep:
            print(f"\n临时目录已保留：{workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    failed = [c for c in CHECKS if not c[1]]
    print("=" * 70)
    print(f"共 {len(CHECKS)} 项断言：通过 {len(CHECKS) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("---------------- 失败明细 ----------------")
        for name, _, detail in failed:
            print(f"  x {name}  -> {detail}")
    print("=" * 70)
    sys.exit(1 if failed else 0)


# ------------------------------------------------------------------ 业务流程
def run_flow() -> None:
    # ---------- 1. 元信息 / 初始状态
    meta = api("GET", "/meta")
    expect("元信息应用名 = ikao", meta.get("app_name") == "ikao", meta.get("app_name"))
    expect("初始题库为空", meta.get("question_count") == 0, meta.get("question_count"))
    default_profile_id = meta.get("current_profile_id")

    # ---------- 2. 导入样例题库（含 1 道重复题）
    result = api("POST", "/import/json", form={"path": str(SAMPLE_JSON), "threshold": "0.9"})
    log_id = result["log_id"]
    expect("导入解析 6 题", result["total"] == 6, result["total"])
    expect("入库 5 题", result["imported"] == 5, result["imported"])
    expect("去重 1 题", result["duplicated"] == 1, result["duplicated"])
    expect("导入无失败", result["failed"] == 0, result["failed"])

    # ---------- 3. 导入日志
    logs = api("GET", "/import/logs?page=1&page_size=10")
    expect("导入日志已记录", logs["total"] >= 1, logs["total"])
    detail = api("GET", f"/import/logs/{log_id}")
    expect("日志明细 6 条", detail["items_total"] == 6, detail["items_total"])

    # ---------- 4. 题库检索
    listing = api("GET", "/questions?page=1&page_size=100")
    expect("题库总数 5", listing["total"] == 5, listing["total"])
    by_type: Dict[str, List[int]] = {}
    for item in listing["items"]:
        by_type.setdefault(item["type"], []).append(item["id"])
    expect(
        "四种题型齐全",
        {"single", "multiple", "judge", "short"} <= set(by_type),
        list(by_type),
    )
    stats_by_type = api("GET", "/questions/stats")
    expect("题型统计总数一致", stats_by_type["total"] == 5, stats_by_type["total"])

    single_id = by_type["single"][0]
    multiple_id = by_type["multiple"][0]
    short_id = by_type["short"][0]

    # 答案只在「后台管理」接口下发，用它拿到正确答案来构造判分用例
    detail_q = api("GET", f"/questions/{single_id}")
    correct_answer = detail_q["answer"]
    wrong_option = next(k for k in ("A", "B", "C", "D") if k != correct_answer)

    # ---------- 5. 抽题：背题模式 / 普通模式
    recite = api("GET", "/practice/questions?mode=recite&count=10&page=1")
    expect("背题模式下发答案", recite["items"][0].get("answer") is not None)
    expect("背题模式下发解析", recite["items"][0].get("analysis") is not None)
    seq = api("GET", "/practice/questions?mode=sequence&count=10&page=1")
    expect("普通模式不下发答案", all(i.get("answer") is None for i in seq["items"]))
    for mode in ("sequence", "random", "wrong", "favorite", "recite"):
        page = api("GET", f"/practice/questions?mode={mode}&count=5&page=1")
        expect(f"抽题可用[{mode}]", page["mode"] == mode)

    # ---------- 6. 判分（先答错，再答对）
    pstats = api("GET", "/practice/stats")
    expect("初始已答 0", pstats["answered"] == 0, pstats["answered"])
    expect("题库总数 5（背题不写流水）", pstats["total"] == 5, pstats["total"])

    wrong_res = api("POST", "/practice/answer", {
        "question_id": single_id, "user_answer": wrong_option, "mode": "sequence", "duration_ms": 1234,
    })
    expect("答错判分正确", wrong_res["is_correct"] is False, wrong_res["is_correct"])
    expect("判分返回正确答案", wrong_res["correct_answer"] is not None)
    expect("判分返回解析", wrong_res["analysis"] is not None)

    after_wrong = api("GET", "/practice/stats")
    expect("已答数 +1", after_wrong["answered"] == 1, after_wrong["answered"])
    expect("错题数 = 1", after_wrong["wrong"] == 1, after_wrong["wrong"])
    wrong_list = api("GET", "/practice/wrong?page=1&page_size=20")
    expect("错题本包含该题", any(i["id"] == single_id for i in wrong_list["items"]))

    ok_res = api("POST", "/practice/answer", {
        "question_id": single_id, "user_answer": correct_answer, "mode": "sequence",
    })
    expect("答对判分正确", ok_res["is_correct"] is True, ok_res["is_correct"])
    expect("答对后移出错题本", api("GET", "/practice/stats")["wrong"] == 0)

    # ---------- 7. 收藏 / 取消收藏
    fav = api("POST", f"/practice/favorites/{single_id}/toggle")
    expect("收藏成功", fav["is_favorite"] is True)
    fav_list = api("GET", "/practice/favorites?page=1&page_size=20")
    expect("收藏夹包含该题", any(i["id"] == single_id for i in fav_list["items"]))
    fav2 = api("POST", f"/practice/favorites/{single_id}/toggle")
    expect("取消收藏成功", fav2["is_favorite"] is False)

    # ---------- 8. 简答题：作答 -> 待自评 -> 自评
    sub = api("POST", "/practice/answer", {
        "question_id": short_id, "user_answer": "我的作答内容", "mode": "sequence",
    })
    expect("简答标记待自评", sub["need_self_eval"] is True, sub.get("need_self_eval"))
    expect("简答未直接判分", sub["is_correct"] is None, sub.get("is_correct"))
    se = api("POST", "/practice/self-evaluate", {
        "question_id": short_id, "is_correct": True, "mode": "sequence",
    })
    expect("简答自评成功", se["is_correct"] is True, se.get("is_correct"))

    # ---------- 9. 移出错题本
    api("POST", "/practice/answer", {
        "question_id": multiple_id, "user_answer": ["A"], "mode": "sequence",
    })
    if api("GET", "/practice/stats")["wrong"] >= 1:
        removed = api("DELETE", f"/practice/wrong/{multiple_id}")
        expect("移出错题本接口可用", removed.get("ok") is True)
    expect("重复移出返回 404", status_of("DELETE", f"/practice/wrong/{multiple_id}") == 404)

    # ---------- 10. 统计看板
    board = api("GET", "/stats/board?trend_days=14")
    overview = board["overview"]
    expect("看板概览已答 >= 1", overview["answered"] >= 1, overview["answered"])
    expect("看板正确率已计算", overview["accuracy"] is not None, overview["accuracy"])
    expect("看板题型分布非空", len(board["by_type"]) >= 1)
    expect("看板模式分布非空", len(board["by_mode"]) >= 1)
    expect("看板趋势 14 天", len(board["trend"]) == 14, len(board["trend"]))
    expect("看板总题数 5", overview["total_questions"] == 5, overview["total_questions"])

    # ---------- 11. 题库增删改 + 查重
    created = api("POST", "/questions", {
        "type": "single",
        "title": "【流程测试】HTTPS 的默认端口号是？",
        "options": [
            {"key": "A", "text": "80"},
            {"key": "B", "text": "443"},
            {"key": "C", "text": "22"},
            {"key": "D", "text": "3389"},
        ],
        "answer": "B",
        "analysis": "HTTPS 默认 443。",
    })
    new_id = created["id"]
    expect("新增题目成功", new_id > 0)
    api("PUT", f"/questions/{new_id}", {
        "type": "single",
        "title": "【流程测试】HTTPS 默认端口是哪一个？",
        "options": [
            {"key": "A", "text": "80"},
            {"key": "B", "text": "443"},
            {"key": "C", "text": "22"},
            {"key": "D", "text": "3389"},
        ],
        "answer": "B",
        "analysis": "HTTPS 默认 443。",
    })
    got = api("GET", f"/questions/{new_id}")
    expect("编辑题目生效", got["title"] == "【流程测试】HTTPS 默认端口是哪一个？", got["title"])
    dup = api("POST", "/questions/check-duplicate", {"title": detail_q["title"]})
    expect("题干查重能命中", dup.get("duplicate") is not None)
    api("DELETE", f"/questions/{new_id}")
    expect("删除题目后返回 404", status_of("GET", f"/questions/{new_id}") == 404)

    # ---------- 12. 档案隔离
    temp_profile = api("POST", "/profiles", {"name": "流程测试临时档案"})
    expect("新建档案成功", temp_profile["id"] > 0)
    api("POST", f"/profiles/{temp_profile['id']}/switch")
    current = api("GET", "/profiles/current")
    expect("切换档案生效", current["id"] == temp_profile["id"], current["id"])
    expect("新档案作答数据隔离", api("GET", "/practice/stats")["answered"] == 0)
    if default_profile_id:
        api("POST", f"/profiles/{default_profile_id}/switch")
    api("DELETE", f"/profiles/{temp_profile['id']}")
    restored = api("GET", "/profiles/current")["id"]
    expect("删除档案并回到默认档案", not default_profile_id or restored == default_profile_id, restored)

    # ---------- 13. 幂等导入 + 日志删除
    again = api("POST", "/import/json", form={"path": str(SAMPLE_JSON), "threshold": "0.9"})
    expect("重复导入全部去重", again["imported"] == 0 and again["duplicated"] == 6, again)
    api("DELETE", f"/import/logs/{again['log_id']}")
    expect("删除导入日志成功", status_of("GET", f"/import/logs/{again['log_id']}") == 404)


if __name__ == "__main__":
    main()
