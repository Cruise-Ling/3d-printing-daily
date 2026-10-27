# -*- coding: utf-8 -*-
"""GitHub 缺陷单采集（软件专栏第 4 个信源，2026-10-20 用户定档 3C/4A）

为什么加这个源：
  官方论坛是「求助 / 吐槽」，GitHub issue 是「可复现的缺陷单」—— 带标签、带版本号、
  带复现步骤。两者互补。CrealityPrint 官方仓库有 195 个 open issue，论坛一条都没引用过。

口径（用户 4A）：进明细、独立标签 `GitHub`、**不进总声量**（countInVolume=false）。
  原因：issue 是缺陷单不是用户声量，混进声量会把「论坛 502 条」这个可比基线打乱。

用法：
  python _col_collect_github.py            # 默认窗口：自家 90 天 / 竞品 30 天
  python _col_collect_github.py --days 730 # 全量回捞
  python _col_collect_github.py --dry-run  # 只看能采到多少，不写盘
"""
import argparse
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

import _col_normalize as N

OUT = "_gh_items_sw.json"
CREDS = "_k3_creds.json"

# (repo, 归属产品线, 是否自家, 默认窗口天数, 单仓上限)
# ⚠️ 只收 Creality 官方仓库。OrcaSlicer 实测近 45 条 issue 里只有 3 条与 Creality 相关
#    （且是「Text adjustment on bed types」这种列举机型的弱相关），其余是 Qidi / 其他品牌。
#    把那些放进明细会让「竞品工具」标签变成误导，所以竞品仓库只取仓库级统计作背景
#    （见 COMPETITOR_STATS），不进明细、不进任何计数。
REPOS = [
    ("CrealityOfficial/CrealityPrint",     "print",       True,  90, 200),
    ("CrealityOfficial/K1_Series_Klipper", "firmware",    True,  730, 60),
    ("CrealityOfficial/K2_Series_Klipper", "firmware",    True,  730, 60),
]
COMPETITOR_STATS = ["SoftFever/OrcaSlicer"]
STATS_OUT = "_gh_competitor_stats.json"

UA = "creality-sw-column-collector/1.0"
SITE_NAME = {
    "CrealityOfficial/CrealityPrint": "GitHub · CrealityPrint",
    "CrealityOfficial/K1_Series_Klipper": "GitHub · K1 Klipper",
    "CrealityOfficial/K2_Series_Klipper": "GitHub · K2 Klipper",
}

# ---------------------------------------------------------------- 字段抽取
RE_VER = re.compile(r"\b[vV]?(\d{1,2}\.\d{1,2}\.\d{1,4}(?:\.\d{1,5})?)\b")
RE_MODEL = [
    (re.compile(r"\bK2\s*Plus\b", re.I), "K2 Plus"),
    (re.compile(r"\bK2\s*Pro\b", re.I), "K2 Pro"),
    (re.compile(r"\bK1\s*Max\b", re.I), "K1 Max"),
    (re.compile(r"\bK1C\b", re.I), "K1C"),
    (re.compile(r"\bK1\b", re.I), "K1"),
    (re.compile(r"\bK2\b", re.I), "K2"),
    (re.compile(r"\bEnder[-\s]?3\s*S1\s*Pro\b", re.I), "Ender-3 S1 Pro"),
    (re.compile(r"\bEnder[-\s]?3\s*S1\b", re.I), "Ender-3 S1"),
    (re.compile(r"\bEnder[-\s]?3\b", re.I), "Ender-3"),
    (re.compile(r"\bCR-?\s?M4\b", re.I), "CR-M4"),
    (re.compile(r"\bEnder[-\s]?5\b", re.I), "Ender-5"),
    (re.compile(r"\bHi\b"), "Hi"),
]
# 缺陷细分：顺序敏感。compat 必须排在 crash 前面 ——
# 「Linux: does not launch」既命中 crash 词也命中平台词，归兼容比归崩溃更能指导动作。
PROBLEM_RULES = [
    ("compat",  [r"\blinux\b", r"\bmacos\b", r"\bfedora\b", r"\bubuntu\b", r"\bflatpak\b",
                 r"\bappimage\b", r"\bmint\b", r"\bdriver\b", r"\badwaita\b", r"\bwebkit\b",
                 r"\bwxwidgets\b", r"\barm64\b", r"\bwayland\b", r"兼容"]),
    ("crash",   [r"\bcrash", r"sigabrt", r"won'?t\s+(start|launch|open)",
                 r"not\s+(launch|loading|booting|opening)", r"does\s+not\s+(start|launch|open)",
                 r"fail(s|ed)?\s+to\s+(start|launch|load)", r"\bfreez", r"崩溃", r"无法启动"]),
    ("ui",      [r"\binterface\b", r"\bdialog\b", r"\bwindow\b", r"\bbutton\b", r"\bmenu\b",
                 r"\bdisplay\b", r"\brender", r"\bfont\b", r"\bgrey\b", r"\bgray\b",
                 r"\bslide\s*out", r"\bunreadable\b", r"\bcolor\b", r"\bicon\b",
                 r"\bdesktop\s*shortcut\b", r"\bname\b", r"界面", r"显示"]),
    ("quality", [r"\bprint\s*quality", r"\bsurface\b", r"\blayer\s*line", r"\bstringing",
                 r"\bblob\b", r"\bwarp", r"\bdimension", r"\bseam\s*scar", r"\bsag",
                 r"质量", r"翘边", r"拉丝"]),
    ("slice",   [r"\bslic", r"\bsupport", r"\binfill", r"\bbrim\b", r"\bz-hop", r"\bretract",
                 r"\bpurge", r"\bprofile", r"\bpreset", r"\bg-?code",
                 r"\bdensity\b", r"\btree\s+support", r"切片"]),
]
FEATURE_WORDS = re.compile(r"\b(enhancement|feature|request|would\s+be\s+nice|add\s+(a|an|the)\b|"
                           r"suggest|proposal|allow\s+(users|the)|support\s+for)", re.I)


