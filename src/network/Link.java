package network;

import org.jgrapht.graph.DefaultEdge;

public abstract class Link extends DefaultEdge {
    protected int id;
    protected int src;
    protected int dst;

    public Link(int id, int src, int dst) {
        this.id = id;
        this.src = src;
        this.dst = dst;
    }

    public int getID() {
        return this.id;
    }

    public int getSrc() {
        return this.src;
    }

    public int getDst() {
        return this.dst;
    }

    @Override
    public String toString() {
        return "The link from %d node to %d node.".formatted(getSrc(), getDst());
    }
}
