import logging
import logging.config
import random

import numpy as np
import pandas as pd
import networkx as nx
from matplotlib import pyplot as plt
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
SLR = 0.6  # 安全链路比率
LB = 1000  # 链路带宽
L = (0, 1)  # 链路安全性

SC = (0.4, 0.3, 0.3)  # 不同类型业务比率，依次为无、尽力、高需求
RB = 10  # 业务带宽需求
RS = (0, 1, 2)  # 业务安全需求
NC = 200  # 业务数量

is_run = False  # 是否运行ILP
is_show = False # 是否绘制加密拓扑
is_plot = True  # 是否绘制结果图

SL = (E - round(E * SLR), round(E * SLR))

# 服务请求 (示例数据)
security_reqs = random.choices(RS, weights=SC, k=NC)
calls = [[[] for _ in range(N)] for _ in range(N)]
for i in range(NC):
    # 随机选择起始节点和目的节点（确保不重合）
    while True:
        start_node = random.randint(0, N - 1)
        end_node = random.randint(0, N - 1)
        if start_node != end_node:
            break

    calls[start_node][end_node].append(
        {"src": str(start_node), "dst": str(end_node), "id": i, "rate": RB, "sec": security_reqs[i]}
    )

# 决策变量
# 加密状态变量 κ_{ij,l}
kappa = LpVariable.dicts(
    "kappa",
    [(i, j, l) for i in topo.G.nodes for j in topo.G[i] for l in L],
    cat='Binary'
)

# 路由状态变量 λ_{ij,l}^{sd,c}
lambda_ = LpVariable.dicts(
    "lambda",
    [(call["src"], call["dst"], c, i, j, l) for row in calls for col in row for c, call in enumerate(col) for i in
     topo.G.nodes for j in topo.G[i] for l in L],
    cat='Binary'
)

# 路由成功变量 γ^{sd,c}
gamma = LpVariable.dicts(
    "gamma",
    [(call["src"], call["dst"], c) for row in calls for col in row for c, call in enumerate(col)],
    cat='Binary'
)

# D. 目标函数: 最大化成功路由的服务数量
prob += lpSum([gamma[(call["src"], call["dst"], c)] for row in calls for col in row for c, call in
               enumerate(col)]), "Total_Successful_Services"

# C. 约束条件
# C.1 拓扑决策约束
# 约束(1): 每个节点的加密链路不超过其连接数
for i in topo.G.nodes:
    prob += lpSum([kappa[(i, j, l)] for j in topo.G[i] for l in L]) <= topo.G.degree(i)

# 约束(2): 每条链路最多一个安全等级
for i in topo.G.nodes:
    for j in topo.G[i]:
        prob += lpSum([kappa[(i, j, l)] for l in L]) <= 1

# 约束(3): 每个安全等级的链路总数不超过其容量
for l in L:
    prob += lpSum([kappa[(i, j, l)] for i in topo.G.nodes for j in topo.G[i]]) <= 2 * SL[l]

# 约束(4): 对称性
for i in topo.G.nodes:
    for j in topo.G[i]:
        for l in L:
            prob += kappa[(i, j, l)] == kappa[(j, i, l)]

# C.2 服务路径约束
for row in calls:
    for col in row:
        for c, call in enumerate(col):
            s, d = call["src"], call["dst"]

            # 约束(5): 源节点流出
            prob += lpSum([lambda_[(s, d, c, s, j, l)]
                           for j in topo.G[s] for l in L]) == gamma[(s, d, c)]

            # 约束(6): 目的节点流入
            prob += lpSum([lambda_[(s, d, c, i, d, l)]
                           for i in topo.G[d] for l in L]) == gamma[(s, d, c)]

            # 约束(8)
            prob += lpSum([lambda_[(s, d, c, i, s, l)]
                           for i in topo.G[s] for l in L]) == 0

            # 约束(9)
            prob += lpSum([lambda_[(s, d, c, d, j, l)]
                           for j in topo.G[d] for l in L]) == 0

            # 约束(5): 中间节点流量守恒
            for k in topo.G.nodes:
                if k != s and k != d:
                    prob += lpSum([lambda_[(s, d, c, i, k, l)]
                                   for i in topo.G[k] for l in L]) == \
                            lpSum([lambda_[(s, d, c, k, j, l)]
                                   for j in topo.G[k] for l in L])

            # 约束(10)
            for i in topo.G.nodes:
                for j in topo.G[i]:
                    for l in L:
                        prob += lambda_[(s, d, c, i, j, l)] <= kappa[(i, j, l)]

