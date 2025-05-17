import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from PIL import Image, ImageEnhance
import numpy as np
import uuid
import json
import io

API_TOKEN = "..." 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

with open("palettes.json", "r", encoding="utf-8") as f:
    PALETTES_LIST = json.load(f)

PALETTES = {item["fdata"]: item for item in PALETTES_LIST}

def get_palette_keyboard():
    buttons = [[InlineKeyboardButton(text=item["label"], callback_data=item["fdata"])] for item in PALETTES_LIST]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

class ProcessingState(StatesGroup):
    choosing_palette = State()
    choosing_mode = State()
    processing = State()

def map_to_palette(img_data, palette):
    height, width = img_data.shape[:2]
    for y in range(height):
        for x in range(width):
            old_pixel = img_data[y, x]
            new_pixel = min(palette, key=lambda color: np.linalg.norm(old_pixel - color))
            img_data[y, x] = new_pixel
    return img_data.astype(np.uint8)

def apply_effect(image, palette):
    image = image.convert("RGB")
    img_data = np.array(image)
    img_data = map_to_palette(img_data, palette)
    image = Image.fromarray(img_data)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.3)
    enhancer = ImageEnhance.Color(image)
    image = enhancer.enhance(1.3)
    return image

def pixelate(image, pixel_size):
    img_data = np.array(image)
    height, width = img_data.shape[:2]
    img_data_small = np.array(Image.fromarray(np.uint8(img_data)).resize((width // pixel_size, height // pixel_size), Image.NEAREST))
    img_data_pixelated = np.array(Image.fromarray(np.uint8(img_data_small)).resize((width, height), Image.NEAREST))
    return Image.fromarray(img_data_pixelated)

def process_image(image, apply_pixelate=False):
    image = apply_effect(image)
    if apply_pixelate:
        return pixelate(image, pixel_size=1)
    return image

def resize_image(image, max_size=1024):
    scale_factor = max_size / max(image.width, image.height)
    new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
    return image.resize(new_size, Image.LANCZOS)

@dp.message(CommandStart())
async def command_start_handler(message: Message):
    await message.reply("<b>Привет!</b>\nОтправь мне фото, и я его обработаю в одной из палитр.")

@dp.message(F.photo | F.document)
async def handle_photo(message: Message, state: FSMContext):
    allowed_mime = {"image/jpeg", "image/png"}
    allowed_ext = {".jpg", ".jpeg", ".png"}

    photo = None

    if message.photo:
        photo = message.photo[-1]
    elif message.document:
        if (
            message.document.mime_type in allowed_mime
            and any(message.document.file_name.lower().endswith(ext) for ext in allowed_ext)
        ):
            photo = message.document
        else:
            await message.reply("❌ Только изображения PNG, JPG, JPEG.")
            return

    if not photo:
        await message.reply("❌ Не удалось распознать изображение.")
        return

    await state.update_data(photo=photo)

    keyboard = get_palette_keyboard()

    sent_message = await message.reply("🎨 Выбери палитру:\n7 секунд до отмены!", reply_markup=keyboard)
    await state.update_data(sent_message_id=sent_message.message_id)
    await state.set_state(ProcessingState.choosing_palette)
    await asyncio.sleep(7)
    data = await state.get_data()
    if not data.get("palette"):
        await bot.delete_message(message.chat.id, sent_message.message_id)
        await state.clear()


@dp.callback_query(lambda c: c.data in PALETTES)
async def choose_palette(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(palette=callback.data)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard = [
            [InlineKeyboardButton(text="Быстрый", callback_data="fast")],
            [InlineKeyboardButton(text="Качественый", callback_data="quality")],
            [InlineKeyboardButton(text="Супер качественый", callback_data="super_quality")],
    
        ]
    )
    await callback.message.edit_text("<b>⚙️ Выбери режим обработки:</b>\n\n1. <b>Быстрый</b> - картинка сжимается и уменьшает свое разрешение (Быстрая обработка)\n2. <b>Качественный</b> - картинка не сжимается но уменьшает своё разрешение (Долгая обработка)\n3. <b>Супер качественный</b> - картинка не сжимается и не меняет своё разрешение (Очень долгая обработка)", reply_markup=keyboard)
    await state.set_state(ProcessingState.choosing_mode)

@dp.callback_query(F.data.in_({"fast", "quality", "super_quality"}))
async def choose_processing_mode(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo = data["photo"]
    mode = callback.data
    palette = PALETTES.get(data["palette"], PALETTES["advanced_milk"])["colors"]

    await callback.message.edit_text(f"⏳ Обрабатываю изображение в режиме {mode}...")
    file = await bot.get_file(photo.file_id)
    photo_file = await bot.download_file(file.file_path)
    image = Image.open(photo_file)

    if mode == "fast":
        image = resize_image(image)
    elif mode == "quality":
        image = resize_image(image)

    processed_image = await asyncio.to_thread(apply_effect, image, palette)
    output = io.BytesIO()
    if mode == "super_quality":
        processed_image.save(output, format='PNG')
    elif mode == "quality":
        processed_image.save(output, format='PNG')
    else:
        processed_image.save(output, format='JPEG', quality=75)
    output.seek(0)

    await callback.message.delete()
    filename = f"{uuid.uuid4()}_p.{'png' if mode=='quality' else 'jpeg'}"
    if mode == "super_quality":
        await callback.message.answer_document(types.BufferedInputFile(output.getvalue(), filename=filename))
    elif mode == "quality":
        await callback.message.answer_document(types.BufferedInputFile(output.getvalue(), filename=filename))
    else:
        await callback.message.answer_photo(types.BufferedInputFile(output.getvalue(), filename=filename))

    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown")