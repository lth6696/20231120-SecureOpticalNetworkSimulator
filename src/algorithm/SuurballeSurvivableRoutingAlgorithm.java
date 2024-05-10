package algorithm;

import network.Flow;
import network.Link;
import network.Node;
import network.Topology;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.GraphPath;
import org.jgrapht.alg.shortestpath.SuurballeKDisjointShortestPaths;

import java.util.List;

public class SuurballeSurvivableRoutingAlgorithm extends Algorithm{
    private static final Logger logger = LogManager.getLogger(SuurballeSurvivableRoutingAlgorithm.class);

    public SuurballeSurvivableRoutingAlgorithm(){
        super();
        this.AlgorithmName = "Suurballe's Survivable Routing Algorithm";
        logger.trace("The \"%s\" has been loaded.".formatted(this.AlgorithmName));
    }

    public void routeFlow(Topology topology, Flow flow){
//        logger.trace("Routing working path and backup path for the %dth flow.".formatted(flow.ID));
        Node[] nodes = topology.getNodes();

        SuurballeKDisjointShortestPaths<Node, Link> suurballe = new SuurballeKDisjointShortestPaths(topology.getGraph());
        List<GraphPath<Node, Link>> paths = suurballe.getPaths(nodes[flow.SourceNode], nodes[flow.DestinationNode], 2);

        for (GraphPath<Node, Link> path : paths) {
            for (Link segment : path.getEdgeList()){
                String attrName = "0";
                int attrValue = segment.bandwidth.get(attrName);
                segment.bandwidth.put(attrName, attrValue - flow.Bandwidth);
            }
        }
    }
}
