#!/usr/bin/env python3
# =====================================================================
#                    НЕЙРО-ХУДОЖНИК v2.3 (ПОЛНАЯ ВЕРСИЯ)
# =====================================================================

import asyncio
import os
import random
import logging
import requests
from datetime import datetime
from typing import Dict
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
    MAX_FREE: int = 10

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
VERSION = "2.3.0"
user_generations: Dict[int, int] = {}
user_text_generations: Dict[int, int] = {}
MAX_FREE_TEXT = 20

# =====================================================================
#                        КНОПКИ
# =====================================================================

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎨 Нарисовать", callback_data="draw"),
        InlineKeyboardButton("📝 Стих", callback_data="poem"),
        InlineKeyboardButton("📱 Пост", callback_data="post"),
        InlineKeyboardButton("🧠 Спросить", callback_data="ask"),
        InlineKeyboardButton("💰 Поддержать", callback_data="donate"),
        InlineKeyboardButton("📋 Команды", callback_data="help")
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="menu"))
    return keyboard

# =====================================================================
#                        ФУНКЦИЯ РАСПОЗНАВАНИЯ КОМАНД
# =====================================================================

def detect_command(text: str):
    if not text:
        return None, None
    
    lower_text = text.lower().strip()
    
    # ВСЕ ВАРИАНТЫ ОБРАЩЕНИЙ К БОТУ
    bot_names = ['фабле', 'фабл', 'фаблэ', 'fabler', 'fable', 'fabl', 'нейро', 'художник', 'бот', 'бро']
    
    # Проверяем, обращаются ли к боту
    is_called = False
    clean_text = lower_text
    
    for name in bot_names:
        if name in lower_text:
            is_called = True
            # Удаляем имя бота из текста
            clean_text = lower_text.replace(name, '').strip()
            break
    
    # Если не обратились к боту - игнорируем
    if not is_called:
        return None, None
    
    # Если после удаления имени ничего не осталось - отвечаем приветствием
    if not clean_text:
        return "hello", ""
    
    # Распознаем команды
    commands = {
        'нарисуй': ['нарисуй', 'рисуй', 'сгенерируй', 'ген', 'картинку', 'картинка', 'изображение', 'фото', 'макака', 'макаку', 'нарисуй'],
        'стих': ['стих', 'стихотворение', 'стихи', 'поэма', 'рифма'],
        'пост': ['пост', 'текст', 'сообщение', 'статья', 'запись'],
        'спроси': ['спроси', 'вопрос', 'ответ', 'скажи', 'расскажи', 'объясни', 'помоги', 'что', 'как', 'почему', 'где', 'когда', 'кто']
    }
    
    for cmd, variants in commands.items():
        for variant in variants:
            if clean_text.startswith(variant):
                prompt = clean_text[len(variant):].strip()
                return cmd, prompt
            if clean_text == variant:
                return cmd, ""
    
    # Если не распознали команду, но текст есть - отвечаем как на вопрос
    if len(clean_text) > 0:
        return "спроси", clean_text
    
    return None, None

# =====================================================================
#                        ОБРАБОТЧИКИ КОМАНД
# =====================================================================

