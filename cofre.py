#!/usr/bin/env python3
"""cofre.py — persiste diretorios do usuario entre boots efêmeros.

O runner do GitHub morre a cada ~6h e o disco vai junto. Este utilitario
empacota Desktop/Documents/Downloads num tar, cifra com AES-256-GCM
(chave derivada por PBKDF2-HMAC-SHA256, 200k iteracoes) e grava um unico
arquivo .cofre que PODE ir para um repo publico: sem a passphrase, e ruido.

Uso:
  python cofre.py save    --src DIR --out ARQUIVO.cofre --pass PASSPHRASE
  python cofre.py restore --src ARQUIVO.cofre --out DIR --pass PASSPHRASE
  python cofre.py info    --src ARQUIVO.cofre --pass PASSPHRASE

Nunca inclui AppData, .ssh, chaves ou arquivos acima de --max-mb.
A extracao e segura contra path traversal (nada de ../ saindo do destino).
"""
import argparse
import io
import os
import secrets
import sys
import tarfile
import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"COFRE1"
SALT_LEN = 16
NONCE_LEN = 12
ITERATIONS = 200_000
EXCLUDE_DIRS = {
    "AppData", ".ssh", ".aws", ".config", "node_modules", "__pycache__",
    ".git", ".cache", ".local", "Temp", "Temporary Internet Files",
}
EXCLUDE_EXT = {".tmp", ".log", ".crdownload", ".part", ".lock"}


def derive(passphrase: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    ).derive(passphrase.encode("utf-8"))


def collect(src: str, max_bytes: int, only=None):
    """Tar em memoria. Arquivos grandes e pastas sensiveis ficam de fora."""
    if only:
        raizes = [os.path.join(src, d) for d in only
                  if os.path.isdir(os.path.join(src, d))]
    else:
        raizes = [src]
    buf = io.BytesIO()
    n, skipped, total = 0, 0, 0
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for raiz in raizes:
            for root, dirs, files in os.walk(raiz):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for name in sorted(files):
                    path = os.path.join(root, name)
                    if os.path.splitext(name)[1].lower() in EXCLUDE_EXT:
                        continue
                    try:
                        size = os.path.getsize(path)
                    except OSError:
                        continue
                    if size > max_bytes:
                        skipped += 1
                        continue
                    if total + size > max_bytes * 8:  # teto do pacote inteiro
                        skipped += 1
                        continue
                    # arcname relativo a src preserva "Desktop/...", "Documents/..."
                    tar.add(path, arcname=os.path.relpath(path, src))
                    total += size
                    n += 1
    return buf.getvalue(), n, skipped, total


def save(src: str, out: str, passphrase: str, max_mb: int, only=None) -> dict:
    raw, n, skipped, total = collect(src, max_mb * 1024 * 1024, only)
    salt = secrets.token_bytes(SALT_LEN)
    nonce = secrets.token_bytes(NONCE_LEN)
    blob = MAGIC + salt + nonce + AESGCM(derive(passphrase, salt)).encrypt(nonce, raw, None)
    with open(out, "wb") as f:
        f.write(blob)
    return {"arquivos": n, "ignorados": skipped, "bytes_plain": total,
            "bytes_cifrado": len(blob), "saida": out}


def load(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("formato invalido (magic ausente)")
    pos = len(MAGIC)
    salt = blob[pos:pos + SALT_LEN]
    nonce = blob[pos + SALT_LEN:pos + SALT_LEN + NONCE_LEN]
    ct = blob[pos + SALT_LEN + NONCE_LEN:]
    # InvalidTag (senha errada / arquivo corrompido) sobe como excecao.
    return AESGCM(derive(passphrase, salt)).decrypt(nonce, ct, None)


def restore(src: str, out: str, passphrase: str) -> dict:
    with open(src, "rb") as f:
        raw = load(f.read(), passphrase)
    os.makedirs(out, exist_ok=True)
    destino = os.path.realpath(out)
    n = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
        for member in tar.getmembers():
            alvo = os.path.realpath(os.path.join(destino, member.name))
            if not (alvo == destino or alvo.startswith(destino + os.sep)):
                raise ValueError("path traversal bloqueado: " + member.name)
            if member.isdir():
                os.makedirs(alvo, exist_ok=True)
            elif member.isfile():
                os.makedirs(os.path.dirname(alvo), exist_ok=True)
                with tar.extractfile(member) as fsrc, open(alvo, "wb") as fdst:
                    fdst.write(fsrc.read())
                n += 1
    return {"arquivos_restaurados": n, "destino": destino}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["save", "restore", "info"])
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--pass", dest="pw", default=os.environ.get("COFRE_PASS", ""))
    p.add_argument("--max-mb", type=int, default=35)
    p.add_argument("--only", default="",
                   help="subpastas separadas por virgula (Desktop,Documents,Downloads)")
    a = p.parse_args()
    if not a.pw:
        print("ERRO: passphrase ausente (--pass ou COFRE_PASS)", file=sys.stderr)
        return 2
    only = [x.strip() for x in a.only.split(",") if x.strip()] or None
    t0 = time.time()
    try:
        if a.cmd == "save":
            r = save(a.src, a.out, a.pw, a.max_mb, only)
        elif a.cmd == "restore":
            r = restore(a.src, a.out, a.pw)
        else:
            with open(a.src, "rb") as f:
                raw = load(f.read(), a.pw)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as t:
                r = {"arquivos": len(t.getmembers()), "bytes_plain": len(raw)}
        r["segundos"] = round(time.time() - t0, 2)
        for k, v in r.items():
            print(f"{k}: {v}")
        return 0
    except Exception as e:
        print(f"ERRO: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
