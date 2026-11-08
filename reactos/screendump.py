"""Fala com o monitor QEMU por Unix socket, pede screendump e converte PPM -> PNG.

Nao depende de KVM, GPU, display ou X11. Funciona em QEMU TCG puro.
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


def fala(cmd, espera=1.0):
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


def ppm_para_png(caminho_ppm, caminho_png):
    with open(caminho_ppm, "rb") as f:
        dados = f.read()
    # P6\n<w> <h>\n<max>\n<pixels>
    partes = dados.split(b"\n", 3)
    if partes[0].strip() != b"P6":
        raise ValueError("nao e PPM P6: %r" % partes[0])
    w, h = [int(x) for x in partes[1].split()]
    maxv = int(partes[2].split()[0])
    px = partes[3]
    if maxv != 255:
        raise ValueError("maxval nao suportado: %d" % maxv)
    if len(px) < w * h * 3:
        raise ValueError("PPM truncado: %d < %d" % (len(px), w * h * 3))
    px = px[: w * h * 3]

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
    with open(caminho_png, "wb") as f:
        f.write(png)
    return w, h, len(png)


def main():
    limite = int(os.environ.get("ROS_ESPERA", "240"))
    inicio = time.time()
    ultimo = None
    while time.time() - inicio < limite:
        try:
            if os.path.exists(PPM):
                os.remove(PPM)
            fala("screendump %s" % PPM, espera=2.0)
            if os.path.exists(PPM) and os.path.getsize(PPM) > 1000:
                w, h, n = ppm_para_png(PPM, PNG)
                print("CAPTURA_OK %dx%d png=%d bytes" % (w, h, n))
                # prova de que nao e tela preta
                with open(PPM, "rb") as f:
                    d = f.read().split(b"\n", 3)[3]
                print("pixel_max=%d pixel_min=%d" % (max(d), min(d)))
                return 0
            ultimo = "screendump nao gerou arquivo ainda"
        except Exception as e:  # monitor ainda a abrir / PPM incompleto
            ultimo = repr(e)
        print("aguardando boot... %3ds  %s" % (int(time.time() - inicio), ultimo))
        time.sleep(10)
    print("FALHOU: %s" % ultimo)
    return 1


if __name__ == "__main__":
    sys.exit(main())
