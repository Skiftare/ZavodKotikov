# Завод Котиков - Stellar Payment Integration

## 📦 Установка зависимостей

Перед запуском приложения установите необходимые библиотеки:

```bash
pip install py-stellar-base python-dotenv Flask Pillow
```

Или используйте requirements.txt:

```bash
pip install -r requirements.txt
```

## 🚀 Запуск приложения

### Правильный способ запуска:

```bash
python run.py
```

или как модуль:

```bash
python -m src.app
```

**НЕ запускайте напрямую** `python src/app.py` - это вызовет ошибки импорта!

## ⚙️ Настройка

### 1. Файл .env

Скопируйте `.env.example` в `.env` и настройте параметры:

```env
# Включить Stellar Payment Gateway (true/false)
USE_STELLAR_PAYMENT=false

# Выберите сеть: testnet или mainnet
STELLAR_NETWORK=testnet

# Ваш публичный адрес Stellar для получения платежей
STELLAR_DESTINATION_ADDRESS=GВАШ_АДРЕС_ЗДЕСЬ

# URL Horizon сервера
STELLAR_HORIZON_URL=https://horizon-testnet.stellar.org

# Интервал проверки платежей (секунды)
PAYMENT_CHECK_INTERVAL=10

# Таймаут ожидания платежа (секунды)
PAYMENT_TIMEOUT=3600

# Секретный ключ для безопасной генерации MEMO
# Сгенерируйте командой: python -c "import secrets; print(secrets.token_hex(32))"
MEMO_SECRET_KEY=ваш_сгенерированный_ключ
```

**ВАЖНО**: Сгенерируйте уникальный `MEMO_SECRET_KEY` и никогда не меняйте его после деплоя!

### 1.5. Генерация секретного ключа для MEMO

Выполните команду:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Скопируйте вывод в `.env` как значение `MEMO_SECRET_KEY`.

### 2. Создание Stellar аккаунта (для TestNet)

1. Перейдите на https://laboratory.stellar.org/#account-creator
2. Нажмите "Generate keypair"
3. Сохраните **Public Key** (G...) - это адрес для получения платежей
4. Сохраните **Secret Key** (S...) - храните в секрете!
5. Нажмите "Fund with friendbot" для получения тестовых XLM

### 3. Запуск приложения

```bash
python app.py
```

Приложение будет доступно по адресу: http://localhost:7080

## 🛒 Новая функциональность корзины

### Выбор котов
- ✅ Чекбоксы для выбора нескольких котов
- ✅ Кнопки "Выбрать всё" / "Снять выбор"
- ✅ Динамический подсчёт суммы выбранных котов
- ✅ Визуальное выделение выбранных котов

### Операции с выбранными котами
- 🗑️ **Удалить выбранное** - удаляет выбранных котов из корзины
- 💳 **Оплатить выбранное** - создаёт заказ только из выбранных котов
- ✨ После успешной оплаты только оплаченные коты удаляются из корзины

## 💰 Stellar Payment Gateway

### Принцип работы

1. **Создание заказа**: Выбираете котов и нажимаете "Оплатить выбранное"
2. **Страница оплаты**: Получаете:
   - Адрес кошелька для оплаты
   - **MEMO** (Order ID) - обязательное поле!
   - Сумму в XLM
   - Инструкции по оплате
3. **Отправка платежа**: Отправляете XLM с указанием MEMO
4. **Автоматическая проверка**: Фоновый поток каждые 10 секунд проверяет транзакции
5. **Подтверждение**: При совпадении MEMO и суммы заказ автоматически подтверждается

### Важно!

⚠️ **MEMO обязателен!** Без правильного MEMO транзакция не будет связана с заказом.

Формат MEMO: UUID заказа (например: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)

### Как отправить тестовый платёж

#### Через Stellar Laboratory

1. Откройте https://laboratory.stellar.org/#txbuilder
2. Выберите сеть "Test"
3. Заполните форму:
   - **Source Account**: ваш адрес отправителя
   - **Sequence Number**: нажмите "Fetch next sequence"
4. Добавьте операцию **Payment**:
   - **Destination**: адрес из страницы оплаты
   - **Asset**: XLM (native)
   - **Amount**: сумма из страницы оплаты
5. **ВАЖНО!** Добавьте **Memo**:
   - **Memo Type**: MEMO_TEXT
   - **Memo Content**: Order ID со страницы оплаты
