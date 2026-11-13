"""Câmera para fotografar o material devolvido (várias fotos seguidas)."""

from kivy.animation import Animation
from kivy.clock import mainthread
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.modalview import ModalView

import photos as ph
import platform_utils as pu

# Tenta HD; se a câmera não aceitar, usa a resolução do leitor de código.
RESOLUTIONS = [(1280, 720), (640, 480)]


def grab_rgb_frame(camera):
    """Quadro atual da câmera como imagem PIL RGB (chamar na thread principal)."""
    from PIL import Image

    core = getattr(camera, "_camera", None)
    if core is None:
        return None
    if pu.IS_ANDROID and hasattr(core, "grab_frame"):
        buf = core.grab_frame()  # NV21
        if not buf:
            return None
        w, h = core._resolution
        return ph.nv21_to_image(buf, w, h)
    tex = camera.texture
    if tex is None:
        return None
    img = Image.frombytes("RGBA", tex.size, tex.pixels).convert("RGB")
    return img.transpose(Image.FLIP_TOP_BOTTOM)  # textura do Kivy é de baixo para cima


class PhotoModal(ModalView):
    """Prévia da câmera; cada toque em FOTOGRAFAR dispara on_photo(nome_do_arquivo)."""

    status = StringProperty("INICIANDO CÂMERA...")
    torch_on = BooleanProperty(False)
    camera_total = NumericProperty(1)
    rotation = NumericProperty(0)
    mirror = BooleanProperty(False)
    camera = ObjectProperty(None, allownone=True)
    count = NumericProperty(0)
    photos_dir = StringProperty("")
    client = StringProperty("")

    __events__ = ("on_photo",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._index = 0

    def on_photo(self, name):
        pass

    # --- ciclo de vida -------------------------------------------------
    def on_open(self):
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

        from scanner import ScannerModal

        self._stop_camera()
        cam = None
        for resolution in RESOLUTIONS:
            try:
                cam = Camera(index=self._index, resolution=resolution, play=True,
                             fit_mode="contain")
            except Exception as exc:  # noqa: BLE001
                print("NeonCart: câmera {}: {}".format(resolution, exc))
                cam = None
                continue
            if getattr(cam, "_camera", None) is not None:
                break
            cam = None
        if cam is None:
            self.status = "CÂMERA INDISPONÍVEL"
            return
        self.rotation, self.mirror = pu.camera_display(self._index)
        ScannerModal._apply_transform(self, cam)
        self.torch_on = False
        self.camera = cam
        self.ids.preview_box.add_widget(cam)
        self._layout_camera()
        cam.bind(texture_size=self._layout_camera)
        self.status = ""

    def _stop_camera(self):
        cam = self.camera
        if cam is not None:
            pu.release_camera(cam)
            if cam.parent is not None:
                cam.parent.remove_widget(cam)
        self.camera = None
        self.torch_on = False

    def _layout_camera(self, *args):
        """Mostra a imagem inteira (sem cortar) dentro da área da prévia."""
        cam = self.camera
        box = self.ids.get("preview_box")
        if cam is None or box is None:
            return
        tw, th = cam.texture_size if cam.texture_size and cam.texture_size[1] else (4, 3)
        rotated = abs(self.rotation) % 180 == 90
        # tamanho que a imagem ocupa já girada
        iw, ih = (th, tw) if rotated else (tw, th)
        scale = min(box.width / float(iw), box.height / float(ih))
        w, h = tw * scale, th * scale
        cam.size_hint = (None, None)
        cam.size = (w, h)
        cam.center = box.center

    # --- foto ----------------------------------------------------------
    def capture(self):
        if self.camera is None:
            return
        try:
            img = grab_rgb_frame(self.camera)
            if img is None:
                return
            img = ph.orient(img, self.rotation, self.mirror)
            name = ph.save_image(img, self.photos_dir)
        except Exception as exc:  # noqa: BLE001
            print("NeonCart: erro ao fotografar:", exc)
            self.status = "ERRO AO FOTOGRAFAR"
            return
        self.count += 1
        flash = self.ids.flash
        Animation.cancel_all(flash)
        flash.opacity = 0.85
        Animation(opacity=0, d=0.35).start(flash)
        self.dispatch("on_photo", name)

    # --- botões --------------------------------------------------------
    def toggle_torch(self):
        if self.camera is None:
            return
        wanted = not self.torch_on
        if pu.set_torch(self.camera, wanted):
            self.torch_on = wanted

    def switch_camera(self):
        if self.camera_total < 2:
            return
        self._index = (self._index + 1) % self.camera_total
        self._start_camera()
