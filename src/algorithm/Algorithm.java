package algorithm;

public abstract class Algorithm {
    protected String AlgorithmName;

    public Algorithm() {}

    public void routeFlow() {}

    public void removeFlow() {}

    public void setName(String name) { this.AlgorithmName = name; }

    public String getName() {
        return this.AlgorithmName;
    }
}
