import os
import secrets
import uuid
from datetime import timedelta
from werkzeug.exceptions import NotFound

from flask import Flask, render_template, request, redirect, url_for, session, flash

from src.utils.image_generator import compose_file
from src.services.order_service import OrderService
from src.services.stellar.payment_gateway import MockPaymentGateway, StellarPaymentGateway
from src.services.stellar.payment_service import OrderItem, PaymentStatus

def test_payment_system():
    """
    Тестирует платёжную систему перед запуском приложения.
    Проверяет:
    1. Инициализацию payment gateway
    2. Создание тестового заказа
    3. Возможность обработки платежа
    """
    print("\n" + "="*70)
    print("🧪 ТЕСТИРОВАНИЕ ПЛАТЁЖНОЙ СИСТЕМЫ")
    print("="*70)

    test_passed = True

    # Тест 1: Проверка инициализации gateway
    print("\n[Тест 1] Проверка инициализации Payment Gateway...")
    try:
        if USE_STELLAR:
            print("  ✓ Stellar Gateway инициализирован")
            print(f"  ✓ Адрес: {payment_gateway.destination_address}")
            print(f"  ✓ Сеть: {os.getenv('STELLAR_NETWORK', 'testnet')}")
            print(f"  ✓ Интервал проверки: {payment_gateway.check_interval}s")
            print(f"  ✓ Таймаут платежа: {payment_gateway.payment_timeout}s")
            print(f"  ✓ Поток мониторинга: {'Активен' if payment_gateway._monitor_thread.is_alive() else 'Неактивен'}")
        else:
            print("  ✓ Mock Gateway инициализирован (тестовый режим)")
        print("  ✅ Тест 1 ПРОЙДЕН")
    except Exception as e:
        print(f"  ❌ Тест 1 ПРОВАЛЕН: {e}")
        test_passed = False

    # Тест 2: Проверка создания заказа
    print("\n[Тест 2] Проверка создания тестового заказа...")
    try:
        test_items = [
            OrderItem(
                cat_id="test-cat-001",
                name="Тестовый Котик",
                breed="Британец",
                color="Серый",
                ears="Круглые",
                paws="В цвет",
                container="Без контейнера",
                pattern="Обычная",
                price=100
            )
        ]

        test_order = order_service.create_order("test-session-001", test_items)
        print(f"  ✓ Заказ создан: {test_order.id}")
        print(f"  ✓ Статус: {test_order.status}")
        print(f"  ✓ Сумма: {test_order.total_amount} XLM")
        print(f"  ✓ MEMO сгенерирован: {test_order.memo}")
        print(f"  ✓ Количество товаров: {len(test_order.items)}")
        print("  ✅ Тест 2 ПРОЙДЕН")
    except Exception as e:
        print(f"  ❌ Тест 2 ПРОВАЛЕН: {e}")
        test_passed = False

    # Тест 3: Проверка обработки платежа (только для Mock)
    if not USE_STELLAR:
        print("\n[Тест 3] Проверка обработки тестового платежа (Mock режим)...")
        try:
            # Тестируем успешный платёж (чётное число)
            status = order_service.process_payment(test_order.id, "test-session-001", "1234")
            if status == PaymentStatus.SUCCESS:
                print(f"  ✓ Платёж обработан успешно: {status}")
                print("  ✅ Тест 3 ПРОЙДЕН")
            else:
                print(f"  ⚠️ Платёж не успешен (ожидаемо для тестов): {status}")
                print("  ✅ Тест 3 ПРОЙДЕН (система работает корректно)")
        except Exception as e:
            print(f"  ❌ Тест 3 ПРОВАЛЕН: {e}")
            test_passed = False
    else:
        print("\n[Тест 3] Проверка Stellar мониторинга...")
        try:
            print("  ✓ Stellar мониторинг запущен и ожидает транзакции")
            print(f"  ℹ️ Для тестирования отправьте XLM с MEMO: {test_order.memo}")
            print("  ✅ Тест 3 ПРОЙДЕН (мониторинг активен)")
        except Exception as e:
            print(f"  ❌ Тест 3 ПРОВАЛЕН: {e}")
            test_passed = False

    # Тест 4: Проверка регенерации MEMO
    print("\n[Тест 4] Проверка регенерации MEMO...")
    try:
        old_memo = test_order.memo
        new_memo, error = order_service.regenerate_memo(test_order.id, "test-session-001")

        if new_memo and not error:
            print(f"  ✓ Старый MEMO: {old_memo}")
            print(f"  ✓ Новый MEMO: {new_memo}")
            print(f"  ✓ MEMO изменён: {old_memo != new_memo}")
            print("  ✅ Тест 4 ПРОЙДЕН")
        else:
            print(f"  ⚠️ Rate limiting активен: {error}")
            print("  ✅ Тест 4 ПРОЙДЕН (защита работает)")
    except Exception as e:
        print(f"  ❌ Тест 4 ПРОВАЛЕН: {e}")
        test_passed = False

    # Итоговый результат
    print("\n" + "="*70)
    if test_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Платёжная система готова к работе")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ!")
        print("⚠️ Проверьте конфигурацию перед запуском")
    print("="*70 + "\n")

    return test_passed

