# ============================================================================
#  install.ps1 — автоустановщик pz3d (Project Zomboid Build 42)
#
#  Что делает:
#    1) Скачивает мод pz3d (из этого репозитория) и ZombieBuddy (Java-loader).
#    2) Раскладывает моды в %USERPROFILE%\Zomboid\mods\.
#    3) Копирует ZombieBuddy.jar + zbNative.dll в папку игры.
#    4) Патчит ProjectZomboid64.json:  -agentlib:zbNative  и  -Xmx >= 4096m.
#    5) Патчит ProjectZomboid64.bat:   SET _JAVA_OPTIONS=-agentlib:zbNative.
#    6) Включает моды через Zomboid\mods\default.txt (старый — в .bak).
#
#  Запуск:  через start.bat  (или: powershell -File install.ps1)
#  Удаление: powershell -File install.ps1 -Uninstall
# ============================================================================
param(
    [string]$GameDir = "",
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding           = [System.Text.Encoding]::UTF8
} catch {}
try {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {}

# ------------------------------ Настройки -----------------------------------
$script:Pz3dZipName = '3807334881_pz3d.zip'
$script:Pz3dUrls = @(
    'https://github.com/Korimuspast1/fgeg/raw/main/3807334881_pz3d.zip',
    'https://raw.githubusercontent.com/Korimuspast1/fgeg/main/3807334881_pz3d.zip'
)
$script:ZbVersion  = 'v2.3.3'
$script:ZbBaseUrl  = "https://github.com/zed-0xff/ZombieBuddy/releases/download/$($script:ZbVersion)"
$script:ZbFiles    = @('zbNative.dll', 'ZombieBuddy.jar', 'ZombieBuddy.jar.zbs')
$script:ZbRepoUrls = @(
    'https://codeload.github.com/zed-0xff/ZombieBuddy/zip/refs/heads/master',
    'https://api.github.com/repos/zed-0xff/ZombieBuddy/zipball/master'
)
$script:MinXmxMB   = 4096
$script:ModIds     = @('ZombieBuddy', 'pz3d', 'pz3d_chainlink')
$script:ZomboidDir = Join-Path $env:USERPROFILE 'Zomboid'
$script:ModsDir    = Join-Path $script:ZomboidDir 'mods'
$script:SavedPath  = Join-Path $script:ZomboidDir 'pz3d_installer_gamepath.txt'
$script:Ts         = Get-Date -Format 'yyyyMMdd_HHmmss'
$script:Step       = 0

# ------------------------------ Сервисные функции ---------------------------
function Write-Step([string]$msg) {
    $script:Step++
    Write-Host ""
    Write-Host "== [Шаг $($script:Step)] $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Info([string]$msg) { Write-Host "    $msg" -ForegroundColor Gray }
function Write-Warn([string]$msg) { Write-Host "    ВНИМАНИЕ: $msg" -ForegroundColor Yellow }

function Fail([string]$msg) {
    Write-Host ""
    Write-Host "ОШИБКА: $msg" -ForegroundColor Red
    throw $msg
}

function Ensure-Dir([string]$path) {
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
}

function Backup-File([string]$path) {
    if (Test-Path $path) {
        $bak = "$path.bak.$($script:Ts)"
        Copy-Item $path $bak -Force
        Write-Info "резервная копия: $bak"
    }
}

function Download-File {
    param([string[]]$Urls, [string]$Dest, [string]$What)
    foreach ($u in $Urls) {
        Write-Info "скачиваю: $u"
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $Dest -TimeoutSec 300
            if ((Test-Path $Dest) -and ((Get-Item $Dest).Length -gt 0)) { Write-Ok $What; return }
        } catch {
            Write-Info "Invoke-WebRequest: $($_.Exception.Message)"
        }
        $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
        if (Test-Path $curl) {
            & $curl -fSL --connect-timeout 30 --retry 2 -o $Dest $u 2>$null | Out-Null
            if (($LASTEXITCODE -eq 0) -and (Test-Path $Dest) -and ((Get-Item $Dest).Length -gt 0)) {
                Write-Ok $What
                return
            }
        }
    }
    Fail "не удалось скачать ($What). Проверьте интернет или скачайте вручную: $($Urls[0])"
}

function Test-DirWritable([string]$dir) {
    try {
        $probe = Join-Path $dir (".pz3d_write_test_" + [guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllText($probe, 'test')
        Remove-Item $probe -Force
        return $true
    } catch { return $false }
}

function Test-ValidGameDir([string]$dir) {
    return ($dir -and (Test-Path (Join-Path $dir 'ProjectZomboid64.json')))
}

# ---------------------------- Поиск папки игры ------------------------------
function Resolve-GameDir {
    $candidates = @()
    if ($GameDir) { $candidates += $GameDir }
    if ($PSScriptRoot) { $candidates += $PSScriptRoot }
    if (Test-Path $script:SavedPath) {
        $saved = ([IO.File]::ReadAllText($script:SavedPath)).Trim()
        if ($saved) { $candidates += $saved }
    }
    $candidates += @(
        (Join-Path ${env:ProgramFiles(x86)} 'Steam\steamapps\common\ProjectZomboid'),
        (Join-Path $env:ProgramFiles 'Steam\steamapps\common\ProjectZomboid'),
        'C:\Games\Project Zomboid',
        'C:\Games\ProjectZomboid',
        'D:\Games\Project Zomboid',
        'D:\Games\ProjectZomboid',
        'E:\Games\Project Zomboid'
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-ValidGameDir ($c.Trim().Trim('"')))) { return $c.Trim().Trim('"') }
    }

    Write-Host ""
    Write-Host "  Не нашёл игру автоматически. Введите путь к папке, в которой лежит" -ForegroundColor Yellow
    Write-Host "  ProjectZomboid64.exe  (например:  C:\Games\Project Zomboid)" -ForegroundColor Yellow
    Write-Host "  Подсказка: папку можно просто перетащить мышкой на файл start.bat," -ForegroundColor Yellow
    Write-Host "  тогда этот вопрос не задаётся." -ForegroundColor Yellow
    for ($i = 0; $i -lt 3; $i++) {
        $ans = (Read-Host "  Путь к папке игры").Trim().Trim('"')
        if (Test-ValidGameDir $ans) { return $ans }
        Write-Warn "в этой папке нет ProjectZomboid64.exe / ProjectZomboid64.json — попробуйте ещё раз."
    }
    Fail "папка игры не указана."
}

function Save-GameDir([string]$dir) {
    try {
        Ensure-Dir $script:ZomboidDir
        [IO.File]::WriteAllText($script:SavedPath, $dir, (New-Object System.Text.ASCIIEncoding))
    } catch {}
}

function Request-ElevationIfNeeded([string]$dir) {
    if (Test-DirWritable $dir) { return }
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdmin) {
        Fail "нет доступа на запись в папку игры даже от администратора. Проверьте антивирус / права на папку: $dir"
    }
    Write-Warn "папка игры требует прав администратора — перезапускаю установщик от имени администратора..."
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-GameDir', "`"$dir`"")
    if ($Uninstall) { $argList += '-Uninstall' }
    Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs
    Write-Info "установка продолжится в новом окне. Это окно можно закрыть."
    exit 99
}

