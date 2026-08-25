# RedrawSpine 测试框架改进计划

版本: Draft 1  
日期: 2026-08-24  
范围: `RedrawSpineEvaluationStarter`、私有 authoring/generator、trusted grader、DS Bench 运行与隔离

## 1. 文档目的

本文汇总当前测试资产、candidate trial 和私有 grader 验证中发现的问题，并给出下一阶段的实施顺序与验收标准。

V1 的核心目标保持不变: 给 candidate 多个 Spine 姿势下的 `before/after` 观察，要求它恢复一套可跨姿势复用的静态 attachment pages；最终按隐藏姿势的渲染结果判断是否 resolved。评分只判断最终行为，不要求复刻原 `RedrawSpine` 的 nearest scatter 或任何指定内部架构。

## 2. 当前基线与已确认事实

### 2.1 当前用例

- 两个 candidate-visible cases: `static_mesh_seed_a`、`static_mesh_seed_b`。
- 共 13 组公开 observations，20 张独立 attachment pages。
- 支持 Region、ordinary/weighted/linked Mesh、attachment switching、骨骼变换和 draw order。
- 不包含 deform、IK/path/transform/physics constraints、clipping、复杂 blend 和 atlas packing。
- 当前 viewport 为 `2450 x 1900` world units，observation render size 为 `768 x 596` pixels，约 `3.19 world units/pixel`。

### 2.2 已验证分数

以下结果均由真正的私有 `trusted-render` 和当前 grader 复核:

| 实现 | Seed A | Seed B | 总分 | 结果 |
|---|---:|---:|---:|---|
| Reference S1 | 1.0000 | 1.0000 | 1.0000 | 通过 |
| No-op S0 | 约 0 | 约 0 | 约 0 | 失败 |
| 初始 Claude 输出，错误外推 coverage | 0.7448 | 0.8215 | 0.7832 | 失败 |
| LS，正确 observed mask，lambda=1.0 | 0.9663 | 0.9711 | 0.9687 | 通过 |
| LS，正确 observed mask，lambda=0.08 | 0.9819 | 0.9847 | 0.9833 | 通过 |
| nearest-style scatter + 邻域填孔 | 0.9774 | 0.9810 | 0.9792 | 通过 |
| nearest-style scatter，不填孔 | 0.4127 | 0.4761 | 0.4444 | 失败 |

这些结果说明:

- 当前 grader 能稳定区分 No-op、缺少 footprint 建模的实现和完整重建。
- 多种合理实现均可超过 `0.9`，符合“只冻结最终行为”的目标。
- 超过 resolved threshold 后的小分差不用于排名，也不应反向强迫 candidate 采用某种算法。
- 当前最大的非预期难点是 coverage 规则未在 starter 中公开，以及低分辨率形成的周期性 texel 条带。

### 2.3 原 RedrawSpine 与当前评测的关系

- 原项目使用约 `1 world unit/pixel` 的 framebuffer。
- 原项目的逆向反写是 nearest-style、单 texel scatter、首写优先，并带 written mask/flood 处理。
- 原项目的前向纹理采样仍然使用 `GL_LINEAR`。
- 当前评测使用 `GL_LINEAR` forward renderer，并允许 candidate 用 bilinear least squares、nearest scatter、CPU raster、GPU ID/UV pass 或其他方法。
- V1 不把 `shift +1 texel`、nearest/bilinear 或多尺度 sampling 作为独立 resolved 门槛。

## 3. 已对齐的设计原则

### 3.1 Candidate 必须有合理的开发反馈

不采用“完全不可调试、最后只运行一次”的纯黑盒开发方式。测试框架应同时提供:

1. 可无限运行的本地合同和自洽性检查。
2. 与最终实例分离的 public development scorer。
3. candidate 无法在开发过程中查询的 final hidden grader。

文件和进程隔离只能防止直接读取 reference、S1 pages 和 hidden poses，不能阻止通过反复查询最终分数进行 score-oracle 搜索。因此最终 Seed A/B 的真实 hidden score 不向 candidate 暴露。

### 3.2 Public dev oracle 与 final grader 必须使用不同实例

Public dev package 应使用独立的 dev target seed、observations 和 validation poses；条件允许时再使用不同角色资产。当 S1 pages 和 validation references 本身就是公开 oracle 时，不需要开发隔离评分服务。candidate 可以反复比较、调参或运行透明评分脚本，这属于正常调试。

最终 cases 必须是 candidate 从未查询过的新实例。这样即使 candidate 对 dev case 过拟合或硬编码，也无法通过 final hidden cases。不能把人工代码审查作为防止 score-oracle 作弊的主要手段。

### 3.3 优先使用接近原始管线的 observation 分辨率

第一选择是将 observations 提升到约 `2450 x 1900`，即接近 `1 world unit/pixel`。只有在 DS Bench 目标容器中测得明确的时间、内存、包体或 OSMesa 性能瓶颈后，才降低 observation 分辨率。

