package simulators.SurvivableRouting;


import network.Node;
import org.apache.commons.lang3.ArrayUtils;

public class ROADM extends Node {
    protected String type;
    protected boolean eavesdropping_risk = false;   // 0 为不存在风险，1 为存在风险
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
