# Continuous-Alpha Real-Art V2 Design Draft

状态: Run 12 public dev、Run 8 hidden pilot、matrix-free baseline、trusted support、private grader 和 starter V2
均已落地并通过 Windows native OpenGL 校准。剩余发布项是 Linux OSMesa acceptance 和 fresh cold-agent trial。

## 1. 目标

V2 使用真实 RedrawSpine 角色、真实 SD 重绘纹理和连续 alpha，测试多层 normal-alpha compositing 下的静态 attachment RGB 逆重建。

它不是 V1 的真实美术换皮版本，而是独立能力分支:

- V1: binary alpha，可靠 opaque fragment 可归属到单一 topmost page。
- V2: continuous alpha，一个屏幕像素可能联合约束多张 page 的多个 texel。

当前 V1 数据、阈值和 starter 不在本设计阶段修改。

## 2. 已确认的数据来源

- Source model: `C:/code/RedrawSpine/SpineProject`
- Spine: 4.2.68-beta
- 308 bones、209 slots、206 MeshAttachments、200 unique texture pages
- 4 IK constraints、7 transform constraints、deform timelines
- Normal blend，straight-alpha fake atlas，真实半透明 attachment alpha
- Original viewport: `1856 x 2288`
- Public development target candidate: SD Run 12
- Hidden target candidates: SD Run 8 and Run 11

Run 12、8、11 已使用归档的 10 张 SD pose frames 和原 `mask-analyzer.exe` 在隔离副本中重放。结果:

| Run | Archived pages exact SHA-256 matches | Different pixels |
|---|---:|---:|
| 8 | 50 / 50 | 0 |
| 11 | 49 / 50 | 287 |
| 12 | 50 / 50 | 0 |

Run 11 的差异只出现在 `L_arm_lace_02_add.png`，共 287 pixels，平均 RGBA 误差约 0.63/255。该差异相对完整 texture/frame 规模可忽略，不作为阈值或兼容性阻塞项。若以后采用 Run 11，generator 统一使用当前 replay output 并记录哈希即可。

## 3. Written/Flood 真值恢复

每个 run 保存:

- S0 pages
- 每帧重放后的 50 张 redraw page snapshots
- 每帧 `.writtenMask` snapshots
- 最终 50 张 redraw S1 pages
- 最终 written masks
- 完整 200-page S1 组装所需数据

最终统计:

| Run | Direct Written | Direct Written but exact white | Flood/propagated colored | Untouched white |
|---|---:|---:|---:|---:|
| 8 | 1,034,348 | 59,472 | 354,710 | 1,709,462 |
| 11 | 1,034,111 | 67,577 | 354,094 | 1,709,462 |
| 12 | 1,030,744 | 59,573 | 356,368 | 1,709,456 |

正式 target 组装不能再使用 `RGB != exact white` 作为唯一规则。已冻结规则:

```text
target_defined = final_written_mask == Written
              OR replayed RGB != exact white

S1.rgb = target_defined ? replayed RGB : S0 RGB
S1.alpha = S0.alpha
```

这同时保留 direct-written 纯白高光和可见 flood 结果。Flood/主观补全区域是否进入精确评分由 support policy 决定，不由 target 组装时删除。

Canonical alpha 0 RGB 固定为黑。Run 12 最终 mask 中 1,030,744 个 texel 状态为 Written；其中 981,928 个
alpha 非零并实际进入 RGB target。再加 356,368 个 propagated texel 后，Run 12 target-defined alpha-nonzero
texel 共 1,338,296。Run 8 对应数量为 983,810、354,710 和 1,338,520。

## 4. Continuous-Alpha Observation Operator

所有几何、draw order、tint 和 alpha 已知。只把 attachment RGB 视为未知量。

对像素 p，从下到上有 fragments `i = 0..n-1`。第 i 层:

```text
sample_rgb_i = tint_rgb_i * sum_t(bilinear_weight_i,t * texture_rgb_t)
sample_alpha_i = tint_alpha_i * bilinear(texture_alpha_i)
```

Normal straight-alpha compositing:

```text
frame_rgb_p = sum_i(
    sample_rgb_i
  * sample_alpha_i
  * product_{j > i}(1 - sample_alpha_j)
)
```

因为 alpha 全部已知，该式对 texture RGB 仍是线性的。定义:

```text
A * x = frame_rgb
```

使用 before/after 差分可消去 S0 与未变化 context:

```text
A * delta_texture_rgb = after_rgb - before_rgb
```

一个 row 可以同时包含多个 attachment page 的 texel 系数。V1 的 topmost-only 方程是本公式在 `sample_alpha_top == 1` 时的特例。

## 5. Baseline 求解与验证

V2 发布前必须实现至少一个不访问 S1 的 baseline:

1. 使用官方 Spine runtime 求 pose、deform 和 constraints。
2. 构建所有参与 normal-alpha blend 的 fragment 系数，而不是只保留 topmost。
3. 使用 `after - before` 作为观测值。
4. 对 RGB 三通道求解同一稀疏线性系统。
5. 允许 Laplacian/TV/多尺度正则，但必须保持静态 page 输出。
6. 对不可辨识 support 外区域不做 pixel-exact 承诺。

已实现 matrix-free forward/adjoint:

- Forward: 按 draw order 计算给定 texture delta 的屏幕 delta。
- Adjoint: 按反向 draw order 将 residual 乘已知 transmittance 和 bilinear weights 回传到 texture。
- Solver: 对角 energy 预条件的 CG on normal equations，ridge `1e-6`，20 iterations。