def pick_problem(title, body, labels):
    lab = " ".join(labels).lower()
    if "enhancement" in lab or "feature" in lab:
        return "feature"
    tx = (title + " " + body).lower()
    if FEATURE_WORDS.search(title) and "bug" not in lab:
        return "feature"
    for code, pats in PROBLEM_RULES:
        for p in pats:
            if re.search(p, tx):
                return code
    if "bug" in lab:
        return "other"
    return "other" if body else ""


def pick_model(tx):
    for rx, name in RE_MODEL:
        if rx.search(tx):
            return name
    return "未标注"


def clean_body(b):
    """issue 正文常带 HTML 注释、复选框模板、日志堆，先削掉再清洗。"""
    b = b or ""
    b = re.sub(r"<!--.*?-->", " ", b, flags=re.S)
    b = re.sub(r"^\s*[-*]\s*\[[ xX]\].*$", " ", b, flags=re.M)   # 复现步骤复选框
    b = re.sub(r"```.*?```", " ", b, flags=re.S)                  # 代码块 / 日志块
    b = re.sub(r"<[^>]{1,80}>", " ", b)                           # 残留 HTML
    b = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", b)                   # 图片
    b = re.sub(r"\n{3,}", "\n\n", b)
    return N.clean_body(b)


# ---------------------------------------------------------------- 采集
def _clear_proxy():
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
              "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)


def _token():
    if not os.path.exists(CREDS):
        return ""
    try:
        d = json.load(io.open(CREDS, encoding="utf-8"))
        return ((d.get("github") or {}).get("token") or "").strip()
    except Exception:
        return ""


def fetch(url, token, tries=3):
    _clear_proxy()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = "Bearer " + token
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                       timeout=30, context=ctx)
            return r.status, json.loads(r.read()), r.headers.get("X-RateLimit-Remaining")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and i < tries - 1:
                time.sleep(4 * (i + 1))
                continue
            return e.code, None, None
        except Exception:
            if i < tries - 1:
                time.sleep(2)
                continue
            return "ERR", None, None
    return "ERR", None, None


