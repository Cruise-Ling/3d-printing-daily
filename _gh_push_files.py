# -*- coding: utf-8 -*-
"""_gh_push_files.py — 按显式文件清单「单次 commit」推送（Git Data API）

为什么需要它：
  日报主流程用 `_gh_push_single_commit.py`，那支脚本的文件清单是硬编码的
  （含 briefing_<date>.html），只适合「日报 + 四专栏」那一批。
  本脚本用于**不涉及当日日报**的补推（改样式 / 改生成器 / 补译文 / 换壳），
  同样走 Git Data API 单次 commit，避免 GitHub Pages 出现中间态。

用法:
  python _gh_push_files.py fullcolor-columns.html _build_column.py
  python _gh_push_files.py <files...> --dry-run       # 只预检，不写远程
  python _gh_push_files.py <files...> -m "提交说明"

注意:
  ① 直连 github.com 在本机不可用（schannel 吊销检查失败 / openssl 后端超时），
     所以只能走 api.github.com —— 这正是本脚本存在的理由。
  ② inline content 上限 1 MB，超了会被静默丢成空 blob，大文件必须先单独建 blob。
  ③ 推送后做远程 blob SHA 全量复核，任一不符即非零退出。
"""
import os, sys, json, io, base64, hashlib, time, urllib.request, urllib.error
import importlib.util

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)


def load_gh():
    """复用 _gh_push.py 的凭据与代理清理，避免第二份 token 出现在仓库里。"""
    spec = importlib.util.spec_from_file_location("ghpush", os.path.join(D, "_gh_push.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gh = load_gh()
PAT = gh.PAT
REPO = gh.REPO
BRANCH = getattr(gh, "BRANCH", None) or "main"

HDR = {
    "Authorization": "Bearer %s" % PAT,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
API = "https://api.github.com"


def api(method, url, body=None, timeout=60):
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


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    msg = None
    files = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-m":
            if i + 1 >= len(argv):
                print("-m 需要一个提交说明")
                return 2
            msg = argv[i + 1]
            i += 2
            continue
        if not a.startswith("-"):
            files.append(a)
        i += 1
    if not files:
        print(__doc__)
        return 2

    names = []
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(D, f)
        if not os.path.exists(p):
            print("local file missing: %s" % f)
            return 2
        names.append(os.path.basename(p))
    files = names

    if hasattr(gh, "_clear_proxy"):
        gh._clear_proxy()

    ref = api("GET", "%s/repos/%s/git/refs/heads/%s" % (API, REPO, BRANCH))
    base_commit = ref["object"]["sha"]
    cmt = api("GET", "%s/repos/%s/git/commits/%s" % (API, REPO, base_commit))
    base_tree = cmt["tree"]["sha"]
    print("repo=%s branch=%s base_commit=%s" % (REPO, BRANCH, base_commit[:12]))

    BLOB_INLINE_LIMIT = 900 * 1024
    entries, local_shas = [], {}
    for f in files:
        text = io.open(os.path.join(D, f), encoding="utf-8", newline="").read()
        raw = text.encode("utf-8")
        local_shas[f] = blob_sha(text)
        if len(raw) > BLOB_INLINE_LIMIT:
            bj = api("POST", "%s/repos/%s/git/blobs" % (API, REPO),
                     {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"})
            entries.append({"path": f, "mode": "100644", "type": "blob", "sha": bj["sha"]})
            print("  staged %-30s %s size=%d (via /git/blobs)" % (f, local_shas[f][:12], len(raw)))
        else:
            entries.append({"path": f, "mode": "100644", "type": "blob",
                            "content": text, "encoding": "utf-8"})
            print("  staged %-30s %s size=%d" % (f, local_shas[f][:12], len(raw)))

    if dry:
        print("=== DRY-RUN: no remote write performed, %d file(s) ===" % len(files))
        return 0

    tree = api("POST", "%s/repos/%s/git/trees" % (API, REPO),
               {"base_tree": base_tree, "tree": entries})
    commit = api("POST", "%s/repos/%s/git/commits" % (API, REPO),
                 {"message": msg or ("push %d file(s)" % len(files)), "tree": tree["sha"],
                  "parents": [base_commit]})
    api("PATCH", "%s/repos/%s/git/refs/heads/%s" % (API, REPO, BRANCH),
        {"sha": commit["sha"], "force": False})
    print("committed %s" % commit["sha"][:12])

    # 远程 blob SHA 全量复核
    time.sleep(1)
    chk = api("GET", "%s/repos/%s/git/trees/%s?recursive=1" % (API, REPO, tree["sha"]))
    remote = {e["path"]: e["sha"] for e in chk.get("tree", [])}
    bad = [f for f in files if remote.get(f) != local_shas[f]]
    for f in files:
        print("  %s %s" % ("OK  " if remote.get(f) == local_shas[f] else "DIFF", f))
    print("ALL MATCH: %s" % (not bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
