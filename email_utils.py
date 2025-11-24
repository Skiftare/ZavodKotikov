import os
from io import BytesIO

from flask import current_app
from flask_mail import Message

from extensions import mail
from image_generator import overlay_images
from payment_service import Order  # только для подсказок типов (можно убрать)


def _slug(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


def _cat_layer_paths_for_email(breed: str, color: str, ears: str,
                               paws: str, container: str, pattern: str) -> list[str]:
    """
    Копия логики из app.py::_cat_layer_paths, но без импорта app,
    пути считаем через current_app.root_path.
    """
    root = current_app.root_path
    layers_dir = os.path.join(root, "static", "cats", "layers")
    special_img = os.path.join(root, "static", "cats", "special.png")

    breed_fn = f"{_slug(breed)}.png"
    color_fn = f"{_slug(color)}.png"
    ears_fn = f"{_slug(ears)}.png"

    # ОБРАТИ ВНИМАНИЕ: порядок файлов такой же, как у тебя в app.py
    filenames = [ears_fn, color_fn, breed_fn]

    if _slug(paws) != "в-цвет":
        paws_fn = f"{_slug(paws)}.png"
        filenames.append(paws_fn)

    if _slug(container) != "без-контейнера":
        container_fn = f"{_slug(container)}.png"
        filenames.append(container_fn)

    if pattern != "Обычная":
        pattern_fn = f"{_slug(pattern)}.png"
        filenames.insert(2, pattern_fn)  # после породы, перед цветом

    paths: list[str] = []
    missing = False

    for fn in filenames:
        p = os.path.join(layers_dir, fn)
        if os.path.isfile(p):
            paths.append(p)
        else:
            current_app.logger.warning(f"Слой не найден: {p}")
            missing = True

    if not paths and os.path.isfile(special_img):
        current_app.logger.error("Не найдено ни одного слоя, используем special.png")
        return [special_img]

    if missing and os.path.isfile(special_img):
        current_app.logger.error("Часть слоев не найдена, добавляем special.png поверх")
        paths.append(special_img)

    if not paths:
        # вообще ничего нет — вернём пустой список, вызывающий код обработает
        current_app.logger.error("Не найдены слои и отсутствует special.png")
        return []

    return paths


def send_nft_cats_email(order: Order) -> None:
    """
    Отправляет письмо с информацией о заказе и PNG-картинками котов во вложениях.
    """
    if not order.email:
        return

    text_lines = [
        "Привет! ✨",
        "",
        f"Оплата заказа #{str(order.id)[:8]} успешно подтверждена.",
        "",
        "Состав заказа:",
    ]

    for i, item in enumerate(order.items, start=1):
        text_lines.append(
            f"{i}. {item.name} ({item.breed}); цвет: {item.color}, "
            f"уши: {item.ears}, лапки: {item.paws}, "
            f"контейнер: {item.container}, рисунок: {item.pattern}"
        )

    text_lines.append("")
    text_lines.append("PNG-картинки ваших котов во вложениях этого письма.")
    text_lines.append("")
    text_lines.append("Спасибо, что выбрали Завод котов! 🐾")

    msg = Message(
        subject=f"Ваши NFT-коты с Завода котов — заказ #{str(order.id)[:8]}",
        recipients=[order.email],
    )
    msg.body = "\n".join(text_lines)

    # генерируем PNG для каждого кота и прикрепляем
    for i, item in enumerate(order.items, start=1):
        paths = _cat_layer_paths_for_email(
            breed=item.breed,
            color=item.color,
            ears=item.ears,
            paws=item.paws,
            container=item.container,
            pattern=item.pattern,
        )
        if not paths:
            continue

        # собираем картинку тем же способом, что и /compose-cat
        img = overlay_images(paths)

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        filename = f"cat_{i}_{item.name or 'kot'}.png"
        msg.attach(filename, "image/png", buf.read())

    current_app.logger.info(f"Отправляем письмо с котами на {order.email}")
    mail.send(msg)
