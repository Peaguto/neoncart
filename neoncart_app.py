"""Neon Cart - baixa de carrinhos (versão Android em Python/Kivy)."""

import os
import tempfile

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import MarkupLabel
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.utils import escape_markup
from kivy.properties import (BooleanProperty, DictProperty, ListProperty,
                             NumericProperty, ObjectProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput

import exporter
import platform_utils as pu
from scanner import ScannerModal
from storage import (ACTION_LABELS, ADD, DELETE, DUPLICATE, EDIT, SCAN, BackupError,
                     Database, DuplicateCodeError, local_datetime, parse_ts)
from theme import ICON_FONT, C, I, gradient_texture

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FONT_PATH = os.path.join(APP_DIR, ICON_FONT)
APP_VERSION = "2.0.0"

# Cor e ícone de cada ação do histórico
ACTION_STYLE = {
    ADD: (C.green400, I.ok),
    DUPLICATE: (C.red500, I.alert),
    EDIT: (C.blue400, I.edit),
    DELETE: (C.purple500, I.trash2),
    SCAN: (C.amber400, I.barcode),
}
HISTORY_FILTERS = [
    ("TODOS", None), ("LIDOS", SCAN), ("REGISTRADOS", ADD),
    ("DUPLICADOS", DUPLICATE), ("EDITADOS", EDIT), ("EXCLUÍDOS", DELETE),
]
SCREEN_TITLES = {
    "home": "CONTROLE DE ESTOQUE",
    "history": "HISTÓRICO DE SCANS",
    "saved": "LISTAS SALVAS",
    "summary": "RESUMO",
    "settings": "AJUSTES",
}


# --- widgets básicos -----------------------------------------------------
class IconLabel(Label):
    icon = StringProperty("")


class IconButton(ButtonBehavior, Label):
    icon = StringProperty("")
    icon_color = ListProperty(C.purple400)
    hover_bg = ListProperty([0, 0, 0, 0])


class GradientButton(ButtonBehavior, BoxLayout):
    icon = StringProperty("")
    text = StringProperty("")
    texture = ObjectProperty(None, allownone=True)


class Chip(ButtonBehavior, Label):
    active = BooleanProperty(False)


class NavButton(ButtonBehavior, BoxLayout):
    icon = StringProperty("")
    text = StringProperty("")
    screen = StringProperty("")
    badge = NumericProperty(0)


class ToggleRow(ButtonBehavior, BoxLayout):
    icon = StringProperty("")
    title = StringProperty("")
    subtitle = StringProperty("")
    active = BooleanProperty(False)


class ActionRow(ButtonBehavior, BoxLayout):
    icon = StringProperty("")
    title = StringProperty("")
    subtitle = StringProperty("")
    danger = BooleanProperty(False)


class StatTile(BoxLayout):
    icon = StringProperty("")
    value = StringProperty("0")
    label = StringProperty("")
    color = ListProperty(C.pink300)


class DivisionBar(BoxLayout):
    division = StringProperty("")
    count = NumericProperty(0)
    ratio = NumericProperty(0)


class NeonInput(TextInput):
    """TextInput com ícone à esquerda e borda neon ao focar."""

    icon = StringProperty("")
    uppercase = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._icon_color = Color(*C.purple600)
        self._icon_rect = Rectangle()
        self.canvas.after.add(self._icon_color)
        self.canvas.after.add(self._icon_rect)
        self.bind(icon=self._render_icon, pos=self._place_icon,
                  size=self._place_icon, focus=self._on_focus_icon)
        Clock.schedule_once(lambda dt: self._render_icon())

    def _render_icon(self, *args):
        if not self.icon:
            self._icon_rect.texture = None
            self._icon_rect.size = (0, 0)
            return
        lbl = CoreLabel(text=self.icon, font_name=ICON_FONT_PATH, font_size=sp(20))
        lbl.refresh()
        self._icon_rect.texture = lbl.texture
        self._icon_rect.size = lbl.texture.size
        self._place_icon()

    def _place_icon(self, *args):
        w, h = self._icon_rect.size
        self._icon_rect.pos = (self.x + dp(14), self.center_y - h / 2)

    def _on_focus_icon(self, *args):
        self._icon_color.rgba = C.pink500 if self.focus else C.purple600

    def insert_text(self, substring, from_undo=False):
        if self.uppercase:
            substring = substring.upper()
        return super().insert_text(substring, from_undo=from_undo)


# --- linhas das listas ---------------------------------------------------
class EntryRow(RecycleDataViewBehavior, BoxLayout):
    entry_id = StringProperty("")
    code = StringProperty("")
    time = StringProperty("")
    division = StringProperty("")
    observation = StringProperty("")
    readonly = BooleanProperty(False)


class HistoryRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    code = StringProperty("")
    division = StringProperty("")
    action = StringProperty("")
    action_label = StringProperty("")
    when = StringProperty("")
    source = StringProperty("")
    color = ListProperty(C.pink300)
    icon = StringProperty("")


class SessionRow(RecycleDataViewBehavior, BoxLayout):
    session_id = StringProperty("")
    name = StringProperty("")
    when = StringProperty("")
    count = NumericProperty(0)
    detail = StringProperty("")


class DuplicateAlert(BoxLayout):
    code = StringProperty("")


class Snackbar(BoxLayout):
    message = StringProperty("")
    action_text = StringProperty("")
    action_cb = ObjectProperty(None, allownone=True)

    def run_action(self):
        cb, self.action_cb = self.action_cb, None
        App.get_running_app().hide_snackbar()
        if cb:
            cb()


# --- telas ---------------------------------------------------------------
class HomeScreen(Screen):
    pass


class HistoryScreen(Screen):
    pass


class SavedScreen(Screen):
    pass


class SummaryScreen(Screen):
    pass


class SettingsScreen(Screen):
    pass


# --- janelas -------------------------------------------------------------
class EditModal(ModalView):
    entry_id = StringProperty("")
    __events__ = ("on_save",)

    def on_save(self, *args):
        pass

    def submit(self):
        self.dispatch("on_save", self.entry_id, self.ids.code.text,
                      self.ids.division.text, self.ids.observation.text)


class ConfirmModal(ModalView):
    icon = StringProperty(I.alert)
    title = StringProperty("")
    message = StringProperty("")
    confirm_text = StringProperty("CONFIRMAR")
    confirm_cb = ObjectProperty(None, allownone=True)

    def confirm(self):
        self.dismiss()
        if self.confirm_cb:
            self.confirm_cb()


class InfoModal(ModalView):
    icon = StringProperty(I.alert)
    title = StringProperty("")
    message = StringProperty("")
    action_text = StringProperty("")
    action_cb = ObjectProperty(None, allownone=True)

    def action(self):
        self.dismiss()
        if self.action_cb:
            self.action_cb()


class PromptModal(ModalView):
    """Pede um texto (nome da lista)."""

    icon = StringProperty(I.save_all)
    title = StringProperty("")
    label = StringProperty("")
    text = StringProperty("")
    confirm_text = StringProperty("SALVAR")
    confirm_cb = ObjectProperty(None, allownone=True)

    def on_open(self):
        Clock.schedule_once(lambda dt: setattr(self.ids.field, "focus", True), 0.2)

    def confirm(self):
        value = self.ids.field.text.strip()
        if not value:
            self.ids.field.focus = True
            return
        self.dismiss()
        if self.confirm_cb:
            self.confirm_cb(value)


class SessionModal(ModalView):
    """Mostra os carrinhos de uma lista salva."""

    session_id = StringProperty("")
    name = StringProperty("")
    subtitle = StringProperty("")


class Root(FloatLayout):
    pass


# --- app -----------------------------------------------------------------
class NeonCartApp(App):
    title = "Neon Cart"
    icon_font = ICON_FONT_PATH
    version = APP_VERSION
    C = C
    I = I

    # lista ativa
    total = NumericProperty(0)
    visible = NumericProperty(0)
    search_query = StringProperty("")
    recent_divisions = ListProperty([])
    # histórico
    history_total = NumericProperty(0)
    history_visible = NumericProperty(0)
    history_query = StringProperty("")
    history_filter = StringProperty("")
    history_filters = ListProperty(HISTORY_FILTERS)
    # listas salvas
    sessions_total = NumericProperty(0)
    # resumo
    summary = DictProperty({})
    # navegação
    current_screen = StringProperty("home")
    screen_title = StringProperty(SCREEN_TITLES["home"])
    # ajustes
    continuous = BooleanProperty(False)
    vibrate_on = BooleanProperty(True)
    sound_on = BooleanProperty(True)

    grad_main = ObjectProperty(None, allownone=True)
    grad_alt = ObjectProperty(None, allownone=True)
    grad_header = ObjectProperty(None, allownone=True)

    def build(self):
        Window.clearcolor = C.bg
        Window.softinput_mode = "below_target"
        self.grad_main = gradient_texture("#9333ea", "#db2777")
        self.grad_alt = gradient_texture("#db2777", "#9333ea")
        self.grad_header = gradient_texture("#581c87", "#701a75", "#831843")
        self.db = Database(os.path.join(self.user_data_dir, "neoncart.json"),
                           legacy_path=os.path.join(self.user_data_dir, "entries.json"))
        self.continuous = self.db.settings["continuous"]
        self.vibrate_on = self.db.settings["vibrate"]
        self.sound_on = self.db.settings["sound"]
        self._sounds = {}
        self._snack_event = None
        self.summary = self.db.summary()
        self.root = Root()
        self.refresh_all()
        Window.bind(width=lambda *a: Clock.schedule_once(lambda dt: self.refresh_list(), 0))
        Window.bind(on_keyboard=self._on_keyboard)
        return self.root

    # Compatibilidade com o nome usado antes
    @property
    def store(self):
        return self.db

    @property
    def ids(self):
        return self.root.ids

    def screen_ids(self, name):
        return self.ids.sm.get_screen(name).ids

    # --- navegação -----------------------------------------------------
    def go(self, name):
        if name == self.current_screen:
            return
        self.ids.sm.current = name
        self.current_screen = name
        self.screen_title = SCREEN_TITLES.get(name, "")
        self.hide_snackbar()
        if name == "history":
            self.refresh_history()
        elif name == "saved":
            self.refresh_sessions()
        elif name == "summary":
            self.refresh_summary()

    def _on_keyboard(self, window, key, *args):
        # 27 = botão voltar do Android / Esc
        if key == 27 and self.current_screen != "home":
            self.go("home")
            return True
        return False

    # --- ajustes -------------------------------------------------------
    def on_continuous(self, *args):
        if hasattr(self, "db"):
            self.db.set_setting("continuous", self.continuous)

    def on_vibrate_on(self, *args):
        if hasattr(self, "db"):
            self.db.set_setting("vibrate", self.vibrate_on)

    def on_sound_on(self, *args):
        if hasattr(self, "db"):
            self.db.set_setting("sound", self.sound_on)

    # --- feedback (som / vibração) ---------------------------------------
    def _sound(self, name):
        if name not in self._sounds:
            try:
                from kivy.core.audio import SoundLoader
                self._sounds[name] = SoundLoader.load(
                    os.path.join(APP_DIR, "assets", "sounds", name + ".wav"))
            except Exception as exc:  # noqa: BLE001
                print("NeonCart: som indisponível:", exc)
                self._sounds[name] = None
        return self._sounds[name]

    def feedback(self, ok):
        if self.sound_on:
            snd = self._sound("ok" if ok else "error")
            if snd is not None:
                try:
                    snd.stop()
                    snd.play()
                except Exception:  # noqa: BLE001
                    pass
        if self.vibrate_on:
            pu.vibrate(50 if ok else 350)

    # --- atualizações ----------------------------------------------------
    def refresh_all(self):
        self.refresh_list()
        self.refresh_history()
        self.refresh_sessions()
        self.refresh_summary()

    def _row_height(self, observation, width):
        # padding + código + setor + 3 espaçamentos do BoxLayout (6dp cada)
        base = dp(12) * 2 + dp(30) + dp(24) + dp(6) * 3
        if not observation:
            return base
        # mesma largura e padding do Label de observação no .kv
        text_width = max(width - dp(16) * 2 - dp(44) - dp(8), dp(80))
        lbl = MarkupLabel(text="[b]OBS:[/b] " + escape_markup(observation),
                          font_size=sp(12), text_size=(text_width, None),
                          padding=(dp(8), dp(8), dp(8), dp(8)))
        lbl.refresh()
        return base + lbl.texture.size[1]

    def entry_rows(self, entries, width, readonly=False):
        data = []
        for e in entries:
            obs = e.get("observation") or ""
            data.append({
                "entry_id": e["id"],
                "code": e["code"],
                "time": local_datetime(e).strftime("%H:%M"),
                "division": e["division"],
                "observation": obs,
                "readonly": readonly,
                "height": self._row_height(obs, width + (dp(44) if readonly else 0)),
            })
        return data

    def refresh_list(self):
        if self.root is None:
            return
        rows = self.db.filter(self.search_query)
        self.total = len(self.db.entries)
        self.visible = len(rows)
        self.recent_divisions = list(self.db.divisions)
        rv = self.screen_ids("home").rv
        width = rv.width if rv.width > 10 else Window.width - dp(32)
        rv.data = self.entry_rows(rows, width)

    def on_search_query(self, *args):
        self.refresh_list()

    def refresh_history(self):
        if self.root is None:
            return
        action = self.history_filter or None
        rows = self.db.filter_history(self.history_query, action)
        self.history_total = len(self.db.history)
        self.history_visible = len(rows)
        data = []
        for h in rows[:1000]:
            color, icon = ACTION_STYLE.get(h["action"], (C.pink300, I.info))
            data.append({
                "code": h["code"],
                "division": h["division"],
                "action": h["action"],
                "action_label": ACTION_LABELS.get(h["action"], h["action"]),
                "when": parse_ts(h["timestamp"]).strftime("%d/%m %H:%M:%S"),
                "source": h.get("source") or "manual",
                "color": list(color),
                "icon": icon,
            })
        self.screen_ids("history").rv.data = data

    def on_history_query(self, *args):
        self.refresh_history()

    def on_history_filter(self, *args):
        self.refresh_history()

    def refresh_sessions(self):
        if self.root is None:
            return
        self.sessions_total = len(self.db.sessions)
        data = []
        for s in self.db.sessions:
            counts = {}
            for e in s["entries"]:
                counts[e["division"]] = counts.get(e["division"], 0) + 1
            top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
            detail = "  ·  ".join("{} ({})".format(d, n) for d, n in top)
            if len(counts) > 3:
                detail += "  ·  +{}".format(len(counts) - 3)
            data.append({
                "session_id": s["id"],
                "name": s["name"],
                "when": parse_ts(s["created"]).strftime("%d/%m/%Y %H:%M"),
                "count": len(s["entries"]),
                "detail": detail or "-",
            })
        self.screen_ids("saved").rv.data = data

    def refresh_summary(self):
        if self.root is None:
            return
        self.summary = self.db.summary()
        box = self.screen_ids("summary").bars
        box.clear_widgets()
        divisions = self.summary["divisions"]
        top = max((n for _, n in divisions), default=1)
        for div, n in divisions:
            box.add_widget(DivisionBar(division=div, count=n, ratio=n / float(top)))

    # --- formulário ----------------------------------------------------
    def submit(self):
        ids = self.screen_ids("home")
        code_in, div_in, obs_in = ids.code, ids.division, ids.observation
        try:
            entry = self.db.add(code_in.text, div_in.text, obs_in.text)
        except DuplicateCodeError as exc:
            code_in.text = ""
            obs_in.text = ""
            self.show_duplicate(exc.code)
            self.feedback(False)
            self.refresh_history()
            self._focus(code_in)
            return
        if entry is None:
            # Campo obrigatório vazio: foca o primeiro que falta.
            self._focus(div_in if not div_in.text.strip() else code_in)
            return
        code_in.text = ""
        obs_in.text = ""
        self.refresh_list()
        self.refresh_history()
        self._focus(code_in)

    def pick_division(self, division):
        self.screen_ids("home").division.text = division
        self._focus(self.screen_ids("home").code)

    def use_code(self, code):
        """Coloca um código no formulário (vindo do histórico)."""
        self.go("home")
        self.screen_ids("home").code.text = code
        self._focus(self.screen_ids("home").code)

    def _focus(self, widget):
        Clock.schedule_once(lambda dt: setattr(widget, "focus", True), 0.1)

    def show_duplicate(self, code):
        alert = self.ids.dup_alert
        alert.code = code
        Animation.cancel_all(alert)
        top_y = self.root.top - dp(24) - alert.height
        alert.y = self.root.top
        alert.opacity = 0
        anim = (Animation(y=top_y, opacity=1, d=0.3, t="out_expo")
                + Animation(d=2.4)
                + Animation(y=self.root.top, opacity=0, d=0.3, t="in_cubic"))
        anim.start(alert)

    # --- snackbar (desfazer) --------------------------------------------
    def show_snackbar(self, message, action_text="", action_cb=None, duration=5):
        bar = self.ids.snackbar
        bar.message = message
        bar.action_text = action_text
        bar.action_cb = action_cb
        Animation.cancel_all(bar)
        Animation(opacity=1, d=0.2).start(bar)
        bar.disabled = False
        if self._snack_event is not None:
            self._snack_event.cancel()
        self._snack_event = Clock.schedule_once(lambda dt: self.hide_snackbar(), duration)

    def hide_snackbar(self):
        if self.root is None:
            return
        bar = self.ids.snackbar
        if self._snack_event is not None:
            self._snack_event.cancel()
            self._snack_event = None
        bar.action_cb = None
        bar.disabled = True
        Animation.cancel_all(bar)
        Animation(opacity=0, d=0.2).start(bar)

    # --- câmera --------------------------------------------------------
    def toggle_continuous(self):
        self.continuous = not self.continuous
        self.show_snackbar("Modo contínuo " + ("LIGADO" if self.continuous else "DESLIGADO"),
                           duration=2)

    def open_scanner(self):
        division = self.screen_ids("home").division.text.strip().upper()
        if self.continuous and not division:
            self.show_info("SETOR VAZIO",
                           "Preencha o SETOR / DIVISÓRIA antes de usar o modo contínuo.",
                           icon=I.grid)
            return
        modal = ScannerModal(continuous=self.continuous, division=division)
        modal.bind(on_result=self._on_scanned, on_dismiss=self._on_scanner_closed)
        modal.open()

    def _on_scanned(self, modal, code):
        code = code.strip().upper()
        self.db.log_scan(code)
        if not modal.continuous:
            self.screen_ids("home").code.text = code
            self.feedback(True)
            self._focus(self.screen_ids("home").code)
            return
        try:
            self.db.add(code, modal.division, "", source="camera")
        except DuplicateCodeError:
            modal.show_feedback(code, False, "JÁ REGISTRADO")
            self.feedback(False)
        else:
            modal.show_feedback(code, True, "REGISTRADO")
            self.feedback(True)
        self.refresh_list()

    def _on_scanner_closed(self, modal):
        self.refresh_history()
        if modal.continuous and modal.count:
            self.show_snackbar("{} carrinho(s) registrado(s) no modo contínuo".format(modal.count),
                               duration=3)

    # --- edição / exclusão ---------------------------------------------
    def edit_entry(self, entry_id):
        entry = self.db.get(entry_id)
        if entry is None:
            return
        modal = EditModal(entry_id=entry_id)
        modal.ids.code.text = entry["code"]
        modal.ids.division.text = entry["division"]
        modal.ids.observation.text = entry.get("observation") or ""
        modal.bind(on_save=self._save_edit)
        modal.open()

    def _save_edit(self, modal, entry_id, code, division, observation):
        try:
            updated = self.db.update(entry_id, code, division, observation)
        except DuplicateCodeError as exc:
            self.show_info("CÓDIGO DUPLICADO",
                           "O código {} já está registrado em outro carrinho!".format(exc.code))
            return
        if updated is None:
            return
        modal.dismiss()
        self.refresh_list()
        self.refresh_history()

    def remove_entry(self, entry_id):
        entry, index = self.db.remove(entry_id)
        if entry is None:
            return
        self.refresh_list()
        self.refresh_history()

        def _undo():
            if self.db.restore(entry, index):
                self.refresh_list()
                self.refresh_history()
            else:
                self.show_info("NÃO FOI POSSÍVEL",
                               "O código {} foi registrado de novo.".format(entry["code"]))

        self.show_snackbar("Carrinho {} excluído".format(entry["code"]), "DESFAZER", _undo)

    def clear_all(self):
        def _do():
            removed = self.db.clear()
            self.search_query = ""
            self.screen_ids("home").search.text = ""
            self.refresh_list()

            def _undo():
                if self.db.restore_all(removed):
                    self.refresh_list()

            self.show_snackbar("{} registro(s) apagado(s)".format(len(removed)), "DESFAZER", _undo)

        self.confirm("LIMPAR LISTA",
                     "Tem certeza que deseja apagar TODOS os registros da lista atual?\n"
                     "Dica: use SALVAR LISTA para guardar antes.", _do, "APAGAR TUDO")

    # --- listas salvas ---------------------------------------------------
    def prompt_save_session(self):
        if not self.db.entries:
            self.show_info("LISTA VAZIA", "Não há carrinhos na lista atual para salvar.",
                           icon=I.save_all)
            return
        PromptModal(title="SALVAR LISTA", label="NOME DA LISTA",
                    text=self.db.default_session_name(),
                    confirm_text="SALVAR", confirm_cb=self._save_session).open()

    def _save_session(self, name):
        session = self.db.save_session(name)
        if session is None:
            return
        self.search_query = ""
        self.screen_ids("home").search.text = ""
        self.refresh_all()
        self.show_snackbar("Lista \"{}\" salva ({} carrinhos)".format(
            session["name"], len(session["entries"])), "VER", lambda: self.go("saved"))

    def view_session(self, session_id):
        session = self.db.get_session(session_id)
        if session is None:
            return
        modal = SessionModal(session_id=session_id, name=session["name"],
                             subtitle="{} carrinhos · {}".format(
                                 len(session["entries"]),
                                 parse_ts(session["created"]).strftime("%d/%m/%Y %H:%M")))
        width = min(Window.width - dp(32), dp(420)) - dp(8)
        modal.ids.rv.data = self.entry_rows(session["entries"], width, readonly=True)
        modal.open()

    def share_session(self, session_id):
        session = self.db.get_session(session_id)
        if session is None:
            return
        self._share(exporter.share_text(session["entries"], title=session["name"]))

    def export_session(self, session_id):
        session = self.db.get_session(session_id)
        if session is None:
            return
        filename = "NeonCart_{}.xlsx".format(exporter.safe_name(session["name"]))
        self._export_file(filename, pu.XLSX_MIME,
                          lambda p: exporter.export_xlsx(session["entries"], p, session["name"]))

    def rename_session(self, session_id):
        session = self.db.get_session(session_id)
        if session is None:
            return

        def _do(name):
            self.db.rename_session(session_id, name)
            self.refresh_sessions()

        PromptModal(title="RENOMEAR LISTA", label="NOVO NOME", text=session["name"],
                    icon=I.edit, confirm_text="RENOMEAR", confirm_cb=_do).open()

    def restore_session(self, session_id):
        session = self.db.get_session(session_id)
        if session is None:
            return

        def _do():
            restored, autosaved = self.db.restore_session(session_id)
            if restored is None:
                return
            self.refresh_all()
            self.go("home")
            msg = "Lista \"{}\" restaurada".format(restored["name"])
            if autosaved:
                msg += "; a anterior foi salva"
            self.show_snackbar(msg)

        message = "Voltar \"{}\" ({} carrinhos) para a lista atual?".format(
            session["name"], len(session["entries"]))
        if self.db.entries:
            message += "\n\nA lista atual ({} carrinhos) será salva automaticamente.".format(
                len(self.db.entries))
        self.confirm("RESTAURAR LISTA", message, _do, "RESTAURAR", icon=I.restore)

    def delete_session(self, session_id):
        index = next((i for i, s in enumerate(self.db.sessions) if s["id"] == session_id), 0)
        session = self.db.delete_session(session_id)
        if session is None:
            return
        self.refresh_sessions()
        self.refresh_summary()

        def _undo():
            self.db.reinsert_session(session, index)
            self.refresh_sessions()
            self.refresh_summary()

        self.show_snackbar("Lista \"{}\" excluída".format(session["name"]), "DESFAZER", _undo)

    # --- histórico -------------------------------------------------------
    def history_item(self, code):
        found = self.db.find_code(code)
        if found:
            lines = ["• {}: setor {}".format(where, e["division"]) for where, e in found[:8]]
            if len(found) > 8:
                lines.append("• +{} outros".format(len(found) - 8))
            message = "Encontrado em:\n" + "\n".join(lines)
        else:
            message = "Este código não está na lista atual nem nas listas salvas."
        self.show_info(code, message, "USAR CÓDIGO", lambda: self.use_code(code), icon=I.where)

    def export_history(self):
        rows = self.db.filter_history(self.history_query, self.history_filter or None)
        if not rows:
            return
        self._export_file(exporter.history_filename(), pu.XLSX_MIME,
                          lambda p: exporter.export_history_xlsx(rows, p))

    def clear_history(self):
        def _do():
            self.db.clear_history()
            self.refresh_history()
            self.refresh_summary()

        self.confirm("LIMPAR HISTÓRICO",
                     "Apagar todo o histórico de scans? A lista e as listas salvas não mudam.",
                     _do, "APAGAR")

    # --- modais genéricos ------------------------------------------------
    def confirm(self, title, message, callback, confirm_text="CONFIRMAR", icon=I.alert):
        ConfirmModal(title=title, message=message, confirm_cb=callback,
                     confirm_text=confirm_text, icon=icon).open()

    def show_info(self, title, message, action_text="", on_action=None, icon=I.alert):
        InfoModal(title=title, message=message, action_text=action_text,
                  action_cb=on_action, icon=icon).open()

    # --- exportar / compartilhar ----------------------------------------
    def _share(self, text):
        try:
            pu.share_text(text)
        except Exception as exc:  # noqa: BLE001
            self.show_info("ERRO", "Não foi possível compartilhar.\n{}".format(exc))

    def share(self):
        rows = self.db.filter(self.search_query) or self.db.entries
        if rows:
            self._share(exporter.share_text(rows))

    def share_summary(self):
        self._share(exporter.summary_text(self.db.summary()))

    def _export_file(self, filename, mime, writer):
        """Gera o arquivo com writer(caminho) e copia para Downloads."""
        pu.request_storage_permission()
        tmp_dir = tempfile.mkdtemp(dir=self.user_data_dir)
        tmp_path = os.path.join(tmp_dir, filename)
        try:
            writer(tmp_path)
            where, uri = pu.save_to_downloads(tmp_path, filename, mime)
        except Exception as exc:  # noqa: BLE001
            self.show_info("ERRO", "Não foi possível exportar.\n{}".format(exc))
            return
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            os.rmdir(tmp_dir)
        if uri is not None:
            self.show_info("EXPORTADO", "Arquivo salvo em:\n" + where, "COMPARTILHAR",
                           lambda: pu.share_file(uri, mime), icon=I.download)
        else:
            self.show_info("EXPORTADO", "Arquivo salvo em:\n" + where, icon=I.download)

    def export(self):
        entries = self.db.entries
        if entries:
            self._export_file(exporter.report_filename(), pu.XLSX_MIME,
                              lambda p: exporter.export_xlsx(entries, p))

    # --- backup ----------------------------------------------------------
    def export_backup(self):
        data = self.db.backup_dict()
        self._export_file(exporter.backup_filename(), pu.JSON_MIME,
                          lambda p: exporter.export_backup(data, p))

    def import_backup(self):
        def _pick():
            try:
                pu.pick_text_file(self._backup_picked)
            except Exception as exc:  # noqa: BLE001
                self.show_info("ERRO", "Não foi possível abrir o seletor.\n{}".format(exc))

        self.confirm("IMPORTAR BACKUP",
                     "Escolha um arquivo NeonCart_Backup_*.json.\n\n"
                     "ATENÇÃO: todos os dados atuais (lista, listas salvas e histórico) "
                     "serão substituídos pelos do backup.", _pick, "ESCOLHER", icon=I.db_import)

    @mainthread
    def _backup_picked(self, text, name):
        if text is None:
            self.show_info("BACKUP", "Nenhum arquivo de backup selecionado.", icon=I.db_import)
            return
        try:
            summary = self.db.load_backup(text)
        except BackupError as exc:
            self.show_info("BACKUP INVÁLIDO", str(exc), icon=I.db_import)
            return
        self.continuous = self.db.settings["continuous"]
        self.vibrate_on = self.db.settings["vibrate"]
        self.sound_on = self.db.settings["sound"]
        self.refresh_all()
        self.show_info("BACKUP RESTAURADO",
                       "{}\n\n{} carrinhos na lista, {} listas salvas.".format(
                           name, summary["total"], summary["sessions"]), icon=I.db_import)


if __name__ == "__main__":
    NeonCartApp().run()
