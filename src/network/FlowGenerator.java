package network;

import org.w3c.dom.*;
import event.Event;
import event.EventScheduler;
import util.Distribution;

import java.util.Arrays;


public class FlowGenerator {
    private int calls;
    private double load;
    private int maxRate;
    private double meanRate;
    private double meanHoldingTime;
    private TrafficInfo[] callsTypesInfo;
    private int TotalCallsWeight;
    private int[] callWeightsVector;
    private int numberCallsTypes;

    /**
     * Returns details about the network traffic: holding time, rate, class of
     * service and weight.
     */
    private static class TrafficInfo {
        private int flow_type;
        private int weight;
        private double holding_time;
        private int rate;

        /**
         * Creates a new TrafficInfo object.
         *
         * @param holding_time seconds by which a call will be delayed
         * @param rate transfer rate, measured in Mbps
         * @param weight cost of the network link
         */
        public TrafficInfo(int type, int weight, double holding_time, int rate) {
            this.flow_type = type;
            this.weight = weight;
            this.holding_time = holding_time;
            this.rate = rate;
        }
    }


    public FlowGenerator(Element xml) {
        // 读取xml流量信息
        this.calls = Integer.parseInt(xml.getAttribute("calls"));
        this.load = Double.parseDouble(xml.getAttribute("load"));
        this.maxRate = Integer.parseInt(xml.getAttribute("max-rate"));

        NodeList callslist = xml.getElementsByTagName("calls");
        this.numberCallsTypes = callslist.getLength();
        this.callsTypesInfo = new TrafficInfo[this.numberCallsTypes];

        this.TotalCallsWeight = 0;
        for (int i = 0; i < this.numberCallsTypes; i++) {
            this.TotalCallsWeight += Integer.parseInt(((Element) callslist.item(i)).getAttribute("weight"));
        }

        // 读取业务类型
        int holdingTime, rate, weight;
        this.meanRate = 0;
        this.meanHoldingTime = 0;
        for (int i = 0; i < this.numberCallsTypes; i++) {
            holdingTime = Integer.parseInt(((Element) callslist.item(i)).getAttribute("holding-time"));
            rate = Integer.parseInt(((Element) callslist.item(i)).getAttribute("rate"));
            weight = Integer.parseInt(((Element) callslist.item(i)).getAttribute("weight"));
            this.meanRate += (double) rate * ((double) weight / (double) this.TotalCallsWeight);
            this.meanHoldingTime += holdingTime * ((double) weight / (double) this.TotalCallsWeight);
            this.callsTypesInfo[i] = new TrafficInfo(i, weight, this.meanHoldingTime, rate);
        }

        this.callWeightsVector = new int[this.TotalCallsWeight];
        int aux = 0;
        for (int i = 0; i < this.numberCallsTypes; i++) {
            for (int j = 0; j < this.callsTypesInfo[i].weight; j++) {
                this.callWeightsVector[aux++] = i;
            }
        }
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
        meanArrivalTime = (this.meanHoldingTime * (this.meanRate / (double) this.maxRate)) / this.load;
        dist1 = new Distribution(1, seed);
        dist2 = new Distribution(2, seed);
        dist3 = new Distribution(3, seed);
        dist4 = new Distribution(4, seed);

        // Generate events
        for (int i=0; i<this.calls; i++){
            TrafficInfo flow_type = this.callsTypesInfo[this.callWeightsVector[dist1.nextInt(this.TotalCallsWeight)]];
            src = dist2.nextInt(num_nodes);
            dst = dist2.nextInt(num_nodes);
            while (src == dst){dst = dist2.nextInt(num_nodes);}
            bandwidth = flow_type.rate;
            start_time = dist3.nextExponential(meanArrivalTime) + time;
            duration = dist4.nextExponential(flow_type.holding_time);
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
