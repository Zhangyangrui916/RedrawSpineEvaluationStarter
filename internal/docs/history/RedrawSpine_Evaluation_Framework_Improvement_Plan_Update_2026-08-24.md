# RedrawSpine 测试框架改进计划状态更新

日期: 2026-08-24  
对应基线: `RedrawSpine_Evaluation_Framework_Improvement_Plan.md` Draft 1  
状态: 六个本地 trial 阻塞项已完成；Linux OSMesa 与正式 DS Bench freeze 尚待执行

## 1. 本次更新目的

本文不替代原改进计划，而是记录后续实验使哪些判断发生了变化、哪些事项已经落地，以及进入 final cases 改造前仍需确认的决策。

当前最重要的新事实是:

- 1:1 synthetic dev 可以在可接受的本地时间和包体内运行，并显著消除了旧 3.2 倍欠采样形成的周期条带。
- 完全公开 S1 和 validation references 后，public dev 不需要隔离评分服务。
- real-art 中 Claude 的 `0.6123` 低分不能归因于 deform/constraints，也不能笼统归因于 SD 高频。
- 原 RedrawSpine flood 会同时填补局部采样孔洞和大块未观测连通区域；后者不应成为 pixel-exact resolved 真值。
- real-art 的可靠自动评分需要由框架提供 trusted observation-support mask，并在评分临时副本中中性化 mask 外区域。

## 2. 相比原计划已经改变的决策

### 2.1 Public dev: 从隔离 scorer 服务改为完全公开 oracle

原计划倾向于开发一个隔离 public dev scorer，由服务持有不可直接读取的 dev reference。

现在改为:

- Public dev 直接公开 S0、S1、observations、validation poses、reference/no-op frames 和评分语义。
- Candidate 可以任意比较、调参或编写自己的分析工具；public dev 不承担最终保密职责。
- Public dev 可选附带透明的 `dev_score.py`，但不需要独立服务、私有进程或查询限额。
- Final Seed A/B 仍不得在开发过程中暴露 score oracle，正式评分只执行一次。
- Final cases 必须使用与 public dev 不同的 target seed 或资产，防止复制和硬编码泛化。

改变原因: dev case 本来就是教学和校准数据。只要 final instances 独立，隐藏 dev S1 并不能增加安全性，反而增加 scorer 隔离开发成本。

### 2.2 Observation 分辨率: 1:1 从建议变为已验证首选

原计划将 `2450 x 1900` 作为首先试验的尺寸，将 `1536 x 1192` 作为可能的性能折中。

现在已有 1:1 synthetic dev 实测:

- Coverage candidates: 32 poses。
- Selected observations: 6。
- Union coverage: 929,986 texels，旧 Seed A 为约 541,721。
- Public package: 更新生成器后约 23.2 MiB。
- Claude 重建: 30.2 秒，validation score `0.9974`。
- `page_019` 等主体 page 的固定采样条带消失，只剩连续遮挡形状。

因此 observation 继续以约 `1 world unit/pixel` 为默认方向。只有 DS Bench 目标容器出现明确 wall-time、RSS、OSMesa 或包体瓶颈时，才降到 `1536 x 1192`。

需要保留的限制: `1 world unit/pixel` 不保证每个真实 Mesh 局部都是 `1 texel/pixel`。UV 缩放、骨骼 scale、weighted mesh 和 attachment 原图尺寸仍会形成局部 minification。

### 2.3 未观测 texel: 从“保持 S0 或允许补全”改为区分数据生成与评分

原计划把以下两条路线并列为待选:

- Coverage 外令 `S1=S0`，整帧直接评分。
- 生成完整 S1，coverage 外不评分，允许 candidate 补全。

新的 real-art 证据表明，需要把两个问题分开:

1. S1 可以保留真实生产管线的 flood/inpainting 结果，便于视觉理解和生产预览。
2. Pixel-exact reconstruction score 只能评价 public observations 可靠约束的 support。

推荐评分语义改为:

```text
M = authoring/trusted renderer 生成的 public-observation reliable union mask

candidate_eval.rgb = M ? candidate.rgb : S1.rgb
noop_eval.rgb      = M ? S0.rgb        : S1.rgb
```

随后渲染 candidate/no-op/reference，并用中性化后的 No-op 重新归一化。Candidate 原始输出不被覆盖，仍用于 flood/inpainting 的视觉预览。

### 2.4 Mask 所有权: 不接受 candidate 提交的评分 mask

