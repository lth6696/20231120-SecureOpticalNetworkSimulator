class Event:
    """
    通用事件类
    """
    EVENT_TYPE = ("simStart", "eventArrive", "eventDeparture", "simEnd")

    def __init__(
            self,
            id: int,
            type: str,
            time: float,
            event: any = None
    ):
        if id < 0:
            raise Exception("Invalid parameters set to the event.")
        if time < 0:
            raise Exception("Invalid parameters set to the event.")
        if type not in Event.EVENT_TYPE:
            raise Exception("Invalid parameters set to the event.")
        # 初始化事件
        self.id = id
        self.type = type
        self.time = time
        self.event = event

    def __str__(self):
        return f"Event {self.id}: type={self.type} | time={self.time}."