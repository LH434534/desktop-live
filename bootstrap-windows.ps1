# bootstrap-windows.ps1 — o degrau final: DONO TOTAL.
#
# RODA NO SEU PC WINDOWS (Windows 10/11), como Administrador.
# Nao roda no GitHub Actions. Nao precisa de VPS nem de cartao.
#
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   $env:GH_TOKEN = 'github_pat_...'          # scope: repo + workflow
#   $env:TS_AUTHKEY = 'tskey-auth-...'        # auth key REUTILIZAVEL
#   $env:MINHA_SENHA = 'senha-forte-aqui'     # senha RDP do usuario dono
#   .\bootstrap-windows.ps1
#
# Resultado: RDP nativo + Tailscale + self-hosted runner registrado no SEU
# repo. Disco permanente, IP estavel, sem teto de 6h, sem cota de minutos,
# sem plataforma decidindo por voce. O hardware e o seu.
#
# VALIDAR_ONLY=1 -> apenas parseia este arquivo e sai (sem tocar em nada).

$ErrorActionPreference = 'Stop'

if ($env:VALIDAR_ONLY -eq '1') {
  $errs = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile(
    $PSCommandPath, [ref]$null, [ref]$errs)
  if ($errs.Count) { $errs | ForEach-Object { Write-Error $_ }; exit 1 }
  'PARSE_OK'
  exit 0
}

function Log($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Need($n, $v) {
  if (-not $v) { throw "Defina a variavel de ambiente $n antes de rodar." }
}

Need 'GH_TOKEN'    $env:GH_TOKEN
Need 'TS_AUTHKEY'  $env:TS_AUTHKEY
Need 'MINHA_SENHA' $env:MINHA_SENHA

$OWNER = if ($env:GH_OWNER) { $env:GH_OWNER } else { 'LH434534' }
$REPO  = if ($env:GH_REPO)  { $env:GH_REPO }  else { 'desktop-live' }
$HOSTNAME = if ($env:TS_HOSTNAME) { $env:TS_HOSTNAME } else { 'meu-pc' }
$API = 'https://api.github.com'

# --- 0. admin ---
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Abra o PowerShell como Administrador.'
}

Log '1/6 RDP nativo + usuario local'
$u = 'dono'
if (-not (Get-LocalUser -Name $u -ErrorAction SilentlyContinue)) {
  $sec = ConvertTo-SecureString $env:MINHA_SENHA -AsPlainText -Force
  New-LocalUser -Name $u -Password $sec -PasswordNeverExpires -AccountNeverExpires | Out-Null
} else {
  $sec = ConvertTo-SecureString $env:MINHA_SENHA -AsPlainText -Force
  Set-LocalUser -Name $u -Password $sec
}
Add-LocalGroupMember -Group 'Remote Desktop Users' -Member $u -ErrorAction SilentlyContinue
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' `
  -Name 'fDenyTSConnections' -Value 0
try { Enable-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue } catch {}
foreach ($s in @('Audiosrv','AudioEndpointBuilder','TermService','UmRdpService')) {
  try { Set-Service -Name $s -StartupType Automatic -ErrorAction SilentlyContinue } catch {}
  try { Start-Service $s -ErrorAction SilentlyContinue } catch {}
}
# Nenhuma exposicao publica: 3389 somente pela faixa CGNAT da tailnet.
Log '2/6 firewall: 3389 SOMENTE pela tailnet (100.64.0.0/10)'
try {
  Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue |
    Where-Object { $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' } |
    ForEach-Object {
      Set-NetFirewallRule -Name $_.Name -RemoteAddress '100.64.0.0/10' `
        -ErrorAction SilentlyContinue
    }
  '  regras RDP restringidas a 100.64.0.0/10'
} catch { "  firewall: $($_.Exception.Message)" }

Log '3/6 Tailscale'
$ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (-not (Test-Path $ts)) {
  try {
    winget install --id Tailscale.Tailscale -e --silent `
      --accept-package-agreements --accept-source-agreements | Out-Null
  } catch {}
}
if (-not (Test-Path $ts)) {
  $setup = "$env:TEMP\tailscale-setup.exe"
  Invoke-WebRequest -Uri 'https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe' `
    -OutFile $setup -UseBasicParsing
  Start-Process $setup -ArgumentList '/S' -Wait
  Start-Sleep -Seconds 8
}
if (-not (Test-Path $ts)) { throw 'Tailscale nao instalou.' }
& $ts up --authkey="$env:TS_AUTHKEY" --hostname="$HOSTNAME" 2>&1 | Select-Object -Last 6
Start-Sleep -Seconds 5
$ip = (& $ts ip -4 | Select-Object -First 1)
$dns = try { (& $ts status --json | ConvertFrom-Json).Self.DNSName } catch { '' }
"ip_tailnet : $ip"
"dns_name   : $dns"

Log '4/6 self-hosted runner (versao obtida da API)'
$hdr = @{
  Authorization = "Bearer $env:GH_TOKEN"
  Accept = 'application/vnd.github+json'
  'X-GitHub-Api-Version' = '2022-11-28'
}
$reg = Invoke-RestMethod -Method Post -Headers $hdr `
  -Uri "$API/repos/$OWNER/$REPO/actions/runners/registration-token"
if (-not $reg.token) { throw 'Nao consegui registration-token.' }
$rel = Invoke-RestMethod -Headers $hdr `
  -Uri "$API/repos/actions/runner/releases/latest"
$tag = $rel.tag_name
$ver = $tag.TrimStart('v')
$url = "https://github.com/actions/runner/releases/download/$tag/actions-runner-win-x64-$ver.zip"
$dir = 'C:\actions-runner'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Set-Location $dir
Invoke-WebRequest -Uri $url -OutFile runner.zip -UseBasicParsing
Expand-Archive -Path runner.zip -DestinationPath $dir -Force
Remove-Item runner.zip

& .\config.cmd --url "https://github.com/$OWNER/$REPO" --token $reg.token `
  --name $HOSTNAME --labels 'meupc,windows,permanente' --work '_work' `
  --unattended --replace 2>&1 | Select-Object -Last 12
if ($LASTEXITCODE -ne 0) { throw "config.cmd falhou rc=$LASTEXITCODE" }

Log '5/6 servico do runner (auto-start no boot)'
& .\svc.cmd install 2>&1 | Select-Object -Last 6
& .\svc.cmd start 2>&1 | Select-Object -Last 6

Log '6/6 cartao de conexao'
$cartao = @(
  '# DESKTOP 10000% SEU — sem GitHub Actions no meio',
  "data          : $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')",
  "maquina       : $env:COMPUTERNAME (hardware seu)",
  '',
  "Host          : $dns",
  "  (ou IP)     : $ip",
  'Porta         : 3389',
  'Usuario       : dono',
  'Senha         : (a que voce definiu em MINHA_SENHA)',
  'App           : Windows App / RD Client',
  'Tailscale     : mesma conta, ativo no celular',
  '',
  'Validade      : NAO EXPIRA — disco, servicos e IP sao seus',
  'Teto de 6h    : inexistente (self-hosted runner)',
  'Cota          : irrelevante (runner self-hosted e gratuito)',
  "Repo          : $OWNER/$REPO (workflow meu-pc.yml)",
  '',
  'Para desligar : .\\svc.cmd stop   /   .\\svc.cmd uninstall',
  'Para revogar  : painel Tailscale -> remova o dispositivo'
) -join "`r`n"
$cartao | Set-Content -Path "$env:USERPROFILE\Desktop\CONECTAR_MEU_PC.txt" -Encoding UTF8
$cartao
Log 'PRONTO — o servidor agora e o seu computador.'
