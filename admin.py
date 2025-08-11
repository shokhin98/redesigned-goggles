import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from config import ADMIN_IDS, STATUS_CANCELLED

logger = logging.getLogger(__name__)

class AdminPanel:
    def __init__(self, db: Database):
        self.db = db
    
    def get_status_translation(self, status: str) -> str:
        """Перевод статуса сделки на русский язык"""
        status_translations = {
            'pending': "Ожидает оплаты",
            'paid': "Оплачено",
            'in_progress': "В работе",
            'completed': "Завершено",
            'disputed': "Спор",
            'cancelled': "Отменено"
        }
        return status_translations.get(status, status)
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        return user_id in ADMIN_IDS
    
    async def handle_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка админской команды /admin"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет доступа к админ-панели!")
            return
        
        await update.message.reply_text(
            "🔧 Админ-панель\n\nВыберите действие:",
            reply_markup=self.get_admin_keyboard()
        )
    
    def get_admin_keyboard(self):
        """Админская клавиатура"""
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("💰 Все сделки", callback_data="admin_deals")],
            [InlineKeyboardButton("🔍 Найти сделку", callback_data="admin_find_deal")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка админских callback"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("❌ У вас нет доступа к админ-панели!")
            return
        
        if query.data == "admin_stats":
            await self.show_stats(update, context)
        elif query.data == "admin_users":
            await self.show_users(update, context)
        elif query.data == "admin_deals":
            await self.show_deals(update, context)
        elif query.data == "admin_find_deal":
            await self.show_find_deal(update, context)
        elif query.data == "admin_settings":
            await self.show_settings(update, context)
        elif query.data.startswith("admin_deal_"):
            deal_id = query.data.replace("admin_deal_", "")
            await self.show_deal_details(update, context, deal_id)
        elif query.data.startswith("admin_resolve_customer_"):
            deal_id = query.data.replace("admin_resolve_customer_", "")
            await self.resolve_dispute(deal_id, "customer", context)
            await query.edit_message_text("✅ Спор решен в пользу заказчика!", reply_markup=self.get_admin_keyboard())
        elif query.data.startswith("admin_resolve_executor_"):
            deal_id = query.data.replace("admin_resolve_executor_", "")
            await self.resolve_dispute(deal_id, "executor", context)
            await query.edit_message_text("✅ Спор решен в пользу исполнителя!", reply_markup=self.get_admin_keyboard())
        elif query.data == "admin_clear_completed":
            await self.show_clear_completed_confirmation(update, context)
        elif query.data == "admin_clear_completed_confirm":
            await self.clear_completed_deals(update, context)
        elif query.data == "admin_panel":
            await query.edit_message_text(
                "🔧 Админ-панель\n\nВыберите действие:",
                reply_markup=self.get_admin_keyboard()
            )
        elif query.data == "admin_settings":
            await self.show_settings(update, context)
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику"""
        query = update.callback_query
        
        # Получаем статистику из базы данных
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Общее количество сделок
            cursor.execute("SELECT COUNT(*) FROM deals")
            total_deals = cursor.fetchone()[0]
            
            # Сделки по статусам
            cursor.execute("SELECT status, COUNT(*) FROM deals GROUP BY status")
            deals_by_status = dict(cursor.fetchall())
            
            # Общая сумма всех сделок
            cursor.execute("SELECT SUM(amount) FROM deals")
            total_amount = cursor.fetchone()[0] or 0
            
            # Общая комиссия
            cursor.execute("SELECT SUM(commission) FROM deals")
            total_commission = cursor.fetchone()[0] or 0
        
        stats_text = "📊 Статистика бота\n\n"
        stats_text += f"👥 Всего пользователей: {total_users}\n"
        stats_text += f"💰 Всего сделок: {total_deals}\n"
        stats_text += f"💵 Общая сумма: {total_amount:.2f} руб.\n"
        stats_text += f"💸 Общая комиссия: {total_commission:.2f} руб.\n\n"
        
        stats_text += "📈 Сделки по статусам:\n"
        for status, count in deals_by_status.items():
            emoji = {
                'pending': '⏳',
                'paid': '💰',
                'in_progress': '🚀',
                'completed': '✅',
                'disputed': '⚠️',
                'cancelled': '❌'
            }.get(status, '❓')
            status_ru = self.get_status_translation(status)
            stats_text += f"{emoji} {status_ru}: {count}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список пользователей"""
        query = update.callback_query
        
        # Получаем пользователей
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, balance, created_at 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            users = cursor.fetchall()
        
        users_text = "👥 Последние 10 пользователей\n\n"
        
        for user in users:
            user_id, username, first_name, balance, created_at = user
            users_text += f"🆔 ID: {user_id}\n"
            users_text += f"👤 Имя: {first_name or 'Не указано'}\n"
            users_text += f"📛 Username: @{username or 'Не указан'}\n"
            users_text += f"💳 Баланс: {balance:.2f} руб.\n"
            users_text += f"📅 Регистрация: {created_at}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_users")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(users_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список сделок"""
        query = update.callback_query
        
        # Получаем сделки
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.deal_id, d.amount, d.commission, d.status, d.created_at,
                       c.first_name as customer_name, e.first_name as executor_name
                FROM deals d
                JOIN users c ON d.customer_id = c.user_id
                JOIN users e ON d.executor_id = e.user_id
                ORDER BY d.created_at DESC 
                LIMIT 10
            """)
            deals = cursor.fetchall()
        
        deals_text = "💰 Последние 10 сделок\n\n"
        
        for deal in deals:
            deal_id, amount, commission, status, created_at, customer_name, executor_name = deal
            status_emoji = {
                'pending': '⏳',
                'paid': '💰',
                'in_progress': '🚀',
                'completed': '✅',
                'disputed': '⚠️',
                'cancelled': '❌'
            }.get(status, '❓')
            
            deals_text += f"{status_emoji} Сделка {deal_id[:8]}...\n"
            deals_text += f"💰 Сумма: {amount} руб.\n"
            deals_text += f"💸 Комиссия: {commission} руб.\n"
            deals_text += f"👤 Заказчик: {customer_name}\n"
            deals_text += f"👷 Исполнитель: {executor_name}\n"
            deals_text += f"📊 Статус: {self.get_status_translation(status)}\n"
            deals_text += f"📅 Создана: {created_at}\n\n"
        
        # Создаем клавиатуру с кнопками для каждой сделки
        keyboard = []
        for deal in deals:
            deal_id = deal[0]
            status_emoji = {
                'pending': '⏳',
                'paid': '💰',
                'in_progress': '🚀',
                'completed': '✅',
                'disputed': '⚠️',
                'cancelled': '❌'
            }.get(deal[3], '❓')
            keyboard.append([InlineKeyboardButton(f"{status_emoji} Сделка {deal_id[:8]}...", callback_data=f"admin_deal_{deal_id}")])
        
        keyboard.extend([
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_deals")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ])
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_deals")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(deals_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать настройки"""
        query = update.callback_query
        
        # Получаем статистику по сделкам
        completed_count = self.db.get_completed_deals_count()
        active_count = self.db.get_active_deals_count()
        
        settings_text = "⚙️ Настройки бота\n\n"
        settings_text += f"💰 Комиссия: 40%\n"
        settings_text += f"🔧 Версия: 1.0.0\n"
        settings_text += f"📊 База данных: SQLite\n"
        settings_text += f"🤖 Статус: Работает\n\n"
        settings_text += f"📈 Статистика сделок:\n"
        settings_text += f"✅ Выполненных: {completed_count}\n"
        settings_text += f"🔄 Активных: {active_count}\n\n"
        settings_text += "Для изменения настроек обратитесь к разработчику."
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить выполненные сделки", callback_data="admin_clear_completed")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(settings_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_find_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать форму поиска сделки"""
        query = update.callback_query
        
        find_text = "🔍 Поиск сделки по номеру\n\n"
        find_text += "📝 Введите номер сделки (ID):\n"
        find_text += "Пример: abc123def456\n\n"
        find_text += "💡 Подсказка: Номер сделки можно найти в уведомлениях или в списке сделок."
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(find_text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Сохраняем состояние для ожидания ввода номера сделки
        context.user_data['admin_state'] = 'waiting_deal_id'
    
    async def handle_deal_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка поиска сделки по номеру"""
        if not self.is_admin(update.effective_user.id):
            return
        
        if context.user_data.get('admin_state') != 'waiting_deal_id':
            return
        
        deal_id = update.message.text.strip()
        
        # Очищаем состояние
        context.user_data['admin_state'] = None
        
        # Ищем сделку
        deal = self.db.get_deal(deal_id)
        if not deal:
            await update.message.reply_text(
                "❌ Сделка с таким номером не найдена!\n\n"
                "Проверьте правильность номера и попробуйте снова.",
                reply_markup=self.get_admin_keyboard()
            )
            return
        
        # Показываем детали сделки
        await self.show_deal_details_admin(update, context, deal)
    
    async def show_deal_details_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, deal: dict):
        """Показать детали сделки для администратора"""
        # Получаем информацию о пользователях
        customer = self.db.get_user(deal['customer_id'])
        executor = self.db.get_user(deal['executor_id']) if deal['executor_id'] else None
        
        customer_name = customer['first_name'] if customer and customer['first_name'] else "Неизвестно"
        customer_username = customer['username'] if customer and customer['username'] else "Не указан"
        
        executor_name = executor['first_name'] if executor and executor['first_name'] else "Не назначен"
        executor_username = executor['username'] if executor and executor['username'] else "Не указан"
        
        # Статус с эмодзи
        status_emoji = {
            'pending': '⏳',
            'paid': '💰',
            'in_progress': '🚀',
            'completed': '✅',
            'disputed': '⚠️',
            'cancelled': '❌'
        }.get(deal['status'], '❓')
        
        deal_text = f"🔍 Детали сделки\n\n"
        deal_text += f"🆔 ID: {deal['deal_id']}\n"
        deal_text += f"💰 Сумма: {deal['amount']} руб.\n"
        deal_text += f"💸 Комиссия: {deal['commission']} руб.\n"
        deal_text += f"📝 Описание: {deal['description']}\n"
        deal_text += f"📊 Статус: {status_emoji} {self.get_status_translation(deal['status'])}\n"
        deal_text += f"📅 Создана: {deal['created_at']}\n\n"
        
        deal_text += f"👤 Заказчик:\n"
        deal_text += f"   ID: {deal['customer_id']}\n"
        deal_text += f"   Имя: {customer_name}\n"
        deal_text += f"   Username: @{customer_username}\n\n"
        
        deal_text += f"👷 Исполнитель:\n"
        deal_text += f"   ID: {deal['executor_id'] or 'Не назначен'}\n"
        deal_text += f"   Имя: {executor_name}\n"
        deal_text += f"   Username: @{executor_username}\n\n"
        
        # Кнопки действий
        keyboard = []
        
        if deal['status'] == 'disputed':
            keyboard.append([
                InlineKeyboardButton("✅ Решить в пользу заказчика", callback_data=f"admin_resolve_customer_{deal['deal_id']}"),
                InlineKeyboardButton("✅ Решить в пользу исполнителя", callback_data=f"admin_resolve_executor_{deal['deal_id']}")
            ])
        
        keyboard.extend([
            [InlineKeyboardButton("📞 Написать заказчику", url=f"https://t.me/{customer_username}")],
            [InlineKeyboardButton("📞 Написать исполнителю", url=f"https://t.me/{executor_username}")] if executor_username != "Не указан" else [],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_find_deal")]
        ])
        
        # Убираем пустые строки
        keyboard = [row for row in keyboard if row]
        
        await update.message.reply_text(
            deal_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_deal_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE, deal_id: str):
        """Показать детали сделки из списка"""
        query = update.callback_query
        
        deal = self.db.get_deal(deal_id)
        if not deal:
            await query.edit_message_text(
                "❌ Сделка не найдена!",
                reply_markup=self.get_admin_keyboard()
            )
            return
        
        # Получаем информацию о пользователях
        customer = self.db.get_user(deal['customer_id'])
        executor = self.db.get_user(deal['executor_id']) if deal['executor_id'] else None
        
        customer_name = customer['first_name'] if customer and customer['first_name'] else "Неизвестно"
        customer_username = customer['username'] if customer and customer['username'] else "Не указан"
        
        executor_name = executor['first_name'] if executor and executor['first_name'] else "Не назначен"
        executor_username = executor['username'] if executor and executor['username'] else "Не указан"
        
        # Статус с эмодзи
        status_emoji = {
            'pending': '⏳',
            'paid': '💰',
            'in_progress': '🚀',
            'completed': '✅',
            'disputed': '⚠️',
            'cancelled': '❌'
        }.get(deal['status'], '❓')
        
        deal_text = f"🔍 Детали сделки\n\n"
        deal_text += f"🆔 ID: {deal['deal_id']}\n"
        deal_text += f"💰 Сумма: {deal['amount']} руб.\n"
        deal_text += f"💸 Комиссия: {deal['commission']} руб.\n"
        deal_text += f"📝 Описание: {deal['description']}\n"
        deal_text += f"📊 Статус: {status_emoji} {self.get_status_translation(deal['status'])}\n"
        deal_text += f"📅 Создана: {deal['created_at']}\n\n"
        
        deal_text += f"👤 Заказчик:\n"
        deal_text += f"   ID: {deal['customer_id']}\n"
        deal_text += f"   Имя: {customer_name}\n"
        deal_text += f"   Username: @{customer_username}\n\n"
        
        deal_text += f"👷 Исполнитель:\n"
        deal_text += f"   ID: {deal['executor_id'] or 'Не назначен'}\n"
        deal_text += f"   Имя: {executor_name}\n"
        deal_text += f"   Username: @{executor_username}\n\n"
        
        # Кнопки действий
        keyboard = []
        
        if deal['status'] == 'disputed':
            keyboard.append([
                InlineKeyboardButton("✅ Решить в пользу заказчика", callback_data=f"admin_resolve_customer_{deal['deal_id']}"),
                InlineKeyboardButton("✅ Решить в пользу исполнителя", callback_data=f"admin_resolve_executor_{deal['deal_id']}")
            ])
        
        keyboard.extend([
            [InlineKeyboardButton("📞 Написать заказчику", url=f"https://t.me/{customer_username}")],
            [InlineKeyboardButton("📞 Написать исполнителю", url=f"https://t.me/{executor_username}")] if executor_username != "Не указан" else [],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_deals")]
        ])
        
        # Убираем пустые строки
        keyboard = [row for row in keyboard if row]
        
        await query.edit_message_text(
            deal_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_clear_completed_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать подтверждение очистки выполненных сделок"""
        query = update.callback_query
        
        completed_count = self.db.get_completed_deals_count()
        active_count = self.db.get_active_deals_count()
        
        if completed_count == 0:
            await query.edit_message_text(
                "ℹ️ Нет выполненных сделок для очистки!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]
                ])
            )
            return
        
        confirmation_text = "🗑️ Очистка выполненных сделок\n\n"
        confirmation_text += f"⚠️ Внимание! Это действие нельзя отменить!\n\n"
        confirmation_text += f"📊 Статистика:\n"
        confirmation_text += f"✅ Выполненных сделок: {completed_count}\n"
        confirmation_text += f"🔄 Активных сделок: {active_count} (не будут затронуты)\n\n"
        confirmation_text += f"🗑️ Будет удалено:\n"
        confirmation_text += f"• {completed_count} выполненных сделок\n"
        confirmation_text += f"• Все сообщения этих сделок\n"
        confirmation_text += f"• Все транзакции этих сделок\n"
        confirmation_text += f"• Все уведомления этих сделок\n"
        confirmation_text += f"• Все инвойсы этих сделок\n"
        confirmation_text += f"• Все предложения этих сделок\n\n"
        confirmation_text += f"🔒 Активные сделки останутся нетронутыми.\n\n"
        confirmation_text += f"Вы уверены, что хотите продолжить?"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="admin_clear_completed_confirm"),
                InlineKeyboardButton("❌ Отмена", callback_data="admin_settings")
            ]
        ]
        
        await query.edit_message_text(confirmation_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def clear_completed_deals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выполнить очистку выполненных сделок"""
        query = update.callback_query
        
        try:
            # Выполняем очистку
            deleted_count = self.db.clear_completed_deals()
            
            result_text = "✅ Очистка выполненных сделок завершена!\n\n"
            result_text += f"🗑️ Удалено сделок: {deleted_count}\n"
            result_text += f"🔄 Активные сделки остались нетронутыми\n\n"
            result_text += f"📊 Обновленная статистика:\n"
            result_text += f"✅ Выполненных: {self.db.get_completed_deals_count()}\n"
            result_text += f"🔄 Активных: {self.db.get_active_deals_count()}\n\n"
            result_text += f"🎉 База данных очищена от старых данных!"
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад в настройки", callback_data="admin_settings")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"Ошибка при очистке выполненных сделок: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при очистке сделок!\n\n"
                f"Ошибка: {str(e)}\n\n"
                "Попробуйте позже или обратитесь к разработчику.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="admin_settings")]
                ])
            )
    
    async def resolve_dispute(self, deal_id: str, resolution: str, context: ContextTypes.DEFAULT_TYPE):
        """Разрешить спор с автоматическим выводом средств через CryptoPay"""
        from crypto_bot_api import crypto_api
        deal = self.db.get_deal(deal_id)
        if not deal:
            return False

        # Получаем crypto user_id для заказчика и исполнителя (должен быть сохранён при оплате)
        customer_crypto_id = deal.get('customer_payment_address')
        executor_crypto_id = deal.get('executor_payment_address')
        amount = deal['amount']
        commission = deal['commission']

        if resolution == "customer":
            # Возврат денег заказчику
            if customer_crypto_id and str(customer_crypto_id).isdigit():
                # Автоматический вывод через CryptoPay
                success = crypto_api.transfer(str(customer_crypto_id), amount, "USDT", f"refund_{deal_id}")
                if success:
                    self.db.add_transaction(deal_id, deal['customer_id'], amount, "refund", "Автоматический возврат через CryptoPay")
                else:
                    self.db.update_balance(deal['customer_id'], amount)
                    self.db.add_transaction(deal_id, deal['customer_id'], amount, "refund", "Возврат на внутренний баланс (ошибка CryptoPay)")
            else:
                self.db.update_balance(deal['customer_id'], amount)
                self.db.add_transaction(deal_id, deal['customer_id'], amount, "refund", "Возврат на внутренний баланс (нет crypto user_id)")
        elif resolution == "executor":
            # Выплата исполнителю
            executor_amount = amount - commission
            if executor_crypto_id and str(executor_crypto_id).isdigit():
                success = crypto_api.transfer(str(executor_crypto_id), executor_amount, "USDT", f"payout_{deal_id}")
                if success:
                    self.db.add_transaction(deal_id, deal['executor_id'], executor_amount, "payout", "Автоматическая выплата через CryptoPay")
                else:
                    self.db.update_balance(deal['executor_id'], executor_amount)
                    self.db.add_transaction(deal_id, deal['executor_id'], executor_amount, "payout", "Выплата на внутренний баланс (ошибка CryptoPay)")
            else:
                self.db.update_balance(deal['executor_id'], executor_amount)
                self.db.add_transaction(deal_id, deal['executor_id'], executor_amount, "payout", "Выплата на внутренний баланс (нет crypto user_id)")

        self.db.update_deal_status(deal_id, STATUS_CANCELLED)

        # Уведомления участникам
        try:
            await context.bot.send_message(
                deal['customer_id'],
                f"⚠️ Спор по сделке {deal_id} разрешен администратором."
            )
            await context.bot.send_message(
                deal['executor_id'],
                f"⚠️ Спор по сделке {deal_id} разрешен администратором."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомления о разрешении спора: {e}")

        return True 