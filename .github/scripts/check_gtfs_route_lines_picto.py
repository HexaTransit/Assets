#!/usr/bin/env python3
import csv
import sys
import io
import os
import argparse
import urllib.request
import zipfile
from collections import defaultdict


def gather_lines_picto(root_dir):
    """Walk `root_dir` and find all files named `lines_picto.csv`.
    Return tuple (agencies_dict, list_of_files_read).
    """
    agencies = defaultdict(set)
    files_read = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn == 'lines_picto.csv':
                full = os.path.join(dirpath, fn)
                files_read.append(full)
                try:
                    with open(full, encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=';')
                        if reader.fieldnames:
                            reader.fieldnames = [x.lstrip('\ufeff') for x in reader.fieldnames]
                        for row in reader:
                            aid = row.get('agency_id')
                            lid = row.get('line_id')
                            if not aid or lid is None:
                                continue
                            lid_s = str(lid).strip()
                            if lid_s:
                                agencies[aid].add(lid_s)
                except Exception as e:
                    print(f'Failed to read {full}: {e}')
    return agencies, files_read


def check_gtfs_for_agencies(agencies, timeout=30):
    errors = []
    total_agencies = len(agencies)
    count = 0
    for agency, line_ids in agencies.items():
        count += 1
        url = f'https://hexatransit.fr/datasets/gtfs/{agency}.zip'
        print(f'[{count}/{total_agencies}] Checking GTFS for agency "{agency}" -> {url}')
        try:
            resp = urllib.request.urlopen(url, timeout=timeout)
            data = resp.read()
        except Exception as e:
            msg = f'Failed to download {url}: {e}'
            print(f'Agency {agency}: ERROR - {msg}')
            errors.append(msg)
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except Exception as e:
            msg = f'Invalid zip for {agency}: {e}'
            print(f'Agency {agency}: ERROR - {msg}')
            errors.append(msg)
            continue

        namelist = z.namelist()
        rname = None
        for n in namelist:
            if n.endswith('routes.txt'):
                rname = n
                break
        if not rname:
            msg = f'No routes.txt in GTFS for {agency} (found files: {namelist[:10]})'
            print(f'Agency {agency}: ERROR - {msg}')
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
            msg = f'Failed to read routes.txt for {agency}: {e}'
            print(f'Agency {agency}: ERROR - {msg}')
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

        csv_ids = set(str(x).strip() for x in line_ids if x is not None and str(x).strip())
        missing = sorted([lid for lid in csv_ids if lid not in route_ids])
        if missing:
            msg = f'{len(missing)} missing line_id(s) not found in routes.txt: {missing[:20]}'
            print(f'Agency {agency}: ERROR - {msg}')
            errors.append(f'Agency {agency}: {msg}')
        else:
            print(f'Agency {agency}: OK ({len(line_ids)} line_ids matched)')

    return errors


def main():
    parser = argparse.ArgumentParser(description='Check GTFS routes for line IDs listed in lines_picto.csv files under a logo directory.')
    parser.add_argument('--logo-dir', default='logo', help='Path to the logo directory to search (default: logo)')
    parser.add_argument('--timeout', type=int, default=30, help='Network timeout seconds when downloading GTFS (default: 30)')
    args = parser.parse_args()

    if not os.path.isdir(args.logo_dir):
        print(f'Logo directory "{args.logo_dir}" not found or is not a directory')
        sys.exit(1)

    agencies, files_read = gather_lines_picto(args.logo_dir)
    if not files_read:
        print(f'No lines_picto.csv files found under "{args.logo_dir}"')
        sys.exit(1)

    print(f'Parsed {len(agencies)} agency(ies) from {len(files_read)} file(s):')
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
