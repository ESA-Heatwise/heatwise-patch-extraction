# heatwise-patch-extraction

Stage 2 of the HEATWISE LCZ pipeline: extracts aligned image patches from a
city's Sentinel-2, hyperspectral, and optional LST/PCA products using
polygon-based LCZ labels, and writes a single HDF5 dataset with spatially
separated train/validation/test subsets.

The processor supports EOAP-compatible STAC staging and stage-out. EO raster
inputs are supplied through a staged STAC catalog, while the generated HDF5
dataset is described by a STAC catalog written alongside the output product.

## Install

```bash
pip install -r requirements.txt
```

## Local execution

For local/non-Docker execution, the original configuration-based interface is
still supported:

```bash
python processor.py --config examples/sample_config.yaml
```

In this mode, `inputs.*` in the YAML configuration can directly reference the
Sentinel-2, HSI, and optional LST/PCA rasters.

For EOAP/Docker/CWL execution, EO raster paths are instead obtained from the
staged STAC input catalog through `--input-catalog`.

## Processing

For each city, the processor:

1. loads the polygon-based LCZ labels;
2. reads aligned Sentinel-2 and hyperspectral products, together with optional
   LST and PCA products;
3. grid-samples candidate points inside the labeled polygons;
4. extracts aligned image patches;
5. filters invalid, empty, out-of-bounds, and insufficient-overlap samples;
6. performs the geographically isolated train/validation/test split using the
   configured block and super-block strategy;
7. writes the resulting patch dataset to HDF5.

Classes for which full geographic isolation is not possible can use the
configured fallback strategy. The `geo_isolated` field in the HDF5 output
records whether each sample belongs to a fully spatially isolated split.

## HDF5 output

The generated HDF5 dataset contains:

- `sen2`, `hsi_bs`: patch stacks `(N, H, W, C)`
- `hsi_pca`: optional PCA patch stack `(N, H, W, C)`
- `lst`: optional LST patch stack
- `lst_valid`: per-patch LST validity flag
- `label`: one-hot labels `(N, num_classes)`, ordered according to
  `class_order`
- `split`: `0=train`, `1=val`, `2=test`
- `geo_isolated`: geographic-isolation flag
- `coords`: patch-center coordinates in the target CRS

For LST patches, `lst_valid=0` indicates that the original LST window included
nodata or an out-of-bounds region and required filling.

## EOAP STAC input

For EOAP execution, EO raster products are supplied as a CWL `Directory`
containing a STAC `catalog.json`, one or more STAC Items, and the referenced
assets.

The processor expects the relevant STAC Item to contain:

- `sentinel2`: required Sentinel-2 raster
- `hsi`: required hyperspectral raster
- `lst`: optional LST raster
- `pca`: optional PCA raster

Example structure:

```text
input_catalog/
├── catalog.json
├── Berlin_item.json
├── Berlin_S2.tif
├── Berlin_hsi_bs.tif
└── Berlin_lst_final.tif
```

The Item uses relative asset `href` values so that the complete directory can
be staged by a CWL runner.

The bundled Berlin sample follows this structure under:

```text
data/Berlin/
```

The processor receives the STAC catalog through:

```bash
--input-catalog /path/to/input_catalog/catalog.json
```

When `--input-catalog` is supplied, the EO raster paths obtained from STAC
replace `cfg["inputs"]` from the YAML configuration.

## Configuration

The EOAP/Docker example configuration is:

```text
examples/sample_config_docker.yaml
```

It controls processing parameters such as:

- city and target CRS;
- polygon labels and class mapping;
- sampling resolution and patch size;
- polygon-overlap thresholds;
- geographic split parameters;
- LST/PCA processing toggles.

EO raster paths are intentionally not included in this configuration because
they are supplied separately through the staged STAC catalog.

The bundled label shapefile remains a supporting resource in the sample Docker
image and is referenced through:

```yaml
labels:
  shp: /app/data/Berlin/Berlin_labels.shp
```

## Sample data

`data/Berlin/` contains the self-contained Berlin test bundle:

