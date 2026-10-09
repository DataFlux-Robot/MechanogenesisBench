# 威胁模型

[English](THREAT_MODEL.md) | **简体中文**

## 当前已 fail-closed 覆盖

- malformed schema 和缺失的 MRS 对象；
- 制品、任务和私有评测器包替换；
- 断裂的进程/世界谱系；
- 物料不闭合；
- 评测决策超过证据上限；
- 虚假的 accepted 标志、鲁棒性不足或净价值不为正；
- 被接受的 Recursive Learner 代中递归 credit 为负或缺失；
- 声明的资源预算超限；
- 两代参考任务中伪造跨代状态：可信评测器会重放 generation 0，并把内存中的 child state
  传给 generation 1，而不是信任提交方提供的 snapshot。

## 当前尚未隔离

开发 runner 会在宿主机上执行任意进程。它不能阻止文件系统检查、网络访问、评测器探测、
资源少报、时钟操纵或串谋，因此其最高证据等级是一致性测试。

在提供外部排行榜或硬件声明前，需要加入 OCI/microVM runner、只读公开挂载、物理分离的
私有评测、默认禁止网络、cgroup/GPU/能耗计量、签名时钟与仪器 receipt、可复现镜像和
append-only 轨迹存储。

形式证明在显式假设下建立协议蕴含。它不会把被攻破的评测器、错误的世界模型或未观测扰动
转化为有效物理证据。

公开的 `mengine --parent-state` 接口会验证 schema、世界绑定和库存上限，但不会证明任意
输入 snapshot 的可达性。这种文件只是开发输入，不是证据。带证据的多代运行必须重放前序
程序/receipts，或在未来使用签名保管链和远程证明。
