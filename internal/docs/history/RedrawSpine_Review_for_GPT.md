# RedrawSpine Code Agent 评测方案 · 评审与修订说明（v1 → v2）

> **这份文档是什么**：对《RedrawSpine Code Agent 评测设计与实现细则 V1》的技术评审。
> v1 写作时缺失三类关键信息：① 笔试题原文的确切要求；② DSBenchV2 平台的真实约束；③ 评测容器的实测规格。
> 这三类信息现已获取，其中若干条**推翻了 v1 的基础假设**。
> **请据本文档产出 v2。** 文末第 9 节列出了 v1 中判断正确、必须原样保留的部分，请勿改动。

---

## 1. 需要先对齐的事实

### 1.1 笔试题原文（决定交付物形态）

> **第一问**：请基于你个人的真实使用经历，选取一个具体的编程任务场景，分别说明 DeepSeek 和其他任意 3 个模型（最好包含 opus）在该场景下的优劣，**不超过 1000 字**。要求：
> - 详细记录各模型/产品的任务完成状态（成功、部分完成或失败，及具体表现）
> - 给出明确的性能优劣排序并阐明排序原因
> - 如果模型变强了，如何调整在该场景下的评测
>
> **第二问**：请参考任务手册，将上述例子构造 Code Agent 测试样例，以展现你对数据工作的理解，并**简要**阐述你是如何将上述例子抽象成标注平台上的一个例子。

### 1.2 DSBenchV2 平台真实约束

| 项目 | 事实 | 对 v1 的影响 |
|---|---|---|
| **被测模型** | **仅 deepseek-v4-flash 与 deepseek-v4-pro**（可配 thinking / reasoning effort） | §12 的「DeepSeek / Claude Opus / Codex / Gemini」四模型表**在平台上无法执行** |
| 打分附件 `/test_files` | **500 个文件 / 500MB**（手册正文写"小于1MB"，已被 UI 与实测证伪，以 UI 为准） | §11.2 的布局体积上可行 |
| 打分脚本 | 平台执行 `cd /eval && python3 test_by_code.py`；可读 `/workspace/`（rollout 产物）与 `/test_files/`（只读） | v1 §6.1 正确 |
| 结果文件 | `/eval/code_result.json`，**有且仅有** `resolved`(bool) / `score`(float 0~1) / `reason`(str) | v1 §6.7 正确 |
| 上下文 | 只能"无上下文"，Prompt 必须单轮自包含，模型看不到前文 | v1 §5.1 符合 |
| 网络 | **可开可关**。rollout 与打分各有独立的「网络配置」开关，勾选"外网"即可联通（"内网镜像站"按钮无效），平台两处均注明"不推荐打开"。阶段一的 SnapCode 准备容器本身有网（手册 1.2 明写支持 github/huggingface 下载）。容器内不可调用任何 LLM/内部 API | 见 1.4 第 4 条：网络是**主动关闭的设计选择**，不是平台限制 |
| 快照机制 | 每轮 CC 对话结束后存档；测试时恢复的是**被测轮次的前一轮**快照；第一轮不可选 | v1 §11.1 步骤 4 正确 |
| Agent Grade | 平台明示不稳定，不推荐 | v1 用 Code Grade，正确 |
| 容器时效 | 2 小时失效，可 Resume；Resume 后旧 session 无法再产快照 | 执行层注意事项 |

### 1.3 评测容器实测规格

```
CPU     : AMD EPYC 9K65（KVM 虚拟机），x86_64，AVX-512
          在线核心 2 个（2-7 离线）
GPU     : 无。无 nvidia-smi，lspci 查不到任何 VGA/3D 设备，无 CUDA
内存    : 30 GiB（可用 ~28 GiB），无 Swap
磁盘    : 979 G（可用 956 G），overlay
OS      : Debian GNU/Linux 13 (trixie)，kernel 6.14
运行时  : Python 3.12.13 / Node.js v22.17.0
图形栈  : 默认完全没有。无 libGL / libEGL / libOSMesa / libGLX / Mesa / DRI / X11 / Vulkan
          但 apt 可用，可安装 libosmesa6 / libegl1 / libgl1-mesa-dri（Mesa 25.0.7，llvmpipe）
```

