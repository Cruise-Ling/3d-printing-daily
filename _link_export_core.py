# -*- coding: utf-8 -*-
"""链接批量导出 · 核心引擎

输入：多条 YouTube / Reddit 链接（可以是整段分享文案）
输出：xlsx（三 sheet）/ csv（zip 三文件）/ json
内容：帖子元数据（时间/访问量/点赞/评论数）+ 全部评论正文 + 中文译文

能力边界（2026-11-20 实测，写死在代码里也不隐藏）
--------------------------------------------------
YouTube  videos.list 取元数据（50 id/次，1 unit）；commentThreads 翻页取评论（100 条/页，1 unit）
Reddit   本机出口 IP 全部通道被限：www/old/api 的 .json → 403，.rss → 429/404，
         api.pullpush.io → 429。因此 Reddit 链接只做「识别 + 占位 + 注明原因」，不伪造字段。

翻译     走 translate.googleapis.com 的 gtx 端点。实测：
         · 单条请求 0.9~3.5s，偶发 RemoteDisconnected；
         · 多 q 参数不可靠（超时）；
         · **分隔符拼接可用**：5 条一次 0.85s，分隔符 100% 存活。
         所以按「一批 ≤20 条 / ≤1800 字符」拼接，段数校验不过则降级逐条重译。
"""
import argparse
import concurrent.futures as futures
import csv
import datetime
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _xlsx_writer as XLSX

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
YT_API = "https://www.googleapis.com/youtube/v3/"
GTX = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t"
CACHE_FILE = os.path.join(HERE, "_link_export_cache.json")
SEP = "\n@@@\n"

YMD = u"%Y-%m-%d"
YMDHMS = u"%Y-%m-%d %H:%M:%S"

QUOTA = {"used": 0, "note": []}

# ---------------------------------------------------------------- 链接解析

RE_URL = re.compile(r"https?://[^\s<>\"'\uff09\u3001\uff0c]+", re.I)
RE_YT = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})", re.I)
RE_RD = re.compile(r"reddit\.com/(?:r/[^/]+/)?comments/([a-z0-9]{4,10})", re.I)
RE_RD2 = re.compile(r"redd\.it/([a-z0-9]{4,10})", re.I)


def parse_links(text):
    """从整段文本里抠出链接，去重并保序。返回 [{platform,id,url,raw}]"""
    seen, out = set(), []
    for raw in RE_URL.findall(text or ""):
        url = raw.rstrip(".,;:!?)]}\u3002\uff0c")
        m = RE_YT.search(url)
        if m:
            vid = m.group(1)
            key = ("yt", vid)
            if key in seen:
                continue
            seen.add(key)
            out.append({"platform": "YouTube", "id": vid,
                        "url": "https://www.youtube.com/watch?v=" + vid, "raw": raw})
            continue
        m = RE_RD.search(url) or RE_RD2.search(url)
        if m:
            pid = m.group(1).lower()
            key = ("rd", pid)
            if key in seen:
                continue
            seen.add(key)
            out.append({"platform": "Reddit", "id": pid, "url": url, "raw": raw})
    return out


# ---------------------------------------------------------------- YouTube

def _yt_get(path, **params):
    key = params.pop("key")
    params["key"] = key
    url = YT_API + path + "?" + urllib.parse.urlencode(params)
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wb-export"})
            with OPENER.open(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "ignore")[:300]
            except Exception:
                pass
            if e.code in (403, 429) and "quota" in body.lower():
                raise RuntimeError("YouTube 配额已耗尽")
            if e.code == 404:
                raise RuntimeError("视频不存在或已删除")
            if attempt == 2:
                raise RuntimeError("HTTP %s %s" % (e.code, body[:120]))
        except Exception:
            if attempt == 2:
                raise
        time.sleep(1.5)


