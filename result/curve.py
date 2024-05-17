import matplotlib.pyplot as plt


class PlotCurve:
    def __init__(self):
        pass

    @ staticmethod
    def plotRealTimeCarriedServiceNum(timeline: list, serviceNumList: list):
        if not serviceNumList:
            raise Exception("Empty list.")
        plt.plot(timeline, serviceNumList)
        plt.show()