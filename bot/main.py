import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass

import uvloop
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv

from db import Database
from keyboards import main_menu_kb, call_menu_kb, contacts_list_kb, search_contacts_kb, call_invite_kb, call_invite_menu_only_kb


class RegStates(StatesGroup):
    waiting_for_name = State()


class SearchStates(StatesGroup):
    waiting_for_query = State()


@dataclass
class Config:
    bot_token: str
    database_url: str
    app_public_base_url: str


def get_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    db_url = os.getenv("DATABASE_URL")
    base_url = os.getenv("APP_PUBLIC_BASE_URL", "http://localhost:8080")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return Config(bot_token=token, database_url=db_url, app_public_base_url=base_url)


@asynccontextmanager
async def lifespan(dp: Dispatcher, db: Database):
    await db.connect()
    try:
        yield
    finally:
        await db.close()


async def send_call_notifications(bot: Bot, initiator_id: int, target_id: int, url: str, room_id: str) -> None:
    notify = "Начат звонок. Ссылка на комнату:\n" + url
    try:
        await bot.send_message(target_id, notify, reply_markup=call_invite_kb(room_id, initiator_id, target_id, url))
    except Exception:
        pass
    try:
        await bot.send_message(initiator_id, notify, reply_markup=call_invite_menu_only_kb(room_id, initiator_id, target_id))
    except Exception:
        pass