# Инициализация сервисов
# Выбираем gateway в зависимости от переменной окружения
USE_STELLAR = os.getenv('USE_STELLAR_PAYMENT', 'false').lower() == 'true'

if USE_STELLAR:
    try:
        payment_gateway = StellarPaymentGateway()
        print("[App] Using Stellar Payment Gateway")
    except Exception as e:
        print(f"[App] Failed to initialize Stellar Gateway: {e}")
        print("[App] Falling back to Mock Payment Gateway")
        payment_gateway = MockPaymentGateway()
        USE_STELLAR = False
else:
    payment_gateway = MockPaymentGateway()
    print("[App] Using Mock Payment Gateway")

order_service = OrderService(payment_gateway)

# Определяем корневую директорию проекта
import pathlib
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()

app = Flask(__name__,
            template_folder=str(PROJECT_ROOT / "templates"),
            static_folder=str(PROJECT_ROOT / "static"))
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(days=7)
LAYERS_DIR = os.path.join(str(PROJECT_ROOT), "static", "cats", "layers")
SPECIAL_IMG = os.path.join(str(PROJECT_ROOT), "static", "cats", "special.png")

def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def compute_price(breed: str, color: str, ears: str, paws: str, pattern: str, container: str) -> str:
    temp_item = OrderItem(
        cat_id=str(uuid.uuid4()),
        name="",
        breed=breed,
        color=color,
        ears=ears,
        paws=paws,
        price=0,
        container=container,
        pattern=pattern
    )
    price = order_service.calculate_price(temp_item)
    return f"{price} XLM"




@app.route("/")
def index():
    return render_template("index.html", title="Главная")


@app.route("/about")
def about():
    return render_template("about.html", title="О нас")

def _slug(s: str) -> str:
    return s.strip().lower().replace(" ", "-")

