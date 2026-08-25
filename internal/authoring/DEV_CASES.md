# Public Development Cases

The generated public development fixtures expose their target pages and validation references on purpose. They are
calibration oracles, not final benchmark instances, so they do not require an isolated scoring service.

## synthetic_dev

Location: `generated/dev_cases/synthetic_dev`

- Uses the final V1 static-mesh capability family.
- Uses `2450 x 1900` observations, approximately one framebuffer pixel per world unit.
- Uses the high-dimensional seeded `band_limited_v2` S1 field with smooth 48-256 texel wavelength rolloffs. S0 keeps
  the existing low-information repeated field.
- Contains 6 observations, 20 output pages, 10 public validation poses, and a fully public procedural S1.
- Package size is about 23.2 MiB.
- Verified baselines after the generator update: Reference `1.0`, No-op approximately `0`, revised Claude LS `0.9972`
  in 13.5 seconds on the latest Windows run.

Rebuild:

```powershell
python generator/generate_pose_coverages.py `
  --spec dev_specs/synthetic_dev.json `
  --renderer C:/tmp/redrawspine-authoring-build/Release/trusted-render.exe `
  --force
python generator/select_observations.py --case-root generated/synthetic_dev
python generator/generate_skins.py --case-root generated/synthetic_dev --force
python generator/build_case_outputs.py `
  --case-root generated/synthetic_dev `
  --renderer C:/tmp/redrawspine-authoring-build/Release/trusted-render.exe `
  --force
python generator/package_public_dev.py `
  --case-root generated/synthetic_dev `
  --output generated/dev_cases/synthetic_dev `
  --force
```

## real_art_dev

Location: `generated/dev_cases/real_art_dev`

- Built from the archived RedrawSpine production asset and SD run 12 without rerunning SD.
- Preserves 308 bones, 209 slots, weighted meshes, deform timelines, 4 IK constraints, 7 transform constraints, and
  real semitransparent alpha.
- Contains 200 unique output pages referenced by 206 MeshAttachments. Fifty pages contain archived redraw pixels and
  150 pages have S1 equal to S0.
- Removes three non-rendering PointAttachments during normalization.
- Contains 10 observations at the original `1856 x 2288` viewport resolution and 12 public validation poses.
- Includes the 10 archived raw SD pose frames for production context, explicitly excluded from equation truth.
- Package size is about 140 MB after including the raw SD references.
- Unmasked full-frame baselines: Reference `1.0`, No-op approximately `0`, revised Claude LS `0.6123`,
  nearest+fill `0.6019`.
- Diagnostic scores: revised Claude LS `0.9907` on the conservative support it accepts itself, and about `0.6442`
  when normalized over the larger independent trusted reliable coverage.

The low unmasked scores are not evidence that the solver failed on observable SD detail. The original production
pipeline floods color through connected opaque texture regions, including texels that no public observation directly
samples. In this fixture, 34.8% of archived written/flood texels fall outside the independent trusted reliable coverage;
54.9% fall outside the more conservative Claude mask. Claude uses only 62.9% of trusted coverage because its final-V1
binary-alpha assumptions reject much of the real semitransparent support. A scorer must neutralize or mask the region
outside trusted coverage before interpreting reconstruction quality. Flood quality may be inspected visually, but it
is not an identifiable pixel-exact target and is not a resolved gate.

Rebuild:

```powershell
python generator/build_real_art_dev.py `
  --redraw-root C:/code/RedrawSpine `
  --run 12 `
  --renderer C:/tmp/redrawspine-authoring-build/Release/trusted-render.exe `
  --output generated/dev_cases/real_art_dev `
  --force
```

## Oracle use

Develop from `case.json`, `source_attachments/`, and `observations/`. Inspect `oracle/target_attachments/` and
`oracle/validation/` afterward. Exact page equality is not required when the inverse is underdetermined; render-space
behavior is the primary diagnostic.

Final benchmark cases use different target seeds or assets and do not expose S1, reference frames, or an iterative
final-score oracle. Hardcoding or copying a public dev target therefore cannot solve a final case.
