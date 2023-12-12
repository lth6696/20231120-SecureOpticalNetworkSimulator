/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package ons.ra;

import ons.EONLightPath;
import ons.EONLink;
import ons.EONPhysicalTopology;
import ons.Flow;
import ons.LightPath;
import ons.Modulation;
import ons.util.WeightedGraph;
import ons.util.YenKSP;
import java.util.ArrayList;
import java.util.TreeSet;

/**
 * The RSAMF algorithm. This solves the RMLSA problem
 * Article: "Algoritmo de Roteamento e Atribuicao de Espectro com Minimizacao de Fragmentacao em Redes Oticas Elasticas",
 * Andre K. Horota, Gustavo B. Figueiredo, Nelson L. S. da Fonseca,
 * Anais do 32 Simposio Brasileiro de Redes de Computadores e Sistemas Distribuídos - SBRC 2014, 
 * Aug 2014.
 * @author lucas
 */
public class RSAMF implements RA {
    
    private ControlPlaneForRA cp;
    private WeightedGraph graph;
    private int modulation;

    @Override
    public void simulationInterface(ControlPlaneForRA cp) {
        this.cp = cp;
        this.graph = cp.getPT().getWeightedGraph();
        //The default modulation
        this.modulation = Modulation._BPSK;
    }
    
    @Override
    public void setModulation(int modulation) {
        this.modulation = modulation;
    }

    @Override
    public void simulationEnd() {   
    }
    
    @Override
    public void flowArrival(Flow flow) {
        //((EONLink) cp.getPT().getLink(6)).printLink();
        int[] nodes;
        int[] links;
        long id;
        LightPath[] lps = new LightPath[1];
        
        int ksp = 6;

        // Try existent lightpaths first (Grooming)
        /*
        lps[0] = getLeastLoadedLightpath(flow);
        if (lps[0] instanceof LightPath) {
            if (cp.acceptFlow(flow.getID(), lps)) {
                return;
            }
        }
        */
        
        // k-Shortest Paths routing
        
        ArrayList<Integer>[] kpaths = YenKSP.kShortestPaths(graph, flow.getSource(), flow.getDestination(), ksp);
        
        double fragRoute[] = new double[ksp];
        for (int k = 0; k < kpaths.length; k++) {
            fragRoute[k] = 0;
            nodes = route(kpaths,k);
            if (nodes.length == 0 || nodes == null) {
                fragRoute[k] = Double.MAX_VALUE;
            } else {
                links = new int[nodes.length - 1];
                for (int j = 0; j < nodes.length - 1; j++) {
                    links[j] = cp.getPT().getLink(nodes[j], nodes[j + 1]).getID();
                }
                double pathLength = pathLength(links);
                this.modulation = Modulation.getBestModulation(pathLength);
                int requiredSlots = Modulation.convertRateToSlot(flow.getRate(), EONPhysicalTopology.getSlotSize(), modulation);
                fragRoute[k] = getRelativeFragmentation(links, requiredSlots);
            }
        }
        sortRoutes(kpaths, fragRoute);//ordenando as rotas pelos enlaces menos fragmentados
        for (int k = 0; k < kpaths.length; k++) {

            nodes = route(kpaths,k);
            // If no possible path found, block the call
            if (nodes.length == 0 || nodes == null) {
                cp.blockFlow(flow.getID());
                return;
            }

            // Create the links vector
            links = new int[nodes.length - 1];
            for (int j = 0; j < nodes.length - 1; j++) {
                links[j] = cp.getPT().getLink(nodes[j], nodes[j + 1]).getID();
            }

            double pathLength = pathLength(links);
            this.modulation = Modulation.getBestModulation(pathLength);
            int requiredSlots = Modulation.convertRateToSlot(flow.getRate(), EONPhysicalTopology.getSlotSize(), modulation);

            int[] firstSlot;
            for (int i = 0; i < links.length; i++) {
                // Try the slots available in each link
                firstSlot = ((EONLink) cp.getPT().getLink(links[i])).getSlotsAvailableToArray(requiredSlots);
                for (int j = 0; j < firstSlot.length; j++) {
                // Now you create the lightpath to use the createLightpath VT
                    //Relative index modulation: BPSK = 0; QPSK = 1; 8QAM = 2; 16QAM = 3;
                    EONLightPath lp = cp.createCandidateEONLightPath(flow.getSource(), flow.getDestination(), links,
                            firstSlot[j], (firstSlot[j] + requiredSlots - 1), modulation);
                    // Now you try to establish the new lightpath, accept the call
                    if ((id = cp.getVT().createLightpath(lp)) >= 0) {
                        // Single-hop routing (end-to-end lightpath)
                        lps[0] = cp.getVT().getLightpath(id);
                        cp.acceptFlow(flow.getID(), lps);
                        return;
                    }
                }
            }
        }
        // Block the call
        cp.blockFlow(flow.getID());
    }

    @Override
    public void flowDeparture(long id) {
    }

    private int[] route(ArrayList<Integer>[] kpaths, int k) {
        if (kpaths[k] != null) {
            int[] path = new int[kpaths[k].size()];
            for (int i = 0; i < path.length; i++) {
                path[i] = kpaths[k].get(i);
            }
            return path;
        } else {
            return null;
        }
    }
    
    private LightPath getLeastLoadedLightpath(Flow flow) {
        long abw_aux, abw = 0;
        LightPath lp_aux, lp = null;

        // Get the available lightpaths
        TreeSet<LightPath> lps = cp.getVT().getAvailableLightpaths(flow.getSource(),
                flow.getDestination(), flow.getRate());
        if (lps != null && !lps.isEmpty()) {
            while (!lps.isEmpty()) {
                lp_aux = lps.pollFirst();
                // Get the available bandwidth
                abw_aux = cp.getVT().getLightpathBWAvailable(lp_aux.getID());
                if (abw_aux > abw) {
                    abw = abw_aux;
                    lp = lp_aux;
                }
            }
        }
        return lp;
    }

    private void sortRoutes(ArrayList<Integer>[] kpaths, double[] fragRoute) {
        ArrayList<Integer> auxPath = new ArrayList<>();
        double auxIndex;
        for (int i = 0; i < fragRoute.length; i++) {
            for (int j = 0; j < fragRoute.length; j++) {
                if(fragRoute[i] > fragRoute[j]){
                    auxPath = kpaths[i];
                    kpaths[i] = kpaths[j];
                    kpaths[j] = auxPath;
                    auxIndex = fragRoute[i];
                    fragRoute[i] = fragRoute[j];
                    fragRoute[j] = auxIndex;
                }
            }
        }
    }

    private double pathLength(int[] links) {
        double pathLength = 0;
        for (int i = 0; i < links.length - 1; i++) {
            pathLength += cp.getPT().getLink(links[i]).getWeight();
        }
        return pathLength;
    }

    private double getRelativeFragmentation(int[] links, int requiredSlots) {
        double frag = 0;
        for (int i = 0; i < links.length; i++) {
            frag += ((double)requiredSlots*(double)((EONLink) cp.getPT().getLink(links[i])).rangeFreeSimultaneous(requiredSlots))/(double)((EONLink) cp.getPT().getLink(links[i])).getAvaiableSlots();
        }
        return frag;
    }
}
