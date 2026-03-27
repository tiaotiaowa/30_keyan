# GeoKD-SR 实验实现与评测体系统一设计（基于 V5.2 细化）

> 约束：只做设计，不写代码。
>
> 本设计从 `D:/30_keyan/docs/GeoKD-SR-实验设计方案-V5.2.md` 出发，对训练实现与评测体系进行“可执行口径化”细化，目标是：公平、可复现、可对比、可诊断。
>
> 本设计已采纳的用户决策：
> - 主评测基准：使用 `final_1_final.jsonl` 导出的 **final test split** 作为主评测集（而非单独维护 GeoSR-Bench）。
> - 模型生成输出格式：统一为 **强制 JSON 块**（评测只解析 JSON 块）。
> - 产物目录：遵循 V5.2 的 `checkpoints/{method}/{seed}/` 结构，但在其下引入 `run_id` 防覆盖：`checkpoints/{method}/{seed}/{run_id}/` 与 `results/{method}/{seed}/{run_id}/`。

---

## 0. 设计目标与范围

### 0.1 Goals
1. **训练实现可复现**：同一实验配置重复 5 seeds 得到可复现统计分布。
2. **评测口径可对比**：不同 exp 只允许在“方法变量”上不同；评测与生成配置完全一致。
3. **指标可诊断**：除总体分数外必须支持按 `spatial_relation_type/difficulty/topology_subtype` 分层，支持错误类型归因。
4. **产物可聚合**：单次 run 产物具备机器可读 JSON（metrics）与逐样本 JSONL（predictions），可自动生成 leaderboard 与统计显著性报告。

### 0.2 Non-goals
- 本阶段不实现任何脚本，不重构代码，仅给出“文件级改造清单/接口/Schema/CLI/验证方法”。

---

## 1. V5.2 的公平性原则落地（I/O Contract + Fairness Gate）

V5.2 在 4.7 节明确：**统一数据 + 字段可选 + 监督可控(mask) + 统计可比**（见 V5.2:763-806）。

### 1.1 统一数据口径（Single Source of Truth）

#### 1.1.1 原始数据唯一真源
- 原始数据文件：`GeoKD-SR/data/final/final_1_final.jsonl`
- 要求：在任何训练/评测 run 的元数据中记录该文件的 `sha256`。

#### 1.1.2 官方切分导出（final->train/dev/test）
- 从原始 final 文件导出官方切分：
  - `GeoKD-SR/data/official_splits/<dataset_id>/train.jsonl`
  - `.../dev.jsonl`
  - `.../test.jsonl`（主评测基准）
- 切分策略参考：V5.2 “full_data -> train/dev” 的公平管理器思想（V5.2:892-907），并补齐 test。

#### 1.1.3 dataset_manifest.json（必须）
每次导出 splits 生成一个不可变的 manifest，用于所有 run 引用。

建议 schema：
- `dataset_id`: 例如 `geokd_sr_final_1_final_v1`
- `source_file`: `GeoKD-SR/data/final/final_1_final.jsonl`
- `source_sha256`: string
- `schema_version`: `v6.0`（与数据生成规范一致）
- `split`:
  - `method`: string（例如 `stratified_entity_exclusion_v1`）
  - `seed`: int
  - `exported_files`: {train/dev/test 路径}
- `distribution_targets`: 记录关系类型/难度/拓扑子类型目标
- `generated_at`, `generator_commit`

> 设计意图：彻底消除当前 exp01/02 与 exp03-09 在默认评测文件上分裂（test.jsonl vs benchmark.json）。

---

## 2. 运行目录与产物协议（Report Protocol）

V5.2 给出 checkpoint 保存路径 `checkpoints/{method}/{seed}/`（V5.2:1317）。本设计在保持该层级的前提下引入 `run_id`，避免覆盖，并为评测/统计聚合提供稳定键。

### 2.1 run_id 定义
`run_id` 推荐组成：
- `{timestamp}_{gitShort}_{method}_{seed}_{dataset_id}`

