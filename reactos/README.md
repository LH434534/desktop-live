# Pesquisa GitHub: o que dá para criar de "Windows" sem licença da Microsoft

Pedido: *"tente pesquisar coisas no GitHub tipo Windows, coisas que dá pra você criar um"*.

Varri os projetos mais relevantes. A distinção que resolve tudo: **quase todos
instalam o Windows da Microsoft** (ISO oficial, trial/ativação, EULA). Só um
projeto entrega um sistema compatível que é **código seu**, de verdade.

| Projeto | O que é | Roda aqui? |
|---|---|---|
| **ReactOS** | SO NT-compatível, GPLv2, clean-room, sem código Microsoft | ✅ **sim**, 198 MB, 64 MB RAM |
| dockur/windows | Windows real em Docker, baixa ISO oficial | ❌ exige `/dev/kvm` + licença |
| WinBoat / WinApps | Windows real em VM + FreeRDP no Linux | ❌ exige KVM, 4 GB, 32 GB |
| Winlator / Box64 | Wine + Box64 no **seu celular Android** | ⚠️ não é Windows, é emulação |
| RDP Wrapper | habilita RDP no Windows Home | ❌ viola EULA, não recomendado |
| Puter / Win11React | desktop "Windows" em React no browser | ❌ simulação, não é SO |
| Apache Guacamole | gateway RDP/VNC em HTML5 | ✅ útil como porta, não cria SO |
| workflows RDP+Tailscale | Windows Server em Actions (o que já tínhamos) | ⚠️ 6 h, hardware alugado |

## O achado

**ReactOS 0.4.16** (29 ago 2026) é um sistema operacional escrito do zero,
compatível com aplicações e drivers Windows NT, **GPLv2/LGPLv2**, sem nenhuma
linha de código da Microsoft e sem chave de ativação. ISO unificada
LiveCD+instalador: **198 MB**. Requisitos mínimos oficiais: **64 MB de RAM**
(256 MB recomendado), **450 MB de disco**, CPU x86, VGA VESA.

E o `dockur/windows` lista `VERSION: reactos` como opção de **0.1 GB** —
confirma que o projeto é leve o bastante para caber onde o Windows 11 (7,9 GB)
não cabe.

👉 Isso muda a natureza da posse: o **sistema** é seu (você pode ler, modificar,
redistribuir e compilar o fonte). O Windows Server do runner, não: é licenciado
pela Microsoft e some com a máquina.

⚠️ **Não é Windows.** Está em alpha desde 1996, tem cara de Windows 2003, não
roda After Effects, Chrome moderno nem Blender 5.2, e o próprio projeto avisa
que não garante estabilidade. É um "Windows que é seu" no sentido de **SO
compatível e livre**, não no sentido de produto Microsoft.

## Como foi criado aqui

`reactos.yml` roda no **seu** repo público `desktop-live` (sem cota de minutos):

1. `apt` → `qemu-system-x86`, `novnc`, `websockify`
2. `gh release download 0.4.16-release --repo reactos/reactos` → ISO oficial
3. QEMU com **`-accel tcg`** (sem KVM — o runner não tem `/dev/kvm`)
4. `-vnc 127.0.0.1:0` + `websockify` **bind apenas no IP da tailnet** → a 6080
   não escuta na internet pública
5. `screendump.py` fala com o monitor QEMU e prova a tela com PNG real
6. coração com relógio real + sucessor aos 300 min (não repete o bug do
   `$t += 60`)

## Conectar

Leia `reactos/CONECTAR_REACTOS.txt` (publicado pelo próprio runner):

- **Chrome do celular:** `http://100.x.y.z:6080/vnc.html`
- **AVNC:** `100.x.y.z:5900` (sem senha; só a sua tailnet alcança)
- Tailscale ativo, mesma conta

## Limites honestos

- Hardware ainda é runner da Microsoft → ~5h50 por execução, renovação
  encadeada com janela de 1–3 min.
- Disco `qcow2` é efêmero neste runner; se quiser permanência, o mesmo
  `reactos.yml` roda num VPS/PC seu com `qemu-system-x86_64` e o disco fica.
- TCG é **lento** (emulação de CPU, sem aceleração de hardware).
- Sem áudio e sem aceleração 3D.
- Não tentei baixar o ISO dentro do meu sandbox: o proxy dele devolve 403 para
  `github.com/releases/download`, `downloads.reactos.org`, SourceForge e
  todos os mirrors Ubuntu testados. Por isso a execução foi para o seu repo,
  onde a rede é livre — e não vou fingir que rodei localmente.

## Fontes

- https://reactos.org/ · https://www.reactos.org/wiki/index.php/FAQ
- https://github.com/reactos/reactos/releases/tag/0.4.16-release
- https://github.com/dockur/windows
- https://github.com/winboat-org/winboat · https://github.com/winapps-org/winapps
- https://github.com/brunodev85/winlator
- https://github.com/stascorp/rdpwrap
- https://github.com/HeyPuter/puter · https://github.com/blueedgetechno/win11React
- https://guacamole.apache.org/
