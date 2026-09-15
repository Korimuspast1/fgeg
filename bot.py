import asyncio, os, html
from dotenv import load_dotenv
import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv(); TOKEN=os.getenv('BOT_TOKEN'); ADMIN=int(os.getenv('ADMIN_ID','1398491942')); DB=os.getenv('DB_PATH','dating.sqlite3')
if not TOKEN or TOKEN == 'PASTE_NEW_TOKEN_HERE': raise RuntimeError('Укажи новый BOT_TOKEN в .env')
bot=Bot(TOKEN); dp=Dispatcher(storage=MemoryStorage()); r=Router(); dp.include_router(r)

async def db(sql,args=(),fetch=False):
    async with aiosqlite.connect(DB) as c:
        c.row_factory=aiosqlite.Row; cur=await c.execute(sql,args); await c.commit()
        return await cur.fetchall() if fetch else cur.lastrowid
async def init():
    await db('''CREATE TABLE IF NOT EXISTS users(tg INTEGER PRIMARY KEY, lang TEXT DEFAULT 'ru', accepted INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, rep INTEGER DEFAULT 0)''')
    await db('''CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY AUTOINCREMENT,tg INTEGER UNIQUE,name TEXT,age INTEGER,city TEXT,about TEXT,interests TEXT,photo TEXT,hidden INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP)''')
    await db('''CREATE TABLE IF NOT EXISTS likes(from_tg INTEGER,to_tg INTEGER, UNIQUE(from_tg,to_tg))''')
    await db('''CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT,from_tg INTEGER,to_tg INTEGER,reason TEXT)''')
async def user(tg):
    x=await db('SELECT * FROM users WHERE tg=?',(tg,),True)
    if not x: await db('INSERT INTO users(tg) VALUES(?)',(tg,)); return await user(tg)
    return x[0]
def kb(rows): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in rows],resize_keyboard=True)
main=kb([['🔎 Смотреть','📝 Моя анкета'],['❤️ Симпатии','⚙️ Настройки']])

def card(p):
    return f"<b>{html.escape(p['name'])}, {p['age']}</b>\n📍 {html.escape(p['city'])}\n\n{html.escape(p['about'] or '')}\n\n<i>{html.escape(p['interests'] or '')}</i>\n\n🆔 Анкета #{p['id']}"