### 2.2 目录结构
- `checkpoints/{method}/{seed}/{run_id}/`
  - `best/`（可选）
  - `final_model/`
  - `trainer_state.json` 等（由训练框架产生）
- `logs/{method}/{seed}/{run_id}/`
  - `train.log`
  - `eval.log`
- `results/{method}/{seed}/{run_id}/`
  - `run_meta.json`
  - `metrics.json`
  - `predictions.jsonl`
  - `report.md`
  - `artifacts/`（可选：混淆矩阵、分布图等）

### 2.3 run_meta.json（必须：复现最小集合）
建议字段：
- `run_id`, `timestamp`
- `git_commit`, `dirty_repo`
- `method`（对应 exp01-exp09/或 method_id）
- `seed`（V5.2 6.1.1 seeds: [42,123,456,789,1024]，见 V5.2:1133-1159）
- `base_model`, `teacher_model`, `tokenizer`
- `dataset_manifest_path`
- `train_config_resolved`（最终展开配置）
- `eval_config_resolved`（含 generation_config）
- `chat_template_id`, `system_prompt_hash`

---

## 3. 训练实现统一口径（Training Contract）

### 3.1 从 V5.2 的“统一输入 + 选择性监督”细化为可执行约束
V5.2 4.7.2/4.7.4 给出了统一输入格式示例（问题：...\n答案：... 或 请逐步分析...），并强调 mask 控制监督范围（V5.2:776-888）。

本设计将其落实为训练侧硬约束（后续实现必须满足）：

#### 3.1.1 数据读取
- 训练/评测数据必须使用 `json.loads` 读取 JSONL（禁止 `eval`）。

#### 3.1.2 Template/Prompt
- 统一使用同一套“消息构造函数”（概念接口）：
  - input messages：system + user
  - assistant target：依据实验选择性包含 answer / reasoning_chain / JSON块等
- 允许差异：Exp4/Exp9 可在 assistant target 中加入 reasoning_chain（对应 V5.2:790-792）。

#### 3.1.3 labels 与 mask
- 统一构造 labels：system+user 段为 `-100`，只对 assistant 段计算 CE。
- 所有软蒸馏损失（KL/attention/hidden）也必须使用同一 valid_mask：
  - `valid_mask = (labels != -100) & (attention_mask == 1)`

> 对应现状风险：exp03-09 多数未生成 labels，导致 hard_loss 常为 0；且 KL 常对 prompt/pad 计算，破坏公平对比。

#### 3.1.4 方法变量与控制变量清单
基于 V5.2 4.7.4/4.7.6（V5.2:809-940），明确：
- **控制变量（必须一致）**：数据（dataset_manifest）、模板与 system prompt、labels/mask 策略、训练超参（lr/batch/epochs 等）、评测生成参数。
- **方法变量（允许不同）**：
  - Exp1: 仅 CE
  - Exp2: CE + Forward KL
  - Exp3a: CE + KL * uniform relation weight
  - Exp3: CE + KL * learnable relation weight
  - Exp4: reasoning_chain distill
  - Exp5: reverse KL
  - Exp6: self distill
  - Exp7: attention/hidden distill
  - Exp8: progressive schedule（仅改变采样/阶段，不改变数据本体）
  - Exp9: 组件组合（loss_weights见 V5.2:1101-1125）

---

## 4. 评测体系统一口径（Evaluation Contract）

V5.2 第七章给出了较完整的评测 pipeline 结构（V5.2:1554-1594）与错误类型分类（V5.2:1511-1524）。但现状代码中各 exp 的指标实现口径不一致（字符级 vs split 分词、RA 方向兜底差异、SR-F1 词表差异等）。

本设计将评测口径改造为：**结构化 JSON 解析 + 规则判定为主**，文本 BLEU/ROUGE 降级为辅助诊断。

### 4.1 主评测集
- 主评测集：`dataset_manifest.exported_files.test`（final test）。

### 4.2 统一输出格式：强制 JSON 块

