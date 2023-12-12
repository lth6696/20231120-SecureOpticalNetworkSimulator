/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package ons.util;

import ons.EONLightPath;
import ons.EONLink;
import ons.LightPath;
import ons.Link;
import ons.Modulation;
//import static ons.PhysicalImpairments.B0;
//import static ons.PhysicalImpairments.C;
//import static ons.PhysicalImpairments.L;
//import static ons.PhysicalImpairments.NF;
//import static ons.PhysicalImpairments.activeAse;
//import static ons.PhysicalImpairments.activeNli;
//import static ons.PhysicalImpairments.alfa;
//import static ons.PhysicalImpairments.beta2;
//import static ons.PhysicalImpairments.centerFrequency;
//import static ons.PhysicalImpairments.gama;
//import static ons.PhysicalImpairments.h;
//import static ons.PhysicalImpairments.power;
import static ons.PhysicalImpairments.ratioForDB;
//import static ons.PhysicalImpairments.slotBand;
import ons.PhysicalTopology;
import ons.VirtualTopology;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

/**
 *
 * @author lucas
 */
public class ComputeSNR implements Runnable {

    int inicio, fim;
    boolean verifyQoT;
    ArrayList<LightPath> lightpathsNeighborsPerLink;
    PhysicalTopology pt;
    VirtualTopology vt;
    Map<Long, Double> snrLpsMap;
    public static boolean status;

    public ComputeSNR(ArrayList<LightPath> lightpathsNeighborsPerLink, int inicio, int fim, boolean verifyQoT, PhysicalTopology pt, VirtualTopology vt, Map<Long, Double> snrLpsMap) {
        this.lightpathsNeighborsPerLink = lightpathsNeighborsPerLink;
        this.pt = pt;
        this.vt = vt;
        this.verifyQoT = verifyQoT;
        this.inicio = inicio;
        this.fim = fim;
        this.snrLpsMap = snrLpsMap;
    }

    @Override
    public void run() {
        this.status = true;
        HashMap<Long, Double> snrPorLightpath = new HashMap<Long, Double>();
        double snrTemp = 0;
        for (int i = inicio; i < fim; i++) {
            if (i < lightpathsNeighborsPerLink.size()) {
                LightPath lpAtual = lightpathsNeighborsPerLink.get(i);
                int primSlot = ((EONLightPath) lpAtual).getFirstSlot();
                int ultSlot = ((EONLightPath) lpAtual).getLastSlot();
                int[] interSlots = {primSlot, ultSlot};
                if (snrLpsMap.containsKey(lpAtual.getID())) {
                    snrTemp = snrLpsMap.get(lpAtual.getID());
                } else {
                    snrTemp = computeSNRlightpath(lpAtual, interSlots, verifyQoT, vt.getLightpaths(lpAtual));
                }
                if (!Modulation.QoTVerify(((EONLightPath) lpAtual).getModulation(), snrTemp)) {
                    this.status = false;
                    return;
                }
                snrLpsMap.put(lpAtual.getID(), snrTemp);
                if (!snrPorLightpath.containsKey(lpAtual.getID())) {
                    snrPorLightpath.put(lpAtual.getID(), snrTemp);
                } else if (!(snrPorLightpath.get(lpAtual.getID()) >= snrTemp)) {
                    snrLpsMap.put(lpAtual.getID(), snrPorLightpath.get(lpAtual.getID()));
                } else {
                    snrPorLightpath.put(lpAtual.getID(), snrTemp);
                }
            }
        }
    }

    /**
     * Artigo: Nonlinear Impairment Aware Resource Allocation in Elastic Optical
     * Networks (2015) Modeling of Nonlinear Signal Distortion in Fiber-Optic
     * Networks (2014)
     *
     * @param lp
     * @param lightpathsNeighborsPerLink
     * @param spectrumAssigned - int[]
     * @param verifQoT - boolean - Utilizado para verificar se o espectro
     * alocado pela requisicao eh considerado ou nao no calculo da potencia
     * total que entra nos amplificadores (true, considera, ou false, nao
     * considera)
     * @return double - SNR (linear)
     */
    private double computeSNRlightpath(LightPath lp, int spectrumAssigned[], boolean verifQoT, ArrayList<ArrayList<LightPath>> lightpathsNeighborsPerLink) {

        double Ptx = ratioOfDB(2) * 1.0E-3; //W, potencia do transmissor
        double Pase = 0.0;
        double Pnli = 0.0;

        int quantSlotsRequeridos = ((EONLightPath) lp).getSlots(); //quantidade de slots requeridos
        double fs = 50; //Hz
        double Bsi = quantSlotsRequeridos * fs; //largura da banda da requisicao

        double totalSlots = ((EONLink) pt.getLink(0)).getNumSlots();
        double lowerFrequency = 1850 - (fs * (totalSlots / 2.0)); //Hz, retira-se a metade de slots porque centerFrequency = 193.0E+12 eh a frequencia central do espectro optico
        double fi = lowerFrequency + (fs * (spectrumAssigned[0])) + (Bsi / 2); //frequencia central da requisicao

        double I = Ptx / (fs * 4); //densidade de potencia do sinal para 4 slots

        //double G0 = alfa * L; //ganho em dB do amplificador
        //Amplifier amp = new Amplifier(G0, pSat, NF, h, centerFrequency, B0, 0.0, A1, A2);
        //amp.setActiveAse(1); //ativa o ruido ASE
        //amp.setTypeGainAmplifier(1); //seta o tipo de ganho como fixo
        for (int l = 0; l < lp.getLinks().length; l++) {
            Link enlace = pt.getLink(lp.getLinks()[l]);
            double Ns = roundUp((enlace.getWeight()) / 50); //numero de spans


        }

        double SNR = I / ((2.0 * Pase) + Pnli);
        return ratioForDB(SNR);
    }

