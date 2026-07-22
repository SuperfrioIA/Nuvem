"""Versionamento de modelos de importacao (Lote R1).

A configuracao/mapeamento de um modelo vive em `modelo_versoes`, uma linha por
VERSAO, IMUTAVEL: editar um modelo nunca altera uma versao existente -- cria uma
nova e move o ponteiro `padrao`. `modelos_importacao` guarda so a identidade
(nome, conector, fonte logica) e um espelho congelado da v1; a fonte da verdade
pro processamento e sempre a versao aqui.

- `padrao`: a versao usada por um upload novo (uma so por modelo, garantida por
  indice unico parcial).
- `ativo`: versao utilizavel; `padrao` exige `ativo` (CHECK no banco).
- `hash_config`: sha256 do mapeamento canonico. O MESMO algoritmo esta inline na
  migration 0002 (que cria a v1 dos modelos legados) -- se mudar aqui, os dois
  deixam de bater; ha teste travando essa igualdade.
"""

import hashlib
import json


def hash_mapeamento(mapeamento: dict) -> str:
    """sha256 do mapeamento em JSON canonico (chaves ordenadas). Deterministico
    e estavel. Igual ao _hash inline da migration 0002 (ver teste de igualdade)."""
    canonico = json.dumps(mapeamento, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def criar_versao(cur, modelo_id: int, mapeamento: dict, padrao: bool = True, ativo: bool = True) -> tuple[int, int]:
    """Cria uma versao nova (imutavel) do modelo. Numera na sequencia
    (max+1). Se `padrao`, tira o padrao das irmas antes. Nunca toca versao
    antiga. Devolve (versao_id, numero_versao)."""
    cur.execute("SELECT COALESCE(MAX(versao), 0) + 1 FROM modelo_versoes WHERE modelo_id = %s", (modelo_id,))
    numero = cur.fetchone()[0]

    if padrao:
        cur.execute("UPDATE modelo_versoes SET padrao = false WHERE modelo_id = %s AND padrao", (modelo_id,))

    cur.execute(
        """
        INSERT INTO modelo_versoes (modelo_id, versao, mapeamento, hash_config, ativo, padrao)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (modelo_id, numero, json.dumps(mapeamento), hash_mapeamento(mapeamento), ativo, padrao),
    )
    return cur.fetchone()[0], numero


def resolver_versao_padrao(cur, modelo_id: int) -> tuple[int, dict] | None:
    """A versao ativa/padrao do modelo (a que um upload novo usa). None se o
    modelo nao tem versao padrao ativa. Uma versao inativa nunca e retornada."""
    cur.execute(
        "SELECT id, mapeamento FROM modelo_versoes WHERE modelo_id = %s AND padrao AND ativo",
        (modelo_id,),
    )
    row = cur.fetchone()
    return (row[0], row[1]) if row else None


def carregar_versao(cur, versao_id: int) -> dict | None:
    """O mapeamento EXATO de uma versao (usado no reprocessamento, que amarra na
    versao da execucao original, nao na padrao atual)."""
    cur.execute("SELECT mapeamento FROM modelo_versoes WHERE id = %s", (versao_id,))
    row = cur.fetchone()
    return row[0] if row else None
