# 网页 / 看板

交付物：**单个 HTML 文件**，双击即可打开。CSS 和 JS 写在文件内；外部库只引用固定版本。

## 技术选择

- **默认 ECharts**（国内最常用，平台普遍可加载）：
  `<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>`
  如果 CDN 被拦截，改用 `https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.1/echarts.min.js`。
- **先测试 CDN 能否加载**（很多办公平台、内网会拦截）。加载不了，或者环境不能联网 → 用本 skill 的 `assets/svg-charts.js`：把整个文件内容粘贴进页面的 `<script>`，提供横向条形（自动处理正负）、柱形 + 目标线、折线（线尾标名称、十字线提示）、表格视图切换，已在桌面和手机宽度测试过。热力矩阵直接用 HTML 表格加背景色（格内标数字）即可。
- CDN 测试方法：`curl -sI https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js | head -1`，返回 200 才能用；用户最终打开页面的环境（公司内网、办公平台）也可能拦截，拿不准时直接用 SVG 方案。
- svg-charts.js 没有的图形（散点、漏斗、热力矩阵）：散点照着 `line` 的坐标换算写 `<circle>`，点旁直接标名称；漏斗用 HTML 条形（div 宽度按比例）或 `hbar`；热力矩阵用 HTML 表格加背景色。
- 页面加载外部库失败时**不能白屏**：用 `typeof echarts === 'undefined'` 判断，失败就回退到 SVG。

## 页面结构（看板）

```
┌ 页面标题 = 总结论 ─────────────────────────────┐
│ 口径行：时间范围 · 单位 · 来源 · 更新时间          │
├ 筛选条（一行，放在所有图上方；先放时间范围）─────┤
├ 指标卡 ×3–5（一个英雄数字）────────────────────┤
├ 图表卡片（每张：小标题 = 分论点；右上角可切换“表格视图”）┤
└──────────────────────────────────────────────┘
```

- 卡片宽度自适应；窄屏（<640px）单列排列，左右留 16px 边距，不能出现横向滚动。
- 每张图都要有“表格视图”切换（可读性和无障碍的兜底）。
- 筛选条控制下方所有图表，所有数字基于同一份数据切片。数据没有可筛选的共同维度时（如漏斗、留存没有城市字段），**不要放筛选条**，或者在受影响的图上写明“全国口径，不随筛选变化”。

## CSS 变量（浅色 / 深色）

```css
:root{--bg:#ffffff;--card:#ffffff;--ink:#1f2329;--ink2:#646a73;--grid:#e6e8eb;--muted:#b4b8bf;
  --c1:#2563c9;--c2:#d9711c;--c3:#12a08a;--c4:#b88a00;--c5:#d6609c;--c6:#4e9a2e;--c7:#8a5cd1;--c8:#d64545;}
@media (prefers-color-scheme: dark){:root{--bg:#111214;--card:#18191c;--ink:#e8eaed;--ink2:#a0a5ad;--grid:#2e3138;--muted:#5a5f68;}}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
```

在 JS 中用 `getComputedStyle(document.documentElement).getPropertyValue('--c1')` 读取颜色，传给 ECharts。监听 `matchMedia('(prefers-color-scheme: dark)')` 的变化，变化时重新 setOption。

## ECharts 公共配置

```js
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const base = () => ({
  textStyle:{fontFamily:'PingFang SC, Microsoft YaHei, sans-serif', color:css('--ink2')},
  grid:{left:8, right:24, top:16, bottom:8, containLabel:true},   // containLabel 防止轴标签被裁切
  tooltip:{trigger:'axis', axisPointer:{type:'line', lineStyle:{color:css('--muted')}},
           valueFormatter:v=>v==null?'-':v.toLocaleString('zh-CN')},
  xAxis:{axisLine:{lineStyle:{color:css('--grid')}}, axisTick:{show:false}, axisLabel:{color:css('--ink2')}},
  yAxis:{splitLine:{lineStyle:{color:css('--grid'), type:'solid'}}, axisLine:{show:false}, axisLabel:{color:css('--ink2')}},
  animationDuration:300,
});
```

图元规格：
- 柱：`barMaxWidth:24, itemStyle:{borderRadius:[3,3,0,0]}`（横向条形用 `[0,3,3,0]`）
- 折线：`lineStyle:{width:2}, symbol:'circle', symbolSize:7, showSymbol:false`（悬停时才显示点），`emphasis:{focus:'series'}`
- 目标线：`markLine:{symbol:'none', lineStyle:{type:'dashed', color:css('--muted')}, data:[{yAxis:target, label:{formatter:'目标 {c}'}}]}`
- 单点高亮：`data` 中对该项写 `{value:v, itemStyle:{color:css('--c1')}}`，其余项用 `--muted`
- 选择性标签：只给特定数据项写 `label:{show:true, position:'right'}`
- **只用一个 yAxis**。不要写 `yAxis:[{},{}]`。

## 指标卡

```html
<div class="kpi"><div class="kpi-label">9 月订单量</div>
  <div class="kpi-value">41.2<span>万单</span></div>
  <div class="kpi-delta down">▼ 12.0% 较 8 月</div>
  <div class="spark" id="spark1"></div></div>
```

变化方向用 ▲▼ 符号加颜色（不能只靠颜色区分）；数值使用比例字宽（不要加 tabular-nums）。

## 安全

类目名、系列名来自数据，插入 DOM 时用 `textContent`，不要用 `innerHTML` 拼接字符串。

## 出图后检查（必须做）

用无头浏览器截图后查看：

```bash
python - <<'EOF'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':1280,'height':900})
    pg.goto('file:///绝对路径/dashboard.html'); pg.wait_for_timeout(1500)
    pg.screenshot(path='shot.png', full_page=True)
    pg.set_viewport_size({'width':390,'height':844}); pg.screenshot(path='shot_mobile.png', full_page=True)
    b.close()
EOF
```

检查：标题是否为结论、标签是否重叠或裁切、手机宽度下有无横向滚动、控制台有无报错。
