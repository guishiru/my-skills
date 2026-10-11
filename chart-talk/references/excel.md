# Excel 原生图表（openpyxl）

目标：交付的 .xlsx 打开就是**原生图表**（可在 Excel 里继续编辑），而不是贴一张图片。

## 基本原则

- 数据放在一个清楚的数据区（表头 + 数据），图表引用这块区域；用户改数据，图会跟着变。
- 计算列（环比、达成率、占比）用 **Excel 公式**写，不要把 Python 算好的结果写死在单元格里。
- 图表标题 = 结论；口径写在图表上方的单元格中（openpyxl 的图表不支持副标题）。
- 一个工作表放 1–4 张图，图和图之间不要重叠；数据区放在图的左侧或上方。
- 字体：中文环境用「微软雅黑」，标题 12–14pt，其余 9–10pt。

## 可复用的代码片段

```python
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText
from openpyxl.drawing.text import Paragraph, ParagraphProperties, CharacterProperties, Font as DFont
from openpyxl.drawing.line import LineProperties

BLUE, GRAY, GRID, INK, INK2 = "2563C9", "B4B8BF", "E6E8EB", "1F2329", "646A73"

def text_props(size=900, color=INK2, bold=False):
    cp = CharacterProperties(sz=size, b=bold, solidFill=color, latin=DFont(typeface="微软雅黑"), ea=DFont(typeface="微软雅黑"))
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])

def style_chart(ch, title):
    ch.title = title
    ch.title.tx.rich.p[0].pPr = ParagraphProperties(defRPr=CharacterProperties(sz=1300, b=True, solidFill=INK, latin=DFont(typeface="微软雅黑"), ea=DFont(typeface="微软雅黑")))
    ch.style = 2
    ch.width, ch.height = 18, 9          # 厘米
    # 网格线：浅灰实线
    if ch.y_axis.majorGridlines is not None:
        ch.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill=GRID, w=6350))
    for ax in (ch.x_axis, ch.y_axis):
        ax.txPr = text_props()
        ax.delete = False                 # 新版 openpyxl 默认隐藏坐标轴，必须显式打开
        ax.spPr = GraphicalProperties(ln=LineProperties(solidFill=GRID))
    ch.legend = None                      # 单系列不要图例；多系列时再设置 ch.legend.position = "t"
    return ch

def fill_series(s, color, line=False, width_emu=25400):
    if line:
        s.graphicalProperties.line.solidFill = color
        s.graphicalProperties.line.width = width_emu   # 25400 EMU = 2pt
        s.smooth = False
    else:
        s.graphicalProperties.solidFill = color
        s.graphicalProperties.line.noFill = True

def highlight_point(series, idx, color):
    """把第 idx 个柱子单独涂色（强调手法）。"""
    pt = DataPoint(idx=idx)
    pt.graphicalProperties.solidFill = color
    pt.graphicalProperties.line.noFill = True
    series.dPt.append(pt)

def label_points(series, idxs=None, num_fmt=None, ser_name=False, pos=None):
    """idxs=None：全部标注（只在类目 ≤12 时用）；否则只标指定点。
    ser_name=True：线尾标签显示“系列名 数值”。pos：'outEnd'（柱/条末端外）、'r'（折线右侧）、't'（上方）。
    注意：单点 DataLabel 不继承系列层的字体/位置/格式，必须逐个设置。"""
    from openpyxl.chart.label import DataLabel
    series.dLbls = DataLabelList()
    series.dLbls.showVal = idxs is None
    series.dLbls.showSerName = series.dLbls.showCatName = series.dLbls.showLegendKey = False
    series.dLbls.showPercent = False
    series.dLbls.txPr = text_props(900, INK)
    if num_fmt: series.dLbls.numFmt = num_fmt
    if pos: series.dLbls.position = pos
    for i in (idxs or []):
        d = DataLabel(idx=i, showVal=True, showSerName=ser_name, showCatName=False, showLegendKey=False, showPercent=False)
        d.txPr = text_props(900, INK)
        if pos: d.position = pos
        if num_fmt: d.numFmt = num_fmt
        if ser_name: d.separator = "\u00a0"   # Excel 显示为空格；LibreOffice 预览会显示成“;”，属渲染差异
        series.dLbls.dLbl.append(d)
```

### 横向条形（项目比较，已排序，单项高亮）

