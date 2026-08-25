param(
    [Parameter(Mandatory = $true)]
    [string]$Renderer,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
[string[]]$forceArguments = @()
if ($Force) {
    $forceArguments += '--force'
}

foreach ($case in @('static_mesh_seed_a', 'static_mesh_seed_b')) {
    $spec = Join-Path $root "case_specs\$case.json"
    $caseRoot = Join-Path $root "generated\$case"

    & python (Join-Path $root 'generator\generate_pose_coverages.py') --spec $spec --renderer $Renderer @forceArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python (Join-Path $root 'generator\select_observations.py') --case-root $caseRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python (Join-Path $root 'generator\generate_skins.py') --case-root $caseRoot @forceArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & python (Join-Path $root 'generator\build_case_outputs.py') --case-root $caseRoot --renderer $Renderer @forceArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& python (Join-Path $root 'generator\package_exports.py') @forceArguments
exit $LASTEXITCODE
