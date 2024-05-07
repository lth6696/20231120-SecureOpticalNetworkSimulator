import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import simulators.SurvivableRouting.Simulator;

public class Main {

    private static final String PhysicalTopoFilePath = "./topo/5NodePartialMeshNet.xml";
//    private static final String LightpathTopoFilePath = "./topo/5NodePartialMeshNet.xml";
    private static final String SimName = "ERSLG-Aware Survivable Routing";
    private static final Logger logger = LogManager.getLogger(Main.class);

    public static void main(String[] args) throws Exception {
        try {
            Simulator sim = new Simulator(PhysicalTopoFilePath, SimName);
            sim.activate();
        } catch (Throwable t) {
            logger.error("Something goes wrong.");
        }
    }
}