def collect(repo, product_line, is_self, days, cap, token, cutoff_all):
    """拉一页页 issue（排除 PR），按 created_at 窗口过滤。"""
    rows, page, remain = [], 1, None
    since = cutoff_all if days >= 365 else (datetime.now(timezone.utc) - timedelta(days=days))
    while len(rows) < cap and page <= 5:
        url = ("https://api.github.com/repos/%s/issues?state=open&sort=created"
               "&direction=desc&per_page=100&page=%d" % (repo, page))
        st, data, rem = fetch(url, token)
        remain = rem if rem is not None else remain
        if st != 200 or not isinstance(data, list):
            print("    ! %s page%d -> %s" % (repo, page, st))
            break
        if not data:
            break
        oldest = None
        for it in data:
            if "pull_request" in it:
                continue
            created = datetime.strptime(it["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            oldest = created
            if created < since:
                continue
            rows.append((it, created))
        if oldest and oldest < since:
            break
        page += 1
        time.sleep(0.6)
    rows = rows[:cap]

    out = []
    for it, created in rows:
        labels = [l["name"] for l in it.get("labels", [])]
        raw_title = (it.get("title") or "").strip()
        body = clean_body(it.get("body") or "")
        body, cut = N.truncate(body)
        mv = RE_VER.search(raw_title) or RE_VER.search(body[:300])
        raw_ver = mv.group(1) if mv else ""
        problem = pick_problem(raw_title, body, labels)
        item = {
            "uid": "GH-%s-%d" % (repo.split("/")[1], it["number"]),
            "date": it["created_at"][:10],
            "platform": "GitHub",
            "site": SITE_NAME.get(repo, "GitHub"),
            "channel": "海外",
            "country": "GLOBAL",
            "language": "EN",
            "title": raw_title,
            "titleCn": "",
            "originalText": body,
            "textCn": "",
            "truncated": cut,
            "url": it["html_url"],
            "productLine": product_line,
            "version": N.norm_version(raw_ver),
            "versionRaw": raw_ver,
            "problemType": problem,
            "model": pick_model(raw_title + " " + body[:400]),
            "grade": "有效" if len(body) >= 40 else "泛讨论",
            "stage": "",
            "tool": "",
            "replyCount": it.get("comments") or 0,
            "views": 0,
            "likeCount": 0,
            "sourceType": "GitHub",
            "countInVolume": False,
            "ghRepo": repo,
            "ghNumber": it["number"],
            "ghState": it.get("state"),
            "ghLabels": labels,
            "ghIsSelf": is_self,
        }
        item["stage"] = N.stage_of(item)
        item["tool"] = "self" if is_self else "competitor"
        out.append(item)
    return out, remain


def collect_competitor_stats(token):
    """竞品仓库只取仓库级指标（开单量 / 最近发布），不取单条 issue。"""
    out = {}
    for repo in COMPETITOR_STATS:
        st, data, _ = fetch("https://api.github.com/repos/" + repo, token)
        if st != 200 or not isinstance(data, dict):
            print("  ! 竞品统计失败 %s -> %s" % (repo, st))
            continue
        rel_st, rel, _ = fetch("https://api.github.com/repos/%s/releases?per_page=1" % repo, token)
        latest = ""
        if rel_st == 200 and isinstance(rel, list) and rel:
            latest = "%s（%s）" % (rel[0].get("tag_name", ""), (rel[0].get("published_at") or "")[:10])
        out[repo] = {
            "openIssues": data.get("open_issues_count"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "latestRelease": latest,
            "pushedAt": (data.get("pushed_at") or "")[:10],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="覆盖所有仓库的窗口天数")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    token = _token()
    print("GitHub 认证：%s" % ("已带 token" if token else "匿名（60 次/小时）"))

    cutoff_all = datetime.now(timezone.utc) - timedelta(days=730)
    all_rows, remain = [], None
    for repo, pl, own, days, cap in REPOS:
        d = a.days or days
        rows, rem = collect(repo, pl, own, d, cap, token, cutoff_all)
        remain = rem if rem is not None else remain
        print("  %-40s %3d 条（窗口 %d 天）" % (repo, len(rows), d))
        all_rows.extend(rows)

    stats = collect_competitor_stats(token)
    for k, v in stats.items():
        print("  %-40s 竞品背景：open=%s ★%s 最新 %s" % (
            k, v.get("openIssues"), v.get("stars"), v.get("latestRelease")))

    # 幂等：同一 issue 只保留一条
    seen, uniq = set(), []
    for r in all_rows:
        if r["uid"] in seen:
            continue
        seen.add(r["uid"])
        uniq.append(r)
    uniq.sort(key=lambda x: (x["date"], x["uid"]), reverse=True)

    print("\n合计 %d 条" % len(uniq))
    print("  按仓库: %s" % dict(Counter(x["ghRepo"].split("/")[1] for x in uniq).most_common()))
    print("  按段:   %s" % dict(Counter(N.STAGE_NAME.get(x["stage"], "跨环节") for x in uniq).most_common()))
    print("  按类型: %s" % dict(Counter(x["problemType"] or "(空)" for x in uniq).most_common()))
    print("  有效/泛: %s" % dict(Counter(x["grade"] for x in uniq).most_common()))
    print("  带版本号: %d 条" % sum(1 for x in uniq if x["version"]))
    print("  日期区间: %s ~ %s" % (uniq[-1]["date"], uniq[0]["date"]))
    if remain:
        print("  剩余配额: %s" % remain)

    if a.dry_run:
        print("\n（dry-run，未写盘）")
        for x in uniq[:8]:
            print("  %s %-52s %s" % (x["date"], x["title"][:52], x["stage"] or "跨环节"))
        return

    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(uniq, ensure_ascii=False, indent=1))
    io.open(STATS_OUT, "w", encoding="utf-8").write(
        json.dumps(stats, ensure_ascii=False, indent=1))
    print("\n已写 %s + %s" % (OUT, STATS_OUT))


if __name__ == "__main__":
    sys.exit(main())
