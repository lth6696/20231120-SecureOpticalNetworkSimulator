package vtm;

import network.Topology;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jgrapht.Graph;
import org.jgrapht.graph.DirectedMultigraph;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

public class PhysicalTopology extends Topology {
    private int wavelength;
    private ROADM[] ROADMs;
    private Fiber[] Fibers;
    protected Graph<ROADM, Fiber> G = new DirectedMultigraph<>(Fiber.class);
    private static final Logger logger = LogManager.getLogger(PhysicalTopology.class);

    public PhysicalTopology(Element xml) throws Exception {
        super(xml);
        if(xml.hasAttribute("name")){
            this.topologyName = xml.getAttribute("name");
        } else {
            throw new Exception("Miss topology name.");
        }
        logger.trace("2.1.Physical topology uses %s topology.".formatted(this.topologyName));

        NodeList nodeList = xml.getElementsByTagName("node");
        NodeList edgeList = xml.getElementsByTagName("link");
        setNodes(nodeList);
        setEdges(edgeList);
//        DijkstraShortestPath<Node, Edge> dijkstra = new DijkstraShortestPath<>(this.G);
//        GraphPath<Node, Edge> path = dijkstra.getPath(NodeList[2], NodeList[0]);
//        for (Edge e : path.getEdgeList())
//        {
//            logger.info("%s".formatted(e.toString()));
//        }
    }

    private void setNodes(NodeList nodeList) {
        this.nodes = nodeList.getLength();
        this.ROADMs = new ROADM[this.nodes];
        logger.trace("2.2.Adding %d nodes.".formatted(this.nodes));
        for (int i = 0; i < this.nodes; i++) {
            int id = Integer.parseInt(((Element) nodeList.item(i)).getAttribute("id"));
            String type = ((Element) nodeList.item(i)).getAttribute("type");
            this.ROADMs[i] = new ROADM(id, type);
            this.G.addVertex(this.ROADMs[i]);
            logger.trace("2.2.%s.Node %d is %s.".formatted(Integer.toString(i+1), id, type));
        }
        logger.trace("2.2.Added.");
    }

    private void setEdges(NodeList edgeList) {
        this.links = edgeList.getLength();
        this.Fibers = new Fiber[this.links];
        logger.trace("2.3.Adding %d fibers.".formatted(this.links));
        for (int i = 0; i < this.links; i++) {
            int id = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("id"));
            int src = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("source"));
            int dst = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("destination"));
            int bandwidth = Integer.parseInt(((Element) edgeList.item(i)).getAttribute("bandwidth"));
            this.Fibers[i] = new Fiber(id, src, dst, bandwidth);
            this.G.addEdge(this.ROADMs[src], this.ROADMs[dst], this.Fibers[i]);
            logger.trace("2.3.%s.Fiber %d from node %d to node %d with %d Gbps.".formatted(
                    Integer.toString(i+1),
                    id,
                    src,
                    dst,
                    bandwidth
            ));
        }
        logger.trace("2.3.Added.");
    }

    public ROADM[] getNodes() {
        return this.ROADMs;
    }

    public Fiber[] getFibers() {
        return this.Fibers;
    }

    public Graph<ROADM, Fiber> getGraph() {
        return this.G;
    }
}
