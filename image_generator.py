# image_generator.py
from PIL import Image
import tempfile, os
from flask import send_file

def overlay_images(paths):
    # открываем все слои в RGBA
    imgs = [Image.open(p).convert("RGBA") for p in paths]

    base = imgs[0]
    for layer in imgs[1:]:
        # если размер отличается — подгоняем к размеру base
        if layer.size != base.size:
            layer = layer.resize(base.size, Image.LANCZOS)
        base = Image.alpha_composite(base, layer)
    return base

def compose_file(paths):
    """Собирает PNG из списка файлов и возвращает Flask Response."""
    img = overlay_images(paths)

    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(tmp_path, format="PNG")

    resp = send_file(tmp_path, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    @resp.call_on_close
    def _cleanup():
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass

    return resp
