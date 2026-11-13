"""Persistência e regras de negócio do Neon Cart.

Módulo sem dependência de Kivy, para poder ser testado no desktop.

Arquivo único (JSON, versão 2) com:
- entries:   lista ativa de carrinhos (mais recentes primeiro)
- history:   histórico de scans/ações (mais recentes primeiro)
- sessions:  listas salvas
- divisions: setores usados recentemente
- settings:  preferências
- folders:   pastas semanais de devolução de material (Porta Vasos)
- clients:   clientes usados recentemente (Porta Vasos)
- client_list: cadastro de clientes (Porta Vasos), em ordem alfabética
"""

import json
import os
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone

import portavasos as pv

DATA_VERSION = 2

# Ações do histórico
ADD = "ADD"
DUPLICATE = "DUPLICATE"
EDIT = "EDIT"
DELETE = "DELETE"
SCAN = "SCAN"
ACTIONS = (ADD, DUPLICATE, EDIT, DELETE, SCAN)

ACTION_LABELS = {
    ADD: "REGISTRADO",
    DUPLICATE: "DUPLICADO",
    EDIT: "EDITADO",
    DELETE: "EXCLUÍDO",
    SCAN: "LIDO",
}

DEFAULT_SETTINGS = {
    "continuous": False,  # câmera cadastra direto e continua aberta
    "vibrate": True,
    "sound": True,
}


