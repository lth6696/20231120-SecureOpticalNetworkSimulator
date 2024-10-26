import algorithm
import network
import result

import logging


class ControlPlane:
    """
    仿真管控平台，用于管理业务事件到达后路由、业务事件离去后资源释放功能
    """
    def __init__(self):
        self.algorithm = None

    def run(self,
            algorithm: str,
            scheduler: network.scheduler.Scheduler,
            topo_gen: network.generator.TopoGen,
            tfk_gen: network.generator.CallsGen,
            net_state: network.state.NetState,
            statistic: result.statistic.Statistic):
        self._set_algorithm(algorithm)
        attacked_regions = []
        while scheduler.getEventNum() != 0:
            (time, event) = scheduler.popEvent()
            # logging.info("{} - {} - The {} event processed on {} second origin from {} to {} with id {}."
            #              .format(__file__, __name__, event.type, time, event.call.sourceNode, event.call.destinationNode, event.id))
            attacked_regions.append(event.event.target)
            if event.type == "eventArrive":
                self.algorithm.routeCall(topo_gen.G, event, net_state)
            elif event.type == "eventDeparture":
                self.algorithm.removeCall(topo_gen.G, event, net_state)
            net_state.update(topo_gen.G, tfk_gen.calls, attacked_regions)
            statistic.snapshot(event, topo_gen.G, tfk_gen.calls)

    def _set_algorithm(self, name: str):
        # 实例化算法
        if name.lower() == "benchmark":
            self.algorithm = algorithm.benchmark.Benchmark()
        elif name.lower() == "CAR":
            self.algorithm = algorithm.car.CAR()
        else:
            raise ValueError
        logging.info(f"{__file__} - {__name__} - Load the {name} algorithm.")