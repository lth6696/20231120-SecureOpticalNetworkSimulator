package simulators.SurvivableRouting;

import network.Link;

public class Fiber extends Link {
    protected int bandwidth;
    protected int wavelength;

    public Fiber(int id, int src, int dst, int bandwidth, int wavelength)
    {
        super(id, src, dst);
        this.bandwidth = bandwidth;
        this.wavelength = wavelength;
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