如果需要降级，首选候选尺寸为 `1536 x 1192`，约 `1.6 world units/pixel`。当前 `768 x 596` 只作为最后的低资源回退，不再作为未经性能验证的默认值。

Observation 分辨率与 hidden grading 分辨率可以解耦。高分辨率 observations 负责提供足够的反写信息；hidden grader 可以用较低分辨率验证静态 pages 在新姿势下的行为。

### 3.4 Stable Diffusion 不进入正式运行时

真实 SD 最符合生产语义，但不适合作为 candidate 或 grader 的在线依赖。后续可由 authoring 端离线生成并冻结一个真实 SD development case，用于:

- 验证 attachment pages 的实际美术连续性。
- 检查其他姿势下的接缝、旧皮肤残留和风格漂移。
- 校准合成 S0/S1 是否仍代表真实工作负载。

正式评测仍使用固定 PNG、确定性 renderer 和可复现 grader。

### 3.5 不靠伪影或隐藏规则维持判别力

周期性 sampling 条带、未公开的 coverage 外 S0 规则和 grader 路径差异都不是应保留的难度。正确实现集中在 `0.97-0.98` 是允许多种方案通过的正面信号，不需要人为拉开其分数。

真实通过率应由多个无设计上下文的 cold-agent rollouts 测量。不能根据同一实现的几个末端变体推断模型通过率，也不能在没有 rollout 数据前加入 deform、packing 或苛刻时间限制来补“判别力”。

## 4. 仍需实验后冻结的决策

### 4.1 未观测 texel 的评分语义

当前 authoring 规则是:

```text
S1 = target color   within reliable public observation coverage
S1 = S0             outside that coverage
```

它忠实对应原 RedrawSpine 的保守部分重绘语义，也使 grader 可以直接比较完整 hidden frames。但在 `3.19 texel/pixel` 下，coverage 呈周期性条带，生成的 page 不像完整新皮肤。

分辨率试验后需在以下两个方向中冻结一个:

**方向 A: 忠实复现保守部分重绘**

- 提高 observation 分辨率，消除 sampling lattice 形成的条带。
- coverage 外继续令 `S1=S0`。
- 在 TASK 中明确这是冻结的数据合同，不能要求 candidate 猜测。
- candidate 向真实遮挡盲区外推新颜色会与目标不一致。

**方向 B: 允许生产型补全**

- S1 在整张 opaque attachment 上生成连续目标皮肤。
- grader 不评价 public observations 无法辨识的 texel。
- candidate 可自由使用 flood fill、Laplacian、inpainting 或保留 S0。
- 需要实现 private texel canonicalization 或 render-space valid mask。

选择标准不是哪个方向分数更分散，而是最终测评究竟要复现现有 RedrawSpine 行为，还是评价允许补全的完整生产资产。

### 4.2 Public dev oracle 的反馈粒度

公开 dev case 至少提供 S0、S1、observations、validation poses 和 reference/no-op frames。透明辅助脚本可以返回:

- 仅 aggregate score；或
- case score、mean、bottom 20%；或
- 进一步返回逐帧诊断。

因为 dev 与 final 实例分离，详细诊断不会泄露最终答案；辅助脚本不是安全边界，也不是发布阻塞项。Final hidden grader 始终不向 candidate 提供可迭代反馈。

## 5. 分阶段实施计划

### Phase 1: 1:1 分辨率单 case 试验

只为 Seed A 生成 `2450 x 1900` 实验版本，不立即替换正式 cases。

需要采集:

- 每页 reliable coverage / opaque texel 比例。
- coverage bbox 内孔洞比例。
- 最大孔洞半径和周期性条带检测结果。
- 各 page 的 coverage 连续性和视觉预览。
- observation、starter export 和 private test files 的磁盘体积。
- generator、candidate、PNG IO 和 trusted grader 的运行时间。
- candidate 与 grader 的峰值 RSS。
- Windows native 与 Linux OSMesa 的最终分数裕量。
- No-op、LS、nearest+fill、nearest-no-fill 的分数。

若 DS Bench 资源不满足要求，按以下顺序降级:

1. 保留 1:1 observations，降低 hidden grader render size。
2. 减少冗余 hidden poses。
3. 优化 reference/no-op frame 的生成与存储方式。
4. 尝试 `1536 x 1192` observations。
5. 最后才回退到 `768 x 596`。

### Phase 2: 补强 coverage audit

现有 audit 只关注 union 相对 best-single 的增益，无法阻止条带状稀疏 coverage。新增 gate:

- 每个实际出现 page 的绝对 coverage ratio。
- coverage bbox 内 hole ratio。
- 最大内部孔洞半径。
- 周期性行列条带检测。
- 主体区域连通性。
- 每页是否只存在真实遮挡/轮廓盲区，而不是采样晶格盲区。
- nearest 单 texel footprint 与 bilinear 2x2 footprint 的分别统计。

阈值必须根据 1:1 Seed A 实测结果制定，不在本文中猜测数值。

### Phase 3: Public development feedback

增加与 final cases 分离的完全公开 dev oracle:

