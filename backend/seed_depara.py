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
e CWBI não aparecem no cadastro de filiais ativas: MRS está sem volumetria desde
02/2023 (marcada inativa); RPIII e CWBI nunca tiveram volumetria (parecem
pré-operacionais, mantidas ativas).

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
    {"sigla": "RPIII", "nome": "RPIII", "ativo": True,
     "apelidos": ["RPIII", "001006"]},
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
     "apelidos": ["RMSP", "RMSPI", "001020", "02060862002006"]},
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
    {"sigla": "RMSPII", "nome": "Barueri/SP", "ativo": True,
     "apelidos": ["RMSPII", "008001", "06975242000187"]},
    {"sigla": "RMSPIII", "nome": "Barueri/SP", "ativo": True,
     "apelidos": ["RMSPIII", "008002", "06975242000268"]},
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
    {"sigla": "CWBI", "nome": "CWBI", "ativo": True,
     "apelidos": ["CWBI", "001995"]},
    # Lote 7.1 (21/jul/2026, POC catering RMSP): RMSPV nasceu no WMS em 14/jul/2026,
    # ainda sem capacidade/contrato/volumetria — ativa e vazia. RMSPIV existe só no
    # cadastro Protheus, nunca apareceu em fonte do DW — registrada pra resolver
    # de-para de uploads antigos, mas inativa (mesmo padrão da MRS).
    {"sigla": "RMSPV", "nome": "Barueri/SP", "ativo": True,
     "apelidos": ["RMSPV", "008009", "06975242000934"]},
    {"sigla": "RMSPIV", "nome": "Barueri/SP", "ativo": False,
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
