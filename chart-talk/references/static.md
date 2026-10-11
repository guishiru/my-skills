# 静态图片（matplotlib PNG）

用于贴进 PPT、文档、群聊。原则和 Excel、网页一样：标题是结论、口径写在副标题、按比较类型选图。

## 中文字体（先做这一步，否则中文显示成方框）

```python
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

def use_cjk_font():
    prefer = ["Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC",
              "WenQuanYi Micro Hei", "SimHei", "Noto Sans CJK JP"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in prefer:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    else:
        raise RuntimeError("没有找到中文字体：先安装 Noto Sans CJK 或微软雅黑")
    plt.rcParams["axes.unicode_minus"] = False   # 负号正常显示
use_cjk_font()
```

用无衬线字体（黑体类），不要用宋体（Serif）。

## 样式基线

```python
INK, INK2, GRID, MUTED, BLUE = "#1f2329", "#646a73", "#e6e8eb", "#b4b8bf", "#2563c9"
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 11,
})

def titles(fig, title, subtitle):
    """标题 = 结论，副标题 = 口径；左对齐。"""
    fig.text(0.01, 0.99, title, ha="left", va="top", fontsize=16, weight="bold", color=INK)
    fig.text(0.01, 0.935, subtitle, ha="left", va="top", fontsize=10, color=INK2)
    fig.subplots_adjust(top=0.84)
```

## 横向条形（排序 + 单项高亮 + 全标数字）

```python
fig, ax = plt.subplots(figsize=(8, 4.5))
order = sorted(zip(names, values), key=lambda x: x[1])            # barh 从下往上画，所以升序
ns, vs = zip(*order)
colors = [BLUE if n == focus else MUTED for n in ns]
bars = ax.barh(ns, vs, color=colors, height=0.6)
for b, v in zip(bars, vs):
    ax.text(b.get_width(), b.get_y() + b.get_height()/2, f" {v:,.1f}", va="center", color=INK, fontsize=10)
ax.xaxis.set_visible(False); ax.grid(False); ax.spines["bottom"].set_visible(False); ax.tick_params(left=False)
ax.set_xlim(0, max(vs) * 1.15)                                     # 从 0 开始，给标签留空间
titles(fig, "成都 30 日留存 38%，领先第二名 5 个百分点", "2026 年 Q3 · 8 个城市 · 来源：用户中台")
fig.savefig("out.png")
```

## 量 + 率（成对横向条形，代替双坐标轴）

```python
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, gridspec_kw={"wspace": 0.25})
# 两个面板共用城市顺序（按“量”降序），各自从 0 开始；主角高亮，其余灰色
```

## 出图后检查

用 Read 工具打开 PNG 看一遍：中文是否正常、标签有无重叠或裁切、标题是否为结论、颜色是否按页面颜色表来。
导出给 PPT 用时，宽高比 16:9（如 `figsize=(11, 6.2)`），字号不小于 10。
