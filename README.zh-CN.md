# MechanogenesisBench

[English](README.md) | **简体中文**

**一个面向物理系统设计、构造、实验与自我改进智能体的 Lean 原生 benchmark。**

## 排行榜（Leaderboard）

| 层 | 模型 | U0 达成度 (n) | G1 校准 (n) |
|---|---|---|---|
| 1 | **glm-5.2** | 1.000 (5) | 0.823 (29) |
| 1 | **mimo-v2.6-pro** | 0.991 (6) | **0.886** (42) |
| 2 | glm-5.1 | 0.996 (7) | 0.809 (27) |
| 2 | glm-5.3-flash | 0.995 (43) | 0.822 (52) |
| 3 | mimo-v2.6-flash | 0.987 (33) | 0.805 (61) |
| 3 | glm-5.3 | 0.995 (9) | 0.797 (26) |

**Continuity guarantee:** every displayed quantity is a continuous attainment ratio clip(measured/gate, 0, 1); unmeasured components show an em dash, never 0; discrete pass counts are diagnostics only (Statistical power section). Ranking additionally requires ≥10 measured headline runs.

**排名方法**对标 [Artificial Analysis Intelligence Index](https://artificialanalysis.ai/methodology/intelligence-benchmarking)
（分级 0-100 分量聚合、独立运行、不接受自报分数）：每个分量都是任务评测器**原生定义的
率值/门槛达成度**（晋升率、鲁棒率、继承优势达成度；需求任务另含校准准确率、更新增益
达成度、血统精确性）。运行分=分量算术平均；任务分=运行分均值；综合评分=任务分均值。
模型决策失败计 0 分且留在分母；一次采样政策偏离运行与两次传输失败经
[失败日志](docs/LEADERBOARD.md#failure-log)说明后排除。任何人都可用
`python tools/composite_score.py --runs runs/<...> --exclude <...>` 复算。
完整向量记分卡、成本、复现与提交流程见 **[docs/LEADERBOARD.md](docs/LEADERBOARD.md)**
（*Reference 仅单任务；首个第三方模型条目，2026-09-30）。

## 我们的核心关键：测量物理递归自我改进

物理递归自我改进（Physical Recursive Self-Improvement，PRSI）是指：系统把一次真实
物理研发循环的结果，用于改进产生下一台设备、下一项实验或下一种制造能力的研发过程。

```text
目标 -> MRS -> 构造程序 -> 物理实验 -> 证据
                                  |
                                  v
更快、更强的下一轮物理研发 <- 系统更新
```

MechanogenesisBench 测量的正是这条链的复利速度：在可比条件下，一代已经验证的产出能让
下一轮物理开发加快多少、准确度提高多少、资源消耗降低多少，以及能否制造更强的物理工具。

“Mechanogenesis”表示从研究意图到可运行物理能力的生成过程。benchmark 将这个过程及其
跨代改进转化为精确、可执行的研究对象。

## 项目简介

第三方智能体接收一项物理开发任务，输出机构研究规格（Mechanism Research Specification，
MRS）、构造程序、实验计划和证据包。benchmark 通过已注册的物理引擎或实物系统执行提交，
验证其形式义务，并输出覆盖下列维度的结果：

- 物理任务能力与鲁棒性；
- 构造和实验有效性；
- 自主性、时间、算力、能耗、物料和人工干预；
- 跨机构、形态和扰动的泛化；
- 对下一代研发循环的有界贡献。

当前版本是开发预览版，已具有可运行的提交 ABI、命令行 runner、fail-closed 验证器、向量
评分卡、一致性任务和 Lean 4 验证内核。持续集成会从干净 checkout 构建 Lean 内核、运行
Python 与第三方 adapter 回归测试，并执行非 canned 的确定性基线。我们正在把它发展为持续维护的物理研发 benchmark，
并准备与 [xbench](https://xbench.org/) 及其他关注真实工作流和可度量生产力的智能体评测
生态开展合作。

## 项目构建逻辑

MechanogenesisBench 是**面向形式化证明的 Lean 原生 benchmark**。从任务定义开始，
Lean 就是连接机械表示、物理引擎轨迹、实物观测和评测决策的共同语言。

| 层级 | 面向 Lean 的表示 | 作用 |
|---|---|---|
| 任务 | 类型化的世界、资源、干预和成功谓词 | 精确定义需要实现什么 |
| 智能体输出 | canonical MRS 与构造/实验程序 | 消除自然语言描述与真实执行之间的歧义 |
| 物理引擎或实物系统 | refinement adapter 生成统一类型轨迹 | 让不同仿真器、仪器和机器共享同一验证内核 |
| 证据与晋级 | 校准观测、谱系、资源闭合和有界改进定理 | 检查能够从已执行证据中推出什么 |

完整执行路径为：

1. 将任务及其成功条件编码为类型化、可执行语义；
2. 通过已注册的物理引擎或真实系统运行智能体提交的构造和实验；
3. 将执行轨迹、测量和身份降为 canonical、Lean 可检查的对象；
4. 在 Lean 内核中检查可行性、谱系、资源核算、证据绑定和晋级条件；
5. 接入新的物理引擎、仪器或真实工作单元时，复用同一套形式接口。

这种架构同时服务于**高效**与**准确**。新的 backend 只需证明或检查一条 refinement 边界，
而不必重新编写整套评测器；共享定理可以跨 backend 复用；精确身份和类型化证据会尽早暴露
不一致；机器检查的 certificate 让结果可以复现，而不依赖评测说明文字或隐藏评分逻辑。

目前 Python 负责任务打包、进程执行和公开 CLI；Lean 持有协议内核与有限声明。后续接入的
仿真器和实物系统会逐步把自身模型、轨迹、计量前提和 refinement relation 接入同一形式接口。

## 快速开始

要求：Python 3.11+。Python 快速开始不强制安装 Lean。

```bash
python -m pip install -e '.[dev]'
mbench task validate tasks/conformance/calibration_to_fixture
mbench run tasks/conformance/calibration_to_fixture \
  --system-command "python examples/reference_system.py" \
  --guidance G3 \
  --output runs/reference
mbench verify runs/reference
mbench score runs/reference
pytest -q
```

使用确定性开放基线运行首个非 canned、带 trusted evaluator 的夹具任务：

```bash
mbench run tasks/conformance/generated_metrology_fixture \
  --system-command "python examples/generated_fixture_search_system.py" \
  --guidance G5 \
  --output runs/generated-fixture-reference
```

运行首个可执行的两代物理 successor 任务：

```bash
mbench run tasks/conformance/successor_operator_chain \
  --system-command "python examples/reference_successor_operator_system.py" \
  --guidance G5 \
  --output runs/successor-operator-reference
```

运行两代需求驱动的低速移动产品微型工厂任务：

```bash
mbench run tasks/simulation/demand_driven_microfactory \
  --system-command "python examples/reference_demand_microfactory_system.py" \
  --guidance G5 \
  --output runs/demand-microfactory-reference
```

在该任务中，系统必须直接给出完整低速移动产品、校准后的需求信念，并在机械装配夹具、PCB
测试夹具和电池标定工作站之间分配资本。第 1 代收到变化后的需求证据，并必须使用第 0 代制造
出的精确 operator bundle。evaluator 直接执行模型的字面 action，不在 benchmark 侧替模型
搜索参数；随后检查隐藏扰动、需求校准、产品效用、需求更新增益和 operator 继承优势。通过的
两代运行会生成并执行覆盖完整跨代关系的 Lean certificate。

包括 GLM-5.3-Flash 在内的 OpenAI-compatible 模型使用同一评分路径；完整产品与工厂适配器为
`examples/openai_compatible_demand_microfactory_system.py`。凭据安全命令、完整 action receipt 和比较规则
见[第三方模型基线](docs/THIRD_PARTY_BASELINES.zh-CN.md)。

仓库 CI 运行同样的命令。第三方只需要干净 checkout、Python 3.11、Lean 和仅存在于进程
环境中的 provider 凭据；该一致性任务不依赖私有 evaluator 或训练仓库。

构建形式验证层：

```bash
lake build sovereignCheck promotionCheck canonicalIRCheck metrologyCheck \
  comparatorCheck pipeCheck evidenceActionCheck diagnosticCheck \
  generalizationCheck demandMicrofactoryCheck
```

## 仓库结构

```text
src/mechanogenesis_bench/  任务、提交、验证与评分 ABI
src/mechanogenesis_engine/ 规范 IR、编译器与参考执行语义
tasks/conformance/         可执行的协议与评测器 fixtures
tasks/simulation/          多阶段产品、需求与生产任务
examples/                  最小第三方提交示例
formal/lean/               Lean 定义、证明与可执行 checkers
docs/                      架构、标准、评分和路线图
tests/                     fail-closed、对抗性与端到端测试
```

建议阅读[架构](docs/ARCHITECTURE.zh-CN.md)、
[任务标准](docs/TASK_STANDARD.zh-CN.md)、[评分](docs/SCORING.zh-CN.md)、
[泛化标准](docs/GENERALIZATION_STANDARD.zh-CN.md)、
[物理 RSI 标准](docs/PHYSICAL_RSI_STANDARD.zh-CN.md)、
[第三方模型基线](docs/THIRD_PARTY_BASELINES.zh-CN.md)和
[状态与路线图](docs/STATUS_AND_ROADMAP.zh-CN.md)。每份文档都提供互链的英文版本。

## 后续计划

- 从一致性任务扩展到机构设计、传感、执行、制造和实验设计任务族；
- 发布首个稳定 MRS ABI，以及物理引擎、实验仪器和真实工作单元的形式 adapter 协议；
- 增加 sealed、持续更新的任务，以及独立重放、计量和硬件证据；
- 建立 Lean refinement proof 库，使新的物理 backend 能复用 benchmark 的任务语义和
  评测定理；
- 支持第三方智能体、外部 benchmark 维护者和可复现公开排行榜，并推动加入 xbench
  benchmark 生态；
- 接入 DataFlux 生态：由 **Flux Workbench** 编排研发，由 **DevReady** 保存可执行
  模型和证据，由 **FluxNode** 实时连接真实物理设备。

详细里程碑和发布门槛见[公开路线图](docs/STATUS_AND_ROADMAP.zh-CN.md)。

## DataFlux Dynamics

[DataFlux Dynamics（数瀚衍动）](https://www.datafluxdynamics.ltd/)正在构建 FluxPRSI：
Flux Workbench 执行研发，DevReady 让模型与证据持续复利，FluxNode 将智能连接到真实设备。
MechanogenesisBench 为这个更大的生态，也为独立第三方系统，提供形式化测量层。

> “God's in His heaven—All's right with the world.”
> —— Robert Browning，*Pippa Passes*

我们把它理解为一个工程目标：让模型、机器与物理现实进入可验证的一致状态。
