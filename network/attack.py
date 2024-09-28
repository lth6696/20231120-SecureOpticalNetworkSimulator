class Attack:
    def __init__(
            self,
            id: int,
            atk_link: int,
            atk_node: int,
            duration: float
    ):
        if duration < 0.0:
            raise Exception("Invalid parameters set to the call.")
        self.id = id
        self.atk_link = atk_link
        self.atk_node = atk_node
        self.duration = duration
