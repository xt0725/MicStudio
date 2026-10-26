$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE) { throw 'Python 3 est requis.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Installation des dépendances impossible.' }
$argsBuild = @('--noconfirm','--clean','--windowed','--onedir','--name','MicStudio','--icon','assets/micstudio.ico','--collect-all','sounddevice','--collect-all','soundfile')
if (!(Test-Path native\rnnoise.dll)) { throw 'RNNoise DLL is required. Run the Windows workflow to compile it.' }
$argsBuild += @('--add-binary','native\rnnoise.dll;native')
if (Test-Path licenses) { $argsBuild += @('--add-data','licenses;licenses') }
& .\.venv\Scripts\pyinstaller.exe @argsBuild app.py
if ($LASTEXITCODE) { throw 'Compilation impossible.' }
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (!(Test-Path $iscc)) { throw 'Installez Inno Setup 6, puis relancez build.ps1.' }
& $iscc installer\MicStudio.iss
if ($LASTEXITCODE) { throw 'Creation installateur impossible.' }
