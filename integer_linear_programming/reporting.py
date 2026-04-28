from __future__ import annotations

from pathlib import Path

from .data_model import NetworkInstance, SolverSolution


def format_solution_report(instance: NetworkInstance, solution: SolverSolution) -> str:
    """Return a Markdown report with the main ILP result mappings."""
    request_lookup = {request.request_id: request for request in instance.requests}

    sections = [
        "# ILP Solution Report",
        "",
        "## Summary",
        _format_summary_table(solution),
        "",
        "## Request To Lightpath Mapping",
        _format_request_lightpath_table(solution, request_lookup),
        "",
        "## Lightpath To Physical Edge Mapping",
        _format_lightpath_edge_table(solution),
    ]
    return "\n".join(sections).rstrip() + "\n"


def write_solution_report(
    instance: NetworkInstance,
    solution: SolverSolution,
    path: str | Path,
) -> None:
    """Write the readable solution report to disk."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_solution_report(instance, solution),
        encoding="utf-8",
    )


def _format_summary_table(solution: SolverSolution) -> str:
    rows = [
        ("status", solution.status),
        ("accepted_requests", f"{solution.admitted_count}/{solution.total_requests}"),
    ]
    if solution.phase_one_objective is not None:
        rows.append(("phase1_max_accept", _format_number(solution.phase_one_objective)))
    if solution.phase_two_objective is not None:
        rows.append(("phase2_min_cost", _format_number(solution.phase_two_objective)))
    rows.extend(
        (name, _format_number(value))
        for name, value in sorted(solution.total_cost_breakdown.items())
    )
    return _format_markdown_table(("item", "value"), rows)


def _format_request_lightpath_table(solution: SolverSolution, request_lookup) -> str:
    rows = []
    for route in solution.request_routes:
        request = request_lookup[route.request_id]
        rows.append(
            (
                route.request_id,
                f"{request.source}->{request.target}",
                _format_number(request.bandwidth),
                _format_number(request.key_rate),
                _format_number(request.security_level),
                str(route.admitted),
                str(route.security_enabled),
                _join_labels(route.service_lightpaths),
                _join_labels(route.security_lightpaths),
            )
        )
    if not rows:
        return "_No request routes._"
    return _format_markdown_table(
        (
            "request",
            "source_target",
            "bandwidth",
            "key_rate",
            "security_level",
            "admitted",
            "security_enabled",
            "service_lightpaths",
            "security_lightpaths",
        ),
        rows,
    )


def _format_lightpath_edge_table(solution: SolverSolution) -> str:
    rows = []
    for lightpath in (*solution.service_lightpaths, *solution.security_lightpaths):
        lightpath_label = lightpath.key.label()
        request_ids = ", ".join(lightpath.request_ids) or "-"
        if not lightpath.physical_assignments:
            rows.append(
                (
                    lightpath.layer,
                    lightpath_label,
                    request_ids,
                    _format_number(lightpath.carried_load),
                    "-",
                    "-",
                    "-",
                )
            )
            continue
        for assignment in lightpath.physical_assignments:
            rows.append(
                (
                    lightpath.layer,
                    lightpath_label,
                    request_ids,
                    _format_number(lightpath.carried_load),
                    f"{assignment.source}->{assignment.target}",
                    str(assignment.wavelength),
                    _format_number(assignment.distance),
                )
            )
    if not rows:
        return "_No active lightpaths._"
    return _format_markdown_table(
        (
            "layer",
            "lightpath_mnk",
            "requests",
            "carried_load",
            "physical_edge_ij",
            "wavelength_w",
            "distance",
        ),
        rows,
    )


def _format_markdown_table(headers: tuple[str, ...], rows) -> str:
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        table.append("| " + " | ".join(_escape_cell(value) for value in row) + " |")
    return "\n".join(table)


def _escape_cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _join_labels(lightpaths) -> str:
    return ", ".join(lightpath.label() for lightpath in lightpaths) or "-"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
