from __future__ import annotations

"""Shared parsed C++ declaration availability markers."""

from typing import Literal


# Coarse availability state exposed by libclang for declarations.
CppAvailability = Literal["available", "deprecated", "not_accessible", "not_available"]
