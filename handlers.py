import inspect
import logging
from datetime import datetime
from typing import List, get_type_hints, Type

from pydantic import BaseModel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ConversationHandler, CallbackContext, \
    ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.helpers import escape_markdown
from model import NewOrder, EditableModel, Order, OrderStatus, InProgressOrder
from repositories import OrderRepository

logger = logging.getLogger(__name__)

# # Define Pydantic models
# class NestedModel(EditableModel):
#     nested_field1: str = None
#     nested_field2: str = None
#
#
# class MainModel(EditableModel):
#     field1: str = Field(None, title='Field 1')
#     field2: int = Field(None, title='Field 2')
#     nested1: NestedModel = Field(None, title='Nested Field 1')
#     nested2: NestedModel = Field(None, title='Nested Field 2')
#     list_field1: List[str] = Field(default_factory=list, title='List Field 1')
#     list_field2: List[str] = Field(default_factory=list, title='List Field 2')

orders = OrderRepository()
BASE_MODEL = NewOrder


# Generate FIELD_MAPPING dictionary
def generate_field_mapping(field_dict, prefix="", title_prefix="", model: Type[EditableModel] = BASE_MODEL):
    mapping = {}
    for field_name, field_type in field_dict.items():
        if field_name in model.get_editable_fields():
            full_field_name = f"{prefix}{field_name}"
            title = model.model_fields[field_name].title
            if inspect.isclass(field_type) and issubclass(field_type, BaseModel):
                nested_mapping = generate_field_mapping(get_type_hints(field_type), prefix=f"{full_field_name}.", title_prefix=f'{title} -> ', model=field_type)
                mapping.update(nested_mapping)
            else:
                mapping[full_field_name] = f"{title_prefix}{title}"
    return mapping


# Conversation states
# FIELD_MAPPING = generate_field_mapping(get_type_hints(BASE_MODEL))

# Data storage for user inputs
user_data = {}
current_models = {}

# Conversation handler states
SELECTING_FIELD, ADDING_LIST_ITEM, SKIP_LIST, MENU, PASSWORD = range(5)

# orders = {
#     '1': Order(
#         id="1",
#         customer_info=CustomerInfo(
#             full_name='Алех',
#             phone_number="4567876542432",
#             shipping_address="Ololo"
#         ),
#         shop_url='http://example.com',
#         products=['fsdlkjflkasj', 'fkjsdlfjsa'],
#         income="10000",
#         price="100",
#         delivery_service="Mist",
#     )
# }