def yt_posts(ids, key):
    """批量拿元数据。返回 {vid: post}，失败的进 errors"""
    posts, errors = {}, {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        QUOTA["used"] += 1
        try:
            d = _yt_get("videos", part="snippet,statistics", id=",".join(chunk), key=key)
        except Exception as e:
            for v in chunk:
                errors[v] = str(e)
            continue
        got = set()
        for it in d.get("items") or []:
            sn, st = it.get("snippet") or {}, it.get("statistics") or {}
            vid = it.get("id")
            got.add(vid)
            posts[vid] = {
                "id": vid, "title": sn.get("title") or "",
                "author": sn.get("channelTitle") or "",
                "publishedAt": sn.get("publishedAt") or "",
                "views": _int(st.get("viewCount")),
                "likes": _int(st.get("likeCount")),
                "comments": _int(st.get("commentCount")),
                "lang": "未知",
            }
        for v in chunk:
            if v not in got:
                errors[v] = errors.get(v) or "视频不存在、私有或已删除"
    return posts, errors


def yt_comments(vid, maxn, key, include_replies=False):
    """翻页取顶层评论。maxn<=0 表示不限（硬上限 5000）。"""
    hard = 5000 if not maxn or maxn <= 0 else min(maxn, 5000)
    out, token, closed = [], "", False
    while len(out) < hard:
        QUOTA["used"] += 1
        params = dict(part="snippet,replies", videoId=vid, textFormat="plainText",
                      order="relevance", maxResults=min(100, hard - len(out)), key=key)
        if token:
            params["pageToken"] = token
        try:
            d = _yt_get("commentThreads", **params)
        except RuntimeError as e:
            if "配额" in str(e):
                raise
            closed = True
            break
        except Exception:
            closed = True
            break
        for it in d.get("items") or []:
            sn = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
            cid = it.get("id") or ""
            out.append({"cid": cid, "author": sn.get("authorDisplayName") or "",
                        "publishedAt": sn.get("publishedAt") or "",
                        "likes": _int(sn.get("likeCount")),
                        "text": (sn.get("textDisplay") or "").strip(),
                        "isReply": 0, "parent": ""})
            if include_replies:
                for rp in ((it.get("replies") or {}).get("comments") or []):
                    rs = rp.get("snippet") or {}
                    out.append({"cid": rp.get("id") or "", "author": rs.get("authorDisplayName") or "",
                                "publishedAt": rs.get("publishedAt") or "",
                                "likes": _int(rs.get("likeCount")),
                                "text": (rs.get("textDisplay") or "").strip(),
                                "isReply": 1, "parent": cid})
        token = d.get("nextPageToken") or ""
        if not token:
            break
    return out, closed


# ---------------------------------------------------------------- Reddit（受限占位）

RD_STATE = {"tried": False, "ok": False, "reason": "", "soft_404": 0}


def rd_fetch(pid):
    """Reddit 帖子 + 评论（Atom）。只试一次，失败后本批次熔断，避免逐条等 11 秒。

    坑：Reddit 对不存在的帖子会返回 200 + HTML 错误页，不能只看状态码。
    必须校验正文确实是 Atom feed，否则会把「软 404」当成成功。
    """
    if RD_STATE["tried"]:
        return None
    RD_STATE["tried"] = True
    url = "https://www.reddit.com/comments/%s/.rss" % pid
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")})
        with OPENER.open(req, timeout=18) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        RD_STATE["reason"] = "HTTP %s" % e.code
        return None
    except Exception as e:
        RD_STATE["reason"] = type(e).__name__
        return None
    if b"<feed" not in body[:2000]:
        RD_STATE["reason"] = "返回非 Atom 内容（软 404 或验证页）"
        return None
    RD_STATE["ok"] = True
    try:
        return _rd_parse(body)
    except Exception as e:
        RD_STATE["ok"] = False
        RD_STATE["reason"] = "Atom 解析失败：%s" % type(e).__name__
        return None


def _rd_parse(body):
    """第一条 entry 视为帖子，其余为评论。未经在线验证，失败即降级。"""
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(body)
    entries = root.findall("a:entry", ns)
    if not entries:
        raise ValueError("空 feed")
    def _txt(e, tag):
        n = e.find("a:" + tag, ns)
        return (n.text or "").strip() if n is not None else ""
    head = entries[0]
    post = {"title": _txt(head, "title"), "publishedAt": _txt(head, "updated"),
            "author": "", "views": None, "likes": None, "comments": None}
    an = head.find("a:author/a:name", ns)
    if an is not None and an.text:
        post["author"] = an.text.strip()
    cs = []
    for e in entries[1:]:
        content = e.find("a:content", ns)
        raw = (content.text or "") if content is not None else ""
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            continue
        au = e.find("a:author/a:name", ns)
        cs.append({"cid": _txt(e, "id")[-32:], "author": (au.text or "").strip() if au is not None else "",
                   "publishedAt": _txt(e, "updated"), "likes": None, "text": raw,
                   "isReply": 0, "parent": ""})
    return {"post": post, "comments": cs}


# ---------------------------------------------------------------- 翻译

def _sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _is_zh(s):
    if not s:
        return True
    cjk = sum(1 for ch in s if u"\u4e00" <= ch <= u"\u9fff")
    return cjk / float(len(s)) > 0.3


def load_cache():
    try:
        with io.open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(c):
    try:
        if len(c) > 40000:
            for k in list(c)[:len(c) - 40000]:
                c.pop(k, None)
        with io.open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(c, ensure_ascii=False))
    except Exception:
        pass


