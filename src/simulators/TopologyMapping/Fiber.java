package simulators.TopologyMapping;

import network.Link;

public class Fiber extends Link {
    protected int bandwidth;

    public Fiber(int id, int src, int dst, int bandwidth)
    {
        super(id, src, dst);
        this.bandwidth = bandwidth;
    }

    public int getBandwidth() {
        return this.bandwidth;
    }

    @Override
    public String toString()
    {
        return "The link from %d node to %d node with %d Gbps.".formatted(getSrc(), getDst(), getBandwidth());
    }
}
