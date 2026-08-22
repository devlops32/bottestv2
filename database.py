# database.py - Работа с базой данных

import sqlite3
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from models import Product, Order, AutoSellCampaign, User
import json
import random
import string

class Database:
    def __init__(self, db_path='bot.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица городов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            ''')
            
            # Таблица товаров
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT NOT NULL,
                    name TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    in_stock BOOLEAN DEFAULT 1,
                    product_code TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    campaign_id INTEGER DEFAULT NULL
                )
            ''')
            
            # Таблица заказов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    city TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    product_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_auto BOOLEAN DEFAULT 0
                )
            ''')
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    subscribed BOOLEAN DEFAULT 1,
                    is_blocked BOOLEAN DEFAULT 0,
                    blocked_at TIMESTAMP DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Таблица кампаний
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cities TEXT NOT NULL,
                    products TEXT NOT NULL,
                    quantities TEXT NOT NULL,
                    prices TEXT NOT NULL,
                    days INTEGER NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    sold_count INTEGER DEFAULT 0,
                    total_revenue INTEGER DEFAULT 0,
                    ended_at TIMESTAMP DEFAULT NULL
                )
            ''')
            
            conn.commit()

    # ============================================
    # ПОЛЬЗОВАТЕЛИ
    # ============================================
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            conn.commit()

    def get_all_users(self) -> List[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE subscribed = 1 AND is_blocked = 0')
            return [row[0] for row in cursor.fetchall()]

    def get_all_users_full(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, 
                       subscribed, is_blocked, blocked_at, created_at,
                       (SELECT COUNT(*) FROM orders WHERE user_id = users.user_id) as orders_count,
                       (SELECT SUM(price) FROM orders WHERE user_id = users.user_id) as total_spent
                FROM users
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_user(self, user_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if not user:
                return None
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(price) as total_spent,
                    AVG(price) as avg_price,
                    MAX(price) as max_price,
                    MIN(price) as min_price
                FROM orders 
                WHERE user_id = ?
            ''', (user_id,))
            stats = cursor.fetchone()
            
            cursor.execute('''
                SELECT product_name, city, quantity, price, product_code, created_at
                FROM orders 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            ''', (user_id,))
            last_orders = [dict(row) for row in cursor.fetchall()]
            
            result = dict(user)
            result['stats'] = dict(stats) if stats else {}
            result['last_orders'] = last_orders
            return result

    def toggle_subscription(self, user_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET subscribed = NOT subscribed 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, user_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_users_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            return cursor.fetchone()[0]

    def get_subscribed_users_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users WHERE subscribed = 1 AND is_blocked = 0')
            return cursor.fetchone()[0]

    def get_users_by_activity(self, days: int = 7) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    u.user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    COUNT(o.id) as orders_count,
                    SUM(o.price) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.user_id 
                    AND o.created_at >= datetime('now', ?)
                WHERE u.is_blocked = 0
                GROUP BY u.user_id
                HAVING orders_count > 0
                ORDER BY orders_count DESC
            ''', (f'-{days} days',))
            return [dict(row) for row in cursor.fetchall()]

    # ============================================
    # БЛОКИРОВКА ПОЛЬЗОВАТЕЛЕЙ
    # ============================================
    
    def block_user(self, user_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET is_blocked = 1, blocked_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def unblock_user(self, user_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET is_blocked = 0, blocked_at = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def is_user_blocked(self, user_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_blocked FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] == 1 if result else False

    def get_blocked_users(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, blocked_at
                FROM users 
                WHERE is_blocked = 1
                ORDER BY blocked_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_blocked_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
            return cursor.fetchone()[0]

    # ============================================
    # ГЕНЕРАЦИЯ КОДОВ
    # ============================================
    
    def generate_product_code(self) -> str:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not self.code_exists(code):
                return code

    def code_exists(self, code: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM products WHERE product_code = ?', (code,))
            return cursor.fetchone() is not None

    def get_product_by_code(self, code: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE product_code = ?', (code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_product_code_by_id(self, product_id: int) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT product_code FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    # ============================================
    # ГОРОДА
    # ============================================
    
    def add_city(self, name: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO cities (name) VALUES (?)', (name,))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def delete_city(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cities WHERE name = ?', (name,))
            conn.commit()
            return cursor.rowcount > 0

    def get_cities(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM cities ORDER BY name')
            return [row[0] for row in cursor.fetchall()]

    # ============================================
    # ТОВАРЫ
    # ============================================
    
    def add_product(self, product: Product) -> bool:
        if not product.product_code:
            product.product_code = self.generate_product_code()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO products (city, name, quantity, price, in_stock, product_code)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (product.city, product.name, product.quantity, product.price, product.in_stock, product.product_code))
            conn.commit()
            return True

    def add_product_with_campaign(self, product: Product, campaign_id: int = None):
        if not product.product_code:
            product.product_code = self.generate_product_code()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO products (city, name, quantity, price, in_stock, product_code, campaign_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (product.city, product.name, product.quantity, product.price, product.in_stock, product.product_code, campaign_id))
            conn.commit()

    def get_products_by_city(self, city: str) -> List[Product]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT city, name, quantity, price, in_stock, product_code
                FROM products
                WHERE city = ? AND in_stock = 1
                ORDER BY name
            ''', (city,))
            return [Product(*row) for row in cursor.fetchall()]

    def get_all_products(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, city, name, quantity, price, in_stock, product_code, created_at
                FROM products
                ORDER BY city, name
            ''')
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def update_product_stock(self, product_id: int, in_stock: bool):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE products SET in_stock = ? WHERE id = ?', (in_stock, product_id))
            conn.commit()

    def get_products_by_campaign(self, campaign_id: int) -> List[Product]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT city, name, quantity, price, in_stock, product_code
                FROM products
                WHERE campaign_id = ?
            ''', (campaign_id,))
            return [Product(*row) for row in cursor.fetchall()]

    # ============================================
    # ЗАКАЗЫ
    # ============================================
    
    def add_order(self, order: Order):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders (user_id, product_name, city, quantity, price, product_code, is_auto)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order.user_id, order.product_name, order.city, order.quantity, order.price, order.product_code, order.is_auto))
            conn.commit()
            return cursor.lastrowid

    def get_orders_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM orders')
            return cursor.fetchone()[0]

    def get_auto_orders(self, days: int = 7) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM orders 
                WHERE is_auto = 1 
                AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
            ''', (f'-{days} days',))
            return [dict(row) for row in cursor.fetchall()]

    def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT product_name, city, quantity, price, product_code, created_at
                FROM orders 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    # ============================================
    # НАСТРОЙКИ
    # ============================================
    
    def set_setting(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value)
                VALUES (?, ?)
            ''', (key, value))
            conn.commit()

    def get_setting(self, key: str, default: str = '') -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else default

    # ============================================
    # КАМПАНИИ
    # ============================================
    
    def create_auto_campaign(self, campaign: AutoSellCampaign) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO auto_campaigns (
                    name, cities, products, quantities, prices, 
                    days, started_at, is_active, sold_count, total_revenue
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                campaign.name,
                json.dumps(campaign.cities),
                json.dumps(campaign.products),
                json.dumps(campaign.quantities),
                json.dumps(campaign.prices),
                campaign.days,
                campaign.started_at,
                campaign.is_active,
                campaign.sold_count,
                campaign.total_revenue
            ))
            conn.commit()
            return cursor.lastrowid

    def get_active_campaigns(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM auto_campaigns 
                WHERE is_active = 1 AND ended_at IS NULL
                ORDER BY started_at DESC
            ''')
            results = cursor.fetchall()
            campaigns = []
            for row in results:
                camp = dict(row)
                camp['cities'] = json.loads(camp['cities'])
                camp['products'] = json.loads(camp['products'])
                camp['quantities'] = json.loads(camp['quantities'])
                camp['prices'] = json.loads(camp['prices'])
                campaigns.append(camp)
            return campaigns

    def get_campaign_by_id(self, campaign_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM auto_campaigns WHERE id = ?', (campaign_id,))
            row = cursor.fetchone()
            if row:
                camp = dict(row)
                camp['cities'] = json.loads(camp['cities'])
                camp['products'] = json.loads(camp['products'])
                camp['quantities'] = json.loads(camp['quantities'])
                camp['prices'] = json.loads(camp['prices'])
                return camp
            return None

    def update_campaign_stats(self, campaign_id: int, sold_count: int, total_revenue: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE auto_campaigns 
                SET sold_count = ?, total_revenue = ?
                WHERE id = ?
            ''', (sold_count, total_revenue, campaign_id))
            conn.commit()

    def end_campaign(self, campaign_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE auto_campaigns 
                SET is_active = 0, ended_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (campaign_id,))
            conn.commit()

db = Database()