# ------------------------------- Установка pz3d ------------------------------
function Install-Pz3d([string]$work) {
    Write-Step "Скачиваю мод pz3d"
    $zip   = Join-Path $work 'pz3d.zip'
    $local = Join-Path $PSScriptRoot $script:Pz3dZipName
    if (Test-Path $local) {
        Write-Info "использую локальный архив рядом со скриптом: $local"
        Copy-Item $local $zip -Force
    } else {
        Download-File -Urls $script:Pz3dUrls -Dest $zip -What 'архив pz3d'
    }

    $x = Join-Path $work 'pz3d_x'
    Expand-Archive -Path $zip -DestinationPath $x -Force

    $pz3dDir = Get-ChildItem -Path $x -Directory -Recurse -Filter 'pz3d' |
        Where-Object { $_.Parent.Name -ieq 'mods' } | Select-Object -First 1
    if (-not $pz3dDir) { Fail "в архиве не найдена папка mods\pz3d" }
    $modsRoot = $pz3dDir.Parent.FullName

    Ensure-Dir $script:ModsDir
    foreach ($d in (Get-ChildItem $modsRoot -Directory)) {
        Copy-Item $d.FullName (Join-Path $script:ModsDir $d.Name) -Recurse -Force
        Write-Ok "мод '$($d.Name)' -> $($script:ModsDir)"
    }
    $check = Get-ChildItem (Join-Path $script:ModsDir 'pz3d') -Recurse -Filter 'mod.info' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $check) { Fail "мод pz3d скопировался неправильно (не найден mod.info)" }
}

