import logging

logger = logging.getLogger(__name__)


class Call:
    def __init__(self, **kwargs):
        self.id: int = -1
        self.src: any = -1
        self.dst: any = -1
        self.rate: float = 0
        self.security: int = -1
        
        self.path: list = []
        self.is_routed: bool = False

        self.set(**kwargs)

    def __str__(self):
        # return f"Call {self.id} from \'{self.src}\' to \'{self.dst}\' require {self.rate}Gbps and \'{self.security}\' security \'{self.is_routed}\' routing to the path: {self.path}."
        return f"Call {self.id} ({self.src} --> {self.dst}): rate={self.rate} Gbps | security={self.security} | routing={self.is_routed} | path={self.path}."

    def set(self, **kwargs):
        # Set instance attributes with validation.
        allowed_attrs = self.__dict__.keys()
        for key in kwargs:
            if key not in allowed_attrs:
                logging.error(f"Invalid attribute '{key}'. Allowed attributes are: {allowed_attrs}")
                continue
            setattr(self, key, kwargs[key])
