package algorithm;

import network.Flow;
import network.Topology;

public abstract class Algorithm {
    protected String AlgorithmName;

    public Algorithm() {}

    public void routeFlow(Topology topology, Flow flow) {}

    public void removeFlow() {}

    public void setName(String name) { this.AlgorithmName = name; }

    public String getName() {
        return this.AlgorithmName;
    }
}