### 1.4 由 1.2 / 1.3 直接得到的四条结论

1. **§12 的四模型对比必须移出平台**，在本地用自有 API key 执行（见第 6 节双轨设计）。
2. **`/test_files` 体积不再是约束**，但"grader 不能链接候选改过的 runtime"这条约束不变——**可信 oracle 仍必须自研，且必须与候选异构**。
3. **OpenGL 可用但需自行安装**；由于 llvmpipe 本身就是 CPU 软件光栅器，在 2 核机器上用 GL **换不到任何性能**。结论是：**不要求、不禁止、但在快照里预装好**；starter 的默认构建路径**不应硬依赖 GL**，否则一次 GL 初始化失败就会让整个 rollout 归零。
4. **网络分阶段处理：准备阶段开，rollout 与打分阶段关。** 这是主动的设计选择，v2 中应当把理由写出来，而不是默认关掉不解释。

   | 阶段 | 网络 | 用途 |
   |---|---|---|
   | 阶段一 SnapCode 准备环境 | **开** | `apt install` Mesa、拉取 spine-cpp、pip 装依赖 → 全部烘进快照 |
   | Rollout（被测模型作答） | **关** | 起点已是装好依赖的快照，不需要网 |
   | 打分 | **关** | 每次重新打分都联网 = 每次都多一个失败点，且网络故障与模型失败无法区分 |

   关闭 rollout 网络的三条理由，按重要性排序：
   - **泄题风险**：RedrawSpine 若在 GitHub 公开，联网模型可直接检索到参考实现（尤其是 `uv_redraw.glsl.inc` 中 attachment ID + texel index 的整数编码，正是本题核心答案）。即便仓库私有，通用检索也可能命中足够多的解题思路。
   - **可复现性**：Track 1（平台）与 Track 2（本地）的 apt 源、pip 版本、GitHub 状态不一致，跨模型与跨时间的比较会失真。这一条对第 6 节的双轨设计是硬性前提。
   - **方差**：单模型样本量只有 3~6，一次 rollout 搜到关键资料、另一次没搜到，这个差异会被误记为模型能力差异，直接吃掉通过率信号。

   **需要在 v2 中如实写明的权衡**：开网会额外测到一项真实的 agentic 能力——"是否会主动查找官方文档与 runtime"。这项能力有价值，但与"可复现地给模型排序"冲突；本次目标是后者，故选择关闭。把这句话写出来，比默认关掉不解释更能体现判断。

   > 附带澄清：曾有"用网络在打分脚本里 `git clone` 以绕过附件体积上限"的想法。**上限是 500 文件 / 500MB，而本方案的隐藏数据量级仅数十 MB，不存在需要绕过的约束**；为一个不存在的限制引入上述三类风险不划算。

---

## 2. P0 — 会让评测失效的问题

### P0-1【最严重】"S1 平滑度"与"off-by-one 判别力"在数学上是同一个量

v1 §4.4 的生成器质量检查要求：**相邻 opaque texel 的最大通道差 P99 ≤ 4~8**，理由是降低采样假阴性。

但"相邻 texel 的通道差"**就是**"UV 偏移 1 texel 所产生的误差"——两者是同一个离散梯度。压低它，等于同时压死 v1 §8.1 中 `Flip-Y / off-by-one` 和 `Nearest sampling` 两个 mutant 的可分性。

用 v1 §6.4 自己的公式代入：

| 量 | 估值 | 说明 |
|---|---|---|
| `D_source` | ≈ 0.157 | S0 平坦色 vs S1 在 [16,239]，平均通道差按 40/255 估 |
| `D_ref` | ≈ 0.004 | 参考实现的误差地板 |
| `D(off-by-1)` | 0.0157 ~ 0.0314 | **即 P99 邻域差本身**，4/255 ~ 8/255 |

```
Q = clip( (D_source - D_candidate) / (D_source - D_ref + eps), 0, 1 )

P99 = 4/255  ->  Q = (0.157 - 0.0157) / (0.157 - 0.004) = 0.92
P99 = 8/255  ->  Q = (0.157 - 0.0314) / (0.157 - 0.004) = 0.82
```

