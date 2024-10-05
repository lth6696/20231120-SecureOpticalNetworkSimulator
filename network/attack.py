class Attack:
    def __init__(
            self,
            id: int,
            atk_area: int,
            duration: float
    ):
        if duration < 0.0:
            raise Exception("Invalid parameters set to the call.")
        self.id = id
        self.atk_area = atk_area
        self.duration = duration
