/* svg-charts.js —— 无外部依赖的 SVG 图表函数（chart-talk skill 配套）
 * 用法：把本文件内容整段粘贴进 HTML 的 <script> 中，然后调用：
 *   SC.hbar(el, {data:[{label:'成都', value:18}], fmt:v=>v+'%', focus:'成都'})        // 横向条形（自动处理正负值）
 *   SC.columns(el, {categories:[...], values:[...], target:[...]|number, fmt, highlight:i=>bool})  // 柱形 + 目标线
 *   SC.line(el, {categories:[...], series:[{name, values, color?, focus?}], fmt})     // 折线，线尾直接标名称
 *   SC.table(btnEl, chartEl, headers, rows)   // “表格视图”切换
 * 颜色读取 CSS 变量：--c1..--c8 --muted --grid --ink --ink2 --card；窗口宽度变化时自动重画。
 */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const text = (parent, x, y, str, attrs) => {
    const t = el('text', Object.assign({ x, y, fill: css('--ink2'), 'font-size': 12 }, attrs || {}), parent);
    t.textContent = str;              // 数据来的文字一律用 textContent
    return t;
  };
  const niceMax = v => {
    if (v <= 0) return 0;
    const p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  };
  const ticks = (lo, hi, count) => {
    const step = niceMax((hi - lo) / count), out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  };

  // ---- 共享悬停提示 ----
  let tip;
  function showTip(evt, html) {
    if (!tip) {
      tip = document.createElement('div');
      Object.assign(tip.style, { position: 'fixed', pointerEvents: 'none', padding: '6px 10px', borderRadius: '6px',
        font: '12px/1.5 sans-serif', boxShadow: '0 2px 8px rgba(0,0,0,.15)', zIndex: 99 });
      document.body.appendChild(tip);
    }
    tip.style.background = css('--card') || '#fff'; tip.style.color = css('--ink');
    tip.replaceChildren(...html.map(([k, v]) => {
      const d = document.createElement('div'); const b = document.createElement('b');
      b.textContent = v; d.append(b, ' ' + k); return d;
    }));
    tip.style.display = 'block';
    const x = Math.min(evt.clientX + 12, innerWidth - tip.offsetWidth - 8);
    tip.style.left = x + 'px'; tip.style.top = (evt.clientY + 12) + 'px';
  }
  const hideTip = () => tip && (tip.style.display = 'none');

  function mount(container, draw) {
    const render = () => {
      container.replaceChildren();
      const w = Math.max(280, container.clientWidth);
      draw(w);
    };
    render();
    let t; addEventListener('resize', () => { clearTimeout(t); t = setTimeout(render, 120); });
    if (window.matchMedia) matchMedia('(prefers-color-scheme: dark)').addEventListener('change', render);
    return render;
  }

  // ---- 横向条形 ----
  function hbar(container, o) {
    const fmt = o.fmt || (v => v.toLocaleString('zh-CN'));
    return mount(container, w => {
      const d = o.data, rowH = o.rowH || 30, barH = Math.min(18, rowH * 0.6);
      const labelW = o.labelW || 64, pad = 56, h = d.length * rowH + 24;
      const svg = el('svg', { width: w, height: h, role: 'img' }, container);
      const lo = Math.min(0, ...d.map(x => x.value)), hi = Math.max(0, ...d.map(x => x.value));
      const plotW = w - labelW - pad * (lo < 0 ? 2 : 1);
      const x0 = labelW + (lo < 0 ? pad : 0);
      const sx = v => x0 + (v - lo) / ((hi - lo) || 1) * plotW;
      d.forEach((r, i) => {
        const y = i * rowH + 8;
        text(svg, labelW - 8, y + barH / 2 + 4, r.label, { 'text-anchor': 'end', fill: css('--ink') });
        const xa = sx(Math.min(0, r.value)), xb = sx(Math.max(0, r.value));
        const color = r.color || (o.focus ? (r.label === o.focus ? css('--c1') : css('--muted'))
          : (r.value < 0 ? (o.negColor || css('--c8')) : css('--c1')));
        const bar = el('rect', { x: xa, y, width: Math.max(1, xb - xa), height: barH, rx: 3, fill: color }, svg);
        bar.addEventListener('pointermove', e => showTip(e, [[r.label, fmt(r.value)]]));
        bar.addEventListener('pointerleave', hideTip);
        const right = r.value >= 0;
        text(svg, right ? xb + 6 : xa - 6, y + barH / 2 + 4, fmt(r.value),
          { 'text-anchor': right ? 'start' : 'end', fill: css('--ink') });
      });
      if (lo < 0) el('line', { x1: sx(0), x2: sx(0), y1: 4, y2: h - 16, stroke: css('--ink2'), 'stroke-width': 1 }, svg);
    });
  }

  // ---- 柱形 + 目标线 ----
  function columns(container, o) {
    const fmt = o.fmt || (v => v.toLocaleString('zh-CN'));
    return mount(container, w => {
      const h = o.height || 260, m = { l: 40, r: 12, t: 16, b: 28 };
      const svg = el('svg', { width: w, height: h, role: 'img' }, container);
      const n = o.categories.length, tg = Array.isArray(o.target) ? o.target : o.target != null ? Array(n).fill(o.target) : null;
      const hi = niceMax(Math.max(...o.values, ...(tg || [0])) * 1.08);
      const pw = w - m.l - m.r, ph = h - m.t - m.b, bw = Math.min(tg ? 28 : 24, pw / n * 0.6);
      const sy = v => m.t + ph - v / hi * ph, cx = i => m.l + pw / n * (i + 0.5);
      ticks(0, hi, 4).forEach(t => {
        el('line', { x1: m.l, x2: w - m.r, y1: sy(t), y2: sy(t), stroke: css('--grid') }, svg);
        text(svg, m.l - 6, sy(t) + 4, fmt(t), { 'text-anchor': 'end', 'font-size': 11 });
      });
      o.categories.forEach((c, i) => {
        const v = o.values[i], on = o.highlight ? o.highlight(i) : true;
        const r = el('rect', { x: cx(i) - bw / 2, y: sy(v), width: bw, height: sy(0) - sy(v), rx: 3,
          fill: on ? css('--c1') : css('--muted') }, svg);
        r.addEventListener('pointermove', e => showTip(e, [['实际', fmt(v)], ...(tg ? [['目标', fmt(tg[i])]] : [])].map(([k, x]) => [c + ' ' + k, x])));
        r.addEventListener('pointerleave', hideTip);
        if (n <= 12) {          // 有目标线时标签放进柱顶内侧（白字），避免和目标线重叠
          if (tg && sy(0) - sy(v) > 22) text(svg, cx(i), sy(v) + 14, fmt(v), { 'text-anchor': 'middle', 'font-size': 10, fill: '#fff' });
          else text(svg, cx(i), sy(v) - 4, fmt(v), { 'text-anchor': 'middle', 'font-size': 11, fill: css('--ink') });
        }
        text(svg, cx(i), h - 8, c, { 'text-anchor': 'middle', 'font-size': 11 });
      });
      if (tg) {
        const pts = tg.map((v, i) => [cx(i) - pw / n / 2, sy(v), cx(i) + pw / n / 2, sy(v)]);
        el('path', { d: pts.map((p, i) => (i ? 'L' : 'M') + p[0] + ' ' + p[1] + ' L' + p[2] + ' ' + p[3]).join(' '),
          fill: 'none', stroke: css('--ink2'), 'stroke-dasharray': '4 3', 'stroke-width': 1.5 }, svg);
      }
    });
  }

  // ---- 折线（线尾直接标名称）----
  function line(container, o) {
    const fmt = o.fmt || (v => v.toLocaleString('zh-CN'));
    return mount(container, w => {
      const h = o.height || 260, m = { l: 40, r: 96, t: 16, b: 28 };
      const svg = el('svg', { width: w, height: h, role: 'img' }, container);
      const all = o.series.flatMap(s => s.values);
      const lo = o.zero === false ? Math.min(...all) : 0, hi = niceMax(Math.max(...all) * 1.05);
      const n = o.categories.length, pw = w - m.l - m.r, ph = h - m.t - m.b;
      const sx = i => m.l + (n === 1 ? pw / 2 : pw * i / (n - 1)), sy = v => m.t + ph - (v - lo) / ((hi - lo) || 1) * ph;
      ticks(lo, hi, 4).forEach(t => {
        el('line', { x1: m.l, x2: w - m.r, y1: sy(t), y2: sy(t), stroke: css('--grid') }, svg);
        text(svg, m.l - 6, sy(t) + 4, fmt(t), { 'text-anchor': 'end', 'font-size': 11 });
      });
      const step = Math.ceil(n / Math.max(2, Math.floor(pw / 56)));
      o.categories.forEach((c, i) => { if (i % step === 0 || i === n - 1) text(svg, sx(i), h - 8, c, { 'text-anchor': 'middle', 'font-size': 11 }); });
      const hasFocus = o.series.some(s => s.focus);
      const used = new Set(o.series.map(s => s.color).filter(Boolean).map(c => c.toLowerCase()));
      const auto = [1, 2, 3, 4, 5, 6, 7, 8].map(i => css('--c' + i)).filter(c => c && !used.has(c.toLowerCase()));
      let ai = 0;
      const ends = [];
      o.series.forEach(s => {
        const color = s.color || (hasFocus && !s.focus ? css('--muted') : auto[ai++ % auto.length]);
        el('path', { d: s.values.map((v, i) => (i ? 'L' : 'M') + sx(i) + ' ' + sy(v)).join(' '), fill: 'none',
          stroke: color, 'stroke-width': hasFocus && !s.focus ? 1.5 : 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
        ends.push({ y: sy(s.values[n - 1]), s, color });
      });
      ends.sort((a, b) => a.y - b.y);                        // 线尾标签：按位置排开，最小间距 14px
      for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 14);
      ends.forEach(e => {
        el('circle', { cx: sx(n - 1), cy: sy(e.s.values[n - 1]), r: 3.5, fill: e.color, stroke: css('--card') || '#fff', 'stroke-width': 2 }, svg);
        text(svg, sx(n - 1) + 8, e.y + 4, e.s.name + ' ' + fmt(e.s.values[n - 1]), { fill: css('--ink'), 'font-size': 11 });
      });
      // 十字线 + 全系列提示
      const guide = el('line', { y1: m.t, y2: m.t + ph, stroke: css('--muted'), visibility: 'hidden' }, svg);
      const hit = el('rect', { x: m.l, y: m.t, width: pw, height: ph, fill: 'transparent' }, svg);
      hit.addEventListener('pointermove', e => {
        const r = svg.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.round((e.clientX - r.left - m.l) / pw * (n - 1))));
        guide.setAttribute('x1', sx(i)); guide.setAttribute('x2', sx(i)); guide.setAttribute('visibility', 'visible');
        showTip(e, o.series.map(s => [s.name + '（' + o.categories[i] + '）', fmt(s.values[i])]));
      });
      hit.addEventListener('pointerleave', () => { guide.setAttribute('visibility', 'hidden'); hideTip(); });
    });
  }

  // ---- 表格视图切换 ----
  function table(button, chartEl, headers, rows) {
    const tbl = document.createElement('table');
    tbl.style.cssText = 'width:100%;border-collapse:collapse;font-size:13px;display:none';
    const tr = (cells, tag) => { const r = document.createElement('tr');
      cells.forEach((c, i) => { const td = document.createElement(tag); td.textContent = c;
        td.style.cssText = 'padding:6px 8px;border-bottom:1px solid var(--grid);text-align:' + (i ? 'right' : 'left'); r.appendChild(td); });
      return r; };
    tbl.appendChild(tr(headers, 'th')); rows.forEach(r => tbl.appendChild(tr(r, 'td')));
    chartEl.after(tbl);
    button.addEventListener('click', () => {
      const showTable = tbl.style.display === 'none';
      tbl.style.display = showTable ? 'table' : 'none'; chartEl.style.display = showTable ? 'none' : '';
      button.textContent = showTable ? '图表视图' : '表格视图';
    });
  }

  window.SC = { hbar, columns, line, table, css };
})();
