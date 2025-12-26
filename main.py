import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "7981543817:AAEzCDQj7iqrib0hpaX1hJlvMYEPBRIA354"
ADMIN_ID = 7487014085 # <-- your Telegram numeric ID

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cur = conn.cursor()

# Users
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    vip INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    active_referrals INTEGER DEFAULT 0,
    balance REAL DEFAULT 0,
    referral_balance REAL DEFAULT 0,
    is_agent INTEGER DEFAULT 0,
    referred_by INTEGER DEFAULT NULL
)
""")

# Payments
cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    vip INTEGER,
    status TEXT
)
""")

# Referrals
cur.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER,
    referred_id INTEGER,
    status TEXT
)
""")

# Withdrawals
cur.execute("""
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    type TEXT,
    method TEXT,
    status TEXT
)
""")
conn.commit()

# ---------------- HELPERS ----------------
def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = cur.fetchone()
    if not user:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        return get_user(uid)
    return user

def check_agent(uid):
    user = get_user(uid)
    if user[1] >= 6 and user[2] >= 15 and user[3] >= 25:
        cur.execute("UPDATE users SET is_agent=1 WHERE user_id=?", (uid,))
        conn.commit()
        return True
    return False

def add_referral(referred_id, referrer_id):
    cur.execute("INSERT INTO referrals (referrer_id, referred_id, status) VALUES (?, ?, ?)",
                (referrer_id, referred_id, "pending"))
    cur.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, referred_id))
    conn.commit()

def activate_referral(referred_id):
    cur.execute("SELECT referrer_id FROM referrals WHERE referred_id=?", (referred_id,))
    row = cur.fetchone()
    if row:
        referrer_id = row[0]
        cur.execute("UPDATE referrals SET status='active' WHERE referred_id=?", (referred_id,))
        cur.execute("UPDATE users SET referrals = referrals + 1, referral_balance = referral_balance + 0 WHERE user_id=?", (referrer_id,))
        cur.execute("UPDATE users SET active_referrals = active_referrals + 1 WHERE user_id=?", (referrer_id,))
        conn.commit()

# ---------------- MENUS ----------------
main_menu = ReplyKeyboardMarkup(
    [["🏠 Home", "📦 Plans"], ["💳 Payment", "💰 Balance"], ["🏧 Withdraw", "🤝 Agent"], ["📞 Contact"]],
    resize_keyboard=True
)

vip_menu = ReplyKeyboardMarkup(
    [["VIP 1", "VIP 2", "VIP 3"], ["VIP 4", "VIP 5", "VIP 6"], ["⬅ Back"]],
    resize_keyboard=True
)

manager_menu = ReplyKeyboardMarkup(
    [["📊 My Members", "💰 Manager Earnings"], ["🏧 Manager Withdraw", "⬅ Back"]],
    resize_keyboard=True
)

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    get_user(user_id)
    args = context.args
    if args:
        try:
            ref_id = int(args[0])
            if ref_id != user_id:
                add_referral(user_id, ref_id)
        except:
            pass
    await update.message.reply_text("Welcome to StepUp Finance 🇪🇹\nChoose an option below:", reply_markup=main_menu)

# ---------------- HOME ----------------
async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 StepUp Finance\n• Invest in USDT or ETB\n• VIP plans with fixed returns\n"
        "• 10% referral bonus\n• Agent & Manager rewards\n• Manual payment approval"
    )

# ---------------- PLANS ----------------
async def plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 VIP Plans\n"
        "VIP 1: 50 USDT / 2,000 ETB → 100 USDT (10 days)\n"
        "VIP 2: 100 USDT / 4,000 ETB → 220 USDT (15 days)\n"
        "VIP 3: 200 USDT / 8,000 ETB → 450 USDT (20 days)\n"
        "VIP 4: 300 USDT / 12,000 ETB → 720 USDT (25 days)\n"
        "VIP 5: 500 USDT / 20,000 ETB → 1,300 USDT (30 days)\n"
        "VIP 6: 700 USDT / 28,000 ETB → 2,000 USDT (35 days)"
    )

# ---------------- PAYMENT ----------------
async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💳 Choose VIP Plan:", reply_markup=vip_menu)

async def vip_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vip = int(update.message.text.split()[1])
    uid = update.message.from_user.id
    cur.execute("INSERT INTO payments (user_id, vip, status) VALUES (?, ?, ?)", (uid, vip, "pending"))
    conn.commit()
    await update.message.reply_text(f"VIP {vip} selected. Send payment screenshot to admin for approval.")

# ---------------- SCREENSHOT ----------------
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    cur.execute("SELECT id, vip FROM payments WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (uid,))
    row = cur.fetchone()
    if not row:
        await update.message.reply_text("No pending payment found.")
        return
    payment_id, vip = row
    caption = f"🧾 Payment Request\nUser ID: {uid}\nVIP: {vip}\n/approve_{payment_id}\n/reject_{payment_id}"
    await update.message.forward(chat_id=ADMIN_ID)
    await context.bot.send_message(chat_id=ADMIN_ID, text=caption)
    await update.message.reply_text("Screenshot sent to admin. Please wait for approval.")

# ---------------- ADMIN APPROVE/REJECT ----------------
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = int(update.message.text.split("_")[1])
    cur.execute("SELECT user_id, vip FROM payments WHERE id=?", (pid,))
    row = cur.fetchone()
    if not row:
        return
    uid, vip = row
    cur.execute("UPDATE payments SET status='approved' WHERE id=?", (pid,))
    cur.execute("UPDATE users SET vip=? WHERE user_id=?", (vip, uid))
    conn.commit()
    activate_referral(uid)
    check_agent(uid)
    await context.bot.send_message(chat_id=uid, text=f"✅ Your VIP {vip} has been approved!")
    await update.message.reply_text("Payment approved.")

async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = int(update.message.text.split("_")[1])
    cur.execute("UPDATE payments SET status='rejected' WHERE id=?", (pid,))
    conn.commit()
    await update.message.reply_text("Payment rejected.")

# ---------------- BALANCE ----------------
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.message.from_user.id)
    referral_link = f"https://t.me/StepUpFinanceBot?start={u[0]}"
    await update.message.reply_text(
        f"💰 Balance\nVIP Level: VIP {u[1]}\nReferral Balance: {u[5]} USDT\nReferrals: {u[2]} Active: {u[3]}\n"
        f"Your referral link: {referral_link}"
    )

# ---------------- WITHDRAW ----------------
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏧 Withdraw Request\nSend like this:\n50 USDT Local\n100 USDT USDT\nAdmin will approve your request."
    )

# ---------------- AGENT ----------------
async def agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user = get_user(uid)
    if check_agent(uid):
        await update.message.reply_text("🤝 Manager Panel", reply_markup=manager_menu)
    else:
        await update.message.reply_text(
            f"🤝 Agent Progress\nVIP: {user[1]}/6\nReferrals: {user[2]}/15\nActive Referrals: {user[3]}/25"
        )

# ---------------- CONTACT ----------------
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 Contact\nTelegram: StepUpFinancekAdmin\nWhatsApp: +251XXXXXXXXX")

# ---------------- TEXT HANDLER ----------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🏠 Home":
        await home(update, context)
    elif text == "📦 Plans":
        await plans(update, context)
    elif text == "💳 Payment":
        await payment(update, context)
    elif text.startswith("VIP"):
        await vip_select(update, context)
    elif text == "💰 Balance":
        await balance(update, context)
    elif text == "🏧 Withdraw":
        await withdraw(update, context)
    elif text == "🤝 Agent":
        await agent(update, context)
    elif text == "📞 Contact":
        await contact(update, context)
    elif text == "⬅ Back":
        await update.message.reply_text("Main Menu", reply_markup=main_menu)

# ---------------- MAIN ----------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
