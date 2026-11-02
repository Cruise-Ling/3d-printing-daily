# -*- coding: utf-8 -*-
"""_hub_ingest.py — 豆包投喂的收料闸门（WorkBuddy 主导 / 豆包供料）

角色分工
--------------------------------------------------------------------------
  豆包：抓登录墙平台（小红书 / 抖音 / 知乎 / X / Instagram），产出 JSON 投到
        `_hub/inbox/<批次日期>/<平台>_<专栏>.json`。**不做任何判定**。
  本脚本：校验 → 去重 → 归一 → 写常驻待并池 `_hub/pending_<专栏>.json`
        → 写回执 `_hub/receipts/<批次>.json`（豆包每天读回执自我修正）。
  主链：`_col_normalize.py`（fc/sw/mbox）与 `_k3_inject_candidates.py`（k3）
        在各自归一入口自动并入 pending 池，页面自然带上，不需要改主链顺序。

用法
--------------------------------------------------------------------------
  python _hub_ingest.py                    # 收今天批次的 inbox
  python _hub_ingest.py --batch 2026-10-31
  python _hub_ingest.py --dry-run          # 只校验，不写 pending / 不写回执

幂等与安全
--------------------------------------------------------------------------
  · 收过的 inbox 文件移到 `_hub/inbox/<批次>/.consumed/`，重复跑不会二次入池
  · 入池按 uid 去重（同一内容多平台转载只留一条）
  · 单条不合格只拒该条，不整批失败；整批不可解析才报错
  · 任何异常都不抛给主链：主链拿不到料就按 0 新增跑，绝不阻断日报

拒收原因（回执里给豆包看）
--------------------------------------------------------------------------
  url-invalid / empty-content / sourceType-invalid / publishedAt-invalid /
  out-of-window / duplicate-url / column-invalid / batch-mismatch
"""
import os
import re
import io
import sys
import json
import glob
import time
import shutil
import argparse
import datetime
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.join(HERE, "_hub")
INBOX = os.path.join(HUB, "inbox")
PENDING = os.path.join(HUB, "pending_%s.json")
RECEIPTS = os.path.join(HUB, "receipts")
SYNCED = os.path.join(HUB, ".synced.json")   # 已同步过哪些远端 inbox 文件（按 blob sha 判重）

COLUMNS = {"fc": "全彩", "k3": "K3", "sw": "软件", "mbox": "mBox"}
SRC_TYPES = ("用户", "KOL", "社区", "媒体", "官方")
WINDOW_DAYS = 7          # 允许交付 T-7 ~ T+1 的内容


def load_engine():
    """复用推送引擎的 norm_url / norm_text / uid_of —— 禁止另写一份，避免口径漂移。"""
    p = os.path.join(HERE, "_k3_feishu_delta.py")
    spec = importlib.util.spec_from_file_location("_k3_engine", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENG = load_engine()


# ---------------------------------------------------------------- 远端 inbox 同步
def load_gh():
    """复用 _gh_push.py 的凭据、代理清理与单文件推送；禁止另存一份 token。"""
    p = os.path.join(HERE, "_gh_push.py")
    spec = importlib.util.spec_from_file_location("_gh_conn", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m._clear_proxy()
    return m


def _load_synced():
    try:
        return json.load(io.open(SYNCED, encoding="utf-8"))
    except Exception:
        return {}


def _save_synced(d):
    try:
        io.open(SYNCED, "w", encoding="utf-8").write(
            json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True))
    except Exception:
        pass


def sync_from_remote(batch, persist=True):
    """把豆包推到 GitHub 的 `_hub/inbox/<批次>/` 拉到本地。

    豆包直接往仓库提交（不写本地目录），所以收料必须以远端为准。
    按 blob sha 判重：同一文件内容没变就不再重复下载/重复入池。
    返回 (新下载的文件名列表, 提示信息)。任何失败都只返回空列表，不抛异常。
    """
    import base64
    import urllib.request
    import urllib.error

    try:
        gh = load_gh()
    except Exception as e:
        return [], "凭据模块加载失败: %s" % e

    hdr = {"Authorization": "Bearer %s" % gh.PAT,
           "Accept": "application/vnd.github+json",
           "User-Agent": "hub-ingest"}
    path = "_hub/inbox/%s" % batch.isoformat()
    api = "https://api.github.com/repos/%s/contents/%s" % (gh.REPO, path)

    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=hdr), timeout=30) as r:
            entries = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return [], "远端无 %s 目录（豆包今天没投）" % path
        return [], "远端列表 HTTP %d" % e.code
    except Exception as e:
        return [], "远端不可达: %s: %s" % (type(e).__name__, e)

    if not isinstance(entries, list):
        return [], "远端返回不是目录（疑似文件名冲突）"

    state = _load_synced().get(batch.isoformat(), {})
    day_dir = os.path.join(INBOX, batch.isoformat())
    os.makedirs(day_dir, exist_ok=True)
    got, skipped, failed = [], 0, []

    for e in entries:
        name = (e.get("name") or "").strip()
        if not name.endswith(".json"):
            continue
        sha = e.get("sha")
        if state.get(name) == sha:
            skipped += 1
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(e["url"], headers=hdr), timeout=40) as r:
                d = json.load(r)
            raw = base64.b64decode(d.get("content") or "")
            if not raw:
                failed.append(name)
                continue
            io.open(os.path.join(day_dir, name), "wb").write(raw)
            state[name] = sha
            got.append(name)
        except Exception as ex:
            failed.append("%s(%s)" % (name, type(ex).__name__))

    allstate = _load_synced()
    if persist:                              # dry-run 不记账，正式跑才会重新处理这批
        allstate[batch.isoformat()] = state
        _save_synced(allstate)

    msg = "新下载 %d｜已是最新跳过 %d" % (len(got), skipped)
    if failed:
        msg += "｜失败 %d: %s" % (len(failed), ",".join(failed[:4]))
    return got, msg


