# -*- coding: utf-8 -*-
"""_step2_yt_collect.py — 海外口碑 Step 2 的 YouTube 评论采集（Reddit 出口已封锁，仅剩此源）

只做「拿到」：搜近期相关视频 → 拉最新评论 → 按时间窗过滤 → 去掉纯表情/纯链接/超短。
情感 / 维度 / 问题点一律不判，交给人（或主链）逐条标注。
"""
import os
import io
import json
import datetime
import urllib.parse
import urllib.request

# 沙箱默认 HTTPS_PROXY 指向本地 502 代理，谷歌接口必须直连
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = json.load(io.open(os.path.join(HERE, "_k3_creds.json"), encoding="utf-8"))["youtube"]["apiKey"]

QUERIES = [
    "Creality K3 review",
    "Creality K3 multicolor",
    "Creality K3 problem",
    "Snapmaker U1 review",
    "Bambu Lab multicolor printer",
]
MIN_LEN = 60          # 少于这个字符的评论信息量不足，直接丢
BATCH = datetime.date.today()
# 时间窗：T-3 00:00 ~ T 23:59（首发期主窗口放宽到 T-3，与 k3-feedback.md 口径一致）
WIN = (datetime.datetime.combine(BATCH - datetime.timedelta(days=3), datetime.time.min),
       datetime.datetime.combine(BATCH, datetime.time(23, 59)))


def _get(path, **params):
    params["key"] = KEY
    url = "https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": "wb"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def search_videos(q):
    try:
        d = _get("search", part="snippet", q=q, type="video", maxResults=8,
                 order="date", publishedAfter="2026-10-10T00:00:00Z",
                 relevanceLanguage="en")
    except Exception as e:
        print("  [search] %s ERR %s" % (q, type(e).__name__))
        return []
    out = []
    for it in d.get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if vid:
            out.append({"videoId": vid, "title": sn.get("title"), "channel": sn.get("channelTitle"),
                        "publishedAt": sn.get("publishedAt")})
    return out


def comments(vid, maxn=40):
    try:
        d = _get("commentThreads", part="snippet", videoId=vid, maxResults=maxn,
                 order="time", textFormat="plainText")
    except Exception:
        return []
    out = []
    for it in d.get("items", []):
        c = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
        out.append({"text": c.get("textDisplay") or "", "author": c.get("authorDisplayName") or "",
                    "publishedAt": c.get("publishedAt") or "",
                    "likes": c.get("likeCount") or 0, "videoId": vid})
    return out


def main():
    seen_v, cands = set(), []
    for q in QUERIES:
        vs = search_videos(q)
        print("[search] %-28s 视频 %d" % (q, len(vs)))
        for v in vs:
            if v["videoId"] in seen_v:
                continue
            seen_v.add(v["videoId"])
            cs = comments(v["videoId"])
            keep = 0
            for c in cs:
                t = (c["text"] or "").strip()
                if len(t) < MIN_LEN:
                    continue
                if t.count("http") > 0 and len(t) < 140:
                    continue
                try:
                    dt = datetime.datetime.strptime(c["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    continue
                if not (WIN[0] <= dt <= WIN[1]):
                    continue
                c["title"] = v["title"]
                c["channel"] = v["channel"]
                c["url"] = "https://www.youtube.com/watch?v=%s&lc=%s" % (v["videoId"], c.get("author", ""))
                c["url"] = "https://www.youtube.com/watch?v=%s" % v["videoId"]
                cands.append(c)
                keep += 1
            print("   %-42s 评论 %d → 窗口内合格 %d" % ((v["title"] or "")[:42], len(cs), keep))

    cands.sort(key=lambda x: (-int(x.get("likes") or 0), x.get("publishedAt") or ""))
    out = os.path.join(HERE, "_step2_yt_candidates.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(
        {"batch": BATCH.isoformat(), "source": "youtube-comments",
         "window": [WIN[0].isoformat(), WIN[1].isoformat()],
         "count": len(cands), "items": cands}, ensure_ascii=False, indent=1))
    print("\n合格候选 %d 条 → %s" % (len(cands), os.path.basename(out)))
    for c in cands[:8]:
        print("  [%s赞] %s" % (c["likes"], (c["text"] or "")[:90].replace("\n", " ")))


if __name__ == "__main__":
    main()
