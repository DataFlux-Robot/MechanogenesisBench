# 第三方模型基线

[English](THIRD_PARTY_BASELINES.md) | **简体中文**

## 测评对象

首个非 canned 基线任务是
`tasks/conformance/generated_metrology_fixture`。模型读取公开任务、世界、干预域和预算，
输出一份严格类型的物理研究策略；benchmark 负责有界搜索、构造程序编译、规范语义执行、
Lean 可检查证书生成和 trusted evaluator 调用。

因此模型不能靠声称“夹具有效”或伪造实验 receipt 得分。模型控制策略，benchmark 控制执行
与裁决。

该任务只产生一代 `CONFORMANCE` 结果，用于检验第三方模型接入和策略可达性；它不证明硬件
性能、参数继承或 PRSI。

下一项校准任务是 `tasks/conformance/successor_operator_chain`：两代在同一规范 world state
中连续执行，第 1 代必须使用第 0 代制造出的精确 operator 加工产品。evaluator 检查 capability
字节身份、world lineage、held-out 误差和采购基线反事实。其需求 brief 仍是冻结合成刺激，
因此不构成真人需求满足或参数继承证据。

首个耦合需求与生产的任务是 `tasks/simulation/demand_driven_microfactory`。模型不再只输出
搜索策略，而是直接决定所有计分变量：两代中分别推断需求分布、预测 reject/adopt/delight、
给出完整低速移动产品，并投资机械装配、PCB 测试和电池标定 operator。第 1 代接收新需求
证据，同时必须使用第 0 代 operator 的精确字节。隐藏样例评估需求校准、物理鲁棒性、产品
效用、需求更新增益和继承生产能力的因果优势。

| 失败阶段 | 可观察局限 |
|---|---|
| Action 形成 | 产品/工厂 action 非法或不完整 |
| 需求感知 | 信念与 held-out 需求真值不一致 |
| 需求闭环 | 读取新证据后，第 1 代信念没有改善 |
| 产品实现 | 字面设计未通过安全、质量或效用样例 |
| 制造机器 | 资本计划未能同时改善三类生产 operator |
| 物理继承 | successor 未绑定或使用上一代精确 operator |
| 需求引导 | 可测 synthetic delight；human-endorsed surprise 必须来自获授权真人结果 |

确定性参考实现可以通过全部仿真 gate，因此说明任务可达，但不代表任何语言模型也可达；模型
baseline 只依据其保留的字面 action 报告。

## OpenAI-compatible 适配器

```bash
python -m pip install -e '.[dev]'
lake build sovereignCheck promotionCheck demandMicrofactoryCheck

export ZHIPU_API_KEY='...'
export MBENCH_API_ENDPOINT='https://open.bigmodel.cn/api/paas/v4'
export MBENCH_MODEL='glm-5.3-flash'
export MBENCH_THINKING='enabled'
export MBENCH_REASONING_EFFORT='max'
export MBENCH_TEMPERATURE='1'
export MBENCH_TOP_P='0.95'
export MBENCH_MAX_TOKENS='8192'

mbench run tasks/conformance/generated_metrology_fixture \
  --system-command 'python examples/openai_compatible_fixture_system.py' \
  --guidance G5 \
  --output runs/glm53-fixture-g5-001
```

两代 history-enabled 对照：

```bash
export MBENCH_HISTORY_MODE='public_evidence'
mbench run tasks/conformance/successor_operator_chain \
  --system-command 'python examples/openai_compatible_successor_operator_system.py' \
  --guidance G5 \
  --output runs/glm53-successor-history-001
```

运行耦合需求微型工厂：

```bash
export MBENCH_HISTORY_MODE='public_evidence'
mbench run tasks/simulation/demand_driven_microfactory \
  --system-command 'python examples/openai_compatible_demand_microfactory_system.py' \
  --guidance G5 \
  --output runs/glm53-demand-microfactory-history-001
```

再用 `MBENCH_HISTORY_MODE=none` 运行 matched stateless 臂。此时模型仍能看到第 1 代可用的
精确物理 operator，但不接收上一代需求与产品证据，从而把跨代证据使用与物理 operator
继承分开。

修改 endpoint、model 和 `MBENCH_API_KEY_ENV` 即可接入其他兼容模型；第三方也可直接实现
进程 ABI，不必依赖仓库内的模型代码。

## 可复现产物

成功运行会保存：不含凭据的完整请求与响应 envelope、送入严格 parser 的精确响应文本、请求与返回模型身份、
provider request ID、token 用量、原始延迟、每次有界重试、策略、构造程序、MRS、trusted
evaluation、verification 和向量分数。模型 action 被嵌入内容寻址的 `update_proposal` MRS
对象；替换请求或输出会改变提交身份。API key 不写入任何产物。

可通过 `MBENCH_REPLAY_MODEL_CALL` 离线重放已归档调用。若旧调用只有 request hash 而没有
完整请求，则必须标记为 `legacy_hash_only`；它可以复现策略执行和评分，但不能满足更强的
完整请求溯源要求。离线重放必须计入原 provider 延迟，不能用更短的 replay 时间冒充模型耗时。
两代适配器分别使用 `MBENCH_REPLAY_MODEL_CALL_G0` 与
`MBENCH_REPLAY_MODEL_CALL_G1`，避免把同一 action 静默复用于两代。

对微型工厂任务，完整 action 包括每一代的需求信念、结果预测、产品规格和三类 operator
资本计划。通过的运行还会保存并用 Lean 执行 `demand_microfactory_certificate.json`。

## 比较纪律

只有 task digest、guidance、prompt、模型控制项、网络/重试策略和 evaluator digest 一致时，
分数才可直接比较。provider 更新模型后，即使营销名称不变，也应形成新基线身份。provider
侧能耗和未报告的 API 价格属于未观测资源轴，不得据此声称能效或成本优势。正式基线还需要
多次独立调用或 provider 支持的 seed，才能报告不确定性。

## 人类需求扩展

人群模拟应作为可选的“需求形成”轨道，而不是混入物理核心总分。MatrAIx 适配器可以采样
异质 persona、反驳候选需求 brief 并记录分组响应；这些输出始终属于
`synthetic_response`，不能提升物理真值、购买、采用或福利主张。真实需求校准要求预测先冻结，
随后由获授权且由 evaluator 持有的真实结果裁决。

这一模块化边界既支持人类需求引导的机器研发，也避免把某个人类模拟模型变成强制依赖，或让
模拟需求补偿失败的构造与实验。

下一项注册的人类需求赛道将分为三步：使用前需求感知、使用后需求修正，以及对真正新功能的
延迟认可。persona 模型可以生成压力样例和人群假设；只有获授权的真人观测可以闭合需求校准
或正向惊喜主张。这样才能测量需求感知、闭环和引导，而不把模拟认可当作真值。
