# 任务标准 0.1

[English](TASK_STANDARD.md) | **简体中文**

一个任务是包含公开问题、分级指导、可信评测器和私有案例的目录。

```text
task.toml
public/{world,inventory,equipment,access,disturbances,evaluator_contract}.json
guidance/G1.md ... guidance/G5.md
evaluator/<entrypoint>
private/<hidden assets>
```

`task.toml` 声明赛道、证据上限、可用指导等级、代数、最少晋级次数、鲁棒性阈值、评测器
命令和七维资源预算。

runner 只向参与系统暴露 `task.toml`、`public/`、一份 `mission.md` 和公开包摘要。
提交包含系统身份、声明的证据等级、资源使用量和连续的 generations 列表。每一代包含：

- 互不相同的 parent/child 进程哈希；
- 互不相同的 parent/child 世界哈希；
- 全部九个内容寻址 MRS 对象；
- 内嵌且哈希绑定的制品；
- 精确整数构造 receipts；
- 实验和 generator-fork receipts。

对于当前 fixture 任务，`compiler_certificate` 是组合后的 Lean Sovereign Kernel 对象。
它嵌入 lower 后的 canonical program、计量 refinement certificates、假设账本和 transition
receipts。可信评测器会根据存储的构造程序和独立重放重新生成完整对象，然后才考虑晋级。
Lean 随后要求 canonical operation 哈希和 receipt 哈希逐位置相等，而且每个 calibration
操作恰有一个 certificate。

可信报告绑定任务包与私有评测器包摘要。它为每一代记录制品哈希、置信界、margin、净价值、
鲁棒性、证据等级和两个 Recursive Research Credit 增量。

晋级采用 fail-closed 条件：

$$
L_{child}\ge U_{parent}+m
\land N>0
\land R\ge R_{min}.
$$

Recursive Learner 晋级还要求时间和预算 RRC 均非负，并至少有一项严格为正。被拒绝的
generation 不推进进程谱系或世界谱系。

物料数量使用任务声明的整数 quanta。每份 receipt 都强制
`input + reserve_draw = output + waste`；物料核算不使用浮点容差。
