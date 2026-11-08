#!/usr/bin/env python3
"""S1/S2 规则检查：事实表 → 取值冲突、时间顺序、期限、金额加总、陈述漂移、同步改口、事后补强、存续期、时间窗口、金额仅言词、文本雷同、陈述跟随被推翻的推测、文风比对，输出 Excel + JSON。

用法:
  python check_facts.py facts.json [constraints.json] [--synonyms synonyms.json] [--texts texts.json] [--out 案件事实表.xlsx]

facts.json      : [{id, source, quote, date, time?, subject, object, attribute, value, amount, currency, party, nature,
                    state?, speaker?, version?, formed_date?, entity?}, ...]
                  nature: 客观记录 / 当事人陈述 / 证人证言 / 法院认定；state: true 表示该属性会随时间合法变化
                  speaker/version: 陈述人与第几次陈述（同一人多次笔录、证言）
                  stated_on: 陈述/出具日期（笔录日期、证言日期、文书落款日期）
                  formed_date: 仅在实际形成日期与落款不同（补写、重新打印、元数据显示更晚）时填写
                  contemporaneous: true 表示该证据按其性质应在事发当时形成（收条、交接单、当时的记录）
                  entity: 事件涉及的地点/公司/物品名称，用于存续期核验
                  disputed: true 表示该书证真伪有争议（如签名待鉴定的借条），不计为金额的客观佐证
                  nature 填"推测"的事实：对方或办案机关当时的推测；overturned_by 填推翻它的事实 id
texts.json 可加 "role": "known"（本人平时所写）/ "disputed"（署名为本人但有疑问的材料），用于文风比对
constraints.json: {"order":[{"before":"F003","after":"F010","reason":"..."}],
                   "sums":[{"total":"F020","parts":["F021","F022"],"reason":"..."}],
                   "deadlines":[{"start":"F012","add_months":12,"add_days":15,"compare":"F030",
                                 "expect":"reached","reason":"原告主张起诉时质保金已到期"}],
                   "entities":[{"name":"某茶楼","start":"2021-07-01","end":"","source":"工商登记"}],
                   "windows":[{"from":"F010","to":"F011","min_minutes":90,"reason":"高铁到站后赶到茶楼至少需要"}],
                   "filing_date":"2024-04-10", "sync_days":60, "late_days":30}
synonyms.json   : {"A320": ["空客320", "空客A320"], ...}   把右边的写法统一成左边
texts.json      : [{"id":"W1","speaker":"证人甲","text":"证言全文"}, ...]  用 --texts 传入，做文本雷同比对
"""
import argparse, json, re, sys
from collections import defaultdict

NA = {"", None, "未载明", "不详", "无"}

def norm_text(s):
    if s is None:
        return ""
    s = str(s).strip()
    # 全角转半角
    s = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in s)
    return re.sub(r"\s+", "", s).upper()

def norm_date(s):
    """'2018年10月5日' / '2018.10.5' / '2018-10' → '2018-10-05' / '2018-10'；无法解析返回原值。"""
    if s in NA:
        return ""
    t = str(s).strip()
    m = re.match(r"^(\d{4})\D{0,2}(\d{1,2})?(?:\D{0,2}(\d{1,2}))?\D*$", t)
    if not m:
        return t
    y, mo, d = m.groups()
    out = y
    if mo:
        out += f"-{int(mo):02d}"
    if d:
        out += f"-{int(d):02d}"
    return out

def norm_amount(a):
    """'130万元' / '1,200,000' / 1.3e6 → float(元)；无法解析返回 None。"""
    if a in NA:
        return None
    if isinstance(a, (int, float)):
        return float(a)
    t = str(a).replace(",", "").replace("，", "").strip()
    mult = 1
    if "亿" in t:
        mult = 1e8
    elif "万" in t:
        mult = 1e4
    m = re.search(r"-?\d+(\.\d+)?", t)
    return float(m.group()) * mult if m else None

