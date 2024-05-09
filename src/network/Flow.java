package network;

public class Flow {
    private long ID;
    private int SourceNode;
    private int DestinationNode;
    private int Bandwidth;
    private double Duration;
    private double StartTime;
    private double EndTime;

    public Flow(long id, int src, int dst, int bandwidth, double duration, double start_time, double end_time){
        if (id < 0 || bandwidth < 1 || duration < 0 || start_time < 0 || end_time < 0) {
            throw (new IllegalArgumentException());
        } else {
            this.ID = id;
            this.SourceNode = src;
            this.DestinationNode = dst;
            this.Bandwidth = bandwidth;
            this.Duration = duration;
            this.StartTime = start_time;
            this.EndTime = end_time;
        }
    }
}
