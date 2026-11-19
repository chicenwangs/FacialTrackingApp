# Build softcam.dll renamed to "FaceCam Camera" with our own CLSID.
# Needs git (only if src is missing) and VS 2022 "Desktop development with C++".
# Output: native/softcam/bin/softcam.dll. Does NOT register (that needs admin).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$src = Join-Path $here "src"
$tag = "v1.8.1"  # upstream commit afb424c2415b04da627fa1a7b4706575c2ba3010
$name = "FaceCam Camera"
$guid = "0xb7e2a4c1, 0x9d3f, 0x4e6a, 0x8b, 0x25, 0x0c, 0x1d, 0x2e, 0x3f, 0x4a, 0x5b"

if (-not (Test-Path $src)) {
    git clone --depth 1 --branch $tag https://github.com/tshino/softcam.git $src
}

# Patch both the stock name/CLSID and the older build, so this works from
# either a fresh upstream clone or the source shipped with this repo.
$cpp = Join-Path $src "src\softcam\softcam.cpp"
$text = Get-Content $cpp -Raw
$text = $text -replace 'L"DirectShow Softcam"', ('L"' + $name + '"')
$oldGuids = @(
    "0xaef3b972, 0x5fa5, 0x4647, 0x95, 0x71, 0x35, 0x8e, 0xb4, 0x72, 0xbc, 0x9e",
    "0x41411e10, 0x0f51, 0x4062, 0x97, 0xe7, 0x8d, 0x29, 0x14, 0xf8, 0xce, 0x52"
)
foreach ($old in $oldGuids) {
    $text = $text -replace [regex]::Escape($old), $guid
}
if ($text -notmatch [regex]::Escape('L"' + $name + '"') -or $text -notmatch '0xb7e2a4c1') {
    throw "patch failed: softcam.cpp changed upstream"
}
Set-Content $cpp $text -NoNewline

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$msbuild = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find "MSBuild\**\Bin\MSBuild.exe" | Select-Object -First 1
if (-not $msbuild) { throw "MSBuild with C++ tools not found. Install VS 2022 Build Tools, C++ workload." }

& $msbuild (Join-Path $src "softcam.sln") /t:softcam /p:Configuration=Release /p:Platform=x64 /p:PostBuildEventUseInBuild=false /m
if ($LASTEXITCODE -ne 0) { throw "build failed" }

$dll = Get-ChildItem $src -Recurse -Filter softcam.dll | Where-Object { $_.FullName -match 'x64\\Release' } | Select-Object -First 1
if (-not $dll) { throw "softcam.dll not found after build" }
New-Item -ItemType Directory -Force (Join-Path $here "bin") | Out-Null
Copy-Item $dll.FullName (Join-Path $here "bin\softcam.dll") -Force
Write-Host "OK -> $(Join-Path $here 'bin\softcam.dll')"