    /**
     * Referencia: - Closed-form expressions for nonlinear transmission
     * performance of densely spaced coherent optical OFDM systems (2010) - A
     * Quality-of-Transmission Aware Dynamic Routing and Spectrum Assignment
     * Scheme for Future Elastic Optical Networks (2013)
     *
     * @param gain, linear
     * @param frequency
     * @return double - ase linear
     */
    private double getAse(double frequency) {
        double noiseFigureLinear = ratioOfDB(10);
        double G0 = 0.5 * 50; //ganho em dB do amplificador
        double gainLinear = ratioOfDB(G0);

        double ase = 0.5 * 0.5 * 20 * frequency * noiseFigureLinear * (gainLinear - 1.0);
        return ase;
    }

    /**
     * Converte um valor em dB para um valor linear (ratio)
     *
     * @param dB
     * @return ratio
     */
    public static double ratioOfDB(double dB) {
        double ratio;
        ratio = Math.pow(10.0, (dB / 10.0));
        return ratio;
    }

    /**
     * Arredonda para cima um valor double para int
     *
     * @param res
     * @return int
     */
    private static int roundUp(double res) {
        int res2 = (int) res;
        if (res - res2 != 0.0) {
            res2++;
        }
        return res2;
    }

    /**
     * Funcao que retorna o seno hiperbolico inverso do argumento asinh ==
     * arcsinh
     *
     * @param x - double
     * @return double
     */
    private static double arcsinh(double x) {
        return Math.log(x + Math.sqrt(x * x + 1.0));
    }

    //-----------------------------------------------------------------------------
    private double getGnli(LightPath lp, Link link, double I, double Bsi, double fi, double gama, double beta2, double alfa, double L, double C, double Ns, double lowerFrequency, ArrayList<LightPath> lightpathsNeighborsPerLink) {
        //Artigo: Nonlinear Impairment Aware Resource Allocation in Elastic Optical Networks (2015)
        double alfaLinear = ratioOfDB(alfa);
        if (beta2 < 0.0) {
            beta2 = -1.0 * beta2;
        }

        //double he = getHe(Ns, alfa, L, Math.E, C);
        //double mi = (3.0 * gama * gama * I * I * I * he) / (2.0 * Math.PI * alfaLinear * beta2);
        double mi = (3.0 * gama * gama * I * I * I) / (2.0 * Math.PI * alfaLinear * beta2);

        double ro = (Math.PI * Math.PI * beta2) / (2.0 * alfaLinear);
        double p1 = arcsinh(ro * Bsi * Bsi);
        double p2 = 0.0;

        //List<Request> listRequests = link.getListRequests();
        int size = lightpathsNeighborsPerLink.size();
        for (int i = 0; i < size; i++) {
            LightPath lpTemp = lightpathsNeighborsPerLink.get(i);

            if (!lp.equals(lpTemp) && vt.getLightPaths().containsKey(lp.getID()) && !vt.getTunnel(lp.getID()).contains(lpTemp)) {
                double fs = 50;
                double numOfSlots = ((EONLightPath) lpTemp).getSlots();
                double Bsj = numOfSlots * fs; //largura de banda da requisicao
                double fj = lowerFrequency + (fs * (((EONLightPath) lpTemp).getFirstSlot())) + (Bsj / 2); //frequencia central da requisicao

                double deltaFij = fi - fj;
                if (deltaFij < 0.0) {
                    deltaFij = -1.0 * deltaFij;
                }

                double d1 = deltaFij + (Bsj / 2);
                double d2 = deltaFij - (Bsj / 2);

                double ln = Math.log(d1 / d2);
                p2 += ln;
            }
        }

        double gnli = mi * (p1 + p2);
        return gnli;
    }

}
