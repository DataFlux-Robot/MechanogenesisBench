# MechanogenesisBench

[English](README.md) | **简体中文**

MechanogenesisBench 是一个面向第三方智能体的开发预览版基准。它评测智能体提出、
构造和测试物理设备的能力，关注证据与过程，而不只是智能体能否描述一个看似合理的机构。

我们的核心观点是：只有当智能能够自主制造并验证设备，而且由此获得的物理能力能够因果性地
改善后续研究或制造循环时，物理递归自我改进（Physical Recursive Self-Improvement，
PRSI）才真正开始。单纯的文本自我修订、CAD 图片或终点评分都不构成物理递归。

> **状态：尚不完整的开发预览版。** 当前仓库已提供可用的提交 ABI、fail-closed
> 验证器、向量评分卡、小型一致性任务，以及机器检查的协议不变量；但任务覆盖度和物理验证
> 尚不足以形成完整 benchmark 或公开排行榜。首个稳定版发布前，接口仍可能变更。

## 本仓库是什么

- 面向第三方智能体的 benchmark 协议；
- 任务包、提交和评测器接口；
- 覆盖能力、鲁棒性、自主性、资源和有界递归贡献的非标量评分卡；
- 对一致性测试、仿真、独立复核仿真、硬件在环和真实硬件进行严格区分的证据层级；
- 针对有界协议性质的 Lean 4 定义与证明；
- 仅用于检查协议一致性的刻意简化参考提交。

## 本仓库不是什么

- 它不是 FLUXPRSI，不包含 FLUXPRSI 训练循环、模型权重、权重更新策略、researcher
  实现或内部实验历史；
- 它不声称 PRSI 已经实现；
- 它尚不是竞赛级沙箱，也不是具有代表性的完整任务集；
- Lean 接受只证明编码后的有限协议条件成立；它不会把仿真 receipt 变成硬件证据，也不会
  证明学习策略一定能够到达一次成功更新。

这一边界是刻意设计的：参与者应按照公开协议实现自己的智能体，而评测器应独立于任何特定系统。

## Episode 模型

```text
智能体 -> MRS -> 构造程序 -> 执行/实验 -> 证据
      -> 独立评测器 -> 有界晋级决策
      -> 可选的下一代提交
```

MRS 是提交的机构研究规格包。递归声明还要求代际链路、精确谱系、评测方持有的证据，以及
资源归一化后为正的下游贡献。当前仓库只检验有界、有限的声明。

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

检查形式化协议层：

```bash
lake build sovereignCheck promotionCheck canonicalIRCheck metrologyCheck \
  comparatorCheck pipeCheck evidenceActionCheck diagnosticCheck \
  generalizationCheck
```

## 仓库结构

```text
src/mechanogenesis_bench/  公开任务、提交、验证和评分 ABI
tasks/conformance/         协议夹具；不构成现实能力证据
examples/                  固定的一致性提交，不是智能体 baseline
formal/lean/               有界 benchmark 协议的定义与证明
docs/                      范围、标准、威胁模型和开发路线图
tests/                     fail-closed 与端到端协议测试
```

建议从[架构](docs/ARCHITECTURE.zh-CN.md)、
[范围与声明边界](docs/SCOPE.zh-CN.md)、[任务标准](docs/TASK_STANDARD.zh-CN.md)、
[评分](docs/SCORING.zh-CN.md)、[泛化标准](docs/GENERALIZATION_STANDARD.zh-CN.md)、
[物理 RSI 标准](docs/PHYSICAL_RSI_STANDARD.zh-CN.md)和
[状态与路线图](docs/STATUS_AND_ROADMAP.zh-CN.md)开始。所有公开说明均提供相互链接的英文版。

## DataFlux Dynamics

[DataFlux Dynamics（数瀚衍动）](https://www.datafluxdynamics.ltd/)正在开发
FluxPRSI：一个更广义的物理研发系统，让软件、设备模型、实验和物理工具通过真实项目结果
持续改进。MechanogenesisBench 是与之分离的公开评测界面，用于评价第三方系统。
benchmark 与更广义系统都仍在开发中；公司网站和本仓库均不应被解读为已经完成 PRSI 的结果。

## 许可证

项目尚未选定开源许可证。仓库公开可见本身并不授予复用权。许可证选择是路线图中明确列出的
预发布治理事项。
