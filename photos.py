"""Fotos dos registros do Porta Vasos (sem Kivy).

Cada foto é um JPEG na pasta "photos" do app, com uma miniatura ao lado
(<nome>_t.jpg). O registro guarda só o nome do arquivo.
"""

import io
import os
import uuid

MAX_SIDE = 1600       # lado maior da foto salva
THUMB_SIDE = 320      # lado maior da miniatura
QUALITY = 82


def _pil():
    from PIL import Image, ImageOps

    return Image, ImageOps


def photo_path(folder, name):
    return os.path.join(folder, name)


def thumb_path(folder, name):
    base, _ext = os.path.splitext(name)
    return os.path.join(folder, base + "_t.jpg")


def exists(folder, name):
    return bool(name) and os.path.exists(photo_path(folder, name))


def _write(img, folder, name):
    Image, _ = _pil()
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    img.save(photo_path(folder, name), "JPEG", quality=QUALITY, optimize=True)
    thumb = img.copy()
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.LANCZOS)
    thumb.save(thumb_path(folder, name), "JPEG", quality=78)


def save_image(img, folder):
    """Salva uma imagem PIL e retorna o nome do arquivo."""
    os.makedirs(folder, exist_ok=True)
    name = "pv_{}.jpg".format(uuid.uuid4().hex[:16])
    _write(img, folder, name)
    return name


def save_bytes(data, folder):
    """Salva bytes de uma imagem (galeria), já na orientação do EXIF."""
    Image, ImageOps = _pil()
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return save_image(img, folder)


def rotate(folder, name, clockwise=True):
    """Gira a foto 90° (e a miniatura)."""
    Image, _ = _pil()
    path = photo_path(folder, name)
    if not os.path.exists(path):
        return False
    with Image.open(path) as img:
        img = img.rotate(-90 if clockwise else 90, expand=True)
        img.load()
    _write(img, folder, name)
    return True


def delete(folder, name):
    for path in (photo_path(folder, name), thumb_path(folder, name)):
        try:
            os.remove(path)
        except OSError:
            pass


def purge_orphans(folder, keep):
    """Apaga fotos que nenhum registro usa mais. Retorna quantas apagou."""
    if not os.path.isdir(folder):
        return 0
    keep = set(keep)
    removed = 0
    for fname in os.listdir(folder):
        if not fname.startswith("pv_") or fname.endswith("_t.jpg"):
            continue
        if fname not in keep:
            delete(folder, fname)
            removed += 1
    return removed


def nv21_to_image(buf, width, height):
    """Quadro NV21 da câmera do Android -> imagem RGB."""
    Image, _ = _pil()
    size = width * height
    data = bytes(buf)
    y = Image.frombytes("L", (width, height), data[:size])
    vu = data[size:size + size // 2]
    half = (width // 2, height // 2)
    v = Image.frombytes("L", half, vu[0::2]).resize((width, height))
    u = Image.frombytes("L", half, vu[1::2]).resize((width, height))
    return Image.merge("YCbCr", (y, u, v)).convert("RGB")


def orient(img, rotation=0, mirror=False):
    """Aplica a mesma rotação/espelho que a prévia da câmera usa na tela."""
    _, ImageOps = _pil()
    if mirror:
        img = ImageOps.mirror(img)
    if rotation % 360:
        img = img.rotate(rotation, expand=True)
    return img


def thumbnail_for_excel(folder, name, max_w=260, max_h=195):
    """Bytes JPEG reduzidos para colocar na planilha (ou None)."""
    Image, _ = _pil()
    path = photo_path(folder, name)
    if not os.path.exists(path):
        return None, (0, 0)
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
        return out.getvalue(), img.size