# ---------------------------- Установка ZombieBuddy --------------------------
function Install-ZombieBuddy([string]$work, [string]$gameDir) {
    Write-Step "Скачиваю ZombieBuddy $script:ZbVersion (Java-loader, обязателен для pz3d)"

    $zbZip = Join-Path $work 'zb_repo.zip'
    Download-File -Urls $script:ZbRepoUrls -Dest $zbZip -What 'репозиторий ZombieBuddy'
    $x = Join-Path $work 'zb_x'
    Expand-Archive -Path $zbZip -DestinationPath $x -Force

    $mi = Get-ChildItem -Path $x -Recurse -Filter 'mod.info' |
        Where-Object { $_.FullName -match '42[\\/]mod\.info$' } | Select-Object -First 1
    if (-not $mi) { Fail "в репозитории ZombieBuddy не найден 42\mod.info" }
    $zbRoot = Split-Path $mi.DirectoryName -Parent

    $dst = Join-Path $script:ModsDir 'ZombieBuddy'
    foreach ($n in @('42', 'common')) {
        $src = Join-Path $zbRoot $n
        if (Test-Path $src) { Copy-Item $src (Join-Path $dst $n) -Recurse -Force }
    }
    Write-Ok "мод 'ZombieBuddy' -> $dst"

    $libs = Join-Path $dst 'libs'
    Ensure-Dir $libs
    foreach ($f in $script:ZbFiles) {
        Download-File -Urls @("$($script:ZbBaseUrl)/$f") -Dest (Join-Path $libs $f) -What "ZombieBuddy/$f"
    }

    Write-Step "Копирую ZombieBuddy.jar и zbNative.dll в папку игры"
    Copy-Item (Join-Path $libs 'ZombieBuddy.jar') (Join-Path $gameDir 'ZombieBuddy.jar') -Force
    Copy-Item (Join-Path $libs 'zbNative.dll')  (Join-Path $gameDir 'zbNative.dll')  -Force
    Write-Ok "$gameDir\ZombieBuddy.jar"
    Write-Ok "$gameDir\zbNative.dll"
}

# ----------------------------- Патч лаунчеров --------------------------------
function Update-XmxInList([System.Collections.ArrayList]$vm) {
    $found = $false
    for ($i = 0; $i -lt $vm.Count; $i++) {
        $m = [regex]::Match([string]$vm[$i], '^-Xmx(\d+)\s*([gGmM])?')
        if ($m.Success) {
            $found = $true
            $n = [int]$m.Groups[1].Value
            if ($m.Groups[2].Value -imatch 'g') { $n = $n * 1024 }
            if ($n -lt $script:MinXmxMB) { $vm[$i] = "-Xmx$($script:MinXmxMB)m" }
        }
    }
    if (-not $found) { $vm.Insert([Math]::Min(1, $vm.Count), "-Xmx$($script:MinXmxMB)m") }
}

function Update-XmxInText([string]$text) {
    $matches = [regex]::Matches($text, '-Xmx(\d+)\s*([gGmM])?')
    for ($i = $matches.Count - 1; $i -ge 0; $i--) {
        $m = $matches[$i]
        $n = [int]$m.Groups[1].Value
        if ($m.Groups[2].Value -imatch 'g') { $n = $n * 1024 }
        if ($n -lt $script:MinXmxMB) {
            $text = $text.Remove($m.Index, $m.Length).Insert($m.Index, "-Xmx$($script:MinXmxMB)m")
        }
    }
    return $text
}

function Update-LauncherJson([string]$path) {
    Write-Step "Патчу ProjectZomboid64.json (обычный запуск)"
    if (-not (Test-Path $path)) { Fail "не найден $path" }
    $raw = [IO.File]::ReadAllText($path)
    $cfg = $raw | ConvertFrom-Json
    if ($null -eq $cfg.vmArgs) { Fail "в ProjectZomboid64.json нет секции vmArgs" }

    $vm = New-Object System.Collections.ArrayList
    foreach ($a in $cfg.vmArgs) { [void]$vm.Add([string]$a) }

    $hasAgent = $false
    foreach ($a in $vm) { if ($a -like '-agentlib:zbNative*') { $hasAgent = $true } }
    if ($hasAgent) {
        Write-Info "-agentlib:zbNative уже прописан"
    } else {
        $vm.Insert(0, '-agentlib:zbNative')
        Write-Ok "добавлен -agentlib:zbNative"
    }

    Update-XmxInList $vm | Out-Null
    Write-Ok "память для игры: минимум $($script:MinXmxMB) МБ"

    $cfg.vmArgs = [object[]]($vm.ToArray())
    Backup-File $path
    $json = ConvertTo-Json $cfg -Depth 32
    [IO.File]::WriteAllText($path, $json + "`r`n", (New-Object System.Text.ASCIIEncoding))
    Write-Ok "ProjectZomboid64.json обновлён"
}