6. Подпишите транзакцию вашим Secret Key
7. Отправьте транзакцию

## 🔄 Переключение между Mock и Stellar

### Mock режим (для разработки)
```env
USE_STELLAR_PAYMENT=false
```
- Используется фейковый XMLCoin
- Оплата по чётному номеру транзакции

### Stellar режим (реальные платежи)
```env
USE_STELLAR_PAYMENT=true
```
- Используется Stellar blockchain
- Оплата через XLM
- Автоматическая проверка транзакций

## 📊 Конвертация цены

Цены в системе хранятся в **stroops** (1 XLM = 10,000,000 stroops):

- `order.total_amount = 100000000` = 10 XLM
- `order.total_amount = 15000000` = 1.5 XLM
- `order.total_amount = 5000000` = 0.5 XLM

## 🎯 Архитектура

```
┌─────────────────┐
│  Flask App      │
│  (app.py)       │
└────────┬────────┘
         │
         ├─── OrderService (order_service.py)
         │         │
         │         └─── PaymentGateway (payment_gateway.py)
         │                   │
         │                   ├─── MockPaymentGateway
         │                   │     (синхронный, для тестов)
         │                   │
         │                   └─── StellarPaymentGateway
         │                         (асинхронный, с фоновым потоком)
         │                         │
         │                         └─── Stellar Horizon API
         │
         └─── Templates
                ├─── account.html (корзина с выбором)
                ├─── payment.html (страница оплаты с MEMO)
                └─── ...
```

## 🧵 Фоновый поток мониторинга

При использовании Stellar запускается daemon-поток, который:
- Проверяет новые транзакции каждые N секунд
- Сопоставляет MEMO с ID заказов
- Проверяет суммы платежей
- Автоматически обновляет статусы заказов
- Обрабатывает таймауты

Поток работает независимо от основного приложения и не блокирует его работу.

## 🔒 Безопасность

### Безопасная генерация MEMO

Система использует **HMAC-SHA256** для генерации безопасных MEMO:

- ✅ **MEMO ≠ Order ID**: Невозможно восстановить Order ID из MEMO без секретного ключа
- ✅ **Детерминированность**: Один Order ID всегда даёт один и тот же MEMO
- ✅ **Отсутствие коллизий**: Уникальность гарантирована SHA256
- ✅ **Защита от подбора**: Без `MEMO_SECRET_KEY` нельзя сгенерировать валидный MEMO

**Формула**: `MEMO = HMAC-SHA256(order_id, secret_key)[:28]`

**Подробнее**: См. документ **MEMO_SECURITY.md**

### Общая безопасность

- ✅ CSRF защита на всех формах
- ✅ Проверка сессий пользователей
- ✅ Secret Key никогда не хранится в коде
- ✅ Валидация сумм и MEMO перед подтверждением
- ✅ Изоляция заказов по session_id
- ✅ Timing-attack защита через `hmac.compare_digest()`

## 🐛 Отладка

### Логи консоли

При запуске приложения вы увидите:
```
[App] Using Stellar Payment Gateway
[Stellar] Gateway initialized on testnet
[Stellar] Monitoring address: GВАШ_АДРЕС
[Stellar] Payment monitor thread started
```

При регистрации платежа:
```
[Stellar] Payment registered for order abc-123
[Stellar] Expected amount: 1.5000000 XLM
[Stellar] Memo text should be: abc-123
```

При подтверждении:
```
[Stellar] Payment confirmed for order abc-123: 1.5000000 XLM
```

### Проверка транзакций

1. Откройте https://stellar.expert/explorer/testnet
2. Введите ваш адрес
3. Проверьте последние транзакции и их MEMO

## 📝 Подробная документация

Полное руководство по Stellar Payment Gateway: **STELLAR_PAYMENT_GUIDE.md**

## 🚀 Production checklist

Перед переходом на MainNet:

- [ ] Установите `STELLAR_NETWORK=mainnet`
- [ ] Используйте реальный Stellar адрес
- [ ] Настройте HTTPS
- [ ] Измените `app.secret_key` на постоянный
- [ ] Включите production режим Flask
- [ ] Настройте логирование в файлы
- [ ] Протестируйте на testnet

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи в консоли
2. Убедитесь, что все библиотеки установлены
3. Проверьте настройки в `.env`
4. Убедитесь, что Stellar аккаунт активирован
5. Проверьте транзакции на stellar.expert
