from utl.event import Event
from queue import PriorityQueue


class Scheduler:
    """
    事件协调器
    """
    def __init__(self):
        self.eventQueue = PriorityQueue()

    def addEvent(self, event: Event):
        self.eventQueue.put((event.time, event))

    def popEvent(self):
        return self.eventQueue.get()

    def getEventNum(self):
        return self.eventQueue.qsize()