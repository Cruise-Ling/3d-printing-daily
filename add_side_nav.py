import os, re

work_dir = r"C:\Users\123004\WorkBuddy\automation-claw-20260423184755"

css_addition = """
/* 分区导航栏 - 顶部固定 */
.section-nav { display:flex; gap:6px; padding:10px 20px; background:#fafbff; border-bottom:1px solid #f0f0f0; flex-wrap:wrap; position:sticky; top:0; z-index:100; }
.section-nav .nav-btn { display:inline-flex; align-items:center; gap:5px; padding:5px 12px; border-radius:20px; border:1px solid #e0e0e0; background:#fff; font-size:12px; color:#555; cursor:pointer; transition:all .2s; user-select:none; }
.section-nav .nav-btn:hover { border-color:#999; }
.section-nav .nav-btn.active { font-weight:500; border-width:1.5px; }
.section-nav .nav-btn .dot { width:7px;height:7px;border-radius:50%;flex-shrink:0; }
.section-highlight { animation:sectionGlow .6s ease; }
@keyframes sectionGlow { 0%{box-shadow:inset 0 0 0 2px rgba(0,0,0,.08);} 100%{box-shadow:none;} }

/* 左侧悬浮导航 - 宽屏 */
.side-nav {
  position:fixed;
  left:max(0px, calc((100vw - 375px) / 2 - 90px));
  top:50%;
  transform:translateY(-50%);
  display:flex;
  flex-direction:column;
  gap:6px;
  z-index:200;
}
.side-nav .side-nav-item {
  display:flex;
  align-items:center;
  gap:8px;
  padding:7px 14px;
  border-radius:20px;
  font-size:12px;
  font-weight:500;
  color:#555;
  cursor:pointer;
  transition:all .25s;
  white-space:nowrap;
  background:#fff;
  box-shadow:0 2px 12px rgba(0,0,0,.08);
  border:1.5px solid #eee;
}
.side-nav .side-nav-item:hover {
  background:#f8f9ff;
  border-color:#c5cae9;
  transform:translateX(3px);
}
.side-nav .side-nav-item.active {
  background:#1a73e8;
  color:#fff;
  border-color:#1a73e8;
  box-shadow:0 2px 12px rgba(26,115,232,.3);
}
.side-nav .side-nav-dot {
  width:8px;height:8px;border-radius:50%;flex-shrink:0;
}

/* 移动端适配 */
@media (max-width:768px) {
  .side-nav { display:none; }
  .section-nav { position:sticky; top:0; z-index:100; box-shadow:0 2px 8px rgba(0,0,0,.06); }
}
@media (min-width:769px) {
  .section-nav { display:none; }
}
"""

side_nav_html = """
<!-- 左侧悬浮导航（宽屏显示） -->
<div class="side-nav" id="sideNav">
  <div class="side-nav-item" onclick="scrollToSection('general')" data-section="general">
    <span class="side-nav-dot" style="background:#1a73e8;"></span>泛行业
  </div>
  <div class="side-nav-item" onclick="scrollToSection('specific')" data-section="specific">
    <span class="side-nav-dot" style="background:#e65100;"></span>细分领域
  </div>
  <div class="side-nav-item" onclick="scrollToSection('consumer')" data-section="consumer">
    <span class="side-nav-dot" style="background:#2e7d32;"></span>消费级
  </div>
  <div class="side-nav-item" onclick="scrollToSection('global')" data-section="global">
    <span class="side-nav-dot" style="background:#7b1fa2;"></span>海外资讯
  </div>
  <div class="side-nav-item" onclick="scrollToSection('feedback')" data-section="feedback">
    <span class="side-nav-dot" style="background:#1565c0;"></span>用户口碑
  </div>
</div>
"""

