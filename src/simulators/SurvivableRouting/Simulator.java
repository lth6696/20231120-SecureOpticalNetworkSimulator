package simulators.SurvivableRouting;

import event.Event;
import event.EventScheduler;
import network.FlowGenerator;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.File;

public class Simulator {
    private String PhysicalTopoFilePath;
    private String SimName;
    private static final Logger logger = LogManager.getLogger(simulators.SurvivableRouting.Simulator.class);
    private static final String FILE_NOT_EXIST = "File does not exist.";
    public Simulator(String PhysicalTopoFilePath,
                     String SimName) throws Exception {
        File PhysicalTopoFile = new File(PhysicalTopoFilePath);
        if (!PhysicalTopoFile.exists()) {
            throw new Exception(FILE_NOT_EXIST);
        }

        this.PhysicalTopoFilePath = PhysicalTopoFilePath;
        this.SimName = SimName;
    }

    public void activate() {
        logger.trace("SIMULATOR BEGIN on \"%s\".".formatted(this.SimName));
        try {
            logger.trace("1.Reading physical topology XML file \"%s\".".formatted(this.PhysicalTopoFilePath));
            DocumentBuilderFactory ptfactory = DocumentBuilderFactory.newInstance();
            DocumentBuilder ptbuilder = ptfactory.newDocumentBuilder();
            Document ptdocument = ptbuilder.parse(this.PhysicalTopoFilePath);
            logger.trace("1.Read.");

            logger.trace("2.Constructing the physical topology.");
            PhysicalTopology pt = new PhysicalTopology((Element) ptdocument.getElementsByTagName("topology").item(0));
            logger.trace("2.Constructed.");

            logger.trace("3.Initializing the eavesdropping risk link group.");
            new EavesdroppingRisk(pt);
            logger.trace("3.Done.");

            logger.trace("4.Generating the traffic flow.");
            EventScheduler evnt_scher = new EventScheduler();
            FlowGenerator flow_gen = new FlowGenerator((Element) ptdocument.getElementsByTagName("traffic").item(0));
            flow_gen.generate(evnt_scher, pt);
            logger.trace("4.Done.");

            logger.trace("5.Simulating the secure optical network.");
            ControlPlane ctrl_plane = new ControlPlane((Element) ptdocument.getElementsByTagName("ra").item(0), pt);
            this.runSimulator(ctrl_plane, evnt_scher);

        } catch (Throwable t) {
            t.printStackTrace();
        }
    }

    private void runSimulator(ControlPlane cp, EventScheduler events){
        Event event;
        int numEvents = events.numEvents();
        int aux = 0;
        while ((event = events.popEvent()) != null) {
            int progress = (int) (Math.round((1 - (double) events.numEvents() / numEvents) * 100));
            if (progress % 10 == 0 && progress != aux) {
                aux = progress;
                logger.trace("The simulation running progress is %d%%.".formatted(progress));
            }
            cp.newEvent(event);
        }
    }
}
