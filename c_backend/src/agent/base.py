from typing import Protocol

from src.documents.models import NormalizedDocument

from .schemas import AgentExtraction


class CorporateActionAgent(Protocol):
    def extract(self, document: NormalizedDocument) -> AgentExtraction:
        """Interpreta um documento normalizado sem executar validações determinísticas."""
        ...
