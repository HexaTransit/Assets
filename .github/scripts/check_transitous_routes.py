#!/usr/bin/env python3
"""Vérifie que les identifiants de lignes des fichiers `lines_picto.csv`
(`line_id`) et `trafic.json` (`lineId`) existent dans les flux Transitous
déclarés par chaque réseau (`logo/<réseau>/transitous.json`).

Les identifiants Transitous sont de la forme `<flux>_<route_id GTFS>`, où
`<flux>` vaut `fr-` + le nom de la source dans
https://github.com/public-transport/transitous/blob/main/feeds/fr.json.
Ce script télécharge le GTFS source de chaque flux (URL lue dans fr.json) et
contrôle que chaque identifiant est un `route_id` d'au moins un des flux.
Les alertes GTFS-RT (trafic.json) utilisent les route_id de ce même GTFS
source.

Options :
  --network fr-star   ne vérifie qu'un réseau (répétable)
  --suggest           propose un route_id pour les lignes introuvables, en
                      comparant le nom de ligne au `route_short_name` du GTFS
  --fix               remplace les identifiants introuvables qui n'ont qu'une
                      seule proposition (implique --suggest)
  --strict            échoue aussi sur les avertissements (lignes introuvables,
                      réseau sans transitous.json, GTFS source indisponible)

Par défaut, seul un flux déclaré mais inconnu de Transitous fait échouer le
script ; le reste est signalé en avertissement.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict

FEEDS_URL = 'https://raw.githubusercontent.com/public-transport/transitous/main/feeds/{region}.json'
HEADERS = {
    'User-Agent': 'HexaTransit-Assets-CI (+https://hexatransit.fr)',
    'Accept': 'application/zip,application/octet-stream,*/*;q=0.8',
}


def http_get(url, timeout):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def load_feed_urls(regions, timeout):
    """Nom de flux Transitous (`fr-xxx`) -> URL du GTFS statique."""
    urls = {}
    for region in sorted(regions):
        data = json.loads(http_get(FEEDS_URL.format(region=region), timeout))
        for src in data.get('sources', []):
            if src.get('spec', 'gtfs') != 'gtfs' or src.get('type') not in ('http', 'url'):
                continue
            name = src.get('name')
            if not name:
                continue
            key = f'{region}-{name}'
            # Une source "skip" n'est pas importée par Transitous
            if key not in urls or (src.get('skip') is not True and urls[key][1]):
                urls[key] = (src.get('url'), src.get('skip') is True)
    return {k: v[0] for k, v in urls.items() if not v[1]}


def read_routes(gtfs_bytes):
    z = zipfile.ZipFile(io.BytesIO(gtfs_bytes))
    name = next((n for n in z.namelist() if n.endswith('routes.txt')), None)
    if not name:
        raise ValueError('routes.txt absent')
    with z.open(name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig', errors='replace'))
        return [{k.strip(): (v or '').strip() for k, v in row.items() if k} for row in reader]


# ---------------------------------------------------------------------------
# Lecture / correction des fichiers du dépôt
# ---------------------------------------------------------------------------

def read_csv_lines(csv_path):
    with open(csv_path, encoding='utf-8-sig') as f:
        rows = csv.DictReader(f, delimiter=';')
        return [
            {'line_id': r['line_id'].strip(),
             'name': (r.get('lineName') or r.get('line_name') or '').strip()}
            for r in rows if (r.get('line_id') or '').strip()
        ]


def fix_csv(csv_path, replacements):
    """Remplace des line_id dans le CSV en conservant le style de guillemets."""
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        lines = f.read().splitlines()
    header = next(csv.reader([lines[0]], delimiter=';'))
    idx = [h.lstrip('﻿') for h in header].index('line_id')
    out = [lines[0]]
    for line in lines[1:]:
        row = next(csv.reader([line], delimiter=';'), [])
        if len(row) > idx and row[idx].strip() in replacements:
            row[idx] = replacements[row[idx].strip()]
            buf = io.StringIO()
            quoting = csv.QUOTE_ALL if line.startswith('"') else csv.QUOTE_MINIMAL
            csv.writer(buf, delimiter=';', quoting=quoting, lineterminator='').writerow(row)
            line = buf.getvalue()
        out.append(line)
    with open(csv_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')


def read_trafic_lines(json_path):
    with open(json_path, encoding='utf-8-sig') as f:
        data = json.load(f)
    rows = []
    for company in data if isinstance(data, list) else [data]:
        for group in company.get('lines', []):
            for item in group if isinstance(group, list) else [group]:
                if isinstance(item, dict) and str(item.get('lineId') or '').strip():
                    rows.append({'line_id': str(item['lineId']).strip(),
                                 'name': str(item.get('lineName') or '').strip()})
    return rows


def fix_trafic_json(json_path, replacements):
    """Remplace des lineId dans trafic.json sans reformater le fichier."""
    with open(json_path, encoding='utf-8-sig', newline='') as f:
        text = f.read()
    for old, new in replacements.items():
        pattern = r'("lineId"\s*:\s*)' + re.escape(json.dumps(old, ensure_ascii=False))
        text = re.sub(pattern, lambda m: m.group(1) + json.dumps(new, ensure_ascii=False), text)
    with open(json_path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def read_networks(logo_dir, only):
    """réseau -> (flux, [(fichier, lignes, fonction de correction)])"""
    networks = {}
    for net in sorted(os.listdir(logo_dir)):
        if only and net not in only:
            continue
        folder = os.path.join(logo_dir, net)
        sources = []
        for filename, reader, fixer in (
            ('lines_picto.csv', read_csv_lines, fix_csv),
            ('trafic.json', read_trafic_lines, fix_trafic_json),
        ):
            path = os.path.join(folder, filename)
            if os.path.isfile(path):
                rows = reader(path)
                if rows:
                    sources.append((path, rows, fixer))
        if not sources:
            continue
        feeds = []
        cfg_path = os.path.join(folder, 'transitous.json')
        if os.path.isfile(cfg_path):
            with open(cfg_path, encoding='utf-8') as f:
                feeds = json.load(f).get('feeds', [])
        networks[net] = (feeds, sources)
    return networks


def _tokens(identifier):
    return re.split(r'[-:]', identifier)


def suggest(row, route_ids, by_short_name):
    """route_id candidats pour une ligne introuvable, d'après :
    - un route_id contenant l'ancien identifiant
      ("1004440" -> "ATOUMOD040:Line:1004440:LOC") ;
    - un route_id ne différant que par son préfixe de version
      ("6-1001" -> "7-1001") ;
    - le nom court de la ligne ("C1", ou "Métro A" -> "A").
    On garde l'intersection quand elle départage les candidats."""
    old = row['line_id']
    old_tokens = _tokens(old)
    by_token = {rid for rid in route_ids if old in _tokens(rid)}
    if not by_token and len(old_tokens) > 1:
        by_token = {rid for rid in route_ids
                    if len(_tokens(rid)) == len(old_tokens)
                    and _tokens(rid)[1:] == old_tokens[1:]}
    name = row['name'].lower()
    by_name = by_short_name.get(name, set()) or by_short_name.get(name.split(' ')[-1], set())
    if by_token and by_name and len(by_token & by_name) == 1:
        return sorted(by_token & by_name)
    return sorted(by_token if len(by_token) == 1 or not by_name else by_name)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--logo-dir', default='logo')
    parser.add_argument('--network', action='append', default=[])
    parser.add_argument('--suggest', action='store_true')
    parser.add_argument('--fix', action='store_true')
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()

    networks = read_networks(args.logo_dir, set(args.network))
    errors = []
    warnings = []

    def warn(msg):
        print('WARNING -', msg)
        warnings.append(msg)

    regions = {feed.split('-', 1)[0] for feeds, _ in networks.values() for feed in feeds}
    feed_urls = load_feed_urls(regions, args.timeout) if regions else {}

    routes_cache = {}
    for net, (feeds, sources) in networks.items():
        if not feeds:
            warn(f'{net}: pas de transitous.json (ou liste "feeds" vide)')
            continue

        routes = []
        for feed in feeds:
            if feed not in routes_cache:
                url = feed_urls.get(feed)
                if not url:
                    routes_cache[feed] = None
                    msg = f'{net}: flux "{feed}" introuvable (ou ignoré) dans Transitous'
                    print('ERROR -', msg)
                    errors.append(msg)
                    continue
                print(f'{net}: téléchargement de {feed} ({url})')
                try:
                    routes_cache[feed] = read_routes(http_get(url, args.timeout))
                except Exception as e:  # noqa: BLE001
                    routes_cache[feed] = None
                    warn(f'{net}: échec du GTFS de {feed}: {e}')
            if routes_cache.get(feed):
                routes.extend(routes_cache[feed])

        if not routes:
            continue

        route_ids = {r.get('route_id', '') for r in routes}
        by_short_name = defaultdict(set)
        for r in routes:
            by_short_name[r.get('route_short_name', '').lower()].add(r.get('route_id', ''))

        for path, rows, fixer in sources:
            label = f'{net}/{os.path.basename(path)}'
            missing = [r for r in rows if r['line_id'] not in route_ids]
            if not missing:
                print(f'{label}: OK ({len(rows)} lignes)')
                continue

            replacements = {}
            if args.suggest or args.fix:
                for r in missing:
                    candidates = suggest(r, route_ids, by_short_name)
                    print(f'    {r["line_id"]!r} ({r["name"]}) -> {candidates or "?"}')
                    if len(candidates) == 1:
                        replacements[r['line_id']] = candidates[0]
            if args.fix and replacements:
                fixer(path, replacements)
                print(f'{label}: {len(replacements)} identifiant(s) corrigé(s)')
                missing = [r for r in missing if r['line_id'] not in replacements]
                if not missing:
                    continue

            warn(f'{label}: {len(missing)} identifiant(s) introuvable(s): '
                 f'{[r["line_id"] for r in missing][:20]}')

    print(f'\n{len(errors)} erreur(s), {len(warnings)} avertissement(s).')
    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == '__main__':
    main()