def push_receipt(batch):
    """把回执写回远端，豆包第二天读这个自我修正。失败只告警不抛。"""
    p = os.path.join(RECEIPTS, "%s.json" % batch.isoformat())
    if not os.path.exists(p):
        return False
    try:
        gh = load_gh()
        gh.gh_push("_hub/receipts/%s.json" % batch.isoformat(),
                   io.open(p, encoding="utf-8").read(),
                   msg="hub: 收料回执 %s（WorkBuddy）" % batch.isoformat())
        return True
    except Exception as e:
        print("[hub] 回执推送失败（不影响收料）: %s" % str(e)[:120])
        return False

try:                                    # 全彩的机型/档次判定规则（复用采集器，不另写）
    _s = importlib.util.spec_from_file_location("_fc_col", os.path.join(HERE, "_col_collect_fc.py"))
    FC = importlib.util.module_from_spec(_s)
    _s.loader.exec_module(FC)
except Exception:                        # 采集器加载失败不致命，只是不做机型判定
    FC = None


# ---------------------------------------------------------------- 校验
def parse_date(s):
    s = (s or "").strip()[:10]
    try:
        return datetime.date(*map(int, s.split("-")))
    except Exception:
        return None


def validate(it, batch, col):
    """返回 (reasons[], fixed_item)。一条不合格只影响这一条。"""
    reasons = []
    url = (it.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        reasons.append("url-invalid")

    title = (it.get("title") or "").strip()
    body = (it.get("originalText") or "").strip()
    if not title and not body:
        reasons.append("empty-content")
    if len(body) > 20000:                # 防呆：整页 HTML 被当正文塞进来
        reasons.append("content-too-long")

    st = (it.get("sourceType") or "用户").strip()
    if st not in SRC_TYPES:
        reasons.append("sourceType-invalid")

    pub = parse_date(it.get("publishedAt")) or parse_date(it.get("date"))
    if pub is None:
        it["publishedAt"] = batch.isoformat()
        it["dateGuessed"] = True
        pub = batch
    else:
        it["publishedAt"] = pub.isoformat()
        it["dateGuessed"] = bool(it.get("dateGuessed"))
    delta = (pub - batch).days
    if delta > 1:
        reasons.append("out-of-window")     # 未来日期，多半是抓错
    elif delta < -WINDOW_DAYS:
        reasons.append("out-of-window")

    it["sourceType"] = st
    it["date"] = (it.get("date") or it["publishedAt"])[:10]
    it["platform"] = (it.get("platform") or "").strip()
    it["site"] = (it.get("site") or it.get("platform") or "").strip()
    it["channel"] = (it.get("channel") or ("国内" if (it.get("country") or "CN") == "CN" else "海外")).strip()
    it["country"] = (it.get("country") or "CN").strip().upper()
    it["language"] = (it.get("language") or ("ZH" if re.search(r"[\u4e00-\u9fff]", title + body) else "EN")).strip().upper()
    it["batch"] = batch.isoformat()
    it["from"] = "doubao"
    it["ingestedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    it["column"] = col
    return reasons, it


def enrich_fc(it):
    """全彩：补机型 / 档次 / 技术路线 / 热度分。规则复用采集器，边界案例留给页面校验暴露。"""
    title, body = it.get("title") or "", it.get("originalText") or ""
    hint = (it.get("modelHint") or "").strip()
    if FC is not None:
        try:
            model, tier = FC.model_of("%s %s" % (title, body), title)
            if not model and hint:                       # 规则没识别出来，退回豆包给的机型提示
                model, tier = FC.model_of("%s %s" % (hint, title), hint)
            if not model and hint:
                model = hint
            it["model"], it["tier"] = model or "", tier or ""
            it["techRoute"] = FC.tech_route_of(it["model"])
        except Exception:
            it["model"] = it.get("modelHint") or ""
            it.setdefault("tier", "")
    else:
        it["model"] = it.get("modelHint") or ""
        it.setdefault("tier", "")

    h = it.get("heat") or {}
    if isinstance(h, str):               # 兼容豆包直接给 "1200赞 / 86评论"
        h = {}
    likes = int(h.get("likes") or h.get("赞") or 0)
    comments = int(h.get("comments") or h.get("评论") or 0)
    collects = int(h.get("collects") or h.get("收藏") or 0)
    score = likes + comments * 2 + collects
    it["heatRaw"] = {"likes": likes, "comments": comments, "collects": collects}
    it["heatScore"] = score
    it["discussLevel"] = "high" if score >= 3000 else ("mid" if score >= 500 else "low")
    it["heatSource"] = "doubao:赞+评论x2+收藏"
    it["heat"] = ("%d 赞 / %d 评论 / %d 收藏" % (likes, comments, collects)) if score else ""
    return it


def enrich_generic(it):
    h = it.get("heat") or {}
    it.setdefault("heatRaw", h if isinstance(h, dict) else {})
    it["heatScore"] = int(it.get("heatScore") or 0)
    it["discussLevel"] = it.get("discussLevel") or "low"
    it["heatSource"] = it.get("heatSource") or ("doubao" if it.get("heat") else "")
    return it


# ---------------------------------------------------------------- 待并池
def load_pool(col):
    p = PENDING % col
    if not os.path.exists(p):
        return []
    try:
        d = json.load(io.open(p, encoding="utf-8"))
        return d.get("items", []) if isinstance(d, dict) else d
    except Exception:
        return []


def save_pool(col, items):
    p = PENDING % col
    io.open(p, "w", encoding="utf-8").write(
        json.dumps({"updated": time.strftime("%Y-%m-%d %H:%M"),
                    "note": "豆包投喂的常驻待并池。由 _hub_ingest.py 累加，"
                            "_col_normalize.py / _k3_inject_candidates.py 在归一入口自动并入。",
                    "items": items}, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- 主流程
def ingest(batch, dry=False, only=None):
    day_dir = os.path.join(INBOX, batch.isoformat())
    files = sorted(glob.glob(os.path.join(day_dir, "*.json")))
    if only is not None:                     # 只收本次从远端新拉下来的，避免重复计拒收
        files = [f for f in files if os.path.basename(f) in only]
    rc = {"batch": batch.isoformat(), "received": 0, "accepted": 0, "rejected": 0,
          "rejectReasons": [], "merged": 0, "columns": {}, "files": len(files),
          "ingestedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not files:
        rc["note"] = "本批次无投喂文件"
        return rc

    pools = {c: load_pool(c) for c in COLUMNS}
    known = {}
    for c, arr in pools.items():
        for x in arr:
            known.setdefault(ENG.norm_url(x.get("url") or ""), (c, x.get("uid")))

    accepted = {c: [] for c in COLUMNS}

    for f in files:
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception as e:
            rc["rejectReasons"].append({"file": os.path.basename(f), "reason": "json-unparsable: %s" % e})
            continue

        items = d.get("items") if isinstance(d, dict) else d
        if not isinstance(items, list):
            rc["rejectReasons"].append({"file": os.path.basename(f), "reason": "items-missing"})
            continue

        col = (d.get("column") or "").strip() if isinstance(d, dict) else ""
        if col not in COLUMNS:
            rc["rejectReasons"].append({"file": os.path.basename(f), "reason": "column-invalid: %r" % col})
            continue

        seen = set()
        for it in items:
            rc["received"] += 1
            if not isinstance(it, dict):
                rc["rejected"] += 1
                rc["rejectReasons"].append({"file": os.path.basename(f), "reason": "item-not-object"})
                continue

            reasons, it = validate(it, batch, col)
            nu = ENG.norm_url(it.get("url") or "")
            if nu and nu in known:
                reasons.append("duplicate-url")
            if nu and nu in seen:
                reasons.append("duplicate-url")

            if reasons:
                rc["rejected"] += 1
                rc["rejectReasons"].append({
                    "file": os.path.basename(f), "column": col,
                    "url": (it.get("url") or "")[:120],
                    "title": (it.get("title") or "")[:60],
                    "reason": ",".join(sorted(set(reasons)))})
                continue

            it["uid"] = ENG.uid_of(it)
            it = enrich_fc(it) if col == "fc" else enrich_generic(it)
            seen.add(nu)
            known[nu] = (col, it["uid"])
            accepted[col].append(it)
            rc["accepted"] += 1

    for c, arr in accepted.items():
        if not arr:
            continue
        have = {x.get("uid") for x in pools[c]}
        add = [x for x in arr if x.get("uid") not in have]
        rc["columns"][COLUMNS[c]] = {"accepted": len(arr), "appended": len(add),
                                     "poolTotal": len(pools[c]) + len(add)}
        if not dry:
            save_pool(c, pools[c] + add)
        rc["merged"] += len(add)

    if not dry:
        done = os.path.join(day_dir, ".consumed")
        os.makedirs(done, exist_ok=True)
        for f in files:
            try:
                shutil.move(f, os.path.join(done, os.path.basename(f)))
            except Exception:
                pass
        os.makedirs(RECEIPTS, exist_ok=True)
        io.open(os.path.join(RECEIPTS, "%s.json" % batch.isoformat()), "w",
                encoding="utf-8").write(json.dumps(rc, ensure_ascii=False, indent=1))
        try:                                  # 待译清单：非中文条目，供主链翻译环节取材
            pend = []
            for c in COLUMNS:
                for x in load_pool(c):
                    if x.get("from") == "doubao" and (x.get("language") or "").upper() != "ZH" \
                            and not x.get("textCn"):
                        pend.append({"uid": x["uid"], "column": c,
                                     "title": x.get("title") or "",
                                     "text": (x.get("originalText") or "")[:1200]})
            io.open(os.path.join(HUB, "translate_todo.json"), "w", encoding="utf-8").write(
                json.dumps({"updated": time.strftime("%Y-%m-%d %H:%M"), "items": pend},
                           ensure_ascii=False, indent=1))
        except Exception:
            pass

    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--local", action="store_true",
                    help="只收本地 _hub/inbox（默认先拉远端仓库，豆包直接推 GitHub）")
    ap.add_argument("--no-receipt-push", action="store_true", help="不把回执推回远端")
    a = ap.parse_args()
    batch = parse_date(a.batch)
    if batch is None:
        raise SystemExit("bad --batch %r (expect YYYY-MM-DD)" % a.batch)

    only = None
    if not a.local:
        got, msg = sync_from_remote(batch, persist=not a.dry_run)
        print("[hub] 远端同步: %s" % msg)
        if not got and "无 " in msg:
            print("[hub] 批次 %s 无新增投喂，跳过" % batch.isoformat())
            return 0
        only = set(got)

    try:
        rc = ingest(batch, dry=a.dry_run, only=only)
    except Exception as e:                     # 绝不把异常抛给主链
        print("[hub] ERR %s: %s" % (type(e).__name__, e))
        return 0

    print("[hub] 批次 %s｜文件 %d｜收到 %d｜收下 %d｜拒收 %d｜入池 %d"
          % (rc["batch"], rc["files"], rc["received"], rc["accepted"], rc["rejected"], rc["merged"]))
    for c, s in rc.get("columns", {}).items():
        print("      %-4s 收下 %d / 新增 %d / 池内共 %d" % (c, s["accepted"], s["appended"], s["poolTotal"]))
    for r in rc["rejectReasons"][:10]:
        print("      [REJECT] %s | %s" % (r.get("reason"), (r.get("title") or r.get("file") or "")[:50]))
    if rc["rejected"] and not rc["accepted"]:
        print("      [WARN] 本批全部拒收 —— 请豆包对照回执修正字段")
    if a.dry_run:
        print("      (dry-run：未写 pending、未写回执、未移动 inbox)")
    elif not a.no_receipt_push and rc["files"]:
        ok = push_receipt(batch)
        print("      回执已写回远端: %s" % ("YES" if ok else "NO（本地已留存）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
