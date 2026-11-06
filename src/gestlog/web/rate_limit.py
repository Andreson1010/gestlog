"""Rate limiting em memória para as rotas abertas de autenticação (AD-015).

Janela deslizante por (rota, IP de origem). A instância é por processo: em
dev/andaime isso basta; ao escalar para múltiplas réplicas, trocar o
dicionário por um store compartilhado (Redis) sem mudar a interface.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from gestlog.config import Settings, get_settings

_MAX_CHAVES = 10_000


class RateLimiter:
    """Contador de tentativas por chave dentro de uma janela deslizante."""

    def __init__(self) -> None:
        """Cria o limitador vazio."""
        self._tentativas: dict[str, deque[float]] = {}
        self._trava = threading.Lock()

    def permitir(self, chave: str, limite: int, janela: int) -> bool:
        """Devolve ``True`` se a tentativa cabe no limite da janela.

        Registra a tentativa corrente quando permitida; descarta as marcas
        mais velhas que a janela antes de contar. A contenção acontece
        ANTES da inserção (L-047): primeiro caem as chaves sem marca viva;
        persistindo o teto (janelas com IPs demais ao mesmo tempo), a chave
        mais antiga é evictada e o dicionário nunca excede ``_MAX_CHAVES``.
        """
        agora = time.monotonic()
        with self._trava:
            if len(self._tentativas) >= _MAX_CHAVES:
                self._podar(agora, janela)
            marcas = self._tentativas.setdefault(chave, deque())
            while marcas and marcas[0] <= agora - janela:
                marcas.popleft()
            if len(marcas) >= limite:
                return False
            marcas.append(agora)
            return True

    def _podar(self, agora: float, janela: int) -> None:
        """Contém o dicionário no teto: chaves mortas primeiro, senão a mais antiga.

        Só roda no gatilho de teto (`permitir`) — o scan é O(N) e não pode
        pagar por tentativa. Remoção ANTES do ``setdefault`` (L-047): a chave
        nova nunca é vítima (não está inserida); no teto, uma chave já
        existente e mais antiga pode ser evictada e recriada vazia — as
        marcas dela se perdem, degradação aceita e registrada na ADR §2.2.
        """
        gastas = [
            chave
            for chave, marcas in self._tentativas.items()
            if not marcas or marcas[-1] <= agora - janela
        ]
        for chave in gastas:
            del self._tentativas[chave]
        while len(self._tentativas) >= _MAX_CHAVES:
            del self._tentativas[next(iter(self._tentativas))]

    def reset(self) -> None:
        """Limpa todas as marcas (uso em testes e entre reinícios de rota)."""
        with self._trava:
            self._tentativas.clear()


limitador = RateLimiter()


def _ip_do_cliente(request: Request) -> str:
    """IP de origem da requisição (``request.client`` é nulo em testes puros)."""
    if request.client is None:
        return "desconhecido"
    return request.client.host


def limitar(rotas: str) -> Callable[..., None]:
    """Cria a dependência de rate limiting para o grupo de rotas dado."""

    def _dependencia(
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        """Aplica o limite de tentativas da janela à rota e IP correntes."""
        chave = f"{rotas}:{_ip_do_cliente(request)}"
        if not limitador.permitir(
            chave, settings.rate_limit_tentativas, settings.rate_limit_janela_segundos
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas; aguarde antes de tentar de novo.",
            )

    return _dependencia
