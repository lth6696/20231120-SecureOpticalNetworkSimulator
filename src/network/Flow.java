package network;

public class Flow {
    public long ID;
    public int SourceNode;
    public int DestinationNode;
    public int Bandwidth;
    public double Duration;
    public double StartTime;
    public double EndTime;

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
