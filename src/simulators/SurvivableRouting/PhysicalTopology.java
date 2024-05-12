package simulators.SurvivableRouting;

import network.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.Graph;
import org.jgrapht.graph.DirectedMultigraph;
import org.jgrapht.graph.WeightedMultigraph;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

public class PhysicalTopology extends Topology {
    private static final Logger logger = LogManager.getLogger(PhysicalTopology.class);

    public PhysicalTopology(Element xml) throws Exception {
        super(xml);
        if(xml.hasAttribute("name")){
            this.topologyName = xml.getAttribute("name");
        } else {
            throw new Exception("Miss topology name.");
        }
        logger.trace("2.1.Physical topology uses %s topology.".formatted(this.topologyName));

        this.G = new WeightedMultigraph<>(Link.class);
        NodeList nodeList = xml.getElementsByTagName("node");
        NodeList edgeList = xml.getElementsByTagName("link");
        setNodes(nodeList);
        setEdges(edgeList);
    }

    private void setNodes(NodeList nodeList) {
        this.numNodes = nodeList.getLength();
        this.nodes = new Node[this.numNodes];
        logger.trace("2.2.Adding %d nodes.".formatted(this.numNodes));
        for (int i = 0; i < this.numNodes; i++) {
            int id = Integer.parseInt(((Element) nodeList.item(i)).getAttribute("id"));
            String type = ((Element) nodeList.item(i)).getAttribute("type");
            this.nodes[i] = new Node(id);
            this.G.addVertex(this.nodes[i]);
            logger.trace("2.2.%s.Node %d is %s.".formatted(Integer.toString(i+1), id, type));
        }
        logger.trace("2.2.Added.");
    }

    private void setEdges(NodeList edgeList) throws Exception {
        this.numLinks = edgeList.getLength();
        this.links = new Link[this.numLinks];
        logger.trace("2.3.Adding %d fibers.".formatted(this.numLinks));
        for (int i = 0; i < this.numLinks; i++) {
            int id = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("id"));
            int src = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("source"));
            int dst = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("destination"));
            int bandwidth = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("bandwidth"));
            int wavelength = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("wavelengths"));
            this.links[i] = new Link(id, src, dst, wavelength, bandwidth);
            this.G.addEdge(this.nodes[src], this.nodes[dst], this.links[i]);
            logger.trace("2.3.%s.Fiber %d from node %d to node %d with %d Gbps.".formatted(
                    Integer.toString(i+1),
                    id,
                    src,
                    dst,
                    bandwidth * wavelength
            ));
        }
        logger.trace("2.3.Added.");
    }
}
