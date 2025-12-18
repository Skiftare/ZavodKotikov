# payment_service.py
import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict


class PaymentStatus(Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class OrderItem:
    cat_id: str
    name: str
    breed: str
    color: str
    ears: str
    paws: str
    container: str
    pattern: str
    price: int

    def __init__(self, cat_id: str, name: str, breed: str, color: str, ears: str, paws: str, container: str,
                 pattern: str, price: int):
        self.cat_id = cat_id
        self.name = name
        self.breed = breed
        self.color = color
        self.ears = ears
        self.paws = paws
        self.container = container
        self.pattern = pattern
        self.price = price


@dataclass
class Order:
    id: str
    session_id: str  # Добавляем привязку к сессии
    items: List[OrderItem]
    total_amount: int
    status: PaymentStatus
    email: Optional[str] = None
    memo: Optional[str] = None  # Добавляем поле для MEMO
    created_at: Optional['datetime'] = None  # Время создания заказа
    memo_created_at: Optional['datetime'] = None  # Время последней генерации MEMO


class MemoGenerator:
    """
    Безопасный генератор MEMO для платежей.
    Использует HMAC-SHA256 с временной солью для создания детерминированных, но не предсказуемых MEMO.
    Поддерживает регенерацию MEMO и хранение нескольких активных MEMO для одного заказа.
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        secret_key - секретный ключ для HMAC. Если не указан, берётся из переменной окружения.
        """
        if secret_key is None:
            secret_key = os.getenv('MEMO_SECRET_KEY')
            if not secret_key:
                # Генерируем случайный ключ, если не задан
                import secrets
                secret_key = secrets.token_hex(32)
                print(f"[Warning] MEMO_SECRET_KEY not set. Using random key: {secret_key}")
                print("[Warning] Add this to .env file for persistence!")

        self.secret_key = secret_key.encode('utf-8')
        # Хранилище для обратного маппинга MEMO -> (Order ID, timestamp)
        self._memo_to_order: Dict[str, tuple[str, datetime]] = {}
        # Хранилище активных MEMO для каждого заказа: Order ID -> [MEMO1, MEMO2, ...]
        self._order_to_memos: Dict[str, List[str]] = {}
        # Время последней генерации для rate limiting: Order ID -> timestamp
        self._last_generation: Dict[str, datetime] = {}

    def generate_memo(self, order_id: str, salt: Optional[str] = None) -> str:
        """
        Генерирует безопасный MEMO на основе Order ID и временной соли.

        Использует HMAC-SHA256 с включением timestamp для уникальности.
        Результат кодируется в base64 и усекается до 28 символов.

        Args:
            order_id: ID заказа
            salt: Дополнительная соль (если None, используется текущий timestamp)

        Returns:
            Безопасный MEMO строка длиной 28 символов
        """
        # Используем текущий timestamp как соль для уникальности
        if salt is None:
            from time import time
            salt = str(int(time()))

        # Комбинируем order_id и соль
        message = f"{order_id}:{salt}".encode('utf-8')

        # Создаём HMAC-SHA256
        hmac_obj = hmac.new(self.secret_key, message, hashlib.sha256)
        hash_bytes = hmac_obj.digest()

        # Кодируем в base64 (URL-safe вариант, без / и +)
        b64_encoded = base64.urlsafe_b64encode(hash_bytes).decode('utf-8')

        # Убираем padding символы '='
        b64_encoded = b64_encoded.rstrip('=')

        # Усекаем до 28 символов (лимит Stellar MEMO_TEXT)
        memo = b64_encoded[:28]

        # Сохраняем маппинг для обратного поиска
        from datetime import datetime
        self._memo_to_order[memo] = (order_id, datetime.now())

        # Добавляем MEMO к списку активных для этого заказа
        if order_id not in self._order_to_memos:
            self._order_to_memos[order_id] = []
        self._order_to_memos[order_id].append(memo)

        return memo

    def regenerate_memo(self, order_id: str, min_interval: int = 60) -> tuple[Optional[str], Optional[str]]:
        """
        Регенерирует MEMO для заказа с проверкой rate limiting.

        Args:
            order_id: ID заказа
            min_interval: Минимальный интервал между регенерациями (секунды)

        Returns:
            (new_memo, error_message) - новый MEMO или None с сообщением об ошибке
        """
        from datetime import datetime

        current_time = datetime.now()

        # Проверяем rate limiting
        if order_id in self._last_generation:
            time_since_last = (current_time - self._last_generation[order_id]).total_seconds()
            if time_since_last < min_interval:
                remaining = int(min_interval - time_since_last)
                return None, f"Подождите ещё {remaining} секунд перед регенерацией"

        # Генерируем новый MEMO
        new_memo = self.generate_memo(order_id)
        self._last_generation[order_id] = current_time

        return new_memo, None

    def get_order_id_by_memo(self, memo: str) -> Optional[str]:
        """
        Находит Order ID по MEMO.

        Args:
            memo: MEMO из транзакции

        Returns:
            Order ID или None, если MEMO не найден
        """
        if memo in self._memo_to_order:
            return self._memo_to_order[memo][0]
        return None

    def get_active_memos(self, order_id: str) -> List[str]:
        """
        Возвращает список всех активных MEMO для заказа.

        Args:
            order_id: ID заказа

        Returns:
            Список активных MEMO
        """
        return self._order_to_memos.get(order_id, [])

    def cleanup_expired_memos(self, timeout_seconds: int = 3600):
        """
        Удаляет устаревшие MEMO (старше timeout_seconds).

        Args:
            timeout_seconds: Таймаут в секундах (по умолчанию 1 час)
        """
        from datetime import datetime

        current_time = datetime.now()
        expired_memos = []

        for memo, (order_id, timestamp) in list(self._memo_to_order.items()):
            if (current_time - timestamp).total_seconds() > timeout_seconds:
                expired_memos.append(memo)

        # Удаляем устаревшие MEMO
        for memo in expired_memos:
            order_id, _ = self._memo_to_order[memo]
            del self._memo_to_order[memo]

            # Удаляем из списка активных MEMO заказа
            if order_id in self._order_to_memos:
                if memo in self._order_to_memos[order_id]:
                    self._order_to_memos[order_id].remove(memo)

                # Если у заказа не осталось MEMO, удаляем запись
                if not self._order_to_memos[order_id]:
                    del self._order_to_memos[order_id]

        if expired_memos:
            print(f"[MemoGenerator] Cleaned up {len(expired_memos)} expired MEMO(s)")

    def verify_memo(self, order_id: str, memo: str) -> bool:
        """
        Проверяет, является ли MEMO валидным для данного Order ID.

        Args:
            order_id: ID заказа
            memo: MEMO для проверки

        Returns:
            True если MEMO валиден для этого заказа
        """
        found_order_id = self.get_order_id_by_memo(memo)
        return found_order_id == order_id
