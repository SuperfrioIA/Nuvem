from abc import ABC, abstractmethod


class Conector(ABC):
    """Interface unica que todo conector implementa.

    O motor so conhece o formato canonico devolvido por buscar():
    {metrica, armazem_na_fonte, competencia, valor}. Nao sabe de onde o dado veio.
    """

    def __init__(self, conector_id: int, config: dict):
        self.conector_id = conector_id
        self.config = config

    @abstractmethod
    def testar(self) -> dict:
        """Retorna {"ok": bool, "mensagem": str}."""

    def buscar(self, competencia):
        """Busca ativa numa fonte externa. upload_manual nao implementa -- o dado
        chega por upload, nao por busca agendada."""
        raise NotImplementedError

    def detalhar(self, *args, **kwargs):
        """Reservado para fontes com grao fino (ex: Pentaho). Nao se constroi
        antes de existir necessidade real."""
        raise NotImplementedError