此前尚未明确 mask 由谁提供。现在确认:

- Scoring mask 必须由 trusted ID/UV coverage pass 生成。
- Candidate 不向 grader 提交 mask，否则可以通过排除错误区域操纵分数。
- Public dev 可以公开 trusted mask，帮助 candidate 对比自己的 inverse map。
- Final grader 私下持有 trusted mask；TASK 公开“mask 外不评分”的规则，但不必公开 final mask 文件。
- Candidate 自己输出的 mask 只用于诊断，不是评分权威。

### 2.5 Real-art 资产: 不再引入 fixed-context page 新概念

原计划曾考虑将约 50 张重绘 pages 与大量固定 context pages 分成不同合同。

现在采用统一输出合同:

- Skeleton 中有 206 个 MeshAttachments，引用 200 张唯一纹理 pages。
- 50 张 page 含 Run 12 重绘颜色。
- 150 张 page 的 S1 与 S0 相同。
- 所有 200 张 page 都是普通 `output_pages`；未重绘 page 只是正确结果恰好为 No-op。
- 不增加 dev-only `fixed_context_attachments` schema 字段。

改变原因: “不重绘、用于维持角色设计一致性的 attachment”可以自然表示为 `S1=S0`，与 final 问题形式没有冲突。

### 2.6 Deform/constraints: 保留在 real-art dev，不归入 final V1 门槛

已经确认 trusted renderer、starter renderer、Claude 实现和原 RedrawSpine 都通过官方 Spine runtime 完成:

- `AnimationState::apply()` 写入 deform 和动画状态。
- `Skeleton::updateWorldTransform()` 求值 IK/transform constraints。
- `MeshAttachment::computeWorldVertices()` 读取最终 deform 和骨骼结果。

因此 deform/constraints 没有干扰 real-art dev 的正常运行。它们保留在 public production calibration case 中，但 final V1 仍遵守较小的明示能力合同，不能用 real-art dev 的失败判定 final V1 实现错误。

### 2.7 Real-art 低分归因已经修正

此前曾初步把 Claude 的 `0.6123` 归因于真实 SD 高频、重采样和 flood。经过受控实验后，结论修正为:

- SD 高频不是已证明的主要原因。
- Deform/constraints 成功运行，不是阻塞。
- Claude 在自己严格接受的 support 上得分约 `0.9907`，说明 LS 求解本身准确。
- Claude 只利用 trusted reliable coverage 的 62.9%，因为它按 final V1 二值 alpha 假设拒绝大量真实半透明/抗锯齿 support。
- Run 12 written/flood texel 中，34.8% 在独立 trusted reliable public coverage 外；这部分没有唯一可辨识的像素真值。
- 未中性化 full-frame score 混合了“算法未利用真实半透明 support”和“不可观测 flood 被当成真值”两个因素，不能直接解释为逆向算法总质量。

### 2.8 Synthetic S1: 低阶解析场已替换为高维带限随机场

Claude 后续发现 legacy `periodic_field` 每通道、每页只有 5 个线性未知量。实测 8 个 target texel 样本即可把旧 S1 整页误差降到平均约 `0.42/255`，20 个样本约 `0.28/255`。公开 dev S1 会把这一生成器结构直接暴露给 final candidate。

现在已经决定并落地:

- S0 保持现有低信息、重复、不可唯一定位的 `source_field`。
- S1 改用 seeded high-dimensional `band_limited_v2`。
- 频谱使用平滑的 48-256 texel 波长 rolloff，优先避免干扰正常逆向，而不是追求高频反作弊。
- 每页、每通道由大量独立随机频率系数组成，不再存在少量相位/base 参数捷径。
- Legacy generator 保留为显式 `legacy_periodic_v1`，只用于尚未重生成的现有 Seed A/B 数据复现。
- 暂不增加自动低阶拟合 generator audit；当前捷径难度已经高于正常解题路径。

一次性回归验证:

| 指标 | Legacy periodic | Band-limited v2 |
|---|---:|---:|
| 8 样本旧 5 参数拟合平均误差 | 0.42/255 | 34.57/255 |
| 20 样本旧 5 参数拟合平均误差 | 0.28/255 | 21.25/255 |
| 100 样本旧 5 参数拟合平均误差 | 0.26/255 | 19.13/255 |
| Claude 正常 LS validation score | 0.9974 | 0.9972 |

