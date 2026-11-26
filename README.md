# Assets Repository

## Contributing

This repository contains graphic assets and data for HexaTransit.

### Repository Structure

- `lines_picto.csv`: CSV file listing line pictograms.
- `trafic.json`: Traffic data.
- `logo/`: Folders containing logos by network and mode (e.g., `fr-idf/metro/`, `fr-star/bus/`, etc.).
- `logo/<network>/transitous.json`: Transitous feeds publishing this network's lines.

### Transitous feeds

The app gets its data from [Transitous](https://transitous.org), where every
line is identified as `<feed>_<route_id>`. Each network folder declares its
feeds in `transitous.json`:

```json
{ "feeds": ["fr-reseau-urbain-STAR"] }
```

A feed id is `fr-` followed by the source `name` in
[transitous/feeds/fr.json](https://github.com/public-transport/transitous/blob/main/feeds/fr.json).
`lines_picto.php` then publishes each `line_id` once per feed, as
`<feed>_<line_id>`. The `line_id` in `lines_picto.csv` must be the `route_id`
of the feed's GTFS. To check (and fix unambiguous mismatches):

```
python .github/scripts/check_transitous_lines_picto.py --network fr-star --suggest
python .github/scripts/check_transitous_lines_picto.py --network fr-star --fix
```

### How to Contribute via Pull Request

1. **Fork** the repository and clone your fork locally.

2. **Create a branch** for your contribution:
   ```
   git checkout -b your-branch-name
   ```

3. **Add or modify** the necessary files, following the structure:
   - Place new logos in the correct subfolder (`logo/<network>/<mode>/`).
   - Update `lines_picto.csv` or `trafic.json` if needed.

4. **Respect the file formats**

5. **Add a clear description to your Pull Request:**
   - Explain the purpose of the contribution.
   - List the files/folders modified or added.
   - Mention any important points (e.g., format, copyright, etc.).

6. **Ensure your contribution does not delete existing files** (unless intentional and justified).

7. **Submit the Pull Request** to the `main` branch of the original repository.

#### Example Pull Request Description

```
### Add logos for Rennes Metro Line 5

- Added SVG files in `logo/fr-star/metro/`
- Updated `lines_picto.csv` to include line 5
- No existing files deleted
```

Thank you for contributing to HexaTransit assets!