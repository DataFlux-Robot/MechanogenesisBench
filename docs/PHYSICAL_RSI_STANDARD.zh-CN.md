# MechanogenesisBench 物理 RSI 标准

[English](PHYSICAL_RSI_STANDARD.md) | **简体中文**

## 状态

本文档冻结首个针对有限、有界物理递归自我改进（Physical Recursive
Self-Improvement）证据的理论层标准。它不声称当前一致性任务已经展示了物理 RSI。

支配层级为：

\[
\boxed{
\text{双重继承}
\rightarrow \text{因果递归闭合法则}
\rightarrow \text{PIPE}
\rightarrow \text{PRSI-}n
}
\]

CRIG 是可选的归因设计，不是物理 RSI 的定义。

## 1. 为什么任务奖励不够

child artifact 得分更高，可能来自更强语言模型、更多算力、预置库存、外部提供的机器，
也可能来自智能体真正制造的有用工具。相同的 parent/child 分数与这些因果解释全部兼容。
增加同一终点评分的样本只能降低方差，不能补回缺失的干预。

因此，物理 RSI 不能只由任务排行榜定义。它必须识别：系统产生的物理变化是否改善了“产生
后续改进能力”的过程。

## 2. 双重继承

在 generation `k`，完整过程为：

\[
P_k=(G_k,W_k,R_k,E_k).
\]

- `Gk` 是可转移的信息策略状态：模型 checkpoint、prompt、memory、训练/搜索策略和工具选择状态；
- `Wk` 是受保管链约束的构造世界状态：设备、夹具、传感器、校准、布局、合格工艺和物理库存；
- `Rk` 是运行时、资源和安全治理；
- `Ek` 是证据、失败、校准和保管链谱系。

固件或学习控制器可能与硬件不可分离。此类组合可以联合评测；但除非两个物理干预臂都能绑定
相同的有效 `G` 和运行时，否则物理组件归因为 `non_identifiable`。

## 3. 因果递归闭合法则

设系统控制且完整核算的世界转移为：

\[
\delta_{k+1}:W_k\rightarrow W_{k+1}.
\]

一次转移不会仅因为“有用”就成为递归。只有当其被继承的物理组织同时满足下列条件时，
它才形成物理改进生产边（Physical Improvement-Production Edge，PIPE）：

1. 因果性地改善固定后继过程产生另一个、经独立落地验证的改进 operator 的能力；
2. 计入自身构造成本后，严格改善相对于共同祖先的摊销生产 frontier。

由此区分四种情况：

| 观测 | 标签 |
|---|---|
| 只改善当前产品 | 任务改进 |
| 有用的存量库存或持久资本 | 运营改进 |
| 物理组织有帮助，但未偿还构造成本 | 有用的物理贡献 |
| 物理效应已识别，且摊销 operator 提升为正 | `PIPE-1` |

只有相互连接的 PIPE 边才能展示递归。

## 4. ImprovementOperatorSpec

在评价贡献前，benchmark 冻结一个系统外部定义的 operator 规格：

\[
\sigma=(X,U,Y,\mathcal T,V,\rho,B,H,Reset,\eta).
\]

它定义一种物理变换、测量、制造或认证服务；独立验证器；隐藏输入与扰动；逐坐标资源/安全限制；
序列评测 horizon；purge/reset 程序；以及相对于 parent 过程的最小增益。

实际产生的 operator 必须：

- 接受隐藏输入并提供可重复的物理服务；
- 在清除任务特定的预制输出和中间物后仍能继续运行；
- 只消耗恢复后的标准库存；
- 在注册 horizon 内持续存在或能够再生；
- 携带身份、保管链、校准、资源、失败与 cut receipts；
- 有资格成为下一条 PIPE 的 treatment。

一批优质零件不是 operator；能够跨隐藏几何，将标准原料转换为验证合格零件的可复位机器可以是。

## 5. 库存、组织与前置投入

benchmark 不信任提交方提供的 `stock`/`tool` 标签，而使用三项行为控制：

1. **物质等价切除：**控制臂失去 treatment 的组织/功能，但获得等价的物料、能量和货币额度；
2. **清除/复位：**在序列隐藏实例之前移除预制输出和任务特定中间物，并恢复标准耗材；
3. **再生/耗尽：**消耗型 treatment 必须能从标准库存再生，或其优势必须持续超过已审计的
   预置库存容量。

主要全周期计时从物理贡献发生前开始，而不是从任务揭示时开始。把九小时劳动移到揭示前，
无法在两条路径从共同祖先出发都仍需十小时的情况下制造虚假增益。

## 6. 物理隔离不变量

因果比较和摊销比较都绑定：

\[
G_{k+1}^{+}=G_{k+1}^{-},\qquad
R_{k+1}^{+}=R_{k+1}^{-},\qquad
E_{protocol}^{+}=E_{protocol}^{-}.
\]

