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
    price: int

@dataclass
class Order:
    id: str
    session_id: str  # Добавляем привязку к сессии
    items: List[OrderItem]
    total_amount: int
    status: PaymentStatus
    email: Optional[str] = None