**结论：一个 texel index 差 1 的错误实现会拿到 0.82~0.92 分，越过（或紧贴）v1 §6.5 设定的 0.85 resolved 门槛，被判为"通过"。** off-by-2 约 0.85，仍在边界。Nearest sampling 误差更小（约半个 texel 步长），Q ≈ 0.95+。

这直接推翻 v1 §8.1 对这两个 mutant 的预期（"所有 case 低分"、"sampling 最明显"）。Flip-Y 因为是全局翻转仍能正常挂掉——也就是说，**当前设计只能测出灾难级错误，测不出任何精度级错误**，而精度恰恰是 v1 §7 单列一行 `Sampling` 想测的东西。

结合 1.2 中平台"低通过率最值钱"的偏好，这条会把通过率推向最不理想的一档，**必须优先修**。

**修法（不是折中，是换轴解决）**

真正的假阴性来源不是 texel 级梯度，而是**亚 texel 级配准歧义**（像素中心 vs texel 中心、clamp 模式、viewport→NDC 公式）。正确实现的亚 texel 误差应当接近 0。因此只要把渲染约定钉死（见 P0-5），就不需要靠"压平 S1"来买容错。具体：

1. **把 S1 从"低通"改成"带通"**：sub-texel 尺度无能量（不超 Nyquist，对双线性友好），但在 **4~16 texel 波段保留足够振幅**，使 1 texel 位移显著去相关。v1 §4.4 的公式形式可保留，但频率必须按 texel 数归一化并显式落在该波段。
2. **把生成器验收指标从"平滑度目标"改成"判别力目标"**，并在生成的数据上实测：
   ```
   D(shift = 1 texel)      >= 0.03
   D(shift = 2 texel)      >= 0.06
   D(swap attachment)      >= 0.5 * D_source
   D(nearest vs bilinear)  >= 0.015
   ```
   §4.4 现有的"P99 邻域差 ≤ 4~8"一行应当**删除或反转**。
3. 若最终决定保留低梯度 S1，则必须承认 sampling case 不成立，**从 §7 测试矩阵中删掉这一行**，不要保留一个测不到的维度。

### P0-2 主指标建议从 mean L1 改为"坏像素率"

映射类错误的像素误差分布是**双峰**的：映射对了 ≈ 0，映射错了 ≈ 大。`mean L1` 会把两峰平均掉，且高度依赖 S1 的颜色动态范围（一个由出题人任意设定的量）。建议：

```
bad_rate_f = |{ p in valid_f : L1(pred_p, target_p) > tau }| / |valid_f|
tau ~ 12/255
frame_quality = 1 - bad_rate_f
```

理由：
- **语义可解释**——"这一帧有 7% 的像素画错了"，直接对应平台要求 `score` 反映"做到了什么程度"。
- **对 S1 的对比度不敏感**，跨 case 天然可比。
- **误差分级符合能力排序**：错到邻近 texel 记轻，错到别的 attachment 记重。

`mean L1` 保留在 `reason` 里做诊断。

另外，v1 §6.4 的归一化分母 `D_source - D_ref` 是由出数据的人任意设定的尺度，两个难度相同的 case 可以有完全不同的分母，导致 §6.5 的 `mean(core_case_quality)` 在平均单位不一致的量。**改用 bad_rate 后这一层归一化可以直接去掉。**

### P0-3 时间预算进了 resolved 硬门槛，却从未写进 Prompt

§6.5 的 `resolved` 要求 `runtime_within_budget`，§11.3 出现 `timeout=120`，§2.4 把"性能预算"列为能力维度——但 §5.1 的 Prompt 中**一个字都没提**。这是纯粹的不公平：候选写了一个 5 分钟的最小二乘求解器被超时判死，而它从来不知道存在预算。

**修法**：在 Prompt 中明写"构建 + 单 case 重建的总耗时预算 ≤ N 秒"；或把它从 resolved 门槛降级为 `reason` 中的记录项。二选一，不能两头都留。**在 2 核机器上这条尤其重要**：候选需要 CMake + 编译 spine-cpp，2 核 -O2 大约 60~120 秒。建议**在快照中预编译 spine-cpp 静态库**，只留候选自己的编译单元，可省一半构建时间并减少构建 flake。