因此旧捷径已经失效，而正常解题结果没有实质回归。

## 3. 已经落地的工作

### 3.1 synthetic_dev

位置: `C:/code/RedrawSpineEvaluationAuthoring/generated/dev_cases/synthetic_dev`

已完成:

- 新增 `dev_specs/synthetic_dev.json`。
- 使用 `2450 x 1900` 生成 1:1 observations。
- 打包 20 张 S0/S1 pages、6 observations、10 validation poses。
- 公开 `oracle/target_attachments`、target atlas、validation reference/no-op frames。
- 新增通用 `generator/package_public_dev.py`。
- JSON Schema、20-page output contract、Reference/No-op 和实际 candidate 重建均通过。
- Synthetic S1 已从 `legacy_periodic_v1` 重生成并重新打包为 `band_limited_v2`。

已验证基线:

| 实现 | Score |
|---|---:|
| Reference | 1.0000 |
| No-op | 约 0 |
| Claude LS, lambda=0.08 | 0.9972 |

### 3.2 real_art_dev

位置: `C:/code/RedrawSpineEvaluationAuthoring/generated/dev_cases/real_art_dev`

已完成:

- 新增 `generator/build_real_art_dev.py`。
- 从归档 RedrawSpine asset 和完整 SD Run 12 构建，不重新运行 SD。
- 保留 308 bones、209 slots、weighted meshes、deform、4 IK、7 transform constraints 和真实半透明 alpha。
- 删除 3 个不渲染的 PointAttachments，避免 renderer 将它们误判为可绘制 attachment。
- 输出 200 张唯一 pages，其中 50 张有重绘、150 张 `S1=S0`。
- 使用原 viewport `1856 x 2288`。
- 从原 sequence 构建 10 observations，包含 setup/rest pose。
- 生成 12 validation poses 和 reference/no-op frames。
- 打包 10 张原始 SD pose 图作为 production reference，明确不作为 equation truth。
- 使用 exact-white 规则从归档 output pages 合成固定 S1，并保持 S0 alpha。
- JSON Schema、200-page output contract、Reference/No-op 和实际 candidate 运行均通过。

包体约 139.9 MiB。Claude LS 运行约 41.4 秒，nearest+fill 约 4.0 秒。

### 3.3 Real-art 低分诊断

诊断目录: `C:/Users/yurayzhang/Downloads/real_art_dev_diagnostics`

已经生成:

- Validation frame 的 No-op/Reference/Claude/误差/中性化对比图。
- `R_arm_02_cloth_01` 的 S0/S1/Claude/observed/written/flood unsupported 对比图。
- Claude mask 与 archived written/flood mask 的 texture-space overlap report。
- 独立 trusted ID/UV coverage union 和 overlap report。
- Candidate-mask 与 trusted-mask 两种中性化的受控 grader 结果。

关键测量:

| 口径 | Score/比例 |
|---|---:|
| 原始 full-frame Claude LS | 0.6123 |
| Claude 自己接受的 support 上重新归一化 | 0.9907 |
| 独立 trusted reliable support 上重新归一化 | 约 0.6442 |
| Claude mask 覆盖 trusted support | 62.9% |
| Archived written/flood 在 trusted support 外 | 34.8% |

### 3.4 Flood 行为已核对

原 `floodWhitePixelWithNeighborColor` 的实际行为:

- 所有 `alpha > 11` 且未直接写入的 texel 初始化为 `NotWritten`。
- 前 3 帧后执行邻域 flood。
- Flood 在整个 opaque alpha 连通区域内反复传播，直到没有可继续填充的 texel。
- 它不知道 texel 是否曾经出现在 UV observation 中，也不区分“可见区域采样小孔”和“从未可见的大块区域”。
- 后续 pose 可以覆盖部分 flooded texel，但最终页面仍可能保留大量外推结果。

在 Claude mask 外的 729,233 个 written/flood texel 中:

- 29.0% 距最近 observed texel 不超过 1.5 texel。
- 14.0% 距离为 1.5-2.5 texel。
- 35.8% 距离为 2.5-32.5 texel。
- 21.2% 距离超过 32.5 texel。

因此 flood 同时包含局部补孔和远距离不可观测外推，不能把其全部结果作为精确 reconstruction truth。

### 3.5 文档与复现入口

已新增或更新:

