package simulators.SurvivableRouting;

import event.Event;
import event.EventScheduler;

public class SimulationRunner {
    public SimulationRunner(ControlPlane cp, EventScheduler events) {
        Event event;
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
            cp.newEvent(event);
        }
    }
}