> **一般性原则，建议写进 v2**：**隐藏测试可以隐藏"实例"，绝不能隐藏"要求"。**
> §5.1 第 2 条"支持题目要求的 RegionAttachment 与 MeshAttachment"中的"题目要求的"是未定义的。若 hidden case 含 deform timeline 而 public case 没有，候选合理地只做了 Region + 静态 Mesh 却被扣分——此时测到的是"猜没猜中出题意图"，不是能力，且会显著增加 rollout 间的方差。应当**直接列出 hidden case 可能出现的特性清单**（Region / Mesh / deform / draw order 变化 / 非方形贴图 / viewport 是否变化），只是不给具体数据。

### P0-4 attachment PNG → atlas page 的重打包契约缺失

候选输出的是 `source_attachments/*.png`，而 renderer 采样的是 atlas page 纹理。两者之间隔着打包过程（旋转、去白边、padding、offset）。v1 全文未说明 grader 如何从候选 PNG 重建 page，而 §4.1 又预留了 `hidden_atlas_optional`（多 page / rotated region）。

**修法**：V1 明确规定 **一个 attachment 一个 atlas page，无旋转、无裁剪、无 padding**，于是 attachment PNG ≡ page 纹理，整个歧义消失（§5.2 的"宽高与 source 一致"其实已隐含这一点，只是没说破）。多 page / rotation 明确推到 L2，并在那时写出重打包规则。由于 atlas 由生成器自己产出，这条修改零成本。

### P0-5 渲染约定必须成文（这是最大的假阴性来源）

v1 说"不测试复杂 PMA 差异"——但 PMA 不是复杂度维度，是一个必须钉死的开关。同样完全没提的还有 **sRGB / gamma**。如果 oracle 在 sRGB framebuffer 下渲染而候选没有，候选可以几何全对、颜色系统性偏移、直接 0 分。这一整类风险在 §13 风险表里缺席。

**修法**：增加一个「参考渲染约定附录」，作为**文字规格**随任务发出（这是约定不是答案，公开它只降噪、不降难度）。至少需要写明：

- 非 PMA，直接 alpha 混合，normal blend，白色 tint
- 无 sRGB / gamma 转换，8bit 原始写出
- 纹理坐标原点与 Y 轴方向
- 屏幕像素中心为 `(x+0.5, y+0.5)`，texel 中心同理
- 过滤：bilinear；wrap：clamp-to-edge
- viewport → NDC 的确切公式
- 三角形填充规则（top-left rule 或等价说明）

---

## 3. P1 — 应该修

