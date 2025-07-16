
import logging
import logging.config
import networkx as nx
import matplotlib.pyplot as plt
from math import ceil
from pulp import *
from network.generator import TopoGen

# 配置日志
log_config_path = "./logconfig.ini"
logging.config.fileConfig(log_config_path)
logger = logging.getLogger(__name__)

# 生成拓扑
topo = TopoGen()
topo.generate(path_gml="None", path_graphml="./topology/SixNode.graphml")
topo.set(_type="")

# 初始化问题
prob = LpProblem("PartiallySecuredOpticalNetwork", LpMaximize)

# A. 输入参数
N = len(topo.G.nodes)  # 节点数量，可根据实际情况调整
L = 2  # 安全等级数量，可根据实际情况调整

# 创建节点集 V
V = [f'v{i}' for i in topo.G.nodes]

# 创建链路集 E
E = [(f'v{i}', f'v{j}') for i, j in topo.G.edges] + [(f'v{j}', f'v{i}') for i, j in topo.G.edges]

# 安全容量 S (示例值)
S = {1: 5, 2: 3}  # 每个安全等级有5个光纤可以配备

# 服务请求 (示例数据)
services = [
    {'source': 'v1', 'dest': 'v5', 'RB': 0.2, 'RS': 2},
    {'source': 'v2', 'dest': 'v6', 'RB': 0.3, 'RS': 1},
    {'source': 'v3', 'dest': 'v5', 'RB': 0.1, 'RS': 1},
    # 可以添加更多服务请求
]
sys.exit()
# B. 决策变量
# 加密状态变量 κ_{ij,l}
kappa = LpVariable.dicts("kappa",
                         [(i, j, l) for (i, j) in E for l in range(1, L + 1)],
                         cat='Binary')

# 路由状态变量 λ_{ij,l}^{sd}
lambda_sd = LpVariable.dicts("lambda",
                             [(s['source'], s['dest'], i, j, l)
                              for s in services for (i, j) in E for l in range(1, L + 1)],
                             cat='Binary')

# 路由成功变量 γ^{sd}
gamma_sd = LpVariable.dicts("gamma",
                            [(s['source'], s['dest']) for s in services],
                            cat='Binary')

# D. 目标函数: 最大化成功路由的服务数量
prob += lpSum([gamma_sd[(s['source'], s['dest'])] for s in services]), "Total_Successful_Services"

# C. 约束条件
# C.1 拓扑决策约束
# 约束(1): 每个节点的加密链路不超过其连接数
for i in V:
    connected_links = [1 for (u, v) in E if u == i or v == i]
    prob += lpSum([kappa[(i, j, l)] for j in V if (i, j) in E for l in range(1, L + 1)] +
                  [kappa[(j, i, l)] for j in V if (j, i) in E for l in range(1, L + 1)]) <= sum(connected_links)

# 约束(2): 每条链路最多一个安全等级
for (i, j) in E:
    prob += lpSum([kappa[(i, j, l)] for l in range(1, L + 1)]) <= 1

# 约束(3): 每个安全等级的链路总数不超过其容量
for l in range(1, L + 1):
    prob += lpSum([(kappa[(i, j, l)]+kappa[(j, i, l)])/2 for (i, j) in E]) <= S[l]

# 约束(4): 对称性
for (i, j) in E:
    for l in range(1, L + 1):
        prob += kappa[(i, j, l)] == kappa[(j, i, l)]

# C.2 服务路径约束
for s in services:
    src, dst = s['source'], s['dest']

    # 约束(5): 对称性
    for (i, j) in E:
        for l in range(1, L + 1):
            prob += lambda_sd[(src, dst, i, j, l)] == lambda_sd[(src, dst, j, i, l)]

    # 约束(6): 源节点流出
    prob += lpSum([lambda_sd[(src, dst, src, j, l)]
                   for j in V if (src, j) in E for l in range(1, L + 1)]) == gamma_sd[(src, dst)]

    # 约束(7): 目的节点流入
    prob += lpSum([lambda_sd[(src, dst, i, dst, l)]
                   for i in V if (i, dst) in E for l in range(1, L + 1)]) == gamma_sd[(src, dst)]

    # 约束(8): 中间节点流量守恒
    for k in V:
        if k != src and k != dst:
            prob += lpSum([lambda_sd[(src, dst, i, k, l)]
                           for i in V if (i, k) in E for l in range(1, L + 1)]) == \
                    lpSum([lambda_sd[(src, dst, k, j, l)]
                           for j in V if (k, j) in E for l in range(1, L + 1)])

# C.3 资源约束
# 约束(9): 链路带宽容量
for (i, j) in E:
    prob += lpSum([lambda_sd[(s['source'], s['dest'], i, j, l)] * s['RB']
                   for s in services for l in range(1, L + 1)]) <= 1

# 约束(10): 安全要求
for s in services:
    for (i, j) in E:
        for l in range(1, L + 1):
            prob += lambda_sd[(s['source'], s['dest'], i, j, l)] * ceil(s['RS'] * 1e-10) <= kappa[(i, j, l)]

# 求解问题
prob.solve()

# 输出结果
logger.info("Status: %s", LpStatus[prob.status])
logger.info("Total successful services: %s", value(prob.objective))

# 打印链路加密配置
logger.info("Link encryption configurations:")
for (i, j) in E:
    for l in range(1, L + 1):
        if kappa[(i, j, l)].value() == 1:
            logger.info("Link %s-%s encrypted at level %s", i, j, l)

# 打印路由成功的服务
logger.info("Successfully routed services:")
for s in services:
    if gamma_sd[(s['source'], s['dest'])].value() == 1:
        logger.info("From %s to %s", s['source'], s['dest'])

# 打印服务路由路径
logger.info("Service routing paths:")
for s in services:
    if gamma_sd[(s['source'], s['dest'])].value() == 1:
        logger.info("Service %s -> %s:", s['source'], s['dest'])
        path = []
        current = s['source']
        visited = set()
        while current != s['dest'] and current not in visited:
            visited.add(current)
            for (i, j) in E:
                for l in range(1, L + 1):
                    if i == current and lambda_sd[(s['source'], s['dest'], i, j, l)].value() == 1:
                        path.append(f"{i}->{j} (level {l})")
                        current = j
                        break
                else:
                    continue
                break
        logger.info(" -> ".join(path))

# 绘制拓扑结构图
# 加载拓扑数据
logger.info("Loading topology data for visualization...")
G = nx.Graph()

# 收集加密链路
encrypted_edges = []
for (i, j) in E:
    for l in range(1, L + 1):
        if kappa[(i, j, l)].value() == 1:
            encrypted_edges.append((i, j))

G.add_nodes_from(V)
G.add_edges_from(encrypted_edges)

# 绘制拓扑
nx.draw(G, with_labels=True)
plt.title('安全拓扑结构（加密链路）')
plt.axis('off')
plt.tight_layout()
plt.show()