package event;

public class Event {
    private double time;

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
}
