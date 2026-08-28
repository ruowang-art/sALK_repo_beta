from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol


class GenotypeResultProvider(Protocol):
    def retrieve(self, destination: Path) -> Path:
        ...


class LocalFileResultProvider:
    def __init__(self, source: Path) -> None:
        self.source = source

    def retrieve(self, destination: Path) -> Path:
        source = self.source.expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

