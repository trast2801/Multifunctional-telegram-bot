import telebot
from PIL import Image, ImageOps
import io
from telebot import types
import config

TOKEN = config.TOKEN

# TOKEN = '<token goes here>'

bot = telebot.TeleBot(TOKEN)

user_states = {}  # тут будем хранить информацию о действиях пользователя

# набор символов из которых составляем изображение
ASCII_CHARS = '@%#*+=-:. '


def resize_image(image, new_width=100):
    '''Изменяет размер изображения с сохранением пропорций.'''
    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))


def grayify(image):
    '''Преобразует цветное изображение в оттенки серого.'''
    return image.convert("L")

def invert_colors(image):
    '''Используется функция invert_colors, которая применяет
    ImageOps.invert из PIL (Python Imaging Library) к изображению.
    '''
    return ImageOps.invert(image)

def send_photo(message):
    '''Преобразует изображение в негатив и отправляет результат'''
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    inverted = invert_colors(image)

    output_stream = io.BytesIO()
    inverted.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)

def image_to_ascii(image_stream, new_width=40):
    '''
    Основная функция для преобразования изображения в ASCII-арт.
    Изменяет размер, преобразует в градации серого и затем в строку ASCII-символов.
    '''
    # Переводим в оттенки серого'''
    image = Image.open(image_stream).convert('L')

    # меняем размер сохраняя отношение сторон
    width, height = image.size
    aspect_ratio = height / float(width)
    new_height = int(
        aspect_ratio * new_width * 0.55)  # 0,55 так как буквы выше чем шире
    img_resized = image.resize((new_width, new_height))

    img_str = pixels_to_ascii(img_resized)
    img_width = img_resized.width

    max_characters = 4000 - (new_width + 1)
    max_rows = max_characters // (new_width + 1)

    ascii_art = ""
    for i in range(0, min(max_rows * img_width, len(img_str)), img_width):
        ascii_art += img_str[i:i + img_width] + "\n"

    return ascii_art


def pixels_to_ascii(image):
    """Конвертирует пиксели изображения в градациях серого в строку ASCII-символов,
    используя предопределенную строку ASCII_CHARS
    """
    pixels = image.getdata()
    characters = ""
    for pixel in pixels:
        characters += ASCII_CHARS[pixel * len(ASCII_CHARS) // 256]
    return characters


# Огрубляем изображение
def pixelate_image(image, pixel_size):
    '''- Принимает изображение и размер пикселя. Уменьшает изображение до размера,
    где один пиксель представляет большую область, затем увеличивает обратно, создавая пиксельный эффек'''
    image = image.resize(
        (image.size[0] // pixel_size, image.size[1] // pixel_size),
        Image.NEAREST
    )
    image = image.resize(
        (image.size[0] * pixel_size, image.size[1] * pixel_size),
        Image.NEAREST
    )
    return image


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Пришлите мне изображение, и я предложу вам варианты")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.reply_to(message, "У меня есть ваша фотография! Пожалуйста, выберите, что бы вы хотели с ней сделать.",
                 reply_markup=get_options_keyboard())
    user_states[message.chat.id] = {'photo': message.photo[-1].file_id}


def get_options_keyboard():
    '''вывод меню для выбора режима обработки изображения пользователем'''
    keyboard = types.InlineKeyboardMarkup()
    pixelate_btn = types.InlineKeyboardButton("Pixelate", callback_data="pixelate")
    ascii_btn = types.InlineKeyboardButton("ASCII Art", callback_data="ascii")
    change_ASCII = types.InlineKeyboardButton("Сменить набор ASCII", callback_data="change_ascii")
    image_negative = types.InlineKeyboardButton("Получить Негатив", callback_data="invert_colors")
    image_FLIP_LEFT_RIGHT = types.InlineKeyboardButton("Зеркало горизонт", callback_data="flip_left_right")
    image_FLIP_TOP_BOTTOM = types.InlineKeyboardButton("Зеркало по вертикаль", callback_data="flip_top_bottom")
    keyboard.add(pixelate_btn, ascii_btn, change_ASCII, image_negative,
                 image_FLIP_LEFT_RIGHT,image_FLIP_TOP_BOTTOM, row_width=2)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    '''    Определяет действия в ответ на выбор пользователя (например, пикселизация или ASCII-арт)
        и вызывает соответствующую функцию обработки.
    '''
    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Пикселизация вашего изображения...")
        pixelate_and_send(call.message)
    elif call.data == "ascii":
        bot.answer_callback_query(call.id, "Преобразование вашего изображения в формат ASCII...")
        ascii_and_send(call.message)
    elif call.data == "change_ascii":
        msg = bot.send_message(call.message.chat.id, 'Введите набор символов')
        bot.register_next_step_handler(msg, ch_asc)
        get_options_keyboard()
    elif call.data == "invert_colors":
        bot.answer_callback_query(call.id, "Преобразование вашего изображения в негатив...")
        send_photo(call.message)
    elif call.data == "flip_left_right":
        bot.answer_callback_query(call.id, "Отражение вашего изображения по горизонтали...")
        mirror_image(call.message,rotate="FLIP_TOP_BOTTOM")
    elif call.data == "flip_top_bottom":
        bot.answer_callback_query(call.id, "Отражение вашего изображения по горизонтали...")
        mirror_image(call.message,rotate="FLIP_LEFT_RIGHT")

def ch_asc(message):
    ''' присваивает новое значение набору символов, учавствуют только уникальные символы '''

    global ASCII_CHARS
    ASCII_CHARS = message.text
    print(f'перед {ASCII_CHARS}')
    ASCII_CHARS = list(set(ASCII_CHARS))
    print(f'после {ASCII_CHARS}')


def pixelate_and_send(message):
    '''Пикселизирует изображение и отправляет его обратно пользователю'''
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    pixelated = pixelate_image(image, 20)

    output_stream = io.BytesIO()
    pixelated.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


def ascii_and_send(message):
    '''Преобразует изображение в ASCII-арт и отправляет результат в виде текстового сообщения.'''
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    ascii_art = image_to_ascii(image_stream)
    bot.send_message(message.chat.id, f"```\n{ascii_art}\n```", parse_mode="MarkdownV2")

def mirror_image(message, rotate):
    '''Создает отраженную копию изображения по горизонтали или вертикали.'''
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)

    if rotate == "FLIP_TOP_BOTTOM":
        image_inverted = image.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
    elif rotate == "FLIP_LEFT_RIGHT":
        image_inverted = image.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT)

    output_stream = io.BytesIO()
    image_inverted.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)

bot.polling(none_stop=True)