@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    if user_id not in user_generations:
        user_generations[user_id] = 0
    if user_id not in user_text_generations:
        user_text_generations[user_id] = 0
    
    await message.reply(
        f"🎨 **{BOT_NAME}** v{VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✨ **Я умею:**\n"
        f"🎨 Рисовать картинки\n"
        f"📝 Писать стихи\n"
        f"📱 Создавать посты\n"
        f"🧠 Отвечать на вопросы\n\n"
        f"📊 **Бесплатно:** {config.MAX_FREE} картинок и {MAX_FREE_TEXT} текстов\n\n"
        f"💰 **Поддержать:** `{config.WALLET}`\n\n"
        f"📝 Просто напиши **Фабле** и что хочешь! 👇\n"
        f"Пример: `Фабле нарисуй закат`",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    await start_command(message)

@dp.message(Command("donate"))
async def donate_command(message: Message):
    await message.reply(
        f"❤️ **ПОДДЕРЖАТЬ ПРОЕКТ**\n\n"
        f"Если тебе нравится бот, можешь отправить донат:\n\n"
        f"💎 **TON Wallet:**\n"
        f"`{config.WALLET}`\n\n"
        f"💰 **Сумма любая!**\n"
        f"Спасибо за поддержку! 🙏",
        reply_markup=get_back_keyboard()
    )

@dp.callback_query(lambda c: True)
async def callback_handler(callback: types.CallbackQuery):
    data = callback.data
    
    if data == "menu":
        await callback.message.edit_text(
            f"🎨 **{BOT_NAME}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Напиши **Фабле** и что хочешь 👇",
            reply_markup=get_main_keyboard()
        )
        await callback.answer()
        return
    
    if data == "help":
        await callback.message.edit_text(
            f"📋 **ЧТО Я УМЕЮ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎨 **Нарисовать:**\n"
            f"`Фабле нарисуй закат`\n"
            f"`Фабле рисуй кота`\n\n"
            f"📝 **Написать стих:**\n"
            f"`Фабле стих о любви`\n\n"
            f"📱 **Создать пост:**\n"
            f"`Фабле пост о путешествиях`\n\n"
            f"🧠 **Спросить:**\n"
            f"`Фабле спроси как дела`\n\n"
            f"💰 **Поддержать:** /donate\n\n"
            f"📊 Бесплатно: {config.MAX_FREE} картинок, {MAX_FREE_TEXT} текстов",
            reply_markup=get_back_keyboard()
        )
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
    
    if data == "draw":
        await callback.message.edit_text(
            f"🎨 **НАРИСОВАТЬ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Напиши:\n"
            f"`Фабле нарисуй закат в горах`\n"
            f"`Фабле рисуй красивую девушку`\n\n"
            f"💡 Я пойму любой запрос!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "poem":
        await callback.message.edit_text(
            f"📝 **НАПИСАТЬ СТИХ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Напиши:\n"
            f"`Фабле стих о любви`\n"
            f"`Фабле стихи про осень`\n\n"
            f"💡 Я пойму любую тему!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "post":
        await callback.message.edit_text(
            f"📱 **СОЗДАТЬ ПОСТ**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Напиши:\n"
            f"`Фабле пост о путешествиях`\n"
            f"`Фабле текст для инстаграма`\n\n"
            f"💡 Я пойму любую тему!",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if data == "ask":
        await callback.message.edit_text(
            f"🧠 **ЗАДАТЬ ВОПРОС**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Напиши:\n"
            f"`Фабле спроси как дела`\n"
            f"`Фабле что такое любовь`\n\n"
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
    
    if user_id not in user_generations:
        user_generations[user_id] = 0
    if user_id not in user_text_generations:
        user_text_generations[user_id] = 0
    
    cmd, prompt = detect_command(text)
    
    # Если обратились к боту без команды
    if cmd == "hello":
        await message.reply(
            f"👋 Привет! Я {BOT_NAME} v{VERSION}\n\n"
            f"Напиши **Фабле** и что хочешь:\n"
            f"• `Фабле нарисуй закат` 🎨\n"
            f"• `Фабле стих о любви` 📝\n"
            f"• `Фабле пост о путешествиях` 📱\n"
            f"• `Фабле спроси как дела` 🧠\n\n"
            f"💰 Поддержать: `{config.WALLET}`",
            reply_markup=get_main_keyboard()
        )
        return
    
    if cmd == "нарисуй":
        if not prompt:
            await message.reply("❌ Напиши что нарисовать. Например: `Фабле нарисуй закат`", reply_markup=get_back_keyboard())
            return
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

# =====================================================================
#                        ГЕНЕРАЦИЯ КАРТИНОК
# =====================================================================

async def generate_image(message: Message, prompt: str, user_id: int):
    if user_generations[user_id] >= config.MAX_FREE:
        await message.reply(
            f"❌ Кончились бесплатные генерации ({config.MAX_FREE})\n\n"
            f"🎨 Хочешь ещё? Поддержи проект:\n"
            f"`{config.WALLET}`\n\n"
            f"❤️ После доната напиши /start и продолжай!",
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
        
        remaining = config.MAX_FREE - user_generations[user_id] - 1
        with open("/tmp/image.png", "rb") as f:
            await message.reply_photo(
                f,
                caption=f"🖼️ **{prompt}**\n"
                        f"📊 Осталось бесплатных: {remaining}\n\n"
                        f"❤️ Поддержать: `{config.WALLET}`",
                reply_markup=get_back_keyboard()
            )
        
        user_generations[user_id] += 1
        os.remove("/tmp/image.png")
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка: {e}\n\n💡 Попробуй позже или измени описание")

# =====================================================================
#                        ГЕНЕРАЦИЯ ТЕКСТОВ
# =====================================================================

async def generate_text(message: Message, prompt: str, mode: str, user_id: int):
    if user_text_generations[user_id] >= MAX_FREE_TEXT:
        await message.reply(
            f"❌ Кончились бесплатные тексты ({MAX_FREE_TEXT})\n\n"
            f"📝 Хочешь ещё? Поддержи проект:\n"
            f"`{config.WALLET}`\n\n"
            f"❤️ После доната напиши /start и продолжай!",
            reply_markup=get_back_keyboard()
        )
        return
    
    system_prompts = {
        "poem": f"Ты профессиональный поэт. Напиши красивое стихотворение на тему: {prompt}. Стих должен быть рифмованным, эмоциональным, с глубоким смыслом. Максимум 12 строк.",
        "post": f"Ты креативный копирайтер. Напиши пост для социальных сетей на тему: {prompt}. Пост должен быть интересным, вовлекающим, с вопросами к аудитории. Длина: 5-8 предложений.",
        "ask": f"Ты умный ассистент. Ответь на вопрос: {prompt}. Ответ должен быть развернутым, полезным, дружелюбным. Длина: 3-5 предложений."
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
        
        remaining = MAX_FREE_TEXT - user_text_generations[user_id] - 1
        await message.reply(
            f"{mode_names.get(mode, '📝')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{text}\n\n"
            f"📊 Осталось бесплатных: {remaining}\n"
            f"❤️ Поддержать: `{config.WALLET}`",
            reply_markup=get_back_keyboard()
        )
        
        user_text_generations[user_id] += 1
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка: {e}\n\n💡 Попробуй позже или измени запрос")

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
