import sys
import os
import logging
import logging.config
import random
import networkx as nx
import matplotlib.pyplot as plt
from math import ceil
from pulp import *
from pathlib import Path

# 获取当前文件的绝对路径
current_file = Path(__file__).resolve()

# 定位到项目根目录（包含network和solver的目录）
project_root = current_file.parent.parent

# 将项目根目录加入模块搜索路径
sys.path.insert(0, str(project_root))

# 现在可以导入network包
from network.generator import TopoGen

# 配置日志
log_config_path = "../logconfig.ini"
logging.config.fileConfig(log_config_path)
logger = logging.getLogger(__name__)

# 生成拓扑
topo = TopoGen()
topo.generate(path_gml="None", path_graphml="../topology/SixNode.graphml")

# 初始化问题
prob = LpProblem("PartiallySecuredOpticalNetwork", LpMaximize)

# 输入参数
N = len(topo.G.nodes)  # 节点数量，可根据实际情况调整
E = len(topo.G.edges)
SL = 0.6  # 安全链路比率
LB = 1000  # 链路带宽
L = (0, 1)  # 链路安全性

SC = (0.4, 0.3, 0.3)  # 不同类型业务比率，依次为无、尽力、高需求
RB = 10  # 业务带宽需求
RS = (0, 1, 2)  # 业务安全需求
NC = 100  # 业务数量

# # 创建节点集 V
# V = [f'v{i}' for i in topo.G.nodes]

# # 创建链路集 E
# E = [(f'v{i}', f'v{j}') for i, j in topo.G.edges] + [(f'v{j}', f'v{i}') for i, j in topo.G.edges]

# # 安全容量 S (示例值)
# S = {1: 5, 2: 5}  # 每个安全等级有5个光纤可以配备

# 服务请求 (示例数据)
security_reqs = random.choices(RS, weights=SC, k=NC)
calls = {}
for i in range(NC):
    # 随机选择起始节点和目的节点（确保不重合）
    while True:
        start_node = random.randint(0, N - 1)
        end_node = random.randint(0, N - 1)
        if start_node != end_node:
            break

    calls[start_node] = {end_node: "rate": RB, "sec": security_reqs[i]}

# services = [
#     {'source': 'v1', 'dest': 'v5', 'RB': 0.4, 'RS': 2},
#     {'source': 'v2', 'dest': 'v6', 'RB': 0.3, 'RS': 2},
#     {'source': 'v2', 'dest': 'v4', 'RB': 0.3, 'RS': 2},
#     {'source': 'v3', 'dest': 'v5', 'RB': 0.2, 'RS': 1},
#     {'source': 'v3', 'dest': 'v1', 'RB': 0.3, 'RS': 2},
#     {'source': 'v6', 'dest': 'v1', 'RB': 0.3, 'RS': 2},
#     {'source': 'v3', 'dest': 'v4', 'RB': 0.2, 'RS': 1},
#     {'source': 'v5', 'dest': 'v6', 'RB': 0.3, 'RS': 2},
#     {'source': 'v4', 'dest': 'v2', 'RB': 0.3, 'RS': 2}
# ]

# 决策变量
# 加密状态变量 κ_{ij,l}
kappa = LpVariable.dicts(
    "kappa",
    [(i, j, l) for (i, j) in topo.G.edges for l in L],
    cat='Binary'
)

# 路由状态变量 λ_{ij,l}^{sd,c}
lambda_ = LpVariable.dicts(
    "lambda",
    [(s['source'], s['dest'], i, j, l) for s in services for (i, j) in E for l in range(1, L + 1)],
    cat='Binary'
)

# 路由成功变量 γ^{sd}
gamma = LpVariable.dicts("gamma",
                            [(s['source'], s['dest']) for s in services],
                            cat='Binary')

# D. 目标函数: 最大化成功路由的服务数量
prob += lpSum([gamma_sd[(s['source'], s['dest'])] for s in services]), "Total_Successful_Services"

# C. 约束条件
# C.1 拓扑决策约束
# 约束(1): 每个节点的加密链路不超过其连接数
for i in V:
    connected_links = [1 for (u, v) in E if u == i]
    prob += lpSum([kappa[(i, j, l)] for j in V if (i, j) in E for l in range(1, L + 1)]) <= sum(connected_links)

# 约束(2): 每条链路最多一个安全等级
for (i, j) in E:
    prob += lpSum([kappa[(i, j, l)] for l in range(1, L + 1)]) <= 1

# 约束(3): 每个安全等级的链路总数不超过其容量
for l in range(1, L + 1):
    prob += lpSum([kappa[(i, j, l)] for (i, j) in E]) <= 2 * S[l]

# 约束(4): 对称性
for (i, j) in E:
    for l in range(1, L + 1):
        prob += kappa[(i, j, l)] == kappa[(j, i, l)]

