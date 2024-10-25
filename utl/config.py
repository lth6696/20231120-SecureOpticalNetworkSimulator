import os
import sys
import configparser as cfg


class Config:
    """
    读取配置文件，存储字条信息
    """
    def __init__(self):
        self.config: cfg.ConfigParser = cfg.ConfigParser()

    def read(self, config_file: str):
        """
        输入：配置文件路径
        输出：返回configer
        读取算法配置、拓扑配置、事件配置、流量配置
        """
        # 检查输入
        if not os.path.exists(config_file):
            raise Exception("Config file does not exist.")
        self.tree = ET.parse(config_file)
        root = self.tree.getroot()
        if root.tag.lower() != self.CONFIG_NAME and root.attrib['version'] != self.SIMULATOR_VERSION:
            raise AttributeError
        # 读取属性
        setting_names = [child.tag for child in root]
        if input(f"Do you want to set {setting_names}?[Y/n]\n") != "Y":
            sys.exit()
        for name in setting_names:
            self._set()

    def _set(self):
        pass