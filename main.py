#!/usr/bin/env python3
# =====================================================================
#                    НЕЙРО-ХУДОЖНИК v2.0 (ПОЛНАЯ ВЕРСИЯ)
# =====================================================================

import asyncio
import os
import re
import random
import logging
import json
import requests
from datetime import datetime
from typing import Optional, Dict, List
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
VERSION = "2.0.0"
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

def detect_command(text: str) -> tuple:
    """Распознает команду в любом регистре и с сокращениями"""
    if not text:
        return None, None
    
    # Приводим к нижнему регистру для проверки
    lower_text = text.lower().strip()
    
    # Словари команд и их синонимов
    commands = {
        'нарисуй': ['нарисуй', 'нарисуй', 'рисуй', 'сгенерируй', 'ген', 'сделай картинку', 'картинку', 'картинка', 'изображение', 'фото'],
        'стих': ['стих', 'стихотворение', 'стихи', 'поэма', 'рифма', 'поэзия'],
        'пост': ['пост', 'текст', 'сообщение', 'статья', 'запись', 'постик'],
        'спроси': ['спроси', 'вопрос', 'ответ', 'скажи', 'расскажи', 'объясни', 'помоги', 'что', 'как', 'почему', 'где', 'когда', 'кто']
    }
    
    # Проверяем начало сообщения
    for cmd, variants in commands.items():
        for variant in variants:
            if lower_text.startswith(variant + ' '):
                # Удаляем команду из текста
                prompt = text[len(variant):].strip()
                return cmd, prompt
            if lower_text == variant:
                return cmd, ""
    
    # Проверяем вхождение команды в текст
    for cmd, variants in commands.items():
        for variant in variants:
            if variant in lower_text:
                # Находим позицию команды
                idx = lower_text.find(variant)
                prompt = text[idx + len(variant):].strip()
                return cmd, prompt
    
    # Проверяем короткие команды (1-2 слова)
    words = lower_text.split()
    if len(words) <= 5:
        for cmd, variants in commands.items():
            for variant in variants:
                if variant in words:
                    return cmd, " ".join(words)
    
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
        f"📝 Пиши что хочешь - я пойму! 👇",
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

@dp.callback_query(lambda c: c.data == "menu")
async def menu_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"🎨 **{BOT_NAME}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Выбери действие или просто напиши 👇",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "help")
async def help_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"📋 **ЧТО Я УМЕЮ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎨 **Нарисовать:**\n"
        f"`нарисуй закат`\n"
        f"`рисуй кота`\n"
        f"`картинку горы`\n\n"
        f"📝 **Написать стих:**\n"
        f"`стих о любви`\n"
        f"`стихи про осень`\n\n"
        f"📱 **Создать пост:**\n"
        f"`пост о путешествиях`\n"
        f"`текст для инстаграма`\n\n"
        f"🧠 **Спросить:**\n"
        f"`спроси как дела`\n"
        f"`что такое любовь`\n\n"
        f"💰 **Поддержать:** /donate\n\n"
        f"📊 Бесплатно: {config.MAX_FREE} картинок, {MAX_FREE_TEXT} текстов",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "donate")
async def donate_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"❤️ **ПОДДЕРЖАТЬ ПРОЕКТ**\n\n"
        f"Если тебе нравится бот, можешь отправить донат:\n\n"
        f"💎 **TON Wallet:**\n"
        f"`{config.WALLET}`\n\n"
        f"💰 **Сумма любая!**\n"
        f"Спасибо за поддержку! 🙏",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "draw")
async def draw_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"🎨 **НАРИСОВАТЬ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Просто напиши:\n"
        f"`нарисуй закат в горах`\n"
        f"`рисуй красивую девушку`\n"
        f"`картинку космос`\n\n"
        f"💡 Я пойму любой запрос!",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "poem")
async def poem_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"📝 **НАПИСАТЬ СТИХ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Просто напиши:\n"
        f"`стих о любви`\n"
        f"`стихи про осень`\n"
        f"`поэма о дружбе`\n\n"
        f"💡 Я пойму любую тему!",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "post")
async def post_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"📱 **СОЗДАТЬ ПОСТ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Просто напиши:\n"
        f"`пост о путешествиях`\n"
        f"`текст для инстаграма`\n"
        f"`сообщение для телеграм`\n\n"
        f"💡 Я пойму любую тему!",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "ask")
