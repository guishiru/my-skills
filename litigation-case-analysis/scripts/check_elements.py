#!/usr/bin/env python3
"""S3/S4 结构校验：要件—证据对照表 + 原审认定事实表 + 鉴定意见四段拆解，自动标出可确定的硬伤。

用法:
  python check_elements.py facts.json elements.json [--contradictions xxx_issues.json] [--out 要件检查.md]

elements.json:
{
  "elements": [
    {"id":"E1","claim":"支付包机款","element":"深圳企业违约","asserted_by":"福建企业",
     "burden_on":"福建企业","basis":"主张方对产生法律关系的基本事实举证（条号待核验）",
     "evidence":["F003","F007"],"status":"证明不足","gap":"..."}
  ],
  "findings": [      // 仅 P2/P3：原审认定的事实
    {"id":"J1","text":"福建企业有权单方变更航司机型","source":"一审判决第6页",
     "supported_by":["F012"],"reasoning":"合同约定以民航总局批复为准",
     "burden_assigned_to":"深圳企业","element":"E2",
     "finding_type":"事实认定",   // 或 "裁判主文"（判项不做事实审查）
     "about":"",                 // 原审驳回我方抗辩的认定填 "我方抗辩"
     "negative":false,           // 消极事实（未清偿/未批准）设 true
     "adopted_appraisal":"A1", "adoption_reason":""}   // 原审采信了哪份鉴定、理由
  ],
  "appraisals": [    // 鉴定意见四段拆解：检材所见 / 送检前提 / 推理 / 结论
    {"id":"A1","subject":"借条签名是否为被告书写","by":"某司法鉴定所","date":"2024-02-01",
     "commissioned_by":"原告单方委托",
     "observations":[{"text":"检材签名笔画特征…","facts":["F030"]}],
     "premises":[{"text":"比对样本系被告书写","source_type":"送检材料","facts":["F031"],"verified":false}],
     "reasoning":"…","specific":true,"expected_missing":["…结论成立时应有而卷内未见的痕迹"],
     "basis_certainty":"倾向","conclusion":"签名是被告所写","conclusion_certainty":"确定",
     "terms":[{"term":"…","standard":"所引标准中的定义","match":true}],
     "expert_own_standards":[{"text":"鉴定人公开称：排除结论 100% 准确","source":"某期刊/访谈","consistent":false}],
     "checklist":{"鉴定人资质在有效期内":true,"接触原始检材":false,"比对样本来源经质证":false,"鉴定时间未明显滞后":true}}
  ]
}
certainty 取值：确定 > 倾向 > 可能 > 无法判断
"""
import argparse, json, re, sys

