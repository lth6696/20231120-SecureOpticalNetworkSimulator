package event;

import network.Flow;

public class Event {
    private double time;
    private Flow flow;
    private String name;

    public Event(String name, Flow flow, double time){
        setName(name);
        setFlow(flow);
        setTime(time);
    }

    /**
     * Sets a new time for the Event to happen.
     *
     * @param time new scheduled period
     */
    public void setTime(double time){
        this.time = time;
    }

    /**
     * Retrieves current scheduled time for a given Event.
     *
     * @return value of the Event's time attribute
     */
    public double getTime() {
        return this.time;
    }

    public void setFlow(Flow flow) { this.flow = flow; }

    public Flow getFlow() { return this.flow; }

    public void setName(String name) { this.name = name; }

    public String getName() { return this.name; }
}
