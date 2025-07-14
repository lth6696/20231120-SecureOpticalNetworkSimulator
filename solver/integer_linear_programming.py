import pulp
import numpy as np


def secure_optical_network_ilp(N, E, S):
    """
    基于图片中的ILP模型实现安全光网络优化
    参数:
        N: 节点数量 (对应|V|)
        E: 无向链路集合 (对应E), 格式为[(i,j), ...]
        S: 各安全等级可用光纤数列表 (对应s^l), [s^1, s^2, ..., s^L]
    """
    # 创建最大化问题
    prob = pulp.LpProblem("Secure_Optical_Network_Optimization", pulp.LpMaximize)

    # 1. 预处理参数
    nodes = range(1, N + 1)  # 节点编号1到N
    L = len(S)  # 安全等级数量
    security_levels = range(1, L + 1)  # 安全等级1到L

    # 创建邻接矩阵（无向图）
    adj_matrix = np.zeros((N + 1, N + 1), dtype=int)  # 节点编号从1开始
    for (i, j) in E:
        adj_matrix[i][j] = 1
        adj_matrix[j][i] = 1

    # 2. 创建决策变量 κ_{ij}^l (对应图片中的变量定义)
    kappa = {}
    for i in nodes:
        for j in nodes:
            if i != j and adj_matrix[i][j] == 1:  # 仅对存在的链路创建变量
                for l in security_levels:
                    var_name = f"kappa_{i}_{j}_{l}"
                    kappa[(i, j, l)] = pulp.LpVariable(var_name, cat='Binary')

    # 3. 设置目标函数 (对应图片中的公式5)
    total_secure_links = pulp.lpSum(kappa.values())
    prob += (2 * total_secure_links) / (N * (N - 1)), "Security_Connectivity"

    # 4. 添加约束条件
    # C.1.1 连通性约束 (公式1)
    for i in nodes:
        # 计算节点i的物理连接数 (∑e_{ij})
        physical_deg = sum(adj_matrix[i][j] for j in nodes if j != i)

        # 节点i的安全连接总数 (∑∑κ_{ij}^l)
        security_deg = pulp.lpSum(
            kappa[(i, j, l)]
            for j in nodes if j != i and adj_matrix[i][j] == 1
            for l in security_levels
        )
        prob += security_deg <= physical_deg, f"Connectivity_Node_{i}"

    # C.1.2 单链路约束 (公式2)
    for i in nodes:
        for j in nodes:
            if i != j and adj_matrix[i][j] == 1:  # 仅对存在的链路添加约束
                prob += pulp.lpSum(
                    kappa[(i, j, l)] for l in security_levels
                ) <= 1, f"Single_Link_{i}_{j}"

    # C.2.1 安全容量约束 (公式3)
    for l in security_levels:
        prob += pulp.lpSum(
            kappa[(i, j, l)]
            for (i, j, l_var) in kappa if l_var == l
        ) <= S[l - 1], f"Security_Level_{l}"

    # C.2.2 对称性约束 (公式4) - 通过变量定义自动满足
    # 因为我们只定义了一个方向的变量，使用时需要确保对称性
    for i in nodes:
        for j in nodes:
            if i != j and adj_matrix[i][j] == 1:
                for l in security_levels:
                    prob += kappa[(i, j, l)] == kappa[(j, i, l)]

    return prob, kappa


# 示例使用
if __name__ == "__main__":
    # 示例1: 4节点全连接网络 (对应图片中的示例)
    N = 4
    E = [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]  # 全连接
    S = [3, 2]  # 2个安全等级，s^1=3, s^2=2

    # 创建并求解模型
    prob, kappa = secure_optical_network_ilp(N, E, S)
    prob.solve()

    # 结果分析
    print("=" * 50)
    print("优化状态:", pulp.LpStatus[prob.status])
    print("目标函数值 (安全连通性):", pulp.value(prob.objective))

    # 打印激活的安全链路
    print("\n激活的安全链路:")
    for key, var in kappa.items():
        if var.varValue > 0.5:  # 激活的链路
            i, j, l = key
            print(f"  链路 {i}-{j}: 安全等级 {l}")

    # 检查安全等级使用情况
    print("\n安全等级使用统计:")
    for l in range(1, len(S) + 1):
        used = sum(1 for key in kappa if key[2] == l and kappa[key].varValue > 0.5)
        print(f"  等级 {l}: 使用 {used}/{S[l - 1]} 条光纤")

    # 检查节点连接度
    print("\n节点连接度检查:")
    for i in range(1, N + 1):
        phys_deg = sum(1 for (a, b) in E if a == i or b == i)
        sec_deg = sum(1 for (a, b, l) in kappa
                      if (a == i or b == i) and kappa[(a, b, l)].varValue > 0.5)
        print(f"  节点 {i}: 物理连接度={phys_deg}, 安全连接度={sec_deg}")

    # 示例2: 6节点环网
    print("\n" + "=" * 50)
    print("6节点环网示例")
    print("=" * 50)
    N = 6
    E = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 1)]  # 环网
    S = [4, 2]  # 2个安全等级

    prob, kappa = secure_optical_network_ilp(N, E, S)
    prob.solve()

    print("优化状态:", pulp.LpStatus[prob.status])
    print("安全连通性:", pulp.value(prob.objective))

    # 打印重要链路的高安全等级分配
    print("\n高安全等级链路分配:")
    for (i, j, l) in kappa:
        if l == 2 and kappa[(i, j, l)].varValue > 0.5:  # 等级2的链路
            print(f"  关键链路 {i}-{j} 使用高安全等级")