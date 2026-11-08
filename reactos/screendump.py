"""Fala com o monitor QEMU, captura a tela e espera o DESKTOP aparecer.

QEMU TCG (sem KVM) e lento: a primeira captura costuma ser so a splash
preta com o logo. Este loop fica amostrando ate a tela ficar majoritariamente
nao-preta (fundo azul + barra de tarefas do ReactOS) e guarda a MELHOR.
"""
import os
import socket
import struct
import sys
import time
import zlib

SOCK = "/tmp/ros/mon.sock"
PPM = "/tmp/ros/frame.ppm"
PNG = "/tmp/ros/frame.png"


def fala(cmd, espera=2.0):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(6)
    s.connect(SOCK)
    try:
        s.recv(65536)  # banner (qemu)
    except socket.timeout:
        pass
    s.sendall((cmd + "\n").encode())
    time.sleep(espera)
    s.close()


def le_ppm():
    with open(PPM, "rb") as f:
        dados = f.read()
    partes = dados.split(b"\n", 3)
    if partes[0].strip() != b"P6":
        raise ValueError("nao e PPM P6")
    w, h = [int(x) for x in partes[1].split()]
    if int(partes[2].split()[0]) != 255:
        raise ValueError("maxval != 255")
    px = partes[3][: w * h * 3]
    if len(px) < w * h * 3:
        raise ValueError("PPM truncado")
    return w, h, px


def escreve_png(w, h, px, caminho):
    bruto = b"".join(
        b"\x00" + px[y * w * 3 : (y + 1) * w * 3] for y in range(h)
    )

    def chunk(tipo, corpo):
        return (
            struct.pack(">I", len(corpo))
            + tipo
            + corpo
            + struct.pack(">I", zlib.crc32(tipo + corpo) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bruto, 6))
    png += chunk(b"IEND", b"")
    with open(caminho, "wb") as f:
        f.write(png)
    return len(png)


def fracao_nao_preta(px):
    # amostra 1 a cada 12 pixels: conta quem tem algum canal > 30
    vivos = 0
    total = 0
    for i in range(0, len(px) - 3, 36):
        total += 1
        if px[i] > 30 or px[i + 1] > 30 or px[i + 2] > 30:
            vivos += 1
    return vivos / max(total, 1)


def main():
    limite = int(os.environ.get("ROS_ESPERA", "420"))
    inicio = time.time()
    melhor = -1.0
    ultimo_erro = None
    while time.time() - inicio < limite:
        try:
            if os.path.exists(PPM):
                os.remove(PPM)
            fala("screendump %s" % PPM)
            if os.path.exists(PPM) and os.path.getsize(PPM) > 1000:
                w, h, px = le_ppm()
                frac = fracao_nao_preta(px)
                decorrido = int(time.time() - inicio)
                if frac > melhor:
                    melhor = frac
                    n = escreve_png(w, h, px, PNG)
                    print(
                        "MELHOR t=%3ds %dx%d nao_preta=%.3f png=%d"
                        % (decorrido, w, h, frac, n)
                    )
                else:
                    print("t=%3ds nao_preta=%.3f (mantem anterior)" % (decorrido, frac))
                # desktop classico: fundo azul + taskbar -> quase tudo aceso
                if frac > 0.55 and decorrido >= 60:
                    print("DESKTOP_DETETADO")
                    return 0
            else:
                ultimo_erro = "screendump sem arquivo"
        except Exception as e:
            ultimo_erro = repr(e)
        print("aguardando... %s" % ultimo_erro)
        time.sleep(20)
    print("FIM sem desktop confirmado; melhor=%.3f" % melhor)
    return 0 if os.path.exists(PNG) else 1


if __name__ == "__main__":
    sys.exit(main())
