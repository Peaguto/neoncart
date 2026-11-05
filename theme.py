"""Cores do tema neon (mesmas do app web / Tailwind)."""

from kivy.utils import get_color_from_hex as _hex


class C:
    bg = _hex("#09090b")
    card = _hex("#12121a")
    field = _hex("#0a0a0f")
    border = _hex("#581c8780")       # purple-900/50
    border_soft = _hex("#a855f74d")  # purple-500/30
    pink500 = _hex("#ec4899")
    pink600 = _hex("#db2777")
    pink400 = _hex("#f472b6")
    pink300 = _hex("#f9a8d4")
    pink200 = _hex("#fbcfe8")
    pink100 = _hex("#fce7f3")
    purple300 = _hex("#d8b4fe")
    purple400 = _hex("#c084fc")
    purple500 = _hex("#a855f7")
    purple600 = _hex("#9333ea")
    purple700 = _hex("#7e22ce")
    purple800 = _hex("#6b21a8")
    purple900 = _hex("#581c87")
    hint = _hex("#581c87aa")
    red500 = _hex("#ef4444")
    red200 = _hex("#fecaca")
    red_bg = _hex("#1a0505")
    green400 = _hex("#4ade80")
    white = (1, 1, 1, 1)
    green500 = _hex("#22c55e")
    blue400 = _hex("#60a5fa")
    amber400 = _hex("#fbbf24")
    overlay = (0, 0, 0, 0.95)


# Ícones (Material Design Icons)
ICON_FONT = "assets/fonts/materialdesignicons-webfont.ttf"


class I:
    cart = "\U000F0110"
    grid = "\U000F0570"
    plus = "\U000F0415"
    history = "\U000F02DA"
    share = "\U000F0497"
    download = "\U000F01DA"
    trash = "\U000F01B4"
    trash2 = "\U000F09E7"
    camera = "\U000F0100"
    close = "\U000F0156"
    switch = "\U000F0108"
    flash = "\U000F0241"
    flash_off = "\U000F06D5"
    alert = "\U000F0026"
    message = "\U000F0369"
    search = "\U000F0349"
    edit = "\U000F03EB"
    save = "\U000F0193"
    save_all = "\U000F0194"
    cog = "\U000F0493"
    chart = "\U000F0128"
    folders = "\U000F0253"
    archive = "\U000F003C"
    undo = "\U000F054C"
    eye = "\U000F0208"
    restore = "\U000F006F"
    file_import = "\U000F0220"
    file_export = "\U000F021D"
    ok = "\U000F05E0"
    error = "\U000F0159"
    keyboard = "\U000F030C"
    barcode = "\U000F0072"
    repeat = "\U000F0456"
    vibrate = "\U000F0566"
    volume = "\U000F057E"
    info = "\U000F02FC"
    bullets = "\U000F0279"
    sweep = "\U000F05E9"
    where = "\U000F0F07"
    db_export = "\U000F095E"
    db_import = "\U000F095D"


def gradient_texture(*hex_colors, steps=64):
    """Textura horizontal em degradê (Kivy não tem gradiente nativo)."""
    from kivy.graphics.texture import Texture

    stops = [_hex(h) for h in hex_colors]
    buf = bytearray()
    segments = len(stops) - 1
    for i in range(steps):
        t = i / (steps - 1) * segments
        k = min(int(t), segments - 1)
        f = t - k
        a, b = stops[k], stops[k + 1]
        buf += bytes(int(255 * (a[c] + (b[c] - a[c]) * f)) for c in range(4))
    tex = Texture.create(size=(steps, 1), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    tex.wrap = "clamp_to_edge"
    return tex
