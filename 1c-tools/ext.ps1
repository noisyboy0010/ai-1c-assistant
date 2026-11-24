# Работа с расширениями 1С через пакетный конфигуратор.
#   .\ext.ps1 dump  -Name МоеРасширение      # расширение -> src\ext\МоеРасширение (XML + BSL)
#   .\ext.ps1 load  -Name МоеРасширение      # src\ext\МоеРасширение -> база, + обновление БД
#   .\ext.ps1 dumpcfg                        # основная конфигурация -> src\cfg (только для чтения/справки)
#   .\ext.ps1 cfe   -Name МоеРасширение      # сохранить расширение в out\МоеРасширение.cfe (для переноса в рабочую базу)
# Перед load закройте конфигуратор этой базы (нужен монопольный доступ к конфигурации).
param(
    [Parameter(Mandatory)][ValidateSet('dump','load','dumpcfg','cfe')][string]$Action,
    [string]$Name
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Get-Content "$root\.env" -Encoding UTF8 | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object {
    Set-Item "env:$($Matches[1])" $Matches[2].Trim()
}
if ($Action -ne 'dumpcfg' -and -not $Name) { throw "Укажите -Name <имя расширения>" }

New-Item -ItemType Directory -Force "$root\logs" | Out-Null
$log = "$root\logs\$Action-$(Get-Date -Format yyyyMMdd-HHmmss).log"
if (-not $env:ONEC_ADMIN_USER) { throw "В .env не заполнен ONEC_ADMIN_USER (администратор базы)" }
$common = @('DESIGNER', '/F', $env:ONEC_BASE, '/N', $env:ONEC_ADMIN_USER)
if ($env:ONEC_ADMIN_PWD) { $common += @('/P', $env:ONEC_ADMIN_PWD) }
$common += @('/DisableStartupDialogs', '/DisableStartupMessages', '/Out', $log)

switch ($Action) {
    'dump'    { $cmd = @('/DumpConfigToFiles', "$root\src\ext\$Name", '-Extension', $Name) }
    'load'    { $cmd = @('/LoadConfigFromFiles', "$root\src\ext\$Name", '-Extension', $Name, '/UpdateDBCfg') }
    'dumpcfg' { $cmd = @('/DumpConfigToFiles', "$root\src\cfg") }
    'cfe'     { New-Item -ItemType Directory -Force "$root\out" | Out-Null
                $cmd = @('/DumpCfg', "$root\out\$Name.cfe", '-Extension', $Name) }
}

$p = Start-Process -FilePath $env:ONEC_BIN -ArgumentList ($common + $cmd | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -Wait -PassThru
Get-Content $log -Encoding Default -ErrorAction SilentlyContinue
if ($p.ExitCode -ne 0) { throw "1cv8 завершился с кодом $($p.ExitCode), см. $log" }
"Готово: $Action $Name"