# C.3 资源约束
# 约束(11): 链路带宽容量
for i in topo.G.nodes:
    for j in topo.G[i]:
        for l in L:
            prob += lpSum(
                [(lambda_[(call["src"], call["dst"], c, i, j, l)] + lambda_[
                    (call["src"], call["dst"], c, j, i, l)]) * RB
                 for row in calls for col in row for c, call in enumerate(col)]
            ) <= LB

# 约束(12): 安全要求
for row in calls:
    for col in row:
        for c, call in enumerate(col):
            s, d = call["src"], call["dst"]
            for i in topo.G.nodes:
                for j in topo.G[i]:
                    for l in L:
                        prob += lambda_[(s, d, c, i, j, l)] * call["sec"] <= l * kappa[(i, j, l)] * 2

# print(listSolvers(onlyAvailable=True))
if is_run:
    # 求解问题
    status = prob.solve(CPLEX_CMD(msg=False))
    if LpStatus[status] == "Optimal":
        pass
    else:
        raise RuntimeError

# 输出结果(阻塞率、拓扑、暴露率、偏差)
logger.info("Status: %s", LpStatus[prob.status])
logger.info("Total successful services: %s", value(prob.objective))

# 打印链路加密配置
logger.info("Link encryption configurations:")
link_status = {"enc": 0, "nom": 0}
for (i, j, l) in kappa:
    logger.info(f"Kappa {i}-{j}-{l} encrypted: {kappa[(i, j, l)].value()}")
    if kappa[(i, j, l)].value() == 1 and kappa[(j, i, l)].value() == 1:
        if l == 0:
            link_status["nom"] += 1
        elif l == 1:
            link_status["enc"] += 1
    elif kappa[(i, j, l)].value() == 0 and kappa[(j, i, l)].value() == 0:
        pass
    else:
        logger.error(
            f"There exist the third status Kappa {i}-{j}-{l}: {kappa[(i, j, l)].value()} and Kappa {j}-{i}-{l}: {kappa[(j, i, l)].value()}")
logger.info(f"Encrypt links: {link_status["enc"] / 2} and norm links: {link_status["nom"] / 2}")  # 除4是因为i-j与j-i相等，所以除2
logger.info(f"The encryption rate is {link_status["enc"] / 2 / E}")

# 打印路由成功的服务
logger.info("Successfully routed services:")


def get_calls_routed_paths():
    """
    格式 {(src, dst, c): [(i, j, l), ...]}
    """
    paths = {}
    for (s, d, c) in gamma:
        if gamma[(s, d, c)].value() != 1:
            continue
        path = []
        for i in topo.G.nodes:
            for j in topo.G[i]:
                for l in L:
                    if lambda_[(s, d, c, i, j, l)].value() == 1:
                        if kappa[(i, j, l)].value() != 1:
                            logger.error(
                                f"Lambda {s}-{d}-{c}-{i}-{j}-{l} is 1, but Kappa {i}-{j}-{l} is {kappa[(i, j, l)].value()}?")
                        path.append((i, j, l))
        paths[(s, d, c)] = path
    return paths


routed_paths = get_calls_routed_paths()
for (s, d, c) in routed_paths:
    logger.info(f"Call src {s}, dst {d}, index {c} routed with sec {calls[int(s)][int(d)][c]["sec"]}")
    logger.info(routed_paths[(s, d, c)])

res = {
    "topology": "6N8E",
    "num of calls": NC,
    "secure link rate": SLR
}

