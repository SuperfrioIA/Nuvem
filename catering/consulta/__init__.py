"""Consultas de leitura da V3 -- a Matriz e, depois, a planilha e o download.

Separado de `catering/carga/` de proposito: carga escreve, consulta le, e as
duas nao compartilham estado. A unica coisa em comum e o `contrato.py`, que
define de onde cada medida sai.
"""
