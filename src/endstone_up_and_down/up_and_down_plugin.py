import datetime
import time
from decimal import *
import threading
import random
from typing import Union


from endstone.command import Command, CommandSender
from endstone.event import EventPriority, ServerLoadEvent, event_handler
from endstone.plugin import Plugin
import yfinance as yf

from endstone_up_and_down.databaseManager import DatabaseManager
from endstone_up_and_down.customWebsocket import CustomWebsocket
from endstone_up_and_down.stockDao import StockDao
from endstone_up_and_down.lockManager import LockException, LockManager, LockWithTimeout
from endstone_up_and_down.marketStatusListenr import MarketStatusListener
from endstone_up_and_down.favorites_manager import FavoritesManager
from endstone_up_and_down.ui_manager import UIManager
from endstone_up_and_down.setting_manager import StockSettingManager
from endstone_up_and_down.player_settings_manager import PlayerSettingsManager


class UpAndDownPlugin(Plugin):
    prefix = "UpAndDown"
    api_version = "0.6"
    load = "POSTWORLD"
    
    # 插件数据目录
    MAIN_PATH = "plugins/UpAndDown"

    commands = {
        "stock":{
                    "description": "股票插件，使用/stock help获取帮助",
                    "usages": ["/stock show [stockName: string] [period: string]",
                               "/stock account",
                               "/stock transferin [amount:int]",
                               "/stock transferout [amount:int]",
                               "/stock buy [stockName: string] [share:int] [price:float]",
                               "/stock sell [stockName: string] [share:int] [price:float]",
                               "/stock orders [page:int]",
                               "/stock help",
                               "/stock shares",
                               "/stock ui"
                               ],
                    "permissions": ["up_and_down.command.transaction"]
                }
    }

    permissions = {
        "up_and_down.command.transaction": {
            "description": "Working on it",
            "default": True,
        }
    }
    
    order_type_dict = {
        "buy_flex": "市价单购买",
        "buy_fix": "限价单购买",
        "sell_flex": "市价单出售",
        "sell_fix": "限价单出售"
    }

    def on_load(self) -> None:
        # 初始化配置管理器
        self.setting_manager = StockSettingManager(self.MAIN_PATH)
        
        # 配置 yfinance 代理
        enable_proxy, proxy_address = self.setting_manager.get_proxy_config()
        if enable_proxy and proxy_address:
            yf.set_config(proxy=proxy_address)
            self.logger.info(f"§e已启用代理: {proxy_address}")
        else:
            self.logger.info("§e未启用代理")
        
        # 设置数据库路径
        import os
        db_path = os.path.join(self.MAIN_PATH, "up_and_down.db")
        
        self.database_manager = DatabaseManager(db_path)
        self.stock_dao = StockDao(self.database_manager)
        self.stock_dao.init_tables()
        self.lock_manager = LockManager()
        
        # 初始化收藏夹管理器、玩家设置管理器和UI管理器
        self.favorites_manager = FavoritesManager(self.database_manager)
        self.player_settings_manager = PlayerSettingsManager(self.database_manager)
        self.ui_manager = UIManager(self)
        
        self.logger.info("§e Up and down Loaded!")
        # self.market_state_listener = MarketStatusListener("AAPL")
        # self.market_state_listener.start_listen()
        

    def on_enable(self) -> None:
        # Schedule leaderboard update every 30 minutes
        self.server.scheduler.run_task(
            self, 
            self.update_leaderboard, 
            delay=0, 
            period=20 * 60 * 30
        )

        self.economy_plugin = self.server.plugin_manager.get_plugin('arc_core')
        self.qqsync = self.server.plugin_manager.get_plugin('qqsync_plugin')
        

    def on_disable(self) -> None:
        pass


    def execute_command(self, sender: CommandSender, args: list[str], return_value:bool, callback=None, callback_args=None):
        def command_executor():
            try:
                # 处理UI命令（不需要线程处理）
                if args[0] == "ui":
                    player = self.server.get_player(sender.name)
                    if player and hasattr(player, 'send_form'):
                        self.ui_manager.show_main_panel(player)
                    else:
                        sender.send_message("§c只有玩家可以使用UI面板")
                    return
                
                player = self.server.get_player(sender.name)
                xuid = player.xuid
                
                if args[0] != "transferin":
                    if not self.stock_dao.check_user_account(xuid):
                        sender.send_message(f"§e请先使用transferin转入初始资金以激活股票账户")
                        return
                
                command_dict = {
                    "show": self.show,
                    "buy": self.buy_stock,
                    "sell": self.sell_stock,
                    "transferin": self.transfer_in,
                    "transferout": self.transfer_out,
                    "account": self.my_account,
                    "help": self.help,
                    "orders": self.show_orders,
                    "shares": self.show_shares
                }
                
                require_lock_command_list = ['buy', 'sell', 'transferin', 'transferout']
                
                command_func = command_dict[args[0]]
                
                if args[0] in require_lock_command_list:
                    player_lock = self.lock_manager.get_player_lock(str(xuid))
                    try:
                        with LockWithTimeout(player_lock, 1):
                            rtn = command_func(xuid, sender, args)
                    except LockException as ex:
                        sender.send_error_message("当前账号有其他股票操作正在进行，请稍候操作")
                else:
                    rtn = command_func(xuid, sender, args)
                
                if return_value:
                    self.server.scheduler.run_task(
                        self,
                        lambda: callback(rtn, sender, callback_args),
                        delay=0
                    )
                    
                
            except Exception as e:
                import traceback
                exception = e
                exception_msg = str(e)
                full_traceback = traceback.format_exc()

                print("Exception Object:", exception)
                print("Exception Message:", exception_msg)
                print("Full Traceback:")
                print(full_traceback)
                
                sender.send_message(f"Exception Object:{exception}")
                sender.send_message(f"Exception Message:{exception_msg}")
                sender.send_message("Full Traceback:")
                sender.send_message(f"{full_traceback}")

        if return_value and callback == None:
            raise Exception("Callback function must not be None if return value is true, Fool!")

        if args[0] == "ui":
            command_executor()
        else:
            thread = threading.Thread(target=command_executor)
            thread.start()

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        '''
            Command router
        '''
        self.execute_command(sender, args, False)

        

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #
    #                     Common Utils
    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 


    def is_available(self, ticket):
        info = ticket.info
        if ticket.ticker == "BTC-USD":
            return True
        
        return info['market'] in ['us_market'] 

    def get_stock_last_price(self, stock, period="1d", interval="1m", return_period=False):
        '''
            Return price, tradeable
        '''

        ticket = yf.Ticker(stock)

        if not self.is_available(ticket):
            return None, None

        df = ticket.history(period=period, interval=interval, prepost=True)
        
        if return_period:
            return list(df["Close"]), True
        
        price = round(df.Close.iloc[-1], 2)
        price = Decimal(str(price))
        
        return price, True
    

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #
    #                     Command Excutors
    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
    def show(self, xuid, sender, args):
        '''
            Show stock price
        '''

        if len(args) == 2:
            unit = "day"
        else:
            unit = args[2]
        
        if unit == "minute":
            price_list, tradeable = self.get_stock_last_price(args[1], return_period=True)
            unit_zh = "10分钟"
        elif unit == "day":
            price_list, tradeable = self.get_stock_last_price(args[1], period="1mo", interval="1d", return_period=True)
            unit_zh = "10天"
        elif unit == "month":
            price_list, tradeable = self.get_stock_last_price(args[1], period="1y",interval="1mo", return_period=True)
            unit_zh = "10个月"
        else:
            sender.send_message(f"§4时间范围必须是minute, day, month其中之一, 你输入的{unit}无效")
            return
        
        if price_list == None:
            sender.send_message(f"你输入了错误的股票名或该股票市场尚不支持:{args[1]}")
            return
        
            
        
        price_str = f"股票{args[1]} 历史{unit_zh}成交价格: "
        price_list = price_list[-11:]
        
        for idx, price in enumerate(price_list):
            if idx == 0:
                continue
            if price > price_list[idx - 1]:
                price_str += "§c" + str(round(price, 2)) + '\n'
            elif price < price_list[idx - 1]:
                price_str += "§q" + str(round(price, 2)) + '\n'
            else:
                price_str += "§7" + str(round(price)) + '\n'
        price_str += "§e以上数据仅供参考，建议使用专业股票软件查询最新价格"
        
        sender.send_message(price_str)
        
        
    def transfer_in(self, xuid, sender, args):
        amount = float(args[1])
        player = self.server.get_player(sender.name)
        
        player_balance = self.economy_plugin.get_player_money(player)
        
        if player_balance < amount:
            sender.send_message(f"§e您的经济实力似乎不足以支付 {amount} 元")
            return
            
        self.economy_plugin.decrease_player_money(player, amount)
        self.stock_dao.increase_balance(xuid, amount, is_transfer_in=True)
        
        sender.send_message(f"§e成功向股票账户汇入 {amount} 元")
        
        
    def my_account(self, xuid, sender, args):
        amount = self.stock_dao.get_balance(xuid)
        sender.send_message(f"§e股票账户余额 {amount} 元")
        
    
    def transfer_out(self, xuid, sender, args):
        # 获取转出金额

        amount = float(args[1])

        # 获取玩家对象
        player = self.server.get_player(sender.name)
        
        # 获取玩家股票账户余额
        stock_balance = self.stock_dao.get_balance(xuid)
        
        # 检查股票账户余额是否足够
        if stock_balance < amount:
            sender.send_message(f"§e您的股票账户余额不足，当前余额: {stock_balance} 元")
            return
        
        # 执行转账操作
        try:
            # 从股票账户扣除金额
            self.stock_dao.decrease_balance(xuid, amount, is_transfer_out=True)
            # 增加玩家游戏账户余额
            self.economy_plugin.increase_player_money(player, amount)
            
            sender.send_message(f"§e成功从股票账户转出 {amount} 元到游戏银行账户")
        except Exception as e:
            # 如果转账过程中出现错误，回滚操作
            sender.send_message("§e转账失败，请稍后重试")
            # 可以在这里添加日志记录
            print(f"Transfer out failed for player {xuid}: {str(e)}")
        
        
    def buy_stock(self, xuid, sender, args) -> Union[bool, str]:
        '''
            Buy stock

            args[0] buy
            args[1] stock_name
            args[2] share
            args[3] [price]

            Return:
            True/False, Message
        '''
        
        player = self.server.get_player(sender.name)
        stock_name = args[1]
        share = args[2]
        
        # sender.send_message("§6交易正在进行中(预计花费30秒到1分钟)...")
        # time.sleep(random.randrange(30, 60))
        
        market_price, tradeable = self.get_stock_last_price(stock_name)
        if tradeable == None:
            message = f"你输入了错误的股票名或该股票市场尚不支持:{args[1]}"
            sender.send_message(message)
            return False, message
        
        if len(args) == 4:
            price = Decimal(str(args[3]))
            type = "buy_fix"
        else:
            price = Decimal(str(market_price)) if tradeable else Decimal(0)
            sender.send_message(f"市价单单价:{price}")
            type = "buy_flex"
            
        market_type = "实时交易" if tradeable else "盘后交易"
        
        order_id = self.stock_dao.create_order(xuid, stock_name, share, type)
        sender.send_message(f"订单创建成功，订单号: {order_id} 类型: {self.order_type_dict[type]} {market_type}")
        
        if price < market_price:
            message = f"股票购买失败，当前市场价:{market_price}, 没有人愿意按您的报价{price}元交易"
            sender.send_message(message)
            return False, message
        player_balance = self.stock_dao.get_balance(xuid)
        
        share = Decimal(str(share))
        fee_rate = Decimal(str(self.setting_manager.get_trading_fee_rate() / 100))
        tax = price * share * fee_rate
        total_price = price * share + tax
        if player_balance < total_price:
            message = f"您的经济实力似乎不足以支付 {total_price} 元"
            sender.send_message(message)
            return False, message
        self.stock_dao.decrease_balance(xuid, total_price)
        self.stock_dao.buy(order_id, stock_name, xuid, share, price, tax, total_price)

        message = f"股票购买成功，总计:{total_price}元"
        sender.send_message(message)
        return True, message
            
            
    def sell_stock(self, xuid, sender, args) -> Union[bool, str]:
        stock_name = args[1]
        share = Decimal(args[2])
        
        # sender.send_message("§6交易正在进行中(预计花费30秒到1分钟)...")
        # time.sleep(random.randrange(30, 60))

        # 获取股票当前价格和可交易状态
        market_price, tradeable = self.get_stock_last_price(stock_name)
        if tradeable is None:
            message = f"你输入了错误的股票名或该股票市场尚不支持:{args[1]}"
            sender.send_message(message)
            return False, message
        
        # 解析价格参数（限价单或市价单）
        if len(args) == 4:
            price = Decimal(str(args[3]))
            order_type = "sell_fix"
        else:
            price = Decimal(str(market_price)) if tradeable else Decimal(0)
            sender.send_message(f"市价单单价:{price}")
            order_type = "sell_flex"
        
        # 检查玩家持股数量
        current_holding = self.stock_dao.get_player_stock_holding(xuid, stock_name)
        if current_holding < Decimal(share):
            message = f"您的持股不足，当前持有 {current_holding} 股"
            sender.send_message(message)
            return False, message
        
        
        # 创建出售订单
        order_id = self.stock_dao.create_order(xuid, stock_name, share, order_type)
        market_type = "实时交易" if tradeable else "盘后交易"
        sender.send_message(f"订单创建成功，订单号: {order_id} 类型: {self.order_type_dict[order_type]} {market_type}")
        

        # 检查市场价格是否满足限价要求
        if market_price < price:
            message = f"股票出售失败，当前市场价:{market_price}, 没有人愿意按您的报价{price}元购买"
            sender.send_message(message)
            return False, message
        
        # 计算总收入（扣除手续费）
        total_price = price * Decimal(share)
        fee_rate = Decimal(str(self.setting_manager.get_trading_fee_rate() / 100))
        tax = total_price * fee_rate
        net_revenue = total_price - tax
        
        # 执行交易
        self.stock_dao.sell(order_id, stock_name, xuid, share, price, tax, total_price)
        self.stock_dao.increase_balance(xuid, net_revenue)

        message = f"股票出售成功，总计:{net_revenue}元"
        sender.send_message(message)

        return True, message
            
    def help(self, xuid, sender, args):
        """显示帮助信息 - 使用UI形式"""
        player = self.server.get_player(sender.name)
        if player and hasattr(player, 'send_form'):
            # 如果玩家在线且有UI支持，显示UI帮助
            self.ui_manager.show_help_panel(player)
        else:
            # 如果无法显示UI，回退到文本消息
            help_str = '''
§c警告：本插件为模拟美股交易插件，您的所有操作均为模拟操作，不会产生真实交易。您只能将股票买卖的利润转为游戏币，您永远无法将其提现为现实中可交易的货币。

§6欢迎来到"荣辱浮沉 (Ups and Downs)" 股票插件，在这里，你可以让自己的财富名列服务器榜首，又或者跟随某个臭名昭著的企业的股票一夜蒸发。

§6这里的一切股票价格都跟实时同步美股市场，所以我强烈推荐你用现实中的股票软件选股和盯盘。股票价格是非常珍贵的数据，我们所提供的数据也仅供参考。

§6如果你不会查股票？那我建议你学起来，毕竟在这里验证你的智商后，你也会迈向亏光家产，哦不，我是说盆满钵满的那一天，你说对吧？

§h指令列表:
/stock ui           §a打开图形化UI界面（推荐使用）
/stock transferin   将资金从服务器经济系统中转入股票账户
/stock transferout  将资金从股票账户中转入服务器经济系统
/stock show <股票代码> [时间范围]   查看股票变化， 时间范围选项: minute (10分钟), day (10天), month (10个月)，默认为minute
/stock account  查看我的股票账户余额
/stock buy <股票代码> <股份数> [价格]   购买股票，份数为整数，不填写价格则为市价单，填写价格则为限价单
/stock sell <股票代码> <股份数> [价格]   出售股票，份数为整数，不填写价格则为市价单，填写价格则为限价单
/stock orders [页数]    查看我的历史订单，页数默认为1
/stock shares [页数]    查看我的持仓，页数默认为1

/stock help 显示本帮助

§s提示：由于屏幕大小限制，↑↑↑请向上滚动阅读完整内容↑↑↑
        
        '''
            
            sender.send_message(help_str)
        
    def show_orders(self, xuid, sender, args):
        player = self.server.get_player(sender.name)
        
        if len(args) == 1:
            page = 0
        else:
            page = args[1] - 1
            
        order_list = self.stock_dao.get_orders(xuid, page)
        
        message = ""
        for order in order_list:
            message += f"§g类型:§h {self.order_type_dict[order['type']]}"
            message += f'§g股票名:§h {order["stock_name"]}'
            message += f'§g股数:§h {order["share"]}'
            message += f'§g单价:§h {order["single_price"]}'
            message += f'§g手续费:§h {order["tax"]}'
            message += f'§g总价:§h {order["total"]}'
            
            
            message += "\n"
            
        sender.send_message(message)
        sender.send_message(f"使用/stock orders {page + 2} 显示下一页")
        
    
    def show_shares(self, xuid, sender, args):
        player = self.server.get_player(sender.name)
        
        if len(args) == 1:
            page = 0
        else:
            page = args[1] - 1
            
        share_list = self.stock_dao.get_shares(xuid, page)
        
        message = ""
        for order in share_list:
            message += f'§g股票名:§h {order["stock_name"]}'
            message += f'§g股数:§h {order["share"]}'
            
            
            message += "\n"
            
        sender.send_message(message)
        sender.send_message(f"使用/stock shares {page + 2} 显示下一页")


    def send_to_qq_group(self, message: str):
        """
        发送消息到QQ群
        :param message: 要发送的消息
        """
        try:
            # 发送消息到QQ群
            success = self.qqsync.api_send_message(message)
            if success:
                self.logger.info(f"[ARC Core] 死亡消息已发送到QQ群: {message}")
            else:
                self.logger.warning(f"[ARC Core] QQ群消息发送失败: {message}")
        except Exception as e:
            self.logger.error(f"[ARC Core] QQ群消息发送异常: {str(e)}")
            # 即使QQ群发送失败，也不影响游戏正常运行
            

    def update_leaderboard(self):
        def _execute():
            """Update leaderboard data for both absolute and relative profit/loss"""
            try:
                self.logger.info("Leaderboard updating")

                # Call get_all_players_profit_loss with is_absolute=True
                absolute_data = self.stock_dao.get_all_players_profit_loss(self.get_stock_last_price)
                self.stock_dao.save_leaderboard_data(absolute_data, True)
                
                # Call get_all_players_profit_loss with is_absolute=False
                relative_data = self.stock_dao.get_all_players_profit_loss(self.get_stock_last_price)
                self.stock_dao.save_leaderboard_data(relative_data, False)
                
                self.logger.info("Leaderboard updated successfully")

                # 获取当前日期，格式 yyyy-mm-dd
                if self.qqsync != None:
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    stored_data = self.get_leaderboard_data(is_absolute=False)
            
                    # 获取最后更新时间
                    last_updated = stored_data[0]['last_updated'] if stored_data else time.time()
                    
                    # 构建内容
                    content = "早安，各位彼阳群友☀️，以下是今日服务器股票排行榜"
                    content += f"相对盈亏排行榜 (更新时间: {datetime.datetime.fromtimestamp(last_updated).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    content += "前5名 (高手榜)\n\n"
                    
                    # 显示前5名
                    for idx, data in enumerate(stored_data[:5], 1):
                        player_name = self._get_player_name(data['player_xuid'])
                        profit_loss_percent = data['relative_profit_loss']
                        profit_loss = data['absolute_profit_loss']
                        
                        # 使用统一的颜色逻辑
                        if profit_loss_percent > 0:
                            sign = "🟥+"
                        elif profit_loss_percent < 0:
                            sign = "🟩-"
                        else:
                            sign = ""
                        
                        content += f"#{idx} {player_name}\n"
                        content += f"   收益率: {sign}{abs(profit_loss_percent):.2f}%\n"
                        content += f"   盈亏: {sign}${abs(profit_loss):.2f}\n\n"
                    
                    content += "倒数5名 (接盘侠榜)\n\n"
                    
                    # 显示倒数5名
                    bottom_5 = stored_data[-5:]
                    bottom_5.reverse()
                    for idx, data in enumerate(bottom_5, 1):
                        player_name = self._get_player_name(data['player_xuid'])
                        profit_loss_percent = data['relative_profit_loss']
                        profit_loss = data['absolute_profit_loss']
                        
                        # 使用统一的颜色逻辑
                        if profit_loss_percent > 0:
                            sign = "🟥+"
                        elif profit_loss_percent < 0:
                            sign = "🟩-"
                        else:
                            sign = ""
                        
                        # 使用存储的排名
                        content += f"#{idx} {player_name}\n"
                        content += f"   收益率: {sign}{abs(profit_loss_percent):.2f}%\n"
                        content += f"   盈亏: {sign}${abs(profit_loss):.2f}\n\n"
                    content += "ARC股票插件，为群友带来初升飞舞的财富🤑"
                    
                    if self.stock_dao.insert_qq_send_log(today_str):
                        self.send_to_qq_group(content)


            except Exception as e:
                self.logger.error(f"Failed to update leaderboard: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())

        threading.Thread(target=_execute).start()


    def get_leaderboard_data(self, is_absolute=True):
        """Get leaderboard data from database
        Args:
            is_absolute: True for absolute leaderboard, False for relative
        Returns:
            List of player data or empty list
        """
        try:
            cached_data = self.stock_dao.get_leaderboard_cached_data(is_absolute)
            if len(cached_data) > 0:
                return cached_data
                
            else:
                return None
        except Exception as e:
            self.logger.error(f"Failed to get leaderboard data: {str(e)}")
            return []
            
        except Exception as e:
            self.logger.error(f"Leaderboard update failed: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    @event_handler
    def on_server_load(self, event: ServerLoadEvent):
        self.logger.info(f"{event.event_name} is passed to on_server_load")

    @event_handler(priority=EventPriority.HIGH)
    def on_server_load_2(self, event: ServerLoadEvent):
        # this will be called after on_server_load because of a higher priority
        self.logger.info(f"{event.event_name} is passed to on_server_load2")

    def log_time(self):
        now = datetime.datetime.now().strftime("%c")
        for player in self.server.online_players:
            player.send_popup(now)
