#!/usr/bin/env python3
"""
Простой скрипт для запуска Telegram Гарант Бота
"""

import os
import sys
from bot import GarantBot

def main():
    """Основная функция запуска"""
    print("🤖 Запуск Telegram Гарант Бота...")
    
    # Устанавливаем токен бота (замените на ваш токен)
    os.environ['BOT_TOKEN'] = '7567641603:AAGno7ZWSynDMrAU0O28DyIVRASJSnn7Ok4'
    # os.environ['ADMIN_ID'] = '123456789'  # Замените на ваш ID
    
    # Проверяем наличие токена
    if not os.getenv('BOT_TOKEN'):
        print("❌ Ошибка: Не найден токен бота!")
        sys.exit(1)
    
    try:
        # Запускаем бота
        bot = GarantBot()
        print("✅ Бот успешно запущен!")
        print("📱 Отправьте /start боту для начала работы")
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 