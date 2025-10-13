"""
股票插件配置管理器
"""
import os
from pathlib import Path


class StockSettingManager:
    setting_dict = {}  # 类变量存储所有配置
    
    def __init__(self, main_path: str):
        """
        初始化配置管理器
        :param main_path: 插件主目录路径
        """
        self.setting_file_path = Path(main_path) / "stock_setting.yml"
        self._load_setting_file()
    
    def _load_setting_file(self):
        """加载配置文件"""
        # 创建配置目录（如果不存在）
        self.setting_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建配置文件（如果不存在）
        if not self.setting_file_path.exists():
            # 创建默认配置
            self._create_default_config()
        
        # 加载配置文件内容
        with self.setting_file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    StockSettingManager.setting_dict[key.strip()] = value.strip()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = """# 股票插件配置文件
# Stock Plugin Configuration File

# VPN代理设置（留空则不使用代理）
# VPN Proxy Settings (leave empty to disable proxy)
# 格式: IP:端口 或 留空
# Format: IP:Port or leave empty
# 示例 / Example: 127.0.0.1:7890
proxy=127.0.0.1:5555

# 是否启用代理（true/false）
# Enable proxy (true/false)
enable_proxy=true

# 股票数据更新间隔（秒）
# Stock data update interval (seconds)
update_interval=60
"""
        with self.setting_file_path.open("w", encoding="utf-8") as f:
            f.write(default_config)
        
        # 同时加载默认值到内存
        StockSettingManager.setting_dict["proxy"] = "127.0.0.1:5555"
        StockSettingManager.setting_dict["enable_proxy"] = "true"
        StockSettingManager.setting_dict["update_interval"] = "60"
    
    def get_setting(self, key: str, default_value: str = None):
        """
        获取配置项
        :param key: 配置键
        :param default_value: 默认值
        :return: 配置值
        """
        # 如果配置项不存在，添加它
        if key not in StockSettingManager.setting_dict:
            with self.setting_file_path.open("a", encoding="utf-8") as f:
                f.write(f"\n{key}=")
            StockSettingManager.setting_dict[key] = ""
        
        value = StockSettingManager.setting_dict[key]
        return default_value if not value else value
    
    def set_setting(self, key: str, value: str):
        """
        设置配置项
        :param key: 配置键
        :param value: 配置值
        """
        # 更新内存中的配置
        StockSettingManager.setting_dict[key] = str(value)
        
        # 重写整个文件
        with self.setting_file_path.open("w", encoding="utf-8") as f:
            for k, v in StockSettingManager.setting_dict.items():
                f.write(f"{k}={v}\n")
    
    def get_proxy_config(self):
        """
        获取代理配置
        :return: (是否启用代理, 代理地址) 或 (False, None)
        """
        enable_proxy = self.get_setting("enable_proxy", "true").lower() == "true"
        proxy = self.get_setting("proxy", "")
        
        if enable_proxy and proxy:
            return True, proxy
        return False, None
    
    def get_update_interval(self):
        """
        获取更新间隔（秒）
        :return: 更新间隔
        """
        try:
            return int(self.get_setting("update_interval", "60"))
        except ValueError:
            return 60

