#!/usr/bin/env python3
"""
Собирает start.bat - самодостаточный one-click установщик pz3d.

start.bat - чистый ASCII: cmd-заголовок извлекает из самого себя base64-payload
(это install.ps1 в UTF-8 с BOM), проверяет SHA-256, пишет %TEMP%\\install_pz3d.ps1
и запускает его через Windows PowerShell. ASCII-only выбран намеренно:
такой файл невозможно испортить кодировкой ни при скачивании, ни копипастой.

Запуск:  python3 tools/build_start_bat.py
Читает:  install.ps1 (UTF-8 с BOM) рядом с корнем репозитория
Пишет:   start.bat (ASCII, CRLF)
"""
import base64
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "install.ps1"
DST = ROOT / "start.bat"
MARK = "PZ3DDATA>"

TEMPLATE = r"""@echo off
rem ============================================================================
rem  pz3d ONE-CLICK INSTALLER  (Project Zomboid Build 42.21.0)
rem
rem  Self-contained: the whole PowerShell installer is embedded inside this
rem  file (base64 payload at the bottom). Just double-click start.bat.
rem  Optional: drag the game folder (with ProjectZomboid64.exe) onto start.bat.
rem
rem  Nothing else to download. {LINES} payload lines, SHA-256 verified.
rem ============================================================================
setlocal EnableExtensions
set "PZ3D_INSTALLER_DIR=%~dp0"
set "D=%TEMP%\pz3d_oneclick"
if not exist "%D%" mkdir "%D%"
set "PS1=%D%\install_pz3d.ps1"
set "B64=%D%\payload.b64"
set "SHA=%D%\payload.sha256"

findstr /b /l "{MARK}" "%~f0" > "%B64%" || (echo [pz3d] ERROR: embedded payload not found. File damaged - re-download start.bat.& pause & exit /b 1)
> "%SHA%" echo {SHA256}

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$e=0; try { $lines = Get-Content $env:B64 | ForEach-Object { $_.Substring({MLEN}) }; $b64 = ($lines -join ''); if (-not $b64) { throw 'empty payload' }; $bytes = [Convert]::FromBase64String($b64); $sha = [System.Security.Cryptography.SHA256]::Create(); $actual = ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-',''); $expected = (Get-Content $env:SHA).Trim(); if ($actual -ne $expected) { Write-Host '[pz3d] ERROR: payload checksum mismatch - file is damaged. Re-download start.bat.' -ForegroundColor Red; $e = 2 } else { [IO.File]::WriteAllBytes($env:PS1, $bytes) } } catch { Write-Host ('[pz3d] ERROR: ' + $_.Exception.Message) -ForegroundColor Red; $e = 1 }; exit $e"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (echo.& pause & exit /b %RC%)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="99" exit /b 0
if not "%RC%"=="0" (echo.& echo [start.bat] Something went wrong. Scroll up to read the error.& pause & exit /b %RC%)
echo.
pause
exit /b 0
rem ==================== payload below - do not edit anything =================
"""


def main() -> int:
    raw = SRC.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        print("ERROR: install.ps1 must be UTF-8 *with BOM*", file=sys.stderr)
        return 1
    b64 = base64.b64encode(raw).decode("ascii")
    sha = hashlib.sha256(raw).hexdigest()
    chunks = [b64[i:i + 4000] for i in range(0, len(b64), 4000)]
    payload = [MARK + c for c in chunks]

    header = TEMPLATE.replace("{LINES}", str(len(chunks))) \
                     .replace("{SHA256}", sha) \
                     .replace("{MARK}", MARK) \
                     .replace("{MLEN}", str(len(MARK)))

    bat_text = header.replace("\n", "\r\n") + "\r\n".join(payload) + "\r\n"
    bat_bytes = bat_text.encode("ascii")  # падает, если случайно не-ASCII
    DST.write_bytes(bat_bytes)

    # самопроверка: извлекаем payload обратно и сравниваем с исходником
    back = [line[len(MARK):] for line in bat_text.splitlines() if line.startswith(MARK)]
    assert base64.b64decode("".join(back)) == raw, "payload round-trip mismatch"
    print(f"OK: {DST.name} written, {len(bat_bytes)} bytes, "
          f"{len(chunks)} payload lines, sha256={sha[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
