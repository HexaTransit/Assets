<?php
// Parcourt récursivement le dossier `logo/` et concatène tous les
// fichiers nommés `lines_picto.csv` en une seule sortie CSV.

// Définir le répertoire de base (par défaut : dossier `logo` à côté du script)
$baseDir = __DIR__ . DIRECTORY_SEPARATOR . 'logo';
if (php_sapi_name() === 'cli') {
    global $argv;
    if (isset($argv[1]) && $argv[1] !== '') {
        $baseDir = $argv[1];
    }
}

if (!is_dir($baseDir)) {
    $msg = "Directory not found: $baseDir\n";
    if (php_sapi_name() === 'cli') {
        fwrite(STDERR, $msg);
    } else {
        header('HTTP/1.1 500 Internal Server Error');
        echo $msg;
    }
    exit(2);
}

// If run from a web server, send CSV headers for download
if (php_sapi_name() !== 'cli') {
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="lines_picto.csv"');
}

$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($baseDir, RecursiveDirectoryIterator::SKIP_DOTS));
$firstHeaderPrinted = false;
$out = fopen('php://output', 'w');

foreach ($it as $file) {
    if (!$file->isFile()) continue;
    if (strtolower($file->getFilename()) !== 'lines_picto.csv') continue;

    $path = $file->getPathname();
    $handle = fopen($path, 'r');
    if (!$handle) continue;

    $header = fgetcsv($handle, 0, ';');
    if ($header === false) {
        fclose($handle);
        continue;
    }

    // Enlever BOM UTF-8 si présent sur la première cellule de l'en-tête
    if (isset($header[0])) {
        $header[0] = preg_replace('/^\xEF\xBB\xBF/', '', $header[0]);
    }

    if (!$firstHeaderPrinted) {
        fputcsv($out, $header, ';');
        $firstHeaderPrinted = true;
    }

    // Compatibilité avec des en-têtes `line_id` ou `lineId`
    $agencyIdIndex = array_search('agency_id', $header, true);
    $lineIdIndex = array_search('line_id', $header, true);
    if ($lineIdIndex === false) {
        $lineIdIndex = array_search('lineId', $header, true);
    }

    while (($row = fgetcsv($handle, 0, ';')) !== false) {
        if ($agencyIdIndex !== false && $lineIdIndex !== false && isset($row[$agencyIdIndex], $row[$lineIdIndex])) {
            $prefix = $row[$agencyIdIndex] . '_';
            if (strpos($row[$lineIdIndex], $prefix) !== 0) {
                $row[$lineIdIndex] = $prefix . $row[$lineIdIndex];
            }
        }

        fputcsv($out, $row, ';');
    }

    fclose($handle);
}

fclose($out);