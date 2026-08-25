"""A fonte CSV -- o UNICO modulo do carregador que conhece o formato de entrada.

## Por que isto e uma classe com `extrair()`

O `V3_PLANO.md` inverte a ordem normal de propósito: o acesso ao Oracle e o
ultimo passo tecnico (V3.5), nao o primeiro. O que permite construir tudo
antes do acesso existir e esta costura:

    extrair()                   <- so ele conhece a fonte
    transformar() + carregar()  <- identico nos dois casos

E foi o que aconteceu no V3.5: `fonte_oracle.FonteOracle` tem o mesmo
`extrair(movimento, desde)`, e nem `transformacao.py` nem `destino.py`
mudaram uma linha. Duas coisas aqui existiam so para garantir isso, e sao as
que pagaram:

1. **`desde` ja esta na assinatura.** No CSV ele filtra em Python por
   `DW_DATA_ALTERACAO`; no Oracle vira `WHERE DW_DATA_ALTERACAO > :desde`. Se
   o parametro so aparecesse no V3.5, a troca mexeria na assinatura de todo
   mundo e deixaria de ser adaptador.
2. **`extrair()` devolve a linha CRUA**, com as chaves em maiusculas como o DW
   as nomeia. Coercao nao acontece aqui -- acontece em `transformacao.py`, que
   aceita texto e valor nativo. Se a fonte ja entregasse tipado, cada
   adaptador teria a sua propria copia da coercao, que e exatamente o que
   afunda a promessa.

## Medido nos dois arquivos de 21/ago/2026

UTF-8 **sem BOM**, CRLF, delimitador `;`, decimal com **ponto**, aspas em
parte dos campos (o leitor de CSV resolve). 36.300 linhas no recebimento e
42.468 na expedicao. Os acentos sao UTF-8 de verdade: a `GR SERVICOS`
aparece com tres grafias, uma delas com cedilha e til, e isso e dado real --
nao mojibake.

## Somente leitura

Os arquivos sao abertos em modo texto de leitura e nada mais. A disciplina e a
mesma que vale para o SharePoint do DataHub (`memory/
sharepoint-datahub-somente-leitura.md`): fonte nao se escreve. Ha teste
conferindo que mtime e tamanho nao mudam depois de uma carga completa.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path

from catering import contrato
from catering.carga import transformacao

logger = logging.getLogger(__name__)

# As extracoes de 21/ago/2026 do processo `catering_to_dw_volumetry_v01`.
ARQUIVO = {
    "rec": "dm_volumetriaRecebimento.csv",
    "exp": "dm_volumetriaExpedicao.csv",
}

DELIMITADOR = ";"
ENCODING = "utf-8"

# `cat_cargas.fonte` (migration 0020). O CHECK aceita 'csv' e 'oracle'.
NOME = "csv"


class FonteCSV:
    """As duas extracoes do DW num diretorio.

    `diretorio` e tipicamente `docs/Analise/`. A classe nao guarda arquivo
    aberto: `extrair()` abre, streama e fecha, para uma carga longa nao
    segurar descritor a mais do que precisa."""

    nome = NOME

    def __init__(self, diretorio):
        self.diretorio = Path(diretorio)

    def caminho(self, movimento) -> Path:
        if movimento not in ARQUIVO:
            raise KeyError(movimento)
        return self.diretorio / ARQUIVO[movimento]

    def descrever(self, movimento) -> str:
        """Uma linha de procedencia para o log -- arquivo e data em que foi
        salvo. Nao vai para o banco (lá fica `cat_cargas.fonte`), e existe
        porque afirmar de quando o dado e sem olhar o arquivo ja deu errado
        antes neste projeto."""
        caminho = self.caminho(movimento)
        if not caminho.exists():
            return f"{caminho} (ausente)"
        info = caminho.stat()
        salvo = datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M")
        return f"{caminho.name}, salvo em {salvo}, {info.st_size} bytes"

    def extrair(self, movimento, desde=None):
        """Gera as linhas cruas do movimento, na ordem do arquivo.

        Duas restricoes, as mesmas da `FonteOracle`, para que uma carga por
        CSV e uma por Oracle do mesmo periodo devolvam exatamente as mesmas
        linhas -- se as duas fontes divergirem no recorte, comparar uma com a
        outra deixa de provar qualquer coisa:

        `piso de periodo`: linha com `nk_calendario` antes de
        `contrato.piso_do_periodo()` nao sai daqui. Nos CSVs de 21/ago isto nao
        muda nada (eles sao 2026), e existe para nao divergir.

        `desde`: quando informado, so devolve linha com `DW_DATA_ALTERACAO`
        **maior** que ele -- a marca d'agua da rodada anterior
        (`cat_cargas.max_dw_data_alteracao`). Maior e nao maior-ou-igual de
        proposito: igual e a linha que a rodada anterior ja carregou, e
        reprocessa-la nao mudaria nada alem de inflar `linhas_lidas`.

        Gerador e nao lista: 78 mil linhas caberiam em memoria, mas a forma
        e a que o Oracle precisa, e forma que muda no V3.5 nao serve de nada.
        """
        caminho = self.caminho(movimento)
        if not caminho.exists():
            raise FileNotFoundError(f"extracao ausente: {caminho}")

        coluna_alteracao = (
            contrato.coluna_dw("dw_data_alteracao", movimento)
            if desde is not None
            else None
        )
        coluna_calendario = contrato.coluna_dw("nk_calendario", movimento)
        piso = contrato.piso_do_periodo()

        with caminho.open(encoding=ENCODING, newline="") as arquivo:
            leitor = csv.DictReader(arquivo, delimiter=DELIMITADOR)
            # O cabecalho e conferido contra o contrato antes da primeira
            # linha: cabecalho errado tem que falhar aqui, com o nome da
            # coluna, e nao 30 mil linhas adiante com erro de tipo.
            transformacao.conferir_colunas(leitor.fieldnames or (), movimento)
            for linha in leitor:
                # O piso primeiro: e o recorte de escopo, e nao depende de
                # rodada anterior nenhuma.
                movimentada_em = transformacao.dia(linha.get(coluna_calendario))
                if movimentada_em is None or movimentada_em < piso:
                    continue
                if coluna_alteracao is not None:
                    alterada_em = transformacao.instante(linha.get(coluna_alteracao))
                    if alterada_em is None or alterada_em <= desde:
                        continue
                yield linha
