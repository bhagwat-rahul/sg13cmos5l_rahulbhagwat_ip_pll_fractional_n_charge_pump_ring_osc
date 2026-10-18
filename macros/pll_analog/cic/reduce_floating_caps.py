#!/usr/bin/env python3
"""Eliminate only internal capacitor-only nodes by an exact Schur complement.

Retain every subcircuit port and device terminal, all compact models and all
device parameters. Floating metal is not grounded. This preserves the linear
capacitive multiport for zero initial floating charge, to numerical precision;
it is not parasitic extraction or a replacement for LVS. Resistive networks
are deliberately unsupported. Run on KPEX CC output, not RC output.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import splu


def reduce_cell(name, ports, body):
    retained = set(ports) | {'0'}
    caps, devices = [], []
    for line in body.splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('*'):
            continue
        if fields[0][0].lower() == 'x':
            model = next((i - 1 for i, f in enumerate(fields) if '=' in f), len(fields) - 1)
            retained.update(fields[1:model])
            devices.append(line)
        elif fields[0][0].lower() == 'c' and len(fields) == 4:
            number = re.fullmatch(r'([+\-\d.eE]+)([fpnum]?)', fields[3], re.I)
            if not number:
                raise ValueError(f'{name}: unsupported capacitance units: {line}')
            value = float(number[1]) * {'f': 1., 'p': 1e3, 'n': 1e6,
                                       'u': 1e9, 'm': 1e12, '': 1e15}[number[2].lower()]
            if not np.isfinite(value) or value < 0:
                raise ValueError(f'{name}: invalid capacitance: {line}')
            caps.append((fields[1], fields[2], value))
        else:
            raise ValueError(f'{name}: unsupported line (CC/X-only input required): {line}')
    nodes = sorted(retained | {n for a, b, _ in caps for n in (a, b)})
    ids = {n: i for i, n in enumerate(nodes)}
    entries = defaultdict(float)
    for a, b, value in caps:
        i, j = ids[a], ids[b]
        if i != j:
            entries[i, i] += value
            entries[j, j] += value
            entries[i, j] -= value
            entries[j, i] -= value
    rows, columns, values = zip(*((i, j, v) for (i, j), v in entries.items())) if entries else ([], [], [])
    matrix = coo_matrix((values, (rows, columns)), shape=(len(nodes), len(nodes))).tocsc()
    _, components = connected_components(matrix, directed=False)
    keep = np.array([ids[n] for n in nodes if n in retained], dtype=int)
    anchored = set(components[keep])
    floating = np.array([i for i, n in enumerate(nodes) if n not in retained and components[i] in anchored], dtype=int)
    disconnected = [n for i, n in enumerate(nodes) if components[i] not in anchored]
    effective = matrix[keep][:, keep].toarray()
    residual = 0.
    if len(floating):
        cff = matrix[floating][:, floating]
        cfk = matrix[floating][:, keep].toarray()
        solved = splu(cff).solve(cfk)
        residual = float(np.max(np.abs(cff @ solved - cfk)))
        effective -= matrix[keep][:, floating] @ solved
    scale = max(float(np.max(np.abs(effective))), 1.)
    symmetry_error = float(np.max(np.abs(effective - effective.T)))
    row_error = float(np.max(np.abs(effective.sum(axis=1))))
    if max(residual, symmetry_error, row_error) > scale * 1e-10:
        raise ValueError(f'{name}: capacitance conservation/numerical audit failed')
    effective = (effective + effective.T) / 2
    names = [nodes[i] for i in keep]
    lines, reconstructed = [], np.zeros_like(effective)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            value = -effective[i, j]
            if value < -scale * 1e-10:
                raise ValueError(f'{name}: nonpassive reduced capacitance')
            if value <= 0:  # Zero or bounded floating-point roundoff only.
                continue
            lines.append(f'Creduced_{len(lines) + 1} {names[i]} {names[j]} {value:.16g}f')
            reconstructed[i, i] += value
            reconstructed[j, j] += value
            reconstructed[i, j] -= value
            reconstructed[j, i] -= value
    reconstruction_error = float(np.max(np.abs(reconstructed - effective)))
    if reconstruction_error > scale * 1e-10:
        raise ValueError(f'{name}: emitted capacitor matrix changed the multiport')
    report = dict(cell=name, input_caps=len(caps), output_caps=len(lines),
                  retained_nodes=names, eliminated_nodes=len(floating),
                  disconnected_cap_only_nodes=len(disconnected),
                  kcl_residual_fF=residual, symmetry_error_fF=symmetry_error,
                  row_sum_error_fF=row_error, reconstruction_error_fF=reconstruction_error)
    return '\n'.join(devices + lines) + '\n', report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    text = args.input.read_text()
    text = re.sub(r'\n\s*\+', ' ', text)
    reports = []
    def replace(match):
        name, ports, body = match.groups()
        reduced, report = reduce_cell(name, ports.split(), body)
        reports.append(report)
        return f'.subckt {name} {ports}\n{reduced}.ends {name}\n'
    reduced = re.sub(r'^\.subckt\s+(\S+)\s+([^\n]+)\n(.*?)^\.ends\b[^\n]*\n?',
                     replace, text, flags=re.I | re.M | re.S)
    if not reports:
        raise ValueError('no subcircuits found')
    # Do not overwrite an extraction or a previous experiment.
    with args.output.open('x') as stream:
        stream.write('* Exact elimination of internal capacitor-only nodes; zero initial floating charge.\n' + reduced)
    report = {'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'limitations': __doc__, 'cells': reports}
    args.output.with_suffix('.reduction.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