STATUS = {"已证明", "证明不足", "无证据", "有相反证据"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("facts")
    ap.add_argument("elements")
    ap.add_argument("--contradictions", help="check_facts 输出的 *_issues.json，用于标 B 类")
    ap.add_argument("--out", default="要件检查.md")
    a = ap.parse_args()
    facts = {f["id"]: f for f in json.load(open(a.facts, encoding="utf-8"))}
    data = json.load(open(a.elements, encoding="utf-8"))
    els = {e["id"]: e for e in data.get("elements", [])}
    contra = set()
    if a.contradictions:
        for i in json.load(open(a.contradictions, encoding="utf-8")):
            contra.update(i.get("facts", []))

    errs, rows = [], []
    for e in els.values():
        for k in ("asserted_by", "burden_on", "status"):
            if not e.get(k):
                errs.append(f"{e['id']} 缺少字段 {k}")
        if e.get("status") and e["status"] not in STATUS:
            errs.append(f"{e['id']} status 只能是 {sorted(STATUS)}，收到 {e['status']}")
        missing = [x for x in e.get("evidence", []) if x not in facts]
        if missing:
            errs.append(f"{e['id']} 引用了不存在的事实 {missing}")
        if e.get("status") == "已证明" and not e.get("evidence"):
            errs.append(f"{e['id']} 标为已证明但没有任何证据")
        if e.get("asserted_by") and e.get("burden_on") and e["asserted_by"] != e["burden_on"] and "倒置" not in e.get("basis", "") and "另有规定" not in e.get("basis", ""):
            errs.append(f"{e['id']} 举证方≠主张方，但 basis 未写明特殊规则依据，请核对")

    _subj = {}
    for ap_ in data.get("appraisals", []):
        _subj.setdefault(re.sub(r"\s", "", ap_.get("subject", "")), []).append(ap_)
    conflict_ids = {x["id"] for lst in _subj.values() if len({re.sub(r"\s", "", y.get("conclusion", "")) for y in lst}) > 1 for x in lst}

    # 原审认定事实 → 自动分类（A/B/D 可由程序确定，C 需人工）
    def same_party(x, y):
        clean = lambda t: re.sub(r"[（(].*?[)）]|\s", "", str(t or ""))
        return clean(x) == clean(y)
    for j in data.get("findings", []):
        if j.get("finding_type") == "裁判主文":
            rows.append((j["id"], j.get("text", ""), j.get("source", ""), "裁判主文，不做事实审查；如有异议在 S5 列为上诉/再审请求"))
            continue
        sup = j.get("supported_by", [])
        bad_ref = [x for x in sup if x not in facts]
        tags = []
        el = els.get(j.get("element"))
        if j.get("about") == "我方抗辩":
            tags.append("原审驳回我方抗辩：核对卷内我方证据是否被忽略、是否误述我方抗辩内容")
        elif not sup or len(bad_ref) == len(sup):
            if j.get("negative") or (el and el.get("negative")):
                tags.append("消极事实（如'未清偿''未批准'）：不能直接判无证据，核对举证责任与对方反证")
            else:
                tags.append("A 无证据支撑")
        if set(sup) & contra:
            tags.append(f"B 证据矛盾（{', '.join(sorted(set(sup) & contra))}）")
        if el and el.get("status") in ("无证据", "证明不足", "有相反证据"):
            tags.append(f"原审采信了要件表判为「{el['status']}」的要件 {el['id']}")
        if el and el.get("status") in ("无证据", "证明不足", "有相反证据"):
            if not j.get("burden_assigned_to"):
                tags.append("原审未写明不利后果由谁承担，D 类需人工判断")
            elif not same_party(j["burden_assigned_to"], el.get("burden_on")):
                tags.append(f"D 举证责任错配（原审由 {j['burden_assigned_to']} 承担，要件表为 {el['burden_on']}）")
        if not j.get("reasoning"):
            tags.append("C? 原审未写推理依据，需人工审查经验法则")
        if j.get("adopted_appraisal") and j["adopted_appraisal"] in conflict_ids:
            tags.append(f"B 所采鉴定 {j['adopted_appraisal']} 与同一事项的其他鉴定结论冲突")
        rows.append((j["id"], j.get("text", ""), j.get("source", ""), "；".join(tags) or "程序未发现问题（C 类仍需人工审）"))
        if bad_ref:
            errs.append(f"{j['id']} 引用了不存在的事实 {bad_ref}")


    # 鉴定意见四段拆解校验
    LV = {"确定": 3, "倾向": 2, "可能": 1, "无法判断": 0}
    apr = data.get("appraisals", [])
    arows = []
    for ap_ in apr:
        tags = []
        cc, bc = ap_.get("conclusion_certainty"), ap_.get("basis_certainty")
        if cc in LV and bc in LV and LV[cc] > LV[bc]:
            tags.append(f"结论超出依据（依据仅「{bc}」，结论写成「{cc}」）")
        for pm in ap_.get("premises", []):
            st = pm.get("source_type", "")
            fx = pm.get("facts", [])
            if st in ("送检材料", "委托方陈述", "当事人陈述"):
                if not fx or all(x not in facts for x in fx):
                    tags.append(f"送检前提「{pm.get('text','')}」在卷内无证据（A）")
                elif set(fx) & contra:
                    tags.append(f"送检前提「{pm.get('text','')}」所依事实被规则检查标出问题（矛盾或事后补强，B）")
                elif pm.get("verified") is False:
                    tags.append(f"送检前提「{pm.get('text','')}」未经质证核实")
        if ap_.get("specific") is False:
            tags.append("推理依赖非特异性征象，未排除其他解释（C）")
        if ap_.get("expected_missing"):
            tags.append("应有而未见：" + "；".join(ap_["expected_missing"]))
        for t in ap_.get("terms", []):
            if t.get("match") is False:
                tags.append(f"术语「{t.get('term')}」与标准定义不符")
        for k, v in (ap_.get("checklist") or {}).items():
            if v is False:
                tags.append(f"质证点：{k} —— 否")
            elif v in (None, "未知", ""):
                tags.append(f"质证点待核实：{k}")
        for es in ap_.get("expert_own_standards", []):
            if es.get("consistent") is False:
                tags.append(f"与鉴定人自己公开的标准或说法不一致：{es.get('text','')}（出处：{es.get('source','未注明')}）")
        if "单方" in str(ap_.get("commissioned_by", "")):
            tags.append("单方委托鉴定，可申请重新鉴定")
        arows.append((ap_["id"], ap_.get("subject", ""), ap_.get("conclusion", ""), "；".join(tags) or "未发现结构性问题（仍需专家意见）"))
    # 同一待证事项多份鉴定结论不一致，检查原审采信理由
    by_subj = {}
    for ap_ in apr:
        by_subj.setdefault(re.sub(r"\s", "", ap_.get("subject", "")), []).append(ap_)
    adopted = {j.get("adopted_appraisal"): j for j in data.get("findings", []) if j.get("adopted_appraisal")}
    for subj, lst in by_subj.items():
        if len({re.sub(r"\s", "", x.get("conclusion", "")) for x in lst}) > 1:
            ids = [x["id"] for x in lst]
            used = [i for i in ids if i in adopted]
            note = "原审未写明采信哪一份" if not used else ("；".join(f"原审采信 {i}" + ("，但未说明理由" if not adopted[i].get("adoption_reason") else f"，理由：{adopted[i]['adoption_reason']}") for i in used))
            arows.append(("/".join(ids), subj, "多份鉴定结论冲突", note))

    import os
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fo:
        fo.write("# 要件与原审认定 结构检查\n\n")
        fo.write("## 结构错误\n\n" + ("\n".join(f"- {x}" for x in errs) if errs else "- 无") + "\n\n")
        fo.write("## 原审认定事实 自动分类\n\n| id | 认定内容 | 出处 | 程序判断 |\n|---|---|---|---|\n")
        for r in rows:
            fo.write("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |\n")
        if arows:
            fo.write("\n## 鉴定意见拆解检查\n\n| id | 待证事项 | 结论 | 程序判断 |\n|---|---|---|---|\n")
            for r in arows:
                fo.write("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |\n")
    print(open(a.out, encoding="utf-8").read())
    return 1 if errs else 0

if __name__ == "__main__":
    sys.exit(main())
