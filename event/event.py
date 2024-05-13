class Event:
    """
    通用事件类
    """
    EVENT_TYPE = ("simStart", "callArrive", "callDeparture", "simEnd")

    def __init__(
            self,
            id: int,
            type: str,
            time: float,
            call: any = None
    ):
        if id < 0:
            raise Exception("Invalid parameters set to the event.")
        if time < 0:
            raise Exception("Invalid parameters set to the event.")
        if type not in Event.EVENT_TYPE:
            raise Exception("Invalid parameters set to the event.")
        # 初始化业务请求
        self.id = id
        self.type = type
        self.time = time
        self.call = call