#### 4.2.1 JSON schema（最小必需字段）
```json
{
  "relation_type": "directional|topological|metric|composite",
  "final_answer": "一句话核心结论",
  "direction": "东|西|南|北|东北|东南|西北|西南",
  "topology_subtype": "within|contains|adjacent|disjoint|overlap",
  "distance": {"value": 12.3, "unit": "km"}
}
```
- directional：必须有 `direction`
- topological：必须有 `topology_subtype`
- metric：必须有 `distance`
- composite：必须同时有 `direction` 和 `distance`

#### 4.2.2 format_valid_rate
- `format_valid_rate = 可解析 JSON 块样本数 / 总样本数`
- 若 format_valid_rate 低于阈值（建议 0.98）可作为 Gate 告警或失败条件（见 5）。

### 4.3 评分规则（结构化为主）
- directional：方向归一到 8 向（支持同义映射，例如“偏西南”->“西南”）
- topological：映射到 5 类 subtype，输出混淆矩阵
- metric：距离单位归一到 km；采用双阈值通过规则（±10% 或 ±50km 取更大）并同时输出 MAE(km)
- composite：`dir_ok AND metric_ok`

### 4.4 指标体系（对齐 V5.2，同时更可执行）
V5.2 7.2 将 RA 作为主要指标，并提出 RA = 0.4*推理步骤 + 0.3*答案准确 + 0.2*完整性 + 0.1*清晰度（V5.2:1361-1375），并引入 GLM-5 LLM 评估 JSON 输出（V5.2:1429-1495）。

本设计建议形成“二层主指标”：
1) **Primary（确定性，可复现）**：结构化准确率为主（对齐你当前工作目标：稳定对比蒸馏实验）
   - `primary_score = mean(overall_correct)` 或按关系类型加权
2) **Secondary（抽样审计，可选）**：LLM-as-a-judge（GLM-5）用于 RA 的“推理质量/完整性/清晰度”评分（成本较高，不作为唯一主指标）

> 解释：V5.2 的 RA 设计偏“LLM评分”，但对实验对比容易引入评估噪声与成本；因此把它降级为抽样审计更稳。

### 4.5 分层统计（必须）
- by `spatial_relation_type`
- by `difficulty`
- by `topology_subtype`（仅 topological）

### 4.6 错误类型 taxonomy（对齐 V5.2 7.4，并补齐结构化解析错误）
在 V5.2 的错误类型（空间关系错误/距离/方向/拓扑混淆/格式错误等，V5.2:1511-1524）基础上，固化为可统计字段：
- `format_error`（JSON 不可解析/缺字段/类型错误）
- `wrong_relation_type`
- `wrong_direction`
- `wrong_topology`
- `wrong_distance_value`
- `unit_error`
- `reasoning_chain_break`（若启用 reasoning_chain 评测）
- `hallucination`（出现无关实体/关系，按规则或 LLM 审计判定）

---

## 5. Fairness Gate（门禁）设计：训练前与评测前的硬条件

结合 V5.2 的“公平性保证机制”与 V6.0 数据验收思想，本设计定义：

### 5.1 Gate-Data（数据门禁）
- 必须：`dataset_manifest` 存在且 sha256 匹配
- 必须：test 集分布统计落在目标容差内（容差来源可引用 V6.0 的 deviation<0.05）

### 5.2 Gate-Train（训练门禁）
- 必须：labels/mask 策略一致（记录到 run_meta）
- 必须：seed 属于 V5.2 seeds 集
- 必须：训练超参对齐（除非方法变量明确允许改变）

### 5.3 Gate-Eval（评测门禁）
- 必须：generation_config 固定（temperature/top_p/max_new_tokens 等全部记录）
- 必须：format_valid_rate ≥ 阈值（默认 0.98）

---

## 6. 统计分析与 leaderboard（对齐 V5.2 第六章）

V5.2 明确：运行 5 次、报告均值±标准差，并进行统计显著性检验 + 效应量 + Holm-Bonferroni 校正（V5.2:1131-1275）。