new_js = """
<script>
/* 点击跳转分区 */
function scrollToSection(name) {
  var colors = { general:'#e8f0fe', specific:'#fff3e0', consumer:'#e8f5e9', global:'#f3e5f5', feedback:'#e3f2fd' };
  var borderColors = { general:'#1a73e8', specific:'#e65100', consumer:'#2e7d32', global:'#7b1fa2', feedback:'#1565c0' };
  document.querySelectorAll('.nav-btn').forEach(function(b){ b.classList.remove('active'); b.style.background=''; b.style.borderColor=''; b.style.color=''; });
  document.querySelectorAll('.side-nav-item').forEach(function(b){ b.classList.remove('active'); b.style.background=''; b.style.borderColor=''; b.style.color=''; });
  var btn = document.getElementById('nav-btn-' + name);
  if (btn) { btn.classList.add('active'); btn.style.background = colors[name]; btn.style.borderColor = borderColors[name]; btn.style.color = borderColors[name]; }
  var sideBtn = document.querySelector('.side-nav-item[data-section="' + name + '"]');
  if (sideBtn) { sideBtn.classList.add('active'); }
  document.querySelectorAll('.section-title').forEach(function(s){ s.classList.remove('section-highlight'); s.style.background=''; });
  var section = document.getElementById('section-' + name);
  if (section) {
    section.classList.add('section-highlight');
    section.style.background = colors[name];
    section.scrollIntoView({ behavior:'smooth', block:'start' });
    setTimeout(function(){ section.classList.remove('section-highlight'); }, 900);
  }
}
/* 滚动监听：自动高亮当前可见分区 */
function updateActiveNav() {
  var sections = ['general','specific','consumer','global','feedback'];
  var colors = { general:'#1a73e8', specific:'#e65100', consumer:'#2e7d32', global:'#7b1fa2', feedback:'#1565c0' };
  var offset = 120;
  var current = 'general';
  for (var i = 0; i < sections.length; i++) {
    var sec = document.getElementById('section-' + sections[i]);
    if (sec) {
      var rect = sec.getBoundingClientRect();
      if (rect.top <= offset) current = sections[i];
    }
  }
  document.querySelectorAll('.nav-btn').forEach(function(b){ b.classList.remove('active'); b.style.background=''; b.style.borderColor=''; b.style.color=''; });
  var btn = document.getElementById('nav-btn-' + current);
  if (btn) { btn.classList.add('active'); btn.style.background = '#' + colors[current].substring(1) + '18'; btn.style.borderColor = colors[current]; btn.style.color = colors[current]; }
  document.querySelectorAll('.side-nav-item').forEach(function(b){ b.classList.remove('active'); b.style.background=''; b.style.borderColor=''; b.style.color=''; });
  var sideBtn = document.querySelector('.side-nav-item[data-section="' + current + '"]');
  if (sideBtn) { sideBtn.classList.add('active'); }
}
window.addEventListener('scroll', updateActiveNav);
window.addEventListener('load', updateActiveNav);
</script>
"""

files = [
    "briefing_20260501.html",
    "briefing_20260502.html",
    "briefing_20260503.html",
    "briefing_20260504.html",
    "briefing_20260505.html",
    "briefing_20260506.html",
    "briefing_20260507.html",
    "briefing_20260508.html",
]

for fname in files:
    fpath = os.path.join(work_dir, fname)
    if not os.path.exists(fpath):
        print(f"SKIP (not found): {fname}")
        continue
    
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 1. 在 </style> 前插入侧边导航 CSS
    if '.side-nav' not in content:
        content = content.replace('</style>', css_addition + '</style>', 1)
    
    # 2. 在 <body> 后插入侧边导航 HTML
    if 'side-nav' not in content:
        content = content.replace('<body>', '<body>' + side_nav_html, 1)
    
    # 3. 替换 <script> 块
    # 找到现有的 <script> ... </script> 块并替换
    script_pattern = r'<script>.*?</script>'
    if re.search(script_pattern, content, re.DOTALL):
        content = re.sub(script_pattern, new_js, content, count=1, flags=re.DOTALL)
    else:
        # 没有 script 块，在 </body> 前插入
        content = content.replace('</body>', new_js + '\n</body>', 1)
    
    # 4. 确保有顶部 section-nav（如果还没有）
    if 'section-nav' not in content:
        # 在 card div 内、第一个 section-title 前插入 section-nav
        nav_html = """
<div class="section-nav" id="sectionNav">
  <div class="nav-btn" id="nav-btn-general" onclick="scrollToSection('general')"><span class="dot" style="background:#1a73e8;"></span>泛行业</div>
  <div class="nav-btn" id="nav-btn-specific" onclick="scrollToSection('specific')"><span class="dot" style="background:#e65100;"></span>细分领域</div>
  <div class="nav-btn" id="nav-btn-consumer" onclick="scrollToSection('consumer')"><span class="dot" style="background:#2e7d32;"></span>消费级</div>
  <div class="nav-btn" id="nav-btn-global" onclick="scrollToSection('global')"><span class="dot" style="background:#7b1fa2;"></span>海外</div>
  <div class="nav-btn" id="nav-btn-feedback" onclick="scrollToSection('feedback')"><span class="dot" style="background:#1565c0;"></span>用户口碑</div>
</div>
"""
        # 找到第一个 section-title 并插入之前
        content = re.sub(r'(<div class="section-title)', nav_html + r'\n\1', content, count=1)
    
    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"UPDATED: {fname}")
    else:
        print(f"UNCHANGED: {fname}")

print("\nDone!")