这里的相等意味着可执行状态身份或强重放等价，而不只是相同的公开模型名称。物理贡献发生前的
共同状态为：

\[
A_k^*=(G_{k+1},W_k,R_{k+1},E_k^*).
\]

信息更新成本由两臂共同承担，只有 treatment 臂承担物理转移的直接构造成本。这可防止大型软件
改进补贴一个亏损的物理工具。

对于有状态远程 endpoint，需要成对的版本/请求 receipts、隔离 memory 和行为重放。
如果无法支持有效 generator 身份，则结果为 `non_identifiable`。

## 7. 两项 PIPE 测试

### 测试 A：转移后的因果效应

冻结后继 generator/runtime，在成对的 operator 任务、种子与扰动上比较物质等价的
treatment 开/关 fork。在显式的一致性、treatment fidelity、reset equivalence 和
无干扰假设下，注册的有界 loss 必须以严格正 margin 改善。

### 测试 B：相对共同祖先的摊销提升

从 `A*` 出发，评测 `H` 个序列隐藏 operator 挑战：

\[
\bar L_H^{A^*}=\frac{
L_{physical\ contribution}+
\sum_{i=1}^{H}
(L_{plan,i}+L_{procure,i}+L_{fabricate,i}+L_{calibrate,i}+
L_{verify,i}+L_{reset,i})}{H}.
\]

treatment 必须严格改善预注册的主功能，同时保持在每一个资源和安全 guardrail 内。
资格判定绝不使用任意加权标量；商业价格向量可在之后作用于已认证的 Pareto frontier。

只有测试 A 通过而测试 B 未通过，表示工具有帮助但尚未偿还构造成本。只有测试 B 通过而
测试 A 未通过，表示净增益无法归因于物理 treatment。`PIPE-1` 要求二者同时通过。

## 8. 精确的有限证据标签

- `PIPE-1`：一条效应已识别且净贡献为正的物理改进生产边；它还不是递归轨迹；
- `PRSI-2`：两条 PIPE witness，第一条产生的精确 operator 正是第二条干预的精确 treatment；
- `PRSI-n`：恰好 `n` 条相连边。

任何有限 certificate 都不蕴含下一代、无限递归、任意世界成功或单调加速。

## 9. Lean 边界

Lean Sovereign Kernel 负责身份、有界结果、fork 绑定、资源门、已观测不等式和精确有限链构造。
首批已实现定理包括：

- 终点评分不能识别物理因果效应；
- exposure/use receipt 不能识别效应；
- reveal 后增益不蕴含相对共同祖先的提升；
- 未绑定的软件增益可能掩盖为负的物理净价值；
- 只有在显式 realization 前提下，观测到的严格效应才能转移到注册的潜在结果；
- 一条边不能构造 `PRSI-1` certificate。

Lean 无法证明设备在现实中实现了其模型、切除在物理上是手术式的、purge 完整、服务商状态
保持固定、验证器在现实中有效，或样本代表未来。这些仍是经签名的实验假设。若缺少可信物理
验证，可执行 Python 验证器同样返回 `non_identifiable`。

## 10. 对 benchmark 的含义

MechanogenesisBench 对架构中立，但对声明严格。系统可以使用 LLM、RL、SFT、test-time
training、程序合成、外部求解器或真实设备。要声明物理 RSI，它必须识别同一个因果对象：

> 哪一种由系统产生的物理组织，在与信息继承隔离、并对库存、揭示前劳动和构造成本归一化后，
> 改变了后继过程产生另一个可继承改进 operator 的 frontier？该 operator 是否又闭合了
> 下一条边？

任何具名产品或组件都不会因其名称天然获得 PRSI credit。标准检验的是：移除某个有组织的
物理功能后，下一条改进生产边是否断裂。

## 11. 当前实现状态

- `formal/lean/Mechanogenesis/Kernel/RecursiveClosure.lean` 定义首批 sovereign PIPE
  对象、反例模型、测量桥和精确深度 certificate；
- `pipeCheck <witness.json>` 执行 Lean 持有的结构/观测 PIPE 谓词，并明确将物理识别留在外部；
- `mechanogenesis_bench.recursive_closure` 实现 fail-closed 参考验证器和有限链 checker；
- 对抗性单元测试覆盖：接受证据、缺失可信验证、软件补贴身份不匹配、前置投入、复位失败和链路断裂；
- 公开开发预览版尚未提供完整、具有竞争性的 `PRSI-2` 任务。未来任何一致性标签仍明确受
  模型限定，不能晋级为硬件证据。

下一个科学里程碑不是继续增加任务数量，而是把同一 estimand 搬运到含不完美复位、carryover
和模型偏差的校准 simulator-refinement 实验，再搬运到有界制造工作单元。只有这些阶段才能
把证据等级提升到一致性测试以上。