不显式存储完整 A；10 个 `1856 x 2288` observations 与多层 fragments 会产生过大的 sparse matrix。Windows
authoring 实测 20 轮约 133-137 秒，working set 约 0.75 GiB。

Operator correctness:

- Action@0.1 fragment samples: 1,864,441。
- `<Ax,y>` 与 `<x,A^Ty>` relative error: `3.05e-8`。
- 使用真实 S0/S1 delta 的整帧 linear prediction MAE: `0.0723/255`。
- Linear prediction RMS 相对真实 render delta: `0.672%`。

## 6. Identifiable Support: 已冻结

Continuous alpha 下，“texel 被某个 footprint 碰到”不等于“texel 可稳定求解”。建议基于 observation operator 的系数能量:

```text
energy_t = sum_p(A[p,t]^2)
```

评估过的候选方案:

### A. Nonzero coefficient support

只排除 `energy == 0` 的 texel。

- 优点: 规则简单，不隐藏阈值。
- 缺点: 极小系数和严重共线 texel 会被当成可稳定求解。

### B. Energy-threshold support（推荐 pilot）

根据 8-bit observation noise 和 baseline 条件数，冻结最小 `energy_t`。

- 优点: 能排除只以极弱 alpha/transmittance 参与的 texel。
- 缺点: 阈值必须通过正确 baseline 校准，不能主观指定。

### C. Render-space valid projection

不生成 texture mask，而在 hidden render 中仅评价能够由 public observation operator 稳定预测的像素子空间。

- 优点: 数学语义最完整。
- 缺点: 需要投影或低秩近似，authoring 和 grader 成本最高。

最终采用 B。Candidate 不提交评分 mask。

### 当前 energy 探针

Trusted renderer 已增加 `continuous-energy` 模式，按反向 draw order 累积:

```text
coefficient = transmittance_above * sampled_alpha * tint * bilinear_weight
energy_t += coefficient^2
```

Run 12 的 10 个 public observations 聚合结果:

- Fragment samples: 18,525,680
- 200 pages 中 alpha-nonzero texel 的 nonzero-energy fraction: 47.4%
- Direct-written texel 中 97.6% 具有 nonzero energy
- Flood/propagated colored texel 中 91.2% 具有 nonzero energy，但大量能量极小

不同绝对 energy threshold 的保留率:

| Threshold | Direct Written | Flood/Propagated | Untouched White |
|---:|---:|---:|---:|
| `> 0` | 97.63% | 91.20% | 0.0007% |
| `> 1e-6` | 97.56% | 62.43% | 0.0007% |
| `> 1e-4` | 96.96% | 20.32% | 0.0007% |
| `> 1e-2` | 95.07% | 16.99% | 0.0004% |
| `> 1e-1` | 93.04% | 13.62% | 0.0003% |

绝对 threshold 冻结为 `energy >= 1e-4`，并要求 S0 alpha 非零。Run 8 private support 覆盖 1,604,189 / 
4,685,761 alpha-nonzero texels，即 `34.2354%`。Run 12 正确 baseline 的 threshold sweep 在 `1e-6` 到 `1e-2`
之间均得分 `0.9729-0.9744`，因此通过不依赖精调阈值。

单 texel 有限差分校验:

- Page: `R_arm_02_cloth_01.png`
- Texel: `(158, 489)`，red channel `+64/255`
- Predicted coefficient energy: 0.9973
- Measured RGBA8 render energy: 0.9788
- Relative difference: 1.86%

有限差分误差足够用于 support 排序；正式 forward/adjoint dot-product test 已按第 5 节完成。

## 7. Support 外中性化

Real-art S1 在 public support 外可能包含 flood/inpainting，不能恢复为 S0。Private grader 需要保存 target S1 pages:

```text
candidate_eval = support 内 candidate，support 外 private S1
noop_eval      = support 内 S0，support 外 private S1
reference      = private S1
```

然后使用 `noop_eval` 重新归一化。Candidate 原始 pages 另行渲染为 completion preview，但 flood/inpainting 美术效果不进入 resolved pixel threshold。

## 8. Frozen Case Split

### Public Dev

- `real_art_continuous_dev_run12`
- 公开 S0、observations、S1、validation、aggregate operator-energy diagnostics
- 允许反复调试

### Hidden Pilot

- `real_art_continuous_run8`
- 不公开 S1、support、hidden poses 或 score oracle
- Run 11 暂不采用

## 9. 发布 Gate 校准结果

必须达到:

| Baseline | Run 12 public | Run 8 hidden | Result at 0.9 |
|---|---:|---:|---|
| Reference S1 | 1.0000 | 1.0000 | Pass |
| Correct continuous-alpha PCG | 0.97384 | 0.97911 | Pass |
| Single-observation PCG | 0.82827 | 0.81565 | Fail |
| Claude topmost/binary-alpha LS | 0.60785 | not reused across target | Fail |
| No-op S0 | approximately 0 | `3.7e-11` | Fail |

Resolved threshold 冻结为 `0.9`。starter `v2` 已替换为独立 Run 8 final case，并包含 Run 12 public dev oracle。

## 10. 剩余发布事项

1. 在 Linux OSMesa 环境重建 trusted renderer，运行 Reference/Correct/Single/No-op acceptance。
2. 从 starter `v2` 干净副本启动 fresh cold agent，收集任务清晰度与缺失信息反馈。
3. 根据 Linux acceptance artifact 打 DS Bench private archive；不再改 support/score threshold，除非出现可复现的跨平台错误。
