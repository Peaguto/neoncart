"""Material Circulante - Cart (baixa de carrinhos) e Porta Vasos (devolução de material)."""

import os
import tempfile
from datetime import date, timedelta

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import MarkupLabel
from kivy.core.clipboard import Clipboard
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
import photos as ph
import platform_utils as pu
from photo_capture import PhotoModal
import portavasos as pv
import reports
from scanner import ScannerModal
from storage import (ACTION_LABELS, ADD, DELETE, DUPLICATE, EDIT, SCAN, BackupError,
                     Database, DuplicateCodeError, local_datetime, parse_ts)
from theme import ICON_FONT, C, I, gradient_texture

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FONT_PATH = os.path.join(APP_DIR, ICON_FONT)
APP_VERSION = "2.1.0"
APP_NAME = "MATERIAL CIRCULANTE"

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
    "menu": "MENU INICIAL",
    "home": "CART · CONTROLE DE ESTOQUE",
    "history": "CART · HISTÓRICO DE SCANS",
    "saved": "CART · LISTAS SALVAS",
    "summary": "CART · RESUMO",
    "settings": "AJUSTES",
    "pv_folders": "PORTA VASOS · PASTAS",
    "pv_folder": "PORTA VASOS · PASTA",
    "pv_new": "PORTA VASOS · CLIENTE NA PASTA",
    "pv_summary": "PORTA VASOS · RESUMO",
}
# Módulo de cada tela (AJUSTES fica no módulo em que foi aberto)
SCREEN_MODULE = {
    "menu": "menu",
    "home": "cart", "history": "cart", "saved": "cart", "summary": "cart",
    "pv_folders": "pv", "pv_folder": "pv", "pv_new": "pv", "pv_summary": "pv",
}
MODULE_HOME = {"cart": "home", "pv": "pv_folders"}
# Para onde o "voltar" leva a partir de telas internas
SCREEN_PARENT = {"pv_new": "pv_folder", "pv_folder": "pv_folders"}
# Cores do status das pastas (texto, fundo)
PV_STATUS_STYLE = {
    pv.WAITING: (C.amber400, (0.98, 0.75, 0.14, 0.15)),
    pv.RETURNED: (C.green400, (0.29, 0.87, 0.5, 0.15)),
}
PV_FILTERS = [("TODAS", ""), ("AGUARDANDO", pv.WAITING), ("DEVOLVIDAS", pv.RETURNED)]


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
    also = StringProperty("")  # outras telas em que o botão fica aceso
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


class MenuCard(ButtonBehavior, BoxLayout):
    icon = StringProperty("")
    title = StringProperty("")
    subtitle = StringProperty("")
    badge = StringProperty("")


class ItemStepper(BoxLayout):
    """Quantidade de um item da devolução: [-] [número] [+]."""

    name = StringProperty("")
    value = NumericProperty(0)

    def step(self, delta):
        self.value = max(0, min(pv.MAX_QTY, int(self.value) + delta))

    def set_text(self, text):
        try:
            value = int(text) if text.strip() else 0
        except ValueError:
            return
        value = max(0, min(pv.MAX_QTY, value))
        if value != self.value:
            self.value = value

    def on_value(self, *args):
        field = self.ids.get("qty")
        if field is not None:
            text = str(int(self.value)) if self.value else ""
            if field.text != text:
                field.text = text
        app = App.get_running_app()
        if app is not None:
            app.pv_update_form_total()


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


class StatusPill(Label):
    status_color = ListProperty(C.amber400)


class FolderRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    folder_id = StringProperty("")
    name = StringProperty("")
    period = StringProperty("")
    status = StringProperty("")
    status_label = StringProperty("")
    status_color = ListProperty(C.amber400)
    detail = StringProperty("")


class ReturnRow(RecycleDataViewBehavior, BoxLayout):
    record_id = StringProperty("")
    number = NumericProperty(0)
    client = StringProperty("")
    dates = StringProperty("")
    items = StringProperty("")
    total = NumericProperty(0)
    thumbs = ListProperty([])     # caminhos das miniaturas (até 4)
    photo_count = NumericProperty(0)
    seq = StringProperty("")      # "2ª DEVOLUÇÃO" quando o cliente repete na pasta


class PhotoThumb(ButtonBehavior, BoxLayout):
    """Miniatura de foto clicável (abre o visualizador)."""

    source = StringProperty("")
    index = NumericProperty(0)
    extra = NumericProperty(0)   # "+N" quando há mais fotos do que miniaturas
    record_id = StringProperty("")


