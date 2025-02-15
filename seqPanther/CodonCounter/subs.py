#!/usr/bin/env python

import pandas as pd
import numpy as np

from .codon_table import codon_table
from copy import deepcopy
from Bio import Seq


def sub_table(coordinates_with_changes, params):
    sequences = params["sequences"]
    rid = params["rid"]
    sample = params["sample"]
    alt_codon_frac = params["alt_codon_frac"]
    alt_nuc_frac = params["alt_nuc_count"]

    gff_data = params["gff_data"]
    min_seq_depth = params["min_seq_depth"]
    keys = set(coordinates_with_changes)
    coordinates_with_change_cds = {}

    for (
            _,
            row,
    ) in gff_data.iterrows():  # TODO: Change it to itertuple for large gff
        selected_coordinates = keys & set(range(row["start"], row["end"] + 2))
        for selected_coordinate in selected_coordinates:
            coordinates_with_change = deepcopy(
                coordinates_with_changes[selected_coordinate])
            coordinates_with_change["start"] = row["start"]
            coordinates_with_change["end"] = row["end"]
            coordinates_with_change["strand"] = row["strand"]
            shift = (selected_coordinate - row["start"]) % 3
            ref_base = sequences[selected_coordinate].seq
            ref_codon = sequences[selected_coordinate -
                                  shift:selected_coordinate - shift +
                                  3].seq.upper()
            ref_codon_count = 0
            total_codon_count = 0
            codon_counts = {}
            bases = coordinates_with_change["bases"]

            for base in bases:

                codons = bases[base]["codon_count"]
                local_codons = {}

                for extended_codon in codons:
                    codon = extended_codon[2 - shift:5 - shift]
                    if ('-' in codon) or ('N' in codon):
                        continue
                    if codon not in local_codons:
                        local_codons[codon] = codons[extended_codon]
                    else:
                        local_codons[codon] += codons[extended_codon]
                    if codon not in codon_counts:
                        codon_counts[codon] = 0
                    codon_counts[codon] += codons[extended_codon]
                total_codon_count += sum(local_codons.values())
                try:
                    ref_codon_count += local_codons[ref_codon]
                except KeyError:
                    pass
                coordinates_with_change["bases"][base][
                    "codon_count"] = local_codons

            # NOTE: Removing less less common codons
            coordinates_with_change["total_codon_count"] = total_codon_count

            codons_to_delete = []
            for codon in codon_counts.keys():
                if codon_counts[codon] / total_codon_count < alt_codon_frac:
                    codons_to_delete.append(codon)

            for base in bases:
                for codon in codons_to_delete:
                    try:
                        del coordinates_with_change["bases"][base][
                            "codon_count"][codon]
                    except KeyError:
                        pass

            # NOTE: Reverse complement
            if row["strand"] == "-":
                ref_codon = str(Seq.Seq(ref_codon).reverse_complement())
                ref_base = str(Seq.Seq(ref_base).reverse_complement())
                for k in coordinates_with_change["bases"]:
                    # NOTE: base need to be reverse complemented

                    codon_count = coordinates_with_change["bases"][k][
                        "codon_count"]
                    new_codon_count = {}
                    for codon in codon_count:
                        new_codon_count[str(
                            Seq.Seq(codon).reverse_complement()
                        )] = codon_count[codon]

                    coordinates_with_change["bases"][k][
                        "codon_count"] = new_codon_count
                new_base = {}
                for k in coordinates_with_change["bases"]:
                    new_base[str(Seq.Seq(k).reverse_complement()
                                 )] = coordinates_with_change["bases"][k]
                coordinates_with_change["bases"] = new_base
            coordinates_with_change["ref_codon"] = ref_codon
            coordinates_with_change["ref_codon_count"] = ref_codon_count
            coordinates_with_change["codon_pos"] = (selected_coordinate -
                                                    shift)
            coordinates_with_change["ref_base"] = ref_base

            if row["strand"] == "+":

                amino_pos = (selected_coordinate - row["start"]) // 3 + 1

            else:
                amino_pos = (row["end"] - selected_coordinate) // 3 + 1

            coordinates_with_change["amino_pos"] = amino_pos
            coordinates_with_change_cds[(
                selected_coordinate, row['start'], row['end'],
                row['strand'])] = coordinates_with_change

    # NOTE: Fix below
    final_table = {
        "Amino Acid Change": [],
        "Nucleotide Change": [],
        "Codon Change": [],
        "alt_codon": [],
        "alt": [],
        "total": [],
        "coor": [],
        "coor_full": [],
        "gene_range": [],
        "ref_codon": [],
        "ref_codon_count": [],
    }
    sub_nuc_dist = {
        'coor': [],
        'ref': [],
        'depth': [],
        'nucs': [],
        'nucs_count': []
    }
    # coors_to_delete = []
    for coor in coordinates_with_change_cds:
        if 'ref_base' not in coordinates_with_change_cds[coor]:
            # coors_to_delete.append(coor)
            continue
        bases = coordinates_with_change_cds[coor]["bases"]
        nucs = []
        nucs_count = []
        for base in bases:
            if bases[base]["nuc_count"] > coordinates_with_change_cds[coor][
                    'read_count'] * alt_nuc_frac:
                nucs.append(base)
                nucs_count.append(bases[base]["nuc_count"])
            if base == coordinates_with_change_cds[coor]["ref_base"]:
                continue

            codon_counts = bases[base]["codon_count"]
            # coordinates_with_change_cds[coor])
            for codon in codon_counts:
                final_table["Amino Acid Change"].append(
                    f"""{codon_table[coordinates_with_change_cds[coor]['ref_codon']
                        ]}{coordinates_with_change_cds[coor
                            ]['amino_pos']}{codon_table[codon]}"""
                )  # TODO: Correct amino acid position
                final_table["Nucleotide Change"].append(
                    f'{coor[0]+1}:{coordinates_with_change_cds[coor]["ref_base"]}>{base}'
                )
                final_table["Codon Change"].append(
                    f"""{coordinates_with_change_cds[coor]["codon_pos"
                        ]+1}:{coordinates_with_change_cds[coor
                            ]["ref_codon"]}>{codon}"""
                )  # TODO: Correct codon position if it is incorrect
                final_table["alt_codon"].append(codon)
                final_table["alt"].append(codon_counts[codon])
                final_table["total"].append(
                    coordinates_with_change_cds[coor]["total_codon_count"])
                final_table["coor"].append(
                    coor[0])  # NOTE: Required later, but also removed
                final_table["coor_full"].append(coor)
                final_table["gene_range"].append(
                    f"{coor[1]}:{coor[2]}({coor[3]})")
                final_table["ref_codon"].append(
                    coordinates_with_change_cds[coor]["ref_codon"])
                final_table["ref_codon_count"].append(
                    coordinates_with_change_cds[coor]["ref_codon_count"])
        if coor[0] not in sub_nuc_dist['coor']:
            sub_nuc_dist["coor"].append(coor[0])
            sub_nuc_dist["ref"].append(
                coordinates_with_change_cds[coor]["ref_base"])
            sub_nuc_dist["depth"].append(
                coordinates_with_change_cds[coor]["read_count"])
            sub_nuc_dist["nucs"].append(nucs)
            sub_nuc_dist["nucs_count"].append(nucs_count)

    final_table = pd.DataFrame(final_table)
    final_table = final_table[final_table["total"] >= min_seq_depth]
    if not final_table.empty:

        final_table["codon_count"] = final_table.apply(
            lambda x: f"""{x['ref_codon']}-{x['ref_codon_count']};{
                x['alt_codon']
         }-{x['alt']}""",
            axis=1,
        )
        final_table["codon_percent"] = final_table.apply(
            lambda x:
            f"""{x['ref_codon']}-{f'%.2f' % (x['ref_codon_count']*100./coordinates_with_change_cds[x['coor_full']]['total_codon_count'])};{
                x['alt_codon']
         }-{f'%.2f'% (x['alt']*100./coordinates_with_change_cds[x['coor_full']]['total_codon_count'])}""",
            axis=1,
        )
        # all_codon_count = final_table[]
    final_table = final_table.drop(
        [
            "ref_codon",
            "ref_codon_count",
            "alt_codon",
            "coor_full",
            "alt",
            "coor",
            "total",
        ],
        axis=1,
    )
    sub_nuc_dist = pd.DataFrame(sub_nuc_dist)
    sub_nuc_dist["Nucleotide Frequency"] = sub_nuc_dist.apply(
        lambda x: ','.join(
            [f'{n}:{c}' for n, c in zip(x['nucs'], x['nucs_count'])]),
        axis=1)
    sub_nuc_dist["Nucleotide Percent"] = sub_nuc_dist.apply(
        lambda x: ','.join([
            f"{n}:{'%0.2f' % c}"
            for n, c in zip(x['nucs'],
                            np.array(x['nucs_count']) * 100 / x['depth'])
        ]),
        axis=1)
    sub_nuc_dist = sub_nuc_dist.drop(
        ["nucs", "nucs_count"], axis=1).rename(columns={
            'depth': 'read_count',
            'ref': 'Reference Nucleotide'
        })
    sub_nuc_dist.insert(0, 'Reference ID', rid)
    sub_nuc_dist.insert(0, 'Sample', sample)
    sub_nuc_dist['coor'] += 1
    final_table.insert(0, 'Reference ID', rid)
    final_table.insert(0, 'Sample', sample)
    return final_table, sub_nuc_dist
