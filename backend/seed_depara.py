"""
De-para oficial das filiais SF (Lote 7).

Fonte: docs/analise/saida/depara_e_relacoes.xlsx (aba depara_filial) cruzado com
"Empresas Grupo Superfrio 5 (Filiais Ativas).csv" em 17/jul/2026 — nenhum dos dois
vai pro git (docs/analise/ está no .gitignore), por isso os dados entram aqui como
literais.

Achados da conferência: o código ERP da JAC na planilha original (001007) não existe
no cadastro oficial — corrigido pra 001008. Cinco filiais têm sigla operacional (WMS)
diferente da sigla do cadastro oficial, mesma empresa (CNPJ e código batendo): CVDI/CVD,
MAQ/MAQII, SSA/SSAI, RMSP/RMSPI, POA/POAI — a sigla operacional fica como `sigla` do
armazém (é como o projeto já fala delas), a do cadastro vira apelido extra. RPIII, MRS
e CWBI não aparecem no cadastro de filiais ativas (MRS está sem volumetria desde
02/2023, marcada inativa).

Conferência de 03/ago/2026 (Maria, contra o cadastro oficial), corrigindo o que ficou
impreciso no Lote 7:

- **CWBI é pré-operacional de verdade** e passou a `ativo=False`: não está no cadastro
  de ativas, não tem CNPJ e não tem volumetria (`fato.csv`). O único vestígio dela é o
  cadastro de capacidade do DW (`camaras_por_filial.csv`: filial 74, uma câmara de
  congelado). O apelido `001995` foi REMOVIDO — não é código Protheus válido. Ele vinha
  de uma linha pela metade da tabela de de-para do DW (`filiais.csv`, registro 2940 de
  20/11/2020: `ERP PROTHEUS FILIAL = 001995` com `WMS JDA WH ID` em branco, cluster
  "New Stores"), e o pareamento com CWBI foi inferência do Lote 7, não dado da fonte.
- **RPIII não é pré-operacional** — é filial real desativada: código `001006`, CNPJ
  02.060.862/0006-40, Ribeirão Preto/SP, situação cadastral INATIVO. O DW tem o de-para
  completo dela (`001006 ↔ RPIII`, segmento SEMENTES) e a exclui do KPI de ocupação.
  Passou a `ativo=False` e ganhou o CNPJ como apelido (autorizado pela Maria em
  03/ago/2026). Consequência declarada: ela sai de toda tela que filtra por armazém
  ativo — é o que "inativa" significa, e o histórico dela continua consultável.
- **CWBIV faltava no cadastro**: `001034`, CNPJ 02.060.862/0034-01, São José dos
  Pinhais/PR, ATIVA no cadastro oficial com situação operacional "SEM OPERAÇÃO".

ICE (Chile) fica fora por ora — não existe de-para ERP×WMS pra elas.

Dicionário de códigos da análise (documentação, não vira tabela — reaproveitar quando
os modelos de importação do Lote 8 forem montados):
- FK_TIPO_TEMPERATURA: 2=CL (Climatizado), 3=CG (Congelado), 4=RF (Resfriado), 5=SC (Seco)
- FK_TIPO_ESTRUTURA: 2=Blocado (BLC), 3=Drive-In (DRV), 4=Porta-Palete (PPA); 1/5/6 não
  confirmados (candidatos: antecâmara, push-back, unitária)
- FK_TIPO_LOCAL_ARM: 1=Câmara, 2=Antecâmara
- TIPO_ACORDO: P=Posições contratadas, L=Locação de câmara, O=indefinido (filiais 12 e 27)
"""