def unflatten_dict(dotted_dict):
    unflattened_dict = {}
    for key, value in dotted_dict.items():
        keys = key.split('.')
        current_dict = unflattened_dict
        for k in keys[:-1]:
            current_dict = current_dict.setdefault(k, {})
        current_dict[keys[-1]] = value
    return unflattened_dict


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user about their gender."""
    logger.info('START COMMAND')
    if str(update.message.chat.id) not in user_data.keys():
        await update.message.reply_text("Розкажи секрет")
        return PASSWORD
    reply_keyboard = [
        [InlineKeyboardButton(text='Додати замовлення', callback_data='add_order')],
        [InlineKeyboardButton(text='Нові замовлення', callback_data='new_orders')],
        [InlineKeyboardButton(text='Замовлення у процесі', callback_data='in_progress_orders')],
        [InlineKeyboardButton(text='Виконані замовлення', callback_data='done_orders')],
        [InlineKeyboardButton(text='Архів', callback_data='archived_orders')],
    ]
    current_models[str(update.message.chat.id)] = None

    await update.message.reply_text(
        """Головне меню""",
        reply_markup=InlineKeyboardMarkup(
            reply_keyboard,
        ),
    )

    return MENU


async def handle_password(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text
    if user_input == datetime.now().strftime("%d*%m*%Y"):
        await update.message.reply_text("Чудово!")
        user_data[str(update.message.chat.id)] = {}
        return MENU
    else:
        await update.message.reply_text("Вийди отсюда, розбійник!")
        return PASSWORD


async def fill_tracking(update: Update, context: CallbackContext):
    params = update.callback_query.data.split('.')[1:]

    if len(params) > 1:
        order_id, idx = params
        order = orders.get(int(order_id))

        order.products_tracking[int(idx)] = True
        method = update.callback_query.message.edit_text
    else:
        order_id = params[-1]
        order = orders.get(int(order_id))
        method = update.callback_query.message.reply_text

    orders.add(order)

    reply_keyboard = []

    for idx, product in enumerate(order.products):
        if order.products_tracking[idx]:
            continue

        reply_keyboard.append(
            [InlineKeyboardButton(text=product, callback_data=f'fill_tracking.{order_id}.{idx}')]
        )

    if len(reply_keyboard):
        await method(
            """Оберіть товари по яких сформовано ТТН""",
            reply_markup=InlineKeyboardMarkup(
                reply_keyboard,
            ),
        )
    else:
        await method('Всі товари заповнено')
    return MENU


async def in_progress_orders(update: Update, context: CallbackContext):
    _orders = orders.get_by_status(OrderStatus.IN_PROGRESS)
    if not len(_orders):
        await update.callback_query.message.reply_text('Немає заявок')

    for order in _orders:

        reply_keyboard = [
            [InlineKeyboardButton(text='Отримано клієнтом', callback_data=f'receive.{order.id}.customer')],
        ]
        if not order.received_at:
            reply_keyboard.insert(0, [InlineKeyboardButton(text='Отримано мною', callback_data=f'receive.{order.id}.me')])

        reply_keyboard.append(
            [InlineKeyboardButton(text='Архівувати', callback_data=f'archive.{order.id}')],
        )

        await display_data(
            update.callback_query.message, order,
            reply_markup=InlineKeyboardMarkup(
                reply_keyboard,
            ),
        )


async def done_orders(update: Update, context: CallbackContext):
    _orders = orders.get_by_status(OrderStatus.DONE)
    if not len(_orders):
        await update.callback_query.message.reply_text('Немає заявок')

    for order in _orders:
        reply_keyboard = [
            [InlineKeyboardButton(text='Архівувати', callback_data=f'archive.{order.id}')],
        ]

        await display_data(
            update.callback_query.message, order,
            reply_markup=InlineKeyboardMarkup(
                reply_keyboard,
            ),
        )


async def archived_orders(update: Update, context: CallbackContext):
    _orders = orders.get_archived()
    if not len(_orders):
        await update.callback_query.message.reply_text('Немає заявок')

    for order in _orders:
        reply_keyboard = [
            [InlineKeyboardButton(text='Відновити', callback_data=f'restore.{order.id}')],
        ]

        await display_data(
            update.callback_query.message, order,
            reply_markup=InlineKeyboardMarkup(
                reply_keyboard,
            ),
        )


async def archive_order(update: Update, context: CallbackContext):
    order_id = update.callback_query.data.split('.')[-1]
    chat_id = update.callback_query.from_user.id
    message_id = update.callback_query.message.id
    order = orders.get(int(order_id))
    order.archived_at = datetime.now()
    orders.add(order)
    await context.bot.delete_message(chat_id, message_id)


async def restore_order(update: Update, context: CallbackContext):
    order_id = update.callback_query.data.split('.')[-1]
    chat_id = update.callback_query.from_user.id
    message_id = update.callback_query.message.id
    order = orders.get(int(order_id))
    order.archived_at = None
    orders.add(order)
    await context.bot.delete_message(chat_id, message_id)


async def receive_order(update: Update, context: CallbackContext):
    order_id, received_by = update.callback_query.data.split('.')[1:]
    order = orders.get(int(order_id))
    order.received_at = datetime.now()
    if received_by == 'me':
        order.received_at = datetime.now()
        await display_data(
            message=update.callback_query.message,
            model=order,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text='Отримано клієнтом', callback_data=f'receive.{order_id}.customer')]
            ]),
            method='edit_text'
        )
    else:
        order.received_at = order.received_at or datetime.now()
        order.received_by_customer_at = datetime.now()
        order.status = OrderStatus.DONE
        await display_data(
            message=update.callback_query.message,
            model=order,
            reply_markup=InlineKeyboardMarkup([]),
            method='edit_text'
        )
    orders.add(order)


async def new_orders(update: Update, context: CallbackContext):
    _new_orders = orders.get_by_status(OrderStatus.NEW)

    if not len(_new_orders):
        await update.callback_query.message.reply_text('Немає заявок')

    for order in _new_orders:
        if all(order.products_tracking):
            reply_keyboard = [
                [InlineKeyboardButton(text='Продовжити', callback_data=f'continue.{order.id}')],
            ]
        else:
            reply_keyboard = [
                [InlineKeyboardButton(text='Вказати наявність ТТН', callback_data=f'fill_tracking.{order.id}')],
            ]

        reply_keyboard.append(
            [InlineKeyboardButton(text='Архівувати', callback_data=f'archive.{order.id}')],
        )

        await display_data(
            update.callback_query.message, order,
            reply_markup=InlineKeyboardMarkup(
                reply_keyboard,
            ),
        )


async def continue_filling(update: Update, context: CallbackContext):
    user_id = str(update.callback_query.from_user.id)
    current_models[user_id] = InProgressOrder
    order_id = update.callback_query.data.split('.')[1]
    data = orders.get(int(order_id)).model_dump()
    data['status'] = OrderStatus.IN_PROGRESS
    user_data[user_id] = InProgressOrder(**data).model_dump(
        exclude_none=True,
        exclude_unset=True,
        exclude_defaults=True
    )
    return await next_field(update, context)


async def add_order(update: Update, context: CallbackContext):
    user_id = str(update.callback_query.from_user.id)
    current_models[user_id] = NewOrder
    return await next_field(update, context)


async def next_field(update: Update, context: CallbackContext) -> int:
    if update.callback_query:
        message = update.callback_query.message
        user_id = str(update.callback_query.message.chat.id)
    else:
        message = update.message
        user_id = str(update.message.chat.id)

    current_model = current_models[user_id](**unflatten_dict(user_data[user_id]))
    for field, prompt in generate_field_mapping(get_type_hints(current_models[user_id]), model=current_models[user_id]).items():
        if field not in user_data[user_id]:
            if is_list_field(field, current_models[user_id]):
                user_data[user_id][field] = []
            else:
                user_data[user_id][field] = None
            await message.reply_text(prompt)
            return SELECTING_FIELD

    if current_models[user_id] is NewOrder:
        order = Order(**current_model.model_dump())
        order.products_tracking = [False] * len(order.products)
    else:
        order = Order(**{**orders.get(current_model.id).model_dump(), **current_model.model_dump()})
    orders.add(order)

    await display_data(message, order)
    del current_models[user_id]
    user_data[user_id] = {}
    return MENU


def is_list_field(field_name: str, model: Type[BaseModel]) -> bool:
    return get_type_hints(model).get(field_name) == List[str]


async def handle_text(update: Update, context: CallbackContext) -> int:
    user_id = str(update.message.chat.id)
    user_input = update.message.text
    current_field = list(user_data[user_id].keys())[-1]
    if current_field:
        if is_list_field(current_field, current_models[user_id]):
            user_data[user_id][current_field].append(user_input)
            await update.message.reply_text("Додано! Додайте ще, або напишіть /skip для завершення.")
            return ADDING_LIST_ITEM
        user_data[user_id][current_field] = user_input
        return await next_field(update, context)

    return MENU


async def handle_list_item(update: Update, context: CallbackContext) -> int:
    user_id = str(update.message.chat.id)
    user_input = update.message.text
    current_field = list(user_data[user_id].keys())[-1]

    # Stay in the same state to keep adding list items
    if user_input.lower() != "/skip":
        user_data[user_id][current_field].append(user_input)
        await update.message.reply_text("Додано! Додайте ще, або напишіть /skip для завершення.")
        return ADDING_LIST_ITEM
    else:
        return await next_field(update, context)


def format_model(model):
    result = ""
    for field_name, field in model.model_fields.items():
        attr = getattr(model, field_name)

        if field_name in ['products_tracking']:
            continue
        elif field_name == 'products':
            products = [
                (
                    escape_markdown(p) + '\t\t\t(є ТТН)'
                    if next(iter(getattr(model, 'products_tracking')[i:i+1]), None)
                    else escape_markdown(p)
                )
                for i, p in enumerate(attr)
            ]
            attr = '\n\t\t' + '\n\t\t'.join(products)

        if isinstance(attr, BaseModel):
            attr = '\n\t\t' + '\t\t'.join(format_model(attr).splitlines(True))
            attr = attr.rstrip('\n')
        elif isinstance(attr, list):
            attr = '\n\t\t' + escape_markdown('\n\t\t'.join(attr))
        else:
            attr = str(attr)
            attr = escape_markdown(attr, version=2)
        result += f"*{field.title}*: {attr}\n"
    return result


async def display_data(message: Message, model: BaseModel, method='reply_text', **kwargs) -> None:
    formatted = format_model(model)
    await getattr(message, method)(f"{formatted}", parse_mode='MarkdownV2', **kwargs)


conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), CommandHandler("start", start)],
            ADDING_LIST_ITEM: [MessageHandler(filters.TEXT, handle_list_item), CommandHandler("start", start)],
            MENU: [
                CallbackQueryHandler(new_orders, 'new_orders'),
                CallbackQueryHandler(done_orders, 'done_orders'),
                CallbackQueryHandler(in_progress_orders, 'in_progress_orders'),
                CallbackQueryHandler(receive_order, 'receive.*'),
                CallbackQueryHandler(add_order, 'add_order'),
                CallbackQueryHandler(continue_filling, 'continue.*'),
                CallbackQueryHandler(fill_tracking, 'fill_tracking.*'),
                CallbackQueryHandler(archived_orders, 'archived_orders'),
                CallbackQueryHandler(archive_order, 'archive.*'),
                CallbackQueryHandler(restore_order, 'restore.*'),
                CommandHandler("start", start)
            ],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)]
        },
        fallbacks=[],
    )
