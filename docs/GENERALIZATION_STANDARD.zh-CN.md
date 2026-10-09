# Mechanogenesis 泛化标准 0.1

[English](GENERALIZATION_STANDARD.md) | **简体中文**

MechanogenesisBench 0.7 将“泛化”从一个 aggregate test score 改为三个不能互相抵消的
平面：

1. **任务宇宙**：world、intervention、embodiment、error-state、mechanism 五个有
   执行语义的因子轴；
2. **反捷径证据**：训练证据必须为每个注册低阶投影提供 same-projection / opposite-
   target witness；
3. **工程与递归证据**：sealed 组合外推、worst-mechanism、canonical/Lean/replay、
   independent backend、physical trial，以及可选的 actual/placebo RRC。

## 为什么不能只追求“点足够散”

几何距离、数据 entropy 和单轴 coverage 都可能很高，同时一个 projection-only
shortcut 仍然完全拟合训练集。标准把“shortcut 被粉碎”定义为：存在两个执行案例，
它们在 shortcut 可读取的全部轴上相同，但 evaluator-owned target 不同。

默认注册所有一阶和二阶轴投影。任务可以增加更高阶投影，但不得在看到 sealed 结果后
修改投影集合。

## 数据 ABI

每个 `FactorizedCase` 含：

- `case_id` 和 split；
- 五个注册因子；
- `target_signature`：canonical program、行为等价类或 evaluator preference；
- 完整执行成本。

因子必须改变 canonical/evaluator 执行语义。仅修改 prompt 或标签不算 coverage。

## 训练算法

`build_shortcut_destruction_curriculum` 只处理已经执行、target 已知的 archive，用于
课程筛选和 oracle ceiling。它不能被部署为下一物理实验选择器。

在线阶段使用 `select_disagreement_experiment`：`AcquisitionCandidate` 明确不含 target，
冻结 world model 通过 `CandidateTargetBelief` 提供 target distribution 和 model hash，
算法最大化每单位完整成本的 expected shortcut destruction。执行后 evaluator reveal
的 `FactorizedCase` 才能缩小 version space。

world-model forecast 不能单独承担 acquisition。若其 decision-level lower bound 无法
覆盖完整实验成本，控制器必须 abstain from learned choice，并调用
`select_grounded_separating_experiment`。该 fallback 在 residual projection 下固定
projection value，并在未被 projection 读取的因子上选择 farthest contrasts；候选 ABI
仍不含 target。结构 contrast 只形成 separability opportunity，不构成 collision
certificate。只有执行后观察到 target 不同，才能消灭 shortcut。

对于某 projection，若存在有证据支持的 finite ambiguity budget $B$，则执行
$B+1$ 个 structurally distinct contrasts 可强制至少一个 collision。没有该上界时，
“点足够散”只是一种搜索策略，不是有限成功保证。learned selector 可以降低平均成本；
只有新 access、传感器、干预或因果证据降低了可认证的 $B$，才能降低 worst-case 阈值。

若没有可执行 witness 而 residual shortcut 非空，训练阶段必须停止并返回
`non_identifiable/access_insufficient`。下一步应生成新干预、传感器、工装或世界，而
不是继续复制同分布样本。

`lean_guided_training_objective` 包含 task、counterfactual ranking、intervention
prediction、nuisance consistency、future RRC 和 shortcut survival 项。只有 residual
shortcut 清零后才启用 description-length/weight-decay pressure。

## Sealed split

合格的 compositional split 同时满足：

- case ID 和完整 factor tuple 不重叠；
- sealed 每个单轴值均在 train 出现；
- sealed 至少一个二阶组合未在 train 出现；
- train 已破坏全部注册 projection shortcut；
- overall 和 worst-mechanism accuracy/regret 过门。

最后一个条件不能被 overall 平均值替代。

## HWE-style 工程证据门

每个 sealed 案例必须通过 canonical parse、Lean kernel、reference replay 和独立
backend，并至少使用三个独立 numerical seeds。physical claim 还要求至少一个真实
物理 trial。该设计借鉴 HWE Bench 的逐级工程验证原则，但不声称机械制造与 FPGA
验证等价。

默认命令：

```bash
mbench generalization audit corpus.json \
  --predictions predictions.json \
  --engineering-receipt engineering.json
```

开发期 simulation-only 报告必须显式使用 `--allow-simulation-only`，输出不具有
physical evidence tier。

## 排行榜输出

不压成一个隐藏权重分数。至少并列报告：

- engineering frontier：成功/性能/时间/成本；
- sealed compositional accuracy/regret 和 worst-mechanism floor；
- destroyed/registered shortcut classes；
- evidence tier；
- 若为 Recursive Learner：actual-vs-parent、actual-vs-placebo 和完整净价值。

## 声明边界

通过本标准只证明对注册任务宇宙和 shortcut 类的有限外推证据。它不证明对任意新世界
的通用泛化，也不证明物理模型没有遗漏。
