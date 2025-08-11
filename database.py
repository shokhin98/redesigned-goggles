import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import logging

class Database:
    def __init__(self, db_path: str = "garant_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Создание таблицы пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Создание таблицы сделок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deals (
                    deal_id TEXT PRIMARY KEY,
                    customer_id INTEGER,
                    executor_id INTEGER,
                    amount REAL,
                    commission REAL,
                    description TEXT,
                    status TEXT,
                    payment_amount REAL DEFAULT 0.0,
                    payment_method TEXT DEFAULT 'crypto',
                    payment_type TEXT DEFAULT 'full',
                    remaining_amount REAL DEFAULT 0.0,
                    customer_payment_method TEXT DEFAULT 'crypto',
                    customer_payment_address TEXT,
                    executor_payment_method TEXT DEFAULT 'crypto',
                    executor_payment_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES users (user_id),
                    FOREIGN KEY (executor_id) REFERENCES users (user_id)
                )
            ''')
            
            # Создание таблицы транзакций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    deal_id TEXT,
                    user_id INTEGER,
                    amount REAL,
                    transaction_type TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deal_id) REFERENCES deals (deal_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Создание таблицы сообщений сделок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deal_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id TEXT,
                    user_id INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deal_id) REFERENCES deals (deal_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Создание таблицы уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    deal_id TEXT,
                    notification_type TEXT,
                    message TEXT,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (deal_id) REFERENCES deals (deal_id)
                )
            ''')
            
            # Создание таблицы инвойсов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    deal_id TEXT,
                    amount REAL,
                    currency TEXT,
                    description TEXT,
                    pay_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paid_at TIMESTAMP,
                    FOREIGN KEY (deal_id) REFERENCES deals (deal_id)
                )
            ''')
            
            # Создание таблицы предложений сделок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deal_offers (
                    offer_id TEXT PRIMARY KEY,
                    deal_id TEXT,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deal_id) REFERENCES deals (deal_id),
                    FOREIGN KEY (from_user_id) REFERENCES users (user_id),
                    FOREIGN KEY (to_user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Создание таблицы чеков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS checks (
                    check_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    amount REAL,
                    description TEXT,
                    pay_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Добавление нового пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def update_balance(self, user_id: int, amount: float):
        """Обновление баланса пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET balance = balance + ? WHERE user_id = ?
            ''', (amount, user_id))
            conn.commit()
    
    def get_user_balance(self, user_id: int) -> float:
        """Получение баланса пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0.0
    
    def create_deal(self, customer_id: int, amount: float, description: str) -> str:
        """Создание новой сделки (без исполнителя)"""
        deal_id = str(uuid.uuid4())
        from config import COMMISSION_PERCENT
        commission = amount * (COMMISSION_PERCENT / 100)  # Комиссия из конфига
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO deals (deal_id, customer_id, executor_id, amount, commission, description, status)
                VALUES (?, ?, NULL, ?, ?, ?, ?)
            ''', (deal_id, customer_id, amount, commission, description, 'pending'))
            conn.commit()
        
        return deal_id
    
    def create_deal_extended(self, customer_id: int, amount: float, payment_amount: float, 
                           payment_method: str, payment_type: str, description: str,
                           customer_payment_method: str = 'crypto', customer_payment_address: str = None,
                           executor_payment_method: str = 'crypto', executor_payment_address: str = None) -> str:
        """Создание новой сделки с расширенными параметрами оплаты"""
        deal_id = str(uuid.uuid4())
        from config import COMMISSION_PERCENT
        commission = amount * (COMMISSION_PERCENT / 100)  # Комиссия из конфига
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO deals (
                    deal_id, customer_id, executor_id, amount, commission, description, status,
                    payment_amount, payment_method, payment_type, remaining_amount,
                    customer_payment_method, customer_payment_address,
                    executor_payment_method, executor_payment_address
                )
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (deal_id, customer_id, amount, commission, description, 'pending', 
                  payment_amount, payment_method, payment_type, amount - payment_amount,
                  customer_payment_method, customer_payment_address,
                  executor_payment_method, executor_payment_address))
            conn.commit()
        
        return deal_id
    
    def get_deal(self, deal_id: str) -> Optional[Dict]:
        """Получение информации о сделке"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM deals WHERE deal_id = ?', (deal_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def update_deal_status(self, deal_id: str, status: str):
        """Обновление статуса сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE deals SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE deal_id = ?
            ''', (status, deal_id))
            conn.commit()
    
    def get_user_deals(self, user_id: int) -> List[Dict]:
        """Получение сделок пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM deals 
                WHERE customer_id = ? OR executor_id = ?
                ORDER BY created_at DESC
            ''', (user_id, user_id))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def add_transaction(self, deal_id: str, user_id: int, amount: float, transaction_type: str, description: str):
        """Добавление транзакции"""
        transaction_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (transaction_id, deal_id, user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (transaction_id, deal_id, user_id, amount, transaction_type, description))
            conn.commit()
    
    def add_deal_message(self, deal_id: str, user_id: int, message_text: str):
        """Добавление сообщения в сделку"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO deal_messages (deal_id, user_id, message_text)
                VALUES (?, ?, ?)
            ''', (deal_id, user_id, message_text))
            conn.commit()
    
    def get_deal_messages(self, deal_id: str) -> List[Dict]:
        """Получение сообщений сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT dm.*, u.username, u.first_name 
                FROM deal_messages dm
                JOIN users u ON dm.user_id = u.user_id
                WHERE dm.deal_id = ?
                ORDER BY dm.created_at ASC
            ''', (deal_id,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def get_available_deals(self) -> List[Dict]:
        """Получение доступных заказов (сделки в статусе pending)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT d.*, 
                       c.first_name as customer_name,
                       c.username as customer_username
                FROM deals d
                JOIN users c ON d.customer_id = c.user_id
                WHERE d.status = 'pending' AND d.executor_id IS NULL
                ORDER BY d.created_at DESC
            ''')
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def accept_deal(self, deal_id: str, executor_id: int) -> bool:
        """Принятие заказа исполнителем"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Проверяем, что сделка доступна для принятия
            cursor.execute('''
                SELECT status, executor_id FROM deals WHERE deal_id = ?
            ''', (deal_id,))
            result = cursor.fetchone()
            
            if not result or result[0] != 'pending':
                return False
            
            # Если исполнитель уже назначен, нельзя принять
            if result[1] is not None:
                return False
            
            # Назначаем исполнителя
            cursor.execute('''
                UPDATE deals SET executor_id = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE deal_id = ?
            ''', (executor_id, deal_id))
            conn.commit()
            return True
    
    def add_notification(self, user_id: int, deal_id: str, notification_type: str, message: str):
        """Добавление уведомления"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notifications (user_id, deal_id, notification_type, message)
                VALUES (?, ?, ?, ?)
            ''', (user_id, deal_id, notification_type, message))
            conn.commit()
    
    def get_user_notifications(self, user_id: int, unread_only: bool = False) -> List[Dict]:
        """Получение уведомлений пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if unread_only:
                cursor.execute('''
                    SELECT * FROM notifications 
                    WHERE user_id = ? AND is_read = FALSE
                    ORDER BY created_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM notifications 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def mark_notification_read(self, notification_id: int):
        """Отметить уведомление как прочитанное"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE notifications SET is_read = TRUE 
                WHERE notification_id = ?
            ''', (notification_id,))
            conn.commit()
    
    def mark_all_notifications_read(self, user_id: int):
        """Отметить все уведомления пользователя как прочитанные"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE notifications SET is_read = TRUE 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def get_unread_notifications_count(self, user_id: int) -> int:
        """Получить количество непрочитанных уведомлений"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM notifications 
                WHERE user_id = ? AND is_read = FALSE
            ''', (user_id,))
            return cursor.fetchone()[0] 
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Получение пользователя по username"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def transfer_deal(self, deal_id: str, new_customer_id: int) -> bool:
        """Передача сделки другому пользователю как заказчику"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Проверяем, что сделка существует и в статусе pending
            cursor.execute('SELECT status FROM deals WHERE deal_id = ?', (deal_id,))
            row = cursor.fetchone()
            if not row or row[0] != 'pending':
                return False
            
            # Обновляем заказчика сделки
            cursor.execute('''
                UPDATE deals SET customer_id = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE deal_id = ?
            ''', (new_customer_id, deal_id))
            conn.commit()
            return True
    
    def assign_executor(self, deal_id: str, executor_id: int) -> bool:
        """Назначение исполнителя для сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Проверяем, что сделка существует и в статусе pending
            cursor.execute('SELECT status, executor_id FROM deals WHERE deal_id = ?', (deal_id,))
            row = cursor.fetchone()
            if not row or row[0] != 'pending':
                return False
            
            # Проверяем, что исполнитель еще не назначен
            if row[1] is not None:
                return False
            
            # Назначаем исполнителя
            cursor.execute('''
                UPDATE deals SET executor_id = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE deal_id = ?
            ''', (executor_id, deal_id))
            conn.commit()
            return True
    
    def remove_executor(self, deal_id: str) -> bool:
        """Удаление назначения исполнителя для сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Проверяем, что сделка существует и в статусе pending
            cursor.execute('SELECT status FROM deals WHERE deal_id = ?', (deal_id,))
            row = cursor.fetchone()
            if not row or row[0] != 'pending':
                return False
            
            # Удаляем назначение исполнителя
            cursor.execute('''
                UPDATE deals SET executor_id = NULL, updated_at = CURRENT_TIMESTAMP 
                WHERE deal_id = ?
            ''', (deal_id,))
            conn.commit()
            return True
    
    def create_deal_offer(self, deal_id: str, from_user_id: int, to_user_id: int) -> str:
        """Создание предложения сделки"""
        offer_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO deal_offers (offer_id, deal_id, from_user_id, to_user_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (offer_id, deal_id, from_user_id, to_user_id, 'pending'))
            conn.commit()
        return offer_id
    
    def get_deal_offer(self, offer_id: str) -> Optional[Dict]:
        """Получение предложения сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM deal_offers WHERE offer_id = ?', (offer_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def update_deal_offer_status(self, offer_id: str, status: str) -> bool:
        """Обновление статуса предложения сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE deal_offers SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE offer_id = ?
            ''', (status, offer_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_user_deal_offers(self, user_id: int, status: str = None) -> List[Dict]:
        """Получение предложений сделок пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT * FROM deal_offers 
                    WHERE to_user_id = ? AND status = ?
                    ORDER BY created_at DESC
                ''', (user_id, status))
            else:
                cursor.execute('''
                    SELECT * FROM deal_offers 
                    WHERE to_user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows] 
    
    def delete_deal(self, deal_id: str):
        """Удаление сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM deals WHERE deal_id = ?', (deal_id,))
            conn.commit()
    
    def clear_completed_deals(self) -> int:
        """Очистка только выполненных сделок (статус 'completed')
        Возвращает количество удаленных сделок"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Сначала получаем количество сделок для удаления
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status = ?', ('completed',))
            count = cursor.fetchone()[0]
            
            # Удаляем выполненные сделки и связанные данные
            cursor.execute('DELETE FROM deal_messages WHERE deal_id IN (SELECT deal_id FROM deals WHERE status = ?)', ('completed',))
            cursor.execute('DELETE FROM transactions WHERE deal_id IN (SELECT deal_id FROM deals WHERE status = ?)', ('completed',))
            cursor.execute('DELETE FROM notifications WHERE deal_id IN (SELECT deal_id FROM deals WHERE status = ?)', ('completed',))
            cursor.execute('DELETE FROM invoices WHERE deal_id IN (SELECT deal_id FROM deals WHERE status = ?)', ('completed',))
            cursor.execute('DELETE FROM deal_offers WHERE deal_id IN (SELECT deal_id FROM deals WHERE status = ?)', ('completed',))
            cursor.execute('DELETE FROM deals WHERE status = ?', ('completed',))
            
            conn.commit()
            return count
    
    def get_completed_deals_count(self) -> int:
        """Получение количества выполненных сделок"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status = ?', ('completed',))
            return cursor.fetchone()[0]
    
    def get_active_deals_count(self) -> int:
        """Получение количества активных (не выполненных) сделок"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status != ?', ('completed',))
            return cursor.fetchone()[0]
    
    def delete_notification(self, notification_id: int):
        """Удаление уведомления"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notifications WHERE notification_id = ?', (notification_id,))
            conn.commit()
    
    def delete_user(self, user_id: int):
        """Удаление пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
    
    def create_invoice(self, deal_id: str, amount: float, currency: str, description: str, pay_url: str) -> str:
        """Создание инвойса для сделки"""
        invoice_id = f"inv_{deal_id}_{int(amount)}_{currency}"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO invoices (invoice_id, deal_id, amount, currency, description, pay_url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (invoice_id, deal_id, amount, currency, description, pay_url))
            conn.commit()
        return invoice_id
    
    def get_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Получение информации об инвойсе"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM invoices WHERE invoice_id = ?', (invoice_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def get_deal_invoice(self, deal_id: str) -> Optional[Dict]:
        """Получение инвойса для сделки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM invoices WHERE deal_id = ? ORDER BY created_at DESC LIMIT 1', (deal_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def update_invoice_status(self, invoice_id: str, status: str, paid_at: str = None):
        """Обновление статуса инвойса"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if paid_at:
                cursor.execute('''
                    UPDATE invoices SET status = ?, paid_at = ? WHERE invoice_id = ?
                ''', (status, paid_at, invoice_id))
            else:
                cursor.execute('''
                    UPDATE invoices SET status = ? WHERE invoice_id = ?
                ''', (status, invoice_id))
            conn.commit()
    
    def update_customer_payment_info(self, deal_id: str, payment_method: str, payment_address: str):
        """Обновление информации о способе оплаты заказчика"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE deals SET customer_payment_method = ?, customer_payment_address = ?, 
                updated_at = CURRENT_TIMESTAMP WHERE deal_id = ?
            ''', (payment_method, payment_address, deal_id))
            conn.commit()
    
    def update_executor_payment_info(self, deal_id: str, payment_method: str, payment_address: str):
        """Обновление информации о способе получения исполнителя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE deals SET executor_payment_method = ?, executor_payment_address = ?, 
                updated_at = CURRENT_TIMESTAMP WHERE deal_id = ?
            ''', (payment_method, payment_address, deal_id))
            conn.commit()
    
    def create_check(self, check_id: str, user_id: int, amount: float, description: str, pay_url: str):
        """Создание чека"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO checks (check_id, user_id, amount, description, pay_url, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (check_id, user_id, amount, description, pay_url, 'pending'))
            conn.commit()
    
    def get_user_checks(self, user_id: int) -> List[Dict]:
        """Получение чеков пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM checks 
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def offer_deal(self, deal_id: str, from_user_id: int, to_user_id: int) -> bool:
        """Предложение сделки другому пользователю"""
        try:
            offer_id = self.create_deal_offer(deal_id, from_user_id, to_user_id)
            return True
        except Exception as e:
            logging.error(f"Ошибка при создании предложения сделки: {e}")
            return False
    
    def get_deal_offers_for_user(self, user_id: int, status: str = None) -> List[Dict]:
        """Получение предложений сделок для пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT do.*, d.amount, d.description, d.status as deal_status,
                           u.first_name as from_user_name, u.username as from_user_username
                    FROM deal_offers do
                    JOIN deals d ON do.deal_id = d.deal_id
                    JOIN users u ON do.from_user_id = u.user_id
                    WHERE do.to_user_id = ? AND do.status = ?
                    ORDER BY do.created_at DESC
                ''', (user_id, status))
            else:
                cursor.execute('''
                    SELECT do.*, d.amount, d.description, d.status as deal_status,
                           u.first_name as from_user_name, u.username as from_user_username
                    FROM deal_offers do
                    JOIN deals d ON do.deal_id = d.deal_id
                    JOIN users u ON do.from_user_id = u.user_id
                    WHERE do.to_user_id = ?
                    ORDER BY do.created_at DESC
                ''', (user_id,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def get_sent_deal_offers(self, user_id: int, status: str = None) -> List[Dict]:
        """Получение предложений сделок, отправленных пользователем"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT do.*, d.amount, d.description, d.status as deal_status,
                           u.first_name as to_user_name, u.username as to_user_username
                    FROM deal_offers do
                    JOIN deals d ON do.deal_id = d.deal_id
                    JOIN users u ON do.to_user_id = u.user_id
                    WHERE do.from_user_id = ? AND do.status = ?
                    ORDER BY do.created_at DESC
                ''', (user_id, status))
            else:
                cursor.execute('''
                    SELECT do.*, d.amount, d.description, d.status as deal_status,
                           u.first_name as to_user_name, u.username as to_user_username
                    FROM deal_offers do
                    JOIN deals d ON do.deal_id = d.deal_id
                    JOIN users u ON do.to_user_id = u.user_id
                    WHERE do.from_user_id = ?
                    ORDER BY do.created_at DESC
                ''', (user_id,))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows] 