class PhotoViewer(ModalView):
    """Foto em tela cheia: anterior/próxima, girar e excluir."""

    names = ListProperty([])
    index = NumericProperty(0)
    photos_dir = StringProperty("")
    title = StringProperty("")
    source = StringProperty("")
    __events__ = ("on_change",)

    def on_change(self, names):
        pass

    def on_open(self):
        self._show()

    def _show(self):
        if not self.names:
            self.dismiss()
            return
        self.index = max(0, min(self.index, len(self.names) - 1))
        self.source = ph.photo_path(self.photos_dir, self.names[self.index])
        img = self.ids.get("image")
        if img is not None:
            img.source = self.source
            img.reload()

    def step(self, delta):
        if self.names:
            self.index = (self.index + delta) % len(self.names)
            self._show()

    def rotate(self):
        if self.names and ph.rotate(self.photos_dir, self.names[self.index]):
            self._show()
            self.dispatch("on_change", list(self.names))

    def delete(self):
        if not self.names:
            return
        names = list(self.names)
        names.pop(self.index)
        self.names = names
        self.dispatch("on_change", list(names))
        self._show()


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
class MenuScreen(Screen):
    pass


class HomeScreen(Screen):
    pass


class PvFoldersScreen(Screen):
    pass


class PvFolderScreen(Screen):
    pass


class PvNewScreen(Screen):
    pass


class PvSummaryScreen(Screen):
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


class FolderModal(ModalView):
    """Criar / editar pasta semanal (nome, início e fim)."""

    icon = StringProperty(I.folder_plus)
    title = StringProperty("")
    confirm_text = StringProperty("SALVAR")
    folder_id = StringProperty("")
    error = StringProperty("")
    __events__ = ("on_save",)

    def on_save(self, *args):
        pass

    def set_week(self, weeks_offset):
        start, end = pv.week_bounds(date.today() + timedelta(weeks=weeks_offset))
        self.ids.start.text = pv.format_date(start)
        self.ids.end.text = pv.format_date(end)
        if not self.folder_id:
            self.ids.name.text = ""

    def name_hint(self, start_text, end_text):
        start = pv.parse_date(start_text)
        end = pv.parse_date(end_text) if end_text.strip() else None
        if start is None:
            return "Ex: SEMANA 08.11 - 14.11"
        return pv.default_folder_name(start, end or start + timedelta(days=6))

    def submit(self):
        self.error = ""
        self.dispatch("on_save", self.ids.name.text, self.ids.start.text, self.ids.end.text)


class ClientPickRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    name = StringProperty("")
    detail = StringProperty("")


class ClientPickerModal(ModalView):
    """Lista de clientes: buscar, escolher, cadastrar novo ou remover da lista."""

    query = StringProperty("")
    can_add = BooleanProperty(False)
    total = NumericProperty(0)
    __events__ = ("on_pick",)

    def on_pick(self, name):
        pass

    def on_open(self):
        self.refresh()
        Clock.schedule_once(lambda dt: setattr(self.ids.search, "focus", True), 0.2)

    def on_query(self, *args):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        db = app.db
        uses = {}
        for f in db.folders:
            for r in f["records"]:
                uses[r["client"]] = uses.get(r["client"], 0) + 1
        names = db.search_clients(self.query)
        self.total = len(db.client_list)
        self.ids.rv.data = [{"name": n, "detail": "{} devolução(ões)".format(uses[n])
                             if uses.get(n) else "sem devoluções ainda"} for n in names]
        typed = pv.normalize_client(self.query)
        self.can_add = bool(typed) and typed not in db.client_list

    def pick(self, name):
        self.dispatch("on_pick", name)
        self.dismiss()

    def add_new(self):
        name = App.get_running_app().db.add_client(self.query)
        if name:
            self.pick(name)

    def remove(self, name):
        app = App.get_running_app()

        def _do():
            app.db.remove_client(name)
            app.refresh_pv()
            self.refresh()

        app.confirm("REMOVER DA LISTA",
                    "Tirar {} da lista de clientes?\nAs devoluções já registradas "
                    "continuam nas pastas.".format(name), _do, "REMOVER")


class ChoiceModal(ModalView):
    """Lista de opções (ex.: compartilhar como texto, PDF ou Excel)."""

    title = StringProperty("")
    subtitle = StringProperty("")
    icon = StringProperty(I.share)

    def add_choice(self, icon, title, subtitle, callback):
        row = ActionRow(icon=icon, title=title, subtitle=subtitle)

        def _go(*args):
            self.dismiss()
            callback()

        row.bind(on_release=_go)
        self.ids.choices.add_widget(row)


class SessionModal(ModalView):
    """Mostra os carrinhos de uma lista salva."""

    session_id = StringProperty("")
    name = StringProperty("")
    subtitle = StringProperty("")


class Root(FloatLayout):
    pass


