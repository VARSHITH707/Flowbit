# Build the standalone Flowbit app (PyInstaller, one folder) into dist\Flowbit.
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1            # GPU build (bundles NVIDIA cuBLAS/cuDNN, ~2.3 GB)
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -CpuOnly   # CPU build, much smaller
# Models are NOT bundled: they are downloaded on first use into a models folder next to the .exe.
param([switch]$CpuOnly)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venv = Join-Path $root ".venv"
$py = Join-Path $venv "Scripts\python.exe"
$sp = Join-Path $venv "Lib\site-packages"

# A clean PATH matters: PyInstaller resolves DLL dependencies through PATH, and a stray OpenSSL
# (for example Git's mingw64\bin) gets bundled instead of Python's own, which breaks `import ssl`.
$env:PATH = "$venv\Scripts;$env:SystemRoot\System32;$env:SystemRoot"

& $py -m pip --version *> $null
if ($LASTEXITCODE -ne 0) { uv pip install --python $py pip *> $null }
& $py -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { uv pip install --python $py pyinstaller }

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build | Out-Null
# app icon: the mascot, drawn by the app's own code (no image files in the repo)
& $py -c "from PySide6.QtGui import QGuiApplication; a = QGuiApplication([]); from voicetype.ui.mascot import mascot_icon; mascot_icon(256).pixmap(256, 256).save('build/flowbit.ico')"
$args = @("-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--name", "Flowbit", "--icon", "$root\build\flowbit.ico",
          "--distpath", "dist", "--workpath", "build", "--specpath", "build",
          "--collect-all", "faster_whisper", "--collect-all", "ctranslate2", "--collect-all", "onnxruntime",
          "--collect-all", "sounddevice", "--collect-all", "_sounddevice_data", "--collect-all", "uiautomation",
          "--hidden-import", "comtypes.stream", "--add-data", "$root\voicetype\assets;voicetype/assets", "--paths", $root)
if (-not $CpuOnly) {
    foreach ($lib in "cublas", "cudnn", "cuda_nvrtc") {
        $args += @("--add-binary", "$sp\nvidia\$lib\bin\*.dll;nvidia/$lib/bin")
    }
}
$args += "run_voicetype.py"
& $py @args
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }
$mb = [math]::Round((Get-ChildItem dist\Flowbit -Recurse | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "Built dist\Flowbit\Flowbit.exe ($mb MB)"
