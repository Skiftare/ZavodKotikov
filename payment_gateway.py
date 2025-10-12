# payment_gateway.py
from abc import ABC, abstractmethod
from payment_service import PaymentStatus, Order


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
