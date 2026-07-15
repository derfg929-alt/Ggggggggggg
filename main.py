#!/usr/bin/env python3
# =====================================================================
#                    НЕЙРО-ХУДОЖНИК v3.0 (ПОЛНАЯ ВЕРСИЯ)
# =====================================================================

import asyncio
import os
import random
import logging
import requests
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# =====================================================================
#                        КОНФИГ
# =====================================================================

@dataclass
class Config:
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    CREATOR_ID: int = int(os.getenv('CREATOR_ID', 0))
    WALLET: str = "UQCvOIAt2X1PHfquND-LxzVYg0Gl3a_IExORwwPjowI3Nkb8"
    DB_PATH: str = "/app/data/bot.db"

config = Config()

if not config.BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан!")

# =====================================================================
#                        НАСТРОЙКА ЛОГОВ
# =====================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================================
#                        БАЗА ДАННЫХ
# =====================================================================

def init_db():
    os.makedirs("/app/data", exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 10,
            total_gens INTEGER DEFAULT 0,
            ref_code TEXT UNIQUE,
            ref_by INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            date TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

init_db()

# =====================================================================
#                        ФУНКЦИИ БАЗЫ ДАННЫХ
# =====================================================================

def get_user(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "coins": row[2],
            "total_gens": row[3],
            "ref_code": row[4],
            "ref_by": row[5],
            "ref_count": row[6],
            "created_at": row[7]
        }
    return None

def create_user(user_id: int, username: str = None) -> Dict:
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    
    # Генерируем реферальный код
    ref_code = f"REF{user_id}{random.randint(100, 999)}"
    
    c.execute("""
        INSERT INTO users (user_id, username, coins, ref_code, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, 10, ref_code, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return get_user(user_id)

def add_coins(user_id: int, amount: int):
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def remove_coins(user_id: int, amount: int) -> bool:
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    if row and row[0] >= amount:
        c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def add_referral(referrer_id: int, referred_id: int):
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    
    c.execute("INSERT INTO referrals (referrer_id, referred_id, date) VALUES (?, ?, ?)",
              (referrer_id, referred_id, datetime.now().isoformat()))
    
    c.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (referrer_id,))
    c.execute("UPDATE users SET coins = coins + 50 WHERE user_id = ?", (referrer_id,))
    c.execute("UPDATE users SET ref_by = ? WHERE user_id = ?", (referrer_id, referred_id))
    
    conn.commit()
    conn.close()

def get_referrals(user_id: int) -> list:
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT referred_id, date FROM referrals WHERE referrer_id = ? ORDER BY date DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_ref_code(user_id: int) -> str:
    user = get_user(user_id)
    if user:
        return user["ref_code"]
    return None

def get_user_by_ref_code(ref_code: str) -> Optional[int]:
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# =====================================================================
#                        ИНИЦИАЛИЗАЦИЯ БОТА
# =====================================================================

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

# =====================================================================
#                        ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# =====================================================================

BOT_NAME = "Нейро-Художник"
VERSION = "3.0.0"
user_generations: Dict[int, int] = {}
user_text_generations: Dict[int, int] = {}
MAX_FREE_TEXT = 20
COST_PER_IMAGE = 50

# =====================================================================
#                        КНОПКИ
# =====================================================================

def get_main_keyboard():
    buttons = [
        [InlineKeyboardButton("🎨 Нарисовать", callback_data="draw")],
        [InlineKeyboardButton("📝 Стих", callback_data="poem")],
        [InlineKeyboardButton("📱 Пост", callback_data="post")],
        [InlineKeyboardButton("🧠 Спросить", callback_data="ask")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="refs")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton("💼 Работа", callback_data="work")],
        [InlineKeyboardButton("📋 Команды", callback_data="help")],
        [InlineKeyboardButton("💰 Поддержать", callback_data="donate")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard():
    buttons = [[InlineKeyboardButton("⬅️ Назад", callback_data="menu")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_work_keyboard():
    buttons = [
        [InlineKeyboardButton("💼 Поработать (10-50)", callback_data="do_work")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# =====================================================================
#                        ФУНКЦИЯ РАСПОЗНАВАНИЯ КОМАНД
# =====================================================================

def detect_command(text: str):
    if not text:
        return None, None
    
    lower_text = text.lower().strip()
    
    bot_names = ['фабле', 'фабл', 'фаблэ', 'fabler', 'fable', 'fabl', 'нейро', 'художник', 'бот', 'бро']
    
    is_called = False
    clean_text = lower_text
    
    for name in bot_names:
        if name in lower_text:
            is_called = True
            clean_text = lower_text.replace(name, '').strip()
            break
    
    if not is_called:
        return None, None
    
    if not clean_text:
        return "hello", ""
    
    commands = {
        'нарисуй': ['нарисуй', 'рисуй', 'сгенерируй', 'ген', 'картинку', 'картинка', 'изображение', 'фото', 'макака', 'макаку'],
        'стих': ['стих', 'стихотворение', 'стихи', 'поэма', 'рифма'],
        'пост': ['пост', 'текст', 'сообщение', 'статья', 'запись'],
        'спроси': ['спроси', 'вопрос', 'ответ', 'скажи', 'расскажи', 'объясни', 'помоги', 'что', 'как', 'почему', 'где', 'когда', 'кто'],
        'работа': ['работа', 'работать', 'заработать', 'деньги'],
        'бонус': ['бонус', 'ежедневный', 'подарок'],
        'баланс': ['баланс', 'монеты', 'сколько'],
        'реферал': ['реферал', 'пригласить', 'друзья', 'друг'],
        'купить': ['купить', 'купи']
    }
    
    for cmd, variants in commands.items():
        for variant in variants:
            if clean_text.startswith(variant):
                prompt = clean_text[len(variant):].strip()
                return cmd, prompt
            if clean_text == variant:
                return cmd, ""
    
    if len(clean_text) > 0:
        return "спроси", clean_text
    
    return None, None

# =====================================================================
#                        ОБРАБОТЧИКИ КОМАНД
# =====================================================================

@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    user = get_user(user_id)
    if not user:
        user = create_user(user_id, username)
        
        # Проверяем реферальный код
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("ref_"):
            ref_code = args[1].replace("ref_", "")
            referrer_id = get_user_by_ref_code(ref_code)
            if referrer_id and referrer_id != user_id:
                add_referral(referrer_id, user_id)
                add_coins(user_id, 10)
                
                try:
                    await bot.send_message(referrer_id, f"🎉 Новый реферал! {message.from_user.first_name} пришёл по твоей ссылке!\n💰 +50 монет")
                except:
                    pass
    
    if user_id not in user_generations:
        user_generations[user_id] = 0
    if user_id not in user_text_generations:
        user_text_generations[user_id] = 0
    
    ref_code = get_ref_code(user_id)
    ref_link = f"https://t.me/{bot.username}?start=ref_{ref_code}"
    
    await message.reply(
        f"🎨 **{BOT_NAME}** v{VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"💰 **Баланс:** {user['coins']} монет\n"
        f"🎨 **Сгенерировано:** {user['total_gens']}\n"
        f"👥 **Рефералов:** {user['ref_count']}\n\n"
        f"✨ **Я умею:**\n"
        f"🎨 Рисовать картинки (50 монет)\n"
        f"📝 Писать стихи (бесплатно)\n"
        f"📱 Создавать посты (бесплатно)\n"
        f"🧠 Отвечать на вопросы (бесплатно)\n\n"
        f"💰 **Как заработать монеты:**\n"
        f"💼 Работа: 10-50 монет\n"
        f"🎁 Ежедневный бонус: 50 монет\n"
        f"👥 Пригласить друга: +50 монет\n\n"
        f"🔗 **Твоя реферальная ссылка:**\n"
        f"`{ref_link}`\n\n"
        f"💎 **Поддержать:** `{config.WALLET}`",
        reply_markup=get_main_keyboard()
    )

# =====================================================================
#                        КОМАНДЫ МОНЕТОК
# =====================================================================

@dp.message(Command("balance"))
async def balance_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        user = create_user(user_id, message.from_user.username)
    
    await message.reply(
        f"💰 **ТВОЙ БАЛАНС**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 Монет: **{user['coins']}**\n"
        f"🎨 Генераций: **{user['total_gens']}**\n"
        f"👥 Рефералов: **{user['ref_count']}**\n\n"
        f"💰 1 генерация = 50 монет\n"
        f"💡 Напиши `Фабле работа` чтобы заработать!",
        reply_markup=get_back_keyboard()
    )

@dp.message(Command("work"))
async def work_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        user = create_user(user_id, message.from_user.username)
    
    # Проверяем кулдаун (10 минут)
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
    last_work = c.fetchone()
    conn.close()
    
    if last_work:
        last_time = datetime.fromisoformat(last_work[0])
        if (datetime.now() - last_time).total_seconds() < 600:
            remaining = int(600 - (datetime.now() - last_time).total_seconds())
            minutes = remaining // 60
            seconds = remaining % 60
            await message.reply(
                f"⏳ Подожди {minutes}мин {seconds}сек до следующей работы!\n"
                f"💡 Попробуй позже.",
                reply_markup=get_back_keyboard()
            )
            return
    
    await message.reply(
        f"💼 **РАБОТА**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Нажми кнопку чтобы поработать и заработать монеты!",
        reply_markup=get_work_keyboard()
    )

@dp.message(Command("bonus"))
async def bonus_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        user = create_user(user_id, message.from_user.username)
    
    # Проверяем кулдаун (24 часа)
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
    last_bonus = c.fetchone()
    conn.close()
    
    if last_bonus:
        last_time = datetime.fromisoformat(last_bonus[0])
        if (datetime.now() - last_time).total_seconds() < 86400:
            remaining = int(86400 - (datetime.now() - last_time).total_seconds())
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await message.reply(
                f"⏳ Ежедневный бонус будет доступен через {hours}ч {minutes}м!\n"
                f"💡 Загляни завтра!",
                reply_markup=get_back_keyboard()
            )
            return
    
    add_coins(user_id, 50)
    
    await message.reply(
        f"🎁 **ЕЖЕДНЕВНЫЙ БОНУС!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 +50 монет!\n"
        f"💎 Баланс: {get_user(user_id)['coins']} монет\n\n"
        f"💡 Завтра бонус снова будет доступен!",
        reply_markup=get_back_keyboard()
    )

@dp.message(Command("referrals"))
async def referrals_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        user = create_user(user_id, message.from_user.username)
    
    ref_code = get_ref_code(user_id)
    ref_link = f"https://t.me/{bot.username}?start=ref_{ref_code}"
    referrals = get_referrals(user_id)
    
    msg = f"👥 **ТВОИ РЕФЕРАЛЫ**\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"🔗 **Твоя ссылка:**\n"
    msg += f"`{ref_link}`\n\n"
    msg += f"📊 **Всего рефералов:** {user['ref_count']}\n"
    msg += f"💰 **Заработано:** {user['ref_count'] * 50} монет\n\n"
    
    if referrals:
        msg += "📋 **Список рефералов:**\n"
        for ref_id, date in referrals[:10]:
            try:
                user_info = await bot.get_chat(ref_id)
                name = user_info.first_name or "Неизвестный"
                msg += f"• {name} — {date[:10]}\n"
            except:
                msg += f"• Пользователь — {date[:10]}\n"
        if len(referrals) > 10:
            msg += f"\n... и ещё {len(referrals) - 10} рефералов"
    else:
        msg += "📭 У тебя пока нет рефералов.\n"
        msg += "💡 Пригласи друга и получи +50 монет!"
    
    await message.reply(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_keyboard())

# =====================================================================
#                        КОЛБЭКИ
# =====================================================================

@dp.callback_query(lambda c: True)
async def callback_handler(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    user = get_user(user_id)
    if not user:
        user = create_user(user_id, callback.from_user.username)
    
    if data == "menu":
        await callback.message.edit_text(
            f"🎨 **{BOT_NAME}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Баланс: {user['coins']} монет\n"
            f"👥 Рефералов: {user['ref_count']}\n\n"
            f"Напиши **Фабле** и что хочешь 👇",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
        return
    
    if data == "balance":
        await callback.message.edit_text(
            f"💰 **ТВОЙ БАЛАНС**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💎 Монет: **{user['coins']}**\n"
            f"🎨 Генераций: **{user['total_gens']}**\n"
            f"👥 Рефералов: **{user['ref_count']}**\n\n"
            f"💰 1 генерация = 50 монет\n"
            f"💡 Работай чтобы заработать!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "refs":
        await referrals_command(callback.message)
        await callback.answer()
        return
    
    if data == "bonus":
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
        last_bonus = c.fetchone()
        conn.close()
        
        if last_bonus:
            last_time = datetime.fromisoformat(last_bonus[0])
            if (datetime.now() - last_time).total_seconds() < 86400:
                remaining = int(86400 - (datetime.now() - last_time).total_seconds())
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await callback.answer(f"⏳ Через {hours}ч {minutes}м", show_alert=True)
                return
        
        add_coins(user_id, 50)
        await callback.message.edit_text(
            f"🎁 **ЕЖЕДНЕВНЫЙ БОНУС!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 +50 монет!\n"
            f"💎 Баланс: {get_user(user_id)['coins']} монет",
            reply_markup=get_back_keyboard()
        )
        await callback.answer("🎁 +50 монет!")
        return
    
    if data == "work":
        await callback.message.edit_text(
            f"💼 **РАБОТА**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Нажми кнопку чтобы поработать!",
            reply_markup=get_work_keyboard()
        )
        await callback.answer()
        return
    
    if data == "do_work":
        # Проверка кулдауна
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
        last_work = c.fetchone()
        conn.close()
        
        if last_work:
            last_time = datetime.fromisoformat(last_work[0])
            if (datetime.now() - last_time).total_seconds() < 600:
                remaining = int(600 - (datetime.now() - last_time).total_seconds())
                minutes = remaining // 60
                seconds = remaining % 60
                await callback.answer(f"⏳ {minutes}мин {seconds}сек", show_alert=True)
                return
        
        # Заработок
        earnings = random.randint(10, 50)
        add_coins(user_id, earnings)
        new_balance = get_user(user_id)["coins"]
        
        await callback.message.edit_text(
            f"💼 **РАБОТА ВЫПОЛНЕНА!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 +{earnings} монет!\n"
            f"💎 Баланс: {new_balance} монет\n\n"
            f"💡 Следующая работа через 10 минут!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer(f"💰 +{earnings} монет!")
        return
    
    if data == "donate":
        await callback.message.edit_text(
            f"❤️ **ПОДДЕРЖАТЬ ПРОЕКТ**\n\n"
            f"💎 **TON Wallet:**\n"
            f"`{config.WALLET}`\n\n"
            f"💰 **Сумма любая!**\n"
            f"Спасибо за поддержку! 🙏",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "help":
        await callback.message.edit_text(
            f"📋 **ЧТО Я УМЕЮ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎨 **Нарисовать (50 монет):**\n"
            f"`Фабле нарисуй закат`\n\n"
            f"📝 **Написать стих:**\n"
            f"`Фабле стих о любви`\n\n"
            f"📱 **Создать пост:**\n"
            f"`Фабле пост о путешествиях`\n\n"
            f"🧠 **Спросить:**\n"
            f"`Фабле спроси как дела`\n\n"
            f"💰 **Заработать монеты:**\n"
            f"`Фабле работа` — 10-50 монет\n"
            f"`Фабле бонус` — 50 монет (24ч)\n"
            f"👥 Пригласить друга — +50 монет\n\n"
            f"🛒 **Купить генерацию:**\n"
            f"Автоматически списывается 50 монет\n\n"
            f"💰 **Поддержать:** /donate",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "draw":
        await callback.message.edit_text(
            f"🎨 **НАРИСОВАТЬ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Стоимость: 50 монет\n"
            f"💎 Баланс: {user['coins']} монет\n\n"
            f"Напиши: `Фабле нарисуй закат в горах`\n\n"
            f"💡 Я пойму любой запрос!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "poem":
        await callback.message.edit_text(
            f"📝 **НАПИСАТЬ СТИХ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Бесплатно!\n\n"
            f"Напиши: `Фабле стих о любви`\n\n"
            f"💡 Я пойму любую тему!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "post":
        await callback.message.edit_text(
            f"📱 **СОЗДАТЬ ПОСТ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 Бесплатно!\n\n"
            f"Напиши: `Фабле пост о путешествиях`\n\n"
            f"💡 Я пойму любую тему!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "ask":
        await callback.message.edit_text(
            f"🧠 **ЗАДАТЬ ВОПРОС**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🧠 Бесплатно!\n\n"
            f"Напиши: `Фабле спроси как дела`\n\n"
            f"💡 Я пойму любой вопрос!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return

# =====================================================================
#                        ОБРАБОТЧИК СООБЩЕНИЙ
# =====================================================================

@dp.message()
async def handle_messages(message: Message):
    if not message.text:
        return
    
    text = message.text.strip()
    user_id = message.from_user.id
    
    user = get_user(user_id)
    if not user:
        user = create_user(user_id, message.from_user.username)
    
    if user_id not in user_generations:
        user_generations[user_id] = 0
    if user_id not in user_text_generations:
        user_text_generations[user_id] = 0
    
    cmd, prompt = detect_command(text)
    
    if cmd == "hello":
        await message.reply(
            f"👋 Привет! Я {BOT_NAME} v{VERSION}\n\n"
            f"💰 Баланс: {user['coins']} монет\n\n"
            f"Напиши **Фабле** и что хочешь:\n"
            f"• `Фабле нарисуй закат` 🎨 (50 монет)\n"
            f"• `Фабле стих о любви` 📝 (бесплатно)\n"
            f"• `Фабле пост о путешествиях` 📱 (бесплатно)\n"
            f"• `Фабле спроси как дела` 🧠 (бесплатно)\n\n"
            f"💰 **Заработать:** `Фабле работа`",
            reply_markup=get_main_keyboard()
        )
        return
    
    if cmd == "нарисуй":
        if not prompt:
            await message.reply("❌ Напиши что нарисовать. Например: `Фабле нарисуй закат`", reply_markup=get_back_keyboard())
            return
        
        # Проверяем баланс
        if user["coins"] < COST_PER_IMAGE:
            await message.reply(
                f"❌ Недостаточно монет!\n"
                f"💰 Стоимость: {COST_PER_IMAGE} монет\n"
                f"💎 Баланс: {user['coins']} монет\n\n"
                f"💡 Заработай: `Фабле работа`",
                reply_markup=get_back_keyboard()
            )
            return
        
        if remove_coins(user_id, COST_PER_IMAGE):
            await generate_image(message, prompt, user_id)
        return
    
    if cmd == "стих":
        if not prompt:
            await message.reply("❌ Напиши тему стиха. Например: `Фабле стих о любви`", reply_markup=get_back_keyboard())
            return
        await generate_text(message, prompt, "poem", user_id)
        return
    
    if cmd == "пост":
        if not prompt:
            await message.reply("❌ Напиши тему поста. Например: `Фабле пост о путешествиях`", reply_markup=get_back_keyboard())
            return
        await generate_text(message, prompt, "post", user_id)
        return
    
    if cmd == "спроси":
        if not prompt:
            await message.reply("❌ Напиши вопрос. Например: `Фабле спроси как дела`", reply_markup=get_back_keyboard())
            return
        await generate_text(message, prompt, "ask", user_id)
        return
    
    if cmd == "работа":
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
        last_work = c.fetchone()
        conn.close()
        
        if last_work:
            last_time = datetime.fromisoformat(last_work[0])
            if (datetime.now() - last_time).total_seconds() < 600:
                remaining = int(600 - (datetime.now() - last_time).total_seconds())
                minutes = remaining // 60
                seconds = remaining % 60
                await message.reply(
                    f"⏳ Подожди {minutes}мин {seconds}сек!\n"
                    f"💡 Попробуй позже.",
                    reply_markup=get_back_keyboard()
                )
                return
        
        earnings = random.randint(10, 50)
        add_coins(user_id, earnings)
        new_balance = get_user(user_id)["coins"]
        
        await message.reply(
            f"💼 **РАБОТА ВЫПОЛНЕНА!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 +{earnings} монет!\n"
            f"💎 Баланс: {new_balance} монет\n\n"
            f"💡 Следующая работа через 10 минут!",
            reply_markup=get_back_keyboard()
        )
        return
    
    if cmd == "бонус":
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT date FROM referrals WHERE referrer_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
        last_bonus = c.fetchone()
        conn.close()
        
        if last_bonus:
            last_time = datetime.fromisoformat(last_bonus[0])
            if (datetime.now() - last_time).total_seconds() < 86400:
                remaining = int(86400 - (datetime.now() - last_time).total_seconds())
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await message.reply(
                    f"⏳ Через {hours}ч {minutes}м!\n"
                    f"💡 Загляни завтра.",
                    reply_markup=get_back_keyboard()
                )
                return
        
        add_coins(user_id, 50)
        await message.reply(
            f"🎁 **ЕЖЕДНЕВНЫЙ БОНУС!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 +50 монет!\n"
            f"💎 Баланс: {get_user(user_id)['coins']} монет",
            reply_markup=get_back_keyboard()
        )
        return
    
    if cmd == "баланс":
        await balance_command(message)
        return
    
    if cmd == "реферал":
        await referrals_command(message)
        return

# =====================================================================
#                        ГЕНЕРАЦИЯ КАРТИНОК
# =====================================================================

async def generate_image(message: Message, prompt: str, user_id: int):
    wait_msg = await message.reply(f"🎨 Рисую: **{prompt[:50]}...**\n⏳ Подожди 5-10 секунд")
    
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=768"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open("/tmp/image.png", "wb") as f:
            f.write(response.content)
        
        user = get_user(user_id)
        with open("/tmp/image.png", "rb") as f:
            await message.reply_photo(
                f,
                caption=f"🖼️ **{prompt}**\n"
                        f"💎 Баланс: {user['coins']} монет\n\n"
                        f"❤️ Поддержать: `{config.WALLET}`",
                reply_markup=get_back_keyboard()
            )
        
        os.remove("/tmp/image.png")
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка: {e}\n\n💡 Попробуй позже")

# =====================================================================
#                        ГЕНЕРАЦИЯ ТЕКСТОВ
# =====================================================================

async def generate_text(message: Message, prompt: str, mode: str, user_id: int):
    system_prompts = {
        "poem": f"Напиши красивое стихотворение на тему: {prompt}. Стих должен быть рифмованным, эмоциональным. Максимум 12 строк.",
        "post": f"Напиши пост для социальных сетей на тему: {prompt}. Пост должен быть интересным, вовлекающим. Длина: 5-8 предложений.",
        "ask": f"Ответь на вопрос: {prompt}. Ответ должен быть развернутым, полезным, дружелюбным. Длина: 3-5 предложений."
    }
    
    system_prompt = system_prompts.get(mode, system_prompts["ask"])
    
    wait_msg = await message.reply(f"🧠 Думаю...\n⏳ Подожди 3-5 секунд")
    
    try:
        url = f"https://text.pollinations.ai/{system_prompt.replace(' ', '%20')}"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        text = response.text.strip()
        
        if len(text) < 10:
            text = "Извини, не смог придумать. Попробуй перефразировать запрос."
        
        mode_names = {
            "poem": "📝 Стихотворение",
            "post": "📱 Пост для соцсетей",
            "ask": "🧠 Ответ на вопрос"
        }
        
        await message.reply(
            f"{mode_names.get(mode, '📝')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{text}\n\n"
            f"❤️ Поддержать: `{config.WALLET}`",
            reply_markup=get_back_keyboard()
        )
        
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка: {e}\n\n💡 Попробуй позже")

# =====================================================================
#                        ЗАПУСК
# =====================================================================

async def on_startup():
    logger.info(f"🚀 {BOT_NAME} v{VERSION} запущен!")
    logger.info(f"👑 Создатель: {config.CREATOR_ID}")
    logger.info(f"💰 Кошелёк: {config.WALLET}")
    await bot.delete_webhook(drop_pending_updates=True)

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    print(f"🚀 Запуск {BOT_NAME}...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