# --- app -----------------------------------------------------------------
class NeonCartApp(App):
    title = "Material Circulante"
    app_name = APP_NAME
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
    current_screen = StringProperty("menu")
    screen_title = StringProperty(SCREEN_TITLES["menu"])
    module = StringProperty("menu")
    # porta vasos
    pv_filters = ListProperty(PV_FILTERS)
    pv_filter = StringProperty("")
    pv_folders_total = NumericProperty(0)
    pv_folders_visible = NumericProperty(0)
    pv_waiting_count = NumericProperty(0)
    pv_folder_id = StringProperty("")
    pv_folder_name = StringProperty("")
    pv_folder_period = StringProperty("")
    pv_folder_status = StringProperty(pv.WAITING)
    pv_folder_status_date = StringProperty("")
    pv_folder_count = NumericProperty(0)
    pv_folder_clients = NumericProperty(0)
    pv_folder_total = NumericProperty(0)
    pv_sum_filter = StringProperty("")
    pv_sum_folders = NumericProperty(0)
    pv_sum_total = NumericProperty(0)
    pv_sum_clients = NumericProperty(0)
    pv_editing = StringProperty("")
    pv_form_photos = ListProperty([])
    pv_form_carts = ListProperty([])
    pv_client_note = StringProperty("")
    pv_form_total = NumericProperty(0)
    pv_recent_clients = ListProperty([])
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
        try:  # fotos de cadastros cancelados / registros excluídos
            self.db.purge_photos()
        except Exception as exc:  # noqa: BLE001
            print("NeonCart: limpeza de fotos:", exc)
        self.root = Root()
        self._build_steppers()
        self.pv_reset_form()
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

    def chip_width(self, text, font_size="12sp"):
        """Largura do Chip para os dados do RecycleView (senão ele usa 100x100)."""
        lbl = CoreLabel(text=text, font_size=sp(float(font_size.rstrip("sp"))), bold=True)
        lbl.refresh()
        return lbl.texture.size[0] + dp(24)

    # --- navegação -----------------------------------------------------
    def go(self, name):
        if name == self.current_screen:
            return
        self.ids.sm.current = name
        self.current_screen = name
        self.module = SCREEN_MODULE.get(name, self.module)
        self.screen_title = SCREEN_TITLES.get(name, "")
        self.hide_snackbar()
        if name == "history":
            self.refresh_history()
        elif name == "saved":
            self.refresh_sessions()
        elif name == "summary":
            self.refresh_summary()
        elif name in ("pv_folders", "pv_folder", "pv_summary", "menu"):
            self.refresh_pv()

    def go_back(self):
        """Voltar: tela interna -> tela do módulo -> início do módulo -> menu inicial."""
        if self.current_screen == "menu":
            return False
        parent = SCREEN_PARENT.get(self.current_screen)
        if parent:
            if self.current_screen == "pv_new":
                self.pv_reset_form()
            self.go(parent)
            return True
        home = MODULE_HOME.get(self.module)
        if home and self.current_screen != home:
            self.go(home)
        else:
            self.go("menu")
        return True

    def _on_keyboard(self, window, key, *args):
        # 27 = botão voltar do Android / Esc
        if key == 27:
            return self.go_back()
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
        self.refresh_pv()

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

    def _export_file(self, filename, mime, writer, after=None):
        """Gera o arquivo com writer(caminho) e copia para Downloads.

        after(local, uri), se informado, substitui o aviso de "EXPORTADO".
        """
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
        if after is not None:
            after(where, uri)
            return
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

    # --- porta vasos: formulário do cliente ------------------------------
    def _build_steppers(self):
        grid = self.screen_ids("pv_new").items_grid
        grid.clear_widgets()
        self._steppers = {}
        for name in pv.ITEMS:
            if name == pv.CART_ITEM:  # carrinhos entram pelo código (bipar/digitar)
                continue
            stepper = ItemStepper(name=name)
            self._steppers[name] = stepper
            grid.add_widget(stepper)

    def pv_update_form_total(self):
        steppers = getattr(self, "_steppers", {})
        self.pv_form_total = (sum(int(s.value) for s in steppers.values())
                              + len(self.pv_form_carts))

    def on_pv_form_carts(self, *args):
        self.pv_update_form_total()
        if self.root is None:
            return
        box = self.screen_ids("pv_new").cart_chips
        box.clear_widgets()
        for code in self.pv_form_carts:
            text = "[font={}]{}[/font] {}  [font={}]{}[/font]".format(
                ICON_FONT_PATH, I.cart, code, ICON_FONT_PATH, I.close)
            chip = Chip(text=text, markup=True, active=True, font_size=sp(13))
            chip.bind(on_release=lambda c, code=code: self.pv_remove_cart(code))
            box.add_widget(chip)

    # --- carrinhos (bipar ou digitar o código) ---------------------------
    def _pv_cart_problem(self, code):
        """Mensagem se o código não pode entrar (repetido), senão ""."""
        if code in self.pv_form_carts:
            return "Carrinho {} já está nesta devolução.".format(code)
        folder = self.pv_folder()
        if folder is not None:
            other = pv.find_cart(folder, code, exclude_id=self.pv_editing or None)
            if other is not None:
                return "Carrinho {} já registrado nesta pasta para {} ({}).".format(
                    code, other["client"], pv.format_date(other["date"]))
        return ""

    def pv_add_cart(self, text=None):
        """Adiciona o código digitado no campo (ou o texto informado)."""
        field = self.screen_ids("pv_new").cart_code
        code = pv.normalize_cart_code(field.text if text is None else text)
        if not code:
            self._focus(field)
            return False
        problem = self._pv_cart_problem(code)
        if problem:
            self.feedback(False)
            self.show_duplicate(code)
            self.show_snackbar(problem, duration=4)
            field.text = ""
            return False
        self.pv_form_carts = list(self.pv_form_carts) + [code]
        field.text = ""
        self.feedback(True)
        self._focus(field)
        return True

    def pv_remove_cart(self, code):
        carts = list(self.pv_form_carts)
        if code in carts:
            carts.remove(code)
            self.pv_form_carts = carts

    def pv_scan_carts(self):
        """Câmera em modo contínuo: cada código lido entra na devolução."""
        client = self.screen_ids("pv_new").client.text.strip().upper()
        modal = ScannerModal(continuous=True, division=client, target_label="CLIENTE")
        modal.bind(on_result=self._pv_cart_scanned)
        modal.open()

    def _pv_cart_scanned(self, modal, code):
        code = pv.normalize_cart_code(code)
        problem = self._pv_cart_problem(code)
        if problem:
            modal.show_feedback(code, False, "JÁ REGISTRADO")
            self.feedback(False)
            return
        self.pv_form_carts = list(self.pv_form_carts) + [code]
        modal.show_feedback(code, True, "CARRINHO ADICIONADO")
        self.feedback(True)

    # --- cliente: digitar ou escolher na lista ---------------------------
    def pv_client_changed(self, text):
        returns = self.db.client_returns(self.pv_folder_id, text, exclude_id=self.pv_editing)
        if not returns:
            self.pv_client_note = ""
            return
        days = ", ".join("{} ({} itens)".format(pv.format_date(r["date"], short=True),
                                                pv.record_total(r)) for r in returns)
        self.pv_client_note = ("{} já tem {} devolução(ões) nesta pasta: {}. Esta será "
                               "registrada como nova devolução, com a data abaixo.".format(
                                   pv.normalize_client(text), len(returns), days))

    def pv_open_client_list(self):
        modal = ClientPickerModal()
        modal.ids.search.text = self.screen_ids("pv_new").client.text.strip()
        modal.bind(on_pick=lambda m, name: self.pv_pick_client(name))
        self._client_picker = modal
        modal.open()

    def _pick_from_row(self, row):
        picker = getattr(self, "_client_picker", None)
        if picker is not None:
            picker.pick(row.name)

    def _remove_from_row(self, row):
        picker = getattr(self, "_client_picker", None)
        if picker is not None:
            picker.remove(row.name)

    def pv_reset_form(self):
        ids = self.screen_ids("pv_new")
        ids.client.text = ""
        ids.date.text = pv.format_date(date.today())
        for stepper in self._steppers.values():
            stepper.value = 0
        self.pv_editing = ""
        self.pv_form_photos = []
        self.pv_form_carts = []
        ids.cart_code.text = ""
        self.pv_client_note = ""
        self.pv_update_form_total()

    # --- fotos do formulário --------------------------------------------
    def pv_take_photo(self):
        client = self.screen_ids("pv_new").client.text.strip().upper()
        modal = PhotoModal(photos_dir=self.db.photos_dir, client=client)
        modal.bind(on_photo=lambda m, name: self._pv_add_photos([name], quiet=True))
        modal.bind(on_dismiss=self._pv_camera_closed)
        modal.open()

    def _pv_camera_closed(self, modal):
        if modal.count:
            self.show_snackbar("{} foto(s) adicionada(s)".format(modal.count), duration=2)

    def pv_pick_photos(self):
        try:
            pu.pick_images(self._pv_picked)
        except Exception as exc:  # noqa: BLE001
            self.show_info("ERRO", "Não foi possível abrir a galeria.\n{}".format(exc))

    @mainthread
    def _pv_picked(self, blobs):
        names = []
        for data in blobs:
            try:
                names.append(ph.save_bytes(data, self.db.photos_dir))
            except Exception as exc:  # noqa: BLE001
                print("NeonCart: foto inválida:", exc)
        if names:
            self._pv_add_photos(names)
        elif blobs:
            self.show_info("FOTO INVÁLIDA", "Não foi possível abrir a imagem escolhida.",
                           icon=I.camera)

    def _pv_add_photos(self, names, quiet=False):
        self.pv_form_photos = list(self.pv_form_photos) + list(names)
        if not quiet:
            self.show_snackbar("{} foto(s) adicionada(s)".format(len(names)), duration=2)

    def on_pv_form_photos(self, *args):
        if self.root is None:
            return
        strip = self.screen_ids("pv_new").photo_strip
        strip.clear_widgets()
        folder = self.db.photos_dir
        for i, name in enumerate(self.pv_form_photos):
            strip.add_widget(PhotoThumb(source=ph.thumb_path(folder, name), index=i))

    def pv_open_photo(self, thumb):
        """Abre o visualizador a partir de uma miniatura (formulário ou lista)."""
        if thumb.record_id:
            _folder, record = self.db.find_record(thumb.record_id)
            if record is None:
                return
            viewer = PhotoViewer(names=list(record["photos"]), index=thumb.index,
                                 photos_dir=self.db.photos_dir, title=record["client"])

            def _changed(v, names, rid=thumb.record_id):
                self.db.set_record_photos(rid, names)
                self.refresh_pv()

            viewer.bind(on_change=_changed)
        else:
            viewer = PhotoViewer(names=list(self.pv_form_photos), index=thumb.index,
                                 photos_dir=self.db.photos_dir, title="FOTOS DO CLIENTE")
            viewer.bind(on_change=lambda v, names: setattr(self, "pv_form_photos", names))
        viewer.open()

    def pv_set_date(self, days_ago=0):
        self.screen_ids("pv_new").date.text = pv.format_date(
            date.today() - timedelta(days=days_ago))

    def pv_pick_client(self, client):
        self.screen_ids("pv_new").client.text = client

    def pv_new_record(self):
        """Abre o formulário para adicionar um cliente na pasta aberta."""
        if not self.db.get_folder(self.pv_folder_id):
            return
        self.pv_reset_form()
        self.go("pv_new")
        self._focus(self.screen_ids("pv_new").client)

    def pv_submit(self):
        ids = self.screen_ids("pv_new")
        items = {name: int(s.value) for name, s in self._steppers.items()}
        editing = self.pv_editing
        photos = list(self.pv_form_photos)
        carts = list(self.pv_form_carts)
        if ids.cart_code.text.strip():  # código digitado e não adicionado
            if not self.pv_add_cart():
                return
            carts = list(self.pv_form_carts)
        try:
            if editing:
                record = self.db.update_record(editing, ids.client.text, ids.date.text, items,
                                               photos=photos, carts=carts)
            else:
                record = self.db.add_record(self.pv_folder_id, ids.client.text, ids.date.text,
                                            items, photos=photos, carts=carts)
        except pv.PvError as exc:
            self.feedback(False)
            self.show_info("CONFIRA OS DADOS", str(exc), icon=I.flower)
            return
        self.pv_reset_form()
        self.refresh_pv()
        self.go("pv_folder")
        if record is None:  # registro apagado enquanto era editado
            return
        self.feedback(True)
        if editing:
            self.show_snackbar("{} atualizado".format(record["client"]))
        else:
            self.show_snackbar("{} registrado ({} itens)".format(
                record["client"], pv.record_total(record)), "+ OUTRO", self.pv_new_record)

    def pv_cancel_edit(self):
        self.pv_reset_form()
        self.go("pv_folder")

    def pv_edit(self, record_id):
        folder, record = self.db.find_record(record_id)
        if record is None:
            return
        self.pv_folder_id = folder["id"]
        ids = self.screen_ids("pv_new")
        ids.client.text = record["client"]
        ids.date.text = pv.format_date(record["date"])
        for name, stepper in self._steppers.items():
            stepper.value = record["items"].get(name, 0)
        self.pv_editing = record_id
        self.pv_form_photos = list(record.get("photos", []))
        self.pv_form_carts = list(record.get("carts", []))
        self.pv_client_changed(record["client"])
        self.pv_update_form_total()
        self.refresh_pv()
        self.go("pv_new")

    def pv_remove(self, record_id):
        folder, record, index = self.db.remove_record(record_id)
        if record is None:
            return
        if self.pv_editing == record_id:
            self.pv_reset_form()
        self.refresh_pv()

        def _undo():
            if self.db.restore_record(folder["id"], record, index):
                self.refresh_pv()

        self.show_snackbar("{} excluído da pasta".format(record["client"]), "DESFAZER", _undo)

    # --- porta vasos: pastas ---------------------------------------------
    def pv_folder(self):
        return self.db.get_folder(self.pv_folder_id)

    def pv_open_folder(self, folder_id):
        if self.db.get_folder(folder_id) is None:
            return
        self.pv_folder_id = folder_id
        self.refresh_pv()
        self.go("pv_folder")

    def pv_new_folder(self):
        start, end = pv.week_bounds(date.today())
        modal = FolderModal(title="NOVA PASTA", confirm_text="CRIAR PASTA", icon=I.folder_plus)
        modal.ids.start.text = pv.format_date(start)
        modal.ids.end.text = pv.format_date(end)
        modal.bind(on_save=self._save_new_folder)
        modal.open()

    def _save_new_folder(self, modal, name, start, end):
        try:
            folder = self.db.add_folder(name, start, end)
        except pv.PvError as exc:
            modal.error = str(exc)
            return
        modal.dismiss()
        self.pv_filter = ""
        self.pv_open_folder(folder["id"])
        self.show_snackbar("Pasta {} criada".format(folder["name"]), "+ CLIENTE",
                           self.pv_new_record)

    def pv_edit_folder(self):
        folder = self.pv_folder()
        if folder is None:
            return
        modal = FolderModal(title="EDITAR PASTA", confirm_text="SALVAR", icon=I.edit,
                            folder_id=folder["id"])
        modal.ids.name.text = folder["name"]
        modal.ids.start.text = pv.format_date(folder["start"])
        modal.ids.end.text = pv.format_date(folder["end"])
        modal.bind(on_save=self._save_edit_folder)
        modal.open()

    def _save_edit_folder(self, modal, name, start, end):
        try:
            self.db.update_folder(modal.folder_id, name, start, end)
        except pv.PvError as exc:
            modal.error = str(exc)
            return
        modal.dismiss()
        self.refresh_pv()

    def pv_toggle_status(self, folder_id=None):
        folder = self.db.get_folder(folder_id or self.pv_folder_id)
        if folder is None:
            return
        new = pv.WAITING if folder["status"] == pv.RETURNED else pv.RETURNED

        def _do():
            self.db.set_folder_status(folder["id"], new)
            self.refresh_pv()
            self.feedback(True)
            self.show_snackbar("{}: {}".format(folder["name"], pv.STATUS_LABELS[new]), duration=3)

        if new == pv.RETURNED:
            self.confirm("MARCAR COMO DEVOLVIDO",
                         "Confirmar que a pasta {} ({} itens) foi DEVOLVIDA?".format(
                             folder["name"], pv.folder_total(folder)),
                         _do, "DEVOLVIDO", icon=I.ok)
        else:
            _do()

    def pv_delete_folder(self):
        folder = self.pv_folder()
        if folder is None:
            return

        def _do():
            removed = self.db.delete_folder(folder["id"])
            self.pv_folder_id = ""
            self.refresh_pv()
            self.go("pv_folders")

            def _undo():
                self.db.reinsert_folder(removed)
                self.refresh_pv()

            self.show_snackbar("Pasta {} excluída".format(removed["name"]), "DESFAZER", _undo)

        self.confirm("EXCLUIR PASTA",
                     "Excluir a pasta {} com {} cliente(s)?".format(
                         folder["name"], len(folder["records"])), _do, "EXCLUIR")

    def pv_set_filter(self, value):
        self.pv_filter = value
        self.refresh_pv()

    def pv_set_sum_filter(self, value):
        self.pv_sum_filter = value
        self.refresh_pv()

    def _return_row_height(self, items, width, has_photos=False):
        # padding + cliente + data + barra de ações + espaçamentos
        base = dp(10) * 2 + dp(26) + dp(18) + dp(40) + dp(6) * 4
        text_width = max(width - dp(14) * 2, dp(80))
        lbl = CoreLabel(text=items, font_size=sp(12), text_size=(text_width, None))
        lbl.refresh()
        return base + lbl.texture.size[1] + (dp(62) if has_photos else 0)

    def refresh_pv(self):
        if self.root is None:
            return
        db = self.db
        self.pv_recent_clients = list(db.clients)
        self.pv_folders_total = len(db.folders)
        self.pv_waiting_count = len(db.folders_by_status(pv.WAITING))

        # lista de pastas
        visible = db.folders_by_status(self.pv_filter or None)
        self.pv_folders_visible = len(visible)
        rows = []
        for f in visible:
            fg, bg = PV_STATUS_STYLE[f["status"]]
            rows.append({
                "folder_id": f["id"],
                "name": f["name"],
                "period": pv.period_text(f),
                "status": f["status"],
                "status_label": pv.STATUS_LABELS[f["status"]],
                "status_color": list(fg),
                "detail": "{} clientes  ·  {} itens".format(
                    len(pv.totals_by_client(f["records"])), pv.folder_total(f)),
            })
        self.screen_ids("pv_folders").rv.data = rows

        # pasta aberta
        folder = db.get_folder(self.pv_folder_id)
        if folder is None:
            self.pv_folder_id = ""
            self.pv_folder_name = ""
            records = []
        else:
            self.pv_folder_name = folder["name"]
            self.pv_folder_period = pv.period_text(folder)
            self.pv_folder_status = folder["status"]
            self.pv_folder_status_date = (pv.format_date(folder["status_date"][:10])
                                          if folder["status_date"] else "")
            records = pv.sort_records(folder["records"])
        self.pv_folder_count = len(records)
        self.pv_folder_clients = len(pv.totals_by_client(records))
        self.pv_folder_total = sum(pv.record_total(r) for r in records)
        rv = self.screen_ids("pv_folder").rv
        width = rv.width if rv.width > 10 else Window.width - dp(32)
        data = []
        per_client = {}
        client_count = {}
        for r in records:
            client_count[r["client"]] = client_count.get(r["client"], 0) + 1
        for n, r in enumerate(records, start=1):
            items = pv.items_text(r)
            names = [p for p in r.get("photos", []) if ph.exists(db.photos_dir, p)]
            per_client[r["client"]] = per_client.get(r["client"], 0) + 1
            seq = ("{}ª DEVOLUÇÃO".format(per_client[r["client"]])
                   if client_count[r["client"]] > 1 else "")
            data.append({
                "record_id": r["id"],
                "number": n,
                "client": r["client"],
                "dates": "DEVOLUÇÃO " + pv.format_date(r["date"]),
                "items": items,
                "total": pv.record_total(r),
                "photo_count": len(names),
                "seq": seq,
                "thumbs": [ph.thumb_path(db.photos_dir, p) for p in names[:4]],
                "height": self._return_row_height(items, width, bool(names)),
            })
        rv.data = data

        # resumo
        chosen = db.folders_by_status(self.pv_sum_filter or None)
        all_recs = pv.all_records(chosen)
        sums, total = pv.totals(all_recs)
        by_client = pv.totals_by_client(all_recs)
        self.pv_sum_folders = len(chosen)
        self.pv_sum_total = total
        self.pv_sum_clients = len(by_client)
        ids = self.screen_ids("pv_summary")
        ids.item_bars.clear_widgets()
        top = max(sums.values()) or 1
        for name, qty in sums.items():
            if qty:
                ids.item_bars.add_widget(
                    DivisionBar(division=name, count=qty, ratio=qty / float(top)))
        ids.client_bars.clear_widgets()
        ctop = by_client[0][1] if by_client else 1
        for client, qty in by_client:
            ids.client_bars.add_widget(
                DivisionBar(division=client, count=qty, ratio=qty / float(ctop)))

    # --- porta vasos: imprimir / exportar / compartilhar ----------------
    def _pv_targets(self, scope):
        """scope: "folder" (pasta aberta), "list" (filtro da lista) ou "summary"."""
        if scope == "folder":
            folder = self.pv_folder()
            return [folder] if folder else []
        status = self.pv_filter if scope == "list" else self.pv_sum_filter
        return self.db.folders_by_status(status or None)

    def _pv_basename(self, scope, folders):
        if len(folders) == 1:
            return "PortaVasos_" + exporter.safe_name(folders[0]["name"])
        status = self.pv_filter if scope == "list" else self.pv_sum_filter
        label = {"": "Todas", pv.WAITING: "Aguardando", pv.RETURNED: "Devolvidas"}[status or ""]
        return "PortaVasos_Pastas_{}_{}".format(label, date.today().strftime("%d-%m-%Y"))

    def _pv_filter_label(self, scope):
        status = self.pv_filter if scope == "list" else self.pv_sum_filter
        return {"": "TODAS AS PASTAS", pv.WAITING: "AGUARDANDO DEVOLUÇÃO",
                pv.RETURNED: "DEVOLVIDAS"}[status or ""]

    def _pv_check(self, folders):
        if not folders:
            self.show_info("NADA PARA EXPORTAR", "Nenhuma pasta neste filtro.", icon=I.folder)
            return False
        return True

    def pv_print(self, scope="folder"):
        """Gera o PDF e abre no leitor do celular (que tem a opção Imprimir)."""
        folders = self._pv_targets(scope)
        if not self._pv_check(folders):
            return
        filename = self._pv_basename(scope, folders) + ".pdf"
        subtitle = self._pv_filter_label(scope)

        def _after(where, uri):
            if not pu.open_file(where, uri, pu.PDF_MIME):
                self.show_info("PDF SALVO", "Arquivo salvo em:\n{}\n\nAbra pelo app de arquivos "
                               "para imprimir.".format(where), icon=I.printer)

        self._export_file(filename, pu.PDF_MIME,
                          lambda p: reports.export_folders_pdf(folders, p, subtitle), after=_after)

    def _pv_photo_count(self, folders):
        return sum(1 for p in pv.all_photos(folders) if ph.exists(self.db.photos_dir, p))

    def pv_export_excel(self, scope="folder"):
        """Excel: pergunta COM ou SEM fotos quando houver fotos."""
        folders = self._pv_targets(scope)
        if not self._pv_check(folders):
            return
        count = self._pv_photo_count(folders)
        if not count:
            self._pv_save_excel(scope, folders, with_photos=False)
            return
        modal = ChoiceModal(title="EXPORTAR EXCEL", subtitle="{} foto(s) nesta exportação".format(
            count), icon=I.excel)
        modal.add_choice(I.camera, "Excel COM fotos",
                         "Fotos de cada cliente abaixo da tabela (arquivo maior)",
                         lambda: self._pv_save_excel(scope, folders, with_photos=True))
        modal.add_choice(I.excel, "Excel SEM fotos", "Só a tabela (arquivo leve)",
                         lambda: self._pv_save_excel(scope, folders, with_photos=False))
        modal.open()

    def _pv_excel_writer(self, folders, with_photos):
        photos_dir = self.db.photos_dir if with_photos else None
        return lambda p: exporter.export_folders_xlsx(folders, p, photos_dir)

    def _pv_excel_name(self, scope, folders, with_photos):
        return self._pv_basename(scope, folders) + ("_com_fotos" if with_photos else "") + ".xlsx"

    def _pv_save_excel(self, scope, folders, with_photos):
        self._export_file(self._pv_excel_name(scope, folders, with_photos), pu.XLSX_MIME,
                          self._pv_excel_writer(folders, with_photos))

    def pv_share(self, scope="folder"):
        folders = self._pv_targets(scope)
        if not self._pv_check(folders):
            return
        what = folders[0]["name"] if len(folders) == 1 else "{} pastas".format(len(folders))
        text = pv.share_text(folders)
        modal = ChoiceModal(title="COMPARTILHAR", subtitle=what)
        modal.add_choice(I.copy, "Copiar texto", "Cole direto no WhatsApp",
                         lambda: self._copy(text))
        modal.add_choice(I.message, "Enviar texto (WhatsApp)", "Lista organizada com os totais",
                         lambda: self._share(text))
        modal.add_choice(I.pdf, "PDF", "Relatório pronto para imprimir",
                         lambda: self._pv_share_file(scope, folders, "pdf"))
        if self._pv_photo_count(folders):
            modal.add_choice(I.camera, "Excel COM fotos", "Planilha .xlsx com as fotos",
                             lambda: self._pv_share_file(scope, folders, "xlsx_photos"))
            modal.add_choice(I.excel, "Excel SEM fotos", "Planilha .xlsx leve",
                             lambda: self._pv_share_file(scope, folders, "xlsx"))
        else:
            modal.add_choice(I.excel, "Excel", "Planilha .xlsx",
                             lambda: self._pv_share_file(scope, folders, "xlsx"))
        modal.open()

    def _pv_share_file(self, scope, folders, kind):
        if kind == "pdf":
            mime = pu.PDF_MIME
            filename = self._pv_basename(scope, folders) + ".pdf"
            subtitle = self._pv_filter_label(scope)
            writer = lambda p: reports.export_folders_pdf(folders, p, subtitle)  # noqa: E731
        else:
            with_photos = kind == "xlsx_photos"
            mime = pu.XLSX_MIME
            filename = self._pv_excel_name(scope, folders, with_photos)
            writer = self._pv_excel_writer(folders, with_photos)

        def _after(where, uri):
            if not pu.share_file(uri, mime, "Porta Vasos"):
                self.show_info("ARQUIVO SALVO", "Arquivo salvo em:\n" + where, icon=I.download)

        self._export_file(filename, mime, writer, after=_after)

    # --- porta vasos: cliente individual ---------------------------------
    def _copy(self, text):
        try:
            Clipboard.copy(text)
        except Exception as exc:  # noqa: BLE001
            self.show_info("ERRO", "Não foi possível copiar.\n{}".format(exc))
            return
        self.feedback(True)
        self.show_snackbar("Copiado! Cole no WhatsApp.", duration=3)

    def pv_copy_record(self, record_id):
        folder, record = self.db.find_record(record_id)
        if record is not None:
            self._copy(pv.record_text(record, folder))

    def pv_share_record(self, record_id):
        folder, record = self.db.find_record(record_id)
        if record is None:
            return
        text = pv.record_text(record, folder)
        names = [p for p in record.get("photos", []) if ph.exists(self.db.photos_dir, p)]
        modal = ChoiceModal(title="ENVIAR CLIENTE", subtitle="{} · {} itens".format(
            record["client"], pv.record_total(record)))
        modal.add_choice(I.copy, "Copiar texto", "Cole direto no WhatsApp",
                         lambda: self._copy(text))
        modal.add_choice(I.message, "Enviar texto", "WhatsApp, e-mail...",
                         lambda: self._share(text))
        if names:
            modal.add_choice(I.camera, "Enviar com fotos ({})".format(len(names)),
                             "Texto + fotos do material",
                             lambda: self._pv_share_with_photos(text, names))
        modal.open()

    def _pv_share_with_photos(self, text, names):
        paths = [ph.photo_path(self.db.photos_dir, n) for n in names]
        try:
            ok = pu.share_images(paths, text, "Enviar cliente")
        except Exception as exc:  # noqa: BLE001
            print("NeonCart: erro ao enviar fotos:", exc)
            ok = False
        if not ok:
            self._copy(text)
            self.show_info("FOTOS", "Não foi possível anexar as fotos neste aparelho. "
                           "O texto foi copiado; anexe as fotos pelo WhatsApp.", icon=I.camera)

    def pv_record_photos(self, record_id):
        """Abre as fotos do cliente (ou avisa que não há)."""
        _folder, record = self.db.find_record(record_id)
        if record is None:
            return
        if not record.get("photos"):
            self.show_info("SEM FOTOS", "Este cliente não tem fotos. Use EDITAR para adicionar.",
                           icon=I.camera)
            return
        thumb = PhotoThumb(record_id=record_id, index=0)
        self.pv_open_photo(thumb)

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
        self.pv_folder_id = ""
        self.refresh_all()
        self.show_info("BACKUP RESTAURADO",
                       "{}\n\n{} carrinhos na lista, {} listas salvas.".format(
                           name, summary["total"], summary["sessions"]), icon=I.db_import)


# Nome novo do app (o antigo continua valendo para não quebrar nada).
MaterialCirculanteApp = NeonCartApp


if __name__ == "__main__":
    NeonCartApp().run()
