# -*- coding: utf-8 -*-
"""软件专栏 · 下线版本维度 + 补「工具 × 实现环节」交叉矩阵（幂等）

为什么下线版本
--------------------------------------------------------------------------
用户 2026-10-27：本专栏定位是「全部 3D 打印行业的软件通用专栏」，不是创想三维一家。
版本维度只在单一产品内部可比；跨工具时各家的版本号体系完全独立
（Creality Print 7.x / OrcaSlicer 2.x / Bambu Studio 1.x / Cura 5.x），
混排在一张「主版本热度」里会被读成同一产品的版本演进 —— 那是错误结论。

删除范围（呈现层）：
  · KPI「覆盖版本」卡        → 换「竞品工具声量」
  · S3「主版本热度」面板      → 换「工具 × 实现环节」交叉矩阵
  · 筛选栏「主版本」下拉
  · S.major / S.version 状态、LABELS、chips 顺序
  · matrixTable() 残留（已无调用点）
保留范围（数据层）：items[].version / versionRaw 不动 —— 将来做「单工具专项」时
  版本维度在单产品内部仍然成立，届时按 tool 过滤后即可复用。
"""
import io
import sys

F = sys.argv[1] if len(sys.argv) > 1 else "_col_shell.html"


def rw(s, old, new, tag, required=True):
    if old not in s:
        if required:
            print("  ! MISS  %s" % tag)
        else:
            print("  - skip  %s" % tag)
        return s
    print("  ok      %s" % tag)
    return s.replace(old, new, 1)


s = io.open(F, encoding="utf-8").read()
print("patch %s (%d bytes)" % (F, len(s)))

# ---------------------------------------------------------------- 1. 状态
s = rw(s,
       'var S = {product:"",major:"",version:"",problem:"",model:"",grade:"",channel:"",source:"",lang:"",',
       'var S = {product:"",problem:"",model:"",grade:"",channel:"",source:"",lang:"",',
       "S 状态删 major/version")

# ---------------------------------------------------------------- 2. match 过滤
s = rw(s,
       '  if(skip!=="major" && S.major && majorOf(it.version)!==S.major) return false;\n'
       '  if(skip!=="version" && S.version && (it.version||"未标注")!==S.version) return false;\n',
       '',
       "match 删版本过滤")

# ---------------------------------------------------------------- 3. KPI
s = rw(s,
       '    var vers = vol.filter(function(x){return x.version;});\n',
       '',
       "KPI 删 vers 变量")

s = rw(s,
       '      {l:"覆盖版本", v:uniq(vers.map(function(x){return x.version;})).length,\n'
       '        s:"已归一为主.次 · 7.x "+vers.filter(function(x){return majorOf(x.version)==="7.x";}).length+\n'
       '          " · 6.x "+vers.filter(function(x){return majorOf(x.version)==="6.x";}).length, c:"#58a6ff"},',
       '      {l:"竞品工具声量", v:(byTool.competitor||0),\n'
       '        s:"自家 "+(byTool.self||0)+" 条 · 未提工具 "+(byTool[""]||0)+" 条 · 全行业口径下看自家软件的位置", c:"#58a6ff"},',
       "KPI 覆盖版本 → 竞品工具声量")

# 总声量口径说明：保留 GitHub 单列，但明确「全行业」不再是「自家」
s = rw(s,
       '      {l:"总声量", v:vol.length, s:"自家工具 "+(byTool.self||0)+" · 竞品工具 "+(byTool.competitor||0)+\n'
       '        " · 未提 "+(byTool[""]||0)+(gh? "<br>另有 GitHub 缺陷单 "+gh+" 条单列，不计入声量":"")+"",\n'
       '        c:"#e6edf3"},',
       '      {l:"总声量", v:vol.length, s:"全行业口径 · 含竞品工具 "+(byTool.competitor||0)+" 条"+\n'
       '        (gh? "<br>另有 GitHub 缺陷单 "+gh+" 条单列，不计入声量":"")+"",\n'
       '        c:"#e6edf3"},',
       "KPI 总声量口径改全行业")

# ---------------------------------------------------------------- 4. 删 matrixTable 残留
i0 = s.find("function matrixTable(){")
if i0 > 0:
    i1 = s.find("\nfunction stagePanel", i0)
    if i1 > 0:
        s = s[:i0] + s[i1 + 1:]
        print("  ok      删 matrixTable() 残留")
    else:
        print("  ! MISS  matrixTable 结束位置")
else:
    print("  - skip  matrixTable 已不存在")

