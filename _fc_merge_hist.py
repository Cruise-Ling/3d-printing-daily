# -*- coding: utf-8 -*-
"""把外部通道候选与历史版本并回 `_fc_items_norm.json` —— **累积合并，只增不减**。

## 为什么需要这个脚本

fc 采集每次重跑，YouTube `search.list` 与 Reddit RSS 的返回都有波动。
实测 2026-10-27 同一天跑两次：

- 18:17 版 84 条
- 18:22 版 79 条 —— **丢掉 6 条 high 讨论度的 YouTube**（HeyGears G1X 评测、
  FlashForge CJ270 俄语评测、Phrozen ARCO、We Finally Cracked Full Color…），
  只新增 1 条

若以「最后一次采集」为准，这些条目会被静默丢弃，且永远不会自己回来。
所以正确行为是**与历史做并集**：新采到的补进来，旧的只要没被明确下架就保留。

## 数据来源（三者并集）

1. 当前 `_fc_items_norm.json`（最新一次采集的归一化结果）
2. `git show HEAD:_fc_items_norm.json`（上一次发布的版本 = 线上基线）
3. `_fc_yt_candidates.json` 的 items（L3 通道原始候选，字段契约与本地采集一致）

## 用法

```bash
python _fc_merge_hist.py            # 只并 YouTube 候选
python _fc_merge_hist.py --with-rd  # 连 Reddit 候选一起并（默认不并，噪音多）
python _fc_merge_hist.py --dry-run  # 只报告将并入多少条，不写文件
```

幂等：重复运行不会重复追加。
"""
import io
import json
import os
import subprocess
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
NORM = os.path.join(HERE, "_fc_items_norm.json")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reset_delta_baseline(hist_items):
    """合并后把「今日新增」的基线重置为**上一版页面**。

    `_build_column.py` 的 track_delta 会把快照里的 uid 当「已见过」：
    合并补进来的条目若不在快照里，本该算新增；但它的逻辑里有一条
    「fetchedAt 未变则沿用上次 delta」的守卫（防止重跑生成器把新增数抹成 0）。
    合并这一步既没有新的 fetchedAt，又改变了条目集合，正好卡在这条守卫上 ——
    实测页面显示「今日新增 1」，而实际从 84 涨到 102。

    办法：把快照 uids 换成历史基线（上一版页面）的条目，delta / fetchedAt / day
    全部清空，让下一次生成器按「当前池 - 上一版页面」重算。
    """
    p = os.path.join(HERE, "_col_snapshot_fc.json")
    if not os.path.exists(p):
        print("! delta 快照不存在，跳过重置")
        return
    if not hist_items:
        print("! 无历史基线，跳过 delta 重置（避免把整池算成新增）")
        return
    try:
        st = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        print("! 快照解析失败：%s" % e)
        return
    st["uids"] = [x.get("uid") for x in hist_items if x.get("uid")]
    st["delta"] = None
    st["fetchedAt"] = ""
    st["day"] = ""
    st["addedToday"] = 0
    io.open(p, "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False))
    print("已重置 delta 基线：快照 uids = 上一版 %d 条（下次生成器按它算今日新增）"
          % len(st["uids"]))


def read_head_norm():
    """取上一个发布版本的 norm（作为历史基线）。失败则返回空列表。"""
    try:
        raw = subprocess.run(["git", "show", "HEAD:_fc_items_norm.json"],
                             cwd=HERE, capture_output=True, timeout=60).stdout
        if not raw:
            return []
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        print("  ! 历史基线读取失败（跳过）：%s" % e)
        return []


def read_candidates(fn):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        print("  - %s 不存在，跳过" % fn)
        return []
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        print("  ! %s 解析失败：%s" % (fn, e))
        return []
    items = d.get("items") or []
    print("  - %s：%d 条" % (fn, len(items)))
    return items


def main():
    with_rd = "--with-rd" in sys.argv
    dry = "--dry-run" in sys.argv

    ENG = load_module(os.path.join(HERE, "_k3_feishu_delta.py"), "_k3_engine")
    CN = load_module(os.path.join(HERE, "_col_normalize.py"), "_col_norm")

    print("=== 全彩专栏累积合并 ===")
    cur = json.load(io.open(NORM, encoding="utf-8"))
    print("当前 norm        ：%d 条" % len(cur))

    hist = read_head_norm()
    print("历史基线(HEAD)   ：%d 条" % len(hist))

    print("外部候选：")
    ext = read_candidates("_fc_yt_candidates.json")
    if with_rd:
        ext += read_candidates("_fc_rd_candidates.json")

    # ---- 归一化外部候选：先补 uid（uid 用 sourceLink + 原文片段，内容是寻址） ----
    if ext:
        for it in ext:
            if not it.get("uid"):
                it["uid"] = ENG.uid_of(it)
        ext = CN.norm_fc(ext)

    # ---- 并集：当前 → 历史独有 → 外部新增 ----
    merged, seen_uid, seen_url = [], set(), set()
    stat = {"cur": 0, "hist": 0, "ext": 0}

    def push(it, bucket):
        uid = it.get("uid") or ""
        nurl = ENG.norm_url(it.get("url") or "")
        if (uid and uid in seen_uid) or (nurl and nurl in seen_url):
            return False
        if uid:
            seen_uid.add(uid)
        if nurl:
            seen_url.add(nurl)
        merged.append(it)
        stat[bucket] += 1
        return True

    for it in cur:
        push(it, "cur")
    for it in hist:
        push(it, "hist")
    for it in ext:
        push(it, "ext")

    # 与页面默认排序一致：讨论度权重降序，其次日期
    merged.sort(key=lambda x: (-(int(x.get("heatScore") or 0)), x.get("date") or ""))

    print("\n--- 结果 ---")
    print("  保留当前      ：%d" % stat["cur"])
    print("  补回历史独有  ：%d" % stat["hist"])
    print("  补入外部新增  ：%d" % stat["ext"])
    print("  合计          ：%d 条" % len(merged))

    from collections import Counter
    print("  平台分布      ：%s" % dict(Counter(x.get("platform") or "?" for x in merged)))
    print("  讨论度        ：%s" % dict(Counter(x.get("discussLevel") or "?" for x in merged)))
    print("  信源类型      ：%s" % dict(Counter(x.get("sourceType") or "?" for x in merged)))

    if dry:
        print("\n--dry-run：未写文件。")
        return

    bak = NORM + ".bak_before_merge"
    io.open(bak, "w", encoding="utf-8").write(io.open(NORM, encoding="utf-8").read())
    print("\n已备份原文件 → %s" % os.path.basename(bak))

    io.open(NORM, "w", encoding="utf-8").write(
        json.dumps(merged, ensure_ascii=False, indent=1))
    print("已写入 %s（%d 条）" % (os.path.basename(NORM), len(merged)))

    # 同步 meta：记录这次合并，避免页面更新条显示的条数与 norm 不一致
    meta_p = NORM + ".meta.json"
    if os.path.exists(meta_p):
        try:
            meta = json.load(io.open(meta_p, encoding="utf-8"))
            meta.setdefault("stats", {})["mergedExternal"] = {
                "histBackfill": stat["hist"],
                "extAdded": stat["ext"],
                "total": len(merged),
                "withReddit": with_rd,
            }
            meta["count"] = len(merged)
            io.open(meta_p, "w", encoding="utf-8").write(
                json.dumps(meta, ensure_ascii=False, indent=1))
            print("已更新 meta：count=%d" % len(merged))
        except Exception as e:
            print("! meta 更新失败：%s" % e)

    # 让页面「今日新增」反映本次真实净增（相对上一版页面），而不是沿用上次抓取的 delta
    reset_delta_baseline(hist)


if __name__ == "__main__":
    main()
