# payment_gateway.py
import os
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Callable

from dotenv import load_dotenv
from stellar_sdk import Server, Network
from stellar_sdk.exceptions import NotFoundError, BadRequestError

from payment_service import PaymentStatus, Order

# Загружаем переменные окружения
load_dotenv()


class PaymentGateway(ABC):
    @abstractmethod
    def process_payment(self, order: Order, payment_token: str) -> PaymentStatus:
        pass


class MockPaymentGateway(PaymentGateway):
    def process_payment(self, order: Order, payment_token: str) -> PaymentStatus:
        """
        Ну а что вы ожидали от мока?
        """
        try:
            trans_num = int(payment_token)
        except ValueError:
            return None

        if trans_num % 2 != 0:
            return None

        if trans_num < 0:
            return PaymentStatus.FAILED

        return PaymentStatus.SUCCESS


class StellarPaymentGateway(PaymentGateway):
    """
    Stellar-based payment gateway that monitors transactions in a separate thread.
    Uses memo field to match payments to orders.
    """

    def __init__(self):
        # Конфигурация из .env
        network_type = os.getenv('STELLAR_NETWORK', 'testnet').lower()
        self.destination_address = os.getenv('STELLAR_DESTINATION_ADDRESS')

        if not self.destination_address:
            raise ValueError("STELLAR_DESTINATION_ADDRESS must be set in .env file")

        # Выбор сети и Horizon URL
        if network_type == 'mainnet':
            self.network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
            horizon_url = os.getenv('STELLAR_HORIZON_URL', 'https://horizon.stellar.org')
        else:
            self.network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
            horizon_url = os.getenv('STELLAR_HORIZON_URL', 'https://horizon-testnet.stellar.org')

        self.server = Server(horizon_url)

        # Настройки проверки платежей
        self.check_interval = int(os.getenv('PAYMENT_CHECK_INTERVAL', '10'))
        self.payment_timeout = int(os.getenv('PAYMENT_TIMEOUT', '3600'))

        # Проверяем валидность аккаунта
        print(f"[Stellar] Gateway initialized on {network_type}")
        print(f"[Stellar] Monitoring address: {self.destination_address}")
        self._check_account_status()

        # Хранилище ожидающих платежей: {memo: (order, callback, timestamp)}
        self._pending_payments: Dict[str, tuple[Order, Optional[Callable], datetime]] = {}
        self._lock = threading.Lock()

        # Запускаем фоновый поток для мониторинга
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_payments, daemon=True)
        self._monitor_thread.start()

    def _check_account_status(self):
        """
        Проверяет валидность аккаунта и выводит информацию о балансе.
        """
        try:
            print(f"[Stellar] Checking account status...")
            account = self.server.accounts().account_id(self.destination_address).call()

            print(f"[Stellar] ✅ Account is ACTIVE")
            print(f"[Stellar] Account ID: {account['id']}")
            print(f"[Stellar] Sequence: {account['sequence']}")

            # Выводим балансы всех активов
            balances = account.get('balances', [])
            print(f"[Stellar] Balances:")
            for balance in balances:
                asset_type = balance.get('asset_type', 'unknown')
                if asset_type == 'native':
                    asset_name = 'XLM (native)'
                    amount = float(balance.get('balance', '0'))
                    print(f"[Stellar]   💰 {asset_name}: {amount:.7f} XLM")
                else:
                    asset_code = balance.get('asset_code', 'Unknown')
                    asset_issuer = balance.get('asset_issuer', 'Unknown')
                    amount = float(balance.get('balance', '0'))
                    print(f"[Stellar]   💰 {asset_code}: {amount:.7f} (Issuer: {asset_issuer[:8]}...)")

            # Проверяем, есть ли минимальный баланс для работы
            native_balance = next((float(b['balance']) for b in balances if b['asset_type'] == 'native'), 0)
            min_balance = 1.0  # Минимальный рекомендуемый баланс

            if native_balance < min_balance:
                print(f"[Stellar] ⚠️  WARNING: Low balance! Recommended minimum: {min_balance} XLM")
                print(f"[Stellar] ⚠️  Current balance: {native_balance:.7f} XLM")

            # Дополнительная информация
            subentry_count = int(account.get('subentry_count', 0))
            base_reserve = 0.5  # Base reserve per entry (может меняться)
            min_reserve = (2 + subentry_count) * base_reserve
            print(f"[Stellar] Subentries: {subentry_count}")
            print(f"[Stellar] Minimum reserve: {min_reserve} XLM")

            available_balance = native_balance - min_reserve
            if available_balance > 0:
                print(f"[Stellar] Available balance: {available_balance:.7f} XLM")
            else:
                print(f"[Stellar] ⚠️  WARNING: Account balance is at or below minimum reserve!")

        except NotFoundError:
            print(f"[Stellar] ⚠️  WARNING: Account NOT FOUND on the network")
            print(f"[Stellar] ⚠️  The account needs to be activated with a minimum deposit")
            print(f"[Stellar] ℹ️  Testnet: Use Friendbot to fund the account:")
            print(f"[Stellar] ℹ️  https://friendbot.stellar.org?addr={self.destination_address}")
            print(f"[Stellar] ℹ️  Mainnet: Send at least 1 XLM to activate the account")
            print(f"[Stellar] ⚠️  Payment monitoring will start, but account cannot receive payments yet")
        except BadRequestError as e:
            print(f"[Stellar] ❌ ERROR: Invalid account address")
            print(f"[Stellar] ❌ Details: {e}")
            raise ValueError(f"Invalid STELLAR_DESTINATION_ADDRESS: {self.destination_address}")
        except Exception as e:
            print(f"[Stellar] ⚠️  WARNING: Could not check account status")
            print(f"[Stellar] ⚠️  Error: {e}")
            print(f"[Stellar] ℹ️  Continuing with monitoring...")

    def process_payment(self, order: Order, payment_token: str) -> PaymentStatus:
        """
        Регистрирует заказ для мониторинга.
        payment_token в данном случае - это ID заказа, который должен быть в мемо транзакции.
        Возвращает PENDING - платёж будет обработан асинхронно.
        """
        with self._lock:
            # Используем безопасный MEMO вместо order.id
            memo = order.memo
            if not memo:
                raise ValueError("Order MEMO not generated")

            self._pending_payments[memo] = (order, None, datetime.now())
            print(f"[Stellar] Payment registered for order {order.id}")
            print(f"[Stellar] Expected amount: {order.total_amount:.2f} XLM")
            print(f"[Stellar] Memo text should be: {memo}")
            print(f"[Stellar] MEMO is hashed and secure (not correlated with Order ID)")

        return PaymentStatus.PENDING

    def register_payment_callback(self, order_id: str, callback: Callable[[Order, PaymentStatus], None]):
        """
        Регистрирует callback-функцию, которая будет вызвана при изменении статуса платежа.
        """
        with self._lock:
            # Ищем по всем pending платежам
            for memo, (order, _, timestamp) in self._pending_payments.items():
                if order.id == order_id:
                    self._pending_payments[memo] = (order, callback, timestamp)
                    break

    def _monitor_payments(self):
        """
        Фоновый поток, который периодически проверяет транзакции.
        Использует payments() для мониторинга платежей с MEMO.
        """
        print(f"[Stellar] Payment monitor thread started")
        last_cursor = 'now'  # Начинаем с текущего момента

        while self._running:
            try:
                with self._lock:
                    if not self._pending_payments:
                        time.sleep(self.check_interval)
                        continue

                    # Копируем список для проверки
                    pending_orders = list(self._pending_payments.items())

                # Получаем платежи для аккаунта (payments включают информацию о транзакциях)
                try:
                    payments_response = self.server.payments().for_account(
                        account_id=self.destination_address
                    ).cursor(last_cursor).limit(200).order(desc=False).call()

                    records = payments_response.get('_embedded', {}).get('records', [])

                    for payment in records:
                        # Обновляем курсор
                        last_cursor = payment['paging_token']

                        # Проверяем только payment операции
                        if payment['type'] not in ['payment', 'create_account']:
                            continue

                        # Проверяем только входящие платежи
                        if payment.get('to') != self.destination_address:
                            continue

                        # Проверяем актив (только нативный XLM)
                        if payment.get('asset_type') != 'native':
                            continue

                        # Получаем мемо из транзакции
                        transaction_hash = payment.get('transaction_hash')
                        if not transaction_hash:
                            continue

                        try:
                            transaction = self.server.transactions().transaction(transaction_hash).call()
                            memo = transaction.get('memo', '')

                            if not memo:
                                continue

                            # Проверяем, есть ли заказ с таким мемо
                            with self._lock:
                                if memo not in self._pending_payments:
                                    continue

                                order, callback, _ = self._pending_payments[memo]

                                # Получаем сумму платежа в XLM
                                amount_xlm = float(payment['amount'])

                                # Проверяем сумму
                                if amount_xlm >= order.total_amount:
                                    print(
                                        f"[Stellar] Payment confirmed for order {order.id}: {amount_xlm:.2f} XLM")
                                    print(f"[Stellar] Transaction hash: {transaction_hash}")
                                    print(f"[Stellar] From: {payment.get('from', 'N/A')}")
                                    order.status = PaymentStatus.SUCCESS

                                    # Вызываем callback если есть
                                    if callback:
                                        try:
                                            callback(order, PaymentStatus.SUCCESS)
                                        except Exception as e:
                                            print(f"[Stellar] Callback error: {e}")

                                    # Удаляем из ожидающих
                                    del self._pending_payments[memo]
                                else:
                                    print(
                                        f"[Stellar] Insufficient payment for order {order.id}: {amount_xlm:.2f} XLM < {order.total_amount:.2f} XLM")
                        except Exception as e:
                            print(f"[Stellar] Error fetching transaction {transaction_hash}: {e}")
                            continue

                except NotFoundError:
                    # Аккаунт может ещё не существовать или не иметь операций
                    # Это нормально, просто ждём
                    pass
                except BadRequestError as e:
                    print(f"[Stellar] Bad request error: {e}")

                # Проверяем таймауты
                current_time = datetime.now()
                with self._lock:
                    expired_orders = []
                    for memo_key, (order, callback, timestamp) in list(self._pending_payments.items()):
                        if (current_time - timestamp).total_seconds() > self.payment_timeout:
                            print(f"[Stellar] Payment timeout for order {order.id}")
                            order.status = PaymentStatus.FAILED

                            if callback:
                                try:
                                    callback(order, PaymentStatus.FAILED)
                                except Exception as e:
                                    print(f"[Stellar] Callback error: {e}")

                            expired_orders.append(memo_key)

                    for memo_key in expired_orders:
                        del self._pending_payments[memo_key]

            except Exception as e:
                print(f"[Stellar] Monitor error: {e}")

            time.sleep(self.check_interval)

    def get_payment_status(self, order_id: str) -> Optional[PaymentStatus]:
        """
        Получает текущий статус платежа.
        """
        with self._lock:
            for memo, (order, _, _) in self._pending_payments.items():
                if order.id == order_id:
                    return order.status
        return None

    def get_account_info(self) -> Optional[Dict]:
        """
        Получает актуальную информацию об аккаунте.
        Возвращает словарь с информацией или None, если аккаунт не найден.
        """
        try:
            account = self.server.accounts().account_id(self.destination_address).call()

            # Собираем информацию о балансах
            balances = []
            for balance in account.get('balances', []):
                asset_type = balance.get('asset_type', 'unknown')
                if asset_type == 'native':
                    balances.append({
                        'asset': 'XLM',
                        'balance': float(balance.get('balance', '0')),
                        'is_native': True
                    })
                else:
                    balances.append({
                        'asset': balance.get('asset_code', 'Unknown'),
                        'balance': float(balance.get('balance', '0')),
                        'issuer': balance.get('asset_issuer', 'Unknown'),
                        'is_native': False
                    })

            return {
                'id': account['id'],
                'sequence': account['sequence'],
                'balances': balances,
                'subentry_count': int(account.get('subentry_count', 0)),
                'exists': True
            }
        except NotFoundError:
            return {'exists': False, 'id': self.destination_address}
        except Exception as e:
            print(f"[Stellar] Error getting account info: {e}")
            return None

    def stop(self):
        """
        Останавливает фоновый поток мониторинга.
        """
        self._running = False
        if self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        print("[Stellar] Gateway stopped")
