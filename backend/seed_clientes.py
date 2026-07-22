"""
Clientes de catering da família RMSP (Lote 7.1, POC catering — docs/PILOTO.md).

Fonte: docs/Analise/clientesDw.csv (NK_CLIENTE, RAZAO_SOCIAL; filtro DW_DATA_FINAL
começando com "2199" = registro vigente) cruzado com docs/Analise/ocupacaoComercial.csv
(contratos vigentes das filiais RMSPII = FK_FILIAL 45 e RMSPIII = FK_FILIAL 46, via
FK_CLIENTE) em 21/jul/2026 — nenhum dos dois vai pro git (docs/Analise/ está no
.gitignore), por isso os dados entram aqui como literais, mesmo padrão do
seed_depara.py.

8 clientes vieram do cruzamento direto com contrato (Sapore, GR, Wyda, Pimenta Verde,
Novita, Grupo Neffa, Sodexo, Bimbo). Os outros 3 (Convida, OG do Brasil, FLV 7) operam
sem contrato vigente na família (achado da análise de 21/jul — docs/PILOTO.md, pergunta
2) e foram localizados por nome em clientesDw.csv.

O segmento do DW está errado pra todos ("Ind. Química/Resinas/Tintas/Sintéticos") — por
isso a lista é curada aqui, não filtrada por segmento.

Tirolez, Delly, Frimesa e Irmãos Boa são contratos da RMSP (locação/posições), fora do
núcleo do catering RMSPII/RMSPIII — não entram aqui.
"""

# cada item: nk_erp = NK_CLIENTE do DW (chave que aparece no fato/comercial), nome de
# exibição (a partir da razão social) e catering=True (só clientes catering entram
# nesta tabela, por ora)
CLIENTES = [
    {"nk_erp": "67945071", "nome": "Sapore", "catering": True},
    {"nk_erp": "02905110", "nome": "GR Serviços e Alimentação", "catering": True},
    {"nk_erp": "04596502", "nome": "Wyda (Cucinare)", "catering": True},
    {"nk_erp": "09060964", "nome": "Pimenta Verde", "catering": True},
    {"nk_erp": "25080393", "nome": "Novita Alimentação", "catering": True},
    {"nk_erp": "00320017", "nome": "Grupo Neffa", "catering": True},
    {"nk_erp": "49930514", "nome": "Sodexo do Brasil Comercial", "catering": True},
    {"nk_erp": "35402759", "nome": "Bimbo do Brasil", "catering": True},
    {"nk_erp": "05599283", "nome": "Convida Refeições", "catering": True},
    {"nk_erp": "40340433", "nome": "OG do Brasil", "catering": True},
    {"nk_erp": "40720488", "nome": "FLV 7 Restaurantes", "catering": True},
]


def aplicar(cur):
    """Insere os clientes de catering. Idempotente: nunca sobrescreve um cliente já
    existente, mesma lógica de armazens/conectores em database.py."""
    for item in CLIENTES:
        cur.execute(
            """
            INSERT INTO clientes (nk_erp, nome, catering) VALUES (%s, %s, %s)
            ON CONFLICT (nk_erp) DO NOTHING
            """,
            (item["nk_erp"], item["nome"], item["catering"]),
        )
