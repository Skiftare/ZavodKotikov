# payment_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import uuid

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

    def __init__(self, cat_id: str, name: str, breed: str, color: str, ears: str, paws: str, container: str, pattern: str, price: int):
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