async def ask_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"🧠 **ЗАДАТЬ ВОПРОС**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Просто напиши:\n"
        f"`спроси как дела`\n"
        f"`что такое любовь`\n"
        f"`расскажи о космосе`\n\n"
        f"💡 Я пойму любой вопрос!",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

# =====================================================================
#                        ОБРАБОТЧИК СООБЩЕНИЙ
# =====================================================================

@dp.message()
async def handle_messages(message: Message):
    """Обработка всех сообщений"""
    if not message.text:
        return
    
    text = message.text.strip()
    user_id = message.from_user.id
    
    if user_id not in user_generations:
        user_generations[user_id] = 0
    if user_id not in user_text_generations:
        user_text_generations[user_id] = 0
    
    # Распознаем команду
    cmd, prompt = detect_command(text)
    
    if cmd == "нарисуй":
        if not prompt:
            await message.reply("❌ Напиши что нарисовать. Например: `нарисуй красивый закат`", reply_markup=get_back_keyboard())
            return
        await generate_image(message, prompt, user_id)
        return
    
    if cmd == "стих":
        if not prompt:
            await message.reply("❌ Напиши тему стиха. Например: `стих о любви`", reply_markup=get_back_keyboard())
            return
        await generate_text(message, prompt, "poem", user_id)
        return
    
    if cmd == "пост":
        if not prompt:
            await message.reply("❌ Напиши тему поста. Например: `пост о путешествиях`", reply_markup=get_back_keyboard())
            return
        await generate_text(message, prompt, "post", user_id)
        return
    
    if cmd == "спроси":
        if not prompt:
            await message.reply("❌ Напиши вопрос. Например: `спроси как дела`", reply_markup=get_back_keyboard())
            return
        await generate_text(message, prompt, "ask", user_id)
        return
    
    # Если не распознали команду, но сообщение короткое - пробуем как вопрос
    if len(text.split()) <= 10 and not text.startswith('/'):
        await generate_text(message, text, "ask", user_id)
        return

# =====================================================================
#                        ГЕНЕРАЦИЯ КАРТИНОК
# =====================================================================

async def generate_image(message: Message, prompt: str, user_id: int):
    """Генерация картинки через Pollinations.ai"""
    
    if user_generations[user_id] >= config.MAX_FREE:
        await message.reply(
            f"❌ Кончились бесплатные генерации ({config.MAX_FREE})\n\n"
            f"🎨 Хочешь ещё? Поддержи проект:\n"
            f"`{config.WALLET}`\n\n"
            f"❤️ После доната напиши `/start`",
            reply_markup=get_back_keyboard()
        )
        return
    
    wait_msg = await message.reply(f"🎨 Рисую: **{prompt[:50]}...**\n⏳ Подожди 5-10 секунд")
    
    try:
        styles = ["", "?model=flux", "?model=realistic", "?model=anime", "?model=fantasy"]
        style = random.choice(styles)
        
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}{style}&width=1024&height=768"
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open("/tmp/image.png", "wb") as f:
            f.write(response.content)
        
        remaining = config.MAX_FREE - user_generations[user_id] - 1
        with open("/tmp/image.png", "rb") as f:
            await message.reply_photo(
                f,
                caption=f"🖼️ **{prompt}**\n"
                        f"📊 Осталось: {remaining}\n\n"
                        f"❤️ Поддержать: `{config.WALLET}`",
                reply_markup=get_back_keyboard()
            )
        
        user_generations[user_id] += 1
        os.remove("/tmp/image.png")
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка: {e}\n\n💡 Попробуй позже")

# =====================================================================
#                        ГЕНЕРАЦИЯ ТЕКСТОВ
# =====================================================================

async def generate_text(message: Message, prompt: str, mode: str, user_id: int):
    """Генерация текста через Pollinations.ai"""
    
    if user_text_generations[user_id] >= MAX_FREE_TEXT:
        await message.reply(
            f"❌ Кончились бесплатные тексты ({MAX_FREE_TEXT})\n\n"
            f"📝 Хочешь ещё? Поддержи проект:\n"
            f"`{config.WALLET}`\n\n"
            f"❤️ После доната напиши `/start`",
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
        url = f"https://text.pollinations.ai/{system_prompt.replace(' ', '%20')}?model=openai"
        
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
            f"📊 Осталось: {remaining}\n"
            f"❤️ Поддержать: `{config.WALLET}`",
            reply_markup=get_back_keyboard()
        )
        
        user_text_generations[user_id] += 1
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
      