# 初始化字典记录各安全等级的业务总数和阻塞数
security_stats = {}
for row in calls:
    for col in row:
        for c, call in enumerate(col):
            rs = call["sec"]
            security_stats.setdefault(rs, {'total': 0, 'blocked': 0})
            security_stats[rs]['total'] += 1

# 统计阻塞业务数量
for (s, d, c) in gamma:
    rs = calls[int(s)][int(d)][c]["sec"]
    if gamma[(s, d, c)].value() != 1:
        security_stats[rs]['blocked'] += 1
num_calls = sum([security_stats[rs]["total"] for rs in security_stats])
res["blocking rate"] = sum([security_stats[rs]["blocked"] for rs in security_stats]) / num_calls * 100

# 计算并打印阻塞率
for rs, stats in sorted(security_stats.items()):
    total = stats['total']
    blocked = stats['blocked']
    blocking_rate = (blocked / total) * 100 if total > 0 else 0
    res[f"blocking rate {rs}"] = blocking_rate
    res[f"br {rs} stack"] = (blocked / num_calls) * 100 if num_calls > 0 else 0

# 计算偏差
security_deviations = {}
for (s, d, c) in routed_paths:
    div_value = 0.0
    rs = calls[int(s)][int(d)][c]["sec"]
    for (i, j, l) in routed_paths[(s, d, c)]:
        # div_value += (G[u][v]['link_security'] - np.ceil(call.security/10)) ** 2
        div_value += (l - np.ceil(rs / 10))
    div_value = (div_value / (len(routed_paths[(s, d, c)]))) ** 0.5
    security_deviations.setdefault(rs, [])
    security_deviations[rs].append(div_value)
res["security deviations"] = np.mean([x for rs in security_deviations for x in security_deviations[rs]])
for rs, stats in sorted(security_deviations.items()):
    res[f"security deviations {rs}"] = np.mean(stats)

# 计算暴露率
exposure_rates = {}
for (s, d, c) in routed_paths:
    expo_value = [0.0, 0.0]
    for (i, j, l) in routed_paths[(s, d, c)]:
        distance = ((topo.G.nodes[i]["Latitude"] - topo.G.nodes[j]["Latitude"]) ** 2 +
                    (topo.G.nodes[i]["Longitude"] - topo.G.nodes[j]["Longitude"]) ** 2) ** 0.5
        expo_value[l] += distance  # 记录非/安全路径长度
    expo_rate = expo_value[0] / sum(expo_value) * 100 if sum(expo_value) != 0 else 0
    rs = calls[int(s)][int(d)][c]["sec"]
    exposure_rates.setdefault(rs, [])
    exposure_rates[rs].append(expo_rate)
res["exposure rate"] = np.mean([x for rs in exposure_rates for x in exposure_rates[rs]])
for rs, stats in sorted(exposure_rates.items()):
    res[f"exposure rate {rs}"] = np.mean(stats)

# 显示所有列
pd.set_option('display.max_columns', None)
# 显示所有行
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 5000)
# 设置value的显示长度为100，默认为50
pd.set_option('max_colwidth', 100)
# print(pd.DataFrame([res]))
df = pd.DataFrame([res])
print(df.to_csv(sep=',', index=False))


def style(width, height, fontsize=11):
    plt.rcParams['figure.figsize'] = (width * 0.39370, height * 0.39370)  # figure size in inches
    # plt.rcParams['font.family'] = 'serif'
    # plt.rcParams['font.serif'] = ['Times New Roman']
    plt.rcParams['font.sans-serif'] = 'cambria'
    plt.rcParams['font.size'] = fontsize
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['patch.linewidth'] = 0.5
    plt.rcParams['axes.linewidth'] = 0.5
    plt.rcParams['ytick.major.width'] = 0.5
    plt.rcParams['xtick.major.width'] = 0.5
    plt.rcParams['ytick.direction'] = 'in'
    plt.rcParams['xtick.direction'] = 'in'


