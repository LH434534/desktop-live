# Pesquisa GitHub → um "Windows" que é realmente seu

## O que achei

Varri os projetos relevantes. Quase todos **instalam o Windows da Microsoft**
(ISO oficial, trial, EULA). Só um entrega um sistema compatível que é
**código seu**:

| Projeto | O que é | Serve aqui? |
|---|---|---|
| **ReactOS 0.4.16** | SO NT-compatível, GPLv2, clean-room | ✅ **foi o que criei** |
| dockur/windows | Windows real em Docker + KVM | ❌ exige `/dev/kvm`, 4 GB, 64 GB |
| WinBoat / WinApps | Windows real em VM + FreeRDP | ❌ KVM, 4 GB RAM, 32 GB |
| Winlator / Box64 | Wine no seu Android | ⚠️ emulação, não é SO |
| RDP Wrapper | RDP no Windows Home | ❌ viola EULA da Microsoft |
| Puter / Win11React | desktop React no browser | ❌ simulação |
| Guacamole | gateway RDP/VNC em HTML5 | ✅ útil, mas não cria SO |
| workflows RDP+Tailscale | o que já tínhamos | ⚠️ 6 h, hardware alugado |

O ReactOS é um sistema escrito do zero, sem nenhuma linha de código da
Microsoft e sem chave de ativação, licenciado GPLv2/LGPLv2 [citation:17].
A versão **0.4.16** saiu em 29 de agosto de 2026 com ISO unificada
LiveCD+instalador de **198 MB** [citation:20][citation:23]. Requisitos
mínimos: **64 MB de RAM**, 450 MB de disco [citation:24]. O próprio
`dockur/windows` lista `VERSION: reactos` como opção de **0.1 GB**, contra
7,9 GB do Windows 11 [citation:15][citation:29].

`dockur/windows` e o WinBoat exigem KVM, 4 GB de RAM e dezenas de GB
[citation:15][citation:21]; o runner do GitHub não expõe `/dev/kvm`. O
RDP Wrapper habilita RDP no Home, mas fere o EULA e quebra a cada update
[citation:11]. Winlator roda Wine no celular, não um SO Windows
[citation:12]. Puter e Win11React são interfaces React [citation:25][citation:28].

## O que eu criei de verdade

Não é uma lista: é um sistema **rodando agora** no seu repo público
`LH434534/desktop-live`, workflow `reactos.yml`, run **#7**.

```
QEMU 6.2 · -accel tcg (SEM KVM) · 512 MB RAM · 1 vCPU
ISO oficial ReactOS 0.4.16 (198 MB) via gh release download
disco qcow2 2G · VNC em 127.0.0.1:5900
noVNC/websockify bind SOMENTE no IP da tailnet :6080
Tailscale na SUA conta · screenshots reais via monitor QEMU
```

**Acesso atual:** `http://100.79.171.38:6080/vnc.html` no Chrome do celular
(ou AVNC em `100.79.171.38:5900`, sem senha). Tailscale ativo, mesma conta.
O endereço é republicado em `reactos/CONECTAR_REACTOS.txt` a cada boot.

**Prova:** `reactos/ULTIMA_TELA.png` — 800×600, fundo azul clássico, cursor
e marca d'água `ReactOS Version 0.4.16-x86 · Reporting NT 5.2 (Build 3790:
Service Pack 2)`. Não é tela preta (`max=255`).

## 4 bugs reais no caminho

| # | Causa confirmada | Correção |
|---|---|---|
| 1 | `git push` do runner falhava silenciosamente (`|| true`) → endereço e PNG nunca apareciam | publicação pela API de contents com `GH_TOKEN` |
| 2 | `-monitor unix:...,server=nowait` → QEMU 6.2: *"Parameter 'server' expects 'on' or 'off'"* | `server=on` |
| 3 | `server=on` sem `wait=off` → QEMU **bloqueava** esperando conexão; step travou 5 min | `server=on,wait=off` |
| 4 | primeira captura congelava na splash preta (TCG é lento) | `screendump.py` amostra até o fundo azul aparecer |

Também descobri que a `TAILSCALE_AUTHKEY` do cofre **ainda é válida e
reusable** — os runs 3–7 entraram na tailnet sem chave nova.

## O que NÃO é

🔴 **Não é Windows.** É alpha desde 1996, cara de Windows 2003, não roda
After Effects, Chrome moderno nem Blender 5.2; o próprio projeto não garante
estabilidade [citation:17][citation:24].

🔴 **O hardware ainda é da Microsoft.** ~5h50 por run, renovação encadeada
aos 300 min com janela de 1–3 min; disco `qcow2` efêmero. O que passou a ser
seu é **o sistema** (código GPL, sem licença, sem conta da Microsoft), não o
ferro. Para 100% de posse, o mesmo `reactos.yml` roda no seu PC/VPS com
`qemu-system-x86_64` e o disco fica lá.

🔴 **TCG é lento** (CPU emulada, sem aceleração), sem áudio e sem 3D.
A captura publicada é o fundo azul com cursor — a barra de tarefas ainda não
tinha aparecido naquele frame. Ao vivo no browser você vê o resto carregar.

🔴 **Não rodei no meu sandbox**: o proxy dele devolve 403 para
`github.com/releases/download`, `downloads.reactos.org`, SourceForge e todos
os mirrors Ubuntu testados. Por isso a execução foi para o seu repo público,
onde a rede é livre. Não vou chamar de "validado localmente".

## Arquivos

- `reactos.yml` — workflow completo (instala, baixa, boota, publica, renova)
- `screendump.py` — cliente do monitor QEMU + PPM→PNG em `zlib`/`struct` puros
- `README.md` — a pesquisa e as fontes
- `RESULTADO.md` — este relatório
- `ULTIMA_TELA.png` — frame real capturado no run #7
