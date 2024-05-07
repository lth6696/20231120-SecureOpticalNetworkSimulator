package simulators.TopologyMapping;

import network.Topology;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.Graph;
import org.jgrapht.graph.DirectedMultigraph;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import java.util.Random;

public class LightpathTopology extends Topology {
    private Lightpath[] Lightpaths;
    private ROADM[] SROADMs;
    private final Graph<ROADM, Lightpath> G = new DirectedMultigraph<>(Lightpath.class);
    private static final Logger logger = LogManager.getLogger(LightpathTopology.class);

    public LightpathTopology(Element xml) throws Exception {
        super(xml);
        logger.trace("4.1.Lightpath topology uses %s topology.".formatted(this.topologyName));

        NodeList nodeList = xml.getElementsByTagName("node");
        NodeList edgeList = xml.getElementsByTagName("link");
        addNodes(nodeList);
        addLightpaths(edgeList);
    }

    private void addNodes(NodeList nodeList) {
        this.nodes = nodeList.getLength();
        this.SROADMs = new ROADM[this.nodes];
        logger.trace("4.2.Adding %d nodes.".formatted(this.nodes));
        for (int i = 0; i < this.nodes; i++) {
            int id = Integer.parseInt(((Element) nodeList.item(i)).getAttribute("id"));
            String type = ((Element) nodeList.item(i)).getAttribute("type");
            this.SROADMs[i] = new ROADM(id, type);
            this.G.addVertex(this.SROADMs[i]);
            logger.trace("4.2.%s.Node %d is %s.".formatted(Integer.toString(i+1), id, type));
        }
        logger.trace("4.2.Added.");
    }

    private void addLightpaths(NodeList edgeList) {
        this.links = edgeList.getLength();
        this.Lightpaths = new Lightpath[this.links];
        Random randomint = new Random();
        logger.trace("4.3.Adding %d lightpaths.".formatted(this.links));
        for (int i = 0; i < this.links; i++) {
            int id = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("id"));
            int src = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("source"));
            int dst = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("destination"));
            int bandwidth = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("bandwidth"));
            int security = randomint.nextInt(2);
            this.Lightpaths[i] = new Lightpath(id, src, dst, bandwidth, security);
            this.G.addEdge(this.SROADMs[src], this.SROADMs[dst], this.Lightpaths[i]);
            logger.trace("4.3.%s.Lightpath %d from node %d to node %d with %d Gbps and %s.".formatted(
                    Integer.toString(i+1),
                    id,
                    src,
                    dst,
                    bandwidth,
                    (security==1)?"security":"unsecurity"
            ));
        }
        logger.trace("4.3.Added.");
    }

    public ROADM[] getNodes() {
        return this.SROADMs;
    }

    public Lightpath[] getLightpaths() {
        return this.Lightpaths;
    }

    public Graph<ROADM, Lightpath> getGraph() {
        return this.G;
    }
}
