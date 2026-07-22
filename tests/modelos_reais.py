"""Os 5 mapeamentos REAIS dos modelos de importacao do Lote 8, para os testes.

Desde o Lote R1.1 a fonte da verdade UNICA e backend/seed_modelos.py (a imagem
Docker so copia `backend/`, entao os literais moram la e sao o que o seed de
banco novo grava como v1). Este modulo apenas re-exporta de la — garante que a
v1 semeada e o mapeamento usado nos testes sao byte a byte o mesmo objeto, sem
risco de divergencia.

Os DADOS dos testes seguem sinteticos (tests/arquivos_sinteticos.py): provam a
mecanica de parser/ingestao com estes mapeamentos, nao a qualidade do dado real.
"""

from backend.seed_modelos import (
    CAPACIDADE_HDR,
    MAPEAMENTOS,
    OCUPACAO_COMERCIAL,
    OCUPACAO_MANUAL,
    POS_SUM,
    VOLUMETRIA_FATO,
)

# alias historico usado pelos testes (mesmas chaves de arquivos_sinteticos.ARQUIVOS)
TODOS = MAPEAMENTOS

__all__ = [
    "POS_SUM",
    "CAPACIDADE_HDR",
    "OCUPACAO_COMERCIAL",
    "OCUPACAO_MANUAL",
    "VOLUMETRIA_FATO",
    "TODOS",
]
