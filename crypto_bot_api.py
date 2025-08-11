import requests
import logging
import json
from typing import Optional, Dict, Any
from config import CRYPTOPAY_API_KEY, CRYPTOPAY_WALLET_ID, CRYPTOPAY_API_URL, EXTERNAL_EXCHANGE_WALLET_ADDRESS, EXTERNAL_EXCHANGE_NAME

logger = logging.getLogger(__name__)

class CryptoPayAPI:
    """Класс для работы с CryptoPay API"""
    
    def __init__(self, api_key: str = CRYPTOPAY_API_KEY):
        self.api_key = api_key
        self.base_url = CRYPTOPAY_API_URL
        self.session = requests.Session()
        logger.info(f"Инициализирован CryptoPay API с ключом: {api_key[:10]}...")
    
    def create_invoice(self, amount: float, currency: str = "USDT", description: str = "") -> Optional[Dict[str, Any]]:
        """Создание инвойса для оплаты через CryptoPay"""
        try:
            logger.info(f"Создание инвойса: {amount} {currency} для {description}")
            logger.info(f"Используемый API ключ: {self.api_key[:20]}...")
            logger.info(f"URL API: {self.base_url}")
            
            # Правильный формат запроса к CryptoBot API
            headers = {
                "Crypto-Pay-API-Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Параметры запроса
            params = {
                "asset": currency,
                "amount": str(amount),
                "description": description
            }
            
            logger.info(f"Заголовки запроса: {headers}")
            logger.info(f"Параметры запроса: {params}")
            
            response = self.session.get(f"{self.base_url}/createInvoice", headers=headers, params=params)
            logger.info(f"Получен ответ: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    invoice_data = result.get("result", {})
                    logger.info(f"✅ Создан инвойс: {invoice_data.get('invoice_id')}")
                    return invoice_data
                else:
                    error_info = result.get('error', {})
                    logger.error(f"❌ Ошибка создания инвойса: {error_info}")
                    if error_info.get('code') == 401:
                        logger.error("🔑 Ошибка 401: Неверный API токен. Проверьте токен в @CryptoBot -> API")
                    return None
            else:
                logger.error(f"Ошибка создания инвойса: {response.status_code} - {response.text}")
                if response.status_code == 401:
                    logger.error("🔑 Ошибка 401: Неверный API токен. Проверьте токен в @CryptoBot -> API")
                return None
            
        except Exception as e:
            logger.error(f"Ошибка при создании инвойса: {e}")
            return None
    
    def get_invoice_status(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса инвойса"""
        try:
            headers = {
                "Crypto-Pay-API-Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            params = {
                "invoice_ids": invoice_id
            }
            
            response = self.session.get(f"{self.base_url}/getInvoices", headers=headers, params=params)
            logger.info(f"Получен ответ getInvoices: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    # API возвращает result.items, а не result напрямую
                    result_data = result.get("result", {})
                    invoices = result_data.get("items", [])
                    
                    if invoices:
                        logger.info(f"✅ Найден инвойс: {invoices[0].get('invoice_id')} со статусом {invoices[0].get('status')}")
                        return invoices[0]  # Возвращаем первый инвойс
                    else:
                        logger.error(f"Инвойс {invoice_id} не найден")
                        return None
                else:
                    logger.error(f"❌ Ошибка получения статуса инвойса: {result.get('error')}")
                    return None
            else:
                logger.error(f"Ошибка получения статуса инвойса: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении статуса инвойса: {e}")
            return None
    
    def check_payment(self, invoice_id: str) -> bool:
        """Проверка оплаты инвойса"""
        try:
            status = self.get_invoice_status(invoice_id)
            if status and status.get("status") == "paid":
                logger.info(f"✅ Инвойс {invoice_id} оплачен")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке оплаты: {e}")
            return False
    
    def transfer(self, user_id: str, amount: float, currency: str = "USDT", description: str = "") -> bool:
        """Перевод средств пользователю"""
        try:
            headers = {
                "Crypto-Pay-API-Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            params = {
                "user_id": user_id,
                "asset": currency,
                "amount": str(amount),
                "spend_id": description  # Используем описание как spend_id
            }
            
            response = self.session.get(f"{self.base_url}/transfer", headers=headers, params=params)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info(f"✅ Перевод {amount} {currency} успешно отправлен пользователю {user_id}")
                    return True
                else:
                    logger.error(f"❌ Ошибка перевода: {result.get('error')}")
                    return False
            else:
                logger.error(f"Ошибка перевода: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при переводе: {e}")
            return False
    
    def send_commission(self, amount: float, currency: str = "USDT", description: str = "") -> bool:
        """Отправка комиссии на внешнюю криптобиржу"""
        try:
            from config import COMMISSION_PERCENT
            commission = amount * (COMMISSION_PERCENT / 100)  # Комиссия из конфига
            
            # Отправляем комиссию на внешний адрес кошелька
            return self.send_to_external_wallet(commission, currency, description)
            
        except Exception as e:
            logger.error(f"Ошибка при отправке комиссии: {e}")
            return False
    
    def send_to_external_wallet(self, amount: float, currency: str = "USDT", description: str = "") -> bool:
        """Отправка средств на внешний кошелек (криптобиржу)"""
        try:
            # Используем CryptoPay API для отправки на внешний адрес
            headers = {
                "Crypto-Pay-API-Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Для отправки на внешний адрес используем метод withdraw
            params = {
                "asset": currency,
                "amount": str(amount),
                "address": EXTERNAL_EXCHANGE_WALLET_ADDRESS,
                "spend_id": f"commission_{description}"
            }
            
            logger.info(f"📤 Отправка {amount} {currency} на {EXTERNAL_EXCHANGE_NAME} кошелек: {EXTERNAL_EXCHANGE_WALLET_ADDRESS}")
            
            # Примечание: Этот метод может отличаться в зависимости от API CryptoPay
            # Возможно потребуется использовать другой endpoint или параметры
            response = self.session.get(f"{self.base_url}/withdraw", headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info(f"✅ Комиссия {amount} {currency} успешно отправлена на {EXTERNAL_EXCHANGE_NAME} ({EXTERNAL_EXCHANGE_WALLET_ADDRESS})")
                    return True
                else:
                    logger.error(f"❌ Ошибка отправки комиссии на {EXTERNAL_EXCHANGE_NAME}: {result.get('error')}")
                    # Fallback: отправляем на внутренний кошелек администратора
                    return self.send_commission_fallback(amount, currency, description)
            else:
                logger.error(f"Ошибка отправки комиссии на {EXTERNAL_EXCHANGE_NAME}: {response.status_code} - {response.text}")
                # Fallback: отправляем на внутренний кошелек администратора
                return self.send_commission_fallback(amount, currency, description)
                
        except Exception as e:
            logger.error(f"Ошибка при отправке на {EXTERNAL_EXCHANGE_NAME}: {e}")
            # Fallback: отправляем на внутренний кошелек администратора
            return self.send_commission_fallback(amount, currency, description)
    
    def send_commission_fallback(self, amount: float, currency: str = "USDT", description: str = "") -> bool:
        """Резервный метод отправки комиссии на внутренний кошелек администратора"""
        try:
            headers = {
                "Crypto-Pay-API-Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            params = {
                "user_id": CRYPTOPAY_WALLET_ID,
                "asset": currency,
                "amount": str(amount),
                "spend_id": f"fallback_commission_{description}"
            }
            
            logger.info(f"🔄 Резервная отправка {amount} {currency} на внутренний кошелек администратора")
            
            response = self.session.get(f"{self.base_url}/transfer", headers=headers, params=params)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info(f"✅ Комиссия {amount} {currency} отправлена на резервный кошелек {CRYPTOPAY_WALLET_ID}")
                    return True
                else:
                    logger.error(f"❌ Ошибка резервной отправки комиссии: {result.get('error')}")
                    return False
            else:
                logger.error(f"Ошибка резервной отправки комиссии: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при резервной отправке комиссии: {e}")
            return False
    
    def get_balance(self) -> Optional[Dict[str, Any]]:
        """Получение баланса"""
        try:
            headers = {
                "Crypto-Pay-API-Token": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = self.session.get(f"{self.base_url}/getBalance", headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения баланса: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении баланса: {e}")
            return None

# Создаем глобальный экземпляр API
crypto_api = CryptoPayAPI() 