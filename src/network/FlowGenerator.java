package network;

import event.Event;
import event.EventScheduler;
import util.Distribution;

public class FlowGenerator {
    private int calls;
    private double load;
    private int maxRate;
    private double meanRate;
    private double meanHoldingTime;

    public FlowGenerator(){
        // 读取xml流量信息
        this.calls = 3;
    }

    public void generate(EventScheduler evnt_scher, Topology topology){
        /* Compute the arrival time
         *
         * load = meanArrivalRate x holdingTime x bw/maxRate
         * 1/meanArrivalRate = (holdingTime x bw/maxRate)/load
         * meanArrivalTime = (holdingTime x bw/maxRate)/load
         */
        int num_nodes = topology.getNodesNum();
        int seed = 1;
        int src, dst, bandwidth;
        double duration, start_time, end_time;
        double time = 0;
        double meanArrivalTime;
        Distribution dist1, dist2, dist3, dist4;
//        meanArrivalTime = (meanHoldingTime * (meanRate / (double) maxRate)) / load;
        meanArrivalTime = 2.3;
        dist1 = new Distribution(1, seed);
        dist2 = new Distribution(2, seed);
        dist3 = new Distribution(3, seed);
        dist4 = new Distribution(4, seed);

        // Generate events
        for (int i=0; i<this.calls; i++){
            src = dist1.nextInt(num_nodes);
            dst = dist1.nextInt(num_nodes);
            while (src == dst){dst = dist1.nextInt(num_nodes);}
            bandwidth = dist2.nextInt(10000);
            start_time = dist3.nextExponential(meanArrivalTime) + time;
            duration = dist4.nextExponential(6000);
            end_time = start_time + duration;
            time += start_time;

            Flow flow = new Flow(i, src, dst, bandwidth, duration, start_time, end_time);
            Event flow_arrive = new Event("FlowArrive", flow, start_time);
            Event flow_departure = new Event("FlowDeparture", flow, end_time);
            evnt_scher.addEvent(flow_arrive);
            evnt_scher.addEvent(flow_departure);
        }
    }
}
