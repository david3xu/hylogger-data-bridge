# Data handling

The demonstrated case uses `SWMB007s_chips.zip` from the WA NVCL catalogue. Model preparation used 19 frozen packages; the [training guide](../developer/docs/training.md#r1-real-data-pilot) records the preparation, labels and evaluation. No raw package is committed or included in the installer.

The owner confirmed that the organiser's HyLogger datasets are the source for the core decision-model work. See [model design](../developer/docs/design.md#local-decision-model) for constructing supervised investigation decisions from actual scientific results. Do not substitute fabricated workflow fixtures or assume geological/assay records already contain next-action labels.

Keep downloaded packages, drillcore images and local caches under ignored subfolders such as `data/raw/` and `data/cache/`. Only this README is tracked under `data/`. Do not force-add ignored files.

Official entry points:

- [WA NVCL catalogue](https://thredds.nci.org.au/thredds/catalog/rs07/WA/catalog.html)
- [DASC](https://dasc.dmirs.wa.gov.au/) — search for HyLogger Drillhole Package
- [GSWA data FAQ](https://github.com/Geological-Survey-of-Western-Australia/gswa-hackathon-2026/discussions/1)
- [pytsg](https://github.com/Geological-Survey-of-Western-Australia/pytsg) — implemented TSG reader behind the [scientific adapter](../developer/docs/design.md#tsg-ingestion-with-pytsg); keep package-level validation and provenance with each new adapter use

For each additional package, record its hole identifier, exact download URL, retrieval time, licence, file sizes/hashes and processing level before analysis. Record missing fields and unknown units explicitly. Do not invent a common schema before inspecting the files.

The FAQ identifies an interim SQLite package and `hylogger_dataset_index` as the link from NVCL hole names to associated drilling references. Do not download the full collection or repeatedly retry failing services during preparation. Select one manageable hole with suitable evidence.

Small derived outputs may be included only after provenance, privacy and source terms are checked. Raw packages remain excluded even when their licences permit some reuse: the organisers expressly ask that they not be committed.
