param(
    [string]$InnoCompiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE."
    }
}

Push-Location (Join-Path $PSScriptRoot '..')
try {
    if (-not (Test-Path -LiteralPath $InnoCompiler -PathType Leaf)) {
        throw 'Install Inno Setup 6 or pass its ISCC.exe path with -InnoCompiler.'
    }
    Invoke-Checked 'py' @('-3.12', '-m', 'venv', '.venv')
    $Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    Invoke-Checked $Python @('-c', "import struct, sys, tkinter; assert sys.platform == 'win32' and struct.calcsize('P') == 8, 'Use 64-bit Windows Python.'")
    Invoke-Checked $Python @('-m', 'pip', 'install', '-r', 'packaging/requirements-build.txt')
    Invoke-Checked $Python @('-m', 'unittest', 'discover', '-s', 'tests', '-v')

    $Version = & $Python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
    if ($LASTEXITCODE -ne 0 -or $Version -notmatch '^\d+\.\d+\.\d+$') {
        throw 'Invalid project version in pyproject.toml.'
    }

    New-Item -ItemType Directory -Force -Path 'build', 'dist' | Out-Null
    Invoke-Checked $Python @('packaging/make_icon.py', 'build/streamkey.ico')
    $Common = @('-m', 'PyInstaller', '--clean', '--noconfirm', '--windowed',
                '--specpath', 'build/spec', '--workpath', 'build/pyinstaller',
                '--icon', 'build/streamkey.ico', '--add-data', 'pyproject.toml:.',
                '--add-data', 'build/streamkey.ico:streamkey', '--noupx')
    Invoke-Checked $Python ($Common + @('--onedir', '--distpath', 'build/installed',
                       '--name', 'T0G-StreamKey', 'run_streamkey.py'))
    Invoke-Checked $Python ($Common + @('--onefile', '--distpath', 'dist',
                       '--name', 'T0G-StreamKey-Portable', 'run_streamkey.py'))
    Invoke-Checked $InnoCompiler @("/DAppVersion=$Version", 'packaging/T0G-StreamKey.iss')
    Get-FileHash 'dist/T0G-StreamKey-Setup.exe', 'dist/T0G-StreamKey-Portable.exe' -Algorithm SHA256
}
finally {
    Pop-Location
}