def _gtx(text):
    url = GTX + "&q=" + urllib.parse.quote(text)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with OPENER.open(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in (d[0] or []) if seg and seg[0])


def translate_batch(texts, cache):
    """texts: 原文列表 -> {原文: 译文}。批量拼接 + 段数校验 + 失败降级。"""
    todo, res = [], {}
    for t in texts:
        if not t or _is_zh(t):
            continue
        h = _sha(t)
        if h in cache:
            res[t] = cache[h]
        elif len(t) <= 1800:
            todo.append(t)
    todo = list(dict.fromkeys(todo))
    if not todo:
        return res

    batches, cur, size = [], [], 0
    for t in todo:
        if cur and (size + len(t) > 1800 or len(cur) >= 20):
            batches.append(cur)
            cur, size = [], 0
        cur.append(t)
        size += len(t)
    if cur:
        batches.append(cur)

    def work(batch):
        if len(batch) > 1:
            try:
                out = _gtx(SEP.join(batch))
                if out.count("@@@") == len(batch) - 1:
                    for src, dst in zip(batch, out.split("@@@")):
                        if dst.strip():
                            res[src] = dst.strip()
                    return
            except Exception:
                pass
        for one in batch:
            try:
                res[one] = _gtx(one)
            except Exception:
                res[one] = ""

    with futures.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(work, batches))
    for k, v in res.items():
        if v:
            cache[_sha(k)] = v
    return res


# ---------------------------------------------------------------- 工具

def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _bj(iso):
    """"2026-11-01T12:34:56Z" -> "2026-11-01 20:34:56"（北京）"""
    if not iso:
        return ""
    try:
        dt = datetime.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return (dt + datetime.timedelta(hours=8)).strftime(YMDHMS)
    except Exception:
        return iso


def load_key():
    k = os.environ.get("YT_API_KEY")
    if k:
        return k.strip()
    try:
        with io.open(os.path.join(HERE, "_k3_creds.json"), encoding="utf-8") as f:
            return json.load(f)["youtube"]["apiKey"]
    except Exception:
        raise RuntimeError("缺少 YouTube API Key：_k3_creds.json 未配置或格式不对")


# ---------------------------------------------------------------- 导出

POST_HEADER = [u"序号", u"平台", u"链接", u"标题", u"标题译文", u"作者", u"发布时间(UTC)",
               u"发布时间(北京)", u"访问量", u"点赞数", u"评论数", u"实取评论", u"状态", u"备注"]
POST_WIDTH = [6, 10, 42, 50, 50, 22, 18, 20, 10, 9, 9, 9, 14, 34]

CMT_HEADER = [u"父序号", u"平台", u"帖子标题", u"评论ID", u"作者", u"评论时间(北京)",
              u"点赞数", u"原文", u"中文译文", u"是否回复", u"父评论ID"]