def kind(f):
    """把 nature/party 归一成：客观记录 / 当事人陈述 / 法院认定。"""
    n = str(f.get("nature", "")) + str(f.get("party", ""))
    if "推测" in n or "假设" in n:
        return "推测"         # 侦查/对方/鉴定前的推测，不是证据
    if "法院" in n or "认定" in n:
        return "法院认定"
    if "证人" in n or "证言" in n or "陈述" in n or "笔录" in n:
        return "当事人陈述"   # 言词证据（含证人证言），不能当书证
    if "客观" in n or "书证" in n or "记录" in n or "第三方" in n:
        return "客观记录"
    return "当事人陈述"

def load_synonyms(path):
    if not path:
        return {}
    raw = json.load(open(path, encoding="utf-8"))
    table = {}
    for canon, alts in raw.items():
        for a in [canon] + list(alts):
            table[norm_text(a)] = norm_text(canon)
    return table

def check(facts, cons, syn):
    by_id = {f["id"]: f for f in facts}
    issues = []

    # 0. 结构检查：每条事实必须有出处
    for f in facts:
        if f.get("source") in NA:
            issues.append({"type": "缺少出处", "level": "提示", "rule": f["id"], "detail": "事实没有材料编号/页码，不应进入分析"})
        f["_date"] = norm_date(f.get("date"))
        f["_amount"] = norm_amount(f.get("amount"))

    # 1. 同一对象同一属性取值不一致（按材料性质分级，避免把"诉辩对立"误报成证据矛盾）
    #    法院认定不参与比对（留给 S4 审查）；标了 state:true 的状态类属性（抚养人、合同状态等）
    #    在不同日期取值不同，按"状态变化"提示，不算矛盾
    groups = defaultdict(list)
    for f in facts:
        if kind(f) in ("法院认定", "推测"):
            continue
        if f.get("object") not in NA and f.get("attribute") not in NA and f.get("value") not in NA:
            groups[(norm_text(f["object"]), norm_text(f["attribute"]))].append(f)
    for (obj, attr), fs in groups.items():
        vals = defaultdict(list)
        for f in fs:
            v = norm_text(f["value"])
            vals[syn.get(v, v)].append(f)
        if len(vals) < 2:
            continue
        kinds = {kind(f) for f in fs}
        dates = [f["_date"] for f in fs]
        if all(f.get("speaker") not in NA for f in fs):
            # 全是带陈述人的言词证据：同一人前后变化交给"陈述漂移/同步改口"；这里只比各人最后一次说法
            last = {}
            for f in sorted(fs, key=lambda x: (float(x.get("version") or 0), x["_date"])):
                last[f["speaker"]] = f
            if len({syn.get(norm_text(f["value"]), norm_text(f["value"])) for f in last.values()}) > 1:
                issues.append({"type": "不同陈述人最终说法不一", "level": "中",
                               "rule": f"{fs[0]['object']}/{fs[0]['attribute']}",
                               "detail": "; ".join(f"{f['speaker']}:{f['id']}={f['value']}" for f in last.values()),
                               "facts": [f["id"] for f in last.values()]})
            continue
        if any(f.get("state") for f in fs) and all(dates) and len(set(dates)) == len(fs):
            typ, level = "可能是状态变化（不同时间的不同取值）", "提示"
        elif len({syn.get(norm_text(f["value"]), norm_text(f["value"])) for f in fs if kind(f) == "客观记录"}) > 1:
            typ, level = "证据矛盾（客观记录之间）", "高"
        elif "客观记录" in kinds:
            typ, level = "陈述与客观记录不符", "中"
        else:
            typ, level = "诉辩对立（仅当事人陈述不同，非证据矛盾）", "提示"
        item = {
            "type": typ, "level": level,
            "rule": f"{fs[0]['object']}/{fs[0]['attribute']}",
            "detail": "; ".join(f"{f['id']}[{f.get('source')}|{kind(f)}]={f['value']}"
                                for v in vals.values() for f in v),
        }
        if level in ("高", "中"):
            item["facts"] = [f["id"] for f in fs]   # 只有真矛盾才会传给 check_elements 标 B 类
        issues.append(item)

    # 2. 时间顺序
    for c in cons.get("order", []):
        a, b = by_id.get(c["before"]), by_id.get(c["after"])
        if not a or not b:
            issues.append({"type": "约束引用缺失", "level": "提示", "rule": c.get("reason", ""), "detail": f"{c['before']} / {c['after']} 不在事实表中"})
            continue
        da, db = a["_date"], b["_date"]
        if not da or not db:
            issues.append({"type": "日期缺失需人工核对", "level": "提示", "rule": c.get("reason", ""), "detail": f"{a['id']}={da or '未载明'}, {b['id']}={db or '未载明'}"})
            continue
        n = min(len(da), len(db))  # 只比较两者共有的精度
        if da[:n] > db[:n]:
            issues.append({"type": "时间顺序异常", "level": "高", "rule": c.get("reason", ""), "detail": f"{a['id']}={da} 晚于 {b['id']}={db}", "facts": [a["id"], b["id"]]})
        elif da[:n] == db[:n] and len(da) != len(db):
            issues.append({"type": "日期精度不同需人工核对", "level": "提示", "rule": c.get("reason", ""), "detail": f"{a['id']}={da}, {b['id']}={db}"})

    # 3. 期限推算：起算日 + N 天/月，与另一事实日期比较（如质保期是否届满、付款是否逾期）
    for c in cons.get("deadlines", []):
        a, b = by_id.get(c["start"]), by_id.get(c["compare"])
        if not a or not b or len(a["_date"]) != 10 or len(b["_date"]) != 10:
            issues.append({"type": "期限推算缺日期需人工核对", "level": "提示", "rule": c.get("reason", ""), "detail": f"{c['start']} / {c['compare']}"})
            continue
        import datetime as _dt
        d0 = _dt.date.fromisoformat(a["_date"])
        m = int(c.get("add_months", 0))
        y, mo = d0.year + (d0.month - 1 + m) // 12, (d0.month - 1 + m) % 12 + 1
        day = min(d0.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1])
        due = _dt.date(y, mo, day) + _dt.timedelta(days=int(c.get("add_days", 0)))
        d1 = _dt.date.fromisoformat(b["_date"])
        reached = d1 >= due
        expect = c.get("expect", "reached")  # 对方主张"已届满/已逾期"时填 reached
        ok = reached if expect == "reached" else not reached
        issues.append({"type": "期限推算" + ("与主张一致" if ok else "与主张不符"), "level": "提示" if ok else "高",
                       "rule": c.get("reason", ""),
                       "detail": f"{a['id']} {a['_date']} 起算 +{m}月+{c.get('add_days',0)}日 = {due}；{b['id']} 为 {d1}，{'已' if reached else '未'}届满",
                       **({} if ok else {"facts": [a["id"], b["id"]]})})

    # 4. 金额加总
    for c in cons.get("sums", []):
        t = by_id.get(c["total"])
        parts = [by_id.get(p) for p in c["parts"]]
        if not t or None in parts:
            issues.append({"type": "约束引用缺失", "level": "提示", "rule": c.get("reason", ""), "detail": c["total"]})
            continue
        if t["_amount"] is None or any(p["_amount"] is None for p in parts):
            issues.append({"type": "金额缺失需人工核对", "level": "提示", "rule": c.get("reason", ""), "detail": c["total"]})
            continue
        s = sum(p["_amount"] for p in parts)
        if abs(s - t["_amount"]) > max(0.01, abs(t["_amount"]) * 1e-6):
            issues.append({"type": "金额不符", "level": "高", "rule": c.get("reason", ""),
                           "detail": f"{t['id']} 总额 {t['_amount']:,.2f} ≠ 分项合计 {s:,.2f}（差 {t['_amount']-s:,.2f}）",
                           "facts": [t["id"]] + c["parts"]})

    return issues


