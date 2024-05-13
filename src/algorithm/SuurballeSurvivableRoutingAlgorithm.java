package algorithm;

import network.Flow;
import network.Link;
import network.Node;
import network.Topology;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.GraphPath;
import org.jgrapht.alg.shortestpath.DijkstraShortestPath;
import org.jgrapht.graph.DefaultWeightedEdge;
import org.jgrapht.graph.WeightedMultigraph;

import java.util.Objects;


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
        GraphPath<Node, DefaultWeightedEdge> workingPath = null;
        GraphPath<Node, DefaultWeightedEdge> backupPath = null;
        WeightedMultigraph<Node, DefaultWeightedEdge> tempOpticalG = this.constructTempG(opticalTopology.nodes, opticalTopology.links, "optical");
        WeightedMultigraph<Node, DefaultWeightedEdge> tempPhysicalG = this.constructTempG(physicalTopology.nodes, physicalTopology.links, "physical");
        DijkstraShortestPath<Node, DefaultWeightedEdge> shortestPathForOpticalG = new DijkstraShortestPath<>(tempOpticalG);
        DijkstraShortestPath<Node, DefaultWeightedEdge> shortestPathForPhysicalG = new DijkstraShortestPath<>(tempPhysicalG);

        workingPath = shortestPathForOpticalG.getPath(opticalTopology.nodes[flow.SourceNode], opticalTopology.nodes[flow.DestinationNode]);
        if (workingPath == null){
            workingPath = shortestPathForPhysicalG.getPath(physicalTopology.nodes[flow.SourceNode], physicalTopology.nodes[flow.DestinationNode]);
        } else {
            this.pruneWorkingPath(tempOpticalG, workingPath, opticalTopology.links, "optical");
        }
        if (workingPath == null){
            // block service
            return false;
        } else {
            this.pruneWorkingPath(tempPhysicalG, workingPath, physicalTopology.links, "physical");
        }
        // todo update link risk
        backupPath = shortestPathForOpticalG.getPath(opticalTopology.nodes[flow.SourceNode], opticalTopology.nodes[flow.DestinationNode]);
        if (backupPath == null){
            backupPath = shortestPathForPhysicalG.getPath(physicalTopology.nodes[flow.SourceNode], physicalTopology.nodes[flow.DestinationNode]);
        }
        if (backupPath == null){
            return false;
        }
        // todo update network state
        // todo update link risk
        return true;
    }

    private WeightedMultigraph<Node, DefaultWeightedEdge> constructTempG(Node[] nodes, Link[] links, String type){
        WeightedMultigraph<Node, DefaultWeightedEdge> tempG = new WeightedMultigraph<>(DefaultWeightedEdge.class);
        for (Node node : nodes){
            tempG.addVertex(node);
        }
        if (Objects.equals(type, "physical")){
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
        } else if (Objects.equals(type, "optical")){
            for (Link link : links){
                tempG.addEdge(nodes[link.src], nodes[link.dst]);
                tempG.setEdgeWeight(nodes[link.src], nodes[link.dst], 1/(double)link.bandwidth[0]);
            }
        }
        return tempG;
    }

    private void pruneWorkingPath(WeightedMultigraph<Node, DefaultWeightedEdge> G, GraphPath<Node, DefaultWeightedEdge> workingPath, Link[] links, String type){
        if (Objects.equals(type, "optical")){
            for (DefaultWeightedEdge e : workingPath.getEdgeList()) {
                G.removeEdge(e);
            }
        } else if (Objects.equals(type, "physical")){
            for (DefaultWeightedEdge e : workingPath.getEdgeList()) {
                double weight = G.getEdgeWeight(e);
                if (weight == 1.0){
                    G.removeEdge(e);
                }else{
                    G.setEdgeWeight(e, weight/(1-weight));
                }
            }
        }
    }
}
