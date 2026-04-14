## Secure Optical Network ILP

This workspace contains a research-oriented Python implementation of the ILP
described in `ILP.md`, built with `PuLP` and visualized with `networkx`.

### Files

- `main.py`: runnable demo entry point
- `secure_optical_ilp/models.py`: data classes for links, requests, costs, and solutions
- `secure_optical_ilp/solver.py`: two-stage ILP builder and solver
- `secure_optical_ilp/topology_loader.py`: read `GraphML` topology files with `networkx`
- `secure_optical_ilp/visualization.py`: `networkx` plots for `mnk` lightpaths and `ijw` links
- `requirements.txt`: Python dependencies

### Modeling Notes

The uploaded formulation contains a few nonlinear or inconsistent terms. To keep
the model solvable by `PuLP`, the implementation uses the following linearized
assumptions:

1. `delta(x)` is represented by binary activation variables for lightpaths.
2. `1 / sum(mu)` is replaced by a two-stage solve:
   - stage 1: maximize the number of accepted requests
   - stage 2: fix the accepted count and minimize security cost
3. The constraints written as `sum lambda = 1` and `sum kappa = 1` are treated
   as activation constraints instead of hard equalities, because the equalities
   are inconsistent with bandwidth and key-rate sharing.
4. Security port cost is charged per active security lightpath slot.
5. A very small tie-break term is added to suppress equivalent cyclic routes and
   prefer shorter logical/physical paths.

### Run

```bash
python -m pip install -r requirements.txt
python main.py --topology topology/SixNode.graphml
```

You can also switch to another file in the `topology` folder, for example:

```bash
python main.py --topology topology/Nsfnet.graphml
```

### Output

Running `main.py` creates:

- `outputs/solution.json`
- `outputs/lightpaths_mnk.png`
- `outputs/links_ijw.png`

Replace the demo topology and requests in `main.py` with your own data to use
the model on a different instance.
