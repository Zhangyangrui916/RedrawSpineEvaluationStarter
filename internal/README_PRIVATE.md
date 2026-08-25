# Private V2 Authoring Archive

This directory is not candidate-visible task material. It contains the V2 generator, trusted renderer, private grader
source, design history, calibration reports, and reproducible packaging scripts. Keep the public `v2` starter branch
free of this directory.

Do not push this archive to a public remote while the benchmark or hidden Run 8 target remains usable. The complete
private target/support package and upload-ready DS Bench parts remain external artifacts referenced by hash in
`ARCHIVE_MANIFEST.md`.

Build the standalone authoring tools with:

```bash
cmake -S internal/authoring -B ../redrawspine-authoring-build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build ../redrawspine-authoring-build -j2
```
