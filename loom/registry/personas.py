"""Persona registry loader."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from loom.fde_session.persona_brief import PersonaBrief

PERSONAS_DIR = Path(__file__).resolve().parents[2] / "registry" / "v1" / "personas"


class PersonaLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersonaCatalog:
    _personas: dict[str, PersonaBrief]

    @classmethod
    def load(cls, root: Path = PERSONAS_DIR) -> PersonaCatalog:
        personas: dict[str, PersonaBrief] = {}
        for path in sorted(root.glob("*.yaml")):
            persona = _load_persona(path)
            if persona.persona_id != path.stem:
                raise PersonaLoadError(
                    f"persona file {path.name} declares persona_id {persona.persona_id!r}"
                )
            if persona.persona_id in personas:
                raise PersonaLoadError(f"duplicate persona id: {persona.persona_id}")
            personas[persona.persona_id] = persona
        if not personas:
            raise PersonaLoadError(f"no persona YAML files found under {root}")
        return cls(_personas=personas)

    def list(self) -> list[PersonaBrief]:
        return [self._personas[key] for key in sorted(self._personas)]

    def get(self, persona_id: str) -> PersonaBrief | None:
        return self._personas.get(persona_id)


def _load_persona(path: Path) -> PersonaBrief:
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception as e:  # noqa: BLE001
        raise PersonaLoadError(f"failed to load persona {path.name}: {e}") from e
    if not isinstance(raw, dict):
        raise PersonaLoadError(f"persona {path.name} must contain a YAML object")
    try:
        return PersonaBrief.model_validate(cast("dict[str, object]", raw))
    except Exception as e:  # noqa: BLE001
        raise PersonaLoadError(f"persona {path.name} validation failed: {e}") from e
