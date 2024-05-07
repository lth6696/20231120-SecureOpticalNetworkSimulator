import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import vtm.Simulator;

public class Main {

    private static final String PhysicalTopoFilePath = "./topo/5NodePartialMeshNet.xml";
    private static final String LightpathTopoFilePath = "./topo/5NodePartialMeshNet.xml";
    private static final String SimName = "EGDVTM";
    private static final Logger logger = LogManager.getLogger(Main.class);

    public static void main(String[] args) throws Exception {
        try {
            Simulator sim = new Simulator(PhysicalTopoFilePath, LightpathTopoFilePath, SimName);
            sim.activate();
        } catch (Throwable t) {
            logger.error("Something goes wrong.");
        }
    }
}