async def main() -> None:
    uvloop.install()
    cfg = get_config()
    bot = Bot(token=cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    db = Database(cfg.database_url)

    @dp.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        payload = message.text.split(maxsplit=1)
        invite_owner_id: int | None = None
        if len(payload) == 2 and payload[1].startswith("add_"):
            try:
                invite_owner_id = int(payload[1].split("_", 1)[1])
            except Exception:
                invite_owner_id = None

        user = await db.get_user(message.from_user.id)
        if invite_owner_id and invite_owner_id == message.from_user.id:
            await message.answer("Это ваша ссылка приглашения. Отправьте её другому пользователю.", reply_markup=main_menu_kb())
            return

        if user is None:
            await message.answer("Добро пожаловать! Пожалуйста, введите ваше имя пользователя:")
            await state.set_state(RegStates.waiting_for_name)
            if invite_owner_id:
                await state.update_data(invite_owner_id=invite_owner_id)
            return

        if invite_owner_id:
            await db.add_contact(invite_owner_id, message.from_user.id)
            await message.answer("Вы добавлены в контакты. Откройте меню.", reply_markup=main_menu_kb())
            return

        await message.answer("Главное меню", reply_markup=main_menu_kb())

    @dp.message(RegStates.waiting_for_name)
    async def on_name_entered(message: Message, state: FSMContext) -> None:
        username = (message.text or "").strip()
        if not username:
            await message.answer("Имя не должно быть пустым. Введите имя ещё раз:")
            return
        await db.upsert_user(message.from_user.id, username)
        data = await state.get_data()
        invite_owner_id = data.get("invite_owner_id")
        if invite_owner_id and invite_owner_id != message.from_user.id:
            await db.add_contact(invite_owner_id, message.from_user.id)
        await state.clear()
        await message.answer(f"Спасибо, {hbold(username)}!", reply_markup=main_menu_kb())

    @dp.callback_query(F.data == "add_contact")
    async def on_add_contact(cb: CallbackQuery) -> None:
        me = await bot.get_me()
        invite_link = f"https://t.me/{me.username}?start=add_{cb.from_user.id}"
        await cb.message.edit_text(
            "Отправьте эту ссылку человеку, чтобы добавить его в контакты:\n" + invite_link,
            reply_markup=main_menu_kb(),
        )
        await cb.answer()

    @dp.callback_query(F.data == "start_call")
    async def on_start_call(cb: CallbackQuery) -> None:
        await cb.message.edit_text("Выберите опцию:", reply_markup=call_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "back_to_main")
    async def on_back_to_main(cb: CallbackQuery) -> None:
        await cb.message.edit_text("Главное меню", reply_markup=main_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "create_link")
    async def on_create_link(cb: CallbackQuery) -> None:
        room_id = secrets.token_urlsafe(9)
        await db.create_room(room_id, cb.from_user.id)
        url = f"{cfg.app_public_base_url}/call.html?room={room_id}"
        await cb.message.edit_text(f"Ссылка на комнату:\n{url}", reply_markup=call_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "choose_from_contacts")
    async def on_choose_from_contacts(cb: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(SearchStates.waiting_for_query)
        await cb.message.edit_text("Введите имя", reply_markup=search_contacts_kb())
        await cb.answer()

    @dp.message(SearchStates.waiting_for_query)
    async def on_text_search(message: Message, state: FSMContext) -> None:
        q = (message.text or "").strip()
        if not q:
            await message.answer("Введите имя для поиска")
            return
        items = await db.search_contacts(message.from_user.id, q)
        if not items:
            await message.answer("Ничего не найдено. Попробуйте другое имя.")
            return
        if len(items) == 1:
            rec = items[0]
            target_id = int(rec["telegram_id"])  # contact id
            room_id = secrets.token_urlsafe(9)
            await db.create_room(room_id, message.from_user.id)
            url = f"{cfg.app_public_base_url}/call.html?room={room_id}"
            await send_call_notifications(bot, message.from_user.id, target_id, url, room_id)
            await state.clear()
            return
        buttons = [(int(r["telegram_id"]), str(r["username"])) for r in items]
        await message.answer("Результаты поиска:", reply_markup=contacts_list_kb(buttons))
        await state.clear()

    @dp.callback_query(F.data.startswith("choose_contact:"))
    async def on_choose_contact(cb: CallbackQuery) -> None:
        try:
            target_id = int(cb.data.split(":", 1)[1])
        except Exception:
            await cb.answer("Ошибка выбора контакта", show_alert=True)
            return
        room_id = secrets.token_urlsafe(9)
        await db.create_room(room_id, cb.from_user.id)
        url = f"{cfg.app_public_base_url}/call.html?room={room_id}"
        await send_call_notifications(bot, cb.from_user.id, target_id, url, room_id)
        await cb.answer("Ссылка отправлена")

    @dp.inline_query()
    async def on_inline_query(iq: InlineQuery) -> None:
        q = (iq.query or "").strip()
        if not q:
            await iq.answer([], cache_time=1, is_personal=True)
            return
        items = await db.search_contacts(iq.from_user.id, q)
        results: list[InlineQueryResultArticle] = []
        for rec in items:
            tg_id = int(rec["telegram_id"])  # contact's tg id
            username = str(rec["username"])  # contact's saved name
            result_id = f"contact:{tg_id}"
            results.append(
                InlineQueryResultArticle(
                    id=result_id,
                    title=username,
                    description="Начать звонок",
                    input_message_content=InputTextMessageContent(
                        message_text=f"{hbold(username)}",
                        parse_mode=ParseMode.HTML,
                    ),
                )
            )
        await iq.answer(results, cache_time=1, is_personal=True)

    @dp.chosen_inline_result()
    async def on_chosen_inline_result(chosen: ChosenInlineResult) -> None:
        try:
            if not chosen.result_id.startswith("contact:"):
                return
            target_id = int(chosen.result_id.split(":", 1)[1])
        except Exception:
            return
        room_id = secrets.token_urlsafe(9)
        url = f"{cfg.app_public_base_url}/call.html?room={room_id}"
        await db.create_room(room_id, chosen.from_user.id)
        notify = "Начат звонок. Ссылка на комнату:\n" + url
        try:
            await bot.send_message(target_id, notify, reply_markup=call_invite_kb(room_id, chosen.from_user.id, target_id, url))
        except Exception:
            pass
        try:
            await bot.send_message(chosen.from_user.id, notify, reply_markup=call_invite_menu_only_kb(room_id, chosen.from_user.id, target_id))
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("call_decline:"))
    async def on_call_decline(cb: CallbackQuery) -> None:
        try:
            _, room_id, initiator_s, target_s = cb.data.split(":", 3)
            initiator_id = int(initiator_s)
            target_id = int(target_s)
        except Exception:
            await cb.answer("Ошибка", show_alert=True)
            return
        await cb.message.edit_text("Звонок отклонён.")
        try:
            await bot.send_message(initiator_id, "Пользователь отклонил звонок ❌")
        except Exception:
            pass
        await cb.answer()

    @dp.callback_query(F.data.startswith("call_menu_cancel:"))
    async def on_call_menu_cancel(cb: CallbackQuery) -> None:
        try:
            _, room_id, initiator_s, target_s = cb.data.split(":", 3)
            initiator_id = int(initiator_s)
            target_id = int(target_s)
        except Exception:
            await cb.answer("Ошибка", show_alert=True)
            return
        await cb.message.edit_text("Главное меню", reply_markup=main_menu_kb())
        try:
            await bot.send_message(initiator_id, "Пользователь отменил звонок")
        except Exception:
            pass
        await cb.answer()

    async with lifespan(dp, db):
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
