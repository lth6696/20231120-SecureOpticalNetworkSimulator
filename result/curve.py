import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def style(width, height, fontsize=8):
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
                          width: float = 5.3*1.3, height: float = 3.3*1.3,
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
        plt.yticks([5*(i+1) for i in range(6)])
        # plt.yticks([2 + 0.5 * i for i in range(5)])
        plt.grid(True, ls=':', lw=0.5, c='#d5d6d8')
        plt.tight_layout()
        if legend:
            plt.legend(legend, ncol=2)
        plt.show()

    def plot_block_rate(self):
        data_file = "./data.csv"
        data = pd.read_csv(data_file)

        sns.lineplot(data=data, x="load", y="block_rate(1)", hue="algorithm")
        # plt.yticks([(x + 1) * 0.1 for x in range(4)])
        # plt.xticks([(x + 1) * 20 for x in range(3)])
        plt.show()
