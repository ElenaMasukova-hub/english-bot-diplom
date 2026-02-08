import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
import random
from config import TOKEN, DB_CONFIG

bot = telebot.TeleBot(TOKEN)
connection = psycopg2.connect(**DB_CONFIG)

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Тренировка"), KeyboardButton("Добавить слово"))
    markup.add(KeyboardButton("Мои слова"), KeyboardButton("Удалить слово"))
    markup.add(KeyboardButton("Статистика"))
    return markup

def training(chat_id):
    cur = connection.cursor()
    cur.execute("SELECT id, russian, english FROM user_words WHERE user_id = %s ORDER BY RANDOM() LIMIT 1", (chat_id,))
    result = cur.fetchone()
    
    if not result:
        cur.execute("SELECT id, russian, english FROM common_words ORDER BY RANDOM() LIMIT 1")
        result = cur.fetchone()
    
    cur.close()
    
    if result:
        word_id, russian, correct_english = result
        
        wrong_variants = ["table", "array", "server", "keyboard", "monitor", "mouse", "screen"]
        wrong_variants = [w for w in wrong_variants if w != correct_english]
        random.shuffle(wrong_variants)
        variants = wrong_variants[:3] + [correct_english]
        random.shuffle(variants)
        
        markup = InlineKeyboardMarkup()
        for variant in variants:
            markup.add(InlineKeyboardButton(variant, callback_data=f"ans_{word_id}_{variant}"))
        
        bot.send_message(
            chat_id,
            f"**Русское слово:** {russian}\n\nВыбери английский перевод:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    else:
        bot.send_message(chat_id, "Нет слов в базе!", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cur = connection.cursor()
    cur.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", 
                (user_id, message.from_user.username))
    connection.commit()
    cur.close()
    
    bot.send_message(
        message.chat.id,
        "Добро пожаловать! Изучай английский программирования:\n\n"
        "• Тренировка - случайное слово + 4 варианта\n"
        "• Добавить слово - сохрани своё слово\n"
        "• Мои слова - твои персональные слова\n"
        "• Удалить слово - удали своё слово\n\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "Тренировка")
def training_handler(message):
    training(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ans_'))
def check_answer(call):
    _, word_id, answer = call.data.split('_', 2)
    
    cur = connection.cursor()
    cur.execute("SELECT english, russian FROM user_words WHERE id = %s AND user_id = %s", 
                (word_id, call.from_user.id))
    result = cur.fetchone()
    
    if not result:
        cur.execute("SELECT english, russian FROM common_words WHERE id = %s", (word_id,))
        result = cur.fetchone()
    
    cur.close()
    
    if result:
        correct_word, russian = result
        
        if answer == correct_word:
            bot.answer_callback_query(call.id, "Правильно!")
            
            markup_continue = InlineKeyboardMarkup()
            markup_continue.add(InlineKeyboardButton("Да, продолжим!", callback_data="continue_training"))
            markup_continue.add(InlineKeyboardButton("Нет, в меню", callback_data="back_to_menu"))
            
            bot.send_message(
                call.message.chat.id,
                f"**{russian}** = **{correct_word}**\n\nПродолжим тренировку?",
                parse_mode='Markdown',
                reply_markup=markup_continue
            )
        else:
            bot.answer_callback_query(call.id, f"Нет: **{correct_word}**")
            
            markup_retry = InlineKeyboardMarkup()
            markup_retry.add(InlineKeyboardButton("Да, продолжим!", callback_data="continue_training"))
            markup_retry.add(InlineKeyboardButton("Нет, в меню", callback_data="back_to_menu"))
            
            bot.send_message(
                call.message.chat.id,
                f"**{russian}** = **{correct_word}** (не {answer})\n\nПопробуй ещё раз!",
                parse_mode='Markdown',
                reply_markup=markup_retry
            )
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "continue_training")
def continue_training(call):
    bot.answer_callback_query(call.id)
    training(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text == "Добавить слово")
def add_word(message):
    bot.send_message(
        message.chat.id,
        "Напиши слово в формате:\n`русское = english`\n\nПример: `клавиатура = keyboard`",
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )
    bot.register_next_step_handler(message, process_add_word)

def process_add_word(message):
    try:
        russian, english = [x.strip() for x in message.text.split('=', 1)]
        
        cur = connection.cursor()
        cur.execute("""
            INSERT INTO user_words (user_id, russian, english) 
            VALUES (%s, %s, %s)
        """, (message.from_user.id, russian, english))
        connection.commit()
        
        cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (message.from_user.id,))
        count = cur.fetchone()[0]
        cur.close()
        
        bot.send_message(
            message.chat.id,
            f"Добавлено: **{russian}** = **{english}**\n\nТы изучаешь **{count}** слов(а)",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    except Exception:
        bot.send_message(
            message.chat.id,
            "Неверный формат!\n`русское = english`\nПример: `клавиатура = keyboard`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        bot.register_next_step_handler(message, process_add_word)

@bot.message_handler(func=lambda m: m.text == "Мои слова")
def my_words(message):
    cur = connection.cursor()
    cur.execute("SELECT russian, english FROM user_words WHERE user_id = %s ORDER BY id DESC LIMIT 10", (message.from_user.id,))
    words = cur.fetchall()
    cur.close()
    
    if words:
        text = "Твои слова:\n\n"
        for russian, english in words:
            text += f"• **{russian}** = **{english}**\n"
        bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    else:
        bot.send_message(message.chat.id, "У тебя пока нет персональных слов.\nДобавь через 'Добавить слово'!", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text == "Удалить слово")
def delete_word(message):
    cur = connection.cursor()
    cur.execute("SELECT id, russian FROM user_words WHERE user_id = %s ORDER BY id DESC LIMIT 10", (message.from_user.id,))
    words = cur.fetchall()
    cur.close()
    
    if words:
        markup = InlineKeyboardMarkup()
        for word_id, russian in words:
            markup.add(InlineKeyboardButton(f"Удалить: {russian}", callback_data=f"del_{word_id}"))
        markup.add(InlineKeyboardButton("Отмена", callback_data="cancel_delete"))
        bot.send_message(message.chat.id, "Выбери слово для удаления:", reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "Нет слов для удаления!", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_word_confirm(call):
    word_id = int(call.data.split('_')[1])
    cur = connection.cursor()
    cur.execute("DELETE FROM user_words WHERE id = %s AND user_id = %s", (word_id, call.from_user.id))
    connection.commit()
    cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (call.from_user.id,))
    count = cur.fetchone()[0]
    cur.close()
    
    bot.answer_callback_query(call.id, "Слово удалено!")
    bot.send_message(
        call.message.chat.id,
        f"🗑️ Слово удалено!\n\nОсталось слов: **{count}**",
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_delete')
def cancel_delete(call):
    bot.answer_callback_query(call.id, "Отменено")
    bot.send_message(call.message.chat.id, "Удаление отменено!", reply_markup=get_main_keyboard())
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "Статистика")
def stats(message):
    cur = connection.cursor()
    cur.execute("SELECT COUNT(*) FROM common_words")
    common_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (message.from_user.id,))
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    cur.close()
    
    bot.send_message(
        message.chat.id,
        f"Статистика:\n\n"
        f"Общих слов: **{common_count}**\n"
        f"Твоих слов: **{user_count}**\n"
        f"Всего пользователей: **{users_count}**",
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработчик всех текстовых сообщений - показывает меню"""
    if message.text not in ["Тренировка", "Добавить слово", "Мои слова", "Удалить слово", "Статистика"]:
        bot.send_message(
            message.chat.id,
            "Добро пожаловать! Изучай английский программирования:\n\n"
            "• Тренировка - случайное слово + 4 варианта\n"
            "• Добавить слово - сохрани своё слово\n"
            "• Мои слова - твои персональные слова\n"
            "• Удалить слово - удали своё слово\n\n"
            "**Выбери действие из меню ниже:**",
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )


if __name__ == '__main__':
    print("VocabVoyage_bot запускается...")
    bot.polling(none_stop=True)