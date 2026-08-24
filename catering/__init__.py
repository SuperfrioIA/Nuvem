"""Volumetria de catering lendo o DW Oracle (V3).

Aplicacao nova, nao refatoracao do `backend/`. Motivo em `docs/V3_PLANO.md`:
o fato publicado da V1/V2 e livro-caixa mensal em formato longo, e esta
aplicacao precisa de grao de DIA com as medidas na mesma linha. Escopo do
negocio: catering = instancias SLIN.

Nada aqui importa de `backend/`. Regra reaproveitada entra por copia, com
teste proprio -- para que a V3 nao herde acoplamento com a leitura do
SharePoint DataHub, que a V3 nao usa.
"""
