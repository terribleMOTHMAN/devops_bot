import os
import re

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

load_dotenv()

TOKEN = os.getenv("TOKEN")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "db_customers")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

EMAIL_TABLE = "emails"
PHONE_TABLE = "phone_numbers"

EMAIL_RE = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", re.IGNORECASE)
PHONE_CHUNK_RE = re.compile(r"(?:\+7|8)[\d\s()-]{9,}")

state = {}

def db_connect():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )

def get_emails():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f'SELECT id, email FROM public."{EMAIL_TABLE}" ORDER BY id DESC LIMIT 200')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_phones():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(f'SELECT id, phone FROM public."{PHONE_TABLE}" ORDER BY id DESC LIMIT 200')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def insert_emails(items):
    conn = db_connect()
    cur = conn.cursor()
    cur.executemany(
        f'INSERT INTO public."{EMAIL_TABLE}" (email) VALUES (%s) ON CONFLICT DO NOTHING',
        [(x,) for x in items],
    )
    conn.commit()
    cur.close()
    conn.close()

def insert_phones(items):
    conn = db_connect()
    cur = conn.cursor()
    cur.executemany(
        f'INSERT INTO public."{PHONE_TABLE}" (phone) VALUES (%s) ON CONFLICT DO NOTHING',
        [(x,) for x in items],
    )
    conn.commit()
    cur.close()
    conn.close()

def get_repl_logs():
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT pg_is_in_recovery()")
        in_recovery = bool(cur.fetchone()[0])
        if in_recovery:
            cur.execute("SELECT status, received_lsn, latest_end_lsn, latest_end_time FROM pg_stat_wal_receiver")
            row = cur.fetchone()
            if not row:
                out = "wal_receiver: нет данных"
            else:
                out = f"wal_receiver status={row[0]} received_lsn={row[1]} latest_end_lsn={row[2]} latest_end_time={row[3]}"
        else:
            cur.execute("SELECT pg_current_wal_lsn()")
            lsn = cur.fetchone()[0]
            cur.execute("SELECT application_name, client_addr, state, sync_state FROM pg_stat_replication ORDER BY application_name")
            rows = cur.fetchall()
            header = f"primary lsn={lsn}"
            if not rows:
                out = header + "\nреплик нет"
            else:
                body = "\n".join([f"{r[0]} addr={r[1]} state={r[2]} sync={r[3]}" for r in rows])
                out = header + "\n" + body
        cur.close()
        conn.close()
        return out
    except Exception as e:
        return str(e)

def extract_emails(text):
    return sorted(set(EMAIL_RE.findall(text)))

def extract_phones(text):
    chunks = PHONE_CHUNK_RE.findall(text)
    out = set()
    for ch in chunks:
        digits = "".join(c for c in ch if c.isdigit())
        if len(digits) == 11 and digits[0] in ("7", "8"):
            if digits[0] == "8":
                digits = "7" + digits[1:]
            out.add("+" + digits)
    return sorted(out)

def help_text():
    return (
        "Команды:\n"
        "/get_repl_logs\n"
        "/get_emails\n"
        "/get_phone_numbers\n"
        "/find_email\n"
        "/find_phone_number\n"
        "/cancel\n\n"
    )

async def on_message(update, context):
    text = (update.message.text or "").strip()
    cid = update.message.chat_id

    if text in ("/start", "/help"):
        await update.message.reply_text(help_text())
        return

    if text == "/cancel":
        state.pop(cid, None)
        await update.message.reply_text("Ок.")
        return

    if text == "/get_repl_logs":
        await update.message.reply_text(get_repl_logs() or "Пусто.")
        return

    if text == "/get_emails":
        rows = get_emails()
        msg = "\n".join([f"{r[0]} | {r[1]}" for r in rows]) or "Пусто."
        await update.message.reply_text(msg)
        return

    if text == "/get_phone_numbers":
        rows = get_phones()
        msg = "\n".join([f"{r[0]} | {r[1]}" for r in rows]) or "Пусто."
        await update.message.reply_text(msg)
        return

    if text == "/find_email":
        state[cid] = {"mode": "wait_email_text"}
        await update.message.reply_text("Пришли текст для поиска email.")
        return

    if text == "/find_phone_number":
        state[cid] = {"mode": "wait_phone_text"}
        await update.message.reply_text("Пришли текст для поиска телефонов.")
        return

    st = state.get(cid)
    if not st:
        await update.message.reply_text("Напиши /help")
        return

    if st["mode"] == "wait_email_text":
        items = extract_emails(text)
        state.pop(cid, None)
        if not items:
            await update.message.reply_text("Email не найден.")
            return
        state[cid] = {"mode": "confirm_save_email", "items": items}
        await update.message.reply_text("Найдено:\n" + "\n".join(items) + "\n\nЗаписать в БД? (да/нет)")
        return

    if st["mode"] == "wait_phone_text":
        items = extract_phones(text)
        state.pop(cid, None)
        if not items:
            await update.message.reply_text("Телефоны не найдены.")
            return
        state[cid] = {"mode": "confirm_save_phone", "items": items}
        await update.message.reply_text("Найдено:\n" + "\n".join(items) + "\n\nЗаписать в БД? (да/нет)")
        return

    if st["mode"] == "confirm_save_email":
        items = st["items"]
        state.pop(cid, None)
        if text.lower() == "да":
            insert_emails(items)
            await update.message.reply_text("Записал.")
        else:
            await update.message.reply_text("Ок, не записываю.")
        return

    if st["mode"] == "confirm_save_phone":
        items = st["items"]
        state.pop(cid, None)
        if text.lower() == "да":
            insert_phones(items)
            await update.message.reply_text("Записал.")
        else:
            await update.message.reply_text("Ок, не записываю.")
        return

def main():
    if not TOKEN:
        raise SystemExit("TOKEN is required")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, on_message))
    app.run_polling()

if __name__ == "__main__":
    main()