| # | 问题 | 修法 |
|---|---|---|
| 1 | **`structural_quality` 占 §6.5 中 10% 权重，但全文没有定义** | 给出定义表，明确它由 §5.2 CLI 合同的哪几项组成；同时注意 `alpha_exact` 既是 resolved 硬门槛又疑似计入 structural，存在重复计分 |
| 2 | **§2.4「核心能力维度」中有一半是自动 grader 无法验证的** | 候选完全可以自己解析 `skeleton.json`、用自写代码实现 Spine 变换、绕开 spine-cpp，而 render-space grader 察觉不到（这甚至是个不错的解）。给该表**加一列「是否自动可验证 / 仅人工复核」**，把"希望激发的能力"与"真正被验证的信号"分开。这个区分本身是有价值的评测设计观点，值得在 v2 中显式论述 |
| 3 | **§8.3 的顺序鲁棒性检查 + `Order-dependent last-write` mutant 在当前设计下不可分** | S1 固定且一致，last-write-wins 无论什么顺序结果几乎相同。要让它有效，必须**刻意让 observation 的屏幕尺度跨度拉大（如 0.4x ~ 3.0x）**，使"该用哪个观察写这个 texel"真的有优劣。顺带说明：这也是唯一能把"按采样质量加权融合"和"随便覆盖"区分开的机制——当前设计里"多观察融合"实质上只考了"取并集"，难度偏低 |
| 4 | **`viewer.cpp` 的能力边界是整个题目的难度总开关，但只用一句"仅能加载并显示/离屏渲染默认动画"带过**（"显示 / 离屏"二选一含义完全不同） | 必须钉死。若已含 FBO + readback，题目是"会不会逆映射"；若只开窗口，题目是"会不会搭离屏渲染 + 逆映射"。并把它显式写成 L0/L1/L2 的难度旋钮 |
| 5 | **缺少"图像配准绕过 spine-cpp"这条攻击面** | 候选手里有 S0 原图 + before.png，对 RegionAttachment 而言变换是纯仿射，直接做图像配准估计仿射矩阵、再套到 after.png 上即可完成重建，全程不碰 Spine。v1 §4.3 要求 S0 低信息量恰好让配准病态——这是个**意外的正确防御，应当写明是有意为之**。真正的防线是 Mesh + deform（非仿射、逐帧变化）。建议加入 §13 风险表 |
| 6 | **`before.png` 是自校准锚点，v1 完全没有点出，应升为核心设计点** | 候选看不到 oracle 源码，唯一能验证自己渲染器是否与 oracle 一致的手段就是"用 S0 渲染，逐像素对比 before.png"。这既是最重要的可解性保障，也是最好的**过程信号**。建议：① v2 中明确写出这个设计意图；② **Prompt 中不提示**，把"是否用 before.png 自校验"记录为过程指标——这是区分"会自验证的 agent"和"一把梭"的极好维度 |
| 7 | **阈值冻结顺序需要写成流程** | §8.2 把"至少一类中低模型能偶尔通过"放进了校准标准，这是在测试集上调参。应明确：① 建 grader → ② 跑 mutant → ③ **仅凭 mutant 冻结阈值** → ④ 跑模型 → ⑤ 阈值不再动。若难度不合适，改的是**数据**不是阈值，且改完后全部模型重跑 |
| 8 | **统计力需要如实说明** | 平台建议 batch 3~6。n=5 的二项置信区间约 ±40%，只能分辨大差距。区分度应主要来自 flash / pro / pro+thinking 三档的**通过率梯度**，而非单模型的重复次数。建议报告 Wilson 区间，区间重叠时并列，不强行排序 |

---

## 4. P2 — 打磨清单

- §11.2 标题是"阶段三"，但文档中不存在"阶段二"，编号断裂。
- `Q_case` 公式中的 `eps` 未定义；`score` 的取值域未声明（平台要求 0.0~1.0）。
- §6.5 的 `worst_10_percent_frame_quality`：同一 case 内各帧高度相关（同一套皮肤），信息量小。改成 **worst-per-attachment** 或 **worst-per-能力分支**，更能抓住"mesh 全错但 region 全对"这种真实失败形态。
- 全文未写明**每个 case 有多少个 observation**——这是覆盖率与成本的主要旋钮，应进 §4.1 的表。
- hidden case 的 viewport 是否与 public 相同需要明示。建议**不同**（能测出硬编码 256×256），但必须写进特性清单（见 P0-3 的一般性原则）。
- §4.4 的颜色场公式中，正弦项频率应按 texel 数归一化，使其与贴图分辨率无关。
- 平台要求"尽量不要让模型在对话中汇报结果，而要产出指定文件"——v1 的 CLI 合同符合，可在 v2 中引用该条作为设计依据。

---

## 5. 架构修订建议

### 5.1 可信 oracle：纯 Python + numpy，与候选异构

无论 `/test_files` 上限是多少，"grader 不能链接候选改过的 runtime"这条约束都要求存在一个独立可信渲染器；而**参考帧本来就得有人渲**。因此这个渲染器是必做项，不是可选项。建议用纯 Python + numpy 实现 Spine 的一个受限子集：

```
minirender.py   # JSON -> bone world transform -> Region/Mesh -> draw order
                # -> 三角形光栅 + 双线性采样；同时提供 ID/UV pass
genfix.py       # seed -> skeleton.json / atlas / S0 / S1 / pose 采样 / observations
grade.py        # 指标、聚合、写 /eval/code_result.json
seeds.json      # 每个 hidden case 的 seed 与参数
```

