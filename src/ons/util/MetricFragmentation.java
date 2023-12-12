/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package ons.util;

import ons.EONLink;
import ons.EONPhysicalTopology;
import ons.PhysicalImpairments;
import ons.PhysicalTopology;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Map;
import static ons.EONPhysicalTopology.valueA;

/**
 *
 * @author kaio
 */
public final class MetricFragmentation {

    /**
     * fragmentação Rosa et al. 2012
     */
    public static double getFragmentation(int links[], PhysicalTopology pt) {
        double frag = 0;
        for (int i = 0; i < links.length; i++) {
            frag = frag + ((EONLink) pt.getLink(links[i])).getExFragmentationRate();
        }
        return frag / (double) links.length;
    }

    /**
     * fragmentação Wu et al. 2014
     *
     */
    public static double getFragmentationWu(int links[], PhysicalTopology pt) {
        double soma1 = 0;
        EONLink l;
        int maxSize, avaiableSlots;
        for (int i = 0; i < links.length; i++) {
            l = (EONLink) pt.getLink(links[i]);
            maxSize = l.maxSizeAvaiable();
            avaiableSlots = l.getAvaiableSlots();
            if (maxSize == avaiableSlots) {
                soma1 += 1;
            } else {
                soma1 += (((double) maxSize / (double) avaiableSlots) * (1 / contaBorda(links[i], pt)));
            }
        }
        soma1 = soma1 / (double) links.length;
        return soma1;
    }

    private static double contaBorda(int link, PhysicalTopology pt) {
        double borda = 0;

        return borda / 2.0;
    }

    /**
     * fragmentação Wright et al. 2015
     *
     */
    public static double getFragmentationWright(int links[], PhysicalTopology pt) {
        double frag = 0.0;
        EONLink l;        
        ArrayList<Integer> blocos = new ArrayList<>();
        for (int i = 0; i < links.length; i++) {
            l = (EONLink) pt.getLink(links[i]);
            if (l.maxSizeAvaiable() == l.getAvaiableSlots()) {
                frag += 0.0;
            } else {
                blocos = l.getLengthFreeBlock();
                for (int bl : blocos) {
                    frag += (((double) bl / (double) l.getNumSlots()) * (Math.log((double) bl) - Math.log((double) l.getNumSlots())));
                }
            }
        }
        return -frag;
    }

    /**
     * fragmentação Sugihara et al. 2017
     *
     */
    public static double getFragmentationEntropia(int links[], PhysicalTopology pt) {

        EONLink l;
        double res = 0;
        int slots = ((EONLink) pt.getLink(0)).getNumSlots();

        return res / (double) links.length;
    }

    /**
     * fragmentação Singh & Jukan. 2017
     *
     */
    public static double getFragmentationSingh(int links[], PhysicalTopology pt) {
        BigDecimal menos_1 = new BigDecimal(1);
        EONLink l;
        BigDecimal valorT = new BigDecimal(0), valorTL = new BigDecimal(0);
        ArrayList<Integer> blocos = new ArrayList<>();
        for (int i = 0; i < links.length; i++) {
            l = (EONLink) pt.getLink(links[i]);
            blocos = l.getLengthFreeBlock();
            BigDecimal r1, r2, valor;
            r2 = new BigDecimal(6);
            valor = new BigDecimal(0);
            for (int bl : blocos) {
                r1 = new BigDecimal(EONPhysicalTopology.valueSi.get(bl));
                r1 = r1.divide(r2, 20, BigDecimal.ROUND_UP);
                valor = valor.add(r1);
            }
            BigDecimal t1;
            t1 = new BigDecimal(EONPhysicalTopology.valueSi.get(l.getAvaiableSlots()));
            t1 = t1.divide(r2, 20, BigDecimal.ROUND_UP);
            valor = valor.divide(t1, 20, BigDecimal.ROUND_UP);
            valorT = menos_1.subtract(valor);
            valorTL = valorTL.add(valorT);
        }
        return (valorTL.doubleValue() / (double) links.length);
    }

    /**
     * fragmentação Wang et al. 2015
     *
     */
    public static double getFragmentationWang(int links[], PhysicalTopology pt) {    
        EONLink l;
        ArrayList<Integer> blocos = new ArrayList<>();
        double prod = 1;
        double soma = 0;
        for (int i = 0; i < links.length; i++) {
            l = (EONLink) pt.getLink(links[i]);
            blocos = l.getLengthFreeBlock();
            for (int n : blocos) {
                prod = prod * EONPhysicalTopology.valueA.get(n);
            }
            soma +=prod;
        }
        return soma;
    }
    
    
}
