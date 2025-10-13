"""
玩家个人设置管理器
"""
from typing import Dict, Optional
from .databaseManager import DatabaseManager


class PlayerSettingsManager:
    def __init__(self, database_manager: DatabaseManager):
        """
        初始化玩家设置管理器
        :param database_manager: 数据库管理器实例
        """
        self.database_manager = database_manager
        self._init_settings_table()
    
    def _init_settings_table(self) -> None:
        """创建玩家设置表"""
        self.database_manager.create_table("tb_player_settings", {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "player_xuid": "TEXT NOT NULL UNIQUE",
            "color_scheme": "TEXT NOT NULL DEFAULT 'red_up'",  # 'red_up' 或 'green_up'
            "created_time": "REAL NOT NULL",
            "updated_time": "REAL NOT NULL"
        })
    
    def get_color_scheme(self, player_xuid: str) -> str:
        """
        获取玩家的涨跌配色方案
        :param player_xuid: 玩家XUID
        :return: 'red_up' (红涨绿跌) 或 'green_up' (绿涨红跌)
        """
        setting = self.database_manager.query_one(
            "SELECT color_scheme FROM tb_player_settings WHERE player_xuid = ?",
            (player_xuid,)
        )
        
        if setting:
            return setting['color_scheme']
        
        # 默认返回红涨绿跌（中国习惯）
        return 'red_up'
    
    def set_color_scheme(self, player_xuid: str, color_scheme: str) -> bool:
        """
        设置玩家的涨跌配色方案
        :param player_xuid: 玩家XUID
        :param color_scheme: 'red_up' 或 'green_up'
        :return: 是否设置成功
        """
        import time
        
        if color_scheme not in ['red_up', 'green_up']:
            return False
        
        # 检查是否已有设置
        existing = self.database_manager.query_one(
            "SELECT * FROM tb_player_settings WHERE player_xuid = ?",
            (player_xuid,)
        )
        
        current_time = time.time()
        
        if existing:
            # 更新现有设置
            return self.database_manager.update(
                "tb_player_settings",
                {
                    "color_scheme": color_scheme,
                    "updated_time": current_time
                },
                "player_xuid = ?",
                (player_xuid,)
            )
        else:
            # 插入新设置
            return self.database_manager.insert("tb_player_settings", {
                "player_xuid": player_xuid,
                "color_scheme": color_scheme,
                "created_time": current_time,
                "updated_time": current_time
            })
    
    def get_up_color(self, player_xuid: str) -> str:
        """
        获取上涨颜色代码
        :param player_xuid: 玩家XUID
        :return: Minecraft 颜色代码
        """
        scheme = self.get_color_scheme(player_xuid)
        return "§c" if scheme == 'red_up' else "§a"
    
    def get_down_color(self, player_xuid: str) -> str:
        """
        获取下跌颜色代码
        :param player_xuid: 玩家XUID
        :return: Minecraft 颜色代码
        """
        scheme = self.get_color_scheme(player_xuid)
        return "§a" if scheme == 'red_up' else "§c"
    
    def get_color_for_change(self, player_xuid: str, change: float) -> str:
        """
        根据涨跌值获取颜色代码
        :param player_xuid: 玩家XUID
        :param change: 涨跌值（正数为涨，负数为跌）
        :return: Minecraft 颜色代码
        """
        if change > 0:
            return self.get_up_color(player_xuid)
        elif change < 0:
            return self.get_down_color(player_xuid)
        else:
            return "§7"  # 平盘为灰色

