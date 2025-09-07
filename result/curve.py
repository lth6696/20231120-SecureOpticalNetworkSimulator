import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy import interpolate
from scipy.interpolate import UnivariateSpline  # 或使用 make_interp_spline


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

    def plot_blocking_rate_vs_sec_rate(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        data_file = "./data/data_lsr_br.csv"
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
                plt.plot(x_smooth*100, y_smooth, label=algo, linewidth=1, zorder=50)

                # 可选：在原数据点位置添加标记
                plt.scatter(x_clean*100, y_clean, marker='o', s=20, linewidths=1, edgecolors="#FFFFFF", zorder=100)
            else:
                # 数据点不足时直接绘制散点图
                plt.scatter(x_clean, y_clean, label=algo, s=15)

        # 使用 annotate 方法
        # 在(20,55)和(20,35)之间添加双箭头标注
        plt.annotate('',
                    xy=(30, 24.410),  # 箭头终点
                    xytext=(30, 45.760),  # 箭头起点
                    arrowprops=dict(arrowstyle='<|-|>', color='black', lw=1),  # 双箭头样式
                    zorder=110)
        plt.text(14, 38, "21.35%", zorder=110)

        plt.annotate('',
                     xy=(60, 8.570),  # 箭头终点
                     xytext=(60, 12.550),  # 箭头起点
                     arrowprops=dict(arrowstyle='<|-|>', color='black', lw=1),  # 双箭头样式
                     zorder=110)
        plt.text(61, 10, "3.98%", zorder=110)

        # 图表装饰
        plt.xlabel('Secure Link Rate (%)')
        plt.ylabel('Blocking Rate (%)')
        # plt.yticks([20*i for i in range(6)])
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()

        # 显示图表
        plt.show()

    def plot_blocking_rate_vs_load(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        # 读取数据
        data = pd.read_csv("./data.csv")

        # 按算法和负载分组，计算均值和标准差
        grouped_data = data.groupby(['algorithm', 'load'])['block_rate(2)'].agg(['mean', 'std']).reset_index()

        # 创建图表
        style(width, height)  # 假设这是自定义的样式函数

        algorithms = grouped_data['algorithm'].unique()

        for algo in algorithms:
            algo_data = grouped_data[grouped_data['algorithm'] == algo]
            loads = algo_data['load']
            means = algo_data['mean']
            stds = algo_data['std']
            print(algo_data)

            # 生成平滑曲线（插值）
            # 注意：插值需要按负载排序且无重复值
            sorted_idx = np.argsort(loads)
            x_sorted = loads.iloc[sorted_idx]
            y_sorted = means.iloc[sorted_idx]

            # 使用UnivariateSpline进行插值（可调整平滑参数s）
            spline = UnivariateSpline(x_sorted, y_sorted, s=0)  # s为平滑因子，越小越贴近原始数据
            x_smooth = np.linspace(x_sorted.min(), x_sorted.max(), 300)  # 生成300个插值点
            y_smooth = spline(x_smooth)

            # 绘制平滑曲线
            plt.plot(x_smooth, y_smooth, label=algo, linewidth=1, zorder=80)

            # 绘制误差棒（可选用errorbar或fill_between）
            plt.errorbar(x_sorted, y_sorted, yerr=stds.iloc[sorted_idx],
                         fmt='none',  # 不绘制数据点
                         capsize=1, capthick=0.5,  # 误差棒端帽大小
                         lw=1, alpha=0.5, elinewidth=0.5,  # 透明度
                         color=plt.gca().lines[-1].get_color(), zorder=50)  # 使用与曲线相同的颜色

            plt.scatter(loads, means,
                        marker='o', s=20,
                        linewidths=1, edgecolors="#FFFFFF",
                        zorder=100)

        plt.xlabel('Load')
        plt.ylabel('Blocking Rate (%)')
        plt.xticks([100*i for i in range(9)])
        # plt.yticks([20*i for i in range(5)])
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()
        plt.show()

    def plot_utilization_vs_load_in_error_bar(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        # 读取数据
        data = pd.read_csv("./data.csv")

        # 按算法和负载分组，计算均值和标准差
        grouped_data = data.groupby(['algorithm', 'load'])['link utilization'].agg(['mean', 'std']).reset_index()

        # 创建图表
        style(width, height)  # 假设这是自定义的样式函数

        algorithms = grouped_data['algorithm'].unique()

        for algo in algorithms:
            algo_data = grouped_data[grouped_data['algorithm'] == algo]
            loads = algo_data['load']
            means = algo_data['mean']
            stds = algo_data['std']

            # 生成平滑曲线（插值）
            # 注意：插值需要按负载排序且无重复值
            sorted_idx = np.argsort(loads)
            x_sorted = loads.iloc[sorted_idx]
            y_sorted = means.iloc[sorted_idx]

            # 使用UnivariateSpline进行插值（可调整平滑参数s）
            spline = UnivariateSpline(x_sorted, y_sorted, s=0.1)  # s为平滑因子，越小越贴近原始数据
            x_smooth = np.linspace(x_sorted.min(), x_sorted.max(), 300)  # 生成300个插值点
            y_smooth = spline(x_smooth)

            # 绘制平滑曲线
            plt.plot(x_smooth, y_smooth, label=algo, linewidth=1, zorder=80)

            # 绘制误差棒（可选用errorbar或fill_between）
            plt.errorbar(x_sorted, y_sorted, yerr=stds.iloc[sorted_idx],
                         fmt='none',  # 不绘制数据点
                         capsize=1, capthick=0.5,  # 误差棒端帽大小
                         lw=1, alpha=0.5, elinewidth=0.5,  # 透明度
                         color=plt.gca().lines[-1].get_color(), zorder=50)  # 使用与曲线相同的颜色

            plt.scatter(loads, means,
                        marker='o', s=20,
                        linewidths=1, edgecolors="#FFFFFF",
                        zorder=100)

        plt.xlabel('Load')
        plt.ylabel('Link Utilization (%)')
        plt.xticks([100 * i for i in range(9)])
        # plt.yticks([20*i for i in range(5)])
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()
        plt.show()

    def plot_deviation_vs_load_in_error_bar(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        # 读取数据
        data = pd.read_csv("./data.csv")

        # 按算法和负载分组，计算均值和标准差
        grouped_data = data.groupby(['algorithm', 'load'])['security deviation (2)'].agg(['mean', 'std']).reset_index()

        # 创建图表
        style(width, height)  # 假设这是自定义的样式函数

        algorithms = grouped_data['algorithm'].unique()

        for algo in algorithms:
            algo_data = grouped_data[grouped_data['algorithm'] == algo]
            loads = algo_data['load']
            means = algo_data['mean']
            stds = algo_data['std']

            # 生成平滑曲线（插值）
            # 注意：插值需要按负载排序且无重复值
            sorted_idx = np.argsort(loads)
            x_sorted = loads.iloc[sorted_idx]
            y_sorted = means.iloc[sorted_idx]

            # 使用UnivariateSpline进行插值（可调整平滑参数s）
            spline = UnivariateSpline(x_sorted, y_sorted, s=0)  # s为平滑因子，越小越贴近原始数据
            x_smooth = np.linspace(x_sorted.min(), x_sorted.max(), 300)  # 生成300个插值点
            y_smooth = spline(x_smooth)

            # 绘制平滑曲线
            plt.plot(x_smooth, y_smooth, label=algo, linewidth=1, zorder=80)

            # 绘制误差棒（可选用errorbar或fill_between）
            plt.errorbar(x_sorted, y_sorted, yerr=stds.iloc[sorted_idx],
                         fmt='none',  # 不绘制数据点
                         capsize=1, capthick=0.5,  # 误差棒端帽大小
                         lw=1, alpha=0.5, elinewidth=0.5,  # 透明度
                         color=plt.gca().lines[-1].get_color(), zorder=50)  # 使用与曲线相同的颜色

            plt.scatter(loads, means,
                        marker='o', s=20,
                        linewidths=1, edgecolors="#FFFFFF",
                        zorder=100)

        plt.xlabel('Load')
        plt.ylabel('Security Deviation')
        plt.xticks([100 * i for i in range(9)])
        # plt.yticks([20*i for i in range(5)])
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()
        plt.show()

    def plot_exposure_vs_load_in_error_bar(self, width: float = 8.4 * 1.3, height: float = 6.3 * 1.3):
        # 读取数据
        data = pd.read_csv("./data.csv")

        # 按算法和负载分组，计算均值和标准差
        grouped_data = data.groupby(['algorithm', 'load'])['exposure ratio(2)'].agg(['mean', 'std']).reset_index()

        # 创建图表
        style(width, height)  # 假设这是自定义的样式函数

        algorithms = grouped_data['algorithm'].unique()

        for algo in algorithms:
            algo_data = grouped_data[grouped_data['algorithm'] == algo]
            loads = algo_data['load']
            means = algo_data['mean']
            stds = algo_data['std']

            # 生成平滑曲线（插值）
            # 注意：插值需要按负载排序且无重复值
            sorted_idx = np.argsort(loads)
            x_sorted = loads.iloc[sorted_idx]
            y_sorted = means.iloc[sorted_idx]

            # 使用UnivariateSpline进行插值（可调整平滑参数s）
            spline = UnivariateSpline(x_sorted, y_sorted, s=0)  # s为平滑因子，越小越贴近原始数据
            x_smooth = np.linspace(x_sorted.min(), x_sorted.max(), 300)  # 生成300个插值点
            y_smooth = spline(x_smooth)

            # 绘制平滑曲线
            plt.plot(x_smooth, y_smooth, label=algo, linewidth=1, zorder=80)

            # 绘制误差棒（可选用errorbar或fill_between）
            plt.errorbar(x_sorted, y_sorted, yerr=stds.iloc[sorted_idx],
                         fmt='none',  # 不绘制数据点
                         capsize=1, capthick=0.5,  # 误差棒端帽大小
                         lw=1, alpha=0.5, elinewidth=0.5,  # 透明度
                         color=plt.gca().lines[-1].get_color(), zorder=50)  # 使用与曲线相同的颜色

            plt.scatter(loads, means,
                        marker='o', s=20,
                        linewidths=1, edgecolors="#FFFFFF",
                        zorder=100)

        plt.xlabel('Load')
        plt.ylabel('Exposure Rate (%)')
        plt.xticks([100 * i for i in range(9)])
        # plt.yticks([20*i for i in range(5)])
        plt.legend()
        plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
        plt.tight_layout()
        plt.show()