```python
ch = BarChart(); ch.type = "bar"           # bar = 横向
ch.gapWidth = 60                           # 条粗约为类目宽度的 60%
ch.x_axis.scaling.orientation = "maxMin"   # 第一行显示在最上面（数据按降序排列时）
data = Reference(ws, min_col=2, min_row=1, max_row=n+1)
cats = Reference(ws, min_col=1, min_row=2, max_row=n+1)
ch.add_data(data, titles_from_data=True); ch.set_categories(cats)
s = ch.series[0]; fill_series(s, GRAY); highlight_point(s, idx_of_focus, BLUE)
label_points(s)                            # 条形少于 12 个时可全部标注
style_chart(ch, "成都 30 日留存 38%，领先第二名 6 个百分点")
ch.y_axis.delete = True                    # 已有数据标签时可去掉数值轴（必须在 style_chart 之后设置）
ws.add_chart(ch, "E2")
```

### 实际 vs 目标（柱形 + 目标线，同一坐标轴）

```python
bar = BarChart(); bar.type = "col"; bar.gapWidth = 80
bar.add_data(Reference(ws, min_col=2, min_row=1, max_row=13), titles_from_data=True)   # 实际
bar.set_categories(Reference(ws, min_col=1, min_row=2, max_row=13))
fill_series(bar.series[0], BLUE)
line = LineChart()
line.add_data(Reference(ws, min_col=3, min_row=1, max_row=13), titles_from_data=True)  # 目标
fill_series(line.series[0], GRAY, line=True, width_emu=19050)
line.series[0].graphicalProperties.line.dashStyle = "sysDash"   # 目标线是唯一允许用虚线的地方
line.series[0].marker.symbol = "none"
bar += line                                # 合并到同一个坐标轴，不要设置 y_axis.axId=200（那是双轴）
style_chart(bar, "9 月订单 41.2 万单，连续 3 个月未达目标")
from openpyxl.chart.legend import Legend
bar.legend = Legend(); bar.legend.position = "t"   # style_chart 默认去掉图例；多系列时在它之后重新加上
bar.y_axis.scaling.min = 0                 # 柱形图从 0 开始
```

### 折线（趋势，突出一条，其余灰色）

```python
ch = LineChart()
ch.add_data(Reference(ws, min_col=2, max_col=k+1, min_row=1, max_row=m+1), titles_from_data=True)
ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=m+1))
for i, s in enumerate(ch.series):
    fill_series(s, BLUE if i == focus else GRAY, line=True, width_emu=28575 if i == focus else 15875)
    s.marker.symbol = "none"
label_points(ch.series[focus], idxs=[m-1])   # 只标注主角的最后一个点
```

### 100% 堆叠条（成分比较）

```python
ch = BarChart(); ch.type = "bar"; ch.grouping = "percentStacked"; ch.overlap = 100; ch.gapWidth = 50
ch.x_axis.scaling.orientation = "maxMin"   # 让第一行（如 1 月）显示在最上面
# 系列按页面颜色表上色：fill_series(ch.series[i], COLOR_OF[name])
# 只给要讲的那一段加数据标签；深色块上用白字，浅色块（灰、黄）上用深色字
```

### 漏斗（顺序色，横向条形）

用横向条形，系列只有一个，每个阶段用 `highlight_point` 按顺序色（深 → 浅）上色。转化率写在旁边的公式列中，并用数据标签或单元格显示。

## 汇报页布局

- **汇报页与数据页分开**：给老板看的“汇报”页只放总结论、口径和图；原始数据和公式列放在“数据”页，图表引用“数据”页。
- **总结论**写在汇报页 B2（加粗 14pt），口径写在 B3；每张图上方一行写“图 N｜口径”，**口径行和图表锚点之间空一行**，否则渲染时会重叠。
- 每张图约占 20 行；图与图之间用分页符隔开，打印/导出 PDF 时每页一张：
  `from openpyxl.worksheet.pagebreak import Break; ws.row_breaks.append(Break(id=行号))`
- 页面设置：横向、缩放到一页宽（见下文“出图后检查”）。

## 不要做

- `y_axis.axId = 200` + `y_axis.crosses = "max"`：这会生成双坐标轴，禁止使用。
- 3D 图表（`BarChart3D`、`PieChart3D`）。
- 把图表导出成图片再插入：会失去可编辑性。
- 默认的 Office 彩色主题：必须逐个系列显式设置颜色。

## 出图后检查（必须做）

```bash
soffice --headless --convert-to pdf out.xlsx    # 用 LibreOffice 渲染
pdftoppm -png -r 80 out.pdf preview              # 转成 PNG 后查看
```

渲染前给每个工作表设置横向、缩放到一页宽，否则一张图会被切到两页：
`ws.page_setup.orientation = "landscape"; ws.sheet_properties.pageSetUpPr.fitToPage = True; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0`

查看 PNG：标题是否为结论、坐标轴是否显示、标签有无重叠、颜色是否按预期。
LibreOffice 的渲染和 Excel 会有细微差异（字体、标签位置），以“结构正确”为准。