```text
Berlin_S2.tif
Berlin_hsi_bs.tif
Berlin_lst_final.tif

Berlin_labels.cpg
Berlin_labels.dbf
Berlin_labels.prj
Berlin_labels.shp
Berlin_labels.shx

catalog.json
Berlin_item.json
```

The raster products are referenced by the STAC Item, while the shapefile is
used as the polygon-based LCZ label source for the bundled example.

## STAC output

After generating the HDF5 dataset, the processor also writes a STAC catalog
describing the output product.

For example:

```text
Berlin_patches.h5
Berlin-patches_item.json
catalog.json
```

The STAC Item references the generated HDF5 file as the `patch_h5` asset and
includes the processor name and software version through the STAC Processing
extension.

## Docker

Build the versioned processor image with:

```bash
docker build \
  -t ghcr.io/heatwise-lcz/heatwise-patch-extraction:0.1.1 \
  .
```

The image uses `CMD` as its default command. When additional arguments are
supplied directly through `docker run`, invoke the processor explicitly:

```bash
mkdir -p output

docker run --rm \
  -v "$(pwd)/data/Berlin:/input:ro" \
  -v "$(pwd)/output:/output" \
  ghcr.io/heatwise-lcz/heatwise-patch-extraction:0.1.1 \
  python /app/processor.py \
  --config /app/examples/sample_config_docker.yaml \
  --input-catalog /input/catalog.json \
  --output-h5 /output/Berlin_patches.h5
```

This writes the HDF5 product and its STAC metadata to the mounted output
directory.

The image is based on `python:3.11-slim` and includes the GDAL system
dependencies required by the geospatial Python stack.

## EO Application Package / CWL

`heatwise_patch_extraction.cwl` is an EOAP-oriented CWL v1.2 Application
Package.

It contains:

- a top-level `Workflow` with `id: main`;
- a `CommandLineTool` implementing patch extraction;
- explicit `baseCommand` and processor arguments;
- a versioned `DockerRequirement`;
- documented CWL inputs;
- staged STAC input as a `Directory`;
- complete working-directory stage-out as a CWL `Directory`.

The workflow inputs are:

```text
config         File
input_catalog  Directory
output_h5      string
```

The `input_catalog` directory must contain:

```text
catalog.json
```

The CWL passes that catalog to the processor as:

```text
--input-catalog <staged-directory>/catalog.json
```

The processor command is defined explicitly by the `CommandLineTool` as:

```text
python /app/processor.py
```

The complete CWL working directory is exposed as the workflow output using:

```yaml
outputs:
  output:
    type: Directory
    outputBinding:
      glob: "."
```

This allows the generated HDF5 product, STAC Item, and `catalog.json` to be
collected together for EOAP stage-out.

## CWL example

The bundled example job is:

```text
examples/job.yaml
```

It stages `data/Berlin/` as the STAC input directory:

```yaml
config:
  class: File
  path: sample_config_docker.yaml

input_catalog:
  class: Directory
  path: ../data/Berlin

output_h5: Berlin_patches.h5
```

Run it from the `examples` directory with:

```bash
cd examples
cwltool ../heatwise_patch_extraction.cwl job.yaml
```

## Automated validation

The `eoap-compliance` branch includes a GitHub Actions workflow that validates
the complete Application Package.

The automated test performs:

- Python syntax checking;
- CWL validation with `cwltool`;
- input STAC validation with PySTAC;
- Docker image build;
- end-to-end execution of the bundled CWL example;
- output STAC validation with PySTAC;
- verification that an HDF5 product was generated.

The complete bundled Berlin example has been successfully executed through
this validation workflow.

## Relationship to the HEATWISE LCZ pipeline

This processor operates after `heatwise-hsi-lst-prep` and before
`heatwise-lcz-classification`.

Conceptually:

```text
heatwise-hsi-lst-prep
        ↓
heatwise-patch-extraction
        ↓
heatwise-lcz-classification
```

One patch-extraction run processes one city. HDF5 products from multiple
cities can subsequently be used by the LCZ classification stage for training
and evaluation.
