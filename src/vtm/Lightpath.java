package vtm;

import network.Link;

public class Lightpath extends Link {
    private final int bandwidth;
    private final int security;

    public Lightpath(int id, int src, int dst, int bandwidth, int security) {
        super(id, src, dst);
        this.bandwidth = bandwidth;
        this.security = security;
    }

    public int getBandwidth() {
        return this.bandwidth;
    }

    public int getSecurity() {
        return this.security;
    }

    @Override
    public String toString() {
        return "The lightpath from %d node to %d node with %d Gbps and %d secrecy.".
                formatted(getSrc(), getDst(), getBandwidth(), getSecurity());
    }
}
