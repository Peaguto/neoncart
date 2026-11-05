"""Tela de leitura de código de barras / QR com a câmera."""

import threading
import time

from kivy.clock import Clock, mainthread
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.modalview import ModalView

import platform_utils as pu

try:
    from PIL import Image
    from pyzbar.pyzbar import decode as zbar_decode
    DECODER_ERROR = ""
except Exception as exc:  # noqa: BLE001 - lib nativa ausente
    Image = None
    zbar_decode = None
    DECODER_ERROR = str(exc)

RESOLUTION = (640, 480)
SCAN_INTERVAL = 0.15
SAME_CODE_COOLDOWN = 2.5  # modo contínuo: ignora o mesmo código por N s
ANY_CODE_COOLDOWN = 0.8   # modo contínuo: pausa entre leituras


def decode_gray(image):
    """Retorna o texto do primeiro código encontrado na imagem ou None."""
    if zbar_decode is None or image is None:
        return None
    for result in zbar_decode(image):
        text = result.data.decode("utf-8", "replace").strip()
        if text:
            return text
    return None


def grab_gray_frame(camera):
    """Captura o quadro atual em tons de cinza (chamar na thread principal)."""
    if Image is None or camera is None:
        return None
    core = getattr(camera, "_camera", None)
    if core is None:
        return None
    if pu.IS_ANDROID and hasattr(core, "grab_frame"):
        buf = core.grab_frame()  # NV21: o plano Y já é a imagem em cinza
        if not buf:
            return None
        w, h = core._resolution
        return Image.frombytes("L", (w, h), bytes(buf[: w * h]))
    tex = camera.texture
    if tex is None:
        return None
    return Image.frombytes("RGBA", tex.size, tex.pixels).convert("L")


class ScannerModal(ModalView):
    """Mostra a prévia da câmera e devolve o código lido em on_result.

    No modo contínuo a janela continua aberta; quem trata on_result chama
    show_feedback() para mostrar se o código foi registrado.
    """

    status = StringProperty("INICIANDO ÓPTICA...")
    torch_on = BooleanProperty(False)
    camera_total = NumericProperty(1)
    rotation = NumericProperty(0)
    mirror = BooleanProperty(False)
    preview_ratio = NumericProperty(4 / 3)
    camera = ObjectProperty(None, allownone=True)
    continuous = BooleanProperty(False)
    division = StringProperty("")
    count = NumericProperty(0)
    last_code = StringProperty("")
    last_message = StringProperty("")
    last_ok = BooleanProperty(True)

    __events__ = ("on_result",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._index = 0
        self._busy = False
        self._done = False
        self._event = None
        self._last_seen = ("", 0.0)
        self._pause_until = 0.0

    def on_result(self, code):
        pass

    # --- ciclo de vida -------------------------------------------------
    def on_open(self):
        if zbar_decode is None:
            self.status = "LEITOR INDISPONÍVEL"
            return
        pu.request_camera_permission(self._permission_result)

    @mainthread
    def _permission_result(self, granted):
        if not granted:
            self.status = "PERMISSÃO DA CÂMERA NEGADA"
            return
        try:
            self.camera_total = pu.camera_count()
            self._index = pu.back_camera_index()
        except Exception:  # noqa: BLE001
            self.camera_total, self._index = 1, 0
        self._start_camera()

    def on_dismiss(self):
        self._stop_camera()

    def _start_camera(self):
        from kivy.uix.camera import Camera

        self._stop_camera()
        try:
            cam = Camera(index=self._index, resolution=RESOLUTION, play=True,
                         fit_mode="fill")
        except Exception as exc:  # noqa: BLE001
            self.status = "CÂMERA INDISPONÍVEL"
            print("NeonCart: erro ao abrir câmera:", exc)
            return
        if getattr(cam, "_camera", None) is None:
            self.status = "CÂMERA INDISPONÍVEL"
            return
        self.rotation, self.mirror = pu.camera_display(self._index)
        self._apply_transform(cam)
        self.torch_on = False
        self.camera = cam
        self.ids.preview_box.add_widget(cam)
        self._layout_camera()
        self.status = ""
        self._event = Clock.schedule_interval(self._scan_tick, SCAN_INTERVAL)

    def _apply_transform(self, cam):
        """Gira a prévia (o sensor do Android fica deitado) e espelha a frontal."""
        from kivy.graphics import PopMatrix, PushMatrix, Rotate, Scale

        with cam.canvas.before:
            PushMatrix()
            rot = Rotate(angle=self.rotation)
            scale = Scale(x=-1 if self.mirror else 1, y=1, z=1)
        with cam.canvas.after:
            PopMatrix()

        def _sync(*_):
            rot.origin = cam.center
            scale.origin = cam.center

        cam.bind(pos=_sync, size=_sync)
        _sync()

    def _stop_camera(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None
        cam = self.camera
        if cam is not None:
            pu.release_camera(cam)
            if cam.parent is not None:
                cam.parent.remove_widget(cam)
        self.camera = None
        self.torch_on = False

    def _layout_camera(self, *args):
        """Imita object-fit: cover dentro da área quadrada."""
        cam = self.camera
        box = self.ids.get("preview_box")
        if cam is None or box is None:
            return
        side = max(box.width, box.height)
        ratio = self.preview_ratio
        if cam.texture_size and cam.texture_size[1]:
            ratio = cam.texture_size[0] / float(cam.texture_size[1])
        cam.size_hint = (None, None)
        cam.size = (side * ratio, side)
        cam.center = box.center

    # --- leitura -------------------------------------------------------
    def _scan_tick(self, dt):
        if self._busy or self._done or self.camera is None:
            return
        self._layout_camera()
        try:
            frame = grab_gray_frame(self.camera)
        except Exception as exc:  # noqa: BLE001
            print("NeonCart: erro ao capturar quadro:", exc)
            return
        if frame is None:
            return
        self._busy = True
        threading.Thread(target=self._decode_worker, args=(frame,), daemon=True).start()

    def _decode_worker(self, frame):
        try:
            code = decode_gray(frame)
        except Exception as exc:  # noqa: BLE001
            print("NeonCart: erro ao decodificar:", exc)
            code = None
        self._decoded(code)

    @mainthread
    def _decoded(self, code):
        self._busy = False
        if not code or self._done:
            return
        if not self.continuous:
            self._done = True
            self.dispatch("on_result", code)
            self.dismiss()
            return
        now = time.monotonic()
        last_code, last_time = self._last_seen
        if now < self._pause_until or (code == last_code and now - last_time < SAME_CODE_COOLDOWN):
            return
        self._last_seen = (code, now)
        self._pause_until = now + ANY_CODE_COOLDOWN
        self.dispatch("on_result", code)

    def show_feedback(self, code, ok, message):
        """Modo contínuo: mostra o resultado do último código lido."""
        self.last_code = code
        self.last_ok = ok
        self.last_message = message
        if ok:
            self.count += 1

    # --- botões --------------------------------------------------------
    def toggle_torch(self):
        if self.camera is None:
            return
        wanted = not self.torch_on
        if pu.set_torch(self.camera, wanted):
            self.torch_on = wanted
        else:
            from kivy.app import App
            App.get_running_app().show_info(
                "FLASH", "O flash não é suportado por esta câmera.")

    def switch_camera(self):
        if self.camera_total < 2:
            return
        self._index = (self._index + 1) % self.camera_total
        self._start_camera()
