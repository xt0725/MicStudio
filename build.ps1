$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3 -m venv .venv
if ($LASTEXITCODE) { throw 'Python 3 est requis.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Installation des dépendances impossible.' }
$argsBuild = @('--noconfirm','--clean','--windowed','--onedir','--name','MicStudio','--collect-all','sounddevice')
if (Test-Path native\rnnoise.dll) { $argsBuild += @('--add-binary','native\rnnoise.dll;native') }
& .\.venv\Scripts\pyinstaller.exe @argsBuild app.py
if ($LASTEXITCODE) { throw 'Compilation impossible.' }
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (!(Test-Path $iscc)) { throw 'Installez Inno Setup 6, puis relancez build.ps1.' }
& $iscc installer\MicStudio.iss
if ($LASTEXITCODE) { throw 'Création de l’installateur impossible.' }
