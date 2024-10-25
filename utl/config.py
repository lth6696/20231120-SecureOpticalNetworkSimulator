import os
import sys
import configparser as cfg


class Config:
    """
    读取配置文件，存储字条信息
    """
    def __init__(self):
        self.config = cfg.ConfigParser()

    def read(self, config_file: str):
        """
        输入：配置文件路径
        输出：返回configer
        读取算法配置、拓扑配置、事件配置、流量配置
        """
        # 检查输入
        if not os.path.exists(config_file):
            raise Exception("Config file does not exist.")
        self.config.read(config_file)

        # 读取属性
        # sections = self.config.sections()
        # if input(f"Do you want to set {sections}?[Y/n]\n") != "Y":
        #     sys.exit()
        return self.config