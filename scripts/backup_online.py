"""Encrypted, offline backup and isolated restore for the online portal."""

import argparse
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
from getpass import getpass
from pathlib import Path, PurePosixPath

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidTag

from database import store
from services import documents


MAGIC = b"TLABBACKUP1"
CHUNK = 1024 * 1024


def _sha256_stream(stream):
    digest = hashlib.sha256()
    while chunk := stream.read(CHUNK):
        digest.update(chunk)
    return digest.hexdigest()


def _key(passphrase, salt):
    if len(passphrase) < 12:
        raise ValueError("A senha do backup deve ter ao menos 12 caracteres.")
    return hash_secret_raw(passphrase.encode("utf-8"), salt, time_cost=2,
                           memory_cost=19456, parallelism=1, hash_len=32, type=Type.ID)


def _members(root, prefix):
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Diretório de backup indisponível: {prefix}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Backup não aceita links simbólicos.")
        if path.is_file():
            yield path, f"{prefix}/{path.relative_to(root).as_posix()}"


def _archive(data_root, docs_root, destination):
    digest_map = {}
    with tarfile.open(destination, "w:gz") as archive:
        for root, prefix in ((data_root, "data"), (docs_root, "reference_docs")):
            for path, name in _members(root, prefix):
                with path.open("rb") as stream:
                    digest_map[name] = _sha256_stream(stream)
                archive.add(path, arcname=name, recursive=False)
        payload = json.dumps({"version": 1, "files": digest_map}, sort_keys=True).encode("utf-8")
        entry = tarfile.TarInfo("manifest.json")
        entry.size = len(payload)
        archive.addfile(entry, io.BytesIO(payload))
    return len(digest_map)


def _snapshot_root(source, destination, prefix):
    destination.mkdir(parents=True, exist_ok=True)
    for path, name in _members(source, prefix):
        if path.name.endswith(("-wal", "-shm", "-journal")):
            continue
        target = destination / Path(*PurePosixPath(name).parts[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".db":
            store.backup_sqlite_file(path, target)
        else:
            shutil.copy2(path, target)


def _encrypt(source, destination, passphrase):
    salt, nonce = os.urandom(16), os.urandom(12)
    cipher = Cipher(algorithms.AES(_key(passphrase, salt)), modes.GCM(nonce)).encryptor()
    with source.open("rb") as input_file, destination.open("xb") as output_file:
        output_file.write(MAGIC + salt + nonce)
        while chunk := input_file.read(CHUNK):
            output_file.write(cipher.update(chunk))
        output_file.write(cipher.finalize())
        output_file.write(cipher.tag)
    os.chmod(destination, 0o600)


def create_backup(data_root, docs_root, output, passphrase):
    data_root, docs_root, output = Path(data_root).resolve(), Path(docs_root).resolve(), Path(output).resolve()
    if output.is_relative_to(data_root) or output.is_relative_to(docs_root):
        raise ValueError("Guarde o backup fora dos diretórios copiados.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("O arquivo de backup já existe.")
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp) / "stage"
        _snapshot_root(data_root, stage / "data", "data")
        _snapshot_root(docs_root, stage / "reference_docs", "reference_docs")
        archive_path = Path(temp) / "snapshot.tar.gz"
        count = _archive(stage / "data", stage / "reference_docs", archive_path)
        _encrypt(archive_path, output, passphrase)
    return count


def _decrypt(source, destination, passphrase):
    size = source.stat().st_size
    header_size = len(MAGIC) + 16 + 12
    if size < header_size + 16:
        raise ValueError("Backup inválido.")
    with source.open("rb") as input_file:
        header = input_file.read(header_size)
        if not header.startswith(MAGIC):
            raise ValueError("Formato de backup inválido.")
        salt = header[len(MAGIC):len(MAGIC) + 16]
        nonce = header[len(MAGIC) + 16:]
        input_file.seek(size - 16)
        tag = input_file.read(16)
        input_file.seek(header_size)
        cipher = Cipher(algorithms.AES(_key(passphrase, salt)), modes.GCM(nonce, tag)).decryptor()
        remaining = size - header_size - 16
        try:
            with destination.open("wb") as output_file:
                while remaining:
                    chunk = input_file.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ValueError("Backup truncado.")
                    output_file.write(cipher.update(chunk))
                    remaining -= len(chunk)
                output_file.write(cipher.finalize())
        except InvalidTag:
            destination.unlink(missing_ok=True)
            raise ValueError("Senha incorreta ou backup alterado.") from None


def _validate_tar(archive):
    entries = archive.getmembers()
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)) or names.count("manifest.json") != 1:
        raise ValueError("Manifesto duplicado ou ausente.")
    manifest = json.load(archive.extractfile("manifest.json"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Manifesto inválido.")
    if set(names) != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Lista de arquivos divergente.")
    for entry in entries:
        if not entry.isfile():
            raise ValueError("Tipo de arquivo não permitido.")
        if entry.name == "manifest.json":
            continue
        name = PurePosixPath(entry.name)
        if (name.is_absolute() or ".." in name.parts or len(name.parts) < 2
                or name.parts[0] not in {"data", "reference_docs"}
                or "\\" in entry.name or ":" in entry.name):
            raise ValueError("Caminho inseguro no backup.")
        if _sha256_stream(archive.extractfile(entry)) != manifest["files"][entry.name]:
            raise ValueError("Hash divergente no backup.")
    return manifest


def verify_backup(source, passphrase, restore_to=None):
    source = Path(source)
    with tempfile.TemporaryDirectory() as temp:
        archive_path = Path(temp) / "snapshot.tar.gz"
        _decrypt(source, archive_path, passphrase)
        with tarfile.open(archive_path, "r:gz") as archive:
            manifest = _validate_tar(archive)
            if restore_to is not None:
                target = Path(restore_to).resolve()
                if target.exists() and any(target.iterdir()):
                    raise ValueError("O destino de restauração deve estar vazio.")
                target.mkdir(parents=True, exist_ok=True)
                for name in manifest["files"]:
                    destination = target.joinpath(*PurePosixPath(name).parts)
                    if not destination.resolve().is_relative_to(target):
                        raise ValueError("Caminho inseguro no backup.")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open("xb") as output_file:
                        shutil.copyfileobj(archive.extractfile(name), output_file, CHUNK)
    return len(manifest["files"])


def main():
    parser = argparse.ArgumentParser(description="Backup cifrado do portal, com app parado")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", metavar="FILE")
    group.add_argument("--verify", metavar="FILE")
    group.add_argument("--restore", metavar="FILE")
    parser.add_argument("--to", metavar="EMPTY_DIR", help="Destino vazio de restauração")
    parser.add_argument("--data-dir", default=str(store.DB_PATH.parent))
    parser.add_argument("--docs-dir", default=str(documents.REFERENCE_ROOT))
    args = parser.parse_args()
    if args.restore and not args.to:
        parser.error("--restore exige --to")
    passphrase = getpass("Senha do backup: ")
    if args.create:
        confirmation = getpass("Confirme a senha do backup: ")
        if confirmation != passphrase:
            raise SystemExit("As senhas não coincidem.")
        count = create_backup(args.data_dir, args.docs_dir, args.create, passphrase)
    else:
        count = verify_backup(args.verify or args.restore, passphrase, args.to)
    print(f"Concluído: {count} arquivos verificados.")


if __name__ == "__main__":
    main()
