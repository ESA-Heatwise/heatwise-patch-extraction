cwlVersion: v1.2

$namespaces:
  s: https://schema.org/

s:softwareVersion: 0.1.1
s:version: 0.1.1

schemas:
  - http://schema.org/version/9.0/schemaorg-current-http.rdf

$graph:

  # -------------------------------------------------------------------------
  # Main EOAP Workflow
  # -------------------------------------------------------------------------
  - class: Workflow
    id: main
    label: HEATWISE Geo-Isolated Patch Extraction Workflow
    doc: |
      EOAP-compatible HEATWISE patch extraction workflow.

      The workflow extracts geographically isolated training, validation,
      and test patches from aligned Sentinel-2, hyperspectral, and optional
      LST/PCA raster products using polygon-based LCZ labels.

      EO raster inputs are provided through a staged STAC catalog directory.
      The processor generates an HDF5 patch dataset and an output STAC catalog
      describing the generated product.

    requirements: []

    inputs:

      - id: config
        type: File
        label: processing configuration
        doc: |
          YAML configuration controlling patch sampling, LCZ labels,
          spatial train/validation/test splitting, optional LST/PCA use,
          and other extraction parameters.

          EO raster paths are not provided through this configuration in the
          EOAP workflow; they are resolved from the input STAC catalog.

      - id: input_catalog
        type: Directory
        label: input STAC catalog
        doc: |
          Directory containing a STAC catalog named catalog.json referencing
          the staged Sentinel-2, hyperspectral, and optional LST/PCA input
          products required for patch extraction.

      - id: output_h5
        type: string
        label: output HDF5 filename
        default: patches.h5
        doc: |
          Path for the generated geographically isolated HDF5 patch dataset,
          relative to the CWL working directory.

    steps:

      processor:
        run: "#patch_extraction_processor"

        in:
          config: config
          input_catalog: input_catalog
          output_h5: output_h5

        out:
          - output

    outputs:

      output:
        type: Directory
        outputSource: processor/output


  # -------------------------------------------------------------------------
  # Patch extraction CommandLineTool
  # -------------------------------------------------------------------------
  - class: CommandLineTool
    id: patch_extraction_processor
    label: HEATWISE Geo-Isolated Patch Extraction Processor
    doc: |
      HEATWISE processor for geographically isolated patch extraction.

      The processor reads the EO raster products referenced by the staged
      STAC input catalog, combines them with the configured polygon labels,
      extracts aligned patches, performs the spatial hold-out split, and
      writes the resulting HDF5 dataset together with an output STAC catalog.

    requirements:

      DockerRequirement:
        dockerPull: ghcr.io/esa-heatwise/heatwise-patch-extraction:eoap-compliance

      InlineJavascriptRequirement: {}

    baseCommand: python

    arguments:
      - /app/processor.py

    inputs:

      config:
        type: File
        label: processing configuration
        doc: |
          YAML configuration controlling the patch extraction workflow,
          including label information, sampling parameters, spatial split
          parameters, and optional LST/PCA processing toggles.
        inputBinding:
          prefix: --config

      input_catalog:
        type: Directory
        label: input STAC catalog
        doc: |
          Directory containing catalog.json and the associated STAC Items
          and Assets for the staged Sentinel-2, hyperspectral, and optional
          LST/PCA EO products.

          The catalog.json path inside this directory is passed to the
          processor through the --input-catalog argument.
        inputBinding:
          prefix: --input-catalog
          valueFrom: $(self.path + "/catalog.json")

      output_h5:
        type: string
        label: output HDF5 filename
        default: patches.h5
        doc: |
          Path for the generated HDF5 patch dataset relative to the CWL
          working directory.
        inputBinding:
          prefix: --output-h5

    outputs:

      output:
        type: Directory
        doc: |
          Complete CWL working directory containing all files produced by
          the processor, including the HDF5 patch dataset and generated
          STAC catalog.
        outputBinding:
          glob: "."
