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
            scheduler: network.scheduler.Scheduler,
            topo_gen: network.generator.TopoGen,
            tfk_gen: network.generator.CallsGen,
            net_state: network.state.NetState,
            statistic: result.statistic.Statistic,
            algo_name: str,
            **kargs):
        self._set_algorithm(algo_name)
        # attacked_regions = []
        while scheduler.getEventNum() != 0:
            (time, event) = scheduler.popEvent()
            logging.debug("The {} processed on {:.3f} second origin from {} to {} with id {}."
                         .format(event.type, time, event.event.src, event.event.dst, event.id))
            # attacked_regions.append(event.event.target)
            # net_state.update(topo_gen.G, tfk_gen.calls, attacked_regions)
            if event.type == "eventArrive":
                self.algorithm.route(event, topo_gen, tfk_gen, net_state, **kargs)
            elif event.type == "eventDeparture":
                self.algorithm.remove(event, topo_gen, tfk_gen)
            # statistic.snapshot(event, topo_gen.G, tfk_gen.calls)

    def _set_algorithm(self, name: str):
        # 实例化算法
        if name.lower() == "benchmark":
            self.algorithm = algorithm.benchmark.Benchmark()
        elif name.lower() == "praca":
            self.algorithm = algorithm.dynamic_praca.PRACA()
        elif name.lower() == "sasp":
            self.algorithm = algorithm.pson_sasp.SASP()
        # elif name.lower() == "spf":
        #     self.algorithm = algorithm.pson_spf.SPF()
        else:
            raise ValueError
        logging.info(f"Load the {self.algorithm.name} algorithm.")