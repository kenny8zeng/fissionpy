from __future__ import annotations

from sample_project.models import User


def get_user(name: str) -> User:
    return User(name=name, age=0)


def list_users() -> list[User]:
    return []
