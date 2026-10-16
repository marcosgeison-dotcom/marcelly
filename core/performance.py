"""
Monitor de desempenho do Marcelly.

Mede o tempo de cada resposta e, ao perceber demora em sequencia,
ativa o modo rapido: agentes e skills passam a gerar respostas mais
curtas, com menos tentativas, menos contexto e chamadas secundarias.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

from core.debug import DEBUG

SLOW_SECONDS = 12.0      # resposta acima disso conta como demora
WINDOW = 4               # ultimas respostas observadas
ACCEL_HINT = (
    "\n\n[Modo rapido] Responda de forma breve e direta, em no maximo "
    "cinco linhas, sem rodeios e sem repetir a pergunta."
)


class PerformanceMonitor:
    def __init__(self):
        self._times: deque = deque(maxlen=WINDOW)
        self._start: Optional[float] = None
        self._current_where = ""

    def start(self, where: str = ""):
        self._start = time.perf_counter()
        self._current_where = where

    def finish(self) -> float:
        if self._start is None:
            return 0.0
        elapsed = time.perf_counter() - self._start
        self._start = None
        self._times.append(elapsed)
        DEBUG.log(
            "perf",
            event="resposta_medida",
            onde=self._current_where,
            segundos=round(elapsed, 2),
            acelerado=self.is_accelerated(),
        )
        return elapsed

    def is_accelerated(self) -> bool:
        """True quando as respostas recentes estao demorando demais."""
        if not self._times:
            return False
        recent = list(self._times)[-3:]
        if recent[-1] >= SLOW_SECONDS:
            return True
        return len(recent) >= 3 and sum(recent) / len(recent) >= SLOW_SECONDS * 0.75


PERF = PerformanceMonitor()
