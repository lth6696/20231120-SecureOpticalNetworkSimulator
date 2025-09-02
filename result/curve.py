import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import numpy as np
from scipy import interpolate


def style(width, height, fontsize=11):
    plt.rcParams['figure.figsize'] = (width * 0.39370, height * 0.39370)  # figure size in inches
    # plt.rcParams['font.family'] = 'serif'
    # plt.rcParams['font.serif'] = ['Times New Roman']
    plt.rcParams['font.sans-serif'] = 'cambria'
    plt.rcParams['font.size'] = fontsize
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['patch.linewidth'] = 0.5
    plt.rcParams['axes.linewidth'] = 0.5
    plt.rcParams['ytick.major.width'] = 0.5
    plt.rcParams['xtick.major.width'] = 0.5
    plt.rcParams['ytick.direction'] = 'in'
    plt.rcParams['xtick.direction'] = 'in'


class PlotCurve:
    def __init__(self):
        self.colors = ["#C76109", "#D9AD47", "#2B9C80", "#81BADA", "#CF9EB6"]
        self.markers = ['s', 'o', 'p', 'X', 'd', 'v']
        self.line_styles = ['-', '--', ':', '-.', '-', '--']

    @staticmethod
    def plotRealTime(timeStamp: list, serviceNumList: list):
        if not serviceNumList:
            raise Exception("Empty list.")
        if len(timeStamp) != len(serviceNumList):
            raise Exception("Two list does not match!")
        plt.plot(timeStamp, serviceNumList)
        plt.show()

    def plotMultiRealTime(self, timeStamp: list, *args,
                          width: float = 5.3 * 1.3, height: float = 3.3 * 1.3,
                          legend: list = None, label: list = None):
        # colors = ["#E1C855", "#E07B54", "#51B1B7", "#E1C855", "#E07B54", "#51B1B7"]
        if len(args) < 1:
            raise Exception("Need at least one data list.")
        for data in args:
            if len(data) != len(timeStamp):
                raise Exception("Two list does not match!")
        style(width=width, height=height)
        for i, data in enumerate(args):
            plt.plot(timeStamp, data,
                     marker=self.markers[i], ms=2.0,  # set marker
                     ls=self.line_styles[i], lw=0.5,  # set line
                     color=self.colors[i])
        if label:
            plt.xlabel(label[0])
            plt.ylabel(label[1])
        # plt.xticks([100*(i+1) for i in range(9)])
        plt.yticks([5 * (i + 1) for i in range(6)])
        # plt.yticks([2 + 0.5 * i for i in range(5)])
        plt.grid(True, ls=':', lw=0.5, c='#d5d6d8')
        plt.tight_layout()
        if legend:
            plt.legend(legend, ncol=2)
        plt.show()

    def plot_block_rate(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        data_file = "./data_lsr_br.csv"
        data = pd.read_csv(data_file)

        # 数据预处理（根据图片信息调整列名和数据类型）
        # 确保列名与CSV文件实际列名匹配（注意空格和特殊字符）
        data = data.rename(columns={
            'link sec ratio': 'link_sec_ratio',
            'block_rate(t)': 'block_rate_t'
        })

        # 提取需要的数据列并转换为数值类型
        data['link_sec_ratio'] = pd.to_numeric(data['link_sec_ratio'], errors='coerce')
        data['block_rate_t'] = pd.to_numeric(data['block_rate_t'], errors='coerce')

        # 按算法分组处理
        algorithms = data['algorithm'].unique()
        style(width=width, height=height)

        for algo in algorithms:
            # 提取当前算法的数据
            algo_data = data[data['algorithm'] == algo]

            # 按link_sec_ratio排序并去重（取均值）
            grouped = algo_data.groupby('link_sec_ratio')['block_rate_t'].mean().reset_index()
            x = grouped['link_sec_ratio'].values
            y = grouped['block_rate_t'].values

            # 移除NaN值
            mask = ~(np.isnan(x) | np.isnan(y))
            x_clean = x[mask]
            y_clean = y[mask]

            if len(x_clean) > 3:  # 确保有足够的数据点进行插值
                # 创建插值函数（使用三次样条插值）
                f = interpolate.interp1d(x_clean, y_clean, kind='quadratic', fill_value='extrapolate')

                # 生成更密集的x值用于平滑曲线
                x_smooth = np.linspace(min(x_clean), max(x_clean), 300)
                y_smooth = f(x_smooth)

                # 绘制曲线
                plt.plot(x_smooth, y_smooth, label=algo, linewidth=1.5, alpha=0.8, zorder=100)

                # 可选：在原数据点位置添加标记
                plt.scatter(x_clean, y_clean, s=15, zorder=100)
            else:
                # 数据点不足时直接绘制散点图
                plt.scatter(x_clean, y_clean, label=algo, s=15)

        # 图表装饰
        plt.xlabel('Link Security Ratio')
        plt.ylabel('Blocking Rate (%)')
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()

        # 显示图表
        plt.show()

    def plot_block_rate_1(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
        import seaborn as sns
        from scipy import stats

        # 创建DataFrame
        data = pd.read_csv("./data.csv")

        # 计算置信区间
        def confidence_interval(data, confidence=0.95):
            n = len(data)
            mean = np.mean(data)
            sem = stats.sem(data)
            h = sem * stats.t.ppf((1 + confidence) / 2, n - 1)
            return mean, h

        # 按algorithm和load分组计算均值和置信区间
        grouped = data.groupby(['algorithm', 'load'])['block_rate(t)'].apply(
            lambda x: confidence_interval(x)
        ).reset_index()

        # 拆分均值和置信区间
        grouped[['mean', 'ci']] = pd.DataFrame(grouped['block_rate(t)'].tolist(), index=grouped.index)
        grouped.drop('block_rate(t)', axis=1, inplace=True)

        # 绘制曲线
        style(width, height)
        sns.lineplot(data=grouped, x='load', y='mean', hue='algorithm', marker='o', linewidth=1.5)

        # 添加置信区间
        for algo in grouped['algorithm'].unique():
            subset = grouped[grouped['algorithm'] == algo]
            plt.fill_between(subset['load'],
                             subset['mean'] - subset['ci'],
                             subset['mean'] + subset['ci'],
                             alpha=0.3)

        plt.xlabel('Load')
        plt.ylabel('Block Rate(t)')
        # plt.title('Block Rate(t) vs Load with 95% Confidence Intervals', fontsize=14)
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()
        plt.show()