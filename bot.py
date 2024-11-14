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
    '''
    Используется функция invert_colors, которая применяет
    ImageOps.invert из PIL (Python Imaging Library) к изображению.
    '''
    return ImageOps.invert(image)

def convert_to_heatmap(image):
    '''
    Изображение преобразуется так, чтобы его цвета отображались в виде тепловой карты,
     от синего (холодные области) до красного (теплые области)
    '''
    return ImageOps.colorize(image.convert('L'), black='blue', white='red', mid='#984f4f', midpoint=127)

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
    image_FLIP_LEFT_RIGHT = types.InlineKeyboardButton("Зеркало горизонтали", callback_data="flip_left_right")
    image_FLIP_TOP_BOTTOM = types.InlineKeyboardButton("Зеркало по вертикали", callback_data="flip_top_bottom")
    heat_map_image = types.InlineKeyboardButton("Тепловая карта", callback_data="heat_map")
    keyboard.add(pixelate_btn, ascii_btn, change_ASCII, image_negative,
                 image_FLIP_LEFT_RIGHT, image_FLIP_TOP_BOTTOM,heat_map_image, row_width=2)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    '''    Определяет действия в ответ на выбор пользователя (например, пикселизация или ASCII-арт)
        и вызывает соответствующую функцию обработки.
    '''
    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Пикселизация вашего изображения...")
        maket_for_processing_image(call.message, "pixelate")
    elif call.data == "ascii":
        bot.answer_callback_query(call.id, "Преобразование вашего изображения в формат ASCII...")
        ascii_and_send(call.message)
    elif call.data == "change_ascii":
        msg = bot.send_message(call.message.chat.id, 'Введите набор символов')
        bot.register_next_step_handler(msg, ch_asc)
        get_options_keyboard()
    elif call.data == "invert_colors":
        bot.answer_callback_query(call.id, "Преобразование вашего изображения в негатив...")
        maket_for_processing_image(call.message, "inverted")
    elif call.data == "flip_left_right":
        bot.answer_callback_query(call.id, "Отражение вашего изображения по горизонтали...")
        maket_for_processing_image(call.message,"FLIP_TOP_BOTTOM")
    elif call.data == "flip_top_bottom":
        bot.answer_callback_query(call.id, "Отражение вашего изображения по горизонтали...")
        maket_for_processing_image(call.message, "FLIP_LEFT_RIGHT")
    elif call.data == "heat_map":
        bot.answer_callback_query(call.id, "Тепловая карта вашего изображения...")
        maket_for_processing_image(call.message, "heat_map")


def ch_asc(message):
    ''' присваивает новое значение набору символов, учавствуют только уникальные символы '''

    global ASCII_CHARS
    ASCII_CHARS = list(set(message.text))

def ascii_and_send(message):
    '''Преобразует изображение в ASCII-арт и отправляет результат в виде текстового сообщения.'''
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    ascii_art = image_to_ascii(image_stream)
    bot.send_message(message.chat.id, f"```\n{ascii_art}\n```", parse_mode="MarkdownV2")

def maket_for_processing_image(message, type_func):
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)

    if type_func == "heat_map":
        rez_image = convert_to_heatmap(image)
    if type_func == "FLIP_TOP_BOTTOM":
        rez_image = image.transpose(method=Image.Transpose.FLIP_TOP_BOTTOM)
    if type_func == "FLIP_LEFT_RIGHT":
        rez_image = image.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT)
    if type_func == "pixelate":
        rez_image = pixelate_image(image, 20)
    if type_func == "inverted":
        rez_image = invert_colors(image)

    output_stream = io.BytesIO()
    rez_image.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)

bot.polling(none_stop=True)
