import os
import secrets
import uuid
from datetime import timedelta

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


def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def compute_price(breed: str, color: str, ears: str, paws: str) -> str:

    temp_item = OrderItem(
        cat_id=str(uuid.uuid4()),
        name="",
        breed=breed,
        color=color,
        ears=ears,
        paws=paws,
        price=0
    )
    price = order_service.calculate_price(temp_item)
    return f"{price} XML"



@app.route("/")
def index():
    return render_template("index.html", title="Главная")


@app.route("/about")
def about():
    return render_template("about.html", title="О нас")


def build_cat_image_path(breed: str, color: str, ears: str, paws: str) -> str:
    """
    Формируем имя файла по выбранным параметрам и проверяем его наличие.
    Если файла нет, возвращаем URL специальной картинки 'cats/special.png'.
    """

    def slug(s: str) -> str:
        return s.strip().lower().replace(" ", "-")

    fname = f"{slug(breed)}_{slug(color)}_{slug(ears)}_{slug(paws)}.png"

    # Абсолютный путь до файла в /static/cats/
    abs_path = os.path.join(app.root_path, "static", "cats", fname)

    if os.path.isfile(abs_path):
        return url_for("static", filename=f"cats/{fname}")
    else:
        # фолбэк
        return url_for("static", filename="cats/special.png")


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
    }
    price = compute_price(form_data["breed"], form_data["color"], form_data["ears"], form_data["paws"])

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
        action = request.form.get("action", "preview")

        form_data.update({"name": name, "breed": breed, "color": color, "ears": ears, "paws": paws})

        price = compute_price(breed, color, ears, paws)

        cat_img_url = build_cat_image_path(breed, color, ears, paws)

        if action == "add":
            cat = {
                "name": name or "Безымянный кот",
                "breed": breed,
                "color": color,
                "ears": ears,
                "paws": paws,
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
