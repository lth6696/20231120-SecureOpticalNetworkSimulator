package algorithm;

import network.Flow;
import network.Link;
import network.Node;
import network.Topology;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.Graph;
import org.jgrapht.GraphPath;
import org.jgrapht.alg.shortestpath.DijkstraShortestPath;
import org.jgrapht.graph.WeightedMultigraph;


public class SuurballeSurvivableRoutingAlgorithm extends Algorithm{
    private static final Logger logger = LogManager.getLogger(SuurballeSurvivableRoutingAlgorithm.class);

    public SuurballeSurvivableRoutingAlgorithm(){
        super();
        this.AlgorithmName = "Suurballe's Survivable Routing Algorithm";
        logger.trace("The \"%s\" has been loaded.".formatted(this.AlgorithmName));
    }

    public boolean routeFlow(Topology physicalTopology, Topology opticalTopology, Flow flow){
        /*
        Algorithm pseudocode:
        1. 计算工作路径。若光路拓扑没有可用路径，则基于物理拓扑新建光路。对于物理拓扑，修建掉已占用的波长后，构建临时图。计算最短路径并基于FirstFit分配波长，更新光路拓扑。
        2. 基于路径加密情况，更新窃听风险链路共享组。
        3. 计算保护路径。删除工作路径所用光路，删除和工作路径共享风险的光路，构建临时光路图，若不存在路径，则基于物理拓扑新建光路。对于物理拓扑，删除已占用波长、与工作路径共享风险波长，构建临时图并计算路径。
        4. 更新窃听风险共享链路组。
        5. 若存在工作路径与保护路径，则输出并退出；若不存在，则锁定业务。
         */
        GraphPath<Node, Link> workingPath = null;
        GraphPath<Node, Link> backupPath = null;
        workingPath = new DijkstraShortestPath<>(opticalTopology.G).getPath(opticalTopology.nodes[flow.SourceNode], opticalTopology.nodes[flow.DestinationNode]);
        if (workingPath == null){
            WeightedMultigraph<Node, Link> tempG = this.constructTempG(physicalTopology.nodes, physicalTopology.links);
            workingPath = new DijkstraShortestPath<>(tempG).getPath(physicalTopology.nodes[flow.SourceNode], physicalTopology.nodes[flow.DestinationNode]);
        }
        if (workingPath == null){
            // block service
            return false;
        }
        // todo update link risk
        Graph<Node, Link> tempG = new WeightedMultigraph<>(Link.class);
        backupPath = new DijkstraShortestPath<>(tempG).getPath(opticalTopology.nodes[flow.SourceNode], opticalTopology.nodes[flow.DestinationNode]);
        if (backupPath == null){
            tempG = new WeightedMultigraph<>(Link.class);
            backupPath = new DijkstraShortestPath<>(tempG).getPath(physicalTopology.nodes[flow.SourceNode], physicalTopology.nodes[flow.DestinationNode]);
        }
        if (backupPath == null){
            return false;
        }
        // todo update network state
        // todo update link risk
        return true;
    }

    private WeightedMultigraph<Node, Link> constructTempG(Node[] nodes, Link[] links){
        WeightedMultigraph<Node, Link> tempG = new WeightedMultigraph<>(Link.class);
        for (Node node : nodes){
            tempG.addVertex(node);
        }
        for (Link link : links){
            double weight = 1;
            for (int i = 0; i < link.wavelength; i++){
                if (!link.usedWavelength[i]){
                    weight += 1;
                }
            }
            tempG.addEdge(nodes[link.src], nodes[link.dst]);
            tempG.setEdgeWeight(nodes[link.src], nodes[link.dst], 1/weight);
        }
        return tempG;
    }
}
