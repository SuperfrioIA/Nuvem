"""Configuracao de logging (Bloco G / G2, V1.8).

Antes deste modulo, nenhum logger do app tinha `basicConfig` -- sob uvicorn
(que so configura os loggers `uvicorn*`), o root ficava em WARNING sem
handler, e os `log.info` de `backend/migracao.py` nunca apareciam. Aqui
tambem entra o request id: um id curto por requisicao, gerado pelo
middleware em `backend/main.py`, que aparece em toda linha de log daquela
requisicao -- correlaciona um erro reportado pelo usuario com a linha certa
no log do container.
"""

import contextvars
import logging
import os

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configurar_logging() -> None:
    nivel = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    logging.basicConfig(level=nivel, handlers=[handler], force=True)
