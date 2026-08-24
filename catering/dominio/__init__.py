"""Regras de dominio da V3: as decisoes NOSSAS sobre o dado do DW.

Principio do schema (`docs/V3_PLANO.md`): **o fato espelha o DW; as tabelas de
dimensao guardam as nossas decisoes**. Este pacote e a forma executavel dessas
decisoes -- funcoes puras, sem banco e sem I/O, para poderem ser testadas
sozinhas e para o de-para ficar auditavel em vez de escondido numa consulta.

Nao ha FK do fato para as dimensoes, de proposito. Unidade nova, cliente novo
ou nome de estoque novo entram sozinhos, com o padrao de identidade, em vez de
derrubar a carga -- e `NAO_CLASSIFICADO` e visivel na tela, que e o sinal.
Bloquear a carga exigiria a maquinaria de pendencia da V2, que existia porque
a fonte era planilha suja.
"""
