"""
UI管理器 - 处理所有股票插件的UI表单
"""
import json
from decimal import Decimal
from typing import Callable, Optional

from endstone.form import ActionForm, ModalForm, Label, TextInput, Dropdown


class UIManager:
    def __init__(self, plugin):
        """
        初始化UI管理器
        :param plugin: 插件实例
        """
        self.plugin = plugin
    
    # ==================== 主面板 ====================
    def show_main_panel(self, player):
        """显示股票插件主面板"""
        try:
            xuid = player.xuid
            
            # 检查账户是否已激活
            if not self.plugin.stock_dao.check_user_account(xuid):
                self._show_activate_account_panel(player)
                return
            
            # 获取账户信息
            balance = self.plugin.stock_dao.get_balance(xuid)
            holdings = self.plugin.stock_dao.get_shares(xuid, page=0, page_size=100)
            
            # 计算总市值
            total_market_value = Decimal('0')
            
            for holding in holdings:
                if holding['share'] <= 0:
                    continue
                    
                stock_name = holding['stock_name']
                share = Decimal(str(holding['share']))
                
                # 获取当前价格
                current_price, _ = self.plugin.get_stock_last_price(stock_name)
                if current_price:
                    market_value = current_price * share
                    total_market_value += market_value
            
            # 总财富 = 余额 + 总市值
            total_wealth = Decimal(str(balance)) + total_market_value
            
            # 获取累计投入
            account_info = self.plugin.database_manager.query_one(
                "SELECT total_investment FROM tb_player_account WHERE player_xuid = ?",
                (xuid,)
            )
            total_investment = Decimal(str(account_info.get('total_investment', 0) or 0)) if account_info else Decimal('0')
            
            # 计算绝对盈亏和相对盈亏
            absolute_profit_loss = total_wealth - total_investment
            if total_investment > 0:
                relative_profit_loss = float((absolute_profit_loss / total_investment) * 100)
            else:
                relative_profit_loss = 0.0
            
            # 获取玩家的颜色配置
            profit_color = self.plugin.player_settings_manager.get_color_for_change(xuid, float(absolute_profit_loss))
            
            # 构建内容
            content = f"=== 股票账户概览 ===\n\n"
            content += f"账户余额: ${balance:.2f}\n"
            content += f"持仓市值: ${total_market_value:.2f}\n"
            content += f"总财富: ${total_wealth:.2f}\n"
            content += f"累计投入: ${total_investment:.2f}\n\n"
            
            # 显示绝对盈亏
            if absolute_profit_loss > 0:
                content += f"绝对盈亏: {profit_color}+${absolute_profit_loss:.2f}§r\n"
            elif absolute_profit_loss < 0:
                content += f"绝对盈亏: {profit_color}${absolute_profit_loss:.2f}§r\n"
            else:
                content += f"绝对盈亏: §7${absolute_profit_loss:.2f}§r\n"
            
            # 显示相对盈亏
            if relative_profit_loss > 0:
                content += f"相对盈亏: {profit_color}+{relative_profit_loss:.2f}%%§r\n"
            elif relative_profit_loss < 0:
                content += f"相对盈亏: {profit_color}{relative_profit_loss:.2f}%%§r\n"
            else:
                content += f"相对盈亏: §7{relative_profit_loss:.2f}%%§r\n"
            
            content += f"\n§r提示: 选择下方功能按钮进行操作"
            
            # 创建主面板
            main_panel = ActionForm(
                title="股票交易系统",
                content=content
            )
            
            # 添加功能按钮
            main_panel.add_button(
                "我的持仓",
                on_click=lambda sender: self.show_holdings_panel(sender)
            )
            
            main_panel.add_button(
                "我的收藏",
                on_click=lambda sender: self.show_favorites_panel(sender)
            )
            
            main_panel.add_button(
                "搜索股票",
                on_click=lambda sender: self.show_search_panel(sender)
            )
            
            main_panel.add_button(
                "历史订单",
                on_click=lambda sender: self.show_orders_panel(sender)
            )
            
            main_panel.add_button(
                "账户管理",
                on_click=lambda sender: self.show_account_panel(sender)
            )
            
            main_panel.add_button(
                "个人设置",
                on_click=lambda sender: self.show_player_settings_panel(sender)
            )
            
            main_panel.add_button(
                "盈亏排行榜",
                on_click=lambda sender: self.show_leaderboard_menu(sender)
            )
            
            player.send_form(main_panel)
            
        except Exception as e:
            print(f"显示主面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示主面板时发生错误")
    
    def _show_activate_account_panel(self, player):
        """显示激活账户面板"""
        activate_form = ModalForm(
            title="激活股票账户",
            controls=[
                Label(text="欢迎来到股票交易系统！\n\n请转入初始资金以激活您的股票账户。\n建议转入至少$1000以开始交易。"),
                TextInput(
                    label="转入金额",
                    placeholder="请输入要转入的金额...",
                    default_value="1000"
                )
            ],
            on_submit=lambda sender, json_str: self._handle_activate_account(sender, json_str),
            on_close=lambda sender: None
        )
        player.send_form(activate_form)
    
    def _handle_activate_account(self, player, json_str: str):
        """处理激活账户"""
        try:
            data = json.loads(json_str)
            amount_str = data[1]
            
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError()
            except:
                player.send_message("§c请输入有效的金额（大于0的数字）")
                return
            
            # 检查玩家余额
            player_balance = self.plugin.economy_plugin.get_player_money(player)
            if player_balance < amount:
                player.send_message(f"§c您的游戏币余额不足，当前余额: ${player_balance:.2f}")
                return
            
            # 执行转账
            self.plugin.economy_plugin.decrease_player_money(player, amount)
            self.plugin.stock_dao.increase_balance(player.xuid, amount, is_transfer_in=True)
            
            player.send_message(f"§a成功激活股票账户并转入 ${amount:.2f}")
            
            # 显示主面板
            self.show_main_panel(player)
            
        except Exception as e:
            print(f"激活账户错误: {str(e)}")
            player.send_message("§c激活账户时发生错误")
    
    # ==================== 持仓面板 ====================
    def show_holdings_panel(self, player):
        """显示持仓面板"""
        try:
            xuid = player.xuid
            holdings = self.plugin.stock_dao.get_shares(xuid, page=0, page_size=100)
            
            # 过滤掉股数为0的持仓
            holdings = [h for h in holdings if h['share'] > 0]
            
            if not holdings:
                no_holdings_form = ActionForm(
                    title="我的持仓",
                    content="您目前没有任何持仓\n\n提示: 使用搜索功能查找并购买股票",
                    on_close=lambda sender: self.show_main_panel(sender)
                )
                player.send_form(no_holdings_form)
                return
            
            # 创建持仓列表面板
            holdings_panel = ActionForm(
                title="我的持仓",
                content="点击股票查看详情和进行交易"
            )
            
            for holding in holdings:
                stock_name = holding['stock_name']
                share = holding['share']
                
                # 获取当前价格
                current_price, _ = self.plugin.get_stock_last_price(stock_name)
                
                if current_price:
                    market_value = float(current_price) * share
                    
                    # 获取平均成本
                    avg_cost = self.plugin.stock_dao.get_average_cost(xuid, stock_name)
                    
                    if avg_cost:
                        cost = float(avg_cost) * share
                        profit_loss = market_value - cost
                        profit_loss_percent = (profit_loss / cost) * 100 if cost > 0 else 0
                        
                        # 获取颜色
                        profit_color = self.plugin.player_settings_manager.get_color_for_change(xuid, profit_loss)
                        
                        if profit_loss > 0:
                            profit_text = f"{profit_color}+${profit_loss:.2f} (+{profit_loss_percent:.2f}%%)§r"
                        elif profit_loss < 0:
                            profit_text = f"{profit_color}${profit_loss:.2f} ({profit_loss_percent:.2f}%%)§r"
                        else:
                            profit_text = f"§7${profit_loss:.2f} (0.00%%)§r"
                    else:
                        profit_text = "无法计算"
                    
                    button_text = f"{stock_name}\n持股: {share} | 市值: ${market_value:.2f}\n{profit_text}"
                else:
                    button_text = f"{stock_name}\n持股: {share} | 价格获取失败"
                
                holdings_panel.add_button(
                    button_text,
                    on_click=lambda sender, stock=stock_name: self.show_stock_detail_panel(sender, stock, from_holdings=True)
                )
            
            # 添加返回按钮
            holdings_panel.add_button(
                "返回主菜单",
                on_click=lambda sender: self.show_main_panel(sender)
            )
            
            player.send_form(holdings_panel)
            
        except Exception as e:
            print(f"显示持仓面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示持仓面板时发生错误")
    
    # ==================== 收藏面板 ====================
    def show_favorites_panel(self, player):
        """显示收藏面板"""
        try:
            xuid = player.xuid
            favorites = self.plugin.favorites_manager.get_favorites(xuid, page=0, page_size=20)
            
            if not favorites:
                no_favorites_form = ActionForm(
                    title="我的收藏",
                    content="您还没有收藏任何股票\n\n提示: 使用搜索功能查找股票并添加收藏",
                    on_close=lambda sender: self.show_main_panel(sender)
                )
                player.send_form(no_favorites_form)
                return
            
            # 创建收藏列表面板
            favorites_panel = ActionForm(
                title="我的收藏",
                content="点击股票查看详情和进行交互"
            )
            
            for favorite in favorites:
                stock_name = favorite['stock_name']
                stock_display_name = favorite.get('stock_display_name', stock_name)
                
                # 获取当前价格
                current_price, tradeable = self.plugin.get_stock_last_price(stock_name)
                
                if current_price:
                    status = "开盘" if tradeable else "盘后"
                    button_text = f"{stock_display_name}\n代码: {stock_name} | 价格: ${current_price:.2f} | {status}"
                else:
                    button_text = f"{stock_display_name}\n代码: {stock_name} | 价格获取失败"
                
                favorites_panel.add_button(
                    button_text,
                    on_click=lambda sender, stock=stock_name: self.show_stock_detail_panel(sender, stock)
                )
            
            # 添加返回按钮
            favorites_panel.add_button(
                "返回主菜单",
                on_click=lambda sender: self.show_main_panel(sender)
            )
            
            player.send_form(favorites_panel)
            
        except Exception as e:
            print(f"显示收藏面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示收藏面板时发生错误")
    
    # ==================== 搜索面板 ====================
    def show_search_panel(self, player):
        """显示搜索面板"""
        search_form = ModalForm(
            title="搜索股票",
            controls=[
                Label(text="请输入股票代码进行搜索\n\n例如: AAPL (苹果), TSLA (特斯拉), MSFT (微软)\nBTC-USD (比特币)"),
                TextInput(
                    label="股票代码",
                    placeholder="请输入股票代码...",
                    default_value=""
                )
            ],
            on_submit=lambda sender, json_str: self._handle_search_stock(sender, json_str),
            on_close=lambda sender: self.show_main_panel(sender)
        )
        player.send_form(search_form)
    
    def _handle_search_stock(self, player, json_str: str):
        """处理股票搜索"""
        try:
            data = json.loads(json_str)
            stock_name = data[1].strip().upper()
            
            if not stock_name:
                player.send_message("§c请输入有效的股票代码")
                return
            
            # 验证股票是否存在
            price, tradeable = self.plugin.get_stock_last_price(stock_name)
            
            if price is None and tradeable is None:
                error_form = ActionForm(
                    title="搜索失败",
                    content=f"未找到股票: {stock_name}\n\n可能原因:\n1. 股票代码输入错误\n2. 该股票市场暂不支持\n3. 网络连接问题",
                    on_close=lambda sender: self.show_search_panel(sender)
                )
                player.send_form(error_form)
                return
            
            # 显示股票详情
            self.show_stock_detail_panel(player, stock_name)
            
        except Exception as e:
            print(f"搜索股票错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c搜索股票时发生错误")
    
    # ==================== 股票详情面板 ====================
    def show_stock_detail_panel(self, player, stock_name: str, from_holdings: bool = False):
        """显示股票详情面板"""
        try:
            xuid = player.xuid
            
            # 获取股票信息
            current_price, tradeable = self.plugin.get_stock_last_price(stock_name)
            
            if current_price is None:
                player.send_message(f"§c无法获取股票 {stock_name} 的价格信息")
                return
            
            # 获取持仓信息
            holding = self.plugin.stock_dao.get_player_stock_holding(xuid, stock_name)
            
            # 构建详情内容
            content = f"=== {stock_name} ===\n\n"
            content += f"当前价格: ${current_price:.2f}\n"
            content += f"市场状态: {'开盘交易中' if tradeable else '盘后'}\n\n"
            
            if holding > 0:
                market_value = float(current_price) * holding
                avg_cost = self.plugin.stock_dao.get_average_cost(xuid, stock_name)
                
                content += f"持有股数: {holding}\n"
                content += f"持仓市值: ${market_value:.2f}\n"
                
                if avg_cost:
                    cost = float(avg_cost) * holding
                    profit_loss = market_value - cost
                    profit_loss_percent = (profit_loss / cost) * 100 if cost > 0 else 0
                    
                    # 获取颜色
                    profit_color = self.plugin.player_settings_manager.get_color_for_change(xuid, profit_loss)
                    
                    content += f"平均成本: ${avg_cost:.2f}\n"
                    
                    if profit_loss > 0:
                        content += f"盈亏: {profit_color}+${profit_loss:.2f} (+{profit_loss_percent:.2f}%%)§r\n"
                    elif profit_loss < 0:
                        content += f"盈亏: {profit_color}${profit_loss:.2f} ({profit_loss_percent:.2f}%%)§r\n"
                    else:
                        content += f"盈亏: §7${profit_loss:.2f} (0.00%%)§r\n"
            else:
                content += f"您目前未持有该股票\n"
            
            # 检查是否已收藏
            is_favorite = self.plugin.favorites_manager.is_favorite(xuid, stock_name)
            
            # 创建详情面板
            detail_panel = ActionForm(
                title=f"{stock_name}",
                content=content
            )
            
            # 添加买入按钮
            detail_panel.add_button(
                "买入",
                on_click=lambda sender: self.show_buy_panel(sender, stock_name)
            )
            
            # 如果有持仓，添加卖出按钮
            if holding > 0:
                detail_panel.add_button(
                    "卖出",
                    on_click=lambda sender: self.show_sell_panel(sender, stock_name)
                )
            
            # 添加收藏/取消收藏按钮
            if is_favorite:
                detail_panel.add_button(
                    "取消收藏",
                    on_click=lambda sender: self._handle_remove_favorite(sender, stock_name)
                )
            else:
                detail_panel.add_button(
                    "添加收藏",
                    on_click=lambda sender: self._handle_add_favorite(sender, stock_name)
                )
            
            # 添加查看历史价格按钮
            detail_panel.add_button(
                "查看价格走势",
                on_click=lambda sender: self._show_price_history_panel(sender, stock_name)
            )
            
            # 添加返回按钮
            if from_holdings:
                detail_panel.add_button(
                    "返回持仓",
                    on_click=lambda sender: self.show_holdings_panel(sender)
                )
            else:
                detail_panel.add_button(
                    "返回主菜单",
                    on_click=lambda sender: self.show_main_panel(sender)
                )
            
            player.send_form(detail_panel)
            
        except Exception as e:
            print(f"显示股票详情错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示股票详情时发生错误")
    
    def _handle_add_favorite(self, player, stock_name: str):
        """处理添加收藏"""
        xuid = player.xuid
        
        if self.plugin.favorites_manager.add_favorite(xuid, stock_name):
            player.send_message(f"已添加 {stock_name} 到收藏")
        else:
            player.send_message(f"添加收藏失败（可能已存在）")
        
        # 返回股票详情
        self.show_stock_detail_panel(player, stock_name)
    
    def _handle_remove_favorite(self, player, stock_name: str):
        """处理取消收藏"""
        xuid = player.xuid
        
        if self.plugin.favorites_manager.remove_favorite(xuid, stock_name):
            player.send_message(f"已取消收藏 {stock_name}")
        else:
            player.send_message(f"取消收藏失败")
        
        # 返回股票详情
        self.show_stock_detail_panel(player, stock_name)
    
    def _show_price_history_panel(self, player, stock_name: str):
        """显示价格走势面板"""
        player.send_message(f"正在查询 {stock_name} 的价格走势...")
        
        # 使用线程执行查询，然后用调度器在主线程显示UI
        import threading
        
        def show_history():
            try:
                xuid = player.xuid
                price_list, tradeable = self.plugin.get_stock_last_price(
                    stock_name, 
                    period="1mo", 
                    interval="1d", 
                    return_period=True
                )
                
                if price_list is None:
                    # 使用调度器在主线程发送消息
                    self.plugin.server.scheduler.run_task(
                        self.plugin,
                        lambda: player.send_message(f"无法获取 {stock_name} 的价格数据"),
                        delay=0
                    )
                    return
                
                # 构建价格走势内容
                content = f"=== {stock_name} 价格走势 ===\n\n"
                content += f"近10个交易日价格变化:\n\n"
                
                price_list = price_list[-11:]  # 取最后11天（包括基准日）
                
                for idx in range(1, len(price_list)):
                    prev_price = price_list[idx - 1]
                    curr_price = price_list[idx]
                    change = curr_price - prev_price
                    change_percent = (change / prev_price * 100) if prev_price > 0 else 0
                    
                    # 获取颜色
                    color = self.plugin.player_settings_manager.get_color_for_change(xuid, change)
                    
                    # 格式化显示
                    if change > 0:
                        content += f"第{idx}天: ${curr_price:.2f} {color}▲+${abs(change):.2f} (+{change_percent:.2f}%)§r\n"
                    elif change < 0:
                        content += f"第{idx}天: ${curr_price:.2f} {color}▼${abs(change):.2f} ({change_percent:.2f}%)§r\n"
                    else:
                        content += f"第{idx}天: ${curr_price:.2f} §7━ ${abs(change):.2f} (0.00%%)§r\n"
                
                content += f"\n§7提示: 建议使用专业股票软件查询最新价格§r"
                
                # 使用调度器在主线程显示面板
                def show_panel():
                    history_panel = ActionForm(
                        title=f"{stock_name} 价格走势",
                        content=content
                    )
                    
                    history_panel.add_button(
                        "返回股票详情",
                        on_click=lambda sender: self.show_stock_detail_panel(sender, stock_name)
                    )
                    
                    player.send_form(history_panel)
                
                self.plugin.server.scheduler.run_task(
                    self.plugin,
                    show_panel,
                    delay=0
                )
                
            except Exception as e:
                print(f"查询价格走势错误: {str(e)}")
                import traceback
                traceback.print_exc()
                # 使用调度器在主线程发送消息
                self.plugin.server.scheduler.run_task(
                    self.plugin,
                    lambda: player.send_message("查询价格走势时发生错误"),
                    delay=0
                )
        
        thread = threading.Thread(target=show_history)
        thread.start()
    
    # ==================== 买入面板 ====================
    def show_buy_panel(self, player, stock_name: str):
        """显示买入面板"""
        try:
            xuid = player.xuid
            
            # 获取当前价格
            current_price, tradeable = self.plugin.get_stock_last_price(stock_name)
            
            if current_price is None:
                player.send_message(f"§c无法获取股票 {stock_name} 的价格信息")
                return
            
            # 获取账户余额
            balance = self.plugin.stock_dao.get_balance(xuid)
            
            buy_form = ModalForm(
                title=f"买入 {stock_name}",
                controls=[
                    Label(text=f"当前价格: ${current_price:.2f}\n账户余额: ${balance:.2f}\n手续费: 2%\n\n请输入购买信息:"),
                    TextInput(
                        label="购买股数",
                        placeholder="请输入要购买的股数（整数）...",
                        default_value="1"
                    ),
                    Dropdown(
                        label="订单类型",
                        options=["市价单（立即成交）", "限价单（指定价格）"],
                        default_index=0
                    ),
                    TextInput(
                        label="限价（仅限价单需要）",
                        placeholder="限价单时填写期望价格...",
                        default_value=str(float(current_price))
                    )
                ],
                on_submit=lambda sender, json_str: self._handle_buy_stock(sender, stock_name, current_price, json_str),
                on_close=lambda sender: self.show_stock_detail_panel(sender, stock_name)
            )
            
            player.send_form(buy_form)
            
        except Exception as e:
            print(f"显示买入面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示买入面板时发生错误")
    
    def _handle_buy_stock(self, player, stock_name: str, market_price, json_str: str):
        """处理买入股票"""
        try:
            xuid = player.xuid
            data = json.loads(json_str)
            
            # 解析输入
            share_str = data[1]
            order_type_index = data[2]
            limit_price_str = data[3]
            
            # 验证股数
            try:
                share = int(share_str)
                if share <= 0:
                    raise ValueError()
            except:
                player.send_message("§c请输入有效的股数（大于0的整数）")
                self.show_buy_panel(player, stock_name)
                return
            
            # 确定价格和订单类型
            if order_type_index == 0:  # 市价单
                price = Decimal(str(market_price))
                order_type = "buy_flex"
            else:  # 限价单
                try:
                    price = Decimal(limit_price_str)
                    if price <= 0:
                        raise ValueError()
                except:
                    player.send_message("§c请输入有效的限价（大于0的数字）")
                    self.show_buy_panel(player, stock_name)
                    return
                order_type = "buy_fix"
            
            # 检查限价单价格
            if order_type == "buy_fix" and price < market_price:
                player.send_message(f"§c买入失败: 您的限价 ${price:.2f} 低于市场价 ${market_price:.2f}")
                self.show_buy_panel(player, stock_name)
                return
            
            # 计算总价
            share_decimal = Decimal(str(share))
            tax = price * share_decimal * Decimal('0.02')
            total_price = price * share_decimal + tax
            
            # 检查余额
            balance = self.plugin.stock_dao.get_balance(xuid)
            if balance < total_price:
                player.send_message(f"§c余额不足: 需要 ${total_price:.2f}，当前余额 ${balance:.2f}")
                self.show_buy_panel(player, stock_name)
                return
            
            # 创建订单
            order_id = self.plugin.stock_dao.create_order(xuid, stock_name, share, order_type)
            
            # 执行买入
            self.plugin.stock_dao.decrease_balance(xuid, float(total_price))
            self.plugin.stock_dao.buy(order_id, stock_name, xuid, share_decimal, price, tax, total_price)
            
            # 显示结果
            result_form = ActionForm(
                title="买入成功",
                content=f"成功买入 {stock_name}\n\n股数: {share}\n单价: ${price:.2f}\n手续费: ${tax:.2f}\n总价: ${total_price:.2f}",
                on_close=lambda sender: self.show_stock_detail_panel(sender, stock_name)
            )
            player.send_form(result_form)
            
        except Exception as e:
            print(f"买入股票错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c买入股票时发生错误")
    
    # ==================== 卖出面板 ====================
    def show_sell_panel(self, player, stock_name: str):
        """显示卖出面板"""
        try:
            xuid = player.xuid
            
            # 获取当前价格
            current_price, tradeable = self.plugin.get_stock_last_price(stock_name)
            
            if current_price is None:
                player.send_message(f"§c无法获取股票 {stock_name} 的价格信息")
                return
            
            # 获取持仓
            holding = self.plugin.stock_dao.get_player_stock_holding(xuid, stock_name)
            
            if holding <= 0:
                player.send_message(f"§c您没有持有 {stock_name}")
                self.show_stock_detail_panel(player, stock_name)
                return
            
            sell_form = ModalForm(
                title=f"卖出 {stock_name}",
                controls=[
                    Label(text=f"当前价格: ${current_price:.2f}\n持有股数: {holding}\n手续费: 2%\n\n请输入卖出信息:"),
                    TextInput(
                        label="卖出股数",
                        placeholder=f"请输入要卖出的股数（最多{holding}）...",
                        default_value=str(holding)
                    ),
                    Dropdown(
                        label="订单类型",
                        options=["市价单（立即成交）", "限价单（指定价格）"],
                        default_index=0
                    ),
                    TextInput(
                        label="限价（仅限价单需要）",
                        placeholder="限价单时填写期望价格...",
                        default_value=str(float(current_price))
                    )
                ],
                on_submit=lambda sender, json_str: self._handle_sell_stock(sender, stock_name, current_price, holding, json_str),
                on_close=lambda sender: self.show_stock_detail_panel(sender, stock_name)
            )
            
            player.send_form(sell_form)
            
        except Exception as e:
            print(f"显示卖出面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示卖出面板时发生错误")
    
    def _handle_sell_stock(self, player, stock_name: str, market_price, max_holding: int, json_str: str):
        """处理卖出股票"""
        try:
            xuid = player.xuid
            data = json.loads(json_str)
            
            # 解析输入
            share_str = data[1]
            order_type_index = data[2]
            limit_price_str = data[3]
            
            # 验证股数
            try:
                share = int(share_str)
                if share <= 0 or share > max_holding:
                    raise ValueError()
            except:
                player.send_message(f"§c请输入有效的股数（1-{max_holding}）")
                self.show_sell_panel(player, stock_name)
                return
            
            # 确定价格和订单类型
            if order_type_index == 0:  # 市价单
                price = Decimal(str(market_price))
                order_type = "sell_flex"
            else:  # 限价单
                try:
                    price = Decimal(limit_price_str)
                    if price <= 0:
                        raise ValueError()
                except:
                    player.send_message("§c请输入有效的限价（大于0的数字）")
                    self.show_sell_panel(player, stock_name)
                    return
                order_type = "sell_fix"
            
            # 检查限价单价格
            if order_type == "sell_fix" and market_price < price:
                player.send_message(f"§c卖出失败: 市场价 ${market_price:.2f} 低于您的限价 ${price:.2f}")
                self.show_sell_panel(player, stock_name)
                return
            
            # 计算收入
            share_decimal = Decimal(str(share))
            total_price = price * share_decimal
            tax = total_price * Decimal('0.02')
            net_revenue = total_price - tax
            
            # 创建订单
            order_id = self.plugin.stock_dao.create_order(xuid, stock_name, share, order_type)
            
            # 执行卖出
            self.plugin.stock_dao.sell(order_id, stock_name, xuid, share_decimal, price, tax, total_price)
            self.plugin.stock_dao.increase_balance(xuid, float(net_revenue))
            
            # 显示结果
            result_form = ActionForm(
                title="卖出成功",
                content=f"成功卖出 {stock_name}\n\n股数: {share}\n单价: ${price:.2f}\n手续费: ${tax:.2f}\n净收入: ${net_revenue:.2f}",
                on_close=lambda sender: self.show_stock_detail_panel(sender, stock_name)
            )
            player.send_form(result_form)
            
        except Exception as e:
            print(f"卖出股票错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c卖出股票时发生错误")
    
    # ==================== 历史订单面板 ====================
    def show_orders_panel(self, player, page: int = 0):
        """显示历史订单面板"""
        try:
            xuid = player.xuid
            orders = self.plugin.stock_dao.get_orders(xuid, page=page, page_size=10)
            
            if not orders:
                no_orders_form = ActionForm(
                    title="历史订单",
                    content="您还没有任何订单记录",
                    on_close=lambda sender: self.show_main_panel(sender)
                )
                player.send_form(no_orders_form)
                return
            
            # 构建订单列表
            content = "=== 历史订单 ===\n\n"
            
            order_type_dict = {
                "buy_flex": "市价买入",
                "buy_fix": "限价买入",
                "sell_flex": "市价卖出",
                "sell_fix": "限价卖出"
            }
            
            for order in orders:
                content += f"订单#{order['id']}\n"
                content += f"  {order_type_dict.get(order['type'], order['type'])}\n"
                content += f"  股票: {order['stock_name']} | 股数: {order['share']}\n"
                content += f"  单价: ${order['single_price']:.2f} | 总价: ${order['total']:.2f}\n"
                content += f"  手续费: ${order['tax']:.2f}\n\n"
            
            orders_panel = ActionForm(
                title="历史订单",
                content=content
            )
            
            # 如果有下一页，添加按钮
            if len(orders) >= 10:
                orders_panel.add_button(
                    "下一页",
                    on_click=lambda sender: self.show_orders_panel(sender, page + 1)
                )
            
            # 如果不是第一页，添加上一页按钮
            if page > 0:
                orders_panel.add_button(
                    "上一页",
                    on_click=lambda sender: self.show_orders_panel(sender, page - 1)
                )
            
            # 添加返回按钮
            orders_panel.add_button(
                "返回主菜单",
                on_click=lambda sender: self.show_main_panel(sender)
            )
            
            player.send_form(orders_panel)
            
        except Exception as e:
            print(f"显示订单面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示订单面板时发生错误")
    
    # ==================== 账户管理面板 ====================
    def show_account_panel(self, player):
        """显示账户管理面板"""
        try:
            xuid = player.xuid
            balance = self.plugin.stock_dao.get_balance(xuid)
            game_balance = self.plugin.economy_plugin.get_player_money(player)
            
            content = f"=== 账户管理 ===\n\n"
            content += f"股票账户余额: ${balance:.2f}\n"
            content += f"游戏币余额: ${game_balance:.2f}\n\n"
            content += f"您可以在股票账户和游戏账户之间转账"
            
            account_panel = ActionForm(
                title="账户管理",
                content=content
            )
            
            account_panel.add_button(
                "从游戏账户转入",
                on_click=lambda sender: self.show_transfer_in_panel(sender)
            )
            
            account_panel.add_button(
                "转出到游戏账户",
                on_click=lambda sender: self.show_transfer_out_panel(sender)
            )
            
            account_panel.add_button(
                "返回主菜单",
                on_click=lambda sender: self.show_main_panel(sender)
            )
            
            player.send_form(account_panel)
            
        except Exception as e:
            print(f"显示账户管理面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("§c显示账户管理面板时发生错误")
    
    def show_transfer_in_panel(self, player):
        """显示转入面板"""
        game_balance = self.plugin.economy_plugin.get_player_money(player)
        
        transfer_form = ModalForm(
            title="转入资金",
            controls=[
                Label(text=f"从游戏账户转入股票账户\n\n游戏币余额: ${game_balance:.2f}"),
                TextInput(
                    label="转入金额",
                    placeholder="请输入要转入的金额...",
                    default_value=""
                )
            ],
            on_submit=lambda sender, json_str: self._handle_transfer_in(sender, json_str),
            on_close=lambda sender: self.show_account_panel(sender)
        )
        player.send_form(transfer_form)
    
    def _handle_transfer_in(self, player, json_str: str):
        """处理转入"""
        try:
            data = json.loads(json_str)
            amount_str = data[1]
            
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError()
            except:
                player.send_message("§c请输入有效的金额（大于0的数字）")
                self.show_transfer_in_panel(player)
                return
            
            # 检查余额
            game_balance = self.plugin.economy_plugin.get_player_money(player)
            if game_balance < amount:
                player.send_message(f"§c游戏币余额不足，当前余额: ${game_balance:.2f}")
                self.show_transfer_in_panel(player)
                return
            
            # 执行转账
            self.plugin.economy_plugin.decrease_player_money(player, amount)
            self.plugin.stock_dao.increase_balance(player.xuid, amount, is_transfer_in=True)
            
            player.send_message(f"§a成功转入 ${amount:.2f} 到股票账户")
            self.show_account_panel(player)
            
        except Exception as e:
            print(f"转入错误: {str(e)}")
            player.send_message("§c转入时发生错误")
    
    def show_transfer_out_panel(self, player):
        """显示转出面板"""
        stock_balance = self.plugin.stock_dao.get_balance(player.xuid)
        
        transfer_form = ModalForm(
            title="转出资金",
            controls=[
                Label(text=f"从股票账户转出到游戏账户\n\n股票账户余额: ${stock_balance:.2f}"),
                TextInput(
                    label="转出金额",
                    placeholder="请输入要转出的金额...",
                    default_value=""
                )
            ],
            on_submit=lambda sender, json_str: self._handle_transfer_out(sender, json_str),
            on_close=lambda sender: self.show_account_panel(sender)
        )
        player.send_form(transfer_form)
    
    def _handle_transfer_out(self, player, json_str: str):
        """处理转出"""
        try:
            data = json.loads(json_str)
            amount_str = data[1]
            
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError()
            except:
                player.send_message("§c请输入有效的金额（大于0的数字）")
                self.show_transfer_out_panel(player)
                return
            
            # 检查余额
            stock_balance = self.plugin.stock_dao.get_balance(player.xuid)
            if stock_balance < amount:
                player.send_message(f"§c股票账户余额不足，当前余额: ${stock_balance:.2f}")
                self.show_transfer_out_panel(player)
                return
            
            # 执行转账
            self.plugin.stock_dao.decrease_balance(player.xuid, amount, is_transfer_out=True)
            self.plugin.economy_plugin.increase_player_money(player, amount)
            
            player.send_message(f"§a成功转出 ${amount:.2f} 到游戏账户")
            self.show_account_panel(player)
            
        except Exception as e:
            print(f"转出错误: {str(e)}")
            player.send_message("§c转出时发生错误")
    
    # ==================== 个人设置面板 ====================
    def show_player_settings_panel(self, player):
        """显示个人设置面板"""
        try:
            xuid = player.xuid
            
            # 获取当前配色方案
            current_scheme = self.plugin.player_settings_manager.get_color_scheme(xuid)
            scheme_text = "红涨绿跌（中国习惯）" if current_scheme == 'red_up' else "绿涨红跌（美国习惯）"
            
            content = f"=== 个人设置 ===\n\n"
            content += f"当前配色方案: {scheme_text}\n\n"
            content += f"说明:\n"
            content += f"- 红涨绿跌: 中国股市习惯，上涨显示红色\n"
            content += f"- 绿涨红跌: 美国股市习惯，上涨显示绿色\n\n"
            content += f"选择一个配色方案:"
            
            settings_panel = ActionForm(
                title="个人设置",
                content=content
            )
            
            settings_panel.add_button(
                "红涨绿跌（中国）",
                on_click=lambda sender: self._set_color_scheme(sender, 'red_up')
            )
            
            settings_panel.add_button(
                "绿涨红跌（美国）",
                on_click=lambda sender: self._set_color_scheme(sender, 'green_up')
            )
            
            settings_panel.add_button(
                "返回主菜单",
                on_click=lambda sender: self.show_main_panel(sender)
            )
            
            player.send_form(settings_panel)
            
        except Exception as e:
            print(f"显示个人设置面板错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("显示个人设置面板时发生错误")
    
    def _set_color_scheme(self, player, scheme: str):
        """设置配色方案"""
        xuid = player.xuid
        
        if self.plugin.player_settings_manager.set_color_scheme(xuid, scheme):
            scheme_text = "红涨绿跌" if scheme == 'red_up' else "绿涨红跌"
            player.send_message(f"已设置配色方案为: {scheme_text}")
        else:
            player.send_message("设置配色方案失败")
        
        # 返回设置面板
        self.show_player_settings_panel(player)
    
    # ==================== 排行榜面板 ====================
    def show_leaderboard_menu(self, player):
        """显示排行榜菜单"""
        try:
            content = "=== 盈亏排行榜 ===\n\n"
            content += "选择要查看的排行榜类型:\n\n"
            content += "- 绝对盈亏: 按赚/亏的金额排序\n"
            content += "- 相对盈亏: 按盈亏百分比排序"
            
            menu_panel = ActionForm(
                title="盈亏排行榜",
                content=content
            )
            
            menu_panel.add_button(
                "绝对盈亏榜",
                on_click=lambda sender: self.show_absolute_leaderboard(sender)
            )
            
            menu_panel.add_button(
                "相对盈亏榜",
                on_click=lambda sender: self.show_relative_leaderboard(sender)
            )
            
            menu_panel.add_button(
                "返回主菜单",
                on_click=lambda sender: self.show_main_panel(sender)
            )
            
            player.send_form(menu_panel)
            
        except Exception as e:
            print(f"显示排行榜菜单错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("显示排行榜菜单时发生错误")
    
    def show_absolute_leaderboard(self, player):
        """显示绝对盈亏排行榜"""
        try:
            xuid = player.xuid
            
            # 获取所有玩家数据
            all_data = self.plugin.stock_dao.get_all_players_profit_loss(
                self.plugin.get_stock_last_price
            )
            
            if not all_data:
                no_data_form = ActionForm(
                    title="绝对盈亏榜",
                    content="暂无数据",
                    on_close=lambda sender: self.show_leaderboard_menu(sender)
                )
                player.send_form(no_data_form)
                return
            
            # 按绝对盈亏排序
            sorted_data = sorted(all_data, key=lambda x: x['absolute_profit_loss'], reverse=True)
            
            # 获取玩家颜色配置
            up_color = self.plugin.player_settings_manager.get_up_color(xuid)
            down_color = self.plugin.player_settings_manager.get_down_color(xuid)
            
            # 构建内容
            content = "=== 绝对盈亏排行榜 ===\n\n"
            content += "§l§6前5名 (土豪榜)§r\n\n"
            
            # 显示前5名
            for idx, data in enumerate(sorted_data[:5], 1):
                player_name = self._get_player_name(data['player_xuid'])
                profit_loss = data['absolute_profit_loss']
                
                # 使用统一的颜色逻辑
                color = self.plugin.player_settings_manager.get_color_for_change(xuid, profit_loss)
                if profit_loss > 0:
                    sign = "+"
                elif profit_loss < 0:
                    sign = ""
                else:
                    sign = ""
                
                if idx == 1:
                    medal = "🥇"
                elif idx == 2:
                    medal = "🥈"
                elif idx == 3:
                    medal = "🥉"
                else:
                    medal = f"#{idx}"
                
                content += f"{medal} {player_name}\n"
                content += f"   盈亏: {color}{sign}${abs(profit_loss):.2f}§r\n"
                content += f"   总财富: ${data['total_wealth']:.2f}\n"
                content += f"   (持仓: ${data['holdings_value']:.2f} + 余额: ${data['balance']:.2f})\n"
                content += f"   累计投入: ${data['total_investment']:.2f}\n\n"
            
            content += "§l§7倒数5名 (韭菜榜)§r\n\n"
            
            # 显示倒数5名
            bottom_5 = sorted_data[-5:]
            bottom_5.reverse()  # 从最惨的开始
            
            for idx, data in enumerate(bottom_5, 1):
                player_name = self._get_player_name(data['player_xuid'])
                profit_loss = data['absolute_profit_loss']
                
                # 使用统一的颜色逻辑
                color = self.plugin.player_settings_manager.get_color_for_change(xuid, profit_loss)
                if profit_loss > 0:
                    sign = "+"
                elif profit_loss < 0:
                    sign = ""
                else:
                    sign = ""
                
                # 修正排名计算：倒数第1名应该是总排名最后一名
                actual_rank = len(sorted_data) - len(bottom_5) + idx
                content += f"#{actual_rank} {player_name}\n"
                content += f"   盈亏: {color}{sign}${abs(profit_loss):.2f}§r\n"
                content += f"   总财富: ${data['total_wealth']:.2f}\n"
                content += f"   (持仓: ${data['holdings_value']:.2f} + 余额: ${data['balance']:.2f})\n"
                content += f"   累计投入: ${data['total_investment']:.2f}\n\n"
            
            leaderboard_panel = ActionForm(
                title="绝对盈亏榜",
                content=content
            )
            
            leaderboard_panel.add_button(
                "返回排行榜菜单",
                on_click=lambda sender: self.show_leaderboard_menu(sender)
            )
            
            player.send_form(leaderboard_panel)
            
        except Exception as e:
            print(f"显示绝对盈亏排行榜错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("显示绝对盈亏排行榜时发生错误")
    
    def show_relative_leaderboard(self, player):
        """显示相对盈亏排行榜"""
        try:
            xuid = player.xuid
            
            # 获取所有玩家数据
            all_data = self.plugin.stock_dao.get_all_players_profit_loss(
                self.plugin.get_stock_last_price
            )
            
            if not all_data:
                no_data_form = ActionForm(
                    title="相对盈亏榜",
                    content="暂无数据",
                    on_close=lambda sender: self.show_leaderboard_menu(sender)
                )
                player.send_form(no_data_form)
                return
            
            # 过滤掉投资额为0的玩家
            valid_data = [d for d in all_data if d['total_investment'] > 0]
            
            if not valid_data:
                no_data_form = ActionForm(
                    title="相对盈亏榜",
                    content="暂无有效投资数据",
                    on_close=lambda sender: self.show_leaderboard_menu(sender)
                )
                player.send_form(no_data_form)
                return
            
            # 按相对盈亏排序
            sorted_data = sorted(valid_data, key=lambda x: x['relative_profit_loss'], reverse=True)
            
            # 获取玩家颜色配置
            up_color = self.plugin.player_settings_manager.get_up_color(xuid)
            down_color = self.plugin.player_settings_manager.get_down_color(xuid)
            
            # 构建内容
            content = "=== 相对盈亏排行榜 ===\n\n"
            content += "§l§6前5名 (高手榜)§r\n\n"
            
            # 显示前5名
            for idx, data in enumerate(sorted_data[:5], 1):
                player_name = self._get_player_name(data['player_xuid'])
                profit_loss_percent = data['relative_profit_loss']
                profit_loss = data['absolute_profit_loss']
                
                # 使用统一的颜色逻辑
                color = self.plugin.player_settings_manager.get_color_for_change(xuid, profit_loss)
                if profit_loss_percent > 0:
                    sign = "+"
                elif profit_loss_percent < 0:
                    sign = "-"
                else:
                    sign = ""
                
                if idx == 1:
                    medal = "🥇"
                elif idx == 2:
                    medal = "🥈"
                elif idx == 3:
                    medal = "🥉"
                else:
                    medal = f"#{idx}"
                
                content += f"{medal} {player_name}\n"
                content += f"   收益率: {color}{sign}{abs(profit_loss_percent):.2f}%%§r\n"
                content += f"   盈亏: {color}{sign}${abs(profit_loss):.2f}§r\n\n"
            
            content += "§l§7倒数5名 (接盘侠榜)§r\n\n"
            
            # 显示倒数5名
            bottom_5 = sorted_data[-5:]
            bottom_5.reverse()  # 从最惨的开始
            
            for idx, data in enumerate(bottom_5, 1):
                player_name = self._get_player_name(data['player_xuid'])
                profit_loss_percent = data['relative_profit_loss']
                profit_loss = data['absolute_profit_loss']
                
                # 使用统一的颜色逻辑
                color = self.plugin.player_settings_manager.get_color_for_change(xuid, profit_loss)
                if profit_loss_percent > 0:
                    sign = "+"
                elif profit_loss_percent < 0:
                    sign = "-"
                else:
                    sign = ""
                
                # 修正排名计算：倒数第1名应该是总排名最后一名
                actual_rank = len(sorted_data) - len(bottom_5) + idx
                content += f"#{actual_rank} {player_name}\n"
                content += f"   收益率: {color}{sign}{abs(profit_loss_percent):.2f}%%§r\n"
                content += f"   盈亏: {color}{sign}${abs(profit_loss):.2f}§r\n\n"
            
            leaderboard_panel = ActionForm(
                title="相对盈亏榜",
                content=content
            )
            
            leaderboard_panel.add_button(
                "返回排行榜菜单",
                on_click=lambda sender: self.show_leaderboard_menu(sender)
            )
            
            player.send_form(leaderboard_panel)
            
        except Exception as e:
            print(f"显示相对盈亏排行榜错误: {str(e)}")
            import traceback
            traceback.print_exc()
            player.send_message("显示相对盈亏排行榜时发生错误")
    
    def _get_player_name(self, player_xuid: str) -> str:
        """
        根据XUID获取玩家名称
        :param player_xuid: 玩家XUID
        :return: 玩家名称，如果获取不到则返回XUID前8位
        """
        try:
            # 使用arc_core插件获取玩家名称
            arc_core = self.plugin.server.plugin_manager.get_plugin('arc_core')
            if arc_core:
                player_name = arc_core.get_player_name_by_xuid(player_xuid)
                if player_name:
                    return player_name
            
            # 如果获取失败，返回XUID的前8位作为标识
            return f"玩家{player_xuid[:8]}"
        except:
            return f"玩家{player_xuid[:8]}"