if is_show:
    # 绘制拓扑结构图
    pos = {node: (topo.G.nodes[node]["Longitude"], topo.G.nodes[node]["Latitude"]) for node in topo.G.nodes}

    # 收集加密链路
    encrypted_edges = {}
    for l in L:
        encrypted_edges[l] = []
        for (i, j, l) in kappa:
            if kappa[(i, j, l)].value() == 1:
                encrypted_edges.setdefault(l, [])
                encrypted_edges[l].append((i, j))

    # 绘制拓扑
    style(width=8.4 * 1, height=6.3 * 1)
    nx.draw(
        topo.G, pos, with_labels=True,
        linewidths=1.5, width=2, edge_color='#FFE64A',
        node_size=200, node_color="#E8AD76", edgecolors="#FFFFFF"
    )
    edge_color = ['#FFE64A', '#FF424B']
    # for i, l in enumerate(sorted(encrypted_edges.keys())):
    #     nx.draw_networkx_edges(topo.G, pos, encrypted_edges[l], edge_color=edge_color[i], width=2)
    nx.draw_networkx_edges(topo.G, pos, encrypted_edges[1], edge_color=edge_color[1], width=2)
    # plt.title("Secure Link Rate = 0.6")
    plt.show()

# 绘制数据结果
if not is_plot:
    sys.exit()

pf = pd.read_csv("../data/data_6N8E_load_br.csv")


def plot_stack_br_sec():
    grouped = pf.groupby("secure link rate")[["br 0 stack", "br 1 stack", "br 2 stack"]].sum().reset_index()

    style(width=8.4 * 1.3, height=6.3 * 1.3)

    # 绘制堆积面积图
    plt.stackplot(
        grouped["secure link rate"] * 100,
        grouped["br 0 stack"],
        grouped["br 1 stack"],
        grouped["br 2 stack"],
        # labels=['Sec. Req. = 0', 'Sec. Req. = 1', 'Sec. Req. = 2'],
        colors=['#64FF98', '#FFF57D', '#FF7D82'],
        edgecolor='#FFFFFF',
        linewidth=1,
        alpha=1
    )

    # 绘制堆积柱状图
    width = 1
    plt.bar(
        grouped["secure link rate"] * 100, grouped["br 0 stack"],
        label='Sec. Req. = 0', width=width,
        color='#00E64B',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["secure link rate"] * 100, grouped["br 1 stack"],
        bottom=grouped["br 0 stack"],
        label='Sec. Req. = 1', width=width,
        color='#EBD700',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["secure link rate"] * 100, grouped["br 2 stack"],
        bottom=grouped["br 0 stack"] + grouped["br 1 stack"],
        label='Sec. Req. = 2', width=width,
        color='#CC000A',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )

    # 设置标题和标签
    plt.xlabel('Secure Link Rate (%)')
    plt.ylabel('Blocking Rate (%)')
    # 添加图例
    plt.legend()
    # 设置网格
    plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
    # 调整布局
    plt.tight_layout()
    # 显示图表
    plt.show()

def plot_stack_br_load():
    grouped = pf.groupby("num of calls")[["br 0 stack", "br 1 stack", "br 2 stack"]].sum().reset_index()

    style(width=8.4 * 1.3, height=6.3 * 1.3)

    # 绘制堆积面积图
    plt.stackplot(
        grouped["num of calls"],
        grouped["br 0 stack"],
        grouped["br 1 stack"],
        grouped["br 2 stack"],
        # labels=['Sec. Req. = 0', 'Sec. Req. = 1', 'Sec. Req. = 2'],
        colors=['#64FF98', '#FFF57D', '#FF7D82'],
        edgecolor='#FFFFFF',
        linewidth=1,
        alpha=1
    )

    # 绘制堆积柱状图
    width = 5
    plt.bar(
        grouped["num of calls"], grouped["br 0 stack"],
        label='Sec. Req. = 0', width=width,
        color='#00E64B',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["num of calls"], grouped["br 1 stack"],
        bottom=grouped["br 0 stack"],
        label='Sec. Req. = 1', width=width,
        color='#EBD700',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["num of calls"], grouped["br 2 stack"],
        bottom=grouped["br 0 stack"] + grouped["br 1 stack"],
        label='Sec. Req. = 2', width=width,
        color='#CC000A',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )

    # 设置标题和标签
    plt.xlabel('Num of Calls')
    plt.ylabel('Blocking Rate (%)')
    # 添加图例
    plt.legend()
    # 设置网格
    plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
    # 调整布局
    plt.tight_layout()
    # 显示图表
    plt.show()