function Update-LauncherBat([string]$path) {
    Write-Step "Патчу ProjectZomboid64.bat (альтернативный запуск)"
    if (-not (Test-Path $path)) {
        Write-Info "файл не найден — пропускаю (обычный запуск уже пропатчен)"
        return
    }
    $txt = [IO.File]::ReadAllText($path)
    $orig = $txt
    $eol = "`n"
    if ($txt.Contains("`r`n")) { $eol = "`r`n" }

    if ($txt -match '-agentlib:zbNative') {
        Write-Info "-agentlib:zbNative уже прописан"
    } elseif ($txt -match '(?im)^[ \t]*SET[ \t]+_JAVA_OPTIONS[ \t]*=.*$') {
        $txt = [regex]::Replace($txt, '(?im)^[ \t]*SET[ \t]+_JAVA_OPTIONS[ \t]*=.*$', 'SET _JAVA_OPTIONS=-agentlib:zbNative')
        Write-Ok "SET _JAVA_OPTIONS=-agentlib:zbNative"
    } else {
        $parts = $txt -split "`r`n|`n", 2
        if ($parts.Count -gt 1) {
            $txt = $parts[0] + $eol + 'SET _JAVA_OPTIONS=-agentlib:zbNative' + $eol + $parts[1]
        } else {
            $txt = 'SET _JAVA_OPTIONS=-agentlib:zbNative' + $eol + $txt
        }
        Write-Ok "добавлена строка SET _JAVA_OPTIONS"
    }

    $txt = Update-XmxInText $txt

    if ($txt -ne $orig) {
        Backup-File $path
        [IO.File]::WriteAllText($path, $txt, (New-Object System.Text.ASCIIEncoding))
        Write-Ok "ProjectZomboid64.bat обновлён"
    }
}

# ----------------------------- Включение модов -------------------------------
function Write-DefaultModList {
    Write-Step "Включаю моды (Zomboid\mods\default.txt)"
    Ensure-Dir $script:ModsDir
    $def = Join-Path $script:ModsDir 'default.txt'
    Backup-File $def
    # Формат игрового сериализатора: id модов в кавычках и с запятой,
    # например:  "pz3d",   — без кавычек файл читается как пустой!
    $lines = @('VERSION = 1,', '', 'mods', '{')
    foreach ($id in $script:ModIds) { $lines += "`t`"$id`"," }
    $lines += @('}', '', 'maps', '{', '}')
    [IO.File]::WriteAllText($def, ($lines -join "`r`n") + "`r`n", (New-Object System.Text.ASCIIEncoding))

    # Самопроверка: перечитываем файл и убеждаемся, что все id на месте
    $check = [IO.File]::ReadAllText($def)
    foreach ($id in $script:ModIds) {
        if ($check -notmatch ('"' + [regex]::Escape($id) + '"')) {
            Fail "default.txt записался некорректно (нет записи `"$id`") — включите моды вручную в меню игры 'Моды'."
        }
    }
    Write-Ok "включены: $($script:ModIds -join ', ')"
    Write-Info "все остальные моды выключены — так требует pz3d. Бэкап старого списка лежит рядом (*.bak)."
    Write-Info "проверка: в главном меню игры зайдите в 'Моды' — все три должны быть с галочкой."
}

# -------------------------------- Удаление -----------------------------------
function Invoke-Uninstall([string]$gameDir) {
    Write-Step "Удаляю ZombieBuddy и pz3d"

    foreach ($f in @('ZombieBuddy.jar', 'ZombieBuddy.jar.new', 'zbNative.dll')) {
        $p = Join-Path $gameDir $f
        if (Test-Path $p) { Remove-Item $p -Force; Write-Ok "удалено: $p" }
    }

    $jsonPath = Join-Path $gameDir 'ProjectZomboid64.json'
    if (Test-Path $jsonPath) {
        $raw = [IO.File]::ReadAllText($jsonPath)
        if ($raw -match '-agentlib:zbNative') {
            $cfg = $raw | ConvertFrom-Json
            $keep = @($cfg.vmArgs | Where-Object { $_ -notlike '-agentlib:zbNative*' })
            $cfg.vmArgs = $keep
            Backup-File $jsonPath
            [IO.File]::WriteAllText($jsonPath, (ConvertTo-Json $cfg -Depth 32) + "`r`n", (New-Object System.Text.ASCIIEncoding))
            Write-Ok "ProjectZomboid64.json очищен"
        }
    }

    $batPath = Join-Path $gameDir 'ProjectZomboid64.bat'
    if (Test-Path $batPath) {
        $txt = [IO.File]::ReadAllText($batPath)
        if ($txt -match '-agentlib:zbNative') {
            $txt = [regex]::Replace($txt, '(?im)^[ \t]*SET[ \t]+_JAVA_OPTIONS[ \t]*=.*$', 'SET _JAVA_OPTIONS=')
            Backup-File $batPath
            [IO.File]::WriteAllText($batPath, $txt, (New-Object System.Text.ASCIIEncoding))
            Write-Ok "ProjectZomboid64.bat очищен"
        }
    }

    foreach ($id in $script:ModIds) {
        $p = Join-Path $script:ModsDir $id
        if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Ok "удалён мод: $p" }
    }

    $def = Join-Path $script:ModsDir 'default.txt'
    $baks = Get-ChildItem "$def.bak.*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    if ($baks.Count -gt 0) {
        Copy-Item $baks[0].FullName $def -Force
        Write-Ok "восстановлен список модов из $($baks[0].Name)"
    } elseif (Test-Path $def) {
        Remove-Item $def -Force
        Write-Ok "default.txt удалён"
    }

    Write-Host ""
    Write-Host "  Готово: pz3d и ZombieBuddy удалены, лаунчеры возвращены в исходное." -ForegroundColor Green
}