# ---------------------------------------------------------------- 5. 主版本热度 → 工具×环节
old_p3 = '''    var p3 = apply("major");
    var arr3 = Object.keys(countBy(p3,function(x){return majorOf(x.version);}))
      .map(function(k){return [k,countBy(p3,function(x){return majorOf(x.version);})[k]];})
      .sort(function(a,b){return parseFloat(b[0])-parseFloat(a[0]);});
    var mx3 = Math.max.apply(null, arr3.map(function(z){return z[1];}).concat([1]));
    B.innerHTML = panel("主版本热度","条数 · 点击可筛选",
      arr3.length? arr3.map(function(r){
        var on = S.major===r[0]?" on":"";
        return '<div class="brow'+on+'" data-pick="major" data-val="'+esc(r[0])+'">'+
          '<span class="nm">'+esc(r[0])+'</span><span class="track"><i class="fill" style="width:'+(r[1]/mx3*100)+'%;background:'+(VER_COLOR[r[0].replace(".x","")]||"#8b949e")+'"></i></span>'+
          '<span class="vl">'+r[1]+' 条</span></div>';
      }).join("")+
      '<div class="pnote">原「版本 × 问题类型」矩阵已删除：35 格里多数只有 1–2 条，且 237 条泛讨论进不去，读不出规律。</div>'
      : '<div class="empty">当前筛选下无版本数据</div>');'''
new_p3 = '''    B.innerHTML = panel("工具 × 实现环节","行=工具类型 · 列=用户环节 · 深色格=该环节的主力工具",
      toolStageMatrix());'''
s = rw(s, old_p3, new_p3, "主版本热度 → 工具×环节矩阵")

# 新增 toolStageMatrix 函数（插在 stagePanel 之前）
if "function toolStageMatrix()" not in s:
    anchor = "/** 实现路径六段：按用户从「找模型」到「分享变现」的实际顺序排，点任一格即筛明细 */"
    fn = '''/** 工具 × 实现环节：哪个环节的活主要由哪类工具承担。
    这是「全行业通用」视角 —— 它不依赖任何一家的版本号，所以在跨工具专栏里成立。
    行只列 6 个真实工具类型；「未提具体工具」不是一个工具类型，它的量级看左侧工具结构。 */
function toolStageMatrix(){
  var base = apply();
  var rows = ["slice","model","cloud","multicolor","firmware","hardware"];
  var cols = STAGE_META.map(function(s){return s[0];}).concat(["跨环节"]);
  function cell(t,c){
    return base.filter(function(x){
      return (x.toolType||"")===t && (x.stage||"跨环节")===c;
    }).length;
  }
  var mx = 1;
  rows.forEach(function(t){ cols.forEach(function(c){ var n=cell(t,c); if(n>mx) mx=n; }); });
  var head = '<tr><th>工具类型</th>'+cols.map(function(c){
    return '<th>'+esc(STAGE_NAME[c]||"跨环节")+'</th>';}).join("")+'<th>合计</th></tr>';
  var body = rows.map(function(t){
    var rt = base.filter(function(x){return (x.toolType||"")===t;});
    if(!rt.length) return "";
    var tds = cols.map(function(c){
      var n = cell(t,c);
      var attr = n? ' style="background:rgba(88,166,255,'+(0.10+0.52*(n/mx)).toFixed(2)+')"' : ' class="cov0"';
      return '<td'+attr+'>'+(n||"—")+'</td>';
    }).join("");
    return '<tr><td>'+esc(TOOLTYPE_NAME[t]||t)+'</td>'+tds+
      '<td style="font-weight:700">'+rt.length+'</td></tr>';
  }).join("");
  if(!body) return '<div class="empty">当前筛选下无工具结构数据</div>';
  return '<table class="mx"><thead>'+head+'</thead><tbody>'+body+'</tbody></table>'+
    '<div class="pnote">版本维度已下线：本专栏覆盖全行业软件，各家版本号体系相互独立'+
    '（Creality Print 7.x / OrcaSlicer 2.x / Bambu Studio 1.x / Cura 5.x），混在一张图里不可比。<br>'+
    '改看「哪类工具在哪个环节吃掉了需求」—— 行与列的交叉密度，就是竞品在哪个环节比我们强。</div>';
}

'''
    if anchor in s:
        s = s.replace(anchor, fn + anchor, 1)
        print("  ok      新增 toolStageMatrix()")
    else:
        print("  ! MISS  toolStageMatrix 插入锚点")
else:
    print("  - skip  toolStageMatrix 已存在")

# ---------------------------------------------------------------- 6. 筛选栏
s = rw(s,
       '    h += selHTML("major","主版本", opts(function(x){return majorOf(x.version);},null,"major"));\n',
       '',
       "筛选栏删主版本")

# ---------------------------------------------------------------- 7. LABELS / chips
s = rw(s,
       'var LABELS = {product:"产品线",major:"主版本",version:"版本",problem:"问题类型",model:"机型",',
       'var LABELS = {product:"产品线",problem:"问题类型",model:"机型",',
       "LABELS 删 major/version")

s = rw(s,
       '  ["product","major","version","problem","model","grade","channel","source","lang",',
       '  ["product","problem","model","grade","channel","source","lang",',
       "clearAll 顺序删 major/version")

# ---------------------------------------------------------------- 8. majorOf 不再有调用点
if "majorOf(" in s and s.count("majorOf(") == 1:
    s = rw(s,
           'function majorOf(v){ var m=String(v||"").match(/^(\\d{1,2})/); return m? m[1]+".x" : ""; }\n',
           '',
           "删无引用的 majorOf()")
else:
    print("  - keep  majorOf 仍有 %d 处引用" % s.count("majorOf("))

io.open(F, "w", encoding="utf-8", newline="\n").write(s)
print("written %d bytes" % len(s))
