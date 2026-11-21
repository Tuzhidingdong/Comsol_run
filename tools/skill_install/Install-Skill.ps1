param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,

    [ValidateSet("Copy", "Junction")]
    [string]$Mode = "Copy",

    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "skills\comsol-6.4"
$targetRootPath = (Resolve-Path -LiteralPath $TargetRoot -ErrorAction Stop).Path
$target = Join-Path $targetRootPath "comsol-6.4"

if (-not (Test-Path -LiteralPath (Join-Path $source "SKILL.md"))) {
    throw "Source Skill entry point was not found: $source"
}

if (Test-Path -LiteralPath $target) {
    if (-not $Force) {
        throw "Target already exists. Use -Force only after reviewing it: $target"
    }
    $item = Get-Item -LiteralPath $target -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c rmdir "$target" | Out-Null
    } else {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

if ($Mode -eq "Junction") {
    New-Item -ItemType Junction -Path $target -Target $source | Out-Null
} else {
    Copy-Item -LiteralPath $source -Destination $target -Recurse
}

Write-Host "Installed Skill: $target"
Write-Host "Entry point: $(Join-Path $target 'SKILL.md')"
