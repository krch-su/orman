from typing import List, Optional

from tinydb import TinyDB, Query, JSONStorage
from tinydb_serialization import SerializationMiddleware
from tinydb_serialization.serializers import DateTimeSerializer

from model import Order, OrderStatus


serialization = SerializationMiddleware(JSONStorage)
serialization.register_serializer(DateTimeSerializer(), 'TinyDate')
db = TinyDB('db.json', storage=serialization)


class OrderRepository:
    _table = db.table('orders')

    def add(self, order: Order) -> int:
        return self._table.upsert(order.model_dump(), Query().id == order.id)[0]

    def get(self, id_: int) -> Optional[Order]:
        data = self._table.get(Query().id == id_)
        if data:
            return Order(**data)
        return None

    def get_by_status(self, status: OrderStatus) -> List[Order]:
        data = self._table.search(
            (Query().status == status) &
            ((Query().archived_at == None) | ~(Query().archived_at.exists()))
        )
        if data:
            return list(map(lambda d: Order(**d), data))
        else:
            return []

    def get_archived(self) -> List[Order]:
        data = self._table.search(Query().archived_at != None)
        if data:
            return list(map(lambda d: Order(**d), data))
        else:
            return []
