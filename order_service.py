# order_service.py
import uuid
from typing import List, Optional

from payment_gateway import PaymentGateway
from payment_service import Order, OrderItem, PaymentStatus


class OrderService:
    def __init__(self, payment_gateway: PaymentGateway):
        self._orders = {}
        self._payment_gateway = payment_gateway

    def create_order(self, session_id: str, items: List[OrderItem]) -> Order:
        order_id = str(uuid.uuid4())
        total = sum(self._recalculate_item_price(item) for item in items)

        order = Order(
            id=order_id,
            session_id=session_id,
            items=items,
            total_amount=total,
            status=PaymentStatus.PENDING
        )
        self._orders[order_id] = order
        return order

    def _recalculate_item_price(self, item: OrderItem) -> int:
        """Какая-то логика ценообразования"""
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

