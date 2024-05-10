package network;

import org.jgrapht.Graph;
import org.w3c.dom.*;

public abstract class Topology {

    public int numNodes;
    public int numLinks;
    public String topologyName;
    public Node[] nodes;
    public Link[] links;
    public Graph<Node, Link> G;

    protected double mensageProcessingTime = 1.0E-5; //(in s)
    protected double configurationTimeOXC = 1.0E-5; //(in s)
    protected double propagationDelayTime = 4.0E-4; //(in s)
    protected double switchTime = 5.0E-4; //(in s)
    protected double oxcTransitionTime = 4.5E-4; //(in s)
    protected double oxcSleepModeExpenditure = 10.0; //(in percent)
    protected double oxcOperationExpenditure = 150.0; //(in W)
    protected double oxcNodeDegreeExpenditure = 85.0; //(in W)
    protected double oxcAddDropDegreeExpenditure = 100.0; //(in W)
    protected double trOverloadExpenditure = 1.683; //(in W)
    protected double trIdleExpenditure = 91.333; //(in W)
    protected double olaExpenditure = 100.0; //(in W)
    protected int spanSize = 80; //(in km)

    /**
     * Creates a new ReadTopology object. Takes the XML file containing all
     * the information about the simulation environment and uses it to populate
     * the PhysicalTopology object. The physical topology is basically composed
     * of nodes connected by links, each supporting different wavelengths.
     *
     * @param xml file that contains the simulation environment information
     */
    public Topology(Element xml) throws Exception {
        if(xml.hasAttribute("name")){
            this.topologyName = xml.getAttribute("name");
        } else {
            throw new Exception("Miss topology name.");
        }
        if(xml.hasAttribute("mensageProcessingTime")){
            this.mensageProcessingTime = Double.parseDouble(xml.getAttribute("mensageProcessingTime"));
        }
        if(xml.hasAttribute("configurationTimeOXC")){
            this.configurationTimeOXC = Double.parseDouble(xml.getAttribute("configurationTimeOXC"));
        }
        if(xml.hasAttribute("propagationDelayTime")){
            this.propagationDelayTime = Double.parseDouble(xml.getAttribute("propagationDelayTime"));
        }
        if(xml.hasAttribute("switchTime")){
            this.switchTime = Double.parseDouble(xml.getAttribute("switchTime"));
        }
        if(xml.hasAttribute("oxcTransitionTime")){
            this.oxcTransitionTime = Double.parseDouble(xml.getAttribute("oxcTransitionTime"));
        }
        if(xml.hasAttribute("oxcSleepModeExpenditure")){
            this.oxcSleepModeExpenditure = Double.parseDouble(xml.getAttribute("oxcSleepModeExpenditure"));
        }
        if(xml.hasAttribute("oxcOperationExpenditure")){
            this.oxcOperationExpenditure = Double.parseDouble(xml.getAttribute("oxcOperationExpenditure"));
        }
        if(xml.hasAttribute("oxcNodeDegreeExpenditure")){
            this.oxcNodeDegreeExpenditure = Double.parseDouble(xml.getAttribute("oxcNodeDegreeExpenditure"));
        }
        if(xml.hasAttribute("oxcAddDropDegreeExpenditure")){
            this.oxcAddDropDegreeExpenditure = Double.parseDouble(xml.getAttribute("oxcAddDropDegreeExpenditure"));
        }
        if(xml.hasAttribute("trOverloadExpenditure")){
            this.trOverloadExpenditure = Double.parseDouble(xml.getAttribute("trOverloadExpenditure"));
        }
        if(xml.hasAttribute("trIdleExpenditure")){
            this.trIdleExpenditure = Double.parseDouble(xml.getAttribute("trIdleExpenditure"));
        }
        if(xml.hasAttribute("olaExpenditure")){
            this.olaExpenditure = Double.parseDouble(xml.getAttribute("olaExpenditure"));
        }
        if(xml.hasAttribute("spanSize")){
            this.spanSize = Integer.parseInt(xml.getAttribute("spanSize"));
        }
    }

    public int getNodesNum() {
        return this.numNodes;
    };

    public int getLinksNum() {
        return this.numLinks;
    }

    public Node[] getNodes() { return this.nodes; }

    public Link[] getLinks() { return this.links; }

    public String getTopologyName() {
        return this.topologyName;
    }

    public Graph<Node, Link> getGraph() {
        return this.G;
    }
}