# cada item: sigla oficial (vira armazens.sigla), nome de exibição, ativo, e a lista de
# apelidos (armazem_na_fonte) que devem resolver pra ela — sigla, código(s) WMS/JDA,
# código ERP Protheus, CNPJ e, quando existir, a sigla do cadastro oficial.
ARMAZENS = [
    {"sigla": "VGS", "nome": "Vargem Grande do Sul/SP", "ativo": True,
     "apelidos": ["VGS", "001001", "02060862000135"]},
    {"sigla": "MGG", "nome": "Mogi Guaçu/SP", "ativo": True,
     "apelidos": ["MGG", "001002", "02060862000216"]},
    {"sigla": "RPI", "nome": "Ribeirão Preto/SP", "ativo": True,
     "apelidos": ["RPI", "001003", "02060862000305"]},
    {"sigla": "RPII", "nome": "Ribeirão Preto/SP", "ativo": True,
     "apelidos": ["RPII", "SFS1", "001005", "02060862000569"]},
    # filial real DESATIVADA (nao pre-operacional, como o Lote 7 supos) --
    # conferida no cadastro oficial em 03/ago/2026
    {"sigla": "RPIII", "nome": "Ribeirão Preto/SP", "ativo": False,
     "apelidos": ["RPIII", "001006", "02060862000640"]},
    {"sigla": "JAC", "nome": "Jacareí/SP", "ativo": True,
     "apelidos": ["JAC", "001008", "02060862000801"]},
    {"sigla": "ARP", "nome": "Arapongas/PR", "ativo": True,
     "apelidos": ["ARP", "ARAP", "001010", "02060862001026"]},
    {"sigla": "MLA", "nome": "Vera Cruz/SP", "ativo": True,
     "apelidos": ["MLA", "001012", "02060862001298"]},
    {"sigla": "LDNI", "nome": "Cambé/PR", "ativo": True,
     "apelidos": ["LDNI", "LDN", "001013", "02060862001379"]},
    {"sigla": "MRS", "nome": "MRS", "ativo": False,
     "apelidos": ["MRS", "001014", "02060862001450"]},
    {"sigla": "CGD", "nome": "Campo Grande/MS", "ativo": True,
     "apelidos": ["CGD", "001017", "02060862001700"]},
    {"sigla": "CVDI", "nome": "Campo Verde/MT", "ativo": True,
     "apelidos": ["CVDI", "CVD", "001018", "02060862001883"]},
    {"sigla": "LDNII", "nome": "Cambé/PR", "ativo": True,
     "apelidos": ["LDNII", "001019", "02060862001964"]},
    {"sigla": "MAQ", "nome": "Mairinque/SP", "ativo": True,
     "apelidos": ["MAQ", "MAQII", "004003", "57046955000369"]},
    {"sigla": "ITA", "nome": "Garuva/SC", "ativo": True,
     "apelidos": ["ITA", "001030", "02060862003070"]},
    {"sigla": "CCV", "nome": "Cascavel/PR", "ativo": True,
     "apelidos": ["CCV", "006001", "33018974000151"]},
    {"sigla": "SSA", "nome": "Simões Filho/BA", "ativo": True,
     "apelidos": ["SSA", "SSAI", "007001", "08301904000169"]},
    {"sigla": "RMSP", "nome": "São Paulo/SP", "ativo": True,
     "apelidos": ["RMSP", "RMSPI", "001020", "02060862002006", "30"]},
    {"sigla": "CGB", "nome": "Cuiabá/MT", "ativo": True,
     "apelidos": ["CGB", "001023", "02060862002340"]},
    {"sigla": "CWBII", "nome": "São José dos Pinhais/PR", "ativo": True,
     "apelidos": ["CWBII", "001025", "02060862002502"]},
    {"sigla": "MAO", "nome": "Manaus/AM", "ativo": True,
     "apelidos": ["MAO", "001024", "02060862002421"]},
    {"sigla": "BEL", "nome": "Benevides/PA", "ativo": True,
     "apelidos": ["BEL", "001026", "02060862002693"]},
    {"sigla": "CWBIII", "nome": "São José dos Pinhais/PR", "ativo": True,
     "apelidos": ["CWBIII", "001029", "02060862002936"]},
    # conferida em 03/ago/2026: estava no cadastro oficial de ativas e faltava aqui
    {"sigla": "CWBIV", "nome": "São José dos Pinhais/PR", "ativo": True,
     "apelidos": ["CWBIV", "001034", "02060862003401"]},
    {"sigla": "RMSPII", "nome": "Barueri/SP", "ativo": True,
     "apelidos": ["RMSPII", "008001", "06975242000187", "45"]},
    # CORRIGIDO em 18/ago/2026: nao e mais destino do de-para de RMSPII/015.
    # O Protheus dela continua sendo o proprio 008002/CNPJ ...0002-68 (o
    # cadastro nao mudou) -- decisao de negocio da Maria e que a exibicao do
    # projeto trata 001/015/016 todas como RMSPII, igual a visao da
    # controladoria. RMSPIII continua cadastrada (uso real em
    # ocupacao/capacidade, FK_FILIAL=46). Observacao do cadastro Protheus:
    # esse CNPJ (...0002-68) so aceita SECO -- bate com "SECO da Sodexo" ja
    # registrado, e a operacao encerrou no mes anterior a 30/jul/2026.
    {"sigla": "RMSPIII", "nome": "Barueri/SP", "ativo": False,
     "apelidos": ["RMSPIII", "008002", "06975242000268", "46"]},
    {"sigla": "RMRJ", "nome": "Duque de Caxias/RJ", "ativo": True,
     "apelidos": ["RMRJ", "008004", "06975242000420"]},
    {"sigla": "POA", "nome": "Nova Santa Rita/RS", "ativo": True,
     "apelidos": ["POA", "POAI", "001027", "02060862002774"]},
    {"sigla": "POAII", "nome": "Canoas/RS", "ativo": True,
     "apelidos": ["POAII", "001031", "02060862003150"]},
    {"sigla": "BSB", "nome": "Brasília/DF", "ativo": True,
     "apelidos": ["BSB", "010001", "01456021000189"]},
    {"sigla": "GYN", "nome": "Aparecida de Goiânia/GO", "ativo": True,
     "apelidos": ["GYN", "010003", "01456021000340"]},
    {"sigla": "UDI", "nome": "Uberlândia/MG", "ativo": True,
     "apelidos": ["UDI", "010004", "01456021000421"]},
    # pre-operacional: sem CNPJ, sem volumetria e sem codigo Protheus valido
    # (o `001995` saiu em 03/ago/2026 -- ver docstring)
    {"sigla": "CWBI", "nome": "CWBI", "ativo": False,
     "apelidos": ["CWBI"]},
    # Lote 8 (22/jul/2026): "30"/"45"/"46" acima são o FK_FILIAL numérico do DW usado
    # por ocupacaoComercial.csv e ocupacaoManual.csv (STG_OCUPACAO_COM_V03/
    # STG_OCUPACAO_MANUAL_V03) -- essas duas fontes não usam a sigla WMS como o fato e
    # o pos_sum, usam a chave numérica. Confirmado nos dados reais: soma de
    # OCUPACAO_POSICAO_QTD com FK_FILIAL=46 bate com o achado de 9.773 posições
    # contratadas da RMSPIII (analise_rmsp.xlsx).

    # Lote 7.1 (21/jul/2026, POC catering RMSP): RMSPV nasceu no WMS em 14/jul/2026,
    # ainda sem capacidade/contrato/volumetria — ativa e vazia. RMSPIV foi cadastrada
    # aqui como inativa (nunca tinha aparecido em fonte do DW), mas em 30/jul/2026
    # a Maria confirmou que ela está ativa de verdade (filial 016 do SharePoint
    # DataHub -- a de maior volumetria da POC) -- corrigido pra ativo=True.
    # RMSPIII (filial 015, SECO da Sodexo) encerrou operação no mês anterior a
    # 30/jul/2026 -- corrigida pra ativo=False (estava True desde o Lote 7).
    {"sigla": "RMSPV", "nome": "Barueri/SP", "ativo": True,
     "apelidos": ["RMSPV", "008009", "06975242000934"]},
    # CORRIGIDO em 18/ago/2026: nao e mais destino do de-para de RMSPII/016.
    # O Protheus dela continua sendo o proprio 008003/CNPJ ...0003-49 (o
    # cadastro nao mudou) -- decisao de negocio da Maria e que a exibicao do
    # projeto trata 001/015/016 todas como RMSPII, igual a visao da
    # controladoria.
    {"sigla": "RMSPIV", "nome": "Barueri/SP", "ativo": True,
     "apelidos": ["RMSPIV", "008003", "06975242000349"]},
]


def aplicar(cur, conector_id):
    """Insere os armazéns e seus apelidos de de-para. Idempotente: nunca sobrescreve
    um armazém já existente (mesma lógica de conectores/métricas em database.py), só
    preenche o que falta."""
    for item in ARMAZENS:
        cur.execute(
            """
            INSERT INTO armazens (nome, sigla, ativo) VALUES (%s, %s, %s)
            ON CONFLICT (sigla) DO NOTHING
            """,
            (item["nome"], item["sigla"], item["ativo"]),
        )
        cur.execute("SELECT id FROM armazens WHERE sigla = %s", (item["sigla"],))
        armazem_id = cur.fetchone()[0]
        for apelido in item["apelidos"]:
            cur.execute(
                """
                INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (conector_id, armazem_na_fonte)
                DO UPDATE SET armazem_id = EXCLUDED.armazem_id
                """,
                (conector_id, apelido, armazem_id),
            )
