#!/usr/bin/env python3
import json
import sys
import io
import os
import argparse
import urllib.request
import zipfile
import csv
from collections import defaultdict


def gather_trafic_json(root_dir):
    """Walk `root_dir` and find all files named `trafic.json`.
    Returns tuple (agencies_dict, files_read).
    Supports files where the JSON is either a single company object or a list of companies.
    """
    agencies = defaultdict(set)
    files_read = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn == 'trafic.json':
                full = os.path.join(dirpath, fn)
                files_read.append(full)
                try:
                    with open(full, encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    print(f'Failed to load {full}: {e}')
                    continue

                def process_company(company):
                    aid = company.get('companyId')
                    if not aid:
                        return
                    for group in company.get('lines', []) or []:
                        for item in group:
                            if not isinstance(item, dict):
                                continue
                            lid = item.get('lineId')
                            if lid is None:
                                continue
                            lid_s = str(lid).strip()
                            if lid_s:
                                agencies[aid].add(lid_s)

                if isinstance(data, list):
                    for company in data:
                        if isinstance(company, dict):
                            process_company(company)
                elif isinstance(data, dict):
                    # Single company object
                    process_company(data)
                else:
                    print(f'Unexpected JSON structure in {full}, skipping')

    return agencies, files_read


def check_gtfs_for_agencies(agencies, timeout=30):
    errors = []
    total = len(agencies)
    idx = 0
    for aid, expected_line_ids in agencies.items():
        idx += 1
        if not expected_line_ids:
            print(f'[{idx}/{total}] Agency "{aid}": no lineIds to check, skipping')
            continue
        url = f'https://hexatransit.fr/datasets/gtfs/{aid}.zip'
        print(f'[{idx}/{total}] Checking GTFS for agency "{aid}" -> {url}')
        try:
            resp = urllib.request.urlopen(url, timeout=timeout)
            dataz = resp.read()
        except Exception as e:
            msg = f'Failed to download {url}: {e}'
            print('ERROR -', msg)
            errors.append(msg)
            continue

        try:
            z = zipfile.ZipFile(io.BytesIO(dataz))
        except Exception as e:
            msg = f'Invalid zip for {aid}: {e}'
            print('ERROR -', msg)
            errors.append(msg)
            continue

        namelist = z.namelist()
        rname = None
        for n in namelist:
            if n.endswith('routes.txt'):
                rname = n
                break
        if not rname:
            msg = f'No routes.txt in GTFS for {aid} (found files: {namelist[:10]})'
            print('ERROR -', msg)
            errors.append(msg)
            continue

        try:
            with z.open(rname) as rf:
                txt = io.TextIOWrapper(rf, encoding='utf-8', errors='replace')
                reader = csv.DictReader(txt)
                if reader.fieldnames:
                    reader.fieldnames = [fn.lstrip('\ufeff') for fn in reader.fieldnames]
                routes = list(reader)
        except Exception as e:
            msg = f'Failed to read routes.txt for {aid}: {e}'
            print('ERROR -', msg)
            errors.append(msg)
            continue

        route_ids = set()
        for r in routes:
            if isinstance(r, dict):
                rid = r.get('route_id')
                if rid is None:
                    continue
                rid_s = str(rid).strip()
                if rid_s:
                    route_ids.add(rid_s)

        expected_ids = set(str(x).strip() for x in expected_line_ids if x is not None and str(x).strip())
        missing = sorted([lid for lid in expected_ids if lid not in route_ids])
        if missing:
            msg = f'{len(missing)} missing line_id(s) not found in routes.txt: {missing[:20]}'
            print('ERROR -', msg)
            errors.append(f'Agency {aid}: {msg}')
        else:
            print(f'Agency {aid}: OK ({len(expected_line_ids)} line_ids matched)')

    return errors


def main():
    parser = argparse.ArgumentParser(description='Check GTFS routes for line IDs listed in trafic.json files under a logo directory.')
    parser.add_argument('--logo-dir', default='logo', help='Path to the logo directory to search (default: logo)')
    parser.add_argument('--timeout', type=int, default=30, help='Network timeout seconds when downloading GTFS (default: 30)')
    args = parser.parse_args()

    if not os.path.isdir(args.logo_dir):
        print(f'Logo directory "{args.logo_dir}" not found or is not a directory')
        sys.exit(1)

    agencies, files_read = gather_trafic_json(args.logo_dir)
    if not files_read:
        print(f'No trafic.json files found under "{args.logo_dir}"')
        sys.exit(1)

    print(f'Parsed {len(agencies)} company(ies) from {len(files_read)} file(s):')
    for p in files_read:
        print(' -', p)

    errors = check_gtfs_for_agencies(agencies, timeout=args.timeout)

    if errors:
        print('\nGTFS verification errors:')
        for e in errors:
            print(' -', e)
        sys.exit(1)
    else:
        print('\nAll GTFS checks passed.')


if __name__ == '__main__':
    main()
