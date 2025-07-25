"""
场景：部分安全光网络
问题：如何在部分安全光网络中实现安全路由
算法：Security Aware Service Provision
"""

from network.generator import TopoGen, CallsGen
from network.state import NetState
from utl.event import Event

class SASP:
    def __init__(self):
        self.name = "Security Aware Service Provision"

    def route(
        self, 
        event: Event, 
        topo_gen: TopoGen, 
        tfk_gen: CallsGen, 
        net_state: NetState, 
        depth: int
        ):
        pass

    def remove(
        self, 
        event: Event, 
        topo_gen: TopoGen, 
        tfk_gen: CallsGen, 
        **kwargs
        ):
        pass