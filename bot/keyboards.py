from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать звонок", callback_data="start_call")],
        [InlineKeyboardButton(text="Добавить контакт", callback_data="add_contact")],
    ])


def call_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать ссылку", callback_data="create_link")],
        [InlineKeyboardButton(text="Выбрать из контактов", callback_data="choose_from_contacts")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")],
    ])


def search_contacts_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Открыть поиск", switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="start_call")],
    ])


def contacts_list_kb(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"choose_contact:{tg_id}")]
            for tg_id, name in items]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="start_call")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
