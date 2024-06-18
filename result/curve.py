import matplotlib.pyplot as plt


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
        self.colors = ["#E1C855", "#E07B54", "#51B1B7"]
        self.markers = ['o', 's', 'X', '*']
        self.line_styles = ['-', '--', ':', '-.']

    @staticmethod
    def plotRealTime(timeStamp: list, serviceNumList: list):
        if not serviceNumList:
            raise Exception("Empty list.")
        if len(timeStamp) != len(serviceNumList):
            raise Exception("Two list does not match!")
        plt.plot(timeStamp, serviceNumList)
        plt.show()

    def plotMultiRealTime(self, timeStamp: list, *args,
                          width: float = 8.6, height: float = 6,
                          legend: list = None, label: list = None):
        colors = ["#E1C855", "#E07B54", "#51B1B7"]
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
                     color=colors[i])
        if label:
            plt.xlabel(label[0])
            plt.ylabel(label[1])
        plt.xticks([100*(i+1) for i in range(9)])
        # plt.yticks([20*i for i in range(6)])
        plt.grid(True, ls=':', lw=0.5, c='#d5d6d8')
        plt.tight_layout()
        if legend:
            plt.legend(legend)
        plt.show()