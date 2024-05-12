package algorithm;

import network.Flow;
import network.Topology;

public abstract class Algorithm {
    protected String AlgorithmName;

    public Algorithm() {}

    public abstract boolean routeFlow(Topology physicalTopology, Topology opticalTopology, Flow flow);

    public void removeFlow() {}

    public void setName(String name) { this.AlgorithmName = name; }

    public String getName() {
        return this.AlgorithmName;
    }
}
