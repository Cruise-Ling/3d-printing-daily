# `_hub/` — WorkBuddy × 豆包 协作总线的契约

> 2026-10-31 建立。WorkBuddy 主导（判定 + 建页 + 推送），豆包供料（登录墙平台抓取）。
> 豆包的操作手册见 `豆包每日作业提示词.md`；本文件是给维护者看的机制说明。

# 一、为什么需要这条总线

两边跑在同一台机器上，但**没有共享上下文**：豆包不知道我昨天拒了它哪几条，我也不知道它今天抓了什么。git 在这里不当版本控制用，当**异步消息队列**用 —— 文件即消息，落盘即送达。

不要引入数据库、消息队列、API 服务。文件够了。

# 二、目录语义

```
_hub/
  inbox/<YYYY-MM-DD>/<平台>_<专栏>.json   豆包写，我只读
  inbox/<YYYY-MM-DD>/.consumed/           我收完后把原文件挪到这里（幂等）
  pending_<专栏>.json                     我维护的常驻待并池（累积）
  receipts/<YYYY-MM-DD>.json              我写的回执，豆包每天读
  translate_todo.json                     非中文待译清单（我翻，豆包不碰）
```

`pending_*` 是**常驻**不是按天：`_col_normalize.py` 每次重建都从它取，所以条目不会因为「今天没重新收集」而掉出页面。

# 三、数据怎么流到页面

```
豆包写 inbox
   ↓  _hub_ingest.py（校验/去重/补机型档次/写回执）
pending_<专栏>.json
   ↓  _col_normalize.py 的 _merge_hub_pending()（唯一归一入口自动并入）
_<专栏>_items_norm.json
   ↓  _col_tr_*.json（我翻译）→ _build_column.py
fullcolor-columns.html → _gh_push_*  → GitHub Pages → 飞书卡片
```

关键设计：**接在归一入口，不是加在主链 prompt 里**。这样主链顺序不用改，任何人跑归一都会自动带上，也不会因为漏跑某一步而丢料。

# 四、谁能自动并，谁不能

| 专栏 | 自动并入 | 原因 |
|---|---|---|
| `fc` 全彩 | ✅ | 机型 / 档次判定已规则化（`model_of`），页面校验能兜住 |
| `k3` | ❌ | 情感 / topics / problemPoints 属语义判定，猜了就是往页面写假结论 |
| `sw` 软件 | ❌ | problemType / 版本抽取必须标题优先人工判 |
| `mbox` | ❌ | 同 sw |

`k3 / sw / mbox` 的投喂只进 pending 池，**由我在主链里逐条标注后再入页**。宁可当天不出，也不出错的。

# 五、质量闸门（收料时逐条判）

| 码 | 判定 | 处置 |
|---|---|---|
| `url-invalid` | 非 http(s) | 拒 |
| `empty-content` | 标题正文皆空 | 拒 |
| `content-too-long` | 正文 > 2 万字（多半塞了整页 HTML） | 拒 |
| `sourceType-invalid` | 不在 用户/KOL/社区/媒体/官方 | 拒 |
| `publishedAt-invalid` | 日期不可解析 | 补为批次日 + `dateGuessed` |
| `out-of-window` | 早于 T-7 或晚于今天 | 拒 |
| `duplicate-url` | 归一化 URL 已在池内 | 拒 |
| `column-invalid` | 专栏名不在 fc/k3/sw/mbox | 整文件拒 |

单条不合格只拒该条；整批不可解析才报错。**任何异常都不往上抛** —— 主链拿不到料就按 0 新增跑，绝不因为等料丢日报。

# 六、时间契约

| 时间 | 谁 | 动作 |
|---|---|---|
| ≤08:30 | 豆包 | 写 inbox |
| 08:35 起 | 我 | 可随时收料（幂等，重复跑安全） |
| 09:00 | 主链 | 归一入口自动并池 → 建页 → 推送 |
| 09:00 后 | 豆包 | 读回执，次日修正 |

过了 08:30 的交付顺延到次日批次 —— 进不了当天 14:00 的飞书点评卡。

# 七、维护提醒

- `pending_*.json` 会一直长。条目数到 ~500 时考虑按季度归档到 `_hub/archive/`，并同步清理页面不再展示的老条目。
- 新增专栏时，只要改 `_hub_ingest.py` 的 `COLUMNS` 与 `_col_normalize.py` 里 `_merge_hub_pending` 的白名单，不要另写一套。
- 这个仓库是 **public**：inbox 里只允许出现公开媒体内容和链接。**抓取策略、平台绕过手段、拒收原因的对抗分析都不许写进来** —— 那些写在本地台账和对话里。
