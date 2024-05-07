package algorithm;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.Graph;
import org.jgrapht.GraphPath;
import org.jgrapht.alg.shortestpath.YenKShortestPath;
import vtm.*;

public class LETSVtopoMapping extends Algorithm{
    private static final Logger logger = LogManager.getLogger(LETSVtopoMapping.class);
    private static final int K = 4;
    public LETSVtopoMapping() {
        super();
        this.AlgorithmName = "LETS";
    }

    public void run(Lightpath[] lightpaths, Graph<ROADM,Fiber> G) {
        logger.trace("5.1.Running %s algorithm to solve the problem.".formatted(getName()));
        logger.trace("5.1.1.Iterate each lightpath.");
        for (Lightpath lightpath : lightpaths) {
            YenKShortestPath<ROADM,Fiber> KSP = new YenKShortestPath<>(G);
            GraphPath<ROADM,Fiber> paths = KSP.getPaths()
        }
    }
}
