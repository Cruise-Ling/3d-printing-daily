# -*- coding: utf-8 -*-
"""光固化专栏 · 日更原子子链（工作日 10:00「专栏增量」Step 4.4 调用）

    python _resin_daily.py              # 阶段 A：采集 + 规则预标，必要时输出待复核清单
    python _resin_daily.py --finalize   # 阶段 B：注入 + 建页 + 静态/运行时双校验

设计纪律：
  1. 一条命令包住整条链，主链 prompt 不需要记住 6 个脚本；
  2. 候选池只是候选 —— 当日新增未经逐条语义复核不得入页（K3 纪律）。
     阶段 A 检测到未复核条目时输出 STATUS: NEEDS_REVIEW 并停住，由 10:00 链的
     Agent 按 .workbuddy/memory/resin-feedback.md 改判后再跑 --finalize；
  3. 失败隔离：任一步失败 / 超时只记 SKIP 并以退出码 0 收尾，绝不拖死主链；
  4. 硬上限 8 分钟（与 H3C 论坛采集一致）；
  5. 本链不发任何飞书卡、不做 P0 自动触达、不碰日报与 README 归档表。

幂等：采集器 seen 双线差集 + 注入器 uidmap + 主链 Step 0.3 的 freshness GREEN 跳过。
"""
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LABELS = os.path.join(BASE, "_resin_labels.json")
RUN = os.path.join(BASE, "_run")
BUDGET = 8 * 60
os.makedirs(RUN, exist_ok=True)
LOG = os.path.join(RUN, "resin_%s.log" % dt.date.today().strftime("%Y%m%d"))


def log(msg):
    line = "[%s] %s" % (dt.datetime.now().strftime("%H:%M:%S"), msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def run(name, cmd, deadline):
    left = deadline - time.time()
    if left <= 0:
        log("%s | SKIP | 总预算耗尽" % name)
        return False, "timeout"
    try:
        p = subprocess.run(cmd, cwd=BASE, timeout=min(left, 240),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace").strip()
        ok = p.returncode == 0
        log("%s | %s | %s" % (name, "OK" if ok else "FAIL", out.splitlines()[-1] if out else ""))
        return ok, out
    except subprocess.TimeoutExpired:
        log("%s | SKIP | 超时" % name)
        return False, "timeout"
    except Exception as e:
        log("%s | SKIP | %s" % (name, type(e).__name__))
        return False, type(e).__name__


def pending_new():
    """返回仍未语义复核的候选条数（新增条目会被 _resin_prelabel.py 标 confirmed=false）。"""
    if not os.path.exists(LABELS):
        return 0
    try:
        lab = json.load(open(LABELS, encoding="utf-8"))
    except (ValueError, OSError):
        return 0
    return sum(1 for v in lab.values() if not v.get("confirmed"))


def finish(status, extra=None):
    rec = {"status": status, "date": dt.date.today().isoformat()}
    rec.update(extra or {})
    print("[RESIN_DAILY] " + json.dumps(rec, ensure_ascii=False))
    log("STATUS " + status)
    sys.exit(0)


def finalize(deadline):
    steps = {}
    for name, cmd in (
        ("inject", [PY, "_resin_inject.py"]),
        ("build", [PY, "_build_resin.py"]),
        ("verify", ["node", "_resin_verify.js"]),
        ("runtime", ["node", "_resin_runtime.js"]),
    ):
        ok, out = run(name, cmd, deadline)
        steps[name] = "OK" if ok else "SKIP"
        if not ok:
            finish("SKIP", {"steps": steps, "failedAt": name})
    finish("OK", {"steps": steps, "page": "resin-line.html"})


def main():
    deadline = time.time() + BUDGET
    log("=== resin daily start ===")
    if "--finalize" in sys.argv:
        if pending_new() > 0:
            log("仍有未复核条目，拒绝注入（先按 resin-feedback.md 逐条语义改判）")
            finish("NEEDS_REVIEW", {"pending": pending_new()})
        finalize(deadline)
        return

    ok, _ = run("collect", [PY, "_resin_collect.py", "--daily"], deadline)
    if not ok:
        # 采集失败也要让当日页面 updatedDate 滚动吗？不 —— 采集没跑成就不该伪造新鲜度。
        finish("SKIP", {"failedAt": "collect"})
    ok, _ = run("prelabel", [PY, "_resin_prelabel.py"], deadline)
    if not ok:
        finish("SKIP", {"failedAt": "prelabel"})

    pend = pending_new()
    if pend:
        inbox = sorted(glob.glob(os.path.join(BASE, "_resin_review_inbox_*.md")))
        log("新增 %d 条待逐条语义复核，清单 %s" % (pend, os.path.basename(inbox[-1]) if inbox else "—"))
        finish("NEEDS_REVIEW", {"pending": pend,
                               "inbox": os.path.basename(inbox[-1]) if inbox else None})
    finalize(deadline)


if __name__ == "__main__":
    main()
