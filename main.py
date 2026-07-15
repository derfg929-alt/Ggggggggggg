#!/usr/bin/env python3
# =====================================================================
#                    НЕЙРО-ХУДОЖНИК v3.1 (РАБОЧАЯ ВЕРСИЯ)
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
VERSION = "3.1.0"
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

@dp.message()
async def handle_messages(message: Message):
    if not message.text:
        return
    
    text = message.text.strip()
    user_id = message.from_user.id
    is_private = message.chat.type == "private"
    
    user = get_user(user_id)
    if not user:
        user = create_user(user_id, message.from_user.username)
    
    # ===== ОБРАБОТКА В ЛИЧКЕ (ОТВЕЧАЕТ НА ВСЁ) =====
    if is_private:
        lower_text = text.lower()
        
        if lower_text.startswith("нарисуй ") or lower_text.startswith("нарисуй") or lower_text.startswith("рисуй ") or lower_text.startswith("сгенерируй "):
            prompt = text[7:].strip() if lower_text.startswith("нарисуй ") else text[6:].strip() if lower_text.startswith("рисуй ") else text[12:].strip()
            if not prompt:
                await message.reply("❌ Напиши что нарисовать. Например: `нарисуй закат`", reply_markup=get_back_keyboard())
                return
            await generate_image(message, prompt, user_id)
            return
        
        if lower_text.startswith("стих "):
            prompt = text[5:].strip()
            if not prompt:
                await message.reply("❌ Напиши тему стиха. Например: `стих о любви`", reply_markup=get_back_keyboard())
                return
            await generate_text(message, prompt, "poem")
            return
        
        if lower_text.startswith("пост "):
            prompt = text[5:].strip()
            if not prompt:
                await message.reply("❌ Напиши тему поста. Например: `пост о путешествиях`", reply_markup=get_back_keyboard())
                return
            await generate_text(message, prompt, "post")
            return
        
        if lower_text.startswith("спроси "):
            prompt = text[7:].strip()
            if not prompt:
                await message.reply("❌ Напиши вопрос. Например: `спроси как дела`", reply_markup=get_back_keyboard())
                return
            await generate_text(message, prompt, "ask")
            return
        
        if lower_text in ["работа", "работать", "заработать"]:
            await work_action(message, user_id)
            return
        
        if lower_text in ["бонус", "ежедневный", "подарок"]:
            await bonus_action(message, user_id)
            return
        
        if lower_text in ["баланс", "монеты", "сколько"]:
            await balance_action(message, user_id)
            return
        
        if lower_text in ["рефералы", "пригласить", "друзья"]:
            await referrals_action(message, user_id)
            return
        
        # Если просто написали что-то в ЛС - отвечаем как на вопрос
        if len(text) > 0:
            await generate_text(message, text, "ask")
            return
    
    # ===== ОБРАБОТКА В ЧАТЕ (ОТВЕЧАЕТ ТОЛЬКО ПРИ УПОМИНАНИИ) =====
    else:
        lower_text = text.lower()
        
        # Проверяем упоминание бота
        bot_names = ['фабле', 'фабл', 'фаблэ', 'fabler', 'fable', 'fabl', 'нейро', 'художник', 'бот', '@fable_al_bot']
        
        is_called = False
        clean_text = lower_text
        
        for name in bot_names:
            if name in lower_text:
                is_called = True
                clean_text = lower_text.replace(name, '').strip()
                break
        
        if not is_called:
            return
        
        if not clean_text:
            await message.reply(
                f"👋 Я здесь! Напиши что хочешь.\n"
                f"Пример: `Фабле нарисуй закат`",
                reply_markup=get_main_keyboard()
            )
            return
        
        # Распознаём команду
        if clean_text.startswith("нарисуй ") or clean_text.startswith("нарисуй") or clean_text.startswith("рисуй "):
            prompt = text[7:].strip() if "нарисуй" in clean_text else text[6:].strip()
            if not prompt:
                await message.reply("❌ Напиши что нарисовать. Например: `Фабле нарисуй закат`", reply_markup=get_back_keyboard())
                return
            await generate_image(message, prompt, user_id)
            return
        
        if clean_text.startswith("стих "):
            prompt = text[5:].strip()
            if not prompt:
                await message.reply("❌ Напиши тему стиха. Например: `Фабле стих о любви`", reply_markup=get_back_keyboard())
                return
            await generate_text(message, prompt, "poem")
            return
        
        if clean_text.startswith("пост "):
            prompt = text[5:].strip()
            if not prompt:
                await message.reply("❌ Напиши тему поста. Например: `Фабле пост о путешествиях`", reply_markup=get_back_keyboard())
                return
            await generate_text(message, prompt, "post")
            return
        
        if clean_text.startswith("спроси "):
            prompt = text[7:].strip()
            if not prompt:
                await message.reply("❌ Напиши вопрос. Например: `Фабле спроси как дела`", reply_markup=get_back_keyboard())
                return
            await generate_text(message, prompt, "ask")
            return
        
        if clean_text in ["работа", "работать"]:
            await work_action(message, user_id)
            return
        
        if clean_text in ["бонус", "ежедневный"]:
            await bonus_action(message, user_id)
            return
        
        if clean_text in ["баланс", "монеты"]:
            await balance_action(message, user_id)
            return
        
        if clean_text in ["рефералы", "пригласить"]:
            await referrals_action(message, user_id)
            return
        
        # Если не распознали - отвечаем как на вопрос
        await generate_text(message, clean_text, "ask")

