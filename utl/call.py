class Call:
    def __init__(self, **kwargs):
        self.id: int = -1
        self.src: any = -1
        self.dst: any = -1
        self.rate: float = 0
        self.path: list = []

        self.set(**kwargs)

    def __str__(self):
        return f"Call {self.id} from \'{self.src}\' to \'{self.dst}\' require {self.rate}Mbps routing to the path: {self.path}."

    def set(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])
