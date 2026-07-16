"""Retencao do arquivo original do upload manual.

Comeca local (pasta na VM, montada por fora do container). Plugavel: quando o
Entra ID for liberado, troca a implementacao pra gravar/ler no SharePoint via
Graph API sem mudar quem chama estas funcoes.
"""

import os
import uuid
from pathlib import Path

UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/app/data/uploads"))


def salvar_arquivo(conteudo: bytes, nome_original: str) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    nome_seguro = f"{uuid.uuid4().hex}_{Path(nome_original).name}"
    destino = UPLOADS_DIR / nome_seguro
    destino.write_bytes(conteudo)
    return str(destino)


def ler_arquivo(caminho: str) -> bytes:
    return Path(caminho).read_bytes()
