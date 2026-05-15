# WDM Optical Network Simulator

这是一个参考 ONS v3.0 设计思想、面向 WDM 场景重构的 Python 3.11 离散事件仿真器。项目重点实现 WDM physical topology、virtual topology、flow arrival/departure、RWA/grooming 算法、统计指标和命令行入口。

不包含 EON、SDM、SNR、BulkData、Batch 或 GUI。

## 目录结构

```text
models/
  flow.py              # Flow, Event, LightpathId, ProvisioningPlan, RoutingDecision
  ports.py               # RoutingAlgorithm, NetworkView, ResourceAllocator, Observer
  events.py

topology/
  physical.py
  virtual.py
  snapshot.py            # NetworkSnapshot / NetworkView 实现

resource/
  allocator.py           # NetworkXResourceAllocator
  allocation.py          # AllocationResult, ReleaseResult

algorithms/
  base.py
  registry.py
  aux_graph/
    models.py
    builder.py
    view.py
    constraints.py
  ag_jdr_grooming.py
  ag_sf_grooming.py
  ag_cf_grooming.py

event/
  scheduler.py
  traffic.py

simulation/
  control_plane.py
  runner.py

observability/
  stats.py
  tracer.py

config.py
main.py
```

## 安装依赖

```bash
python -m pip install -e .
```

项目依赖 `networkx`。

## 运行示例

```bash
python -m wdm_sim examples/config.json
```

或安装后：

```bash
wdm-sim examples/config.json
```

受保护工作/备份成对路径算法示例：

```bash
python -m wdm_sim examples/protected_config.json --pretty
```

## 运行测试

```bash
python -m unittest discover -s tests
```

可用算法名称：

- `shortest_path_first_fit`
- `grooming_shortest_path`
- `k_shortest_path_first_fit`
- `joint_kpath_pair_grooming`

## 配置说明

`examples/config.json` 中包含：

- `algorithm`: 算法名称
- `topology_path`: 拓扑文件路径，相对配置文件解析
- `traffic`: 负载、平均 holding time、call type、pair weight 等参数
- `k_paths`: KSP 算法使用的路径数量

如果 `traffic.pairs` 为空或缺失，仿真器会在所有 `src != dst` 节点对之间均匀随机选择。

WDM 到达间隔均值采用：

```text
mean_arrival_time = (mean_holding_time * (mean_rate / max_rate)) / load
```

## 拓扑说明

拓扑支持 JSON、XML 和 GraphML。JSON/XML 拓扑是有向图，双向链路需要显式写两条方向相反的 link。GraphML 如果是 `edgedefault="undirected"`，读取时会自动展开为两条方向相反的 WDM 链路。每条 link 拥有：

- `wavelengths`: wavelength 数量
- `bandwidth`: 每个 wavelength 的固定带宽
- `weight`: 路由权重

GraphML 文件通常不包含 WDM 参数；缺省时每个节点使用 8 个 grooming 输入/输出端口，每条链路使用 4 个 wavelength，每个 wavelength 带宽为 100。若 GraphML edge 存在 `weight`、`distance` 或 `cost`，会作为边权；否则若节点存在经纬度，会使用地理距离作为边权。

## 受保护 Pair Grooming 算法

`joint_kpath_pair_grooming` 实现上传伪代码中的 Joint KPath Pair Grooming：

- 在容量可用的辅助图上计算最多 `k_paths` 条工作路径。
- 对每条工作路径临时排除其物理边，构造备份图。
- 在备份图上寻找与工作路径链路不相交的最短备份路径。
- 在可行解中选择工作路径成本 + 备份路径成本最低的一组。
- 对 `security_required=true` 的 flow 建立工作 lightpath 并预留 backup lightpath；flow 离开时同时释放工作和备份资源。
- 对 `security_required=false` 的 flow，算法退化为先 grooming、再 KSP first-fit。

## WDM 资源语义

- 创建 lightpath 时占用每条 link 上指定 wavelength，并占用源节点 grooming input port 与宿节点 grooming output port。
- flow 接入 lightpath 时不再检查 wavelength 是否 free，只检查该 lightpath 对应 wavelength 的剩余带宽。
- 多个 flow 可 grooming 到同一个 src-dst lightpath，直到剩余带宽不足。
- 最后一个 flow 离开后，若 lightpath 非 reserved，则删除 lightpath 并释放物理资源。
- 初版不实现 wavelength converter，因此同一 lightpath 的所有 link 使用同一个 wavelength；数据结构仍保留 `wavelengths: list[int]`。