import datetime as _dt

def to_date(s):
    try:
        return _dt.date.fromisoformat(s) if s and len(s) == 10 else None
    except ValueError:
        return None

def to_dt(f):
    d = to_date(f.get("_date"))
    if not d:
        return None
    t = str(f.get("time") or "").strip()
    m = re.match(r"^(\d{1,2})[:：](\d{2})", t)
    if not m:
        return None
    return _dt.datetime(d.year, d.month, d.day, int(m.group(1)), int(m.group(2)))

def ngrams(t, n=4):
    t = re.sub(r"[\s，。、；：“”‘’！？（）《》,.;:!?()\"']", "", str(t))
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}

def check_more(facts, cons, syn, texts):
    """书中方法转成的确定性规则：陈述漂移、同步改口、事后补强、存续期、时间窗口、金额仅言词、文本雷同。"""
    by_id = {f["id"]: f for f in facts}
    issues = []
    val = lambda f: syn.get(norm_text(f.get("value")), norm_text(f.get("value")))

    # 5. 陈述漂移：同一陈述人对同一事项，前后版本取值不同
    seq = defaultdict(list)
    for f in facts:
        if f.get("speaker") not in NA and f.get("object") not in NA and f.get("attribute") not in NA \
                and f.get("value") not in NA and not f.get("state"):
            seq[(f["speaker"], norm_text(f["object"]), norm_text(f["attribute"]))].append(f)
    changes = []   # (speaker, key, old, new, date_of_new, fact_old, fact_new)
    for (sp, o, a), fs in seq.items():
        fs.sort(key=lambda x: (float(x.get("version") or 0), norm_date(x.get("stated_on") or x.get("date"))))
        for x, y in zip(fs, fs[1:]):
            if val(x) != val(y):
                when = norm_date(y.get("stated_on") or y.get("formed_date") or y.get("date"))
                changes.append((sp, (o, a), val(x), val(y), when, x, y))
                issues.append({"type": "陈述漂移（同一人前后说法不同）", "level": "中",
                               "rule": f"{sp}：{x['object']}/{x['attribute']}",
                               "detail": f"{x['id']}[第{x.get('version','?')}次 {norm_date(x.get('stated_on')) or '陈述日未载明'}]={x['value']} → {y['id']}[第{y.get('version','?')}次 {norm_date(y.get('stated_on')) or '陈述日未载明'}]={y['value']}",
                               "facts": [x["id"], y["id"]]})

    # 6. 同步改口：不同陈述人对同一事项，从同一旧值改成同一新值，且改口时间相近
    win = int(cons.get("sync_days", 60))
    for i, c1 in enumerate(changes):
        for c2 in changes[i + 1:]:
            if c1[0] != c2[0] and c1[1] == c2[1] and c1[2] == c2[2] and c1[3] == c2[3]:
                d1, d2 = to_date(c1[4]), to_date(c2[4])
                near = d1 and d2 and abs((d1 - d2).days) <= win
                issues.append({"type": "同步改口（多人一起改成同一说法）", "level": "高" if near else "中",
                               "rule": f"{c1[5]['object']}/{c1[5]['attribute']}",
                               "detail": f"{c1[0]} 与 {c2[0]} 均由「{c1[5]['value']}」改为「{c1[6]['value']}」（改口日期 {c1[4] or '未载明'} / {c2[4] or '未载明'}）",
                               "facts": [c1[5]["id"], c1[6]["id"], c2[5]["id"], c2[6]["id"]]})

    # 7. 事后补强：①实际形成日期晚于落款（补写、重新打印、倒签）；②按性质应当场形成的证据却明显晚形成
    late = int(cons.get("late_days", 30))
    filing = to_date(norm_date(cons.get("filing_date")))
    for f in facts:
        fd = to_date(norm_date(f.get("formed_date")))
        if not fd:
            continue
        sd = to_date(norm_date(f.get("stated_on")))
        ed = to_date(f["_date"])
        after_filing = bool(filing and fd > filing)
        if sd and (fd - sd).days > late:
            issues.append({"type": "事后补强（实际形成晚于落款日期）", "level": "高" if after_filing else "中", "rule": f["id"],
                           "detail": f"{f['id']} 落款 {sd}，实际形成 {fd}（晚 {(fd - sd).days} 天{'，且在起诉之后' if after_filing else ''}）", "facts": [f["id"]]})
        elif f.get("contemporaneous") and ed and (fd - ed).days > late:
            issues.append({"type": "事后补强（应当场形成的证据明显晚形成）", "level": "高" if after_filing else "中", "rule": f["id"],
                           "detail": f"{f['id']} 证明 {ed} 的事项，按性质应当场形成，实际形成于 {fd}", "facts": [f["id"]]})

    # 8. 存续期冲突：事件发生时，涉及的地点/公司/物品尚不存在或已不存在
    ents = {norm_text(e["name"]): e for e in cons.get("entities", [])}
    for f in facts:
        e = ents.get(norm_text(f.get("entity")))
        if not e:
            continue
        d = to_date(f["_date"])
        st, en = to_date(norm_date(e.get("start"))), to_date(norm_date(e.get("end")))
        if not d:
            issues.append({"type": "存续期核验缺日期", "level": "提示", "rule": f["id"], "detail": f"{f['id']} 涉及 {e['name']}，但事件日期未精确到日"})
        elif (st and d < st) or (en and d > en):
            issues.append({"type": "存续期冲突（事发时该实体不存在）", "level": "高", "rule": f"{f['id']} / {e['name']}",
                           "detail": f"{f['id']} 事件日期 {d}；{e['name']} 存续 {st or '?'} 至 {en or '至今'}（来源：{e.get('source','未注明')}）",
                           "facts": [f["id"]]})

    # 9. 时间窗口：两个事件之间的实际间隔，小于完成中间行为所需的最短时间
    for w in cons.get("windows", []):
        a, b = by_id.get(w["from"]), by_id.get(w["to"])
        ta, tb = (to_dt(a), to_dt(b)) if a and b else (None, None)
        if not ta or not tb:
            issues.append({"type": "时间窗口缺时刻需人工核对", "level": "提示", "rule": w.get("reason", ""), "detail": f"{w['from']} / {w['to']} 需要日期和 time 字段"})
            continue
        gap = (tb - ta).total_seconds() / 60
        if gap < float(w["min_minutes"]):
            issues.append({"type": "时间窗口不可行", "level": "高", "rule": w.get("reason", ""),
                           "detail": f"{a['id']} {ta:%Y-%m-%d %H:%M} → {b['id']} {tb:%Y-%m-%d %H:%M}，间隔 {gap:.0f} 分钟，至少需要 {w['min_minutes']} 分钟",
                           "facts": [a["id"], b["id"]]})

    # 10. 金额仅言词支撑：涉及金额的事项，没有任何客观记录佐证
    objs_with_record = {norm_text(f.get("object")) for f in facts
                        if kind(f) == "客观记录" and f["_amount"] is not None and not f.get("disputed")}
    flagged = set()
    for f in facts:
        o = norm_text(f.get("object"))
        if f["_amount"] is not None and kind(f) == "当事人陈述" and o and o not in objs_with_record and o not in flagged:
            flagged.add(o)
            issues.append({"type": "金额仅言词支撑（无书证/流水）", "level": "中", "rule": f.get("object", ""),
                           "detail": f"{f['id']} 主张 {f.get('amount')}，事实表中没有该事项的客观记录"})

    # 11. 文本雷同：不同陈述人的陈述文本高度相似，可能出自同一模板
    thr = float(cons.get("similarity", 0.35))
    for i, x in enumerate(texts):
        for y in texts[i + 1:]:
            if x.get("speaker") == y.get("speaker"):
                continue
            gx, gy = ngrams(x["text"]), ngrams(y["text"])
            if min(len(gx), len(gy)) < 10:
                continue
            sim = len(gx & gy) / min(len(gx), len(gy))
            if sim >= thr:
                issues.append({"type": "文本雷同（不同人陈述高度相似）", "level": "高" if sim >= 0.6 else "中",
                               "rule": f"{x['id']} vs {y['id']}",
                               "detail": f"{x.get('speaker')} 与 {y.get('speaker')} 的陈述 4 字片段重合度 {sim:.0%}（阈值 {thr:.0%}）"})

    # 12. 陈述与已被推翻的推测一致：陈述内容跟着一个后来被证伪的推测走，而不是跟着客观记录走
    for h in facts:
        if kind(h) != "推测" or not h.get("overturned_by"):
            continue
        refs = [r for r in h["overturned_by"] if r in by_id]
        if not refs:
            issues.append({"type": "推测的推翻依据缺失", "level": "提示", "rule": h["id"], "detail": f"overturned_by 引用的事实不在事实表中"})
            continue
        for f in facts:
            if f is h or kind(f) != "当事人陈述":
                continue
            if norm_text(f.get("object")) == norm_text(h.get("object")) and norm_text(f.get("attribute")) == norm_text(h.get("attribute")) \
                    and val(f) == val(h):
                issues.append({"type": "陈述与已被推翻的推测一致（可能来源于推测而非亲历）", "level": "高",
                               "rule": f"{h['object']}/{h['attribute']}",
                               "detail": f"{f['id']}（{f.get('speaker') or f.get('party','')}）称「{f['value']}」，与推测 {h['id']} 相同；该推测已被 {', '.join(refs)} 推翻",
                               "facts": [f["id"], h["id"]] + refs})

    # 13. 文风比对：署名为某人但有疑问的材料，与其本人平时文字的风格差异
    known = defaultdict(list)
    for t in texts:
        if t.get("role") == "known":
            known[t.get("speaker")].append(t)
    for t in texts:
        if t.get("role") != "disputed" or not known.get(t.get("speaker")):
            continue
        ks = known[t["speaker"]]
        prof = lambda x: style_profile(x["text"])
        kp = [prof(k) for k in ks]
        dp = prof(t)
        sims = [cosine(dp["bigrams"], k["bigrams"]) for k in kp]
        base = [cosine(a["bigrams"], b["bigrams"]) for i, a in enumerate(kp) for b in kp[i + 1:]]
        notes = []
        for key, label in (("sent_len", "平均句长"), ("formal", "书面语词频"), ("punct", "标点密度")):
            kv = sum(k[key] for k in kp) / len(kp)
            if (kv and (dp[key] > kv * 1.8 or dp[key] < kv / 1.8)) or (not kv and dp[key] >= 1.0):
                notes.append(f"{label} {dp[key]:.2f}，本人平时约 {kv:.2f}")
        low = base and max(sims) < min(base) * 0.8
        if notes or low:
            issues.append({"type": "文风与本人平时文字不符（线索，正式结论需文书鉴定）", "level": "中",
                           "rule": f"{t['id']}（署名 {t['speaker']}）",
                           "detail": "；".join(notes + ([f"用字相似度 {max(sims):.2f}，低于本人各样本之间的 {min(base):.2f}"] if low else []))
                                     + "。另请人工核对：错别字、的地得用法、方言词、专业术语是否超出本人水平"})
    return issues