- `C:/code/RedrawSpineEvaluationAuthoring/DEV_CASES.md`
- `C:/code/RedrawSpineEvaluationAuthoring/README_AUTHORING.md`
- `C:/code/RedrawSpineEvaluationAuthoring/dev_specs/synthetic_dev.json`
- `C:/code/RedrawSpineEvaluationAuthoring/generator/package_public_dev.py`
- `C:/code/RedrawSpineEvaluationAuthoring/generator/build_real_art_dev.py`
- `C:/Users/yurayzhang/Downloads/RedrawSpine_Evaluation_Framework_Improvement_Plan.md`

所有新增文本均为 UTF-8 without BOM。Authoring CTest、两个 case schema 和两个 output contract 均已通过。

## 4. 刚刚完成的工作

本轮围绕 real-art `0.6123` 进行了以下新增验证:

1. 重新渲染 Claude validation frames，并生成放大误差图。
2. 导出 Claude 自己的 200 张 observed masks。
3. 统计 archived Run 12 written/flood mask 与 Claude mask 的交集。
4. 构造“observed 内完美 S1、外 S0”和“observed 内 Claude、外真实 S1”的受控页面。
5. 证明 Claude 在自己接受的 support 上约为 `0.9907`。
6. 使用独立 trusted coverage renderer 对全部 10 observations 重新生成 reliable union mask。
7. 证明 Claude 只利用 trusted support 的 62.9%，real semitrans alpha 是主要能力差异之一。
8. 量化 archived written/flood 中有 34.8% 位于 trusted public coverage 外。
9. 核对原 flood 源码，确认它没有 visibility 边界，会传播到整个 alpha 连通区域。
10. 修正文档，撤回“低分主要由 SD 高频造成”的未经证明结论。
11. 复现并确认 legacy S1 的 5 参数拟合捷径。
12. 实现 48-256 texel 波长的高维 `band_limited_v2`，重生成 synthetic dev。
13. 验证旧稀疏拟合失效，同时 Claude 正常 LS 仍保持 `0.9972`。

## 5. 仍待讨论和确认的事项

### 5.1 是否为 real_art_dev 正式增加 trusted masks 与透明 dev scorer

建议增加:

```text
real_art_dev/oracle/observable_masks/*.png
real_art_dev/tools/dev_score.py
```

`dev_score.py` 应完成:

- 校验 candidate page set、尺寸、RGBA 和 alpha。
- 在临时目录中按 trusted mask 中性化 candidate 和 No-op。
- 渲染 validation poses。
- 使用中性化后的 No-op 重新归一化 observable reconstruction score。
- 同时保留未中性化 raw completion preview，供人工检查 flood/inpainting 美术效果。

待确认: 是否现在实现并把它作为 real-art public dev 的标准入口。

### 5.2 Final cases 是否采用相同的不可观测区域中性化

推荐采用，但尚未落地。需要冻结:

- Final grader 使用 texture-space canonicalization，还是 render-space valid mask。
- Trusted coverage 的 alpha 阈值、ownership 邻域半径和 bilinear footprint 规则。
- TASK 对“不可靠 support 不评分”的公开表述。
- Final trusted mask 是否只在 grader 私有侧保存。

不建议接受 candidate 提交 mask。

### 5.3 Final Seed A/B 是否重生成 1:1 observations

Synthetic dev 已证明 1:1 可行，但 final cases 尚未改变。需要在 DS Bench 容器中测量:

- 两 case clean build + reconstruction wall time。
- Candidate 和 OSMesa grader peak RSS。
- Starter、observations 和 private test files 包体。
- 44 个现有 hidden frames 的 grader 时间。
- Windows native reference 与 Linux OSMesa candidate 的 score margin。

资源不足时，优先降低 hidden grading 分辨率或 hidden pose 数，再考虑把 observations 降到 `1536 x 1192`。

### 5.4 Real-art 半透明 alpha 的定位

当前 real-art dev 保留真实 semitrans alpha，因此有意超出 final V1 二值 alpha 合同。需要确认:

- 继续把它定位为 optional advanced/production calibration case；或
- 另生成一个 alpha 二值化的 `real_art_v1_dev`，用于区分 alpha 能力与真实纹理能力。

不应使用 advanced real-art dev 的 `0.6442` 判断 final V1 实现是否正确。

### 5.5 Dev cases 的分发方式

当前两个包合计约 160 MiB，尚未复制进 starter。需要确认:

- 直接提交到 starter；
- 作为独立 public dev bundle 随 DS Bench 挂载；
- starter 只放 synthetic dev，real-art dev 单独分发。

