# 核心闭源文件清单（不上传GitHub）

以下文件是PHM核心IP，**不上传到代码仓库**：

## L1 引擎层（物理引擎核心）
| 文件 | 说明 |
|------|------|
| hsec_predictor.py | HESC预测引擎（d_eff/η/相变/因果锥/曲率/临界失效） |
| qec_optimizer.py | QEC优化器（12平台跑分榜，d₀标定） |
| physics_constraint_engine.py | 物理约束引擎（5条规则，违规拦截） |
| hsec_report_generator.py | 报告生成器 |
| standard_model_module.py | 标准模型参数（中微子/夸克质量推导） |
| millennium_algorithms.py | 千禧算法（素数计数/黎曼零点） |

## L2 心智层
| 文件 | 说明 |
|------|------|
| phm_v3.py | PHM v3.0自主循环（记忆流+自反性+内在动机） |
| phm_boot.py | 启动脚本 |

## L3 LLM协作层（含约束Prompt）
| 文件 | 说明 |
|------|------|
| deepseek_phm_bridge.py | DeepSeek双向通信（含8条物理规则Prompt） |
| phm_deepseek.py | 一键调用接口 |
| phm_deepseek_v2.py | V2版本（含增强校验） |
| resumable_1000.py | 大规模测试脚本（含测试方法论） |
| dynamic_verifier_test.py | 动态测试脚本 |
| .api_key | API密钥（绝对不上传） |

## L4 安全层
| 文件 | 说明 |
|------|------|
| hsec_firewall.py | HESC防火墙 |
| hsec_active_defense.py | 主动防御 |
| phm_penetration_test_v2.py | 渗透测试 |

## L5 API层
| 文件 | 说明 |
|------|------|
| api_server_v2.py | FastAPI服务端 |
