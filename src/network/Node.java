package network;

public abstract class Node {
    protected int id;

    public Node(int id) {
        this.id = id;
    }

    public int getID() {
        return this.id;
    }

    public String toString() {
        return "Node %s.".formatted(getID());
    }
}
