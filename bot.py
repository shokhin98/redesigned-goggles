import logging
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from config import BOT_TOKEN, ADMIN_IDS, COMMISSION_PERCENT, STATUS_PENDING, STATUS_PAID, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_DISPUTED, STATUS_CANCELLED
from database import Database
from keyboards import Keyboards
from admin import AdminPanel

import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_AMOUNT, WAITING_FOR_DESCRIPTION, WAITING_FOR_USERNAME = range(3)
WAITING_FOR_PAYMENT_METHOD, WAITING_FOR_PAYMENT_TYPE, WAITING_FOR_PREPAYMENT_AMOUNT = range(4, 7)

class GarantBot:
    def __init__(self):
        self.db = Database()
        self.admin_panel = AdminPanel(self.db)
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        # Обработчик команды /start (всегда работает вне ConversationHandler)
        self.application.add_handler(CommandHandler("start", self.start_command))
        # Обработчик команды /help
        self.application.add_handler(CommandHandler("help", self.help_command))
        # Обработчик команды /rate
        self.application.add_handler(CommandHandler("rate", self.rate_command))
        # Обработчик команды /admin
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        # Обработчик создания сделки
        logger.info("🔧 Регистрирую ConversationHandler для создания сделки")
        deal_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.create_deal_start, pattern="^create_deal$")
            ],
            states={
                WAITING_FOR_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_amount)],
                WAITING_FOR_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_description)],
            },
            fallbacks=[CallbackQueryHandler(self.cancel_operation, pattern="^cancel$")]
        )
        self.application.add_handler(deal_conv_handler)
        logger.info("✅ ConversationHandler для создания сделки зарегистрирован")
        
        # Обработчик отправки сделок
        transfer_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.request_username, pattern="^transfer_deal_")
            ],
            states={
                WAITING_FOR_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_username)],
            },
            fallbacks=[CallbackQueryHandler(self.cancel_operation, pattern="^cancel$")]
        )
        self.application.add_handler(transfer_conv_handler)
        
        # Обработчик назначения исполнителя
        assign_executor_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.request_executor_username, pattern="^assign_executor_")
            ],
            states={
                WAITING_FOR_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_executor_username)],
            },
            fallbacks=[CallbackQueryHandler(self.cancel_operation, pattern="^cancel$")]
        )
        self.application.add_handler(assign_executor_conv_handler)
        
        # Обработчик предложений сделок
        offer_deal_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.request_offer_username, pattern="^offer_deal_")
            ],
            states={
                WAITING_FOR_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_offer_username)],
            },
            fallbacks=[CallbackQueryHandler(self.cancel_operation, pattern="^cancel$")]
        )
        self.application.add_handler(offer_deal_conv_handler)
        
        # Обработчик кнопок (универсальный)
        logger.info("🔧 Регистрирую универсальный CallbackQueryHandler")
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        logger.info("✅ Универсальный CallbackQueryHandler зарегистрирован")
        
        # Обработчик текстовых сообщений для админ-поиска
        self.application.add_handler(MessageHandler(filters.TEXT, self.handle_text_message))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)

        # Обработчики принятия/отклонения предложения сделки
        self.application.add_handler(CallbackQueryHandler(self.accept_offered_deal, pattern="^accept_offered_deal_"))
        self.application.add_handler(CallbackQueryHandler(self.reject_offered_deal, pattern="^reject_offered_deal_"))

        # Обработчик команд вне ConversationHandler (гарантирует доступность)
        self.application.add_handler(MessageHandler(filters.Regex(r"^/start"), self.start_command))
        self.application.add_handler(MessageHandler(filters.Regex(r"^/help"), self.help_command))
        self.application.add_handler(MessageHandler(filters.Regex(r"^/rate"), self.rate_command))
        self.application.add_handler(MessageHandler(filters.Regex(r"^/admin"), self.admin_command))

        # Обработчик поиска сделки по номеру для админов
        self.application.add_handler(MessageHandler(
            filters.TEXT & filters.User(ADMIN_IDS),
            self.admin_panel.handle_deal_search
        ))

    def get_currency_symbol(self, user_id: int) -> str:
        """Получить символ валюты для пользователя"""
        return "$"  # Всегда доллары

    def get_currency_name(self, user_id: int) -> str:
        """Получить название валюты для пользователя"""
        return "USD"  # Всегда доллары
    
    def get_payment_method_name(self, payment_method: str) -> str:
        """Получить название способа оплаты"""
        # Оставляем только CryptoBot для всех способов оплаты
        return '💎 CryptoPay (USDT)'
    
    def get_status_translation(self, status: str) -> str:
        """Перевод статуса сделки на русский язык"""
        status_translations = {
            STATUS_PENDING: "Ожидает оплаты",
            STATUS_PAID: "Оплачено",
            STATUS_IN_PROGRESS: "В работе",
            STATUS_COMPLETED: "Завершено",
            STATUS_DISPUTED: "Спор",
            STATUS_CANCELLED: "Отменено",
            'pending': "Ожидает оплаты",
            'paid': "Оплачено",
            'in_progress': "В работе",
            'completed': "Завершено",
            'disputed': "Спор",
            'cancelled': "Отменено"
        }
        return status_translations.get(status, status)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        self.db.add_user(user.id, user.username, user.first_name, user.last_name)

        # Получаем количество непрочитанных уведомлений
        unread_count = self.db.get_unread_notifications_count(user.id)

        welcome_text = f"""🛡️ **ГАРАНТ БОТ** 🛡️

🎉 **Добро пожаловать, {user.first_name}!**

🔐 **Ваш надежный помощник для безопасных сделок**
💼 **Защита покупателей и исполнителей**

📋 КАК ЭТО РАБОТАЕТ:

🔸 Создайте заказ с указанием суммы
🔸 Исполнитель принимает ваш заказ
🔸 Средства блокируются в гаранте
🔸 Исполнитель выполняет работу
🔸 После проверки - деньги переводятся

💎 ПРЕИМУЩЕСТВА:

✅ Полная безопасность сделок
✅ Защита от мошенничества 
✅ Быстрые переводы
✅ Круглосуточная поддержка

💰 Комиссия сервиса: 2.0%

🚀 Начните работу прямо сейчас!"""

        await update.message.reply_text(
            welcome_text,
            reply_markup=Keyboards.get_main_menu(unread_count)
        )

        return ConversationHandler.END
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        help_text = """
❓ Помощь по использованию бота

📋 Основные команды:
/start - Запустить бота
/help - Показать эту справку
/rate - Показать актуальный курс валют

💰 Как создать сделку:
1. Нажмите "Создать сделку"
2. Укажите сумму сделки в рублях
3. Выберите способ и тип оплаты
4. Опишите услугу
5. Ожидайте, пока исполнитель примет заказ

💳 Оплата:
• Для Crypto Bot используется актуальный курс USD/RUB
• После оплаты обязательно подтвердите платеж
• Деньги удерживаются до подтверждения выполнения

🔒 Безопасность:
• Деньги удерживаются до подтверждения выполнения
• При споре - решение принимает администратор
• Все транзакции записываются в базу данных

📞 Поддержка:
Если у вас возникли вопросы, обратитесь к администратору: @WawilonovX
        """
        
        # Проверяем, это команда или callback
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=Keyboards.get_main_menu()
            )
        else:
                    await update.message.reply_text(
            help_text,
            reply_markup=Keyboards.get_main_menu()
        )
    
    async def rate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /rate - показать курс валют"""
        rate_info = "💱 Курс USD: актуальный\n\n💡 Для точного курса используйте актуальные данные при оплате."
        
        await update.message.reply_text(
            f"💱 Курс валют\n\n{rate_info}\n\n"
            f"💡 Используйте актуальный курс для конвертации валют при оплате.",
            reply_markup=Keyboards.get_main_menu()
        )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /admin"""
        await self.admin_panel.handle_admin_command(update, context)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        logger.info(f"🔘 Обработка кнопки: {query.data}")
        if query.data == "main_menu":
            await self.show_main_menu(update, context)
            return
        elif query.data == "my_deals":
            await self.show_my_deals(update, context)
        elif query.data == "deposit":
            await self.show_deposit(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "support":
            support_text = (
                "📞 Поддержка\n\n"
                "🔧 Если у вас возникли вопросы или проблемы:\n\n"
                "👤 Администратор: @m1ras18\n"
                "📧 Email: support@garant-bot.com\n"
                "🌐 Сайт: https://garant-bot.com\n\n"
                "💡 Часто задаваемые вопросы:\n"
                "• Как создать сделку?\n"
                "• Как оплатить заказ?\n"
                "• Что делать при споре?\n"
                "• Как получить деньги?\n\n"
                "📋 Для получения помощи нажмите 'Связаться с админом'"
            )
            keyboard = [
                [InlineKeyboardButton("👤 Связаться с админом", url="https://t.me/m1ras18")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                support_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
            return
        elif query.data == "notifications":
            await self.show_notifications(update, context)
        elif query.data == "mark_all_read":
            await self.mark_all_notifications_read(update, context)
        elif query.data == "available_deals":
            await self.show_available_deals(update, context)
        elif query.data == "deal_offers":
            await self.show_deal_offers(update, context)
        elif query.data == "my_offers":
            await self.show_my_offers(update, context)
        elif query.data.startswith("view_deal_"):
            await self.view_available_deal(update, context)
        elif query.data.startswith("accept_deal_"):
            await self.accept_deal(update, context)
        elif query.data.startswith("accept_offered_deal_"):
            await self.accept_offered_deal(update, context)
        elif query.data.startswith("reject_offered_deal_"):
            await self.reject_offered_deal(update, context)
        elif query.data.startswith("accept_offer_"):
            await self.accept_deal_offer(update, context)
        elif query.data.startswith("reject_offer_"):
            await self.reject_deal_offer(update, context)
        elif query.data.startswith("deal_"):
            await self.handle_deal_actions(update, context)
        elif query.data.startswith("pay_deal_"):
            await self.handle_payment(update, context)
        elif query.data.startswith("check_payment_"):
            await self.check_payment_status(update, context)
        elif query.data.startswith("confirm_payment_"):
            await self.confirm_payment(update, context)
        elif query.data.startswith("payment_confirmed_"):
            await self.payment_confirmed(update, context)
        elif query.data.startswith("payment_cancelled_"):
            await self.payment_cancelled(update, context)

        elif query.data.startswith("start_work_"):
            await self.start_work(update, context)
        elif query.data.startswith("complete_work_"):
            await self.complete_work(update, context)
        elif query.data.startswith("confirm_completion_"):
            await self.confirm_completion(update, context)
        elif query.data.startswith("receive_payment_"):
            await self.receive_payment(update, context)
        elif query.data.startswith("finish_deal_"):
            await self.finish_deal(update, context)
        elif query.data.startswith("confirm_complete_"):
            await self.confirm_complete_work(update, context)
        elif query.data.startswith("final_confirm_"):
            await self.final_confirm_completion(update, context)
        elif query.data.startswith("open_dispute_"):
            await self.open_dispute(update, context)

        elif query.data == "cancel":
            await self.cancel_operation(update, context)
        elif query.data == "start_captcha":
            await self.start_captcha(update, context)
        elif query.data == "new_captcha":
            await self.new_captcha(update, context)
        # Админские callback
        elif query.data.startswith("admin_"):
            await self.admin_panel.handle_admin_callback(update, context)
        elif query.data.startswith("check_payment_status_"):
            await self.check_payment_status(update, context)
        elif query.data.startswith("verify_payment_"):
            await self.verify_payment_status(update, context)
        else:
            logger.warning(f"⚠️ Неизвестная кнопка: {query.data}")
            logger.warning(f"⚠️ ConversationHandler не перехватил callback: {query.data}")
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        unread_count = self.db.get_unread_notifications_count(user_id)
        try:
            await query.edit_message_text(
                "🤖 Главное меню Гарант Бота\n\nВыберите действие:",
                reply_markup=Keyboards.get_main_menu(unread_count)
            )
        except Exception as e:
            if 'Message is not modified' in str(e):
                # Не отправляем query.answer здесь, чтобы не было дублирования
                pass
            else:
                await query.answer(f"Ошибка: {str(e)}", show_alert=True)
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции и возврат в главное меню"""
        query = update.callback_query
        user_id = update.effective_user.id
        unread_count = self.db.get_unread_notifications_count(user_id)
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        await query.edit_message_text(
            "❌ Операция отменена\n\n🤖 Главное меню Гарант Бота\n\nВыберите действие:",
            reply_markup=Keyboards.get_main_menu(unread_count)
        )
        return ConversationHandler.END
    
    def generate_captcha(self):
        # Удалить весь метод
        pass
    
    async def start_captcha(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Удалить весь метод
        pass
    
    async def new_captcha(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Удалить весь метод
        pass
    
    async def show_captcha(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Удалить весь метод
        pass
    
    async def check_captcha(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Удалить весь метод
        pass
    
    async def create_deal_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания сделки"""
        query = update.callback_query
        user_id = update.effective_user.id
        logger.info(f"🎯 create_deal_start вызван для пользователя {user_id}")
        
        context.user_data['role'] = 'customer'  # По умолчанию создаем как заказчик
        logger.info("👤 Создание сделки как заказчик")
        
        # Выбираем текст в зависимости от языка
        amount_text = "💰 Введите сумму сделки в долларах:"
        
        await query.edit_message_text(
            amount_text,
            reply_markup=Keyboards.get_cancel_keyboard()
        )
        logger.info(f"✅ create_deal_start завершен, возвращаем WAITING_FOR_AMOUNT: {WAITING_FOR_AMOUNT}")
        return WAITING_FOR_AMOUNT
    


    async def get_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть больше 0!")
                return WAITING_FOR_AMOUNT
            context.user_data['amount'] = amount
            # Сразу переходим к описанию
            await update.message.reply_text(
                f"💰 Сумма: {amount} $\n\nВведите описание сделки:",
                reply_markup=Keyboards.get_cancel_keyboard()
            )
            return WAITING_FOR_DESCRIPTION
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите корректную сумму!")
            return WAITING_FOR_AMOUNT

    async def get_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        description = update.message.text
        if len(description) < 10:
            await update.message.reply_text("❌ Описание должно содержать минимум 10 символов!")
            return WAITING_FOR_DESCRIPTION
        
        # Создаем сделку
        amount = context.user_data.get('amount')
        
        # Создаем сделку в базе данных
        deal_id = self.db.create_deal_extended(
            customer_id=user_id,
            amount=amount,
            payment_amount=amount,
            payment_method='crypto',
            payment_type='full',
            description=description,
            customer_payment_method='crypto',
            customer_payment_address='CryptoPay',
            executor_payment_method='crypto',
            executor_payment_address='CryptoPay'
        )
        
        # Создаем чек для оплаты через CryptoPay API
        try:
            from crypto_bot_api import crypto_api
            
            # Создаем инвойс через CryptoPay API
            invoice_data = crypto_api.create_invoice(
                amount=amount,
                currency="USDT",
                description=f"Оплата сделки {deal_id}"
            )
            
            if invoice_data:
                # Получаем ссылку на чек
                check_id = invoice_data.get('invoice_id')
                pay_url = invoice_data.get('pay_url')
                
                # Сохраняем информацию о чеке в базе данных
                self.db.create_check(check_id, user_id, amount, f"Оплата сделки {deal_id}", pay_url)
                
                # Формируем сообщение о созданной сделке с чеком
                deal_text = f"✅ Сделка создана!\n\n"
                deal_text += f"🆔 ID: {deal_id}\n"
                deal_text += f"💰 Сумма: {amount} $\n"
                deal_text += f"💸 Комиссия: {amount * (COMMISSION_PERCENT / 100)} $ ({COMMISSION_PERCENT}%)\n"
                deal_text += f"📝 Описание: {description}\n\n"
                deal_text += f"💳 Способ оплаты: 💎 CryptoPay (USDT)\n"
                deal_text += f"💳 Тип оплаты: Полная оплата\n"
                deal_text += f"💵 Сумма к оплате: ${amount} USD\n\n"
                deal_text += f"💳 Инструкции по оплате:\n"
                deal_text += f"🔗 Для оплаты перейдите по ссылке на чек:\n"
                deal_text += f"{pay_url}\n\n"
                deal_text += f"💵 Сумма к оплате: {amount} USDT\n\n"
                deal_text += f"⚠️ После оплаты нажмите 'Подтвердить оплату'\n"
                deal_text += f"💳 Ссылка на чек: {pay_url}"
                
                keyboard = [
                    [InlineKeyboardButton("🔗 Оплатить чек", url=pay_url)],
                    [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"deal_{deal_id}")],
                    [InlineKeyboardButton("🔍 Проверить оплату", callback_data=f"verify_payment_{deal_id}")],
                ]
                
                logger.info(f"✅ Сделка и чек созданы: {deal_id} - {amount} USDT, чек: {check_id}")
                
            else:
                raise Exception("Не удалось создать инвойс через CryptoPay API")
            
        except Exception as e:
            logger.error(f"Ошибка при создании чека для сделки {deal_id}: {e}")
            
            # Показываем обычное сообщение при ошибке создания чека
            deal_text = f"✅ Сделка создана!\n\n"
            deal_text += f"🆔 ID: {deal_id}\n"
            deal_text += f"💰 Сумма: {amount} $\n"
            deal_text += f"💸 Комиссия: {amount * (COMMISSION_PERCENT / 100)} $ ({COMMISSION_PERCENT}%)\n"
            deal_text += f"📝 Описание: {description}\n\n"
            deal_text += f"💳 Способ оплаты: CryptoPay (USD)\n"
            deal_text += f"💳 Способ получения: CryptoPay (USD)\n\n"
            deal_text += f"📊 Статус: Ожидает оплаты\n\n"
        deal_text += f"💡 Сделка создана успешно! Ожидайте предложений от исполнителей."
        
        keyboard = [
            [InlineKeyboardButton("📤 Отправить исполнителю", callback_data=f"transfer_deal_{deal_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
            ]
        
        # Отправляем уведомление администратору
        admin_message = f"🆕 Новая сделка #{deal_id}\n\n💰 Сумма: {amount} $\n📝 Описание: {description}\n👤 Заказчик: {update.effective_user.first_name}"
        try:
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(chat_id=admin_id, text=admin_message)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление администратору: {e}")
        
        await update.message.reply_text(
            deal_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        context.user_data.clear()
        return ConversationHandler.END
    

    
    async def show_my_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать сделки пользователя"""
        query = update.callback_query
        user_id = update.effective_user.id
        deals = self.db.get_user_deals(user_id)
        
        if not deals:
            await query.edit_message_text(
                "📋 У вас пока нет сделок.\n\nСоздайте первую сделку!",
                reply_markup=Keyboards.get_main_menu()
            )
            return
        
        deals_text = "📋 Ваши сделки:\n\n"
        for i, deal in enumerate(deals[:5], 1):  # Показываем только последние 5 сделок
            status_emoji = {
                STATUS_PENDING: "⏳",
                STATUS_PAID: "💰",
                STATUS_IN_PROGRESS: "🚀",
                STATUS_COMPLETED: "✅",
                STATUS_DISPUTED: "⚠️",
                STATUS_CANCELLED: "❌"
            }.get(deal['status'], "❓")
            
            deals_text += f"{status_emoji} Сделка #{i}\n"
            deals_text += f"💰 Сумма: {deal['amount']} $\n"
            deals_text += f"📝 {deal['description'][:50]}...\n"
            deals_text += f"📊 Статус: {self.get_status_translation(deal['status'])}\n"
            
            # Добавляем информацию об исполнителе
            if deal['executor_id'] is not None:
                executor = self.db.get_user(deal['executor_id'])
                if executor:
                    executor_name = executor.get('first_name', 'Неизвестно')
                    deals_text += f"👨‍💼 Исполнитель: {executor_name}\n"
                else:
                    deals_text += f"👨‍💼 Исполнитель: Назначен\n"
            else:
                deals_text += f"👨‍💼 Исполнитель: Не назначен\n"
            
            deals_text += "\n"
        
        keyboard = []
        for i, deal in enumerate(deals[:5], 1):
            keyboard.append([InlineKeyboardButton(
                f"Сделка #{i}", 
                callback_data=f"deal_{deal['deal_id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await query.edit_message_text(
            deals_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_deal_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка действий со сделкой"""
        query = update.callback_query
        deal_id = query.data.split("_", 1)[1]
        
        deal = self.db.get_deal(deal_id)
        if not deal:
            await query.edit_message_text("❌ Сделка не найдена!", reply_markup=Keyboards.get_main_menu())
            return
        
        user_id = update.effective_user.id
        is_customer = deal['customer_id'] == user_id
        is_executor = deal['executor_id'] == user_id
        
        if not (is_customer or is_executor):
            await query.edit_message_text("❌ У вас нет доступа к этой сделке!", reply_markup=Keyboards.get_main_menu())
            return
        
        # Показываем информацию о сделке
        status_emoji = {
            STATUS_PENDING: "⏳",
            STATUS_PAID: "💰",
            STATUS_IN_PROGRESS: "🚀",
            STATUS_COMPLETED: "✅",
            STATUS_DISPUTED: "⚠️",
            STATUS_CANCELLED: "❌"
        }.get(deal['status'], "❓")
        
        deal_text = f"{status_emoji} Сделка {deal_id}\n\n"
        deal_text += f"💰 Общая сумма: {deal['amount']} $\n"
        deal_text += f"💸 Комиссия: {deal['commission']} $\n"
        
        # Добавляем информацию о способе оплаты
        payment_method = deal.get('payment_method', 'crypto')
        payment_type = deal.get('payment_type', 'full')
        payment_amount = deal.get('payment_amount', deal['amount'])
        
        deal_text += f"💳 Способ оплаты: 💎 CryptoPay (USDT)\n"
        
        if payment_type == 'prepayment':
            deal_text += f"💸 Тип оплаты: Предоплата ({payment_amount} $)\n"
            remaining = deal.get('remaining_amount', deal['amount'] - payment_amount)
            deal_text += f"💰 Остаток: {remaining} $\n"
        else:
            deal_text += f"💸 Тип оплаты: Полная оплата\n"
        
        deal_text += f"📝 Описание: {deal['description']}\n"
        deal_text += f"📊 Статус: {self.get_status_translation(deal['status'])}\n"
        deal_text += f"📅 Создана: {deal['created_at']}\n"
        
        # Добавляем информацию о заказчике
        customer = self.db.get_user(deal['customer_id'])
        if customer:
            customer_name = customer.get('first_name', 'Неизвестно')
            customer_username = customer.get('username', 'Без username')
            deal_text += f"👤 Заказчик: {customer_name} (@{customer_username})\n"
        else:
            deal_text += f"👤 Заказчик: Неизвестно\n"
        
        # Добавляем информацию об исполнителе
        if deal['executor_id'] is not None:
            executor = self.db.get_user(deal['executor_id'])
            if executor:
                executor_name = executor.get('first_name', 'Неизвестно')
                executor_username = executor.get('username', 'Без username')
                deal_text += f"👨‍💼 Исполнитель: {executor_name} (@{executor_username})\n"
            else:
                deal_text += f"👨‍💼 Исполнитель: Назначен (ID: {deal['executor_id']})\n"
        else:
            deal_text += f"👨‍💼 Исполнитель: Не назначен\n"
        
        deal_text += "\n"
        
        # Подготавливаем данные для клавиатуры
        deal_data = {
            'executor_id': deal['executor_id'],
            'customer_id': deal['customer_id']
        }
        
        # Добавляем username исполнителя
        if deal['executor_id'] is not None:
            executor = self.db.get_user(deal['executor_id'])
            if executor and executor.get('username') and isinstance(executor['username'], str) and executor['username'].strip():
                deal_data['executor_username'] = executor['username']
            elif 'executor_username' in deal_data:
                del deal_data['executor_username']

        # Добавляем username заказчика
        customer = self.db.get_user(deal['customer_id'])
        if customer and customer.get('username') and isinstance(customer['username'], str) and customer['username'].strip():
            deal_data['customer_username'] = customer['username']
        elif 'customer_username' in deal_data:
            del deal_data['customer_username']
        
        if is_customer:
            deal_text += "👤 Вы: Заказчик\n\n"
            
            # Если сделка ожидает оплаты, показываем интерфейс с чеком
            if deal['status'] == STATUS_PENDING:
                # Ищем существующий чек для этой сделки
                checks = self.db.get_user_checks(user_id)
                payment_url = None
                
                for check in checks:
                    if f"Оплата сделки {deal_id}" in check.get('description', ''):
                        payment_url = check.get('pay_url')
                        break
                
                if payment_url:
                    deal_text += f"💳 Инструкции по оплате:\n"
                    deal_text += f"🔗 Для оплаты перейдите по ссылке на чек:\n"
                    deal_text += f"{payment_url}\n\n"
                    deal_text += f"💵 Сумма к оплате: {payment_amount} USDT\n\n"
                    deal_text += f"⚠️ После оплаты нажмите 'Подтвердить оплату'\n"
                    deal_text += f"💳 Ссылка на чек: {payment_url}"
                    
                    keyboard = [
                        [InlineKeyboardButton("🔗 Оплатить чек", url=payment_url)],
                        [InlineKeyboardButton("🔍 Проверить оплату", callback_data=f"verify_payment_{deal_id}")],
                        [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")],
                        [InlineKeyboardButton("📤 Отправить исполнителю", callback_data=f"transfer_deal_{deal_id}")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
                    ]
                else:
                    # Если чек не найден, создаем новый
                    try:
                        from crypto_bot_api import crypto_api
                        
                        invoice_data = crypto_api.create_invoice(
                            amount=payment_amount,
                            currency="USDT",
                            description=f"Оплата сделки {deal_id}"
                        )
                        
                        if invoice_data:
                            check_id = invoice_data.get('invoice_id')
                            payment_url = invoice_data.get('pay_url')
                            
                            # Сохраняем чек в базе данных
                            self.db.create_check(check_id, user_id, payment_amount, f"Оплата сделки {deal_id}", payment_url)
                            
                            deal_text += f"💳 Инструкции по оплате:\n"
                            deal_text += f"🔗 Для оплаты перейдите по ссылке на чек:\n"
                            deal_text += f"{payment_url}\n\n"
                            deal_text += f"💵 Сумма к оплате: {payment_amount} USDT\n\n"
                            deal_text += f"⚠️ После оплаты нажмите 'Подтвердить оплату'\n"
                            deal_text += f"💳 Ссылка на чек: {payment_url}"
                            
                            keyboard = [
                                [InlineKeyboardButton("🔗 Оплатить чек", url=payment_url)],
                                [InlineKeyboardButton("🔍 Проверить оплату", callback_data=f"verify_payment_{deal_id}")],
                                [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")],
                                [InlineKeyboardButton("📤 Отправить исполнителю", callback_data=f"transfer_deal_{deal_id}")],
                                [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
                            ]
                        else:
                            # Если не удалось создать чек, показываем обычное сообщение
                            deal_text += f"💳 Способ оплаты: 💎 CryptoPay (USDT)\n"
                            deal_text += f"💵 Сумма к оплате: {payment_amount} USDT\n\n"
                            deal_text += f"⚠️ Обратитесь к администратору для получения ссылки на оплату"
                            
                            keyboard = [
                                [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")],
                                [InlineKeyboardButton("📤 Отправить исполнителю", callback_data=f"transfer_deal_{deal_id}")],
                                [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
                            ]
                    except Exception as e:
                        logger.error(f"Ошибка при создании чека для сделки {deal_id}: {e}")
                        deal_text += f"💳 Способ оплаты: 💎 CryptoPay (USDT)\n"
                        deal_text += f"💵 Сумма к оплате: {payment_amount} USDT\n\n"
                        deal_text += f"⚠️ Обратитесь к администратору для получения ссылки на оплату"
                        
                        keyboard = [
                            [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")],
                            [InlineKeyboardButton("📤 Отправить исполнителю", callback_data=f"transfer_deal_{deal_id}")],
                            [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
                        ]
            else:
                keyboard = Keyboards.get_deal_actions_keyboard(deal_id, deal['status'], deal_data)
        else:
            deal_text += "👷 Вы: Исполнитель"
            keyboard = Keyboards.get_executor_deal_keyboard(deal_id, deal['status'], deal_data)
        
        await query.edit_message_text(deal_text, reply_markup=keyboard)
    
    async def handle_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ информации об оплате сделки"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_PENDING:
            await query.answer("❌ Сделка уже оплачена!")
            return
        
        # Получаем параметры оплаты
        payment_amount = deal.get('payment_amount', deal['amount'])
        
        # Формируем сообщение об оплате
        payment_text = f"💳 Оплата сделки {deal_id}\n\n"
        payment_text += f"💰 Общая сумма: {deal['amount']} $\n"
        payment_text += f"💸 Способ оплаты: 💎 CryptoPay (USDT)\n"
        payment_text += f"💳 Тип оплаты: Полная оплата\n"
        payment_text += f"💵 Сумма к оплате: {payment_amount} USDT\n"
        payment_text += f"📝 Описание: {deal['description']}\n\n"
        payment_text += f"💳 Инструкции по оплате:\n"
        payment_text += f"1️⃣ Нажмите 'Создать чек для оплаты'\n"
        payment_text += f"2️⃣ Перейдите по ссылке в CryptoBot\n"
        payment_text += f"3️⃣ Оплатите чек полностью\n"
        payment_text += f"4️⃣ Вернитесь и нажмите 'Проверить оплату'\n\n"
        payment_text += f"⚠️ Чек создается только при нажатии кнопки!"
        
        keyboard = [
            [InlineKeyboardButton("💳 Создать чек для оплаты", callback_data=f"confirm_payment_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"deal_{deal_id}")]
        ]
        
        await query.edit_message_text(
            payment_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def confirm_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создание чека для оплаты сделки"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_PENDING:
            await query.answer("❌ Сделка уже оплачена!")
            return
        
        payment_amount = deal.get('payment_amount', deal['amount'])
        
        # Показываем сообщение о создании чека
        await query.edit_message_text(
            f"💳 Создание чека для оплаты...\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"💰 Сумма: {payment_amount} $\n"
            f"💵 Сумма в USDT: {payment_amount}\n\n"
            f"⏳ Создаем чек через CryptoPay API...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Обновить", callback_data=f"confirm_payment_{deal_id}")
            ]])
        )
        
        # Создаем новый чек через CryptoPay API
        try:
            from crypto_bot_api import crypto_api
            
            invoice_data = crypto_api.create_invoice(
                amount=payment_amount,
                currency="USDT",
                description=f"Оплата сделки {deal_id}"
            )
            
            if invoice_data:
                check_id = invoice_data.get('invoice_id')
                payment_url = invoice_data.get('pay_url')
                
                # Сохраняем чек в базе данных
                self.db.create_check(check_id, update.effective_user.id, payment_amount, f"Оплата сделки {deal_id}", payment_url)
                
                # Показываем информацию о чеке и ссылку на оплату
                payment_text = f"💳 Чек создан для оплаты\n\n"
                payment_text += f"🆔 ID сделки: {deal_id}\n"
                payment_text += f"💰 Сумма: {payment_amount} $\n"
                payment_text += f"💵 Сумма в USDT: {payment_amount}\n"
                payment_text += f"💳 Чек: {check_id}\n"
                payment_text += f"📝 Описание: {deal['description']}\n\n"
                payment_text += f"💳 Инструкции по оплате:\n"
                payment_text += f"🔗 Нажмите кнопку 'Оплатить чек' ниже\n"
                payment_text += f"💳 Перейдите в CryptoBot и оплатите чек\n"
                payment_text += f"✅ После оплаты вернитесь и нажмите 'Проверить оплату'\n\n"
                payment_text += f"⚠️ Важно: Оплатите чек полностью!"
                
                keyboard = [
                    [InlineKeyboardButton("🔗 Оплатить чек", url=payment_url)],
                    [InlineKeyboardButton("🔍 Проверить оплату", callback_data=f"verify_payment_{deal_id}")],
                    [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
                ]
                
                await query.edit_message_text(
                    payment_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            else:
                error_text = f"❌ Ошибка создания чека\n\n"
                error_text += f"🆔 ID сделки: {deal_id}\n"
                error_text += f"💰 Сумма: {payment_amount} $\n\n"
                error_text += f"Не удалось создать чек через CryptoPay API.\n"
                error_text += f"Попробуйте позже или обратитесь к администратору."
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"confirm_payment_{deal_id}")],
                    [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
                ]
                
                await query.edit_message_text(
                    error_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
        except Exception as e:
            logger.error(f"Ошибка при создании чека для сделки {deal_id}: {e}")
            error_text = f"❌ Ошибка создания чека\n\n"
            error_text += f"🆔 ID сделки: {deal_id}\n"
            error_text += f"💰 Сумма: {payment_amount} $\n\n"
            error_text += f"Произошла ошибка при создании чека.\n"
            error_text += f"Попробуйте позже или обратитесь к администратору."
            
            keyboard = [
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"confirm_payment_{deal_id}")],
                [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
            ]
            
            await query.edit_message_text(
                error_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    async def payment_confirmed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение реальной оплаты"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_PENDING:
            await query.answer("❌ Сделка уже оплачена!")
            return
        
        # Обновляем статус сделки
        payment_amount = deal.get('payment_amount', deal['amount'])
        self.db.update_deal_status(deal_id, STATUS_PAID)
        self.db.add_transaction(deal_id, update.effective_user.id, payment_amount, "payment", "Подтвержденная оплата сделки")
        
        # Добавляем уведомление исполнителю
        notification_message = f"💰 Сделка {deal_id} оплачена на сумму {payment_amount} $. Можете начинать работу."
        self.db.add_notification(deal['executor_id'], deal_id, "deal_paid", notification_message)
        
        await query.edit_message_text(
            f"✅ Оплата подтверждена!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"💰 Сумма: {payment_amount} $\n"
            f"📊 Статус: Оплачено\n"
            f"🔍 Проверка: Автоматическая через API\n\n"
            f"Исполнитель может начать работу.",
            reply_markup=Keyboards.get_main_menu()
        )
        
        # Уведомление исполнителю
        try:
            await context.bot.send_message(
                deal['executor_id'],
                f"💰 Сделка {deal_id} оплачена!\n\nМожете начинать работу.",
                reply_markup=Keyboards.get_main_menu()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    
    async def payment_cancelled(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена подтверждения оплаты"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        # Просто возвращаемся к информации о сделке
        await self.handle_payment(update, context)
    
    async def check_payment_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка статуса оплаты"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        # Проверяем инвойс
        invoice = self.db.get_deal_invoice(deal_id)
        if not invoice:
            await query.answer("❌ Инвойс не найден!")
            return
        
        # Проверяем статус через CryptoPay API
        from crypto_bot_api import crypto_api
        invoice_status = crypto_api.check_payment(invoice['invoice_id'])
        
        if invoice_status:
            # Обновляем статус инвойса
            self.db.update_invoice_status(invoice['invoice_id'], 'paid')
            # Автоматически подтверждаем оплату
            await self.payment_confirmed(update, context)
        else:
            # Показываем текущий статус
            await query.answer("📊 Статус оплаты: Не оплачен")
    
    async def verify_payment_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детальная проверка статуса оплаты с отображением результата"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        # Ищем чек для этой сделки
        checks = self.db.get_user_checks(update.effective_user.id)
        check_id = None
        
        for check in checks:
            if f"Оплата сделки {deal_id}" in check.get('description', ''):
                check_id = check.get('check_id')
                break
        
        if not check_id:
            await query.answer("❌ Чек для сделки не найден!")
            return
        
        # Показываем сообщение о проверке
        await query.edit_message_text(
            f"🔍 Проверяем статус оплаты...\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"💰 Сумма: {deal['amount']} $\n"
            f"💳 Чек: {check_id}\n\n"
            f"⏳ Подождите, проверяем через CryptoPay API...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Обновить", callback_data=f"verify_payment_{deal_id}")
            ]])
        )
        
        # Проверяем статус оплаты
        try:
            from crypto_bot_api import crypto_api
            
            # Получаем детальную информацию о статусе
            status_info = crypto_api.get_invoice_status(check_id)
            
            if status_info:
                status = status_info.get('status', 'unknown')
                amount = status_info.get('amount', 'N/A')
                created_at = status_info.get('created_at', 'N/A')
                
                if status == 'paid':
                    result_text = f"✅ Оплата подтверждена!\n\n"
                    result_text += f"🆔 ID сделки: {deal_id}\n"
                    result_text += f"💰 Сумма: {amount} USDT\n"
                    result_text += f"💳 Чек: {check_id}\n"
                    result_text += f"📅 Создан: {created_at}\n"
                    result_text += f"📊 Статус: {status}\n\n"
                    result_text += f"🎉 Оплата успешно получена!"
                    
                    keyboard = [
                        [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"payment_confirmed_{deal_id}")],
                        [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
                    ]
                else:
                    result_text = f"❌ Оплата не найдена\n\n"
                    result_text += f"🆔 ID сделки: {deal_id}\n"
                    result_text += f"💰 Сумма: {amount} USDT\n"
                    result_text += f"💳 Чек: {check_id}\n"
                    result_text += f"📅 Создан: {created_at}\n"
                    result_text += f"📊 Статус: {status}\n\n"
                    result_text += f"Возможные причины:\n"
                    result_text += f"• Оплата еще не поступила\n"
                    result_text += f"• Оплата была произведена не через этот чек\n"
                    result_text += f"• Ошибка в системе"
                    
                    keyboard = [
                        [InlineKeyboardButton("🔄 Проверить снова", callback_data=f"verify_payment_{deal_id}")],
                        [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
                    ]
            else:
                result_text = f"❌ Ошибка получения статуса\n\n"
                result_text += f"🆔 ID сделки: {deal_id}\n"
                result_text += f"💳 Чек: {check_id}\n\n"
                result_text += f"Не удалось получить информацию о статусе чека."
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"verify_payment_{deal_id}")],
                    [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
                ]
            
            await query.edit_message_text(
                result_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса оплаты для сделки {deal_id}: {e}")
            
            error_text = f"❌ Ошибка проверки\n\n"
            error_text += f"🆔 ID сделки: {deal_id}\n"
            error_text += f"💳 Чек: {check_id}\n\n"
            error_text += f"Произошла ошибка при проверке статуса оплаты.\n"
            error_text += f"Попробуйте позже или обратитесь к администратору."
            
            keyboard = [
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"verify_payment_{deal_id}")],
                [InlineKeyboardButton("🔙 Назад к сделке", callback_data=f"deal_{deal_id}")]
            ]
            
            await query.edit_message_text(
                error_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    async def start_work(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать работу по сделке"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['executor_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_PAID:
            await query.answer("❌ Сделка не оплачена!")
            return
        
        self.db.update_deal_status(deal_id, STATUS_IN_PROGRESS)
        
        await query.edit_message_text(
            f"🚀 Работа начата!\n\n"
            f"📊 Статус: В работе\n\n"
            f"Выполняйте заказ и сообщите о завершении.",
            reply_markup=Keyboards.get_main_menu()
        )
        
        # Уведомление заказчику
        try:
            await context.bot.send_message(
                deal['customer_id'],
                f"🚀 Исполнитель начал работу по сделке {deal_id}!",
                reply_markup=Keyboards.get_main_menu()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    
    async def complete_work(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершить работу"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['executor_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] not in [STATUS_PAID, STATUS_IN_PROGRESS]:
            await query.answer("❌ Работа не была начата!")
            return
        
        # Показываем подтверждение завершения
        confirm_text = f"⚠️ Подтверждение завершения работы\n\n"
        confirm_text += f"🆔 ID сделки: {deal_id}\n"
        confirm_text += f"💰 Сумма: {deal['amount']} $\n"
        confirm_text += f"📝 Описание: {deal['description']}\n\n"
        confirm_text += f"❗️ Вы уверены, что работа выполнена полностью?\n\n"
        confirm_text += f"После подтверждения:\n"
        confirm_text += f"• Заказчик получит уведомление\n"
        confirm_text += f"• Ожидается подтверждение от заказчика\n"
        confirm_text += f"• После подтверждения вы получите оплату\n\n"
        confirm_text += f"Вы действительно завершили работу?"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, завершил", callback_data=f"confirm_complete_{deal_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data=f"deal_{deal_id}")
            ]
        ]
        
        await query.edit_message_text(
            confirm_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def send_commission_to_crypto_bot(self, deal_id: str, commission_amount: float):
        """Отправка комиссии на внешнюю криптобиржу"""
        try:
            from crypto_bot_api import crypto_api
            
            # Комиссия уже в долларах (USDT), конвертация не нужна
            usdt_commission = commission_amount
            
            # Отправляем комиссию через CryptoPay API на внешнюю биржу
            success = crypto_api.send_commission(usdt_commission, "USDT", f"Deal_{deal_id}")
            
            if success:
                logger.info(f"💰 Комиссия {usdt_commission} USDT успешно отправлена на внешнюю биржу за сделку {deal_id}")
                return True
            else:
                logger.error(f"❌ Не удалось отправить комиссию {usdt_commission} USDT на внешнюю биржу за сделку {deal_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке комиссии на внешнюю биржу: {e}")
            return False
    
    async def confirm_completion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтвердить выполнение работы"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_COMPLETED:
            await query.answer("❌ Работа не завершена!")
            return
        
        # Показываем подтверждение
        confirm_text = f"⚠️ Подтверждение выполнения работы\n\n"
        confirm_text += f"🆔 ID сделки: {deal_id}\n"
        confirm_text += f"💰 Сумма: {deal['amount']} $\n"
        confirm_text += f"📝 Описание: {deal['description']}\n\n"
        confirm_text += f"❗️ Вы уверены, что работа выполнена качественно?\n\n"
        confirm_text += f"После подтверждения:\n"
        confirm_text += f"• Исполнитель получит оплату: {deal['amount'] - deal['commission']} $\n"
        confirm_text += f"• Комиссия: {deal['commission']} $\n"
        confirm_text += f"• Сделка будет полностью завершена\n"
        confirm_text += f"• Отменить будет невозможно\n\n"
        confirm_text += f"Вы действительно довольны результатом?"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, подтверждаю", callback_data=f"final_confirm_{deal_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data=f"deal_{deal_id}")
            ]
        ]
        
        await query.edit_message_text(
            confirm_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def receive_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение денег исполнителем"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['executor_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_COMPLETED:
            await query.answer("❌ Сделка не завершена!")
            return
        
        # Выплата исполнителю
        executor_amount = deal['amount'] - deal['commission']
        self.db.update_balance(deal['executor_id'], executor_amount)
        self.db.add_transaction(deal_id, deal['executor_id'], executor_amount, "payout", "Выплата исполнителю")
        
        # Отправка комиссии на указанный счет
        await self.send_commission_to_crypto_bot(deal_id, deal['commission'])
        
        # Комиссия боту
        self.db.add_transaction(deal_id, 0, deal['commission'], "commission", "Комиссия бота")
        
        await query.edit_message_text(
            f"🎉 Деньги получены!\n\n"
            f"💰 Вы получили: {executor_amount} $\n"
            f"💸 Комиссия: {deal['commission']} $\n"
            f"💳 Баланс пополнен автоматически\n\n"
            f"Спасибо за работу!",
            reply_markup=Keyboards.get_main_menu()
        )
        
        # Уведомление заказчику
        try:
            await context.bot.send_message(
                deal['customer_id'],
                f"💰 Исполнитель получил оплату по сделке {deal_id}!\n\n"
                f"Сделка полностью завершена.",
                reply_markup=Keyboards.get_main_menu()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    
    async def finish_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершить сделку (универсальная функция)"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal:
            await query.answer("❌ Сделка не найдена!")
            return
        
        user_id = update.effective_user.id
        is_customer = deal['customer_id'] == user_id
        is_executor = deal['executor_id'] == user_id
        
        if not (is_customer or is_executor):
            await query.answer("❌ У вас нет доступа к этой сделке!")
            return
        
        # Проверяем статус сделки
        if deal['status'] == STATUS_PENDING:
            await query.answer("❌ Сделка еще не оплачена!")
            return
        elif deal['status'] == STATUS_PAID:
            # Если заказчик нажимает - предлагаем подтвердить выполнение
            if is_customer:
                await query.answer("❌ Сначала исполнитель должен начать работу!")
                return
            else:
                # Исполнитель может завершить работу
                await self.complete_work(update, context)
                return
        elif deal['status'] == STATUS_IN_PROGRESS:
            # Если заказчик нажимает - предлагаем подтвердить выполнение
            if is_customer:
                await query.answer("❌ Исполнитель еще работает!")
                return
            else:
                # Исполнитель может завершить работу
                await self.complete_work(update, context)
                return
        elif deal['status'] == STATUS_COMPLETED:
            # Если заказчик нажимает - подтверждаем выполнение
            if is_customer:
                await self.confirm_completion(update, context)
                return
            else:
                # Исполнитель может получить деньги
                await self.receive_payment(update, context)
                return
        elif deal['status'] == STATUS_DISPUTED:
            await query.answer("❌ Сделка в споре! Обратитесь к администратору.")
            return
        elif deal['status'] == STATUS_CANCELLED:
            await query.answer("❌ Сделка отменена!")
            return
    
    async def confirm_complete_work(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение завершения работы исполнителем"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['executor_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] not in [STATUS_PAID, STATUS_IN_PROGRESS]:
            await query.answer("❌ Работа не была начата!")
            return
        
        # Обновляем статус сделки
        self.db.update_deal_status(deal_id, STATUS_COMPLETED)
        
        # Показываем успешное завершение
        success_text = f"✅ Работа успешно завершена!\n\n"
        success_text += f"🆔 ID сделки: {deal_id}\n"
        success_text += f"💰 Сумма: {deal['amount']} $\n"
        success_text += f"📝 Описание: {deal['description']}\n"
        success_text += f"📊 Статус: Завершено\n\n"
        success_text += f"📧 Заказчик получил уведомление\n"
        success_text += f"⏳ Ожидайте подтверждения от заказчика\n"
        success_text += f"💰 После подтверждения вы получите: {deal['amount'] - deal['commission']} $"
        
        keyboard = [
            [InlineKeyboardButton("🔙 К сделке", callback_data=f"deal_{deal_id}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Уведомление заказчику
        try:
            notification_text = f"✅ Исполнитель завершил работу!\n\n"
            notification_text += f"🆔 ID сделки: {deal_id}\n"
            notification_text += f"💰 Сумма: {deal['amount']} $\n"
            notification_text += f"📝 Описание: {deal['description']}\n\n"
            notification_text += f"🔍 Проверьте качество выполненной работы\n"
            notification_text += f"✅ Подтвердите выполнение, если все в порядке"
            
            notification_keyboard = [
                [InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"confirm_completion_{deal_id}")],
                [InlineKeyboardButton("⚠️ Открыть спор", callback_data=f"open_dispute_{deal_id}")],
                [InlineKeyboardButton("🔙 К сделке", callback_data=f"deal_{deal_id}")]
            ]
            
            await context.bot.send_message(
                deal['customer_id'],
                notification_text,
                reply_markup=InlineKeyboardMarkup(notification_keyboard)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    
    async def final_confirm_completion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Финальное подтверждение выполнения работы заказчиком"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['customer_id'] != update.effective_user.id:
            await query.answer("❌ Ошибка доступа!")
            return
        
        if deal['status'] != STATUS_COMPLETED:
            await query.answer("❌ Работа не завершена!")
            return
        
        # Выплата исполнителю
        executor_amount = deal['amount'] - deal['commission']
        self.db.update_balance(deal['executor_id'], executor_amount)
        self.db.add_transaction(deal_id, deal['executor_id'], executor_amount, "payout", "Выплата исполнителю")
        
        # Отправка комиссии на указанный счет
        await self.send_commission_to_crypto_bot(deal_id, deal['commission'])
        
        # Комиссия боту
        self.db.add_transaction(deal_id, 0, deal['commission'], "commission", "Комиссия бота")
        
        # Показываем успешное завершение
        success_text = f"🎉 Сделка успешно завершена!\n\n"
        success_text += f"🆔 ID сделки: {deal_id}\n"
        success_text += f"💰 Сумма: {deal['amount']} $\n"
        success_text += f"📝 Описание: {deal['description']}\n"
        success_text += f"📊 Статус: Завершено\n\n"
        success_text += f"✅ Исполнитель получил: {executor_amount} $\n"
        success_text += f"💸 Комиссия: {deal['commission']} $\n\n"
        success_text += f"Спасибо за использование нашего сервиса!"
        
        keyboard = [
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Уведомление исполнителю
        try:
            notification_text = f"🎉 Сделка завершена!\n\n"
            notification_text += f"🆔 ID сделки: {deal_id}\n"
            notification_text += f"💰 Вы получили: {executor_amount} $\n"
            notification_text += f"💸 Комиссия: {deal['commission']} $\n"
            notification_text += f"💳 Баланс пополнен автоматически\n\n"
            notification_text += f"Спасибо за качественную работу!"
            
            notification_keyboard = [
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            
            await context.bot.send_message(
                deal['executor_id'],
                notification_text,
                reply_markup=InlineKeyboardMarkup(notification_keyboard)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
    
    async def open_dispute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Открыть спор по сделке"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal:
            await query.answer("❌ Сделка не найдена!")
            return
        
        user_id = update.effective_user.id
        if deal['customer_id'] != user_id and deal['executor_id'] != user_id:
            await query.answer("❌ У вас нет доступа к этой сделке!")
            return
        
        # Обновляем статус сделки на спор
        self.db.update_deal_status(deal_id, STATUS_DISPUTED)
        
        dispute_text = f"⚠️ Спор открыт по сделке {deal_id}\n\n"
        dispute_text += f"💰 Сумма: {deal['amount']} $\n"
        dispute_text += f"📝 Описание: {deal['description']}\n"
        dispute_text += f"📊 Статус: Спор\n\n"
        dispute_text += f"📞 Обратитесь к администратору для разрешения спора."
        
        keyboard = [
            [InlineKeyboardButton("📞 Связаться с админом", url="https://t.me/Ators13")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"deal_{deal_id}")]
        ]
        
        await query.edit_message_text(
            dispute_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Уведомление другому участнику
        other_user_id = deal['executor_id'] if deal['customer_id'] == user_id else deal['customer_id']
        try:
            await context.bot.send_message(
                other_user_id,
                f"⚠️ Открыт спор по сделке {deal_id}!\n\nОбратитесь к администратору.",
                reply_markup=Keyboards.get_main_menu()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о споре: {e}")
    
    async def show_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать баланс пользователя"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Получаем баланс пользователя
        balance = self.db.get_user_balance(user_id)
        currency_symbol = self.get_currency_symbol(user_id)
        
        balance_text = f"💳 Ваш баланс: {balance} {currency_symbol}\n\n💡 Баланс пополняется после завершения сделок в качестве исполнителя."
    
    async def request_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос username для отправки сделки"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        context.user_data['deal_id'] = deal_id
        
        await query.edit_message_text(
            "👤 Введите username пользователя (без @):",
            reply_markup=Keyboards.get_cancel_keyboard()
        )
        return WAITING_FOR_USERNAME
    
    async def get_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение username для предложения сделки исполнителю"""
        username = update.message.text.strip()
        deal_id = context.user_data.get('deal_id')
        
        if not username:
            await update.message.reply_text("❌ Username не может быть пустым!")
            return WAITING_FOR_USERNAME
        
        # Убираем @ если есть
        if username.startswith('@'):
            username = username[1:]
        
        # Находим пользователя по username
        user = self.db.get_user_by_username(username)
        if not user:
            await update.message.reply_text("❌ Пользователь с таким username не найден!")
            return WAITING_FOR_USERNAME
        
        # Создаём предложение сделки
        offer_id = self.db.create_deal_offer(deal_id, update.effective_user.id, user['user_id'])
        
        # Уведомляем исполнителя с кнопками
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"accept_offered_deal_{offer_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_offered_deal_{offer_id}")
            ]
        ])
        try:
            await context.bot.send_message(
                user['user_id'],
                f"📨 Вам поступило предложение сделки!\n\nID: {deal_id}\nПосмотрите детали и примите решение:",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f'Ошибка при отправке предложения исполнителю: {e}')
            await update.message.reply_text(
            f"✅ Сделка {deal_id} предложена исполнителю @{username}",
                reply_markup=Keyboards.get_main_menu()
            )
        context.user_data.clear()
        return ConversationHandler.END
    
    async def request_executor_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос username исполнителя"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        context.user_data['deal_id'] = deal_id
        
        await query.edit_message_text(
            "👷 Введите username исполнителя (без @):",
            reply_markup=Keyboards.get_cancel_keyboard()
        )
        return WAITING_FOR_USERNAME
    
    async def get_executor_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение username исполнителя"""
        username = update.message.text.strip()
        deal_id = context.user_data.get('deal_id')
        
        if not username:
            await update.message.reply_text("❌ Username не может быть пустым!")
            return WAITING_FOR_USERNAME
        
        # Убираем @ если есть
        if username.startswith('@'):
            username = username[1:]
        
        # Находим пользователя по username
        user = self.db.get_user_by_username(username)
        if not user:
            await update.message.reply_text("❌ Пользователь с таким username не найден!")
            return WAITING_FOR_USERNAME
        
        # Назначаем исполнителя
        success = self.db.assign_executor(deal_id, user['id'])
        
        if success:
            await update.message.reply_text(
                f"✅ Исполнитель @{username} назначен для сделки {deal_id}",
                reply_markup=Keyboards.get_main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при назначении исполнителя!",
                reply_markup=Keyboards.get_main_menu()
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def request_offer_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запрос username для предложения сделки"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        context.user_data['deal_id'] = deal_id
        
        await query.edit_message_text(
            "👤 Введите username пользователя для предложения сделки (без @):",
            reply_markup=Keyboards.get_cancel_keyboard()
        )
        return WAITING_FOR_USERNAME
    
    async def get_offer_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение username для предложения сделки"""
        username = update.message.text.strip()
        deal_id = context.user_data.get('deal_id')
        if not username:
            await update.message.reply_text("❌ Username не может быть пустым!")
            return WAITING_FOR_USERNAME
        # Убираем @ если есть
        if username.startswith('@'):
            username = username[1:]
        # Находим пользователя по username
        user = self.db.get_user_by_username(username)
        if not user:
            await update.message.reply_text("❌ Пользователь с таким username не найден!")
            return WAITING_FOR_USERNAME
        # Предлагаем сделку
        success = self.db.offer_deal(deal_id, update.effective_user.id, user['id'])
        if success:
            # Уведомляем заказчика (отправителя)
            try:
                await context.bot.send_message(
                    update.effective_user.id,
                    f"✅ Ваше предложение сделки отправлено пользователю @{username}!"
                )
            except Exception:
                pass
            # Уведомляем получателя (исполнителя)
            try:
                await context.bot.send_message(
                    user['id'],
                    f"📨 Вам поступило предложение сделки от пользователя @{update.effective_user.username or update.effective_user.id} (ID: {deal_id})"
                )
            except Exception:
                pass
            await update.message.reply_text(
                f"✅ Сделка {deal_id} предложена пользователю @{username}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при предложении сделки!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
            )
        context.user_data.clear()
        return ConversationHandler.END
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        message = update.effective_message
        chat = message.chat
        # Если это админ и он в режиме поиска сделки — вызываем обработчик поиска
        if update.effective_user.id in ADMIN_IDS and context.user_data.get('admin_state') == 'waiting_deal_id':
            await self.admin_panel.handle_deal_search(update, context)
            return
        # Только для групп/каналов
        if chat.type != 'private':
            if '@Almazov_guarantor_robot' not in message.text:
                try:
                    # Формируем упоминание пользователя
                    user = message.from_user
                    mention = user.mention_html() if hasattr(user, 'mention_html') else f"<a href='tg://user?id={user.id}'>пользователь</a>"
                    await context.bot.send_message(
                        chat.id,
                        f"{mention}, чтобы написать в этот чат, обязательно укажите @Almazov_guarantor_robot в сообщении!",
                        reply_to_message_id=message.message_id,
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
                try:
                    await message.delete()
                except Exception:
                    pass
                return
        # В личных чатах или если всё ок — ничего не делаем
        pass
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ошибок"""
        logger.error(f"Ошибка в боте: {context.error}")
        
        # Отправляем сообщение пользователю об ошибке
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору.",
                reply_markup=Keyboards.get_main_menu()
            )
    
    def run(self):
        """Запуск бота"""
        print("🚀 Запускаю бота...")
        self.application.run_polling()
    
    async def show_available_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать доступные заказы для исполнителей"""
        query = update.callback_query
        deals = self.db.get_available_deals()
        
        if not deals:
            await query.edit_message_text(
                "🔍 Нет доступных заказов.\n\nВсе заказы уже приняты или находятся в работе.",
                reply_markup=Keyboards.get_main_menu()
            )
            return
        
        deals_text = "🔍 Доступные заказы:\n\n"
        for i, deal in enumerate(deals[:10], 1):  # Показываем только первые 10 заказов
            deals_text += f"📋 Заказ #{i}\n"
            deals_text += f"💰 Сумма: {deal['amount']} $\n"
            deals_text += f"📝 {deal['description'][:50]}...\n"
            deals_text += f"👤 Заказчик: {deal.get('customer_name', 'Неизвестно')}\n"
            deals_text += f"📅 Создан: {deal['created_at']}\n\n"
        
        keyboard = []
        for i, deal in enumerate(deals[:10], 1):
            keyboard.append([InlineKeyboardButton(
                f"Заказ #{i} - {deal['amount']} $", 
                callback_data=f"view_deal_{deal['deal_id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await query.edit_message_text(
            deals_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def view_available_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать детали доступного заказа"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        
        deal = self.db.get_deal(deal_id)
        if not deal or deal['status'] != STATUS_PENDING or deal['executor_id'] is not None:
            await query.edit_message_text("❌ Заказ недоступен!", reply_markup=Keyboards.get_main_menu())
            return
        
        # Получаем информацию о заказчике
        customer = self.db.get_user(deal['customer_id'])
        customer_name = customer.get('first_name', 'Неизвестно') if customer else 'Неизвестно'
        customer_username = customer.get('username', 'Без username') if customer else 'Без username'
        
        deal_text = f"📋 Заказ {deal_id}\n\n"
        deal_text += f"💰 Сумма: {deal['amount']} $\n"
        deal_text += f"💸 Комиссия: {deal['commission']} $\n"
        deal_text += f"📝 Описание: {deal['description']}\n"
        deal_text += f"📊 Статус: Ожидает исполнителя\n"
        deal_text += f"📅 Создан: {deal['created_at']}\n"
        deal_text += f"👤 Заказчик: {customer_name} (@{customer_username})\n\n"
        deal_text += f"💡 Если вы готовы выполнить этот заказ, нажмите 'Принять заказ'"
        
        keyboard = [
            [InlineKeyboardButton("✅ Принять заказ", callback_data=f"accept_deal_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="available_deals")]
        ]
        
        await query.edit_message_text(
            deal_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def accept_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принятие заказа исполнителем"""
        query = update.callback_query
        deal_id = query.data.split("_", 2)[2]
        user_id = update.effective_user.id
        
        # Проверяем, что заказ доступен
        deal = self.db.get_deal(deal_id)
        if not deal or deal['status'] != STATUS_PENDING or deal['executor_id'] is not None:
            await query.edit_message_text("❌ Заказ недоступен!", reply_markup=Keyboards.get_main_menu())
            return
        
        # Принимаем заказ
        success = self.db.accept_deal(deal_id, user_id)
        
        if success:
            # Уведомляем заказчика
            try:
                await context.bot.send_message(
                    deal['customer_id'],
                    f"✅ Ваш заказ {deal_id} принят исполнителем!\n\nОжидайте оплаты для начала работы."
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить заказчика: {e}")
            
            await query.edit_message_text(
                f"✅ Заказ {deal_id} успешно принят!\n\nОжидайте оплаты от заказчика для начала работы.",
                reply_markup=Keyboards.get_main_menu()
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при принятии заказа!",
                reply_markup=Keyboards.get_main_menu()
            )
    
    async def show_deal_offers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать предложения сделок"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Получаем предложения для пользователя
        offers = self.db.get_user_deal_offers(user_id, 'pending')
        
        if not offers:
            await query.edit_message_text(
                "📨 У вас нет предложений сделок.",
                reply_markup=Keyboards.get_main_menu()
            )
            return
        
        offers_text = "📨 Предложения сделок:\n\n"
        for i, offer in enumerate(offers[:5], 1):
            deal = self.db.get_deal(offer['deal_id'])
            if deal:
                offers_text += f"📋 Предложение #{i}\n"
                offers_text += f"💰 Сумма: {deal['amount']} $\n"
                offers_text += f"📝 {deal['description'][:50]}...\n"
                offers_text += f"📅 Получено: {offer['created_at']}\n\n"
        
        keyboard = []
        for i, offer in enumerate(offers[:5], 1):
            keyboard.append([InlineKeyboardButton(
                f"Предложение #{i}", 
                callback_data=f"view_offer_{offer['offer_id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        
        await query.edit_message_text(
            offers_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_my_offers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать мои предложения сделок"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Получаем предложения, отправленные пользователем
        offers = self.db.get_user_deal_offers(user_id, 'pending')
        
        if not offers:
            await query.edit_message_text(
                "📨 Вы не отправляли предложений сделок.",
                reply_markup=Keyboards.get_main_menu()
            )
            return
        
        offers_text = "📨 Мои предложения сделок:\n\n"
        for i, offer in enumerate(offers[:5], 1):
            deal = self.db.get_deal(offer['deal_id'])
            if deal:
                offers_text += f"📋 Предложение #{i}\n"
                offers_text += f"💰 Сумма: {deal['amount']} $\n"
                offers_text += f"📝 {deal['description'][:50]}...\n"
                offers_text += f"📅 Отправлено: {offer['created_at']}\n"
                offers_text += f"📊 Статус: {self.get_status_translation(offer['status'])}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        
        await query.edit_message_text(
            offers_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def accept_offered_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка принятия предложения сделки исполнителем"""
        query = update.callback_query
        offer_id = query.data.split('_', 3)[3]
        offer = self.db.get_deal_offer(offer_id)
        if not offer or offer['status'] != 'pending':
            await query.edit_message_text(
                "❌ Предложение недоступно!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
            )
            return
        deal_id = offer['deal_id']
        executor_id = offer['to_user_id']
        customer_id = offer['from_user_id']
        # Сначала обновляем статус предложения
        self.db.update_deal_offer_status(offer_id, 'accepted')
        # Назначаем исполнителя
        success = self.db.assign_executor(deal_id, executor_id)
        if success:
            # Уведомляем обе стороны
            try:
                await context.bot.send_message(
                    executor_id,
                    f"✅ Вы приняли предложение и назначены исполнителем сделки!\nID: {deal_id}"
                )
                await context.bot.send_message(
                    customer_id,
                    f"✅ Ваше предложение сделки принято исполнителем!\nID: {deal_id}"
                )
            except Exception as e:
                logger.error(f'Ошибка при уведомлении сторон: {e}')
            await query.edit_message_text(
                "✅ Вы приняли предложение!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
            )
        else:
            await query.edit_message_text(
                "❌ Не удалось назначить исполнителя",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
            )
    
    async def reject_offered_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка отклонения предложения сделки исполнителем"""
        query = update.callback_query
        offer_id = query.data.split('_', 3)[3]
        offer = self.db.get_deal_offer(offer_id)
        if not offer:
            await query.answer("❌ Предложение не найдено", show_alert=True)
            return
        deal_id = offer['deal_id']
        executor_id = offer['to_user_id']
        customer_id = offer['from_user_id']
        self.db.update_deal_offer_status(offer_id, 'rejected')
        # Уведомляем обе стороны
        try:
            await context.bot.send_message(
                executor_id,
                f"❌ Вы отклонили предложение сделки.\nID: {deal_id}"
            )
            await context.bot.send_message(
                customer_id,
                f"❌ Ваше предложение сделки было отклонено исполнителем.\nID: {deal_id}"
            )
        except Exception as e:
            logger.error(f'Ошибка при уведомлении сторон: {e}')
        await query.edit_message_text(
            "❌ Вы отклонили предложение",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
        )
    
    async def accept_deal_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принятие предложения сделки"""
        query = update.callback_query
        offer_id = query.data.split("_", 2)[2]
        
        offer = self.db.get_deal_offer(offer_id)
        if not offer or offer['status'] != 'pending':
            await query.edit_message_text("❌ Предложение недоступно!", reply_markup=Keyboards.get_main_menu())
            return
        
        # Принимаем предложение
        success = self.db.accept_deal(offer['deal_id'], offer['to_user_id'])
        
        if success:
            # Обновляем статус предложения
            self.db.update_deal_offer_status(offer_id, 'accepted')
            
            await query.edit_message_text(
                f"✅ Предложение сделки принято!\n\nОжидайте оплаты от заказчика.",
                reply_markup=Keyboards.get_main_menu()
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при принятии предложения!",
                reply_markup=Keyboards.get_main_menu()
            )
    
    async def reject_deal_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отклонение предложения сделки"""
        query = update.callback_query
        offer_id = query.data.split("_", 2)[2]
        
        offer = self.db.get_deal_offer(offer_id)
        if not offer or offer['status'] != 'pending':
            await query.edit_message_text("❌ Предложение недоступно!", reply_markup=Keyboards.get_main_menu())
            return
        
        # Отклоняем предложение
        self.db.update_deal_offer_status(offer_id, 'rejected')
        
        await query.edit_message_text(
            "❌ Предложение сделки отклонено.",
            reply_markup=Keyboards.get_main_menu()
        )
    
    async def show_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о поддержке"""
        query = update.callback_query
        
        support_text = "📞 Поддержка\n\n"
        support_text += "🔧 Если у вас возникли вопросы или проблемы:\n\n"
        support_text += "👤 Администратор: @m1ras18\n"
        support_text += "📧 Email: support@garant-bot.com\n"
        support_text += "🌐 Сайт: https://garant-bot.com\n\n"
        support_text += "💡 Часто задаваемые вопросы:\n"
        support_text += "• Как создать сделку?\n"
        support_text += "• Как оплатить заказ?\n"
        support_text += "• Что делать при споре?\n"
        support_text += "• Как получить деньги?\n\n"
        support_text += "📋 Для получения помощи нажмите 'Связаться с админом'"
        
        keyboard = [
            [InlineKeyboardButton("👤 Связаться с админом", url="https://t.me/m1ras18")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            support_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    
    async def show_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о пополнении баланса"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        balance = self.db.get_user_balance(user_id)
        
        deposit_text = f"💰 Пополнение баланса\n\n"
        deposit_text += f"💳 Текущий баланс: {balance} $\n\n"
        deposit_text += "💡 Баланс пополняется автоматически после завершения сделок в качестве исполнителя.\n\n"
        deposit_text += "📋 Для пополнения баланса:\n"
        deposit_text += "1. Выполните заказ как исполнитель\n"
        deposit_text += "2. Дождитесь подтверждения от заказчика\n"
        deposit_text += "3. Получите оплату на баланс\n\n"
        deposit_text += "⚠️ Ручное пополнение баланса не предусмотрено."
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            deposit_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать уведомления пользователя"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        notifications = self.db.get_user_notifications(user_id, unread_only=False)
        
        if not notifications:
            await query.edit_message_text(
                "🔔 У вас нет уведомлений.",
                reply_markup=Keyboards.get_main_menu()
            )
            return
        
        notifications_text = "🔔 Ваши уведомления:\n\n"
        for i, notification in enumerate(notifications[:10], 1):
            status_icon = "🔴" if not notification['is_read'] else "⚪"
            notifications_text += f"{status_icon} {notification['message']}\n"
            notifications_text += f"📅 {notification['created_at']}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("📖 Отметить все как прочитанные", callback_data="mark_all_read")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            notifications_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def mark_all_notifications_read(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить все уведомления как прочитанные"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        self.db.mark_all_notifications_read(user_id)
        
        await query.edit_message_text(
            "✅ Все уведомления отмечены как прочитанные!",
            reply_markup=Keyboards.get_main_menu()
        )