package simulators.SurvivableRouting;

import algorithm.*;
import event.Event;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.w3c.dom.Element;

public class ControlPlane {
    private String raName;
    private Algorithm algorithm;
    private PhysicalTopology pt;
    double currentTime;
    private static final Logger logger = LogManager.getLogger(ControlPlane.class);
    public ControlPlane(Element xml, PhysicalTopology pt){
        this.raName = xml.getAttribute("module");
        this.pt = pt;
        switch (this.raName){
            case "Suurballe":
                this.algorithm = new SuurballeSurvivableRoutingAlgorithm();
                break;
            default:
                logger.error("No \"%s\" algorithm.".formatted(this.raName));
        }
    }

    public void newEvent(Event event) {
        this.currentTime = event.getTime();
        switch (event.getName()) {
            case "FlowArrive":
//                long time = System.currentTimeMillis();
                this.algorithm.routeFlow(this.pt, event.getFlow());
                break;
            case "FlowDeparture":
                this.algorithm.removeFlow();
                break;
            case "SimStart":
                logger.trace("Simulation started.");
                break;
            case "SimEnd":
                logger.trace("Simulation ended.");
        }
    }
}
