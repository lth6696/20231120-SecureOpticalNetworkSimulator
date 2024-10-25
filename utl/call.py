
class Call:
    def __init__(self, **kwargs):
        self.id = ""
        self.src = -1
        self.dst = -1
        self.rate = 0
        self.path = None

    def set_path(self, path: dict):
        self.path = path