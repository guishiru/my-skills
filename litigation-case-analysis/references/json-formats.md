# 输入文件格式（脚本用）

所有文件 UTF-8 编码，放在本案工作目录（如 `案件名/work/`）。

## facts.json：事实表

数组，每条一个事实。同一事实在多份材料中出现，分别建行，不要合并。

| 字段 | 必填 | 说明 |
|---|---|---|
| id | 是 | F001 起顺序编号 |
| source | 是 | 材料编号 + 页码；二手材料写"材料名§段落"。找不到出处的不进表 |
| quote | 是 | 原文摘录，不改写 |
| date | | 事件日期 YYYY-MM-DD；原文只到月就写到月，不推断 |
| time | | 时刻 HH:MM，算时间窗口时填 |
| subject | | 谁做了什么 / 谁出具 |
| object | | 事实指向的具体对象（某航班、某笔款、某房产） |
| attribute | | 对象的哪个方面（机型、金额、地点、日期） |
| value | | 该属性的值；原文没有写"未载明" |
| amount / currency | | 涉及金额时填数字和币种 |
| party | | 原告 / 被告 / 第三方 / 法院认定 / 办案机关 |
| nature | 是 | 只能填：客观记录 / 当事人陈述 / 证人证言 / 法院认定 / 推测 |
| speaker / version | 言词证据必填 | 陈述人；同一人第几次陈述 |
| stated_on | | 陈述日期或书证落款日期 |
| formed_date | | 只在实际形成日期与落款不同（补写、重新打印、元数据更晚）时填 |
| contemporaneous | | 收条、交接单等按性质应当场形成的填 true |
| entity | | 事件涉及的地点 / 公司 / 物品名称，用于存续期核验 |
| state | | 会随时间合法变化的属性（抚养人、合同状态）填 true |
| disputed | | 书证真伪有争议（如签名待鉴定的借条）填 true。nature 仍填"客观记录"，但脚本不把它算作金额的客观佐证 |
| overturned_by | | nature 为"推测"且已被推翻时，填推翻它的事实 id 数组 |

示例：

```json
[
 {"id":"F001","source":"D02§事实与理由","quote":"在本市云雾茶楼二楼包间以现金方式向被告出借50万元",
  "date":"2023-05-10","time":"15:00","object":"现金交付","attribute":"地点","value":"云雾茶楼",
  "party":"原告","nature":"当事人陈述","speaker":"王某","version":1,"stated_on":"2024-04-10","entity":"云雾茶楼"},
 {"id":"F010","source":"D10","quote":"成立日期：2023年6月20日","object":"云雾茶楼","attribute":"成立日期",
  "value":"2023-06-20","nature":"客观记录"},
 {"id":"F020","source":"初查勘验","quote":"推测凶手翻墙逃离","object":"逃离路线","attribute":"方式",
  "value":"翻墙","nature":"推测","party":"办案机关","overturned_by":["F021"]}
]
```

## constraints.json：规则约束

由分析者根据案情列出，交律师确认后再运行。各项都可省略。

```json
{
  "order": [{"before":"F005","after":"F004","reason":"报批申请应早于批复"}],
  "sums": [{"total":"F020","parts":["F021","F022"],"reason":"损失总额应等于各分项之和"}],
  "deadlines": [{"start":"F012","add_months":12,"add_days":15,"compare":"F030","expect":"reached",
                 "reason":"原告主张起诉时质保金已到期"}],
  "entities": [{"name":"云雾茶楼","start":"2023-06-20","end":"","source":"工商登记"}],
  "windows": [{"from":"F009","to":"F001","min_minutes":95,"reason":"高铁站到茶楼驾车约95分钟"}],
  "filing_date": "2024-04-10",
  "sync_days": 60,
  "late_days": 30,
  "similarity": 0.35
}
```

- `order`、`deadlines`、`windows` 引用的都必须是**带日期的事实**。比较对象是起诉日、开庭日这类程序节点时，先在 facts.json 里为它单独建一条事实（如 F032 起诉日 2024-04-10），再引用它的 id。`windows` 两端还需要 `time` 字段。
- `deadlines.expect`：对方主张"已到期/已逾期"填 `reached`，主张"未到期"填 `not_reached`。
- `sync_days`：两人改口相隔多少天以内算"同步"。`late_days`：形成日期晚于落款多少天算事后补强。`similarity`：文本雷同阈值。

## synonyms.json：同义写法（可选）

```json
{"A320": ["空客320", "空客A320"]}
```

## texts.json：陈述全文（可选）

用于文本雷同和文风比对。

```json
[
 {"id":"W1","speaker":"张某","text":"证言全文……"},
 {"id":"K1","speaker":"马某","role":"known","text":"本人平时所写（日记、聊天记录）……"},
 {"id":"D1","speaker":"马某","role":"disputed","text":"署名为本人但有疑问的材料……"}
]
```

## elements.json：要件、原审认定、鉴定意见

```json
{
  "elements": [
    {"id":"E1","claim":"返还借款","element":"款项已实际交付","asserted_by":"原告","burden_on":"原告",
     "basis":"主张法律关系存在的一方对基本事实举证（条号待核验）",
     "evidence":["F001","F003"],"status":"证明不足","gap":"无取款记录","negative":false}
  ],
  "findings": [
    {"id":"J1","text":"借条签名系被告所写","source":"一审判决§本院认为(一)",
     "supported_by":["F004"],"reasoning":"采信鉴定A1","element":"E2",
     "burden_assigned_to":"","finding_type":"事实认定","about":"","negative":false,
     "adopted_appraisal":"A1","adoption_reason":"结论明确"}
  ],
  "appraisals": [
    {"id":"A1","subject":"借条签名是否为被告书写","by":"某司法鉴定所","date":"2024-02-01","commissioned_by":"原告单方委托",
     "observations":[{"text":"签名特征多数相同","facts":["F006"]}],
     "premises":[{"text":"比对样本系被告书写","source_type":"送检材料","facts":[],"verified":false}],
     "reasoning":"……","specific":true,"expected_missing":[],
     "basis_certainty":"倾向","conclusion":"是被告本人书写","conclusion_certainty":"确定",
     "terms":[{"term":"……","standard":"所引标准定义","match":true}],
     "expert_own_standards":[{"text":"鉴定人公开的标准或说法","source":"出处","consistent":false}],
     "checklist":{"鉴定人资质在有效期内":"未知","接触原始检材":false,"比对样本来源经质证":false,"鉴定时间未明显滞后":true}}
  ]
}
```

- `negative`：要件或原审认定是消极事实（未清偿、未批准）时填 true，脚本不会机械判为"无证据"。
- 同一待证事项的多份鉴定，`subject` 要写得完全一致，脚本才能识别为冲突。
- `status` 只能填：已证明 / 证明不足 / 无证据 / 有相反证据。
- `finding_type`：事实认定 / 裁判主文（判项不做事实审查）。
- `about`：原审驳回我方抗辩的认定填"我方抗辩"。
- `burden_assigned_to`：原审没写明不利后果由谁承担的留空，不要推断。
- certainty 取值：确定 > 倾向 > 可能 > 无法判断。checklist 无法核实的填"未知"。

## 输出文件

- `check_facts.py --out work/事实表.xlsx` 会同时生成 `work/事实表_issues.json`（文件名 = out 去掉扩展名 + `_issues.json`）。第二个脚本的 `--contradictions` 就填这个文件。
- 没装 openpyxl 时，Excel 换成 `事实表_事实表.csv` 和 `事实表_规则检查.csv`，issues.json 照常生成。