CMT_WIDTH = [7, 10, 42, 26, 22, 20, 8, 80, 60, 9, 26]

README = u"""链接批量导出 · 字段与口径说明
==============================

一、适用范围
本文件由「专栏 · 明细反馈流 · 批量导出」生成，只覆盖本次粘贴的链接，
不代表专栏池的全量口碑，禁止外推为产品负面率/满意度。

二、平台能力
YouTube：元数据与评论均来自官方 Data API v3，数据为导出时刻的快照；
        评论按「相关度」翻页取满，回复随线程一并返回（每条线程最多 5 条，零额外配额）。
Reddit ：本机出口 IP 的公开通道被限流（.json 403 / .rss 429），
        本期仅登记链接并注明原因，访问量、点赞、评论正文均无数据。
        该平台不公开 viewCount，即便通道恢复也只有 score 与评论。

三、翻译
引擎为 Google 公开翻译端点（gtx），批量拼接请求，逐条校验段数；
机器翻译未经人工校对，专有名词、反讽、缩略语可能失真，
引用到正式报告前请抽检原文。中文原文不翻译。

四、字段
访问量/点赞数/评论数：None 表示该平台不提供或该帖已删除，不是 0。
实取评论：本次实际抓到并写入「评论明细」的条数，可能小于评论数（上限设置或评论已关闭）。
"""


def build(links, opts, log=None):
    key = load_key() if any(l["platform"] == "YouTube" for l in links) else None
    cache = load_cache()
    posts, cmts = [], []

    yt_ids = [l["id"] for l in links if l["platform"] == "YouTube"]
    meta, errs = ({}, {})
    if yt_ids:
        if log:
            log(u"拉取 %d 个视频的元数据…" % len(yt_ids))
        meta, errs = yt_posts(yt_ids, key)

    for idx, l in enumerate(links, 1):
        row = {"idx": idx, "platform": l["platform"], "url": l["url"], "title": "",
               "titleCn": "", "author": "", "pubUtc": "", "pubBj": "", "views": None,
               "likes": None, "commentsTotal": None, "taken": 0, "lang": "",
               "status": u"成功", "note": ""}

        if l["platform"] == "Reddit":
            got = rd_fetch(l["id"])
            if got:
                p = got["post"]
                row.update({"title": p["title"], "author": p["author"],
                            "pubUtc": p["publishedAt"], "pubBj": _bj(p["publishedAt"]),
                            "views": None, "likes": None,
                            "commentsTotal": p["comments"], "taken": len(got["comments"])})
                for c in got["comments"]:
                    c.update({"parentIdx": idx, "platform": "Reddit",
                              "postTitle": p["title"]})
                cmts.extend(got["comments"])
                row["status"] = u"部分成功"
                row["note"] = u"Reddit 不公开访问量；点赞/评论数 RSS 不保证"
            else:
                row["status"] = u"通道受限"
                row["note"] = (u"Reddit 通道不可用（%s），本期仅登记链接，未取数"
                               % (RD_STATE["reason"] or "未知"))
            posts.append(row)
            continue

        m = meta.get(l["id"])
        if not m:
            row["status"] = u"失败"
            row["note"] = errs.get(l["id"], u"元数据缺失")
            posts.append(row)
            continue

        row.update({"title": m["title"], "author": m["author"], "pubUtc": m["publishedAt"],
                    "pubBj": _bj(m["publishedAt"]), "views": m["views"],
                    "likes": m["likes"], "commentsTotal": m["comments"]})
        try:
            cs, closed = yt_comments(l["id"], opts["max_comments"], key, opts["include_replies"])
        except Exception as e:
            row["status"] = u"部分成功"
            row["note"] = u"元数据成功，评论失败：%s" % e
            posts.append(row)
            continue
        if closed and not cs:
            row["status"] = u"部分成功"
            row["note"] = u"评论区已关闭或无权限"
        if log:
            log(u"  %s 取到 %d 条评论" % (l["id"], len(cs)))
        row["taken"] = len(cs)
        for c in cs:
            c["parentIdx"] = idx
            c["platform"] = "YouTube"
            c["postTitle"] = m["title"]
        cmts.extend(cs)
        posts.append(row)

    if opts["translate"] and cmts:
        if log:
            log(u"翻译 %d 条评论…" % len(cmts))
        tr = translate_batch([c["text"] for c in cmts], cache)
        for c in cmts:
            c["textCn"] = tr.get(c["text"], "" if not _is_zh(c["text"]) else c["text"])
        save_cache(cache)
        titles = [p["title"] for p in posts if p["title"]]
        ttr = translate_batch(titles, cache)
        for p in posts:
            p["titleCn"] = ttr.get(p["title"], "")
    else:
        for c in cmts:
            c["textCn"] = ""
        for p in posts:
            p["titleCn"] = ""

    return posts, cmts


