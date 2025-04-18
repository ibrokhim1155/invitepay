from aiogram import types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from config import bot, dp, ADMIN_ID, HELP_USERNAME
from db import conn, cursor
from states import WithdrawState
from keyboards import main_menu, back_menu, admin_menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from referral import register_user_if_needed
from middlewares import is_subscribed

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None

    if user_id == ADMIN_ID:
        await message.answer("🔧 Admin paneliga xush kelibsiz!", reply_markup=admin_menu())
        return

    cursor.execute("SELECT title, username FROM channels")
    channels = cursor.fetchall()

    not_joined = []
    for title, username in channels:
        try:
            check = await bot.get_chat_member(f"@{username}" if "t.me/" not in username else username, user_id)
            if check.status not in ["member", "administrator", "creator"]:
                not_joined.append((title, username))
        except Exception:
            not_joined.append((title, username))

    if not_joined:
        text = "❗ Botdan foydalanish uchun quyidagi kanallarga a'zo bo‘ling:\n\n"
        for title, username in not_joined:
            link = f"https://t.me/{username.lstrip('@')}" if "t.me/" not in username else username
            text += f"📢 <a href='{link}'>{title}</a>\n"
        text += "\n✅ A'zo bo‘lganingizdan so‘ng, <b>Tekshirish</b> tugmasini bosing."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data=f"checksub:{payload or ''}")]
        ])
        await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
        return

    register_user_if_needed(user_id, payload)
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu())


@dp.callback_query(F.data.startswith("checksub"))
async def check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    payload = callback.data.split(":")[1] if ":" in callback.data else None

    if await is_subscribed(user_id):
        register_user_if_needed(user_id, payload)
        await callback.message.edit_text("✅ A'zolik tasdiqlandi!\n🏠 Asosiy menyu:", reply_markup=main_menu())
    else:
        await callback.answer("❗ Hali barcha kanallarga a'zo emassiz.", show_alert=True)


@dp.callback_query(F.data == "ref")
async def referral_link(callback: types.CallbackQuery):
    bot_user = await bot.get_me()
    link = f"https://t.me/{bot_user.username}?start={callback.from_user.id}"
    await callback.message.edit_text(f"📨 Sizning referal havolangiz:\n\n{link}", reply_markup=back_menu())


@dp.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    await callback.message.edit_text(f"💰 Sizning balansingiz: {balance} so'm", reply_markup=back_menu())


@dp.callback_query(F.data == "withdraw")
async def withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance < 5000:
        await callback.message.edit_text("❗ Pul yechish uchun balansingiz kamida <b>5000 so‘m</b> bo‘lishi kerak.")
        return

    await state.set_state(WithdrawState.full_name)
    await callback.message.edit_text("👤 Ism familiyangizni yuboring:")



@dp.message(WithdrawState.full_name)
async def get_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(WithdrawState.card_number)
    await message.answer("💳 Plastik raqamingizni yuboring:")


@dp.message(WithdrawState.card_number)
async def get_card_number(message: types.Message, state: FSMContext):
    data = await state.get_data()
    full_name = data["full_name"]
    card = message.text
    user_id = message.from_user.id

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]

    await bot.send_message(
        ADMIN_ID,
        f"🧾 Pul yechish so‘rovi:\n👤 {full_name}\n💳 {card}\n💰 {balance} so'm"
    )

    cursor.execute(
        "UPDATE users SET balance = 0, full_name = ?, card_number = ? WHERE user_id = ?",
        (full_name, card, user_id)
    )
    cursor.execute("INSERT INTO payouts (user_id, amount) VALUES (?, ?)", (user_id, balance))
    conn.commit()

    await message.answer("✅ So‘rovingiz yuborildi. Tez orada ko‘rib chiqiladi.")
    await state.clear()


@dp.callback_query(F.data == "help")
async def help_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(f"🌐 Yordam uchun: @{HELP_USERNAME}", reply_markup=back_menu())


@dp.callback_query(F.data == "back")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu())