class DuplicateCodeError(ValueError):
    """Código de carrinho já registrado."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class BackupError(ValueError):
    """Arquivo de backup inválido."""


def normalize_code(value):
    return (value or "").strip().upper()


def normalize_division(value):
    return (value or "").strip().upper()


def normalize_observation(value):
    return (value or "").strip()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_ts(value):
    """Converte timestamp ISO (UTC) para datetime local."""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def local_datetime(item):
    """Horário local do campo "timestamp" (registro ou histórico)."""
    if not isinstance(item, dict):
        return datetime.now().astimezone()
    return parse_ts(item.get("timestamp"))


def _valid_entry(e):
    return isinstance(e, dict) and isinstance(e.get("id"), str) and isinstance(e.get("code"), str)


def _clean_entry(e):
    return {
        "id": e["id"],
        "code": normalize_code(e["code"]),
        "division": normalize_division(e.get("division")),
        "observation": normalize_observation(e.get("observation")),
        "timestamp": e.get("timestamp") or now_iso(),
    }


def _clean_entries(items):
    return [_clean_entry(e) for e in items or [] if _valid_entry(e)]


def _clean_history(items):
    out = []
    for h in items or []:
        if isinstance(h, dict) and h.get("action") in ACTIONS and isinstance(h.get("code"), str):
            out.append({
                "id": h.get("id") or str(uuid.uuid4()),
                "action": h["action"],
                "code": h["code"],
                "division": h.get("division") or "",
                "source": h.get("source") or "manual",
                "timestamp": h.get("timestamp") or now_iso(),
            })
    return out


def _clean_sessions(items):
    out = []
    for s in items or []:
        if isinstance(s, dict) and isinstance(s.get("id"), str):
            out.append({
                "id": s["id"],
                "name": str(s.get("name") or "Lista"),
                "created": s.get("created") or now_iso(),
                "entries": _clean_entries(s.get("entries")),
            })
    return out


class Database:
    """Todos os dados do app em um arquivo JSON."""

    MAX_HISTORY = 5000
    MAX_DIVISIONS = 8
    MAX_CLIENTS = 12

    def __init__(self, path, legacy_path=None):
        self.path = path
        self.entries = []
        self.history = []
        self.sessions = []
        self.divisions = []
        self.folders = []
        self.clients = []
        self.client_list = []
        self.settings = dict(DEFAULT_SETTINGS)
        # Falso se o arquivo existe mas não pôde ser lido: aí nada é apagado.
        self.loaded_ok = True
        if os.path.exists(path):
            self.loaded_ok = False
            self._load()
        elif legacy_path and os.path.exists(legacy_path):
            self._migrate_v1(legacy_path)

    # --- arquivo -------------------------------------------------------
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):  # ValueError cobre JSON e texto com bytes inválidos
            return
        if isinstance(data, list):  # formato antigo (só a lista)
            data = {"entries": data}
        if isinstance(data, dict):
            self._apply(data)
            self.loaded_ok = True

    def _apply(self, data):
        self.entries = _clean_entries(data.get("entries"))
        self.history = _clean_history(data.get("history"))[: self.MAX_HISTORY]
        self.sessions = _clean_sessions(data.get("sessions"))
        self.divisions = [normalize_division(d) for d in data.get("divisions") or []
                          if isinstance(d, str) and d.strip()][: self.MAX_DIVISIONS]
        self.folders = pv.clean_folders(data.get("folders"))
        self.clients = [pv.normalize_client(c) for c in data.get("clients") or []
                        if isinstance(c, str) and c.strip()][: self.MAX_CLIENTS]
        # cadastro de clientes; na 1ª vez, monta com os clientes que já estão nas pastas
        names = [c for c in data.get("client_list") or [] if isinstance(c, str)]
        if "client_list" not in data:
            names += [r["client"] for f in self.folders for r in f["records"]]
        self.client_list = sorted({pv.normalize_client(c) for c in names if c.strip()})
        settings = dict(DEFAULT_SETTINGS)
        for key, value in (data.get("settings") or {}).items():
            if key in DEFAULT_SETTINGS and isinstance(value, bool):
                settings[key] = value
        self.settings = settings

    def _migrate_v1(self, legacy_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, list):
            self.entries = _clean_entries(data)
            self.save()

    def to_dict(self):
        return {
            "version": DATA_VERSION,
            "entries": self.entries,
            "history": self.history,
            "sessions": self.sessions,
            "divisions": self.divisions,
            "settings": self.settings,
            "folders": self.folders,
            "clients": self.clients,
            "client_list": self.client_list,
        }

    def save(self):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        # Grava em arquivo temporário e renomeia para não corromper os dados.
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".neoncart-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # --- histórico -----------------------------------------------------
    def _log(self, action, code, division="", source="manual"):
        self.history.insert(0, {
            "id": str(uuid.uuid4()),
            "action": action,
            "code": code,
            "division": division,
            "source": source,
            "timestamp": now_iso(),
        })
        del self.history[self.MAX_HISTORY:]

    def log_scan(self, code, source="camera"):
        """Registra uma leitura da câmera (antes de cadastrar)."""
        code = normalize_code(code)
        if code:
            self._log(SCAN, code, source=source)
            self.save()

    def filter_history(self, query="", action=None):
        q = (query or "").upper()
        return [
            h for h in self.history
            if (action is None or h["action"] == action)
            and (not q or q in h["code"].upper() or q in h["division"].upper())
        ]

    def clear_history(self):
        self.history = []
        self.save()

    # --- lista ativa ---------------------------------------------------
    def get(self, entry_id):
        return next((e for e in self.entries if e["id"] == entry_id), None)

    def has_code(self, code, exclude_id=None):
        return any(e["code"] == code and e["id"] != exclude_id for e in self.entries)

    def find_code(self, code):
        """Onde o código aparece: [("Lista atual", entry) | (nome_da_lista, entry)]."""
        code = normalize_code(code)
        found = [("Lista atual", e) for e in self.entries if e["code"] == code]
        for s in self.sessions:
            found += [(s["name"], e) for e in s["entries"] if e["code"] == code]
        return found

    def _remember_division(self, division):
        if division in self.divisions:
            self.divisions.remove(division)
        self.divisions.insert(0, division)
        del self.divisions[self.MAX_DIVISIONS:]

    def forget_division(self, division):
        division = normalize_division(division)
        if division in self.divisions:
            self.divisions.remove(division)
            self.save()

    def add(self, code, division, observation="", source="manual"):
        """Adiciona um registro. Retorna None se faltar código ou divisória."""
        code = normalize_code(code)
        division = normalize_division(division)
        if not code or not division:
            return None
        if self.has_code(code):
            self._log(DUPLICATE, code, division, source)
            self.save()
            raise DuplicateCodeError(code)
        entry = {
            "id": str(uuid.uuid4()),
            "code": code,
            "division": division,
            "observation": normalize_observation(observation),
            "timestamp": now_iso(),
        }
        self.entries.insert(0, entry)
        self._remember_division(division)
        self._log(ADD, code, division, source)
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
        self._remember_division(division)
        self._log(EDIT, code, division)
        self.save()
        return entry

    def remove(self, entry_id):
        """Remove e retorna (entry, posição) para permitir desfazer."""
        for idx, e in enumerate(self.entries):
            if e["id"] == entry_id:
                del self.entries[idx]
                self._log(DELETE, e["code"], e["division"])
                self.save()
                return e, idx
        return None, -1

    def restore(self, entry, index=0):
        """Desfaz uma exclusão. Falha se o código foi registrado de novo."""
        if self.has_code(entry["code"]) or self.get(entry["id"]):
            return False
        self.entries.insert(max(0, min(index, len(self.entries))), entry)
        self._log(ADD, entry["code"], entry["division"], "desfazer")
        self.save()
        return True

    def clear(self):
        """Apaga a lista ativa e retorna os registros (para desfazer)."""
        removed = self.entries
        self.entries = []
        self.save()
        return removed

    def restore_all(self, entries):
        if self.entries:
            return False
        self.entries = list(entries)
        self.save()
        return True

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

    # --- listas salvas -------------------------------------------------
    def get_session(self, session_id):
        return next((s for s in self.sessions if s["id"] == session_id), None)

    @staticmethod
    def default_session_name(now=None):
        now = now or datetime.now()
        return "Lista {}".format(now.strftime("%d/%m/%Y %H:%M"))

    def save_session(self, name=""):
        """Move a lista ativa para uma lista salva. None se estiver vazia."""
        if not self.entries:
            return None
        session = {
            "id": str(uuid.uuid4()),
            "name": (name or "").strip() or self.default_session_name(),
            "created": now_iso(),
            "entries": self.entries,
        }
        self.sessions.insert(0, session)
        self.entries = []
        self.save()
        return session

    def rename_session(self, session_id, name):
        session = self.get_session(session_id)
        name = (name or "").strip()
        if session is None or not name:
            return None
        session["name"] = name
        self.save()
        return session

    def delete_session(self, session_id):
        session = self.get_session(session_id)
        if session is not None:
            self.sessions.remove(session)
            self.save()
        return session

    def reinsert_session(self, session, index=0):
        if self.get_session(session["id"]) is None:
            self.sessions.insert(max(0, min(index, len(self.sessions))), session)
            self.save()

    def restore_session(self, session_id):
        """Volta uma lista salva para a lista ativa.

        Se a lista ativa tiver registros, ela é salva antes. Retorna
        (lista_restaurada, lista_salva_automaticamente_ou_None).
        """
        session = self.get_session(session_id)
        if session is None:
            return None, None
        autosaved = None
        if self.entries:
            autosaved = {
                "id": str(uuid.uuid4()),
                "name": self.default_session_name() + " (auto)",
                "created": now_iso(),
                "entries": self.entries,
            }
        self.sessions.remove(session)
        if autosaved:
            self.sessions.insert(0, autosaved)
        self.entries = list(session["entries"])
        for e in self.entries:
            if e["division"]:
                self._remember_division(e["division"])
                break
        self.save()
        return session, autosaved

    # --- porta vasos: pastas semanais -----------------------------------
    def get_folder(self, folder_id):
        return next((f for f in self.folders if f["id"] == folder_id), None)

    def folders_by_status(self, status=None):
        return [f for f in self.folders if status is None or f["status"] == status]

    def _folder_conflict(self, start, exclude_id=None):
        return next((f for f in self.folders
                     if f["start"] == start and f["id"] != exclude_id), None)

    def add_folder(self, name, start, end):
        """Cria uma pasta. Levanta portavasos.PvError (inclusive semana repetida)."""
        folder = pv.build_folder(name, start, end)
        other = self._folder_conflict(folder["start"])
        if other is not None:
            raise pv.PvError("Já existe a pasta \"{}\" começando em {}.".format(
                other["name"], pv.format_date(other["start"])))
        self.folders.append(folder)
        self.folders = pv.sort_folders(self.folders)
        self.save()
        return folder

    def update_folder(self, folder_id, name, start, end):
        folder = self.get_folder(folder_id)
        if folder is None:
            return None
        data = pv.build_folder(name, start, end, folder_id=folder_id, created=folder["created"])
        other = self._folder_conflict(data["start"], exclude_id=folder_id)
        if other is not None:
            raise pv.PvError("Já existe a pasta \"{}\" começando em {}.".format(
                other["name"], pv.format_date(other["start"])))
        folder.update(name=data["name"], start=data["start"], end=data["end"])
        self.folders = pv.sort_folders(self.folders)
        self.save()
        return folder

    def set_folder_status(self, folder_id, status):
        folder = self.get_folder(folder_id)
        if folder is None or status not in pv.STATUSES:
            return None
        folder["status"] = status
        folder["status_date"] = pv.now_iso() if status == pv.RETURNED else ""
        self.save()
        return folder

    def delete_folder(self, folder_id):
        folder = self.get_folder(folder_id)
        if folder is not None:
            self.folders.remove(folder)
            self.save()
        return folder

    def reinsert_folder(self, folder):
        if self.get_folder(folder["id"]) is None:
            self.folders.append(folder)
            self.folders = pv.sort_folders(self.folders)
            self.save()

    def _remember_client(self, client):
        if client in self.clients:
            self.clients.remove(client)
        self.clients.insert(0, client)
        del self.clients[self.MAX_CLIENTS:]
        if client not in self.client_list:
            self.client_list = sorted(self.client_list + [client])

    # --- cadastro de clientes ------------------------------------------
    def add_client(self, name):
        """Cadastra um cliente na lista. Retorna o nome normalizado (ou None)."""
        name = pv.normalize_client(name)
        if not name:
            return None
        if name not in self.client_list:
            self.client_list = sorted(self.client_list + [name])
            self.save()
        return name

    def remove_client(self, name):
        """Tira o cliente da lista (os registros dele continuam nas pastas)."""
        name = pv.normalize_client(name)
        changed = False
        if name in self.client_list:
            self.client_list.remove(name)
            changed = True
        if name in self.clients:
            self.clients.remove(name)
            changed = True
        if changed:
            self.save()
        return changed

    def search_clients(self, query=""):
        q = pv.normalize_client(query)
        return [c for c in self.client_list if not q or q in c]

    def client_returns(self, folder_id, client, exclude_id=None):
        """Devoluções do cliente já registradas na pasta (por data)."""
        folder = self.get_folder(folder_id)
        client = pv.normalize_client(client)
        if folder is None or not client:
            return []
        return pv.sort_records([r for r in folder["records"]
                                if r["client"] == client and r["id"] != exclude_id])

    def find_record(self, record_id):
        """(pasta, registro) ou (None, None)."""
        for folder in self.folders:
            for r in folder["records"]:
                if r["id"] == record_id:
                    return folder, r
        return None, None

    @staticmethod
    def _check_carts(folder, carts, exclude_id=None):
        for code in pv.clean_carts(carts):
            other = pv.find_cart(folder, code, exclude_id)
            if other is not None:
                raise pv.PvError("O carrinho {} já foi registrado nesta pasta para {} "
                                 "({}).".format(code, other["client"],
                                                pv.format_date(other["date"])))

    def add_record(self, folder_id, client, return_date, items, photos=None, carts=None):
        """Registra uma devolução na pasta. Levanta portavasos.PvError.

        O mesmo cliente pode ter várias devoluções (uma por data).
        """
        folder = self.get_folder(folder_id)
        if folder is None:
            raise pv.PvError("Pasta não encontrada.")
        record = pv.build_record(client, return_date, items, photos=photos, carts=carts)
        self._check_carts(folder, record["carts"])
        folder["records"].append(record)
        self._remember_client(record["client"])
        self.save()
        return record

    def update_record(self, record_id, client, return_date, items, photos=None, carts=None):
        """Atualiza o registro. photos/carts=None mantêm o que ele já tinha."""
        folder, old = self.find_record(record_id)
        if old is None:
            return None
        if carts is None and old.get("carts"):
            carts = old["carts"]
        record = pv.build_record(client, return_date, items, record_id=record_id,
                                 timestamp=old["timestamp"],
                                 photos=old.get("photos") if photos is None else photos,
                                 carts=carts)
        self._check_carts(folder, record["carts"], exclude_id=record_id)
        old.clear()
        old.update(record)
        self._remember_client(record["client"])
        self.save()
        return old

    def set_record_photos(self, record_id, photos):
        _folder, record = self.find_record(record_id)
        if record is None:
            return None
        record["photos"] = pv.clean_photos(photos)
        self.save()
        return record

    @property
    def photos_dir(self):
        return os.path.join(os.path.dirname(os.path.abspath(self.path)), "photos")

    def used_photos(self):
        return set(pv.all_photos(self.folders))

    def purge_photos(self, keep_extra=()):
        """Apaga do aparelho fotos que nenhum registro usa (ex.: cadastro cancelado)."""
        import photos

        if not self.loaded_ok:
            return 0
        return photos.purge_orphans(self.photos_dir, self.used_photos() | set(keep_extra))

    def remove_record(self, record_id):
        """Remove e retorna (pasta, registro, posição) para desfazer."""
        for folder in self.folders:
            for idx, r in enumerate(folder["records"]):
                if r["id"] == record_id:
                    del folder["records"][idx]
                    self.save()
                    return folder, r, idx
        return None, None, -1

    def restore_record(self, folder_id, record, index=0):
        folder = self.get_folder(folder_id)
        if folder is None or self.find_record(record["id"])[1] is not None:
            return False
        folder["records"].insert(max(0, min(index, len(folder["records"]))), record)
        self.save()
        return True

    # --- ajustes -------------------------------------------------------
    def set_setting(self, key, value):
        if key not in DEFAULT_SETTINGS:
            raise KeyError(key)
        self.settings[key] = bool(value)
        self.save()

    # --- resumo --------------------------------------------------------
    def summary(self, today=None):
        today = today or datetime.now().astimezone().date()
        by_div = Counter(e["division"] for e in self.entries)
        today_counts = Counter(
            h["action"] for h in self.history if parse_ts(h["timestamp"]).date() == today)
        return {
            "total": len(self.entries),
            "with_obs": sum(1 for e in self.entries if e.get("observation")),
            "divisions": sorted(by_div.items(), key=lambda kv: (-kv[1], kv[0])),
            "today_added": today_counts[ADD],
            "today_duplicates": today_counts[DUPLICATE],
            "today_scans": today_counts[SCAN],
            "sessions": len(self.sessions),
            "saved_entries": sum(len(s["entries"]) for s in self.sessions),
            "folders": len(self.folders),
        }

    # --- backup --------------------------------------------------------
    def backup_dict(self):
        data = self.to_dict()
        data["app"] = "neoncart"
        data["exported"] = now_iso()
        return data

    def load_backup(self, data):
        """Substitui todos os dados pelos do backup (dict ou texto JSON)."""
        if isinstance(data, (str, bytes)):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise BackupError("Arquivo não é um JSON válido") from exc
        if isinstance(data, list):
            data = {"entries": data}
        if not isinstance(data, dict) or not any(
                k in data for k in ("entries", "sessions", "history", "folders")):
            raise BackupError("Arquivo não é um backup do Neon Cart")
        self._apply(data)
        self.save()
        return self.summary()


# Compatibilidade com o nome antigo.
EntryStore = Database