def export(path, fmt, posts, cmts, opts):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    has_rd = any(p["platform"] == "Reddit" for p in posts)
    if not has_rd:
        rd_note = u"本次无 Reddit 链接"
    elif RD_STATE["ok"]:
        rd_note = u"RSS 可用（元数据不完整，Reddit 不公开访问量）"
    else:
        rd_note = u"通道受限：" + (RD_STATE["reason"] or u"未知")
    if fmt == "xlsx":
        sheet1 = [[p["idx"], p["platform"], p["url"], p["title"], p["titleCn"], p["author"],
                   p["pubUtc"], p["pubBj"], p["views"], p["likes"], p["commentsTotal"],
                   p["taken"], p["status"], p["note"]] for p in posts]
        sheet2 = [[c["parentIdx"], c["platform"], c["postTitle"], c["cid"], c["author"],
                   _bj(c["publishedAt"]), c["likes"], c["text"], c.get("textCn") or "",
                   u"是" if c["isReply"] else u"否", c["parent"]] for c in cmts]
        notes = [
            [u"导出时间", stamp],
            [u"链接数", len(posts)],
            [u"评论条数", len(cmts)],
            [u"翻译引擎", u"Google gtx（批量拼接，机器翻译未校对）" if opts["translate"] else u"未翻译"],
            [u"评论上限", opts["max_comments"] or u"不限"],
            [u"含回复", u"是" if opts["include_replies"] else u"否"],
            [u"YouTube 配额消耗", u"%d units（估算）" % QUOTA["used"]],
            [u"Reddit 状态", rd_note],
            [u"口径", u"仅本次粘贴链接的快照，不代表专栏池全量，禁止外推"],
        ]
        XLSX.save(path, [
            {"name": u"帖子清单", "header": POST_HEADER, "rows": sheet1, "widths": POST_WIDTH},
            {"name": u"评论明细", "header": CMT_HEADER, "rows": sheet2, "widths": CMT_WIDTH},
            {"name": u"导出说明", "header": [u"项", u"值"], "rows": notes, "widths": [20, 70]},
        ])
        return path

    if fmt == "csv":
        base = os.path.splitext(path)[0]
        with zipfile.ZipFile(base + ".zip", "w", zipfile.ZIP_DEFLATED) as z:
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(POST_HEADER)
            for p in posts:
                w.writerow([p["idx"], p["platform"], p["url"], p["title"], p["titleCn"],
                            p["author"], p["pubUtc"], p["pubBj"], p["views"], p["likes"],
                            p["commentsTotal"], p["taken"], p["status"], p["note"]])
            z.writestr("posts.csv", u"\ufeff" + buf.getvalue())

            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(CMT_HEADER)
            for c in cmts:
                w.writerow([c["parentIdx"], c["platform"], c["postTitle"], c["cid"], c["author"],
                            _bj(c["publishedAt"]), c["likes"], c["text"],
                            c.get("textCn") or "", u"是" if c["isReply"] else u"否", c["parent"]])
            z.writestr("comments.csv", u"\ufeff" + buf.getvalue())
            z.writestr("README.txt", u"\ufeff" + README + u"\n导出时间：" + stamp + u"\n")
        return base + ".zip"

    data = {"exportedAt": stamp, "options": opts, "quota": QUOTA,
            "reddit": {"ok": RD_STATE["ok"], "reason": RD_STATE["reason"]},
            "posts": posts, "comments": cmts}
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    return path


