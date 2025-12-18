# order_service.py
import uuid
from datetime import datetime
from typing import List, Optional

from src.services.stellar.payment_gateway import PaymentGateway
from src.services.stellar.payment_service import Order, OrderItem, PaymentStatus, MemoGenerator


class OrderService:
    def __init__(self, payment_gateway: PaymentGateway):
        self._orders = {}
        self._payment_gateway = payment_gateway
        self._memo_generator = MemoGenerator()

    def create_order(self, session_id: str, items: List[OrderItem]) -> Order:
        order_id = str(uuid.uuid4())
        total = sum(self._recalculate_item_price(item) for item in items)

        # Генерируем безопасный MEMO
        memo = self._memo_generator.generate_memo(order_id)

        current_time = datetime.now()

        order = Order(
            id=order_id,
            session_id=session_id,
            items=items,
            total_amount=total,
            status=PaymentStatus.PENDING,
            memo=memo,
            created_at=current_time,
            memo_created_at=current_time
        )
        self._orders[order_id] = order
        return order

    def _recalculate_item_price(self, item: OrderItem) -> int:
        """Какая-то логика ценообразования. Возвращает цену в XLM."""
        base_price = 10
        diffs = 0
        if item.breed.lower() != "британец":
            diffs += 1
        if item.color.lower() != "серый":
            diffs += 1
        if item.ears.lower() != "острые в разные стороны":
            diffs += 1
        if item.paws.lower() != "в цвет":
            diffs += 1
        if item.container.lower() != "без контейнера":
            diffs += 1
        if item.pattern.lower() != "обычная":
            diffs += 1

        return base_price + 5 * diffs

    def calculate_price(self, item: OrderItem) -> int:
        return self._recalculate_item_price(item)

    def get_order(self, order_id: str, session_id: str) -> Optional[Order]:
        order = self._orders.get(order_id)
        if not order or order.session_id != session_id:
            return None
        return order

    def process_payment(self, order_id: str, session_id: str, payment_token: str) -> PaymentStatus:
        """
        - PaymentStatus.SUCCESS
        - PaymentStatus.FAILED
        - None
        """
        order = self.get_order(order_id, session_id)
        if not order:
            raise ValueError("Order not found or access denied")

        if order.status == PaymentStatus.SUCCESS:
            raise ValueError("Order already paid")

        status = self._payment_gateway.process_payment(order, payment_token)

        if status is None:
            return None

        order.status = status
        return status

    def get_order_by_memo(self, memo: str) -> Optional[Order]:
        """
        Находит заказ по MEMO.
        """
        order_id = self._memo_generator.get_order_id_by_memo(memo)
        if order_id:
            return self._orders.get(order_id)
        return None

    def regenerate_memo(self, order_id: str, session_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Регенерирует MEMO для заказа с проверкой прав доступа.

        Args:
            order_id: ID заказа
            session_id: ID сессии пользователя

        Returns:
            (new_memo, error_message) - новый MEMO или None с сообщением об ошибке
        """
        # Проверяем права доступа
        order = self.get_order(order_id, session_id)
        if not order:
            return None, "Заказ не найден или доступ запрещён"

        # Проверяем, что заказ ещё не оплачен
        if order.status == PaymentStatus.SUCCESS:
            return None, "Заказ уже оплачен"

        # Генерируем новый MEMO
        new_memo, error = self._memo_generator.regenerate_memo(order_id, min_interval=60)

        if new_memo:
            # Обновляем MEMO в заказе (сохраняем последний сгенерированный)
            order.memo = new_memo
            order.memo_created_at = datetime.now()
            print(f"[OrderService] Regenerated MEMO for order {order_id}: {new_memo}")

        return new_memo, error

    def get_all_active_memos(self, order_id: str) -> List[str]:
        """
        Возвращает все активные MEMO для заказа.
        """
        return self._memo_generator.get_active_memos(order_id)
