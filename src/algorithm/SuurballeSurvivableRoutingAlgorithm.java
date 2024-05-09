package algorithm;

import network.Flow;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.Graph;
import org.jgrapht.alg.shortestpath.SuurballeKDisjointShortestPaths;
import simulators.SurvivableRouting.Fiber;
import simulators.SurvivableRouting.PhysicalTopology;
import simulators.SurvivableRouting.ROADM;

public class SuurballeSurvivableRoutingAlgorithm extends Algorithm{
    private static final Logger logger = LogManager.getLogger(SuurballeSurvivableRoutingAlgorithm.class);

    public SuurballeSurvivableRoutingAlgorithm(){
        super();
        this.AlgorithmName = "Suurballe's Survivable Routing Algorithm";
        logger.trace("The \"%s\" has been loaded.".formatted(this.AlgorithmName));
    }

    public void routeFlow(PhysicalTopology pt, Flow flow){
        logger.trace("4.1.Routing working path and backup path for service request.");
        ROADM[] nodes = pt.getNodes();
        SuurballeKDisjointShortestPaths<ROADM, Fiber> a = new SuurballeKDisjointShortestPaths(pt.getGraph());
        logger.trace(a.getPaths(nodes[0], nodes[2], 2));
        allocateWavelength();
    }

    private void allocateWavelength(){}
}
