import os
import secrets
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(days=7)

def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]

app.jinja_env.globals["csrf_token"] = generate_csrf_token

def compute_price(breed: str, color: str, ears: str, paws: str) -> str:
    """
    Базовая конфигурация (10 XML):
      - Порода: Британец
      - Цвет: Серый   (БЕСПЛАТНАЯ смена цвета — не влияет на цену)
      - Ушки: Острые в разные стороны
      - Лапки: В цвет

    За КАЖДОЕ отличие от базовой конфигурации (кроме цвета) +5 XML.
    """
    base_price = 10
    diffs = 0
    if breed != "Британец":
        diffs += 1
    # цвет не считаем
    if ears != "Острые в разные стороны":
        diffs += 1
    if paws != "В цвет":
        diffs += 1
    return f"{base_price + 5 * diffs} XML"

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

    # значения по умолчанию
    form_data = {
        "name": "",
        "breed": "Британец",
        "color": "Серый",
        "ears": "Острые в разные стороны",
        "paws": "В цвет",
    }
    # цена по умолчанию
    price = compute_price(form_data["breed"], form_data["color"], form_data["ears"], form_data["paws"])

    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not token or token != session.get("_csrf_token"):
            flash("Неверный CSRF-токен", "error")
            return redirect(url_for("shop"))

        name  = request.form.get("name", "").strip()
        breed = request.form.get("breed", form_data["breed"])
        color = request.form.get("color", form_data["color"])
        ears  = request.form.get("ears",  form_data["ears"])
        paws  = request.form.get("paws",  form_data["paws"])
        action = request.form.get("action", "preview")

        # пересобираем данные формы
        form_data.update({"name": name, "breed": breed, "color": color, "ears": ears, "paws": paws})

        # считаем цену на основе выбранных параметров
        price = compute_price(breed, color, ears, paws)

        # генерим URL картинки под параметры
        cat_img_url = build_cat_image_path(breed, color, ears, paws)

        if action == "add":
            cat = {
                "name": name or "Безымянный кот",
                "breed": breed,
                "color": color,
                "ears": ears,
                "paws": paws,
                "price": price,           # используем вычисленную цену
                "image": cat_img_url,
            }
            session.setdefault("orders", []).append(cat)
            session.modified = True
            flash(f"Кот '{cat['name']}' добавлен в корзину!", "success")
        # для preview — без flash

    return render_template(
        "shop.html",
        title="Генератор кота",
        cat_img_url=cat_img_url,
        form_data=form_data,
        price=price,  # передаём цену в шаблон
    )

@app.route("/account")
def account():
    orders = session.get("orders", [])
    return render_template("account.html", title="Корзина", orders=orders)

if __name__ == "__main__":
    app.run(debug=False)
