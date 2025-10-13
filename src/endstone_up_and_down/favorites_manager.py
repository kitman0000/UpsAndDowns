"""
股票收藏夹管理器
"""
from typing import List, Dict, Optional
from .databaseManager import DatabaseManager


class FavoritesManager:
    def __init__(self, database_manager: DatabaseManager):
        """
        初始化收藏夹管理器
        :param database_manager: 数据库管理器实例
        """
        self.database_manager = database_manager
        self._init_favorites_table()
    
    def _init_favorites_table(self) -> None:
        """创建收藏夹表"""
        self.database_manager.create_table("tb_stock_favorites", {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "player_xuid": "TEXT NOT NULL",
            "stock_name": "TEXT NOT NULL",
            "stock_display_name": "TEXT",
            "add_time": "REAL NOT NULL",
            "UNIQUE": "(player_xuid, stock_name)"
        })
    
    def add_favorite(self, player_xuid: str, stock_name: str, stock_display_name: str = None) -> bool:
        """
        添加收藏股票
        :param player_xuid: 玩家UUID
        :param stock_name: 股票代码
        :param stock_display_name: 股票显示名称（可选）
        :return: 是否添加成功
        """
        try:
            import time
            
            # 检查是否已经收藏
            if self.is_favorite(player_xuid, stock_name):
                return False
            
            self.database_manager.insert("tb_stock_favorites", {
                "player_xuid": player_xuid,
                "stock_name": stock_name,
                "stock_display_name": stock_display_name or stock_name,
                "add_time": time.time()
            })
            return True
        except Exception as e:
            print(f"添加收藏失败: {str(e)}")
            return False
    
    def remove_favorite(self, player_xuid: str, stock_name: str) -> bool:
        """
        取消收藏股票
        :param player_xuid: 玩家UUID
        :param stock_name: 股票代码
        :return: 是否取消成功
        """
        try:
            return self.database_manager.delete(
                "tb_stock_favorites",
                "player_xuid = ? AND stock_name = ?",
                (player_xuid, stock_name)
            )
        except Exception as e:
            print(f"取消收藏失败: {str(e)}")
            return False
    
    def is_favorite(self, player_xuid: str, stock_name: str) -> bool:
        """
        检查是否已收藏
        :param player_xuid: 玩家UUID
        :param stock_name: 股票代码
        :return: 是否已收藏
        """
        result = self.database_manager.query_one(
            "SELECT * FROM tb_stock_favorites WHERE player_xuid = ? AND stock_name = ?",
            (player_xuid, stock_name)
        )
        return result is not None
    
    def get_favorites(self, player_xuid: str, page: int = 0, page_size: int = 10) -> List[Dict]:
        """
        获取玩家的收藏列表
        :param player_xuid: 玩家UUID
        :param page: 页码（从0开始）
        :param page_size: 每页数量
        :return: 收藏列表
        """
        offset = page * page_size
        sql = """
            SELECT * FROM tb_stock_favorites 
            WHERE player_xuid = ? 
            ORDER BY add_time DESC 
            LIMIT ? OFFSET ?
        """
        return self.database_manager.query_all(sql, (player_xuid, page_size, offset))
    
    def get_favorites_count(self, player_xuid: str) -> int:
        """
        获取玩家的收藏数量
        :param player_xuid: 玩家UUID
        :return: 收藏数量
        """
        result = self.database_manager.query_one(
            "SELECT COUNT(*) as count FROM tb_stock_favorites WHERE player_xuid = ?",
            (player_xuid,)
        )
        return result['count'] if result else 0