### 6.1 聚合输入
- 从 `results/{method}/{seed}/{run_id}/metrics.json` 聚合。

### 6.2 输出
- `leaderboard.csv`：每个 method 的均值、std、分层指标、format_valid_rate
- `stats_report.json/md`：
  - Exp2 vs Exp1、Exp3a vs Exp2、...、Exp9 vs Exp2 等 V5.2 4.7.6 的对比集合（V5.2:928-940）
  - p 值、校正后 p 值、Cohen's d、Cliff's Delta、95%CI

---

## 7. metrics.json 与 predictions.jsonl Schema（设计草案）

### 7.1 metrics.json
- `meta`: run_meta 的关键摘要
- `gate`: Gate-Data/Train/Eval 通过情况
- `overall`:
  - `primary_score`
  - `format_valid_rate`
  - `direction_accuracy`
  - `topology_accuracy`
  - `metric_pass_rate`, `metric_mae_km`
  - `composite_accuracy`
- `stratified`:
  - `by_spatial_relation_type`...
  - `by_difficulty`...
  - `by_topology_subtype`...
- `secondary_text_metrics`（可选）：BLEU/ROUGE（统一 tokenization；默认字符级）
- `error_analysis`: error_type 统计 + 混淆矩阵

### 7.2 predictions.jsonl（逐样本）
- `id`, `question`, `reference_answer`, `prediction_text`
- `parsed_json`（解析结果或 null）
- `correct`: {overall, dir_ok, topo_ok, metric_ok, composite_ok}
- `error_type`: list
- `spatial_relation_type`, `difficulty`, `topology_subtype`

---

## 8. 文件级改造清单（只列设计，不写代码）

> 以 V5.2 第 7.5.3 建议的“模块化评测脚本结构”为蓝本（V5.2:1581-1594），并与现有 exp01-exp09 保持可迁移。

### 8.1 新增（建议）
- `GeoKD-SR/experiments/contract/`
  - `dataset_manifest.schema.json`
  - `run_meta.schema.json`
  - `metrics.schema.json`
  - `predictions.schema.json`
- `GeoKD-SR/experiments/eval/`（对应 V5.2 scripts/modules 结构）
  - `inference.py`, `metrics.py`, `parser.py`, `error_analysis.py`, `reporting.py`
- `GeoKD-SR/experiments/train/`
  - `data_io.py`（jsonl loads + split loader）
  - `prompting.py`（统一 messages + JSON块输出规范）
  - `labeling.py`（labels/mask 生成）
  - `losses/`（把 C1-C6 的 loss 接口统一）

### 8.2 修改（建议）
- `GeoKD-SR/exp/exp01-exp09/*/train.py`：改为调用统一模块，仅保留方法变量配置
- `GeoKD-SR/exp/exp01-exp09/*/evaluate.py`：改为统一 evaluator CLI（或薄封装）

### 8.3 删除/弃用（建议）
- 弃用各 exp 内部自定义 BLEU/ROUGE/RA/SR-F1 实现，统一迁移到公共 metrics。

---

## 9. 设计验证（本阶段验收标准）

1) 任何一个 run 都能用 `run_meta.json + dataset_manifest.json` 复现：
   - 使用哪个 test 集
   - 用了什么 prompt/system
   - 生成参数是什么
2) 任意两个 method 的对比，不因评测口径/分词/词表差异导致不可比。
3) leaderboard 能按 V5.2 的对比集合产出：均值±标准差 + 显著性检验 + 效应量 + 多重比较校正。

---

## 10. 待确认的口径点（下一轮可以继续细化）
1) 是否保留 V5.2 的“LLM 辅助评测（RA 打分）”为抽样审计？（默认保留为可选 secondary）
2) JSON 块输出：是强制输出为 ```json fenced code```，还是允许纯 JSON 行？（建议强制 fenced，便于解析）
3) primary_score 是否按关系类型加权（使用 V5.2 的 relation_weights，V5.2:1112-1117）？

