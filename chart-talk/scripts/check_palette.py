#!/usr/bin/env python3
"""配色校验脚本（无第三方依赖，Python 3.8+）。

用法：
  python check_palette.py "#1f6fd1,#e8702a,#1b9e77" [--bg "#ffffff"] [--all-pairs] [--ordinal]

检查项（分类色）：
  1. 亮度带：OKLCH L 在 0.42-0.78（浅底）/ 0.48-0.70（深底，bg 亮度<0.5 自动判断）
  2. 彩度下限：C >= 0.09，否则看起来像灰色
  3. 色弱区分：红色盲(protan)/绿色盲(deutan)模拟后，相邻两色 ΔE(OKLab×100) >= 8 为通过，6-8 为警告（必须配直接标签）
  4. 正常视觉区分：相邻两色 ΔE >= 15，否则为失败
  5. 与背景对比度：>= 3:1 通过，2-3 警告（必须有数据标签或表格），<2 失败
灰色/辅助色（彩度 C < 0.03）会被自动识别为“弱化色”，只检查对比度（< 1.5 才警告），不参与 1-4 项。
--all-pairs：散点/地图/小多图等任意两色都可能相邻的场景，检查所有两两组合。
--ordinal：顺序色（漏斗阶段、等级、热力矩阵），改为检查亮度单调、相邻 ΔL >= 0.06、单一色相；
          对比度不足只警告（顺序色/热力格必须在格内或条旁标数字）。
退出码：0 = 无失败；1 = 有失败。
"""
import math
import sys

# Machado, Oliveira & Fernandes (2009) 严重度 1.0 模拟矩阵，作用于线性 RGB
PROTAN = ((0.152286, 1.052583, -0.204868),
          (0.114503, 0.786281, 0.099216),
          (-0.003882, -0.048116, 1.051998))
DEUTAN = ((0.367322, 0.860646, -0.227968),
          (0.280085, 0.672501, 0.047413),
          (-0.011820, 0.042940, 0.968881))


def hex_to_rgb(h):
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin_rgb(h):
    return tuple(to_linear(c) for c in hex_to_rgb(h))


def oklab(lin):
    r, g, b = lin
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklch(h):
    L, a, b = oklab(lin_rgb(h))
    return L, math.hypot(a, b), (math.degrees(math.atan2(b, a)) + 360) % 360


def simulate(lin, mat):
    return tuple(max(0.0, min(1.0, sum(mat[i][j] * lin[j] for j in range(3)))) for i in range(3))


def delta_e(a, b):
    return 100 * math.dist(a, b)


def luminance(h):
    r, g, b = lin_rgb(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main(argv):
    if not argv or argv[0].startswith('-'):
        print(__doc__)
        return 2
    colors = [c for c in argv[0].split(',') if c.strip()]
    bg = '#ffffff'
    if '--bg' in argv:
        bg = argv[argv.index('--bg') + 1]
    all_pairs = '--all-pairs' in argv
    ordinal = '--ordinal' in argv
    dark = luminance(bg) < 0.18
    fails, warns = [], []

    print(f"背景 {bg}（{'深色' if dark else '浅色'}），共 {len(colors)} 色\n")
    print(f"{'色值':<9} {'L':>5} {'C':>5} {'H':>5} {'对比度':>6}")
    lch = []
    neutrals = []
    if not ordinal:
        for c in colors:
            if oklch(c)[1] < 0.03:
                neutrals.append(c)
        colors = [c for c in colors if c not in neutrals]
        for c in neutrals:
            cr = contrast(c, bg)
            print(f"{c:<9} 弱化灰，对比度 {cr:.2f}（不参与分类色检查）")
            if cr < 1.5:
                warns.append(f"弱化灰 {c} 与背景对比度 {cr:.2f} < 1.5，几乎看不见")
    for c in colors:
        L, C, H = oklch(c)
        cr = contrast(c, bg)
        lch.append((L, C, H))
        print(f"{c:<9} {L:5.2f} {C:5.2f} {H:5.0f} {cr:6.2f}")
        if ordinal and cr < 3:
            warns.append(f"{c} 与背景对比度 {cr:.2f}：顺序色/热力格必须标数字")
        elif cr < 2:
            fails.append(f"{c} 与背景对比度 {cr:.2f} < 2")
        elif cr < 3:
            warns.append(f"{c} 与背景对比度 {cr:.2f} < 3：必须配数据标签或表格")

    if ordinal:
        Ls = [x[0] for x in lch]
        mono = all(Ls[i] > Ls[i + 1] for i in range(len(Ls) - 1)) or all(Ls[i] < Ls[i + 1] for i in range(len(Ls) - 1))
        if not mono:
            fails.append("顺序色亮度不单调")
        for i in range(len(Ls) - 1):
            if abs(Ls[i] - Ls[i + 1]) < 0.06:
                fails.append(f"{colors[i]} 与 {colors[i+1]} 亮度差 {abs(Ls[i]-Ls[i+1]):.3f} < 0.06")
        hues = [x[2] for x in lch if x[1] > 0.03]
        if hues:
            spread = max(min(abs(a - b), 360 - abs(a - b)) for a in hues for b in hues)
            if spread > 40:
                warns.append(f"顺序色色相跨度 {spread:.0f}° 偏大，建议单一色相")
    else:
        lo, hi = (0.48, 0.70) if dark else (0.42, 0.78)
        for c, (L, C, _) in zip(colors, lch):
            if not lo <= L <= hi:
                fails.append(f"{c} 亮度 L={L:.2f} 不在 {lo}-{hi}")
            if C < 0.09:
                fails.append(f"{c} 彩度 C={C:.2f} < 0.09，会被看成灰色")
        n = len(colors)
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n)] if all_pairs else [(i, i + 1) for i in range(n - 1)]
        labs = {k: [oklab(simulate(lin_rgb(c), m) if m else lin_rgb(c)) for c in colors]
                for k, m in (('normal', None), ('protan', PROTAN), ('deutan', DEUTAN))}
        print(f"\n{'检查的配对':<20} {'正常':>6} {'红色盲':>6} {'绿色盲':>6}")
        worst_cvd, worst_norm = 999, 999
        for i, j in pairs:
            dn = delta_e(labs['normal'][i], labs['normal'][j])
            dp = delta_e(labs['protan'][i], labs['protan'][j])
            dd = delta_e(labs['deutan'][i], labs['deutan'][j])
            print(f"{colors[i]}-{colors[j]:<10} {dn:6.1f} {dp:6.1f} {dd:6.1f}")
            worst_norm = min(worst_norm, dn)
            cvd = min(dp, dd)
            worst_cvd = min(worst_cvd, cvd)
            if dn < 15:
                fails.append(f"{colors[i]} 与 {colors[j]} 正常视觉 ΔE {dn:.1f} < 15")
            if cvd < 6:
                fails.append(f"{colors[i]} 与 {colors[j]} 色弱 ΔE {cvd:.1f} < 6")
            elif cvd < 8:
                warns.append(f"{colors[i]} 与 {colors[j]} 色弱 ΔE {cvd:.1f} 在 6-8：必须加直接标签")
        if pairs:
            print(f"\n最差配对：正常 ΔE {worst_norm:.1f}，色弱 ΔE {worst_cvd:.1f}")
        else:
            print("\n只有 1 个彩色，无需配对检查")

    print()
    for w in warns:
        print("警告：" + w)
    for f in fails:
        print("失败：" + f)
    print("结论：" + ("失败，先修正再出图" if fails else ("通过（有警告，按提示补救）" if warns else "全部通过")))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
