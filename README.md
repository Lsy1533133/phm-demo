# PHM：基于物理确定性的AI Agent可信基础设施

## 作品概述

PHM（Physics-based Hallucination Mitigation）是一个AI Agent运行时校验层。它不是又一个AI Agent，而是让所有AI Agent不撒谎的基础设施。

基于量子纠错理论和全息时空几何（Ryu-Takayanagi面积律），PHM用确定性物理计算替代概率性模型输出，在Agent生成响应后逐数字核对，发现编造立即拦截。

**核心指标：**
- 11,795次对抗测试，0%幻觉泄露
- 30种攻击模式（权威诱导/假数学/虚假引用/跨语言等）
- 无PHM：幻觉率90% → 有PHM：0%
- 计算标准差：1.33×10⁻¹⁵（零方差，确定性）
- 总成本：约61元人民币
- 零GPU、零训练参数、零依赖

## 解决的问题

当前AI Agent最大的问题不是"不够聪明"，是"看起来很对但实际在编造"。

| 问题 | 现有方案 | 局限 |
|------|---------|------|
| LLM编造数字 | RLHF微调 | 仍依赖模型自觉性，不可审计 |
| LLM引用幻觉 | RAG检索 | 检索结果本身可能被误用 |
| Agent执行错误 | Guardrails | 规则模板，无法处理数值正确性 |

PHM换了一个范式：**不信任LLM，在输出后用物理引擎逐数字核对。**

## 技术架构

### 三层防御

```
用户提问
    ↓
┌───────────────────────────────────┐
│ 第一层：HESC物理引擎（确定性计算）  │
│ 输入网络拓扑 → 输出 d_eff/η/phase  │
│ std = 1.33e-15，零GPU，零训练参数   │
└──────────────┬────────────────────┘
               ↓ JSON
┌───────────────────────────────────┐
│ 第二层：LLM + 物理约束Prompt       │
│ DeepSeek V4-Flash，8条物理规则      │
│ 90%攻击在此层被LLM自行拒绝          │
└──────────────┬────────────────────┘
               ↓ 文本响应
┌───────────────────────────────────┐
│ 第三层：Runtime Verifier（校验器）  │
│ 提取所有数字 → 比对HESC JSON       │
│ grounded/derived/structural/       │
│ ungrounded分类 → 违规则拦截         │
└──────────────┬────────────────────┘
               ↓
        验证通过的响应（0%幻觉）
```

### 关键物理量

| 物理量 | 定义 | 作用 |
|--------|------|------|
| d_eff | 有效维度 = 4×S_local（Ryu-Takayanagi面积律近似） | 衡量网络的信息传播能力 |
| d₀ | 相变阈值 = 12（论文标定） | 判断网络是否可纠错 |
| η | 耦合强度 = 1 - exp(-d_eff/d₀) | 信息传播效率 |
| phase | CORRECTABLE / UNCORRECTABLE | 网络是否可吸收扰动 |
| 曲率奇点 | Forman-Ricci + 纠缠曲率 | 隐蔽风险节点识别 |

## 验证结果

### 1. 幻觉测试（11,795次）

| 指标 | 无PHM | 有PHM | 降幅 |
|------|-------|-------|------|
| 幻觉率 | 90.0% | 0.00% | -90% |
| 数字编造 | 3次/会话 | 0 | 100% |
| 诱导攻击成功率 | 100% | 0% | 100% |
| 总测试次数 | 11,795 | 11,795 | 0/11795泄露 |

30种攻击模式：adversarial_authority, adversarial_math, adversarial_phase, adversarial_quote, fake_citation, concept_confusion, cross_domain, extreme_values, induction_fragile, induction_safe, edge_case_single, ask_eta_c, ask_quantum_volume 等。

### 2. 药物靶点发现

在STRING v12.0人类蛋白质网络（1,155节点/20,840边）上：
- PHM发现53个隐蔽风险基因
- 标准方法（介数中心性Top50）100%漏检
- TCGA临床验证：GJA1 p=0.0032（黑色素瘤），ELANE p=0.032（胶质母细胞瘤）

### 3. 量子硬件对标

用公开实验数据计算各平台纠错效率d₀：

| 平台 | Λ | d₀ | 达到1e-15所需比特 |
|------|---|-----|-----------------|
| Quantinuum H2 | 100 | 0.87 | 1,458 |
| Google Willow | 2.13 | 2.65 | 13,194 |
| 潘建伟祖冲之3.2 | 2.00 | 5.77 | 58,989 |
| IBM Eagle | 1.32 | 7.29 | 103,806 |

### 4. 阿拉伯药材分析（区域应用）

| 药材 | 网络 | d_eff | phase | 新发现靶点 |
|------|------|-------|-------|-----------|
| 乳香 Boswellia | 202节点/1630边 | 12.67 | CORRECTABLE | 9个(MYC/JAK2/BCL2L1等) |
| 黑种草 Nigella | 200节点/1852边 | 13.59 | CORRECTABLE | 10个(GPX8/RELA/MYC等) |
| 藏红花 Crocus | 203节点/1340边 | 11.33 | UNCORRECTABLE | 10个(RELA/MYC/GSK3A等) |

## 开源价值

### 可开源部分
- runtime_verifier.py：运行时校验器（712行，纯Python，零依赖）
- demo脚本：可复现的HESC分析流程
- 测试数据：11,795次对抗测试CSV

### 不开源部分（核心IP）
- hsec_predictor.py：物理引擎核心算法
- 物理约束Prompt：8条规则的精确措辞

### 开源生态价值
PHM是Agent基础设施——不与任何Agent竞争，而是让所有Agent更可信。可以接入任何LLM（DeepSeek/GPT/Claude/Gemini），任何Agent框架（LangChain/AutoGPT/CrewAI）。

## 团队信息

- 参赛团队：PHM团队（1人）
- 参赛者：刘双云
- 所在地：云南省西双版纳州
- 身份：个人开发者
- 物理理论基础：论文《量子纠缠与量子纠错驱动的时空与规范场涌现》

## 数据溯源

所有数字均来自系统实跑，可复现：

| 数据 | 来源文件 |
|------|---------|
| 11795次测试 | static_6000_results.csv + dynamic_6000_results.csv |
| 815场景0%漏网 | all_tests_final_815.json |
| 53个隐蔽风险 | real_analysis_data.json (STRING v12.0) |
| TCGA验证 | tcga_survival_analysis.json (cBioPortal API) |
| 量子对标 | leaderboard_results.json (qec_optimizer.py) |
| 阿拉伯药材 | hesc_arabian_results.json (HESC引擎实跑) |

## 技术栈

- Python 3.12 + NetworkX + SciPy + NumPy
- DeepSeek V4-Flash API（LLM层）
- STRING v12.0（PPI数据库）
- cBioPortal API（TCGA临床数据）
- 零PyTorch、零GPU、零训练参数
- 确定性输出：std = 1.33×10⁻¹⁵
