# v7 - INSTALAR / PROVAR O DESKTOP COM WINDOWS DE VERDADE
# Executado DENTRO do job conectar-windows #7 pelo gancho de hash.
# ASCII puro: o pwsh 5.1/cp1252 ja quebrou com "──" nesta conversa.
# NAO reinicia servico, NAO troca senha, NAO derruba o RDP.
$ErrorActionPreference = 'Continue'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

$o = Get-CimInstance Win32_OperatingSystem
$c = Get-CimInstance Win32_ComputerSystem
$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$term = (Get-Service TermService -ErrorAction SilentlyContinue).Status
$audio = (Get-Service Audiosrv -ErrorAction SilentlyContinue).Status
$explorers = @(Get-Process explorer -ErrorAction SilentlyContinue)
$rdp = try {
  Test-NetConnection -ComputerName 127.0.0.1 -Port 3389 `
    -InformationLevel Quiet -WarningAction SilentlyContinue
} catch { $false }
$ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
$ip = if (Test-Path $ts) { (& $ts ip -4 | Select-Object -First 1) } else { '' }
$dns = try { (& $ts status --json | ConvertFrom-Json).Self.DNSName } catch { '' }

$linhas = @(
  'DESKTOP COM WINDOWS DE VERDADE',
  "gerado_utc   : $stamp",
  "caption      : $($o.Caption)",
  "version      : $($o.Version) build $($o.BuildNumber)",
  "product_name : $($cv.ProductName)",
  "edition_id   : $($cv.EditionID)",
  "install_type : $($cv.InstallationType)",
  "arch         : $($o.OSArchitecture)",
  "product_type : $($o.ProductType)  (3 = Server, 1 = Workstation)",
  "host         : $($c.Name)",
  "cores        : $((Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum)",
  "ram_gb       : $([math]::Round($c.TotalPhysicalMemory/1GB,1))",
  "explorer     : $($explorers.Count) processo(s)",
  "term_service : $term",
  "audio_srv    : $audio",
  "rdp_3389     : $rdp",
  "tailnet_ip   : $ip",
  "magicdns     : $dns",
  '',
  'Isto e um SO Microsoft genuino, nao ReactOS, nao Wine, nao pagina HTML.',
  'Imagem: GitHub-hosted windows-latest = Windows Server 2025 Datacenter.',
  'RDP nativo :3389 com audio, clipboard e redirecionamento de drives.'
)

# --- 1) garante o desktop grafico de pe (best-effort, sem derrubar nada) ---
if ($explorers.Count -eq 0) {
  try { Start-Process explorer.exe -ErrorAction SilentlyContinue | Out-Null } catch {}
  $linhas += 'explorer    : iniciado best-effort (estava ausente)'
}

# --- 2) instala evidencia visivel NA AREA DE TRABALHO do usuario ---
$desk = 'C:\Users\winuser\Desktop'
try { New-Item -ItemType Directory -Force -Path $desk | Out-Null } catch {}
try {
  [System.IO.File]::WriteAllLines(
    "$desk\WINDOWS_DE_VERDADE.txt",
    [string[]]$linhas,
    (New-Object System.Text.UTF8Encoding($false))
  )
  $linhas += 'desktop_file : WINDOWS_DE_VERDADE.txt gravado'
} catch { $linhas += "desktop_file ERRO: $($_.Exception.Message)" }

# --- 3) atalho real para winver.exe (prova visual de um clique) ---
try {
  $w = New-Object -ComObject WScript.Shell
  $s = $w.CreateShortcut("$desk\Este PC - Windows real.lnk")
  $s.TargetPath = "$env:WINDIR\System32\winver.exe"
  $s.Description = 'Mostra a versao genuine do Windows instalado'
  $s.Save()
  $linhas += 'atalho       : Este PC - Windows real.lnk -> winver.exe'
} catch { $linhas += "atalho ERRO: $($_.Exception.Message)" }

# --- 4) publica a prova no repo (o watchdog le daqui) ---
try {
  Set-Location $env:GITHUB_WORKSPACE
  [System.IO.File]::WriteAllLines(
    'INSTALACAO_DESKTOP.txt',
    [string[]]$linhas,
    (New-Object System.Text.UTF8Encoding($false))
  )
  git add -f INSTALACAO_DESKTOP.txt 2>&1 | Out-Null
  git commit -m "instalacao desktop windows real $stamp" 2>&1 | Out-Null
  for ($i = 1; $i -le 5; $i++) {
    git pull --rebase -X theirs origin main 2>&1 | Out-Null
    git push origin HEAD:main 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds ($i * 2)
  }
  $linhas += "publicado    : INSTALACAO_DESKTOP.txt (push rc=$LASTEXITCODE)"
} catch { $linhas += "publicado ERRO: $($_.Exception.Message)" }

$linhas | ForEach-Object { "  $_" }
exit 0
