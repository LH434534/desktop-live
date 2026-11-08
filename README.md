# desktop-live

Repo **publico** para o desktop remoto. Runners standard em repositorios
publicos nao consomem a cota de minutos do plano Free — foi isso que
destravou depois que a conta privada esgotou o limite.

## Conectar (Windows via RDP)

- App: **Windows App / RD Client** (Microsoft)
- Host: o IP `100.x` publicado em `CONECTAR_WINDOWS.txt` (porta 3389)
- Usuario: `winuser`
- Senha: **nao fica no repo** — e um Actions secret, informada no chat

Requisito: Tailscale ativo no celular, na mesma conta.

## Workflows

- `conectar-windows.yml` — Windows Server 2025 real, RDP nativo, Tailscale,
  heartbeat a cada 10 min, auto-reparo e renovacao encadeada (~5h15)
- `watchdog-windows.yml` — Linux, entra na tailnet e faz handshake X.224 real
- `health.yml` — prova minima de que o runner publico executa

Nenhuma chave ou senha e commitada neste repo. Os valores ficam em
**Settings -> Secrets and variables -> Actions**.

O repo antigo `plasma-desktop-sandbox` continua privado e parado.

## Persistencia (novo)

`cofre.py` cifra `Desktop` / `Documents` / `Downloads` com AES-256-GCM e
grava `estado.cofre` neste repo. O `conectar-windows.yml` restaura no boot e
salva a cada 10 min — os arquivos sobrevivem a morte do runner. A passphrase
e o secret `COFRE_PASSPHRASE`; sem ela o `.cofre` e ruido.

`cofre-teste.yml` valida o ciclo completo num runner real. `bootstrap-vps.sh`
e o caminho para 24/7 definitivo (veja `PERMANENTE.md`).
