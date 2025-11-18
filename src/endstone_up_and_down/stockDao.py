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
            "player_xuid": "TEXT",
            "stock_name": "nvarchar",
            "share": "int",
            "time": "float"
        })

        '''Player order table'''
        self.database_manager.create_table("tb_player_order", {
            "id": "INTEGER primary key autoincrement",
            "player_xuid": "TEXT",
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
            "player_xuid": "TEXT",
            "balance": "float"
        })
            
        # Leaderboard table
        self.database_manager.create_table("tb_leaderboard", {
            "id": "INTEGER primary key autoincrement",
            "player_xuid": "TEXT",
            "total_wealth": "float",
            "balance": "float",
            "holdings_value": "float",
            "total_investment": "float",
            "absolute_profit_loss": "float",
            "relative_profit_loss": "float",
            "is_absolute": "BOOLEAN",
            "last_updated": "float",
            "rank": "int"
        })
        
        
    def create_order(self, xuid, stock_name, share, type):
        stock_name = stock_name.upper()
        
        self.database_manager.insert("tb_player_order", {
            "player_xuid": xuid,
            "stock_name": stock_name,
            "share": share,
            "type": type,
            "create_time": time.time(),
        })

        result = self.database_manager.query_one(
            "SELECT id FROM tb_player_order WHERE player_xuid = ? ORDER BY id DESC LIMIT 1",
            (xuid,)
        )
        order_id = result["id"] if result else None
        
        return order_id

    def buy(self, order_id, stock_name, xuid, share, price, tax, total):
        stock_name = stock_name.upper()
        
        # Buy
        exists_share = self.database_manager.query_one("SELECT * FROM tb_player_stock WHERE player_xuid = ? AND stock_name = ?", (xuid, stock_name))
        if exists_share == None:
            self.database_manager.insert("tb_player_stock", {
                "player_xuid": xuid,
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
        
        
    def sell(self, order_id, stock_name, xuid, share, price, tax, total):
        stock_name = stock_name.upper()
        
        # Sell stock
        # 查询玩家当前持股记录
        exists_share = self.database_manager.query_one(
            "SELECT * FROM tb_player_stock WHERE player_xuid = ? AND stock_name = ?", 
            (xuid, stock_name)
        )
        
        if exists_share is None:
            # 理论上不会发生，因为调用前已检查持股
            raise ValueError(f"Player {xuid} has no stock {stock_name} to sell")
        
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
        
    def check_user_account(self, xuid):
        user_count = self.database_manager.query_one('SELECT COUNT(*) as count FROM tb_player_account WHERE player_xuid = ? ', (xuid,))
        return user_count["count"] == 1
        
        
    def get_balance(self, xuid):
        account = self.database_manager.query_one("SELECT * FROM tb_player_account WHERE player_xuid = ? ", (xuid,))
        return account["balance"]
        
        
    def increase_balance(self, xuid, amount, is_transfer_in=False):
        """
        增加余额
        :param xuid: 玩家XUID
        :param amount: 金额
        :param is_transfer_in: 是否为转入操作（影响累计投入）
        """
        account = self.database_manager.query_one("SELECT * FROM tb_player_account WHERE player_xuid = ? ", (xuid,))
        
        if account == None:
            # 新账户
            self.database_manager.insert("tb_player_account", {
                "player_xuid": xuid,
                "balance": amount
            })
        else:
            new_balance = float(Decimal(str(account["balance"])) + Decimal(str(amount)))
            self.database_manager.update("tb_player_account", {
                "balance": new_balance
            }, f"player_xuid='{xuid}'")


    def decrease_balance(self, xuid, amount, is_transfer_out=False):
        """
        减少余额
        :param xuid: 玩家XUID
        :param amount: 金额
        :param is_transfer_out: 是否为转出操作（影响累计投入）
        """
        account = self.database_manager.query_one("SELECT * FROM tb_player_account WHERE player_xuid = ? ", (xuid,))
        if account is None:
            raise Exception("User not found")
        else:
            new_balance = float(Decimal(str(account["balance"])) - Decimal(str(amount)))
            self.database_manager.update("tb_player_account", {
                "balance": new_balance
            }, f"player_xuid='{xuid}'")
            
            
    def get_player_stock_holding(self, xuid, stock_name):
        stock_name = stock_name.upper()
        
        exists_share = self.database_manager.query_one(
            "SELECT * FROM tb_player_stock WHERE player_xuid = ? AND stock_name = ?", 
            (xuid, stock_name)
        )
        
        if exists_share == None:
            return 0
        
        return exists_share["share"]
    
    
    def get_orders(self, player_xuid, page=1, page_size=10):
        """
        分页查询玩家订单
        :param player_xuid: 玩家XUID
        :param page: 页码，从1开始
        :param page_size: 每页数量
        :return: 订单列表
        """
        offset = (page - 1) * page_size
        sql =  "SELECT * FROM tb_player_order WHERE player_xuid = ? AND total IS NOT NULL ORDER BY id DESC LIMIT ? OFFSET ?"
        return self.database_manager.query_all(sql, (player_xuid, page_size, offset))
    
    
    def get_shares(self, player_xuid, page=1, page_size=10):
        offset = (page - 1) * page_size
        sql =  "SELECT * FROM tb_player_stock WHERE player_xuid = ? AND share > 0 ORDER BY id DESC LIMIT ? OFFSET ?"
        return self.database_manager.query_all(sql, (player_xuid, page_size, offset))
    
    
    def get_average_cost(self, player_xuid, stock_name):
        """
        计算玩家持有某股票的平均成本
        :param player_xuid: 玩家XUID
        :param stock_name: 股票名称
        :return: 平均成本价格，如果没有持仓返回None
        """
        # 查询所有买入订单
        buy_orders = self.database_manager.query_all(
            """
            SELECT share, single_price, total 
            FROM tb_player_order 
            WHERE player_xuid = ? 
            AND stock_name = ? 
            AND (type = 'buy_flex' OR type = 'buy_fix')
            AND total IS NOT NULL
            ORDER BY finish_time ASC
            """,
            (player_xuid, stock_name)
        )
        
        # 查询所有卖出订单
        sell_orders = self.database_manager.query_all(
            """
            SELECT share 
            FROM tb_player_order 
            WHERE player_xuid = ? 
            AND stock_name = ? 
            AND (type = 'sell_flex' OR type = 'sell_fix')
            AND total IS NOT NULL
            ORDER BY finish_time ASC
            """,
            (player_xuid, stock_name)
        )
        
        if not buy_orders:
            return None
        
        # 计算总买入成本和总买入股数
        total_cost = Decimal('0')
        total_buy_shares = Decimal('0')
        
        for order in buy_orders:
            share = Decimal(str(order['share']))
            # 总成本包含手续费
            cost = Decimal(str(order['total']))
            total_cost += cost
            total_buy_shares += share
        
        # 计算总卖出股数
        total_sell_shares = Decimal('0')
        for order in sell_orders:
            total_sell_shares += Decimal(str(order['share']))
        
        # 当前持有股数
        current_shares = total_buy_shares - total_sell_shares
        
        if current_shares <= 0:
            return None
        
        # 按比例计算剩余持仓的成本
        # 假设先进先出（FIFO），按比例分摊成本
        remaining_cost = total_cost * (current_shares / total_buy_shares)
        average_cost = remaining_cost / current_shares
        
        return float(average_cost)
    

    def get_leaderboard_cached_data(self, is_absolute):
        # Get current timestamp
        current_time = time.time()
        
        # Get data from cache if it's fresh enough (less than 1 hour old)
        cached_data = self.database_manager.query_all(
            "SELECT * FROM tb_leaderboard WHERE is_absolute = ? AND last_updated > ? ORDER BY rank LIMIT 10",
            (is_absolute, current_time - 3600)
        )

        return cached_data
    
    
    def get_all_players_profit_loss(self, get_stock_price_func):
        """
        获取所有玩家的盈亏数据
        :param get_stock_price_func: 获取股票价格的函数
        :return: 包含玩家盈亏信息的列表
        """
        # 获取所有有账户的玩家
        all_accounts = self.database_manager.query_all(
            "SELECT player_xuid, balance FROM tb_player_account"
        )
        
        if not all_accounts:
            return []
        
        players_data = []
        
        for account in all_accounts:
            player_xuid = account['player_xuid']
            balance = Decimal(str(account['balance']))
            
            # 实时计算累计投入：通过查询买入订单的总成本
            buy_orders = self.database_manager.query_all(
                """
                SELECT share, single_price, tax 
                FROM tb_player_order 
                WHERE player_xuid = ? 
                AND (type = 'buy_flex' OR type = 'buy_fix')
                AND total IS NOT NULL
                """,
                (player_xuid,)
            )
            
            total_investment = Decimal('0')
            for order in buy_orders:
                # 累计投入 = 买入总金额 + 手续费
                share = Decimal(str(order['share']))
                price = Decimal(str(order['single_price']))
                tax = Decimal(str(order['tax'])) if order['tax'] else Decimal('0')
                total_investment += (share * price) + tax
            
            # 如果累计投入为0，跳过（没有实际投资过）
            if total_investment == 0:
                continue
            
            # 计算持仓市值
            holdings_value = Decimal('0')
            holdings = self.database_manager.query_all(
                "SELECT stock_name, share FROM tb_player_stock WHERE player_xuid = ? AND share > 0",
                (player_xuid,)
            )
            
            for holding in holdings:
                stock_name = holding['stock_name']
                share = Decimal(str(holding['share']))
                
                # 获取当前股票价格
                current_price, _ = get_stock_price_func(stock_name)
                if current_price:
                    holdings_value += current_price * share
            
            # 当前总财富 = 持仓市值 + 账户余额
            total_wealth = holdings_value + balance
            
            # 绝对盈亏 = 当前总财富 - 累计投入
            absolute_profit_loss = total_wealth - total_investment
            
            # 相对盈亏（百分比） = 绝对盈亏 / 累计投入 * 100
            if total_investment > 0:
                relative_profit_loss = float((absolute_profit_loss / total_investment) * 100)
            else:
                relative_profit_loss = 0.0
            
            players_data.append({
                'player_xuid': player_xuid,
                'total_wealth': float(total_wealth),
                'holdings_value': float(holdings_value),
                'balance': float(balance),
                'total_investment': float(total_investment),
                'absolute_profit_loss': float(absolute_profit_loss),
                'relative_profit_loss': relative_profit_loss
            })
        
        return players_data
    
    
    def save_leaderboard_data(self, players_data, is_absolute):
        """
        保存排行榜数据到数据库
        :param players_data: 玩家数据列表
        :param is_absolute: 是否为绝对盈亏排行榜
        """
        # 先清空旧数据
        self.database_manager.execute(
            "DELETE FROM tb_leaderboard WHERE is_absolute = ?", 
            (is_absolute,)
        )
        
        # 按指定字段排序（绝对盈亏或相对盈亏）
        if is_absolute:
            sorted_data = sorted(players_data, key=lambda x: x['absolute_profit_loss'], reverse=True)
        else:
            sorted_data = sorted(players_data, key=lambda x: x['relative_profit_loss'], reverse=True)
        
        # 插入新数据
        for rank, player_data in enumerate(sorted_data, 1):
            self.database_manager.insert("tb_leaderboard", {
                "player_xuid": player_data['player_xuid'],
                "total_wealth": player_data['total_wealth'],
                "balance": player_data['balance'],
                "holdings_value": player_data['holdings_value'],
                "total_investment": player_data['total_investment'],
                "absolute_profit_loss": player_data['absolute_profit_loss'],
                "relative_profit_loss": player_data['relative_profit_loss'],
                "is_absolute": is_absolute,
                "last_updated": time.time(),
                "rank": rank
            })
