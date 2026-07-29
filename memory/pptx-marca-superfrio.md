---
name: pptx-marca-superfrio
description: Armadilhas ao gerar PPTX da marca SuperFrio com pptxgenjs (layout, extensão negativa, asset do logo)
metadata:
  type: reference
---

Ao gerar apresentações da marca (skill `superfrio`) com pptxgenjs nesta máquina:

- `pres.layout = 'LAYOUT_16x9'` no pptxgenjs é **10 × 5.625 in**, não 13.33 × 7.5.
  Para o palco de 13.33 × 7.5 usar `'LAYOUT_WIDE'` — senão todo o conteúdo à direita
  de 10 in e abaixo de 5.6 in é cortado silenciosamente.
- Shape com largura ou altura **negativa** (ex.: linha desenhada de um ponto para outro
  com `w: x2 - x1` negativo) gera `<a:ext cx="-...">` e o **PowerPoint recusa o arquivo
  inteiro** como "corrompido e ilegível" (HRESULT 0x80070570). O zip fica válido, então
  o erro só aparece ao abrir. Normalizar com `Math.min`/`Math.abs` + `flipH`/`flipV`.
- Os assets `logo_combined_color.png` / `logo_combined_white.png` **não são recortados
  como o skill afirma**: têm ~50% de altura vazia e uma faixa solta no rodapé (linhas
  ~556–578 de 577), que aparece como um risco branco sob a marca nos slides escuros.
  Recortar para `(0, 6, 1456, 282)` antes de embutir em base64.
- Conferência visual: não há LibreOffice, mas o PowerPoint 16.0 está instalado —
  exportar PNG por COM (`Presentations.Open` + `Slide.Export`) funciona e é a única
  forma de ver overflow de texto e sobreposição. Pillow está disponível; python-pptx e
  pptxgenjs global, não (instalar pptxgenjs no scratchpad).

Primeiro uso: `docs/APRESENTACAO_POC_DATAHUB.pptx` (29/jul/2026). Ver [[projeto-nuvem-ia]].
