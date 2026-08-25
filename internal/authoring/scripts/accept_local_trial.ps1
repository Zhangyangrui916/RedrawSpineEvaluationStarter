param(
    [Parameter(Mandatory = $true)]
    [string]$TrialRoot,
    [string]$Renderer,
    [string]$Output
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$authoringRoot = Split-Path -Parent $PSScriptRoot
$trial = (Resolve-Path -LiteralPath $TrialRoot).Path
$results = Join-Path $trial 'results'
$testFiles = Join-Path $authoringRoot 'generated\exports\test_files'
$grader = Join-Path $authoringRoot 'grader\grade_all.py'

if (-not (Test-Path -LiteralPath $results -PathType Container)) {
    throw "Trial results directory does not exist: $results"
}
if (-not (Test-Path -LiteralPath $testFiles -PathType Container)) {
    throw "Private test files are missing: $testFiles"
}

foreach ($caseId in @('static_mesh_seed_a', 'static_mesh_seed_b')) {
    $caseResults = Join-Path $results $caseId
    if (-not (Test-Path -LiteralPath $caseResults -PathType Container)) {
        throw "Missing result directory: $caseResults"
    }
    $expected = 0..19 | ForEach-Object { 'page_{0:D3}.png' -f $_ }
    $actual = @(Get-ChildItem -LiteralPath $caseResults -File -Filter '*.png' | Select-Object -ExpandProperty Name)
    $difference = @(Compare-Object -ReferenceObject $expected -DifferenceObject $actual)
    if ($difference.Count -ne 0) {
        throw "Output page set mismatch for ${caseId}: $($difference | Out-String)"
    }
}

function Import-VsDeveloperEnvironment {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $installation = $null
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $installation = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    }
    if (-not $installation) {
        $fallback = 'C:\Program Files\Microsoft Visual Studio\2022\Professional'
        if (Test-Path -LiteralPath $fallback -PathType Container) {
            $installation = $fallback
        }
    }
    if (-not $installation) {
        throw 'Visual Studio 2022 with the x64 C++ toolchain was not found.'
    }

    $devCmd = Join-Path $installation 'Common7\Tools\VsDevCmd.bat'
    $command = "call `"$devCmd`" -no_logo -arch=x64 -host_arch=x64 >nul && set"
    $lines = & $env:ComSpec /d /c $command
    if ($LASTEXITCODE -ne 0) {
        throw "VsDevCmd failed with exit code $LASTEXITCODE"
    }
    foreach ($line in $lines) {
        $separator = $line.IndexOf('=')
        if ($separator -gt 0) {
            [Environment]::SetEnvironmentVariable(
                $line.Substring(0, $separator),
                $line.Substring($separator + 1),
                'Process'
            )
        }
    }
    return $installation
}

if ($Renderer) {
    $rendererPath = (Resolve-Path -LiteralPath $Renderer).Path
} else {
    $build = Join-Path $authoringRoot 'build-local'
    $rendererPath = Join-Path $build 'trusted-render.exe'
    $installation = Import-VsDeveloperEnvironment
    $cmakeCommand = Get-Command cmake.exe -ErrorAction SilentlyContinue
    if ($cmakeCommand) {
        $cmakePath = $cmakeCommand.Source
    } else {
        $cmakePath = Join-Path $installation 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
        if (-not (Test-Path -LiteralPath $cmakePath -PathType Leaf)) {
            throw 'CMake was not found in PATH or the Visual Studio installation.'
        }
    }
    $ninjaPath = Join-Path $installation 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe'
    if (-not (Test-Path -LiteralPath $ninjaPath -PathType Leaf)) {
        throw "Visual Studio Ninja was not found: $ninjaPath"
    }

    if (-not (Test-Path -LiteralPath (Join-Path $build 'CMakeCache.txt') -PathType Leaf)) {
        & $cmakePath -S $authoringRoot -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_MAKE_PROGRAM=$ninjaPath"
        if ($LASTEXITCODE -ne 0) { throw "CMake configure failed with exit code $LASTEXITCODE" }
    }
    & $cmakePath --build $build -j2 --target trusted-render
    if ($LASTEXITCODE -ne 0) { throw "trusted-render build failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path -LiteralPath $rendererPath -PathType Leaf)) {
    throw "Trusted renderer does not exist: $rendererPath"
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
& $python -c 'import numpy, PIL'
if ($LASTEXITCODE -ne 0) {
    throw 'The active Python must provide NumPy and Pillow.'
}

if (-not $Output) {
    $Output = Join-Path (Split-Path -Parent $trial) 'acceptance_result.json'
}
$outputPath = [IO.Path]::GetFullPath($Output)

& $python $grader `
    --results-root $results `
    --test-files $testFiles `
    --renderer $rendererPath `
    --output $outputPath
if ($LASTEXITCODE -ne 0) {
    throw "Private grader failed with exit code $LASTEXITCODE"
}

$result = Get-Content -LiteralPath $outputPath -Raw | ConvertFrom-Json
Write-Host ("resolved={0} score={1:F6} reason={2}" -f $result.resolved, [double]$result.score, $result.reason)
Write-Host "result=$outputPath"
if (-not [bool]$result.resolved) {
    exit 1
}
exit 0
