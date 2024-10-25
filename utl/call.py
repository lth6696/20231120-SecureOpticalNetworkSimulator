class Call:
    def __init__(self, **kwargs):
        self.id: int = -1
        self.src: any = -1
        self.dst: any = -1
        self.rate: float = 0
        self.path: list = []

        self.set(**kwargs)

    def set(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])
