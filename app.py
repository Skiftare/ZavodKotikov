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


@app.route("/")
def index():
    return render_template("index.html", title="Главная")


@app.route("/about")
def about():
    return render_template("about.html", title="О нас")


# Генератор котов (страница "Магазин")
@app.route("/shop", methods=["GET", "POST"])
def shop():
    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not token or token != session.get("_csrf_token"):
            flash("Неверный CSRF-токен", "error")
            return redirect(url_for("shop"))

        name = request.form.get("name")
        color = request.form.get("color")
        price = request.form.get("price", "10 XML")

        cat = {
            "name": name,
            "color": color,
            "price": price
        }

        if "orders" not in session:
            session["orders"] = []
        session["orders"].append(cat)
        session.modified = True

        flash(f"Кот {name} создан и добавлен в историю заказов!", "success")
        return redirect(url_for("account"))

    return render_template("shop.html", title="Генератор кота")


@app.route("/account")
def account():
    orders = session.get("orders", [])
    return render_template("account.html", title="Мой аккаунт", orders=orders)


if __name__ == "__main__":
    app.run(debug=False)
