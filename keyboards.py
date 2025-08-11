from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

class Keyboards:
    @staticmethod
    def get_main_menu(unread_count: int = 0):
        """Главное меню"""
        notification_text = f"🔔 Уведомления ({unread_count})" if unread_count > 0 else "🔔 Уведомления"
        keyboard = [
            [InlineKeyboardButton("💰 Создать сделку", callback_data="create_deal")],
            [InlineKeyboardButton("📋 Мои сделки", callback_data="my_deals")],
            [InlineKeyboardButton("🔍 Доступные заказы", callback_data="available_deals")],
            [InlineKeyboardButton("📨 Предложения сделок", callback_data="deal_offers")],
            [InlineKeyboardButton(notification_text, callback_data="notifications")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_notifications_keyboard():
        """Клавиатура для уведомлений"""
        keyboard = [
            [InlineKeyboardButton("📖 Отметить все как прочитанные", callback_data="mark_all_read")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_deal_type_keyboard():
        """Выбор типа сделки"""
        keyboard = [
            [InlineKeyboardButton("👤 Создать заказ", callback_data="deal_customer")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_deal_status_keyboard(deal_id: str):
        """Клавиатура для управления сделкой"""
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")],
            [InlineKeyboardButton("🚀 Начать работу", callback_data=f"start_work_{deal_id}")],
            [InlineKeyboardButton("✅ Завершить работу", callback_data=f"complete_work_{deal_id}")],
            [InlineKeyboardButton("🎯 Завершить сделку", callback_data=f"finish_deal_{deal_id}")],
            [InlineKeyboardButton("⚠️ Открыть спор", callback_data=f"open_dispute_{deal_id}")],
            [InlineKeyboardButton("💬 Написать сообщение", callback_data=f"send_message_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_customer_deal_keyboard(deal_id: str, status: str = None, deal: dict = None):
        """Клавиатура для заказчика"""
        keyboard = []
        
        # Кнопки в зависимости от статуса
        if status == "pending":
            keyboard.append([InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_deal_{deal_id}")])
        elif status == "completed":
            keyboard.append([InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"confirm_completion_{deal_id}")])
        
        # Универсальная кнопка завершения сделки
        keyboard.append([InlineKeyboardButton("🎯 Завершить сделку", callback_data=f"finish_deal_{deal_id}")])
        
        # Кнопки для связи с исполнителем
        if deal and deal.get('executor_id'):
            keyboard.append([InlineKeyboardButton("👨‍💼 Написать исполнителю", url=f"https://t.me/{deal.get('executor_username', '')}")])
        
        # Кнопки, доступные всегда
        keyboard.extend([
            [InlineKeyboardButton("📤 Отправить другому", callback_data=f"transfer_deal_{deal_id}")],
            [InlineKeyboardButton("⚠️ Открыть спор", callback_data=f"open_dispute_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
        ])
        # Защита от пустой или некорректной клавиатуры
        if not keyboard or not any(isinstance(row, list) and row for row in keyboard):
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_executor_deal_keyboard(deal_id: str, status: str = None, deal: dict = None):
        """Клавиатура для исполнителя"""
        keyboard = []
        
        # Кнопки в зависимости от статуса
        if status == "paid":
            keyboard.append([InlineKeyboardButton("🚀 Начать работу", callback_data=f"start_work_{deal_id}")])
        elif status == "in_progress":
            keyboard.append([InlineKeyboardButton("✅ Завершить работу", callback_data=f"complete_work_{deal_id}")])
        elif status == "completed":
            keyboard.append([InlineKeyboardButton("💰 Получить деньги", callback_data=f"receive_payment_{deal_id}")])
        
        # Универсальная кнопка завершения сделки
        keyboard.append([InlineKeyboardButton("🎯 Завершить сделку", callback_data=f"finish_deal_{deal_id}")])
        
        # Кнопки для связи с заказчиком
        if deal and deal.get('customer_username'):
            username = deal['customer_username']
            if isinstance(username, str) and username.strip():
                keyboard.append([InlineKeyboardButton("👤 Написать заказчику", url=f"https://t.me/{username}")])
        
        # Кнопки, доступные всегда
        keyboard.extend([
            [InlineKeyboardButton("⚠️ Открыть спор", callback_data=f"open_dispute_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
        ])
        # Защита от пустой или некорректной клавиатуры
        if not keyboard or not any(isinstance(row, list) and row for row in keyboard):
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_cancel_keyboard():
        """Клавиатура с кнопкой отмены"""
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_yes_no_keyboard(callback_data: str):
        """Клавиатура Да/Нет"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Да", callback_data=f"yes_{callback_data}"),
                InlineKeyboardButton("❌ Нет", callback_data="no")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_admin_keyboard():
        """Админская клавиатура"""
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("💰 Все сделки", callback_data="admin_deals")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_available_deals_keyboard(deals):
        """Клавиатура для доступных заказов"""
        keyboard = []
        for i, deal in enumerate(deals[:10], 1):  # Показываем только первые 10 заказов
            keyboard.append([InlineKeyboardButton(
                f"Заказ #{i} - {deal['amount']} руб.", 
                callback_data=f"view_deal_{deal['deal_id']}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_deal_accept_keyboard(deal_id):
        """Клавиатура для принятия заказа"""
        keyboard = [
            [InlineKeyboardButton("✅ Принять заказ", callback_data=f"accept_deal_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="available_deals")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_deal_accept_reject_keyboard(deal_id):
        """Клавиатура для принятия или отказа от предложенной сделки"""
        keyboard = [
            [InlineKeyboardButton("✅ Принять сделку", callback_data=f"accept_offered_deal_{deal_id}")],
            [InlineKeyboardButton("❌ Отказаться от сделки", callback_data=f"reject_offered_deal_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    

    
    @staticmethod
    def get_deal_actions_keyboard(deal_id: str, status: str = None, deal: dict = None):
        """Клавиатура действий со сделкой для заказчика"""
        keyboard = []
        
        # Кнопки в зависимости от статуса
        if status == "pending":
            keyboard.extend([
                [InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_deal_{deal_id}")],
                [InlineKeyboardButton("👨‍💼 Назначить исполнителя", callback_data=f"transfer_deal_{deal_id}")],
                [InlineKeyboardButton("📨 Предложить сделку", callback_data=f"offer_deal_{deal_id}")]
            ])
        elif status == "completed":
            keyboard.append([InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"confirm_completion_{deal_id}")])
        
        # Кнопки для связи с исполнителем
        if deal and deal.get('executor_username'):
            keyboard.append([InlineKeyboardButton("👨‍💼 Написать исполнителю", url=f"https://t.me/{deal['executor_username']}")])
        
        # Кнопки, доступные всегда
        keyboard.extend([
            [InlineKeyboardButton("⚠️ Открыть спор", callback_data=f"open_dispute_{deal_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
        ])
        # Защита от пустой или некорректной клавиатуры
        if not keyboard or not any(isinstance(row, list) and row for row in keyboard):
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_payment_method_keyboard():
        """Клавиатура для выбора способа оплаты (только Crypto Bot)"""
        keyboard = [
            [InlineKeyboardButton("💎 Crypto Bot (USD)", callback_data="payment_crypto")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_payment_type_keyboard():
        """Клавиатура для выбора типа оплаты"""
        keyboard = [
            [InlineKeyboardButton("💰 Полная оплата", callback_data="payment_type_full")],
            [InlineKeyboardButton("💸 Предоплата", callback_data="payment_type_prepayment")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_customer_payment_method_keyboard():
        """Клавиатура для выбора способа оплаты заказчиком (только Crypto Bot)"""
        keyboard = [
            [InlineKeyboardButton("💎 Crypto Bot (USD)", callback_data="customer_payment_crypto")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_executor_payment_method_keyboard():
        """Клавиатура для выбора способа получения исполнителем (только Crypto Bot)"""
        keyboard = [
            [InlineKeyboardButton("💎 Crypto Bot (USD)", callback_data="executor_payment_crypto")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_deal_offer_keyboard(offer_id: str):
        """Клавиатура для предложения сделки"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"accept_offer_{offer_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_offer_{offer_id}")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_deals")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_deal_offers_list_keyboard():
        """Клавиатура для списка предложений сделок"""
        keyboard = [
            [InlineKeyboardButton("📨 Мои предложения", callback_data="my_offers")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard) 

    @staticmethod
    def get_balance_keyboard():
        """Клавиатура баланса"""
        keyboard = [
            [InlineKeyboardButton("💰 Пополнить счет", callback_data="deposit")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
 