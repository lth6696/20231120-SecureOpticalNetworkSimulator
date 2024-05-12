package algorithm;

import network.Flow;
import network.Topology;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class EASTSurvivableRoutingAlgorithm extends Algorithm {
    private static final Logger logger = LogManager.getLogger(EASTSurvivableRoutingAlgorithm.class);
    public EASTSurvivableRoutingAlgorithm(){
        super();
        this.AlgorithmName = "ESRLG Aware Survivable Routing Algorithm";
        logger.trace("The \"%s\" has been loaded.".formatted(this.AlgorithmName));
    }

    public boolean routeFlow(Topology physicalTopology, Topology opticalTopology, Flow flow){
        int a = 1;
        return false;
    }
}
