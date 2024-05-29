import matplotlib.pyplot as plt


class PlotCurve:
    def __init__(self):
        pass

    @ staticmethod
    def plotRealTimeCarriedServiceNum(timeline: list, serviceNumList: list):
        if not serviceNumList:
            raise Exception("Empty list.")
        if len(timeline) != len(serviceNumList):
            raise Exception("Two list does not match!")
        plt.plot(timeline, serviceNumList)
        plt.show()