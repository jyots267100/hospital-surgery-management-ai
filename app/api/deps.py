from __future__ import annotations

from app.dependencies import Container, get_container


def get_container_dep() -> Container:
    return get_container()
