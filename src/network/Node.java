package network;

import java.util.HashMap;
import java.util.Map;

public class Node {
    public int id;
    public String type;
    public Map<String, Integer> attributes;

    public Node(int id) {
        this.id = id;
    }

    public int getID() {
        return this.id;
    }

    public void setAttr(String attrName, Integer attrValue) {
        if (this.attributes == null){
            this.attributes = new HashMap<>();
        }
        this.attributes.put(attrName, attrValue);
    }

    public String toString() {
        return "Node %s.".formatted(getID());
    }
}