# --------------------------------- MAIN --------------------------------------
try {
    Write-Host ""
    Write-Host "  =============================================================" -ForegroundColor DarkCyan
    Write-Host "   pz3d  автоустановщик  (Project Zomboid Build 42.21.0)" -ForegroundColor DarkCyan
    Write-Host "  =============================================================" -ForegroundColor DarkCyan
    Write-Warn "игра должна быть версии 42.21.0 — иначе pz3d не запустится."

    $game = Resolve-GameDir
    Write-Ok "папка игры: $game"
    Save-GameDir $game
    Request-ElevationIfNeeded $game

    if ($Uninstall) {
        Invoke-Uninstall $game
    } else {
        $work = Join-Path $env:TEMP ("pz3d_setup_" + [guid]::NewGuid().ToString('N'))
        Ensure-Dir $work
        try {
            Install-Pz3d $work
            Install-ZombieBuddy $work $game
            Update-LauncherJson (Join-Path $game 'ProjectZomboid64.json')
            Update-LauncherBat  (Join-Path $game 'ProjectZomboid64.bat')
            Write-DefaultModList
        } finally {
            Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
        }

        Write-Host ""
        Write-Host "  =============================================================" -ForegroundColor Green
        Write-Host "   ГОТОВО! pz3d + ZombieBuddy установлены и включены." -ForegroundColor Green
        Write-Host "  =============================================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Что дальше:" -ForegroundColor White
        Write-Host "   1. Запустите игру." -ForegroundColor White
        Write-Host "   2. Зайдите в меню 'Моды': ZombieBuddy, pz3d и pz3d_chainlink должны" -ForegroundColor White
        Write-Host "      быть ВКЛЮЧЕНЫ. Если галочки не стоят - поставьте сами (сначала" -ForegroundColor White
        Write-Host "      ZombieBuddy, потом pz3d) и нажмите 'Принять'." -ForegroundColor White
        Write-Host "   3. При первом запуске с модами ZombieBuddy покажет окно" -ForegroundColor White
        Write-Host "      подтверждения Java-мода pz3d - нажмите Yes. Окно может" -ForegroundColor White
        Write-Host "      оказаться ПОД окном игры - проверьте через Alt+Tab!" -ForegroundColor White
        Write-Host "   4. Слева вверху должно быть '1 active Java mods: pz3d'," -ForegroundColor White
        Write-Host "      а в строке версии - приписка [ZB]." -ForegroundColor White
        Write-Host "   5. Создайте НОВОЕ одиночное сохранение: моды включаются" -ForegroundColor White
        Write-Host "      только для нового мира, в старом pz3d не появится." -ForegroundColor White
        Write-Host "   6. После появления в мире нажмите Insert - вход в 3D-режим." -ForegroundColor White
        Write-Host ""

        $ans = Read-Host "  Запустить Project Zomboid сейчас? [Y/n]"
        if ($ans -eq '' -or $ans -imatch '^(y|д|yes|да)') {
            $exe = Join-Path $game 'ProjectZomboid64.exe'
            if (Test-Path $exe) {
                Start-Process $exe -WorkingDirectory $game
                Write-Ok "игра запущена"
            } else {
                Write-Warn "ProjectZomboid64.exe не найден — запустите игру привычным способом."
            }
        }
    }

    Write-Host ""
    exit 0
} catch {
    Write-Host ""
    Write-Host "  Установка не завершена: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Исправьте причину и запустите start.bat ещё раз - уже сделанное" -ForegroundColor Red
    Write-Host "  не сломается, установка продолжится с места ошибки." -ForegroundColor Red
    Write-Host ""
    exit 1
}
