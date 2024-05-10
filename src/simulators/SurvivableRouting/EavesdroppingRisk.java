package simulators.SurvivableRouting;

import network.Node;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

public class EavesdroppingRisk {
    private static final double RiskNodeRatio = 0.2;
    private static final Logger logger = LogManager.getLogger(EavesdroppingRisk.class);
    public EavesdroppingRisk(PhysicalTopology pt){
        Set<Integer> risk_nodes = setEavesdroppingRiskNodeRandom(pt);
        logger.trace("3.1.Randomly sampled eavesdropping nodes: "+risk_nodes);
    }

    public void setEavesdroppingRiskSharedLinkGroup(){
        // 节点关联性，层级关联性
        
    }

    private Set<Integer> setEavesdroppingRiskNodeRandom(PhysicalTopology pt){
        int num_nodes = pt.getNodesNum();
        Node[] nodes = pt.getNodes();
        Set<Integer> risk_nodes = new HashSet<>();

        while (risk_nodes.size() < (int)(RiskNodeRatio * num_nodes)) {
            int selected_node = (int)(Math.random() * num_nodes);
            risk_nodes.add(selected_node);
            nodes[selected_node].setAttr("TappingRisk", 1);
        }
        return risk_nodes;
    }
}