- dev package 公开 S1 pages、validation poses、reference/no-op frames 和评分公式。
- public dev 不需要隔离服务；可选透明脚本只负责使用便利性。
- dev oracle 可反复使用；final score 不可查询。
- candidate 必须被明确告知，observations 未必唯一确定逐 texel S1，主要按 render-space 行为诊断。
- final evaluation 在全新实例上重新构建和运行 candidate。

同时提供不依赖私有答案的本地工具:

- output contract。
- S0 `before` 自校准误差。
- candidate pages 在 public observations 上的重投影误差。
- equation-level interpolation holdout，明确它只用于调求解器，不代表 hidden-pose 泛化。
- 使用 candidate pages 渲染任意动画姿势的预览命令。

### Phase 4: Grader 与隔离加固

- 保持 trusted renderer、spine-cpp、shader 和 PNG loader 与 candidate 隔离。
- 最终 grader 只读取 result pages，不使用 candidate 修改后的 skeleton、atlas、runtime 或 shader。
- 验证 candidate 子进程无法读取 `/test_files`、grader 参数、环境变量中的私有路径和其他进程文件描述符。
- 保留 page set、尺寸、RGBA8、alpha、symlink 和路径安全检查。
- 明确透明 texel RGB 的 canonicalization 行为。
- 根据 Phase 1 和 4.1 的决策实现 coverage 外 S0 合同或无观测区域中性化。
- Final hidden evaluation 每次 submission 只执行一次，不提供中途 oracle。

### Phase 5: Starter 文档与测试整理

更新 `TASK.md`:

- 公布评分边界、相对 No-op 的 render-space L1、聚合方式和 resolved threshold。
- 说明 hidden 使用未公开姿势，但不会隐藏能力合同。
- 明确 reference renderer 是权威 forward semantics；实现可以替换，语义不能改变。
- 说明 `page_manifest.json` 的用途和所有文本文件的 UTF-8 编码。
- 说明 grader 如何处理透明 RGB 和未观测 texel。
- 给出 build、单 case、总 submission 的时间与内存预算。
- 统一 Ninja、Windows multi-config 和 Linux 可执行文件路径示例。

整理测试:

- candidate preflight 与 author-only source packaging audit 分离。
- source-only audit 不再因为 candidate 按 README 创建 `build/` 而失败。
- `STATUS.md` 移回 authoring 侧，不作为 candidate 说明文档。
- public checks 不访问 RGB hidden truth，也不约束 candidate 内部实现。

### Phase 6: 真实 SD development case

- authoring 端离线运行一次真实 RedrawSpine + SD 流程。
- 冻结 observations、必要元数据和人工检查过的目标表现。
- 不把 SD、模型权重、网络 API 或随机推理放入 benchmark runtime。
- 先作为 development/calibration case，不立即作为 resolved gate。
- 对比合成 case 与真实 case 的采样密度、色彩频谱、遮挡残留和跨姿势一致性。

### Phase 7: 跨平台与 cold-agent 验收

- Windows native 负责本地 authoring 迭代。
- Linux OSMesa 负责 DS Bench 最终平台验证。
- 使用 Reference、No-op 和至少三种独立正确实现验证分数裕量。
- 使用多个无 `Context.txt`、设计文档和 authoring 私有信息的 cold agents 做校准 rollout。
- 记录失败发生在任务理解、Spine 几何、采样、coverage、输出合同还是资源限制。
- 在指定的 calibration rollouts 后冻结阈值；正式评测开始后不根据榜单移动阈值。

## 6. 验收标准

框架进入可发布状态前必须满足:

1. Observation coverage 中不存在由固定采样间距造成的明显周期条带。
2. 目标 page 在选定的未观测语义下具有可解释的美术表现。
3. Candidate 可以在不接触 final hidden truth 的情况下获得有效开发反馈。
4. Final hidden score 不能在任务过程中被反复查询。
5. 至少两种不同重建路线能以明确裕量通过，No-op 和缺失核心能力的实现失败。
6. DS Bench 容器内 clean build、两 case 重建和 grader 均在已公开资源预算内完成。
7. Windows reference 与 Linux OSMesa candidate render 的后端差异不会使正确答案跌破阈值。
8. TASK 单独阅读即可了解输入、输出、评分边界、未观测区域规则和资源限制，不要求猜测 authoring 意图。
9. Starter 中不包含 private S1、hidden poses、reference/no-op frames、threshold 源文件或 grader 实现。
10. 正式阈值、case 数据和评分公式在官方 rollout 前被冻结并留有版本记录。

## 7. 建议执行顺序

近期只执行以下四项，避免同时改变过多变量:

1. 生成 1:1 Seed A 实验 case，并完成 coverage、资源和跨平台测量。
2. 根据实验结果冻结未观测 texel 的语义及 observation/hidden render size。
3. 发布独立 public dev oracle，并封闭 final score oracle。
4. 更新 starter 文档和测试，再进行 cold-agent rollout。

真实 SD dev case、额外 Spine 能力和更严格时间约束放在上述 V1 基线稳定之后。
