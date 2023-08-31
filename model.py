import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from decimal import Decimal
from pydantic import BaseModel, Field


class EditableModel(BaseModel):
    @classmethod
    def get_editable_fields(cls):
        return list(cls.model_fields.keys())


class Product(EditableModel):
    color: Optional[str] = Field(None, title='Колір')
    size: Optional[str] = Field(None, title='Розмір')
    quantity: Optional[int] = Field(None, title='Кількість')
    price: Optional[Decimal] = Field(None, title='Ціна')


class OrderStatus(str, Enum):
    NEW = 'new'
    IN_PROGRESS = 'in_progress'
    DONE = 'done'


class CustomerInfo(EditableModel):
    full_name: Optional[str] = Field(
        None, title="Повне ім'я"
    )

    phone_number: Optional[str] = Field(
        None, title='Номер телефону'
    )

    shipping_address: Optional[str] = Field(
        None, title='Адреса доставки'
    )


class Order(BaseModel):
    id: int = Field(default_factory=lambda: uuid.uuid4().int, title='ID')
    created_at: Optional[datetime] = Field(default_factory=datetime.now, title="Дата створення")
    customer_info: CustomerInfo = Field(title='Інформація про клієнта', default_factory=CustomerInfo)
    shop_url: Optional[str] = Field(None, title='Посилання на магазин')
    products: List[str] = Field(default_factory=list, title='Товари')
    income: Optional[str] = Field(None, title='Скинули')
    price: Optional[str] = Field(None, title='Вартість всіх товарів')
    delivery_service: Optional[str] = Field(None, title='Служба доставки')
    delivery_price: Optional[str] = Field(None, title="Вартість доставки")
    service_fee: Optional[str] = Field(None, title="Комісія")
    received_at: Optional[datetime] = Field(None, title="Дата отримання")
    received_by_customer_at: Optional[datetime] = Field(None, title="Дата отримання клієнтом")
    status: Optional[OrderStatus] = Field(OrderStatus.NEW, title="Статус")
    products_tracking: List[bool] = Field(default_factory=list, title="Наявність ТТН")
    archived_at: Optional[datetime] = Field(None, title="Дата архівування")


class InProgressOrder(EditableModel):
    id: int
    delivery_price: Optional[str] = Field(None, title="Вартість доставки")
    service_fee: Optional[str] = Field(None, title="Комісія")
    status: OrderStatus = Field(OrderStatus.IN_PROGRESS)

    @classmethod
    def get_editable_fields(cls):
        return [f for f in list(cls.model_fields.keys()) if f not in ['id', 'status']]


class NewOrder(EditableModel):
    customer_info: CustomerInfo = Field(title='Інформація про клієнта', default_factory=CustomerInfo)
    shop_url: Optional[str] = Field(None, title='Посилання на магазин')
    products: List[str] = Field(default_factory=list, title='Товари')
    income: Optional[str] = Field(None, title='Скинули')
    price: Optional[str] = Field(None, title='Вартість всіх товарів')
    delivery_service: Optional[str] = Field(None, title='Служба доставки')


def set_nested_attribute(model: EditableModel, path, value) -> EditableModel:
    if len(path) == 1:
        model.__setattr__(path[0], value)
        return model
    else:
        key = path[0]
        return set_nested_attribute(getattr(model, key), path[1:], value)


def get_fields_paths(model: EditableModel) -> list:
    paths = []
    for field in model.get_editable_fields():
        if issubclass(NewOrder.model_fields[field].annotation, EditableModel):
            paths.extend(map(lambda x: f'{field}.{x}', get_fields_paths(getattr(model, field))))
        else:
            paths.append(field)
    return paths
