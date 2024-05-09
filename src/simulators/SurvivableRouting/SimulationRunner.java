package simulators.SurvivableRouting;

import event.Event;
import event.EventScheduler;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class SimulationRunner {
    private static final Logger logger = LogManager.getLogger(SimulationRunner.class);

    public SimulationRunner(ControlPlane cp, EventScheduler events) {
        Event event;
        int numEvents = events.numEvents();
        int aux = 0;
//        Tracer tr = Tracer.getTracerObject();
//        MyStatistics st = MyStatistics.getMyStatisticsObject();
        while ((event = events.popEvent()) != null) {
//            tr.add(event);
//            if (event instanceof OrdinaryEvent) {
//                st.addOrdinaryEvent(event);
////            } else if (cp.getPT() instanceof EONPhysicalTopology) {
////                st.addEvent(event, ((EONPhysicalTopology) cp.getPT()).getAvailableSlots(), cp.getPT().getAllFreeGroomingInputPorts(), ((EONPhysicalTopology) cp.getPT()).getExFragmentation());
//            } else {
//                st.addEvent(event, cp.getPT().getAllFreeGroomingInputPorts());
//            }
            int progress = (int) (Math.round((1 - (double) events.numEvents() / numEvents) * 100));
            if (progress % 10 == 0 && progress != aux) {
                aux = progress;
                logger.trace("The simulation running progress is %d%%.".formatted(progress));
            }
            cp.newEvent(event);
        }
    }
}
