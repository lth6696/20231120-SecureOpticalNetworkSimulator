package vtm;


import network.Node;
import org.apache.commons.lang3.ArrayUtils;

public class ROADM extends Node {
    protected String type;
    private final String[] NodeType = new String[] {"ROADM", "SROADM"};

    public ROADM(int id, String type) {
        super(id);
        setAttr("type", type);
    }

    private void setAttr(String AttrName, String AttrValue) {
        switch (AttrName) {
            case "type":
                if (ArrayUtils.contains(this.NodeType, AttrValue)) {this.type = AttrValue;}
                else {throw new IllegalArgumentException();}
                break;
            default:
                throw new IllegalArgumentException();
        }
    }
}
