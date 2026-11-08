$ErrorActionPreference = 'Continue'
$ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
$ip  = (& $ts ip -4 | Select-Object -First 1)
$dns = try { (& $ts status --json | ConvertFrom-Json).Self.DNSName } catch { '' }
if (-not $dns) { $dns = $ip }
$stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'
@(
  "# ENDERECO FIXO — lido de DENTRO do seu Windows",
  "data_utc  : $stamp",
  "run       : $env:GITHUB_RUN_NUMBER",
  "Host FIXO : $dns",
  "IP atual  : $ip",
  "Porta     : 3389",
  "Usuario   : winuser",
  "Nota      : o IP muda a cada boot; ESTE NOME nao muda.",
  "App       : Windows App / RD Client -> campo NOME DO COMPUTADOR",
  "Requisito : Tailscale ativo no celular, mesma conta"
) | Set-Content DNS_FIXO.txt -Encoding UTF8
$f = 'CONECTAR_WINDOWS.txt'
if (Test-Path $f) {
  $c = Get-Content $f
  if (-not ($c -match '^Host FIXO')) {
    $c = $c -replace '^(Address       : .+)$', "`$1`r`nHost FIXO     : $dns"
    $c | Set-Content $f -Encoding UTF8
  }
}
git config user.name dns-fixo
git config user.email dns-fixo@localhost
git add DNS_FIXO.txt CONECTAR_WINDOWS.txt 2>&1 | Out-Null
git commit -m "dns fixo $dns" 2>&1 | Out-Null
for ($i=0; $i -lt 4; $i++) {
  git pull --rebase -X theirs origin main 2>&1 | Out-Null
  git push origin HEAD:main 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { break }
  Start-Sleep -Seconds 3
}
"DNS_FIXO_PUBLICADO : $dns"
exit 0