# =====================================================================
#                        ДЕЙСТВИЯ
# =====================================================================

async def work_action(message: Message, user_id: int):
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
            await message.reply(f"⏳ Подожди {minutes}мин {seconds}сек до следующей работы!", reply_markup=get_back_keyboard())
            return
    
    earnings = random.randint(10, 50)
    add_coins(user_id, earnings)
    user = get_user(user_id)
    
    await message.reply(
        f"💼 **РАБОТА ВЫПОЛНЕНА!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 +{earnings} монет!\n"
        f"💎 Баланс: {user['coins']} монет\n\n"
        f"💡 Следующая работа через 10 минут!",
        reply_markup=get_back_keyboard()
    )

async def bonus_action(message: Message, user_id: int):
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
            await message.reply(f"⏳ Бонус через {hours}ч {minutes}м!", reply_markup=get_back_keyboard())
            return
    
    add_coins(user_id, 50)
    user = get_user(user_id)
    
    await message.reply(
        f"🎁 **ЕЖЕДНЕВНЫЙ БОНУС!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 +50 монет!\n"
        f"💎 Баланс: {user['coins']} монет",
        reply_markup=get_back_keyboard()
    )

async def balance_action(message: Message, user_id: int):
    user = get_user(user_id)
    await message.reply(
        f"💰 **ТВОЙ БАЛАНС**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 Монет: **{user['coins']}**\n"
        f"🎨 Генераций: **{user['total_gens']}**\n"
        f"👥 Рефералов: **{user['ref_count']}**\n\n"
        f"💰 1 генерация = 50 монет",
        reply_markup=get_back_keyboard()
    )

async def referrals_action(message: Message, user_id: int):
    user = get_user(user_id)
    ref_code = get_ref_code(user_id)
    ref_link = f"https://t.me/{bot.username}?start=ref_{ref_code}"
    referrals = get_referrals(user_id)
    
    msg = f"👥 **ТВОИ РЕФЕРАЛЫ**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"🔗 **Твоя ссылка:**\n`{ref_link}`\n\n"
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
        msg += "📭 У тебя пока нет рефералов.\n💡 Пригласи друга и получи +50 монет!"
    
    await message.reply(msg, reply_markup=get_back_keyboard())

# =====================================================================
#                        ГЕНЕРАЦИЯ КАРТИНОК
# =====================================================================

async def generate_image(message: Message, prompt: str, user_id: int):
    user = get_user(user_id)
    
    if user["coins"] < COST_PER_IMAGE:
        await message.reply(
            f"❌ Недостаточно монет!\n"
            f"💰 Стоимость: {COST_PER_IMAGE} монет\n"
            f"💎 Баланс: {user['coins']} монет\n\n"
            f"💡 Заработай: `работа` или `бонус`",
            reply_markup=get_back_keyboard()
        )
        return
    
    wait_msg = await message.reply(f"🎨 Рисую: **{prompt[:50]}...**\n⏳ Подожди 5-10 секунд")
    
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=768"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open("/tmp/image.png", "wb") as f:
            f.write(response.content)
        
        remove_coins(user_id, COST_PER_IMAGE)
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

async def generate_text(message: Message, prompt: str, mode: str):
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
            f"💰 1 генерация = 50 монет",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "refs":
        await referrals_action(callback.message, user_id)
        await callback.answer()
        return
    
    if data == "bonus":
        await bonus_action(callback.message, user_id)
        await callback.answer()
        return
    
    if data == "work":
        await work_action(callback.message, user_id)
        await callback.answer()
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
            f"👥 Пригласить друга — +50 монет",
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
            f"Напиши: `Фабле нарисуй закат`",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "poem":
        await callback.message.edit_text(
            f"📝 **НАПИСАТЬ СТИХ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Бесплатно!\n\n"
            f"Напиши: `Фабле стих о любви`",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "post":
        await callback.message.edit_text(
            f"📱 **СОЗДАТЬ ПОСТ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 Бесплатно!\n\n"
            f"Напиши: `Фабле пост о путешествиях`",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "ask":
        await callback.message.edit_text(
            f"🧠 **ЗАДАТЬ ВОПРОС**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🧠 Бесплатно!\n\n"
            f"Напиши: `Фабле спроси как дела`",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return

# =====================================================================
#                        ЗАПУСК
# =====================================================================

async def on_startup():
    logger.info(f"🚀 {BOT_NAME} v{VERSION} запущен!")
    logger.info(f"👑 Создатель: {config.CREATOR_ID}")
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
