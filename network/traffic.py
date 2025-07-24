class OTNCalls:
    """
    面向OTN的业务类
    """
    def __init__(
            self,
            id: int,
            sourceNode: int,
            destinationNode: int,
            duration: float,
            requestBandwidth: int,
            requestSecurity: int
    ):
        if id < 0 & sourceNode < 0 & destinationNode < 0 & requestBandwidth < 0 & requestSecurity < 0:
            raise Exception("Invalid parameters set to the call.")
        if duration < 0.0:
            raise Exception("Invalid parameters set to the call.")
        self.id = id
        self.sourceNode = sourceNode
        self.destinationNode = destinationNode
        self.duration = duration
        self.requestBandwidth = requestBandwidth
        self.requestSecurity = requestSecurity