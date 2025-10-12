import os
import secrets
import uuid
from image_generator import compose_file
from datetime import timedelta
from werkzeug.exceptions import NotFound

from flask import Flask, render_template, request, redirect, url_for, session, flash

from order_service import OrderService
from payment_gateway import MockPaymentGateway
from payment_service import OrderItem, PaymentStatus

# Инициализация сервисов
payment_gateway = MockPaymentGateway()
order_service = OrderService(payment_gateway)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(days=7)
LAYERS_DIR = os.path.join(app.root_path, "static", "cats", "layers")
SPECIAL_IMG = os.path.join(app.root_path, "static", "cats", "special.png")

def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def compute_price(breed: str, color: str, ears: str, paws: str, container: str) -> str:
    temp_item = OrderItem(
        cat_id=str(uuid.uuid4()),
        name="",
        breed=breed,
        color=color,
        ears=ears,
        paws=paws,
        price=0,
        container=container
    )
    price = order_service.calculate_price(temp_item)
    return f"{price} XML"




@app.route("/")
def index():
    return render_template("index.html", title="Главная")


@app.route("/about")
def about():
    return render_template("about.html", title="О нас")

def _ensure_layer_or_fallback(filename: str) -> str:
    """Вернёт путь к слою, если есть; иначе путь к special.png (если и его нет — 404)."""
    candidate = os.path.join(LAYERS_DIR, filename)
    if os.path.isfile(candidate):
        return candidate
    if os.path.isfile(SPECIAL_IMG):
        return SPECIAL_IMG
    # если и фолбэк отсутствует — бросаем 404
    raise NotFound("Ни слой, ни special.png не найдены")

def _slug(s: str) -> str:
    return s.strip().lower().replace(" ", "-")

def _cat_layer_paths(breed: str, color: str, ears: str, paws: str, container: str) -> list[str]:
    """
    Слои в порядке наложения:
      1) <порода>-<цвет>.png
      2) <уши>.png
      3) <лапы>.png (если лапы != 'в цвет')
    Если отсутствует хотя бы один из нужных слоёв — добавляем SPECIAL_IMG поверх.
    Если не найден ни один слой и есть SPECIAL_IMG — возвращаем только SPECIAL_IMG.
    Если нет вообще ничего — 404.
    """
    # формируем имена файлов
    breed_fn = f"{_slug(breed)}.png"
    color_fn = f"{_slug(color)}.png"
    ears_fn  = f"{_slug(ears)}.png"

    filenames = [ears_fn, color_fn, breed_fn]

    # лапы добавляем только если они НЕ "в цвет"
    if _slug(paws) != "в-цвет":
        paws_fn = f"{_slug(paws)}.png"
        filenames.append(paws_fn)

    # контейнер тоже с условием
    if _slug(container) != "без-контейнера":
        container_fn = f"{_slug(container)}.png"
        filenames.append(container_fn)

    paths: list[str] = []
    missing = False

    for fn in filenames:
        p = os.path.join(LAYERS_DIR, fn)
        if os.path.isfile(p):
            paths.append(p)
        else:
            missing = True  # какого-то слоя не хватает

    print(filenames)

    # если вообще ничего не нашли, но есть special — отдаём только special
    if not paths and os.path.isfile(SPECIAL_IMG):
        return [SPECIAL_IMG]

    # если чего-то не хватает и special существует — кладём special поверх всех
    if missing and os.path.isfile(SPECIAL_IMG):
        paths.append(SPECIAL_IMG)

    if not paths:
        # нет ни одного слоя и нет special — явная ошибка
        raise NotFound("Слои не найдены, отсутствует и special.png")

    return paths

@app.route("/compose-cat.png")
def compose_cat():
    breed = request.args.get("breed", "Британец")
    color = request.args.get("color", "Серый")
    ears  = request.args.get("ears", "Острые в разные стороны")
    paws  = request.args.get("paws", "В цвет")
    container = request.args.get("container", "Без контейнера")

    files = _cat_layer_paths(breed, color, ears, paws, container)
    return compose_file(files)


# Страница «Магазин»
@app.route("/shop", methods=["GET", "POST"])
def shop():
    cat_img_url = None

    form_data = {
        "name": "",
        "breed": "Британец",
        "color": "Серый",
        "ears": "Острые в разные стороны",
        "paws": "В цвет",
        "container": "Без контейнера",  # <— добавили
    }
    price = compute_price(form_data["breed"], form_data["color"], form_data["ears"], form_data["paws"],
                          form_data["container"])

    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not token or token != session.get("_csrf_token"):
            flash("Неверный CSRF-токен", "error")
            return redirect(url_for("shop"))

        name = request.form.get("name", "").strip()
        breed = request.form.get("breed", form_data["breed"])
        color = request.form.get("color", form_data["color"])
        ears = request.form.get("ears", form_data["ears"])
        paws = request.form.get("paws", form_data["paws"])
        container = request.form.get("container", form_data["container"])
        action = request.form.get("action", "preview")

        form_data.update({"name": name, "breed": breed, "color": color, "ears": ears, "paws": paws,
                          "container": container})

        price = compute_price(breed, color, ears, paws, container)

        cat_img_url = url_for(
            "compose_cat",
            breed=breed,
            color=color,
            ears=ears,
            paws=paws,
            container=container
        )

        if action == "add":
            cat = {
                "name": name or "Безымянный кот",
                "breed": breed,
                "color": color,
                "ears": ears,
                "paws": paws,
                "container": container,
                "price": price,
                "image": cat_img_url,
            }

            session.setdefault("orders", []).append(cat)
            session.modified = True
            flash(f"Кот '{cat['name']}' добавлен в корзину!", "success")

    return render_template(
        "shop.html",
        title="Генератор кота",
        cat_img_url=cat_img_url,
        form_data=form_data,
        price=price,
    )


