package algorithm;

import network.Flow;
import org.jgrapht.Graph;
import simulators.SurvivableRouting.Fiber;
import simulators.SurvivableRouting.ROADM;

public abstract class Algorithm {
    protected String AlgorithmName;

    public Algorithm() {}

    public void routeFlow(Graph<ROADM, Fiber> G, Flow flow) {}

    public void removeFlow() {}

    public void setName(String name) { this.AlgorithmName = name; }

    public String getName() {
        return this.AlgorithmName;
    }
}
