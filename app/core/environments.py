# -*- coding: utf-8 -*-
"""
Ortam tipleri ve transfer yön kuralları.

İzin verilen yönler:
    PROD  -> TEST
    PROD  -> LOCAL
    TEST  -> LOCAL

Yasak yönler:
    LOCAL -> PROD
    TEST  -> PROD
    LOCAL -> TEST
    (ayrıca aynı ortamdan aynı ortama, ve bilinmeyen kombinasyonlar)

Kural mantığı: Veri yalnızca "daha güvenli/daha üst" ortamdan
"daha düşük/geliştirme" ortamına doğru akabilir. Asla yukarı doğru değil.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class Environment(str, Enum):
    PROD = "PROD"
    TEST = "TEST"
    LOCAL = "LOCAL"

    @property
    def label(self) -> str:
        return {
            Environment.PROD: "Production",
            Environment.TEST: "Test",
            Environment.LOCAL: "Local",
        }[self]

    @property
    def rank(self) -> int:
        # Yükseklik sırası: PROD en üstte, LOCAL en altta.
        return {Environment.PROD: 3, Environment.TEST: 2, Environment.LOCAL: 1}[self]


# Açıkça izin verilen yönler (kaynak, hedef)
ALLOWED_DIRECTIONS: set[tuple[Environment, Environment]] = {
    (Environment.PROD, Environment.TEST),
    (Environment.PROD, Environment.LOCAL),
    (Environment.TEST, Environment.LOCAL),
}


@dataclass(frozen=True)
class DirectionCheck:
    allowed: bool
    reason: str


def check_direction(source: Environment, target: Environment) -> DirectionCheck:
    """Bir transfer yönünün izinli olup olmadığını döndürür."""
    if source == target:
        return DirectionCheck(
            False,
            f"Kaynak ve hedef aynı ortam ({source.label}). Aynı ortama transfer yapılamaz.",
        )

    if (source, target) in ALLOWED_DIRECTIONS:
        return DirectionCheck(
            True,
            f"{source.label} → {target.label} aktarımına izin veriliyor.",
        )

    # Yukarı doğru akış mı?
    if target.rank > source.rank:
        return DirectionCheck(
            False,
            f"{source.label} → {target.label} YASAK. "
            f"Veri yalnızca üst ortamdan alt ortama aktarılabilir "
            f"({target.label} ortamına geri yazılamaz).",
        )

    return DirectionCheck(
        False,
        f"{source.label} → {target.label} yönüne izin verilmiyor.",
    )


def allowed_targets_for(source: Environment) -> list[Environment]:
    """Verilen kaynak için izin verilen hedef ortamların listesi."""
    return [t for (s, t) in ALLOWED_DIRECTIONS if s == source]
