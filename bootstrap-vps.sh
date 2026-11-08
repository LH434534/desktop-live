#!/usr/bin/env bash
# bootstrap-vps.sh — transforma um Ubuntu 22.04/24.04 seu em desktop permanente.
#
# RODA NO SEU VPS, como root. Nao roda no GitHub Actions.
#   export GH_TOKEN='github_pat_...'          # precisa de scope repo + workflow
#   export TAILSCALE_AUTHKEY='tskey-auth-...'
#   export VPS_PASSWORD='uma-senha-forte'     # senha RDP do usuario vpsuser
#   curl -fsSL <URL_RAW_DO_REPO>/bootstrap-vps.sh | bash
#   # ou: scp bootstrap-vps.sh root@IP:/root/ && ssh root@IP bash /root/bootstrap-vps.sh
#
# O que fica permanente: disco, XRDP, Tailscale, runner self-hosted.
# Nao depende de cota de minutos nem do teto de 6h de job.
set -euo pipefail

: "${GH_TOKEN:?defina GH_TOKEN}"
: "${TAILSCALE_AUTHKEY:?defina TAILSCALE_AUTHKEY}"
: "${VPS_PASSWORD:?defina VPS_PASSWORD}"

OWNER="${OWNER:-LH434534}"
REPO="${REPO:-desktop-live}"
HOST="vps-permanente"
API="https://api.github.com"

log() { printf '\n=== %s ===\n' "$*"; }

log "1/6 sistema base"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl jq ca-certificates gnupg ufw \
  xrdp xfce4 xfce4-goodies dbus-x11 x11-xserver-utils \
  python3 python3-pip

log "2/6 usuario RDP"
if ! id -u vpsuser >/dev/null 2>&1; then
  useradd -m -s /bin/bash -G sudo vpsuser
fi
echo "vpsuser:${VPS_PASSWORD}" | chpasswd
echo "startxfce4" > /home/vpsuser/.xsession
chown vpsuser:vpsuser /home/vpsuser/.xsession
systemctl enable --now xrdp
adduser xrdp ssl-cert || true
systemctl restart xrdp

log "3/6 firewall (3389 SOMENTE pela tailnet)"
ufw allow OpenSSH || ufw allow 22/tcp
ufw allow in on tailscale0 to any port 3389 proto tcp
ufw --force enable
# Nao abrimos 3389 para 0.0.0.0/0: o acesso e so pela tailnet.

log "4/6 Tailscale"
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
tailscale up --authkey="${TAILSCALE_AUTHKEY}" --hostname="${HOST}"
IP_TS="$(tailscale ip -4 | head -n1)"
echo "ip_tailnet: ${IP_TS}"

log "5/6 self-hosted runner (versao obtida da API, nada fixado)"
REG_JSON="$(curl -fsS -X POST \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  -H 'Accept: application/vnd.github+json' \
  "${API}/repos/${OWNER}/${REPO}/actions/runners/registration-token")"
REG_TOKEN="$(echo "${REG_JSON}" | jq -r .token)"
[ -n "${REG_TOKEN}" ] && [ "${REG_TOKEN}" != "null" ] || {
  echo "ERRO: nao consegui registration-token"; exit 1; }

REL_JSON="$(curl -fsS -H "Authorization: Bearer ${GH_TOKEN}" \
  "${API}/repos/actions/runner/releases/latest")"
TAG="$(echo "${REL_JSON}" | jq -r .tag_name)"
VER="${TAG#v}"
URL="https://github.com/actions/runner/releases/download/${TAG}/actions-runner-linux-x64-${VER}.tar.gz"

mkdir -p /opt/actions-runner && cd /opt/actions-runner
curl -fsSL -o runner.tar.gz "${URL}"
tar xzf runner.tar.gz && rm runner.tar.gz
./bin/installdependencies.sh

runuser -u vpsuser -- ./config.sh \
  --url "https://github.com/${OWNER}/${REPO}" \
  --token "${REG_TOKEN}" \
  --name "${HOST}" \
  --labels vps,permanente \
  --work _work --unattended --replace
./svc.sh install vpsuser
./svc.sh start

log "6/6 cartao de conexao"
cat > /home/vpsuser/CONECTAR_VPS.txt <<EOF
# DESKTOP PERMANENTE (Linux + XRDP, RDP nativo com audio)
App            : Windows App / RD Client
Host           : ${IP_TS}
Porta          : 3389
Usuario        : vpsuser
Senha          : (a que voce definiu em VPS_PASSWORD)
Sessao         : XFCE ( escolha Xorg / Xvfb se o cliente perguntar )
Tailscale      : mesma conta do celular
Validade       : NAO EXPIRA — disco e servicos locais
Repo           : ${OWNER}/${REPO} (workflow permanente.yml)
EOF
chown vpsuser:vpsuser /home/vpsuser/CONECTAR_VPS.txt
cat /home/vpsuser/CONECTAR_VPS.txt

log "PRONTO"
echo "xrdp       : $(systemctl is-active xrdp)"
echo "tailscaled : $(systemctl is-active tailscaled)"
echo "runner     : $(./svc.sh status | head -n3 | tr '\n' ' ')"
echo "Observacao : isto e Linux com XRDP, NAO Windows Server."
echo "             Para Windows real permanente, use um VPS Windows (licenca paga)."
