#!/usr/bin/env python3

import argparse
import json
import sys

import networkx


def clean(x, graph_format):
    if graph_format == 'gml':
        return clean_gml(x)
    if graph_format == 'graphml':
        return clean_graphml(x)


def clean_gml(x):
    if isinstance(x, dict):
        x = {k: clean_gml(v) for k, v in x.items()}
        x = {k: v for k, v in x.items() if v is not None}
        x = {k: v for k, v in x.items() if k != 'abstract_inverted_index'}
        if len(x) > 0:
            return x
        else:
            return None
    elif isinstance(x, list):
        x = [clean_gml(v) for v in x]
        x = [v for v in x if v is not None]
        if len(x) > 0:
            return x
        else:
            return None
    else:
        return x


def clean_graphml(x, y=dict(), prefix=''):
    if isinstance(x, dict):
        for k, v in x.items():
            y = clean_graphml(v, y, f'{prefix}_{k}')
    elif isinstance(x, list):
        for i, v in enumerate(x):
            y = clean_graphml(v, y, f'{prefix}_{i}')
    elif x is not None:
        y[prefix[1:]] = x
    return y


def filter_metadata(w):
    metadata = ['id', 'publication_date', 'authorships', 'referenced_works']
    try:
        metadata += args.metadata
    except AttributeError:
        pass
    return {m: w[m] for m in metadata if m in w}


def graph_authors(works, graph_format, path):
    g = networkx.DiGraph()

    authors = {
        a['author']['id']: a['author']
        for w in works for a in w['authorships']
    }
    for i, a in authors.items():
        a['works'] = 0
        g.add_node(i, **clean(a, graph_format))

    works = {w['id']: {
        'publication_date': w['publication_date'],
        'authorships': [a['author'] for a in w['authorships']],
        'referenced_works': w['referenced_works']
    } for w in works}
    for w in sorted(works.values(), key=lambda x: x['publication_date']):
        for a in w['authorships']:
            for r in w['referenced_works']:
                if r not in works:
                    continue
                for b in works[r]['authorships']:
                    try:
                        g.edges[(a['id'], b['id'])]['num'] += 1
                    except KeyError:
                        g.add_edge(a['id'], b['id'], den=0, num=1)

    for w in sorted(works.values(), key=lambda x: x['publication_date']):
        for a in w['authorships']:
            for b in g.nodes():
                d = g.nodes[b]['works']
                try:
                    g.edges[(a['id'], b)]['den'] += d
                except KeyError:
                    continue
            g.nodes[a['id']]['works'] += 1

    for e in g.edges():
        e = g.edges[e]
        try:
            e['weight'] = float(e['num'])/float(e['den'])*100
        except ZeroDivisionError:
            e['weight'] = 0.0

    if graph_format == 'gml':
        networkx.write_gml(g, path)
    elif graph_format == 'graphml':
        networkx.write_graphml(g, path)


def graph_works(works, graph_format, node_metadata, path):
    g = networkx.DiGraph()

    for w in works:
        node_metadata = {m: w[m] for m in node_metadata if m in w}
        node_metadata = clean(node_metadata, graph_format)
        g.add_node(w['id'], **node_metadata)

    for w in works:
        for r in w['referenced_works']:
            if r not in g:
                continue
            if 'publication_date' in w:
                g.add_edge(w['id'], r, date=w['publication_date'])
            else:
                g.add_edge(w['id'], r)

    if graph_format == 'gml':
        networkx.write_gml(g, path)
    elif graph_format == 'graphml':
        networkx.write_graphml(g, path)


parent_parser = argparse.ArgumentParser(add_help=False)
parent_parser.add_argument(
    'works',
    type=argparse.FileType(), nargs='?', default=sys.stdin,
    help='JSONL file of OpenAlex works (default: standard input)'
)
parent_parser.add_argument(
    'output',
    type=argparse.FileType('wb'),
    help='file to output the graph'
)
parent_parser.add_argument(
    '-f', '--format',
    choices=['gml', 'graphml'], default='gml',
    help=(
        'graph format to output. '
        'GML format can store more metadata (default: gml)'
    )
)

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='cmd', required=True)
works_parser = subparsers.add_parser(
    'works',
    parents=[parent_parser],
    help='the nodes of the graph are the works'
)
works_parser.add_argument(
    '-m', '--metadata',
    nargs='*', default=[
        'title', 'publication_date', 'authorships', 'primary_location',
    ],
    help=(
        'metadata no include in the nodes '
        '(default: title, publication_date, authorships, primary_location)'
    )
)
authors_parser = subparsers.add_parser(
    'authors',
    parents=[parent_parser],
    help=(
        'the nodes of the graph are the authors. '
        'See the readme to understand the weight of the edges'
    )
)

args = parser.parse_args()
works = [
    filter_metadata(json.loads(j))
    for j in args.works.read().splitlines()
]
if args.cmd == 'works':
    graph_works(works, args.format, args.metadata, args.output)
elif args.cmd == 'authors':
    graph_authors(works, args.format, args.output)