@app.route("/account")
def account():
    orders = session.get("orders", [])
    return render_template("account.html", title="Корзина", orders=orders)


@app.route("/checkout", methods=["POST"])
def checkout():
    token = request.form.get("csrf_token")
    if not token or token != session.get("_csrf_token"):
        flash("Неверный CSRF-токен", "error")
        return redirect(url_for("account"))

    if "orders" not in session:
        flash("Корзина пуста", "error")
        return redirect(url_for("account"))

    # Убедимся что у нас есть session_id
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    try:
        app.logger.info(f"Создаём заказ из корзины: {session['orders']}")

        items = []
        for cat in session["orders"]:
            price = int(cat["price"].split()[0])
            items.append(
                OrderItem(
                    cat_id=str(uuid.uuid4()),
                    name=cat["name"],
                    breed=cat["breed"],
                    color=cat["color"],
                    ears=cat["ears"],
                    paws=cat["paws"],
                    container=cat["container"],
                    price=price
                )
            )

        # Используем наш собственный session_id
        order = order_service.create_order(session["session_id"], items)
        app.logger.info(f"Создан заказ {order.id}")

        return redirect(url_for("payment_page", order_id=order.id))

    except Exception as e:
        app.logger.error(f"Ошибка создания заказа: {str(e)}")
        flash(f"Ошибка при создании заказа: {str(e)}", "error")
        return redirect(url_for("account"))


@app.route("/payment/<order_id>")
def payment_page(order_id):
    if "session_id" not in session:
        flash("Сессия устарела", "error")
        return redirect(url_for("account"))

    order = order_service.get_order(order_id, session["session_id"])
    if not order:
        flash("Заказ не найден или доступ запрещён", "error")
        return redirect(url_for("account"))
    return render_template("payment.html", title="Оплата", order=order)


# Добавляем обработчик для /payment без order_id
@app.route("/payment")
def payment_redirect():
    flash("Некорректный URL заказа", "error")
    return redirect(url_for("account"))


@app.route("/confirm-payment/<order_id>", methods=["POST"])
def confirm_payment(order_id):
    if "session_id" not in session:
        flash("Сессия устарела", "error")
        return redirect(url_for("account"))

    token = request.form.get("csrf_token")
    if not token or token != session.get("_csrf_token"):
        flash("Неверный CSRF-токен", "error")
        return redirect(url_for("payment_page", order_id=order_id))

    email = request.form.get("email")
    transaction_id = request.form.get("transaction_id")

    if not email or not transaction_id:
        flash("Необходимо заполнить все поля", "error")
        return redirect(url_for("payment_page", order_id=order_id))

    try:
        status = order_service.process_payment(order_id, session["session_id"], transaction_id)

        if status == PaymentStatus.SUCCESS:
            order = order_service.get_order(order_id, session["session_id"])
            if order:
                order.email = email
                session.pop("orders", None)
            return redirect(url_for("payment_success", order_id=order_id))
        elif status == PaymentStatus.FAILED or status is None:
            return redirect(url_for("payment_failed", order_id=order_id))

    except Exception as e:
        app.logger.error(f"Ошибка при подтверждении оплаты: {str(e)}")
        return redirect(url_for("payment_failed", order_id=order_id))

    return redirect(url_for("account"))


@app.route("/payment-success/<order_id>")
def payment_success(order_id):
    if "session_id" not in session:
        flash("Сессия устарела", "error")
        return redirect(url_for("account"))

    order = order_service.get_order(order_id, session["session_id"])
    if not order or order.status != PaymentStatus.SUCCESS:
        flash("Заказ не найден", "error")
        return redirect(url_for("account"))

    return render_template("payment_success.html", title="Успешная оплата", order=order)


@app.route("/payment-failed/<order_id>")
def payment_failed(order_id):
    if "session_id" not in session:
        flash("Сессия устарела", "error")
        return redirect(url_for("account"))

    order = order_service.get_order(order_id, session["session_id"])
    if not order:
        flash("Заказ не найден", "error")
        return redirect(url_for("account"))

    return render_template("payment_failed.html", title="Ошибка оплаты", order=order)


if __name__ == "__main__":
    app.run(debug=False, port=7070)
