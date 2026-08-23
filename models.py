# models.py - Модели данных (ИСПРАВЛЕН - правильный порядок полей)

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class City:
    name: str

@dataclass
class Product:
    # Обязательные поля (БЕЗ значений по умолчанию)
    city: str
    name: str
    quantity: str
    price: int
    # Необязательные поля (СО значениями по умолчанию)
    in_stock: bool = True
    product_code: str = None
    id: int = None
    created_at: datetime = None

@dataclass
class Order:
    # Обязательные поля
    user_id: int
    product_name: str
    city: str
    quantity: str
    price: int
    # Необязательные поля
    product_code: str = None
    created_at: datetime = None
    is_auto: bool = False

@dataclass
class AutoSellCampaign:
    # Обязательные поля
    id: int
    name: str
    cities: List[str]
    products: List[str]
    quantities: List[str]
    prices: List[int]
    days: int
    started_at: datetime
    # Необязательные поля
    is_active: bool = True
    sold_count: int = 0
    total_revenue: int = 0

@dataclass
class User:
    # Обязательное поле
    user_id: int
    # Необязательные поля
    username: str = None
    first_name: str = None
    last_name: str = None
    subscribed: bool = True
    is_blocked: bool = False
    blocked_at: datetime = None
    created_at: datetime = None