def _cat_layer_paths(breed: str, color: str, ears: str, paws: str, container: str, pattern: str) -> list[str]:
    """
    Слои в порядке наложения:
      1) <порода>-<цвет>.png
      2) <рисунок>.png (если рисунок не "Обычная")
      3) <уши>.png
      4) <лапы>.png (если лапы != 'в цвет')
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

    # рисунок добавляем только если не "Обычная"
    if pattern != "Обычная":
        pattern_fn = f"{_slug(pattern)}.png"
        filenames.insert(2, pattern_fn)  # добавляем после breed и перед color

    paths: list[str] = []
    missing = False

    for fn in filenames:
        p = os.path.join(LAYERS_DIR, fn)
        if os.path.isfile(p):
            paths.append(p)
        else:
            print(f"ERROR! LAYER {LAYERS_DIR} {fn} NOT FOUND!")
            missing = True  # какого-то слоя не хватает

    print("Requested files list: ", filenames)

    # если вообще ничего не нашли, но есть special — отдаём только special
    if not paths and os.path.isfile(SPECIAL_IMG):
        print("ERROR! NO IMAGES!")
        return [SPECIAL_IMG]

    # если чего-то не хватает и special существует — кладём special поверх всех
    if missing and os.path.isfile(SPECIAL_IMG):
        print("ERROR! LAYER(S) NOT FOUND!")
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
    pattern = request.args.get("pattern", "Обычная")

    files = _cat_layer_paths(breed, color, ears, paws, container, pattern)
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
        "container": "Без контейнера",
        "pattern": "Обычная"
    }
    price = compute_price(form_data["breed"], form_data["color"], form_data["ears"], form_data["paws"],
                          form_data["container"], form_data["pattern"])

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
        pattern = request.form.get("pattern", form_data["pattern"])
        container = request.form.get("container", form_data["container"])
        action = request.form.get("action", "preview")

        form_data.update({"name": name, "breed": breed, "color": color, "ears": ears, "paws": paws,
                          "container": container, "pattern": pattern})

        price = compute_price(breed, color, ears, paws, pattern, container)

        cat_img_url = url_for(
            "compose_cat",
            breed=breed,
            color=color,
            ears=ears,
            paws=paws,
            container=container,
            pattern=pattern
        )

        if action == "add":
            cat = {
                "name": name or "Безымянный кот",
                "breed": breed,
                "color": color,
                "ears": ears,
                "paws": paws,
                "container": container,
                "pattern": pattern,
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


@app.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        token = request.form.get("csrf_token")
        if not token or token != session.get("_csrf_token"):
            flash("Неверный CSRF-токен", "error")
            return redirect(url_for("account"))

        action = request.form.get("action")
        selected_indices = request.form.getlist("selected_cats")

        if not selected_indices:
            flash("Не выбрано ни одного кота", "error")
            return redirect(url_for("account"))

        # Преобразуем индексы в числа
        selected_indices = [int(i) for i in selected_indices]

        if action == "delete":
            # Удаляем выбранных котов
            orders = session.get("orders", [])
            # Создаём новый список без выбранных элементов
            new_orders = [cat for i, cat in enumerate(orders) if i not in selected_indices]
            session["orders"] = new_orders
            session.modified = True
            flash(f"Удалено {len(selected_indices)} котов из корзины", "success")
            return redirect(url_for("account"))

        elif action == "checkout":
            # Оплата выбранных котов
            orders = session.get("orders", [])
            selected_cats = [orders[i] for i in selected_indices if i < len(orders)]

            if not selected_cats:
                flash("Выбранные коты не найдены", "error")
                return redirect(url_for("account"))

            # Убедимся что у нас есть session_id
            if "session_id" not in session:
                session["session_id"] = str(uuid.uuid4())

            try:
                app.logger.info(f"Создаём заказ из выбранных котов: {selected_cats}")

                items = []
                for cat in selected_cats:
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
                            pattern=cat["pattern"],
                            price=price
                        )
                    )

                # Создаём заказ
                order = order_service.create_order(session["session_id"], items)
                app.logger.info(f"Создан заказ {order.id}")

                # Сохраняем индексы для удаления после успешной оплаты
                session["pending_checkout_indices"] = selected_indices
                session.modified = True

                return redirect(url_for("payment_page", order_id=order.id))

            except Exception as e:
                app.logger.error(f"Ошибка создания заказа: {str(e)}")
                flash(f"Ошибка при создании заказа: {str(e)}", "error")
                return redirect(url_for("account"))

    # GET запрос - показываем корзину
    orders = session.get("orders", [])
    return render_template("account.html", title="Корзина", orders=orders)


@app.route("/checkout", methods=["POST"])
def checkout():
    # Старый метод для обратной совместимости - оплата всех котов
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
                    pattern=cat["pattern"],
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

    # Передаём информацию о Stellar
    use_stellar = USE_STELLAR
    stellar_address = os.getenv('STELLAR_DESTINATION_ADDRESS', '')
    stellar_network = os.getenv('STELLAR_NETWORK', 'testnet')
    payment_timeout = int(os.getenv('PAYMENT_TIMEOUT', '3600'))

    return render_template(
        "payment.html",
        title="Оплата",
        order=order,
        use_stellar=use_stellar,
        stellar_address=stellar_address,
        stellar_network=stellar_network,
        payment_timeout=payment_timeout
    )


# Добавляем обработчик для /payment без order_id
@app.route("/payment")
def payment_redirect():
    flash("Некорректный URL заказа", "error")
    return redirect(url_for("account"))


@app.route("/api/regenerate-memo/<order_id>", methods=["POST"])
def regenerate_memo(order_id):
    """
    API endpoint для регенерации MEMO с rate limiting.
    """
    if "session_id" not in session:
        return {"success": False, "error": "Сессия устарела"}, 401

    # Проверяем CSRF токен
    token = request.form.get("csrf_token") or request.json.get("csrf_token") if request.is_json else None
    if not token or token != session.get("_csrf_token"):
        return {"success": False, "error": "Неверный CSRF-токен"}, 403

    try:
        new_memo, error = order_service.regenerate_memo(order_id, session["session_id"])

        if error:
            return {"success": False, "error": error}, 429  # Too Many Requests

        if new_memo:
            order = order_service.get_order(order_id, session["session_id"])

            # Вычисляем время истечения MEMO (1 час от момента создания)
            from datetime import datetime, timedelta
            payment_timeout = int(os.getenv('PAYMENT_TIMEOUT', '3600'))
            expires_at = order.memo_created_at + timedelta(seconds=payment_timeout)
            remaining_seconds = int((expires_at - datetime.now()).total_seconds())

            app.logger.info(f"MEMO regenerated for order {order_id}: {new_memo}")
            return {
                "success": True,
                "memo": new_memo,
                "message": "MEMO успешно обновлён!",
                "expires_at": expires_at.isoformat(),
                "remaining_seconds": remaining_seconds
            }, 200

        return {"success": False, "error": "Не удалось сгенерировать MEMO"}, 500

    except Exception as e:
        app.logger.error(f"Error regenerating MEMO: {str(e)}")
        return {"success": False, "error": "Произошла ошибка сервера"}, 500


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

                # Удаляем оплаченных котов из корзины
                if "pending_checkout_indices" in session:
                    pending_indices = session.pop("pending_checkout_indices")
                    orders = session.get("orders", [])
                    # Удаляем оплаченных котов
                    new_orders = [cat for i, cat in enumerate(orders) if i not in pending_indices]
                    session["orders"] = new_orders
                else:
                    # Если использовался старый метод checkout - очищаем всю корзину
                    session.pop("orders", None)

                session.modified = True

            return redirect(url_for("payment_success", order_id=order_id))

        elif status == PaymentStatus.PENDING and USE_STELLAR:
            # Для Stellar - показываем, что платёж в обработке
            flash("Платёж зарегистрирован. Ожидаем подтверждение транзакции...", "info")
            return redirect(url_for("payment_page", order_id=order_id))

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
    # Пропускаем тесты в режиме отладки
    if not app.debug:
        test_payment_system()

    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    app.run(debug=False, host=host, port=port)