def plot_stack_dev_load():
    grouped = pf.groupby("num of calls")[["security deviations", "security deviations 1", "security deviations 2"]].sum().reset_index()

    style(width=8.4 * 1.3, height=6.3 * 1.3)

    # 绘制堆积面积图
    plt.stackplot(
        grouped["num of calls"],
        grouped["security deviations"],
        grouped["security deviations 1"],
        grouped["security deviations 2"],
        # labels=['Sec. Req. = 0', 'Sec. Req. = 1', 'Sec. Req. = 2'],
        colors=['#64FF98', '#FFF57D', '#FF7D82'],
        edgecolor='#FFFFFF',
        linewidth=1,
        alpha=1
    )

    # 绘制堆积柱状图
    width = 5
    plt.bar(
        grouped["num of calls"], grouped["security deviations"],
        label='Sec. Req. = 0', width=width,
        color='#00E64B',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["num of calls"], grouped["security deviations 1"],
        bottom=grouped["security deviations"],
        label='Sec. Req. = 1', width=width,
        color='#EBD700',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["num of calls"], grouped["security deviations 2"],
        bottom=grouped["security deviations"] + grouped["security deviations 1"],
        label='Sec. Req. = 2', width=width,
        color='#CC000A',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )

    # 设置标题和标签
    plt.xlabel('Num of Calls')
    plt.ylabel('Security Deviations')
    plt.yticks([0.1*i for i in range(5)])
    # 添加图例
    plt.legend()
    # 设置网格
    plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
    # 调整布局
    plt.tight_layout()
    # 显示图表
    plt.show()

def plot_stack_expo_load():
    grouped = pf.groupby("num of calls")[["exposure rate", "exposure rate 1", "exposure rate 2"]].sum().reset_index()

    style(width=8.4 * 1.3, height=6.3 * 1.3)

    # 绘制堆积面积图
    plt.stackplot(
        grouped["num of calls"],
        grouped["exposure rate"],
        grouped["exposure rate 1"],
        grouped["exposure rate 2"],
        # labels=['Sec. Req. = 0', 'Sec. Req. = 1', 'Sec. Req. = 2'],
        colors=['#64FF98', '#FFF57D', '#FF7D82'],
        edgecolor='#FFFFFF',
        linewidth=1,
        alpha=1
    )

    # 绘制堆积柱状图
    width = 5
    plt.bar(
        grouped["num of calls"], grouped["exposure rate"],
        label='Sec. Req. = 0', width=width,
        color='#00E64B',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["num of calls"], grouped["exposure rate 1"],
        bottom=grouped["exposure rate"],
        label='Sec. Req. = 1', width=width,
        color='#EBD700',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )
    plt.bar(
        grouped["num of calls"], grouped["exposure rate 2"],
        bottom=grouped["exposure rate"] + grouped["exposure rate 1"],
        label='Sec. Req. = 2', width=width,
        color='#CC000A',
        linewidth=0.5, edgecolor="#FFFFFF", zorder=10
    )

    # 设置标题和标签
    plt.xlabel('Num of Calls')
    plt.ylabel('Exposure Rate (%)')
    plt.yticks([10*i for i in range(6)])
    # 添加图例
    plt.legend()
    # 设置网格
    plt.grid(color='#FAB9E1', linestyle=':', linewidth=0.5, alpha=1, zorder=0)
    # 调整布局
    plt.tight_layout()
    # 显示图表
    plt.show()

plot_stack_expo_load()