由于 500MB 上限充裕，**建议参考帧与 eval map 在出题阶段预计算好并上传**（grader 更简单、更快、更稳），生成器脚本一并放入 `/test_files` 作为**原创性凭证**与快速改难度的工具。

**这套东西同时解决四个问题**：grader 与候选彻底隔离（异构语言、异构实现）；S1 从不落到 `/workspace`；生成器与渲染器 100% 原创，是应对平台查重最强的证据形式；改一行 `seeds.json` 就能加 case。

### 5.2 OpenGL 的定位

**不要求、不禁止、但在阶段一快照里预装好**（`libosmesa6` / `libegl1` / `libgl1-mesa-dri`）。理由：llvmpipe 本身是 CPU 光栅器，GL 在这台机器上换不到性能；但预装可以让想走 GL 路线的候选不被环境卡住。**starter 的默认构建路径不应硬依赖 GL**，保证 GL 初始化失败不会让整题归零。这与 v1 §2.3「实现方式不限」的立场一致，只需把环境准备说清楚。

### 5.3 `test_by_code.py` 骨架

```python
# cd /eval && python3 test_by_code.py
# 可读 /workspace/（rollout 产物）与 /test_files/（只读）
# 必须写 /eval/code_result.json，且仅含 resolved / score / reason

build_candidate("/workspace")                       # 超时保护
for case in hidden_cases:                           # 从 /test_files 解压到 /tmp/eval_case
    out = run_candidate(case, timeout=T)            # 调用 CLI，不写回 /workspace
    structural = validate_outputs(case, out)        # 文件名/尺寸/格式/alpha/退出码
    visual     = evaluate_hidden_frames(case, out)  # 用 minirender 渲隐藏 pose，算 bad_rate
score, resolved, reason = aggregate(...)
write_json("/eval/code_result.json", {...})         # 详细指标走 stdout，不加字段
```

---

## 6. 交付物拆分与双轨实验（v1 最大的结构性问题）

### 6.1 两个交付物必须分开

| | **交付物 A（≤1000 字）** | **交付物 B（平台测例）** |
|---|---|---|
| 要求 | 真实使用经历、DeepSeek + 3 个模型（含 Opus）、完成状态、明确排序及理由、模型变强后怎么调 | 参考手册构造一个 Code Agent 测例 + **简要**阐述抽象过程 |
| 执行地点 | **本地**（平台只有 DeepSeek） | DSBenchV2 平台 |
| v1 现状 | §12 是一张**空表** | §1~§11、§13~§15，严重过量 |

v1 §14（模型变强后的升级路线）质量很好，正好对应第一问的第三小问，可直接压缩进 1000 字。

### 6.2 双轨实验：测例只造一次，在两个地方跑

| | Track 1 · 平台 | Track 2 · 本地 |
|---|---|---|
| 被测 | deepseek-v4-flash / v4-pro / pro+thinking | Claude Opus / Codex / Gemini / DeepSeek API |
| starter + Prompt | 同一份 | **完全相同** |
| 打分 | `test_by_code.py` | **同一份脚本，本地直接跑** |
| 产出 | 手册要求的测例 + 通过率梯度（证明有区分度） | 第一问要求的四模型对比 |

**关键点是两边共用同一个 grader。** 这样第一问的"明确排序及排序原因"就不是回忆，而是四个模型在同一自动评分器下的实测分数 + 各自具体的失败分支——JD 原话要求的"可复核的依据"。

这同时把"平台只有 DeepSeek"从一个抱怨变成一个**主动处理过的约束**，可以直接写进文档：*平台侧只能覆盖 DeepSeek 家族，因此我把测例做成了平台外可复现的形式（starter + prompt + 独立 grader 三件套），用同一评分口径补齐跨厂商对比。*

第三小问"模型变强了怎么调"也随之有了实证基础：观察到 Opus 在哪一档饱和、DS 在哪一档挂掉，下一档该加 mesh 还是加 coverage 就是观测出来的，而不是想出来的。

**成本增量很小**：真正的工作量是 grader + 生成器（必做项），Track 2 只是在本地多跑一遍；Track 1 大约三到四小时。

---

## 7. 执行计划（约 3 天）与最大技术风险