# C.2 服务路径约束
for s in services:
    src, dst = s['source'], s['dest']

    # 约束(6): 源节点流出
    prob += lpSum([lambda_sd[(src, dst, src, j, l)]
                   for j in V if (src, j) in E for l in range(1, L + 1)]) == gamma_sd[(src, dst)]

    # 约束(7): 目的节点流入
    prob += lpSum([lambda_sd[(src, dst, i, dst, l)]
                   for i in V if (i, dst) in E for l in range(1, L + 1)]) == gamma_sd[(src, dst)]

    prob += lpSum([lambda_sd[(src, dst, i, src, l)]
                   for i in V if (i, src) in E for l in range(1, L + 1)]) == 0

    prob += lpSum([lambda_sd[(src, dst, dst, j, l)]
                   for j in V if (dst, j) in E for l in range(1, L + 1)]) == 0

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
    prob += lpSum(
        [lambda_sd[(s['source'], s['dest'], i, j, l)] * s['RB'] + lambda_sd[(s['source'], s['dest'], j, i, l)] * s['RB']
         for s in services]) <= 1

# 约束(10): 安全要求
for s in services:
    for (i, j) in E:
        for l in range(1, L + 1):
            prob += lambda_sd[(s['source'], s['dest'], i, j, l)] * s['RS'] <= l * kappa[(i, j, l)]
            prob += lambda_sd[(s['source'], s['dest'], i, j, l)] <= kappa[(i, j, l)]

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
        logger.info("From %s to %s with %s level", s['source'], s['dest'], s['RS'])

# 打印服务路由路径
logger.info("Service routing paths:")
for s in services:
    if gamma_sd[(s['source'], s['dest'])].value() == 1:
        logger.info("Service %s -> %s (level %s):", s['source'], s['dest'], s['RS'])
        path = []
        for (i, j) in E:
            for l in range(1, L + 1):
                if lambda_sd[(s['source'], s['dest'], i, j, l)].value() == 1:
                    path.append(f"{i}->{j} (level {l})")
        logger.info(" -> ".join(path))

# 绘制拓扑结构图
# 加载拓扑数据
logger.info("Loading topology data for visualization...")
G = nx.Graph()
for node, attr in topo.G.nodes(data=True):
    G.add_node(node, **attr)
pos = {node: (G.nodes[node]["Longitude"], G.nodes[node]["Latitude"]) for node in G.nodes}

# 收集加密链路
encrypted_edges = {}
for l in range(1, L + 1):
    encrypted_edges[l] = []
    for (i, j) in E:
        if kappa[(i, j, l)].value() == 1:
            encrypted_edges[l].append((i.replace('v', ''), j.replace('v', '')))

# # 绘制拓扑
# # nx.draw(G, pos, width=0.5, linewidths=0.5, node_size=30, node_color="#0070C0", edge_color="k", with_labels=True)
# nx.draw_networkx_nodes(G, pos, linewidths=0.5, node_size=30, node_color="#0070C0")
# nx.draw_networkx_labels(G, pos, labels={n: n for n in G.nodes})
# edge_color = ['b', 'g', 'y', 'r']
# for i, l in enumerate(encrypted_edges):
#     nx.draw_networkx_edges(G, pos, encrypted_edges[l], edge_color=edge_color[i], width=2)
# plt.show()

# 初始化字典记录各安全等级的业务总数和阻塞数
security_stats = {}
for s in services:
    rs = s['RS']
    security_stats.setdefault(rs, {'total': 0, 'blocked': 0})
    security_stats[rs]['total'] += 1

# 统计阻塞业务数量
for s in services:
    rs = s['RS']
    if gamma_sd[(s['source'], s['dest'])].value() != 1:
        security_stats[rs]['blocked'] += 1

# 计算并打印阻塞率
print("\n各安全等级业务阻塞率分析:")
print("=" * 50)
print(f"{'安全等级':<10}{'总业务数':<10}{'阻塞业务数':<12}{'阻塞率(%)':<10}")
print("-" * 50)

for rs, stats in sorted(security_stats.items()):
    total = stats['total']
    blocked = stats['blocked']
    blocking_rate = (blocked / total) * 100 if total > 0 else 0

    print(f"{rs:<12}{total:<10}{blocked:<12}{blocking_rate:.2f}%")

# 准备数据
security_levels = sorted(security_stats.keys())
blocking_rates = [(stats['blocked'] / stats['total']) * 100 for stats in security_stats.values()]

plt.figure(figsize=(10, 6))
bars = plt.bar(security_levels, blocking_rates, color=['blue', 'green', 'red'])

# 添加数值标签
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width() / 2., height,
             f'{height:.2f}%', ha='center', va='bottom')

plt.xlabel('Security Level')
plt.ylabel('Blocking Rate (%)')
# plt.title('各安全等级业务阻塞率')
plt.xticks(security_levels)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.show()
# plt.savefig('blocking_rates.png')
# print("\n阻塞率可视化图表已保存为 'blocking_rates.png'")
