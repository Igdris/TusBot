import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, 
    CallbackQueryHandler, CallbackContext, Filters
)

# ========== КОНФИГУРАЦИЯ ==========
# Используем переменную окружения, если есть, иначе тестовый токен
TOKEN = os.environ.get('BOT_TOKEN', '8032006876:AAE4b7z902XbYYQQ8VIW2J7kmIHTu8zVkO8')
# ==================================

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КЛАСС DATABASE ==========
class Database:
    def __init__(self, db_name: str = 'movies.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()
        print(f"База данных {db_name} создана/подключена")
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'want_to_watch',
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                watched_date TIMESTAMP,
                is_public BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        self.conn.commit()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?)
        ''', (user_id, username or '', first_name or ''))
        self.conn.commit()
    
    def add_movie(self, user_id: int, title: str, is_public: bool = True):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO movies (user_id, title, is_public) VALUES (?, ?, ?)
        ''', (user_id, title, 1 if is_public else 0))
        self.conn.commit()
        movie_id = cursor.lastrowid
        print(f"Добавлен фильм: ID={movie_id}, пользователь={user_id}, название={title}, публичный={'Да' if is_public else 'Нет'}")
        return movie_id
    
    def get_movies(self, user_id: int, status: str = 'want_to_watch', show_private: bool = True):
        cursor = self.conn.cursor()
        
        if show_private:
            cursor.execute('''
                SELECT id, title, added_date FROM movies 
                WHERE user_id = ? AND status = ? 
                ORDER BY added_date DESC
            ''', (user_id, status))
        else:
            cursor.execute('''
                SELECT id, title, added_date FROM movies 
                WHERE user_id = ? AND status = ? AND is_public = 1
                ORDER BY added_date DESC
            ''', (user_id, status))
        
        movies = []
        for row in cursor.fetchall():
            movies.append({
                'id': row[0],
                'title': row[1],
                'added_date': row[2]
            })
        return movies
    
    def mark_as_watched(self, user_id: int, movie_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE movies 
            SET status = 'watched', watched_date = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ?
        ''', (movie_id, user_id))
        self.conn.commit()
        success = cursor.rowcount > 0
        print(f"Отметка как просмотренный: ID={movie_id}, успех={success}")
        return success
    
    def delete_movie(self, user_id: int, movie_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM movies WHERE id = ? AND user_id = ?
        ''', (movie_id, user_id))
        self.conn.commit()
        success = cursor.rowcount > 0
        print(f"Удаление фильма: ID={movie_id}, успех={success}")
        return success
    
    def get_movie_by_id(self, user_id: int, movie_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, status, is_public FROM movies 
            WHERE id = ? AND user_id = ?
        ''', (movie_id, user_id))
        
        row = cursor.fetchone()
        if row:
            return {'id': row[0], 'title': row[1], 'status': row[2], 'is_public': row[3]}
        return None
    
    def get_all_movies(self, user_id: int, show_private: bool = True):
        cursor = self.conn.cursor()
        
        if show_private:
            cursor.execute('''
                SELECT id, title, status, added_date, is_public FROM movies 
                WHERE user_id = ? 
                ORDER BY added_date DESC
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT id, title, status, added_date, is_public FROM movies 
                WHERE user_id = ? AND is_public = 1
                ORDER BY added_date DESC
            ''', (user_id,))
        
        movies = []
        for row in cursor.fetchall():
            movies.append({
                'id': row[0],
                'title': row[1],
                'status': row[2],
                'added_date': row[3],
                'is_public': row[4]
            })
        return movies
    
    def get_all_public_movies(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT m.id, m.title, m.status, m.added_date, m.watched_date, 
                   u.user_id, u.username, u.first_name 
            FROM movies m
            LEFT JOIN users u ON m.user_id = u.user_id
            WHERE m.is_public = 1
            ORDER BY m.added_date DESC
        ''')
        
        movies = []
        for row in cursor.fetchall():
            movies.append({
                'id': row[0],
                'title': row[1],
                'status': row[2],
                'added_date': row[3],
                'watched_date': row[4],
                'user_id': row[5],
                'username': row[6],
                'first_name': row[7]
            })
        return movies
    
    def toggle_movie_privacy(self, user_id: int, movie_id: int):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT is_public FROM movies 
            WHERE id = ? AND user_id = ?
        ''', (movie_id, user_id))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        current_state = row[0]
        new_state = 0 if current_state else 1
        
        cursor.execute('''
            UPDATE movies 
            SET is_public = ? 
            WHERE id = ? AND user_id = ?
        ''', (new_state, movie_id, user_id))
        self.conn.commit()
        
        success = cursor.rowcount > 0
        if success:
            print(f"Изменена приватность фильма: ID={movie_id}, новый статус={'публичный' if new_state else 'приватный'}")
        return new_state if success else None

# Инициализация базы данных
db = Database()

# ========== КОМАНДЫ БОТА ==========
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
🎬 Привет, {user.first_name}!

Я бот для управления списком фильмов.

👁️ **ВАЖНО:** Все добавляемые фильмы видны всем пользователям в публичном списке!

📌 **Как пользоваться:**
1. Просто отправь мне название фильма
2. Я добавлю его в список "Хочу посмотреть" (и в публичный список)
3. После просмотра нажми кнопку "✅ Просмотрен"
4. Чтобы скрыть фильм от других, используйте /private <ID_фильма>

📋 **Команды:**
/add <название> - добавить фильм (автоматически публичный)
/my_movies - показать мои списки
/watched - показать просмотренные
/public - показать общий публичный список
/private <ID> - скрыть фильм от других (сделать приватным)
/help - показать справку

🎥 **Начни прямо сейчас - напиши название фильма!**
    """
    
    update.message.reply_text(welcome_text)

def help_command(update: Update, context: CallbackContext):
    help_text = """
📋 **Доступные команды:**

🎬 **Основные:**
/start - начать работу с ботом
/add <название> - добавить фильм в список (публичный по умолчанию)
/my_movies - показать все мои списки
/watched - показать только просмотренные фильмы
/public - показать общий публичный список фильмов
/private <ID> - скрыть фильм от других пользователей

👁️ **О публичных фильмах:**
• Все добавленные фильмы видны всем пользователям
• Используйте /private <ID> чтобы скрыть фильм
• Повторный /private <ID> сделает фильм снова публичным

🗑️ **Удаление фильмов:**
- Нажмите кнопку "🗑️ Удалить" под любым фильмом
- Можно удалять как из "Хочу посмотреть", так и из "Просмотренных"
    """
    
    update.message.reply_text(help_text)

def add_movie(update: Update, context: CallbackContext):
    user = update.effective_user
    
    if context.args:
        title = ' '.join(context.args)
    else:
        title = update.message.text
    
    if not title or len(title.strip()) == 0:
        update.message.reply_text("📝 Пожалуйста, укажите название фильма.\nНапример: /add Инцепция")
        return
    
    title = title.strip()
    movie_id = db.add_movie(user.id, title)
    
    keyboard = [
        [
            InlineKeyboardButton("📋 Мои списки", callback_data='show_lists'),
            InlineKeyboardButton("✅ Просмотрен", callback_data=f'watch_{movie_id}')
        ],
        [
            InlineKeyboardButton("🗑️ Удалить", callback_data=f'delete_{movie_id}')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"✅ Фильм \"{title}\" добавлен в список 'Хочу посмотреть'!\n"
        f"👁️ *Фильм виден всем пользователям в публичном списке*\n\n"
        f"После просмотра нажми кнопку '✅ Просмотрен'",
        reply_markup=reply_markup
    )

def show_my_movies(update: Update, context: CallbackContext):
    user = update.effective_user
    
    want_to_watch = db.get_movies(user.id, 'want_to_watch')
    watched = db.get_movies(user.id, 'watched')
    
    text = "🎬 **Ваши списки фильмов**\n\n"
    
    text += "📝 **Хочу посмотреть:**\n"
    if want_to_watch:
        for i, movie in enumerate(want_to_watch[:15], 1):
            text += f"{i}. {movie['title']}\n"
        if len(want_to_watch) > 15:
            text += f"... и еще {len(want_to_watch) - 15} фильмов\n"
    else:
        text += "Список пуст. Добавьте первый фильм!\n"
    
    text += "\n✅ **Просмотренные:**\n"
    if watched:
        for i, movie in enumerate(watched[:10], 1):
            text += f"{i}. {movie['title']}\n"
        if len(watched) > 10:
            text += f"... и еще {len(watched) - 10} фильмов\n"
    else:
        text += "Список пуст. Посмотрите первый фильм!\n"
    
    text += f"\n📊 **Статистика:**\n"
    text += f"• Хочу посмотреть: {len(want_to_watch)} фильмов\n"
    text += f"• Просмотрено: {len(watched)} фильмов\n"
    text += f"• Всего: {len(want_to_watch) + len(watched)} фильмов"
    
    keyboard = []
    
    if want_to_watch:
        for movie in want_to_watch[:5]:
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Отметить '{movie['title'][:20]}...'", 
                    callback_data=f'watch_{movie["id"]}'
                )
            ])
    
    if watched:
        for movie in watched[:5]:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ Удалить '{movie['title'][:20]}...'", 
                    callback_data=f'delete_{movie["id"]}'
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить фильм", callback_data='add_new_movie')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    update.message.reply_text(text, reply_markup=reply_markup)

def show_watched(update: Update, context: CallbackContext):
    user = update.effective_user
    watched = db.get_movies(user.id, 'watched')
    
    text = "✅ **Просмотренные фильмы:**\n\n"
    
    if watched:
        for i, movie in enumerate(watched, 1):
            date_str = movie['added_date'][:10] if movie['added_date'] else "дата неизвестна"
            text += f"{i}. {movie['title']} ({date_str})\n"
    else:
        text += "Пока нет просмотренных фильмов.\n"
        text += "Добавьте фильм командой /add и отметьте его как просмотренный!"
    
    text += f"\n📊 Всего просмотрено: {len(watched)} фильмов"
    
    keyboard = []
    
    if watched:
        for movie in watched[:5]:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ Удалить '{movie['title'][:20]}...'", 
                    callback_data=f'delete_{movie["id"]}'
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton("📋 Все списки", callback_data='show_lists'),
        InlineKeyboardButton("🎬 Все фильмы", callback_data='all_movies')
    ])
    
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def show_all_movies(update: Update, context: CallbackContext = None, query=None, user_id=None):
    if user_id is None and update:
        user_id = update.effective_user.id
    
    all_movies = db.get_all_movies(user_id)
    
    text = "🎬 **Все ваши фильмы:**\n\n"
    
    if all_movies:
        want_count = 0
        watched_count = 0
        
        for i, movie in enumerate(all_movies[:20], 1):
            status_icon = "✅" if movie['status'] == 'watched' else ""
            privacy_icon = "👁️" if movie['is_public'] else "🔒"
            date_str = movie['added_date'][:10] if movie['added_date'] else ""
            
            text += f"{i}. {privacy_icon} {movie['title']}"
            if status_icon:
                text += f" {status_icon}"
            if date_str:
                text += f" ({date_str})"
            text += "\n"
            
            if movie['status'] == 'watched':
                watched_count += 1
            else:
                want_count += 1
        
        if len(all_movies) > 20:
            text += f"\n... и еще {len(all_movies) - 20} фильмов\n"
    
    else:
        text += "У вас пока нет фильмов.\n"
        text += "Добавьте первый фильм командой /add или просто напишите его название!"
    
    want_count = len(db.get_movies(user_id, 'want_to_watch'))
    watched_count = len(db.get_movies(user_id, 'watched'))
    
    text += f"\n📊 **Статистика:**\n"
    text += f"• Всего: {want_count + watched_count} фильмов\n"
    text += f"• Хочу посмотреть: {want_count}\n"
    text += f"• Просмотрено: {watched_count}"
    
    keyboard = [
        [
            InlineKeyboardButton("📋 К спискам", callback_data='show_lists'),
            InlineKeyboardButton("✅ Просмотренные", callback_data='watched_only')
        ],
        [
            InlineKeyboardButton("➕ Добавить фильм", callback_data='add_new_movie')
        ]
    ]
    
    if query:
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update:
        update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def show_public_movies(update: Update, context: CallbackContext):
    all_public_movies = db.get_all_public_movies()
    
    text = "🎬 **Общий публичный список фильмов**\n\n"
    text += "👁️ *Все фильмы здесь видны всем пользователям*\n\n"
    
    if all_public_movies:
        user_stats = {}
        
        for movie in all_public_movies[:50]:
            user_key = f"{movie['first_name'] or 'Аноним'}"
            if user_key not in user_stats:
                user_stats[user_key] = {'total': 0, 'want': 0, 'watched': 0}
            
            user_stats[user_key]['total'] += 1
            if movie['status'] == 'watched':
                user_stats[user_key]['watched'] += 1
            else:
                user_stats[user_key]['want'] += 1
        
        for user_name, stats in user_stats.items():
            if stats['total'] > 0:
                text += f"👤 **{user_name}** (всего: {stats['total']})\n"
                if stats['want'] > 0:
                    text += f"  📝 Хочет посмотреть: {stats['want']}\n"
                if stats['watched'] > 0:
                    text += f"  ✅ Просмотрено: {stats['watched']}\n"
                text += "\n"
        
        text += "📅 **Последние добавленные фильмы:**\n"
        recent_movies = all_public_movies[:10]
        for i, movie in enumerate(recent_movies, 1):
            status_icon = "✅" if movie['status'] == 'watched' else "📝"
            user_name = movie['first_name'] or 'Аноним'
            text += f"{i}. {status_icon} {movie['title']} (от {user_name})\n"
            
    else:
        text += "Пока никто не добавил публичные фильмы.\n"
        text += "Все добавленные фильмы автоматически становятся публичными!"
    
    want_count = sum(1 for m in all_public_movies if m['status'] != 'watched')
    watched_count = sum(1 for m in all_public_movies if m['status'] == 'watched')
    
    text += f"\n📊 **Общая статистика публичных фильмов:**\n"
    text += f"• Всего фильмов: {len(all_public_movies)}\n"
    text += f"• Хотят посмотреть: {want_count}\n"
    text += f"• Уже просмотрено: {watched_count}\n"
    text += f"• Участников: {len(set(m['user_id'] for m in all_public_movies))}"
    
    keyboard = [
        [
            InlineKeyboardButton("📋 Мои фильмы", callback_data='show_lists'),
            InlineKeyboardButton("➕ Добавить фильм", callback_data='add_new_movie')
        ]
    ]
    
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def toggle_privacy(update: Update, context: CallbackContext):
    user = update.effective_user
    
    if not context.args:
        update.message.reply_text(
            "📝 Использование: /private <ID_фильма>\n\n"
            "Пример: /private 5\n\n"
            "Чтобы узнать ID фильма, используйте /my_movies"
        )
        return
    
    try:
        movie_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ ID фильма должен быть числом!")
        return
    
    movie = db.get_movie_by_id(user.id, movie_id)
    if not movie:
        update.message.reply_text("❌ Фильм не найден или у вас нет доступа к нему!")
        return
    
    new_state = db.toggle_movie_privacy(user.id, movie_id)
    
    if new_state is not None:
        status_text = "публичным" if new_state else "приватным"
        update.message.reply_text(
            f"✅ Фильм \"{movie['title']}\" теперь {status_text}!\n\n"
            f"📝 Статус: {'👁️ Публичный' if new_state else '🔒 Приватный'}"
        )
    else:
        update.message.reply_text("❌ Не удалось изменить приватность фильма.")

# ========== ОБРАБОТКА КНОПОК ==========
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    user = update.effective_user
    data = query.data
    
    print(f"Нажата кнопка: {data}, пользователь: {user.id}")
    
    if data == 'show_lists':
        show_lists_menu(query, user.id)
    
    elif data.startswith('watch_'):
        movie_id = int(data.split('_')[1])
        success = db.mark_as_watched(user.id, movie_id)
        
        if success:
            movie = db.get_movie_by_id(user.id, movie_id)
            if movie:
                keyboard = [
                    [
                        InlineKeyboardButton("📋 К спискам", callback_data='show_lists'),
                        InlineKeyboardButton("🎬 Все фильмы", callback_data='all_movies')
                    ]
                ]
                query.edit_message_text(
                    f"🎉 Отлично! Фильм \"{movie['title']}\" отмечен как просмотренный!\n\n"
                    f"Что дальше?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            query.edit_message_text("❌ Не удалось найти фильм. Возможно, он уже удален.")
    
    elif data.startswith('delete_'):
        movie_id = int(data.split('_')[1])
        success = db.delete_movie(user.id, movie_id)
        
        if success:
            keyboard = [
                [
                    InlineKeyboardButton("📋 К спискам", callback_data='show_lists'),
                    InlineKeyboardButton("🎬 Все фильмы", callback_data='all_movies')
                ]
            ]
            query.edit_message_text(
                "🗑️ Фильм удален из списка!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            query.edit_message_text("❌ Не удалось удалить фильм.")
    
    elif data == 'all_movies':
        show_all_movies(query=query, user_id=user.id)
    
    elif data == 'watched_only':
        watched = db.get_movies(user.id, 'watched')
        
        text = "✅ **Просмотренные фильмы:**\n\n"
        
        if watched:
            for i, movie in enumerate(watched, 1):
                date_str = movie['added_date'][:10] if movie['added_date'] else "дата неизвестна"
                text += f"{i}. {movie['title']} ({date_str})\n"
        else:
            text += "Пока нет просмотренных фильмов.\n"
            text += "Добавьте фильм и отметьте его как просмотренный!"
        
        text += f"\n📊 Всего просмотрено: {len(watched)} фильмов"
        
        keyboard = []
        
        if watched:
            for movie in watched[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑️ Удалить '{movie['title'][:20]}...'", 
                        callback_data=f'delete_{movie["id"]}'
                    )
                ])
        
        keyboard.append([
            InlineKeyboardButton("📋 Все списки", callback_data='show_lists'),
            InlineKeyboardButton("🎬 Все фильмы", callback_data='all_movies')
        ])
        
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'add_new_movie':
        query.edit_message_text(
            "📝 Отправьте название фильма, который хотите добавить.\n\n"
            "👁️ *Фильм будет автоматически добавлен в публичный список*"
        )
    
    elif data == 'help_btn':
        help_text = """
📋 **Управление списками:**

👁️ **Публичные фильмы:**
• Все добавленные фильмы видны всем пользователям
• Используйте команду /private <ID> чтобы скрыть фильм
• Иконки: 👁️ - публичный, 🔒 - приватный

🎬 **Основные действия:**
• Нажмите кнопку "✅ Просмотрен" под фильмом
• Используйте кнопки навигации для перехода между списками
• Напишите название фильма, чтобы добавить новый

🗑️ **Удаление фильмов:**
• Кнопка "🗑️ Удалить" доступна под каждым фильмом
• Удаление необратимо!
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Назад к спискам", callback_data='show_lists')]
        ]
        
        query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'public_list':
        all_public_movies = db.get_all_public_movies()
        
        text = "👁️ **Общий публичный список**\n\n"
        
        if all_public_movies:
            recent_movies = all_public_movies[:10]
            for i, movie in enumerate(recent_movies, 1):
                status_icon = "✅" if movie['status'] == 'watched' else "📝"
                user_name = movie['first_name'] or 'Аноним'
                date_str = movie['added_date'][:10] if movie['added_date'] else ""
                text += f"{i}. {status_icon} {movie['title']} (от {user_name}) {date_str}\n"
            
            if len(all_public_movies) > 10:
                text += f"\n... и еще {len(all_public_movies) - 10} фильмов\n"
        else:
            text += "Пока нет публичных фильмов.\n"
        
        want_count = sum(1 for m in all_public_movies if m['status'] != 'watched')
        watched_count = sum(1 for m in all_public_movies if m['status'] == 'watched')
        
        text += f"\n📊 Всего публичных фильмов: {len(all_public_movies)}"
        text += f"\n📝 Хотят посмотреть: {want_count}"
        text += f"\n✅ Просмотрено: {watched_count}"
        
        keyboard = [
            [
                InlineKeyboardButton("📋 Мои списки", callback_data='show_lists'),
                InlineKeyboardButton("🎬 Все фильмы", callback_data='all_movies')
            ],
            [
                InlineKeyboardButton("➕ Добавить фильм", callback_data='add_new_movie')
            ]
        ]
        
        query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def show_lists_menu(query, user_id):
    want_to_watch = db.get_movies(user_id, 'want_to_watch')
    watched = db.get_movies(user_id, 'watched')
    
    text = "📋 **Управление списками**\n\n"
    text += f"📝 Хочу посмотреть: {len(want_to_watch)} фильмов\n"
    text += f"✅ Просмотрено: {len(watched)} фильмов\n\n"
    text += "Выберите действие:"
    
    keyboard = []
    
    if want_to_watch:
        for movie in want_to_watch[:3]:
            short_title = movie['title'][:20] + ('...' if len(movie['title']) > 20 else '')
            keyboard.append([
                InlineKeyboardButton(f"✅ {short_title}", callback_data=f'watch_{movie["id"]}')
            ])
    
    if watched:
        for movie in watched[:3]:
            short_title = movie['title'][:20] + ('...' if len(movie['title']) > 20 else '')
            keyboard.append([
                InlineKeyboardButton(f"🗑️ {short_title}", callback_data=f'delete_{movie["id"]}')
            ])
    
    keyboard.append([
        InlineKeyboardButton("🎬 Все фильмы", callback_data='all_movies'),
        InlineKeyboardButton("✅ Просмотренные", callback_data='watched_only')
    ])
    
    keyboard.append([
        InlineKeyboardButton("👁️ Общий список", callback_data='public_list'),
        InlineKeyboardButton("➕ Добавить фильм", callback_data='add_new_movie')
    ])
    
    keyboard.append([
        InlineKeyboardButton("❓ Помощь", callback_data='help_btn')
    ])
    
    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    print("=" * 50)
    print("🎬 Movie Bot - Бот для управления списком фильмов")
    print("👁️ ВСЕ фильмы добавляются в публичный список по умолчанию")
    print("=" * 50)
    print(f"Токен начинается с: {TOKEN[:10]}...")
    print("Запуск бота...")
    
    try:
        updater = Updater(TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("add", add_movie))
        dispatcher.add_handler(CommandHandler("my_movies", show_my_movies))
        dispatcher.add_handler(CommandHandler("watched", show_watched))
        dispatcher.add_handler(CommandHandler("all_movies", show_all_movies))
        dispatcher.add_handler(CommandHandler("public", show_public_movies))
        dispatcher.add_handler(CommandHandler("private", toggle_privacy))
        
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, add_movie))
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        
        print("✅ Бот успешно запущен!")
        print("✅ База данных movies.db создана")
        print("✅ ВСЕ фильмы теперь публичные по умолчанию")
        print("✅ Используйте /private <ID> чтобы сделать фильм приватным")
        print("✅ Ожидаем сообщения от пользователей...")
        print("=" * 50)
        
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
        print("\nВозможные причины:")
        print("1. Неверный токен бота")
        print("2. Проблемы с интернет-соединением")
        print("3. Библиотека python-telegram-bot не установлена")
        print("\nРешение:")
        print("1. Убедитесь, что токен корректен")
        print("2. Проверьте интернет-соединение")
        print("3. Установите библиотеку: pip install python-telegram-bot")

# ========== ЗАПУСК ПРОГРАММЫ ==========
if __name__ == '__main__':
    if TOKEN == '8032006876:AAE4b7z902XbYYQQ8VIW2J7kmIHTu8zVkO8':
        print("=" * 50)
        print("⚠️  ВНИМАНИЕ: Используется тестовый токен!")
        print("=" * 50)
        print("Для рабочего бота:")
        print("1. Получите токен у @BotFather")
        print("2. В Render Dashboard:")
        print("   - Settings → Environment")
        print("   - Добавьте переменную BOT_TOKEN")
        print("   - Вставьте ваш токен")
        print("3. Перезапустите сервис")
        print("=" * 50)
        print("Запуск с тестовым токеном...")
        print("Бот может не отвечать!")
        print("=" * 50)
    
    try:
        main()
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
        print("Проверьте токен и настройки!")