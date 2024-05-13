package network;

import java.util.HashMap;
import java.util.Map;


public class Link {
    public int id;
    public int src;
    public int dst;
    public int wavelength;
    public boolean[] usedWavelength;
    public int[] bandwidth;
    public Map<String, Integer> attributes;


    public Link(int id, int src, int dst, int wavelength, int bandwidth) throws Exception {
        if (id < 0 || src < 0 || dst < 0 || wavelength < 0 || wavelength > 48 || bandwidth < 0) {
            throw new Exception("Invalid setting of link.");
        }
        this.id = id;
        this.src = src;
        this.dst = dst;
        this.wavelength = wavelength;
        this.bandwidth = new int[wavelength];
        this.usedWavelength = new boolean[wavelength];
        for (int i = 0; i < this.wavelength; i++){
            this.bandwidth[i] = bandwidth;
            this.usedWavelength[i] = false;
        }
    }

    public void setAttr(String attrName, Integer attrValue){
        if (this.attributes == null) {
            this.attributes = new HashMap<>();
        }
        this.attributes.put(attrName, attrValue);
    }

    public String toString() {
        return "(" + this.src + " : " + this.dst + ")";
    }
}
