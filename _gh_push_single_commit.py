# -*- coding: utf-8 -*-
"""_gh_push_single_commit.py — 日报 4 文件「单次 commit」推送固化脚本（P1 加固）

用法:
  python _gh_push_single_commit.py 20261012            # 正式推送
  python _gh_push_single_commit.py 20261012 --dry-run  # 只预检，不写远程

推送文件（5 个，单次 commit，避免 Pages 中间态 errored）:
  user-complaints.html
  briefing_<YYYYMMDD>.html
  creality-k3.html        ← K3 用户反馈专栏（2026-10-14 并入）
  index.html
  README.md

加固点（对照 2026-10-12 事故）:
  ① api() 内**统一** resp.read() + json.loads，调用方只拿 dict
     → 根除 `'HTTPResponse' object is not subscriptable`（把未解析响应当 JSON 下标）
  ② 任何异常**自动重试 1 次**（间隔 5s），重试后仍失败才发飞书告警
     → 根除「首跑崩溃即告警、30 秒后自动修复重跑成功」的假警报
  ③ --dry-run 预检：只做 GET ref + 读本地 + 算 blob sha，绝不写远程
  ④ 远程 blob SHA 全量复核，任一 DIFF → 非零退出（区别于可重试错误，不重试）
  ⑤ 复用 _gh_push._clear_proxy（推送前必须 pop 全部代理变量，否则 502）
"""
import os, sys, json, io, time, base64, hashlib, urllib.request, urllib.error

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)

import importlib.util
_spec = importlib.util.spec_from_file_location("ghpush", os.path.join(D, "_gh_push.py"))
gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gh)

PAT = gh.PAT
REPO = gh.REPO
BRANCH = "main"

HDR = {
    "Authorization": "Bearer %s" % PAT,
    "Accept": "application/vnd.github+json",
    "User-Agent": "gh-single-commit",
    "Content-Type": "application/json",
}


class NonRetryable(Exception):
    """内容不一致等重试无意义的错误 → 不重试，直接告警退出。"""


def norm_date(s):
    s = (s or "").strip().replace("-", "").replace("/", "")
    if len(s) != 8 or not s.isdigit():
        raise SystemExit("bad date %r (expect YYYYMMDD, e.g. 20261012)" % s)
    return s