def agree(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Принимаю соглашение',callback_data='agree')]])
def actions(tg): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❤️ Нравится',callback_data=f'like:{tg}'),InlineKeyboardButton(text='➡️ Дальше',callback_data=f'skip:{tg}')],[InlineKeyboardButton(text='🚩 Пожаловаться',callback_data=f'report:{tg}')]])

class Form(StatesGroup): name=State(); age=State(); city=State(); about=State(); interests=State(); photo=State()
async def ask_form(m,state): await state.set_state(Form.name); await m.answer('Как тебя зовут?')
@r.message(CommandStart())
async def start(m:Message):
    u=await user(m.from_user.id)
    if u['banned']: return await m.answer('⛔ Доступ ограничен.')
    if not u['accepted']: return await m.answer('Привет! Здесь люди знакомятся уважительно. Перед началом прими лицензионное соглашение и правила сообщества.',reply_markup=agree())
    await m.answer('Готово. Выбирай действие 👇',reply_markup=main)
@r.callback_query(F.data=='agree')
async def agreed(c:CallbackQuery):
    await db('UPDATE users SET accepted=1 WHERE tg=?',(c.from_user.id,)); await c.message.answer('Отлично! Создай короткую анкету.',reply_markup=main); await c.answer()
@r.message(F.text=='📝 Моя анкета')
async def profile(m,state):
    p=await db('SELECT * FROM profiles WHERE tg=?',(m.from_user.id,),True)
    if p: return await m.answer(card(p[0]),parse_mode='HTML',reply_markup=kb([['✏️ Изменить анкету','🗑 Удалить анкету'],['🔙 В меню']]))
    await ask_form(m,state)
@r.message(F.text=='✏️ Изменить анкету')
async def edit(m,state): await ask_form(m,state)
@r.message(Form.name)
async def f1(m,state): await state.update_data(name=m.text); await state.set_state(Form.age); await m.answer('Сколько лет? (18+)')
@r.message(Form.age)
async def f2(m,state):
    if not m.text.isdigit() or not 18<=int(m.text)<=99: return await m.answer('Введи возраст от 18 до 99.')
    await state.update_data(age=int(m.text)); await state.set_state(Form.city); await m.answer('Город?')
@r.message(Form.city)
async def f3(m,state): await state.update_data(city=m.text); await state.set_state(Form.about); await m.answer('Расскажи о себе в одной-двух фразах.')
@r.message(Form.about)
async def f4(m,state): await state.update_data(about=m.text); await state.set_state(Form.interests); await m.answer('Твои интересы?')
@r.message(Form.interests)
async def f5(m,state): await state.update_data(interests=m.text); await state.set_state(Form.photo); await m.answer('Пришли фото или напиши «пропуск».')
@r.message(Form.photo)
async def f6(m,state):
    d=await state.get_data(); photo=m.photo[-1].file_id if m.photo else None
    await db('''INSERT INTO profiles(tg,name,age,city,about,interests,photo) VALUES(?,?,?,?,?,?,?) ON CONFLICT(tg) DO UPDATE SET name=excluded.name,age=excluded.age,city=excluded.city,about=excluded.about,interests=excluded.interests,photo=excluded.photo,hidden=0''',(m.from_user.id,d['name'],d['age'],d['city'],d['about'],d['interests'],photo)); await state.clear(); await m.answer('Анкета готова ✨',reply_markup=main)

async def next_profile(tg):
    x=await db('''SELECT p.* FROM profiles p JOIN users u ON u.tg=p.tg WHERE p.tg<>? AND p.hidden=0 AND u.banned=0 AND p.tg NOT IN(SELECT to_tg FROM likes WHERE from_tg=?) ORDER BY p.id DESC LIMIT 1''',(tg,tg),True); return x[0] if x else None
@r.message(F.text=='🔎 Смотреть')
async def browse(m):
    p=await next_profile(m.from_user.id)
    if not p:return await m.answer('Пока новых анкет нет. Загляни позже 🙂')
    if p['photo']: await m.answer_photo(p['photo'],caption=card(p),parse_mode='HTML',reply_markup=actions(p['tg']))
    else: await m.answer(card(p),parse_mode='HTML',reply_markup=actions(p))
@r.callback_query(F.data.startswith(('like:','skip:','report:')))
async def act(c):
    typ,t=c.data.split(':'); t=int(t)
    if typ=='like':
        await db('INSERT OR IGNORE INTO likes VALUES(?,?)',(c.from_user.id,t)); back=await db('SELECT 1 FROM likes WHERE from_tg=? AND to_tg=?',(t,c.from_user.id),True)
        if back: await db('UPDATE users SET rep=rep+1 WHERE tg IN (?,?)',(t,c.from_user.id)); await bot.send_message(t,'💞 У вас взаимная симпатия! Напишите друг другу.')
    elif typ=='report': await db('INSERT INTO reports(from_tg,to_tg,reason) VALUES(?,?,?)',(c.from_user.id,t,'обычная жалоба')); await bot.send_message(ADMIN,f'🚩 Жалоба на пользователя {t}')
    await c.answer('Готово'); await c.message.delete();
@r.message(F.text=='🗑 Удалить анкету')
async def delete(m): await db('DELETE FROM profiles WHERE tg=?',(m.from_user.id,)); await m.answer('Анкета удалена.',reply_markup=main)
@r.message(F.text=='⚙️ Настройки')
async def settings(m): await m.answer('Настройки',reply_markup=kb([['🌐 Язык','🙈 Скрыть анкету'],['🔙 В меню']]))
@r.message(F.text=='🙈 Скрыть анкету')
async def hide(m): await db('UPDATE profiles SET hidden=1 WHERE tg=?',(m.from_user.id,)); await m.answer('Анкета скрыта.',reply_markup=main)
@r.message(F.text=='🔙 В меню')
async def menu(m): await m.answer('Меню',reply_markup=main)

admin_kb=kb([['📊 Статистика','🔍 Найти анкету'],['🗑 Удалить по ID','⛔ Бан по Telegram ID'],['✅ Разбан','⭐ Репутация'],['🔙 В меню']])
admin_modes={}
@r.message(Command('admin'))
async def admin(m):
    if m.from_user.id==ADMIN: await m.answer('Админ-панель',reply_markup=admin_kb)
@r.message(F.text=='📊 Статистика')
async def stats(m):
    if m.from_user.id!=ADMIN:return
    a=await db('SELECT COUNT(*) n FROM users',(),True); p=await db('SELECT COUNT(*) n FROM profiles',(),True); await m.answer(f'Пользователей: {a[0]["n"]}\nАнкет: {p[0]["n"]}')
@r.message(F.text.in_({'🔍 Найти анкету','🗑 Удалить по ID','⛔ Бан по Telegram ID','✅ Разбан','⭐ Репутация'}))
async def admin_action(m):
    if m.from_user.id!=ADMIN:return
    await m.answer('Отправь число: ID анкеты или Telegram ID, в зависимости от выбранного действия.')
    admin_modes[m.from_user.id]=m.text
@r.message(F.text.regexp(r'^\d+$'))
async def admin_number(m):
    if m.from_user.id!=ADMIN:return
    action=admin_modes.get(m.from_user.id); n=int(m.text)
    if action=='🔍 Найти анкету':
        x=await db('SELECT * FROM profiles WHERE id=? OR tg=?',(n,n),True); await m.answer(card(x[0]) if x else 'Не найдено',parse_mode='HTML')
    elif action=='🗑 Удалить по ID': await db('DELETE FROM profiles WHERE id=? OR tg=?',(n,n)); await m.answer('Удалено.')
    elif action=='⛔ Бан по Telegram ID': await db('UPDATE users SET banned=1 WHERE tg=?',(n,)); await m.answer('Заблокирован.')
    elif action=='✅ Разбан': await db('UPDATE users SET banned=0 WHERE tg=?',(n,)); await m.answer('Разблокирован.')
    elif action=='⭐ Репутация': await db('UPDATE users SET rep=rep+1 WHERE tg=?',(n,)); await m.answer('Репутация +1.')
    admin_modes.pop(m.from_user.id,None)

async def main_loop(): await init(); await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main_loop())
