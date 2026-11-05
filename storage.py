"""Persistência e regras de negócio dos registros de carrinhos.

Módulo sem dependência de Kivy, para poder ser testado no desktop.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone


class DuplicateCodeError(ValueError):
    """Código de carrinho já registrado."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def normalize_code(value):
    return (value or "").strip().upper()


def normalize_division(value):
    return (value or "").strip().upper()


def normalize_observation(value):
    return (value or "").strip()


class EntryStore:
    """Lista de registros salva em JSON, mais recentes primeiro."""

    def __init__(self, path):
        self.path = path
        self.entries = self._load()

    # --- arquivo -------------------------------------------------------
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        return [e for e in data if isinstance(e, dict) and "id" in e and "code" in e]

    def save(self):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        # Grava em arquivo temporário e renomeia para não corromper os dados.
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".entries-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.entries, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # --- operações -----------------------------------------------------
    def get(self, entry_id):
        return next((e for e in self.entries if e["id"] == entry_id), None)

    def has_code(self, code, exclude_id=None):
        return any(e["code"] == code and e["id"] != exclude_id for e in self.entries)

    def add(self, code, division, observation=""):
        """Adiciona um registro. Retorna None se faltar código ou divisória."""
        code = normalize_code(code)
        division = normalize_division(division)
        if not code or not division:
            return None
        if self.has_code(code):
            raise DuplicateCodeError(code)
        entry = {
            "id": str(uuid.uuid4()),
            "code": code,
            "division": division,
            "observation": normalize_observation(observation),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.insert(0, entry)
        self.save()
        return entry

    def update(self, entry_id, code, division, observation=""):
        code = normalize_code(code)
        division = normalize_division(division)
        if not code or not division:
            return None
        entry = self.get(entry_id)
        if entry is None:
            return None
        if self.has_code(code, exclude_id=entry_id):
            raise DuplicateCodeError(code)
        entry.update(code=code, division=division,
                     observation=normalize_observation(observation))
        self.save()
        return entry

    def remove(self, entry_id):
        before = len(self.entries)
        self.entries = [e for e in self.entries if e["id"] != entry_id]
        if len(self.entries) != before:
            self.save()

    def clear(self):
        self.entries = []
        self.save()

    def filter(self, query):
        q = (query or "").upper()
        if not q:
            return list(self.entries)
        return [
            e for e in self.entries
            if q in e["code"]
            or q in e["division"].upper()
            or q in (e.get("observation") or "").upper()
        ]


def local_datetime(entry):
    """Converte o timestamp ISO (UTC) do registro para o horário local."""
    try:
        dt = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return datetime.now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()