def api(method, url, body=None, timeout=60):
    """统一的 GitHub REST 调用。

    ⚠️ 关键加固：响应体在这里一次性 read + json.loads，返回 **dict**。
    调用方绝不能再拿到 HTTPResponse 对象去下标，否则复现
    `'HTTPResponse' object is not subscriptable`。
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError("%s %s -> HTTP %s: %s" % (method, url, e.code, detail)) from None
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def blob_sha(text):
    b = text.encode("utf-8")
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(b))
    h.update(b)
    return h.hexdigest()


def do_push(date, dry_run=False):
    files = [
        "user-complaints.html",
        "briefing_%s.html" % date,
        "creality-k3.html",
        "index.html",
        "README.md",
    ]
    # 专栏页：存在才带（保持与日报老流程兼容；上线后恒存在）
    # 2026-10-27 起 fullcolor-columns.html 并入同一次 commit，避免多 commit 造成 Pages 中间态
    # 2026-11-04 起 bambu-h3c.html 同批（H3C 专栏上线）
    for extra in ("creality-mbox.html", "software-columns.html", "fullcolor-columns.html", "bambu-h3c.html"):
        p = os.path.join(D, extra)
        if os.path.exists(p) and extra not in files:
            files.insert(3, extra)
    miss = [f for f in files if not os.path.exists(os.path.join(D, f))]
    if miss:
        raise NonRetryable("local file(s) missing: %s" % ", ".join(miss))

    # 0) 推送前强制去重 index 的 BRIEFING_DATA。
    #    2026-10-23 实证：休眠唤醒后主流水线与兜底轮并发，两边都往头部插当日条目，
    #    会出现两条同一日期（页面上看不出来，但会占位置且 g(date) 只取第一条）。
    #    放在唯一推送入口做，任何调用方都绕不过去。
    try:
        import importlib
        if D not in sys.path:
            sys.path.insert(0, D)
        DD = importlib.import_module("_index_dedupe")
        p_idx = os.path.join(D, "index.html")
        s_idx = io.open(p_idx, encoding="utf-8", newline="").read()
        head, lines, tail = DD.split_block(s_idx)
        seen, kept, dropped = set(), [], []
        for ln in lines:
            m = DD.DATE_RE.search(ln)
            if not m:
                kept.append(ln)
                continue
            if m.group(1) in seen:
                dropped.append(m.group(1))
                continue
            seen.add(m.group(1))
            kept.append(ln)
        if dropped:
            io.open(p_idx, "w", encoding="utf-8", newline="\n").write(head + "\n".join(kept) + tail)
            print("  [dedupe] index 去掉重复日期: %s" % "、".join(dropped))
        else:
            print("  [dedupe] index BRIEFING_DATA 无重复日期（%d 条）" % len(seen))
    except Exception as e:
        print("  [dedupe] 跳过（%s: %s）" % (type(e).__name__, e))

    # 0.5) README 合并式写入（2026-10-31 加固）。
    #      原逻辑是把本地 README 整份覆盖到远端：本地副本一旦落后（API 推送不更新本地
    #      git 历史，实测本地停在 10-27、远端已到 10-30），别人在 GitHub 网页改的内容
    #      次日 09:00 就被冲掉。改为「取远端为基底 → 归档行并集 → 落本地 → 再推」。
    #      顺带修复归档表分隔行错位（历史插入逐日把分隔行推到了表尾，表格一直没渲染）。
    #      失败不阻断日报（P0 不可缺），退化为原行为并显式告警。
    if "README.md" in files:
        try:
            import importlib
            _rm = importlib.import_module("_readme_merge")
            _r = _rm.merge(date, apply=True)
            print("  [readme] %s %s" % (_r["status"], _r["msg"]))
        except Exception as e:
            print("  [readme] WARN 合并失败，回退本地内容: %s: %s" % (type(e).__name__, e))

    gh._clear_proxy()

    # 1) ref -> base commit -> base tree
    refj = api("GET", "https://api.github.com/repos/%s/git/refs/heads/%s" % (REPO, BRANCH))
    try:
        base_commit = refj["object"]["sha"]
    except (TypeError, KeyError, IndexError) as e:
        raise NonRetryable("unexpected refs payload: %s | %s" % (e, str(refj)[:200]))
    cmtj = api("GET", "https://api.github.com/repos/%s/git/commits/%s" % (REPO, base_commit))
    base_tree = cmtj["tree"]["sha"]
    print("base_commit=%s base_tree=%s" % (base_commit[:12], base_tree[:12]))

    # 2) stage files + compute local blob shas
    # ⚠️ `POST /git/trees` 的 inline content 有 1 MB 上限，超了会被静默丢成空 blob
    #    （sha = e69de29bb2d1，即 Git 空文件）。software-columns.html 已超 1 MB，
    #    所以大文件必须先单独建 blob，tree entry 只引用 sha。
    BLOB_INLINE_LIMIT = 900 * 1024
    tree_entries, local_shas = [], {}
    for fp in files:
        with open(os.path.join(D, fp), encoding="utf-8") as f:
            text = f.read()
        raw = text.encode("utf-8")
        local_shas[fp] = blob_sha(text)
        if len(raw) > BLOB_INLINE_LIMIT:
            bj = api("POST", "https://api.github.com/repos/%s/git/blobs" % REPO,
                     {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"})
            tree_entries.append({"path": fp, "mode": "100644", "type": "blob", "sha": bj["sha"]})
            print("  staged %-26s local_blob=%s size=%d (via /git/blobs)" % (fp, local_shas[fp][:12], len(raw)))
        else:
            tree_entries.append({"path": fp, "mode": "100644", "type": "blob",
                                 "content": text, "encoding": "utf-8"})
            print("  staged %-26s local_blob=%s size=%d" % (fp, local_shas[fp][:12], len(raw)))

    if dry_run:
        print("=== DRY-RUN: no remote write performed ===")
        print("would push %d file(s) on top of %s" % (len(files), base_commit[:12]))
        return

    # 3) create tree (base_tree → 保留其它所有文件)
    treej = api("POST", "https://api.github.com/repos/%s/git/trees" % REPO,
                {"base_tree": base_tree, "tree": tree_entries})
    new_tree = treej["sha"]
    print("new_tree=%s" % new_tree[:12])

    # 4) create commit
    msg = "daily: %s-%s-%s briefing + overseas feedback + k3 feedback + index/readme (single commit)" \
          % (date[:4], date[4:6], date[6:8])
    cmj = api("POST", "https://api.github.com/repos/%s/git/commits" % REPO,
              {"message": msg, "tree": new_tree, "parents": [base_commit]})
    new_commit = cmj["sha"]
    print("new_commit=%s" % new_commit[:12])

    # 5) update ref
    api("PATCH", "https://api.github.com/repos/%s/git/refs/heads/%s" % (REPO, BRANCH),
        {"sha": new_commit, "force": False})
    print("ref updated -> %s" % new_commit[:12])

    # 6) verify remote blob sha
    # 用 contents API 返回的 `sha`（本身就是 blob sha）比较，而不是比对解码后的文本 ——
    # contents API 对 >1 MB 的文件不返回 content（返回空串），按文本比会把大文件误判成空。
    print("=== REMOTE VERIFY ===")
    allmatch = True
    for fp in files:
        try:
            j = api("GET", "https://api.github.com/repos/%s/contents/%s" % (REPO, fp))
            rsha = j.get("sha") or ""
            match = (rsha == local_shas[fp])
            allmatch = allmatch and match
            print("%s %-26s local=%s remote=%s"
                  % ("MATCH" if match else "DIFF ", fp, local_shas[fp][:12], rsha[:12]))
        except Exception as e:
            allmatch = False
            print("VERIFY ERR %-26s %s" % (fp, e))
    if not allmatch:
        raise NonRetryable("SHA MISMATCH after commit %s -> verify manually" % new_commit[:12])
    print("ALL MATCH: True")
    print("DONE single-commit push + verify")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        raise SystemExit("usage: python _gh_push_single_commit.py <YYYYMMDD> [--dry-run]")
    date = norm_date(args[0])

    last_err = None
    for attempt in (1, 2):
        try:
            do_push(date, dry_run=dry)
            print("OK (attempt %d)" % attempt)
            return 0
        except NonRetryable as e:
            print("NON-RETRYABLE: %s" % e)
            last_err = e
            break
        except Exception as e:
            last_err = e
            print("ATTEMPT %d FAILED: %s" % (attempt, e))
            if attempt == 1:
                print("retry in 5s ...")
                time.sleep(5)

    if dry:
        print("DRY-RUN FAILED:", last_err)
        return 1
    import traceback
    tb = traceback.format_exc()
    gh.feishu_alert("❌ 3D打印日报 %s 推送失败（重试后仍失败）: %s\n%s"
                    % (date, last_err, tb[-600:]))
    print("PUSH FAILED:", last_err)
    return 1


if __name__ == "__main__":
    sys.exit(main())