def run(text, fmt="xlsx", max_comments=300, translate=True, include_replies=True,
        out=None, log=print):
    links = parse_links(text)
    if not links:
        raise RuntimeError("没有识别到 YouTube / Reddit 链接")
    log(u"识别到 %d 条链接（YouTube %d / Reddit %d）" % (
        len(links), sum(1 for l in links if l["platform"] == "YouTube"),
        sum(1 for l in links if l["platform"] == "Reddit")))
    posts, cmts = build(links, {"max_comments": max_comments, "translate": translate,
                                "include_replies": include_replies}, log=log)
    if not out:
        out = os.path.join(HERE, u"链接导出_%s.%s" % (
            datetime.datetime.now().strftime("%Y%m%d_%H%M"), fmt))
    path = export(out, fmt, posts, cmts, {"max_comments": max_comments,
                                          "translate": translate,
                                          "include_replies": include_replies})
    log(u"已生成：%s（%d 帖 / %d 评论 / 配额 %d units）" % (path, len(posts), len(cmts), QUOTA["used"]))
    return path


def self_test():
    """离线自检：不联网，验证解析与三种格式落地"""
    t = (u"看这个 https://www.youtube.com/watch?v=dQw4w9WgXcQ 挺好\n"
         u"还有 https://youtu.be/abcdefghijk?t=10\n"
         u"reddit 有人讨论 https://www.reddit.com/r/3Dprinting/comments/1abc23/x/\n"
         u"重复 https://youtu.be/abcdefghijk")
    ls = parse_links(t)
    assert len(ls) == 3, ls
    assert [l["platform"] for l in ls] == ["YouTube", "YouTube", "Reddit"]
    assert ls[0]["id"] == "dQw4w9WgXcQ" and ls[1]["id"] == "abcdefghijk"

    posts = [{"idx": 1, "platform": "YouTube", "url": "u", "title": u"标题 & <测试>",
              "titleCn": u"标题译文", "author": "ch", "pubUtc": "2026-11-01T00:00:00Z",
              "pubBj": "2026-11-01 08:00:00", "views": 100, "likes": 9,
              "commentsTotal": 2, "taken": 1, "lang": "", "status": u"成功", "note": ""}]
    cmts = [{"parentIdx": 1, "platform": "YouTube", "postTitle": u"标题 & <测试>",
             "cid": "c1", "author": "u1", "publishedAt": "2026-11-02T00:00:00Z",
             "likes": 3, "text": u"bad adhesion", "textCn": u"粘连很差",
             "isReply": 0, "parent": ""}]
    opts = {"max_comments": 300, "translate": True, "include_replies": False}
    d = os.path.join(HERE, "_selftest_out")
    os.makedirs(d, exist_ok=True)
    for fmt in ("xlsx", "csv", "json"):
        p = export(os.path.join(d, "t." + fmt), fmt, posts, cmts, opts)
        assert os.path.exists(p), p
        print("  %-5s %8d B  %s" % (fmt, os.path.getsize(p), os.path.basename(p)))
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", default="", help="直接传链接文本")
    ap.add_argument("--links-file", default="", help="从 txt 读取（一行一条或整段）")
    ap.add_argument("--format", default="xlsx", choices=["xlsx", "csv", "json"])
    ap.add_argument("--max-comments", type=int, default=300, help="每帖上限，0=不限")
    ap.add_argument("--no-translate", action="store_true")
    ap.add_argument("--no-replies", action="store_true", help="不展开评论回复（默认展开，零额外配额）")
    ap.add_argument("--out", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        self_test()
        return
    text = a.links
    if a.links_file:
        with io.open(a.links_file, encoding="utf-8") as f:
            text += "\n" + f.read()
    if not text.strip():
        print("需要 --links 或 --links-file")
        return
    try:
        run(text, a.format, a.max_comments, not a.no_translate,
            not a.no_replies, a.out or None)
    except Exception as e:
        print("失败：%s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
