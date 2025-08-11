import os
from dotenv import load_dotenv

load_dotenv()

# Настройки бота
BOT_TOKEN = '8358529091:AAGsoEGKWERtoC9_IwmzHyi9PSBpmq5Zfd8'
# ADMIN_ID = 7726649938
ADMIN_IDS = [7726649938, 5731003228, 686666666, 7229590364]  # добавлен @almazovp2p

# Настройки комиссии (в процентах)
COMMISSION_PERCENT = 40.0  # 40% от суммы сделки

# Настройки CryptoPay API
CRYPTOPAY_API_KEY = '429837:AAwGb3pgcB4UcJgSJDIILXmZhwvBSP3jXSL'
CRYPTOPAY_WALLET_ID = 5731003228  # ID администратора
CRYPTOPAY_API_URL = "https://pay.crypt.bot/api"

# Настройки внешней криптобиржи для комиссии
EXTERNAL_EXCHANGE_NAME = "Binance"  # Название биржи
EXTERNAL_EXCHANGE_WALLET_ADDRESS = "TPicyKTC5qkBAACrgki49AiVgBuAr1JDuH"  # Адрес кошелька на внешней бирже (USDT TRC20)
EXTERNAL_EXCHANGE_API_KEY = ""  # API ключ биржи (если нужен)
EXTERNAL_EXCHANGE_SECRET = ""  # Секрет API биржи (если нужен)

# Курс валют (можно обновлять через API)
USD_TO_RUB_RATE = 95.0  # Примерный курс доллара к рублю

# Статусы сделок
STATUS_PENDING = "pending"      # Ожидает оплаты
STATUS_PAID = "paid"           # Оплачено
STATUS_IN_PROGRESS = "in_progress"  # В работе
STATUS_COMPLETED = "completed"  # Завершено
STATUS_DISPUTED = "disputed"    # Спор
STATUS_CANCELLED = "cancelled"  # Отменено

# Команды бота
COMMANDS = {
    'start': 'Запустить бота',
    'help': 'Помощь',
    'create_deal': 'Создать новую сделку',
    'my_deals': 'Мои сделки',
    'balance': 'Баланс',
    'support': 'Поддержка'
} 