FORMAL = ["鉴于", "予以", "系", "之", "其", "兹", "特此", "上述", "该", "据此", "遂", "均", "业已", "须"]

def style_profile(t):
    t = str(t)
    sents = [x for x in re.split(r"[。！？!?；;]", t) if x.strip()]
    chars = re.sub(r"\s", "", t)
    n = max(1, len(chars))
    bg = defaultdict(int)
    for i in range(len(chars) - 1):
        bg[chars[i:i + 2]] += 1
    return {"sent_len": len(chars) / max(1, len(sents)),
            "formal": sum(chars.count(w) for w in FORMAL) * 100 / n,
            "punct": len(re.findall(r"[，。、；：！？,.;:!?]", chars)) * 100 / n,
            "bigrams": bg}

def cosine(a, b):
    num = sum(v * b.get(k, 0) for k, v in a.items())
    da = sum(v * v for v in a.values()) ** 0.5
    db = sum(v * v for v in b.values()) ** 0.5
    return num / (da * db) if da and db else 0.0

def write_xlsx(facts, issues, out):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        # 没装 openpyxl 时退回 CSV（Excel 可直接打开），不中断流程
        import csv
        base = out.rsplit(".", 1)[0]
        cols = ["id", "source", "quote", "date", "time", "subject", "object", "attribute", "value", "amount", "currency",
                "party", "nature", "speaker", "version", "stated_on", "formed_date", "contemporaneous", "entity"]
        with open(base + "_事实表.csv", "w", encoding="utf-8-sig", newline="") as fo:
            w = csv.writer(fo); w.writerow(cols)
            for f in facts:
                w.writerow([f.get(k, "") for k in cols])
        with open(base + "_规则检查.csv", "w", encoding="utf-8-sig", newline="") as fo:
            w = csv.writer(fo); w.writerow(["类型", "级别", "对象/规则", "详情"])
            for i in issues:
                w.writerow([i["type"], i.get("level", ""), i["rule"], i["detail"]])
        print("提示：未安装 openpyxl，已输出 CSV。需要 Excel 可运行 pip install openpyxl")
        return base + "_事实表.csv / _规则检查.csv"
    wb = Workbook()
    ws = wb.active
    ws.title = "事实表"
    cols = ["id", "source", "quote", "date", "time", "subject", "object", "attribute", "value", "amount", "currency",
            "party", "nature", "speaker", "version", "stated_on", "formed_date", "contemporaneous", "entity"]
    ws.append(cols)
    for f in facts:
        ws.append([f.get(k, "") for k in cols])
    wt = wb.create_sheet("时间线")
    wt.append(["日期", "id", "主体", "对象", "原文", "出处", "提出方"])
    for f in sorted([f for f in facts if f["_date"]], key=lambda x: x["_date"]):
        wt.append([f["_date"], f["id"], f.get("subject", ""), f.get("object", ""), f.get("quote", ""), f.get("source", ""), f.get("party", "")])
    wi = wb.create_sheet("规则检查")
    wi.append(["类型", "级别", "对象/规则", "详情"])
    for i in issues:
        wi.append([i["type"], i.get("level", ""), i["rule"], i["detail"]])
    for sh in wb.worksheets:
        for c in sh[1]:
            c.font = Font(bold=True)
    wb.save(out)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("facts")
    ap.add_argument("constraints", nargs="?")
    ap.add_argument("--synonyms")
    ap.add_argument("--texts", help="陈述全文 JSON，用于文本雷同比对")
    ap.add_argument("--out", default="案件事实表.xlsx")
    a = ap.parse_args()
    facts = json.load(open(a.facts, encoding="utf-8"))
    cons = json.load(open(a.constraints, encoding="utf-8")) if a.constraints else {}
    syn = load_synonyms(a.synonyms)
    texts = json.load(open(a.texts, encoding="utf-8")) if a.texts else []
    issues = check(facts, cons, syn) + check_more(facts, cons, syn, texts)
    import os
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    saved = write_xlsx(facts, issues, a.out)
    json.dump(issues, open(a.out.rsplit(".", 1)[0] + "_issues.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"事实 {len(facts)} 条；规则检查 {len(issues)} 项；已保存 {saved}")
    for i in issues:
        print(f"- [{i.get('level','')}][{i['type']}] {i['rule']}：{i['detail']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