**Day 1 — 先解决判别力问题（全局前提）**
- 写 `minirender.py` 与 `genfix.py`。
- **当天验收目标是一组数字而非代码量**：在生成数据上实测 no-op / single-pose / shift-1 / shift-2 / nearest / flip-Y / region-only 各拿多少分，把颜色场从"低通"调成"带通"，直到 P0-1 中列出的分离度指标达标。

**Day 2 — starter + grader + 上平台**
- C++17 / CMake / spine-cpp / CPU 光栅 viewer / `reconstruct.cpp` 留 TODO / 公开 case / smoke test。
- `test_by_code.py`，先用 no-op 与参考解验证 grader 本身，再跑模型。
- 阶段一上传与快照 → 阶段二选轮次 → 阶段三 rollout + 打分。

**Day 3 — Track 2 + 写作**
- 本地四模型各 3 次，同一 grader 打分。
- 写 1000 字（含真实失败分支），把设计文档压成附录。

**难度旋钮（按影响力排序，看到实际通过率后据此调整）**：① starter 里的渲染器给到什么程度（最大的一档）→ ② 有无 Mesh / deform → ③ observation 数量与覆盖率 → ④ 约定规格公开到什么粒度 → ⑤ resolved 阈值。**永远优先调前三个，最后才动阈值，且阈值一旦跑过模型就冻结。**

**最大技术风险**：Python oracle 必须与真实 spine-cpp **逐像素对齐**，否则所有候选都会吃系统性假阴性。
缓解：把 fixture 限制在语义无歧义的子集——只有 translate / rotate / scale 的骨骼、线性插值、无 IK / path / 任何 constraint、无特殊 transform inherit 模式。**Day 1 的收工标准是：用真实 spine-cpp 渲一帧，与 `minirender.py` 逐像素比对通过。**


---

## 8. v1 中判断正确、请原样保留的部分

以下是 v1 做对的、且是这类评测最容易被做错的地方，**v2 修订时请勿改动**：

1. **主评分放在 render space**，而不是要求候选 PNG 与 S1 逐 texel 相等（§6.2 末尾、§9 问答）。
2. **grader 与候选代码彻底隔离**，只消费最终 attachment PNG（§3.4、§6.2）。
3. **先用 mutant 校准 grader，再跑模型**；参考实现只用于定义误差地板而非唯一正确解（§8、§13.1）。
4. **固定隐藏目标皮肤 S1 提供唯一真值**，并由此推出 observations 无顺序语义（§2.1、§2.2）。
5. **S0 必须低信息量**，不能让 texel 颜色成为隐式 UV 编码（§4.3）——并且它顺带防住了图像配准绕过（见 P1-5）。
6. **二值 alpha 先隔离几何/UV 能力**，把半透明与复杂 blend 作为独立升级项（§4.5）。
7. **不按 attachment 大小等权**，能力差异通过独立 case 表达（§6.6）。
8. **数据生成器优化的是 coverage 而非 sequence**（§4.6）。
9. **可解性保证**：评分区域必须在至少一个 observation 中被充分观察（§2.3、§4.6）。
   > 补充一条 v1 遗漏的检查：由于双线性 footprint 覆盖 4 个 texel，任一 texel 未被观察即需排除，`valid_mask` 可能被侵蚀得很厉害。应增加"每个隐藏帧的 valid 像素占角色不透明面积的比例 ≥ X%"这一条生成器验收项，否则该帧的误差统计噪声过大。
10. **§10 的原工程 vs V1 差异表**、**§9 的面试问答**、**§14 的升级路线**——这三部分是 v1 最有价值的内容，压缩后应完整保留。

---

## 附：已作废的早期意见（避免混淆）

以下是评审过程中提出、后经查证**不成立或已被推翻**的意见，v2 中不必处理：

- ~~`/test_files` 限 1MB，必须改为种子化现场生成~~ → 实际上限 500 文件 / 500MB，手册正文有误。
- ~~容器无法运行 OpenGL，V1 应完全砍掉 GL~~ → apt 可装 Mesa/OSMesa（llvmpipe），改为"不要求、不禁止、预装好"。
