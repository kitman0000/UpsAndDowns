import time
from decimal import *

from endstone_up_and_down.databaseManager import DatabaseManager

class StockDao:
    def __init__(self, database_manager):
        self.database_manager:DatabaseManager = database_manager
        
        
    def init_tables(self) -> bool:
        """Player Share Table"""
        self.database_manager.create_table("tb_player_stock", {
            "id": "INTEGER primary key autoincrement",
            "player_uuid": "TEXT",
            "stock_name": "nvarchar",
            "share": "int",
            "time": "float"
        })

        '''Player order table'''
        self.database_manager.create_table("tb_player_order", {
            "id": "INTEGER primary key autoincrement",
            "player_uuid": "TEXT",
            "stock_name": "nvarchar",
            "share": "int",
            "single_price": "float",
            "type": "nvarchar",
            "create_time": "float",
            "finish_time": "float",
            "tax": "float",
            "total": "float"
        })
        
        '''Player account table'''
        self.database_manager.create_table("tb_player_account",{
            "player_uuid": "TEXT",
            "balance": "float"
        })
        
        
    def create_order(self, uuid, stock_name, share, type):
        self.database_manager.insert("tb_player_order", {
            "player_uuid": uuid,
            "stock_name": stock_name,
            "share": share,
            "type": type,
            "create_time": time.time(),
        })

        order_id = self.database_manager.query_one(
            f'SELECT id FROM tb_player_order WHERE player_uuid = "{uuid}" ORDER BY id DESC LIMIT 1 '
        )["id"]
        
        return order_id

    def buy(self, order_id, stock_name, uuid, share, price, tax, total):
        # Buy
        exists_share= self.database_manager.query_one("SELECT * FROM tb_player_stock WHERE player_uuid = ? AND stock_name = ?", (uuid, stock_name))
        if exists_share == None:
            self.database_manager.insert("tb_player_stock", {
                "player_uuid": uuid,
                "stock_name": stock_name,
                "share": share,
                "time": time.time()
            })
        else:
            new_share = exists_share["share"] + share
            id = exists_share["id"]
            
            self.database_manager.update("tb_player_stock",{
                "share": new_share
            }, f"id = {id}")

        self.database_manager.update("tb_player_order", {
            "single_price": price,
            "finish_time": time.time(),
            "tax": tax,
            "total": total
        }, f"id = {order_id}")
        
        
    def sell(self, order_id, stock_name, uuid, share, price, tax, total):
        # Sell stock
        # 查询玩家当前持股记录
        exists_share = self.database_manager.query_one(
            "SELECT * FROM tb_player_stock WHERE player_uuid = ? AND stock_name = ?", 
            (uuid, stock_name)
        )
        
        if exists_share is None:
            # 理论上不会发生，因为调用前已检查持股
            raise ValueError(f"Player {uuid} has no stock {stock_name} to sell")
        
        current_share = exists_share["share"]
        record_id = exists_share["id"]
        
        # 计算卖出后的持股数量
        new_share = current_share - share
        
        # 更新持股数量
        self.database_manager.update(
            "tb_player_stock",
            {"share": new_share},
            f"id = {record_id}"
        )
        
        # 更新订单状态
        self.database_manager.update(
            "tb_player_order",
            {
                "single_price": price,
                "finish_time": time.time(),
                "tax": tax,
                "total": total
            },
            f"id = {order_id}"
        )
        
    def check_user_account(self, uuid):
        user_count = self.database_manager.query_one('SELECT COUNT(*) as count FROM tb_player_account WHERE player_uuid = ? ', (uuid,))
        return user_count["count"] == 1
        
        
    def get_balance(self, uuid):
        account = self.database_manager.query_one("SELECT * FROM tb_player_account WHERE player_uuid = ? ", (uuid,))
        return account["balance"]
        
        
    def increase_balance(self, uuid, amount):
        account = self.database_manager.query_one("SELECT * FROM tb_player_account WHERE player_uuid = ? ", (uuid,))
        
        if account == None:
            self.database_manager.insert("tb_player_account", {
                "player_uuid": uuid,
                "balance": amount
            })
        else:
            new_balance = float(Decimal(str(account["balance"])) + Decimal(str(amount)))
            self.database_manager.update("tb_player_account", {
                "balance": new_balance
            }, f"player_uuid='{uuid}'")


    def decrease_balance(self, uuid, amount):
        account = self.database_manager.query_one("SELECT * FROM tb_player_account WHERE player_uuid = ? ", (uuid,))
        if account is None:
            raise Exception("User not found")
        else:
            new_balance = float(Decimal(str(account["balance"])) - Decimal(str(amount)))
            self.database_manager.update("tb_player_account", {
                "balance": new_balance
            }, f"player_uuid='{uuid}'")
            
            
    def get_player_stock_holding(self, uuid, stock_name):
        exists_share = self.database_manager.query_one(
            "SELECT * FROM tb_player_stock WHERE player_uuid = ? AND stock_name = ?", 
            (uuid, stock_name)
        )
        
        if exists_share == None:
            return 0
        
        return exists_share["share"]
    
    
    def get_orders(self, player_uuid, page=1, page_size=10):
        """
        分页查询玩家订单
        :param player_uuid: 玩家UUID
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: 订单列表
        """
        offset = (page - 1) * page_size
        sql =  "SELECT * FROM tb_player_order WHERE player_uuid = ? AND total IS NOT NULL ORDER BY id DESC LIMIT ? OFFSET ?"
        return self.database_manager.query_all(sql, (player_uuid, page_size, offset))
    
    
    def get_shares(self, player_uuid, page=1, page_size=10):
        offset = (page - 1) * page_size
        sql =  "SELECT * FROM tb_player_stock WHERE player_uuid = ? AND share > 0 ORDER BY id DESC LIMIT ? OFFSET ?"
        return self.database_manager.query_all(sql, (player_uuid, page_size, offset))