建议 synthetic dev 随 starter，real-art dev 作为独立可选 bundle，避免主任务仓库膨胀和高级能力干扰。

### 5.6 Run 12 exact-white 合成规则是否长期接受

归档 run 没有保存最终 written mask。当前规则是:

```text
archived RGB != exact white -> 使用重绘 RGB
archived RGB == exact white -> 保留 S0
alpha -> 始终保留 S0 alpha
```

它确定、可复现，但可能把 SD 真正生成的纯白 texel误判为未写入。需要确认该近似是否足够用于 public dev，还是要从旧 UV/written 数据重新恢复更精确的 production mask。

### 5.7 Public dev 辅助反馈的最终粒度

需要决定透明 scorer 输出:

- 只输出 aggregate observable score；
- 同时输出逐帧 score；
- 是否输出 per-page coverage overlap；
- raw completion 只生成预览，还是增加非 resolved 的美术统计。

### 5.8 Starter 文档和测试尚未按新决策更新

仍需更新:

- `TASK.md` 的评分公式、未观测 support 语义、资源预算和 renderer 权威性。
- README build 路径与 author/candidate tests 分离。
- `page_manifest.json`、UTF-8、透明 RGB canonicalization 的说明。
- 移除或迁移 candidate 包中的 authoring `STATUS.md`。

## 6. 建议的下一步执行顺序

1. 确认 5.1 和 5.2: real-art dev 与 final grader 是否统一采用 trusted-mask 中性化。
2. 若确认，先实现公开 `observable_masks` 和透明 `dev_score.py`，用已生成诊断结果做回归测试。
3. 在 DS Bench 容器运行 1:1 synthetic dev，测量 wall time、RSS、包体和 OSMesa。
4. 根据资源结果重生成 final Seed A/B，或降级到 `1536 x 1192`。
5. 更新 starter TASK/README/tests，并决定 dev bundle 分发方式。
6. 使用无设计上下文的 cold agents 重新 rollout。
7. 在 calibration rollouts 后冻结 final cases、threshold、mask policy 和评分公式。

## 7. 当前结论

Public dev 数据构造已经完成，1:1 synthetic 路线得到正面验证，real-art 也证明了问题具有真实生产意义。Final binary-alpha cases 已冻结使用 trusted texture-space support 和 mask 外 S0 canonicalization，并完成本地重生成与校准。Real-art 的未经 mask 全帧分数仍不应用作模型能力结论；continuous-alpha 与完成度诊断保留为后续独立能力。

## 8. 六个本地 trial 阻塞项完成记录

本节覆盖第 5～7 节中已经被后续执行完成的事项。

已完成:

1. Final grader 使用 private trusted observable masks，在临时评分副本中把 mask 外 candidate RGB 恢复为 S0。
2. Private package 每案导出 20 张 observable masks，并验证 mask 集合、尺寸、二值值域及 `S1=S0` support 外不变量。
3. Final Seed A/B 已切换到 `band_limited_v2` 和 `2450 x 1900`，重新生成 observations、coverage、hidden frames 和 exports。
4. Starter 已同步新版 A/B 与公开 `synthetic_dev`；final cases 未泄漏 S1、masks、hidden poses、references 或 grader。
5. `TASK.md` 已公开评分公式、0.9 本地阈值、trusted-support canonicalization、forward semantics、UTF-8、透明 RGB 和临时资源预算。
6. Candidate preflight 与 maintainer source audit 已拆分；README 路径修正，candidate `STATUS.md` 已移除。
7. Clean Visual Studio Release build、starter preflight、source audit、三个 case schema 和三个 No-op output contract 均通过。
8. 已创建无 `.git`、无 build、无 results 的 `C:/code/_agent_trial_v2/work`。

新版校准:

| Baseline | Score | Result |
|---|---:|---|
| Reference S1 | 1.0000 | Pass |
| Claude LS, lambda=0.08 | 0.9981 | Pass |
| nearest scatter without fill | 0.9815 | Pass at 1:1 |
| Single-observation LS | 0.6807 | Fail |
| No-op S0 | approximately 0 | Fail |

因此本地 cold-agent trial 已可启动。仍未完成但不阻塞本地 trial 的事项是 Linux OSMesa 验证、DS Bench 正式资源预算与 threshold freeze、real-art 透明 scorer/双 mask 诊断，以及 dev bundle 最终分发方式。
