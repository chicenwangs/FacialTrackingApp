# Build softcam.dll renamed to "McG Cam" (ADR-009). Needs git + VS 2022 "Desktop development with C++".
# Output: native/softcam/bin/softcam.dll. Does NOT register (that needs admin; see README).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$src = Join-Path $here "src"
$tag = "v1.8.1"  # commit afb424c2415b04da627fa1a7b4706575c2ba3010

if (-not (Test-Path $src)) {
    git clone --depth 1 --branch $tag https://github.com/tshino/softcam.git $src
}

# Patch name + CLSID so McG Cam never clashes with stock softcam installs.
$cpp = Join-Path $src "src\softcam\softcam.cpp"
$text = Get-Content $cpp -Raw
$text = $text -replace 'L"DirectShow Softcam"', 'L"McG Cam"'
$text = $text -replace '0xaef3b972, 0x5fa5, 0x4647, 0x95, 0x71, 0x35, 0x8e, 0xb4, 0x72, 0xbc, 0x9e',
                       '0x41411e10, 0x0f51, 0x4062, 0x97, 0xe7, 0x8d, 0x29, 0x14, 0xf8, 0xce, 0x52'
if ($text -notmatch 'L"McG Cam"' -or $text -notmatch '0x41411e10') { throw "patch failed: softcam.cpp changed upstream" }
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
