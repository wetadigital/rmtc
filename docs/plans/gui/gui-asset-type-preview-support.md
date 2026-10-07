# GUI Asset Type Preview Support

## Feature Description

Support asset-type-specific preview widgets throughout the GUI, particularly in the Junction ingestion tool and the Object Property editor. Currently, preview of ingested/tracked assets is limited to property-list displays with generic data layout. The feature would add rich, type-aware preview panels (image thumbnails, mesh viewports, tensor/table inline viewers, etc.) to give users immediate visual feedback on what they are ingesting or tracking before committing to the store.

## Criticality

High. The GUI is the user-facing entry point to RMTC; preview support directly improves usability and discovery during ingestion (Junction tool) and property inspection (central Property editor). Without it, users cannot visually verify asset correctness before tracking, and schema mismatches or corrupted assets may go unnoticed until training or inference fails downstream.

## T-Shirt Size

L. Requires adding 4–6 new widget classes for different asset types (image thumbnail, mesh, tensor table, camera, audio visualizer as a start), refactoring the common property-display layout to host dynamic preview panels (changes to `gui/common/properties.py` and `gui/common/widgets.py`), and coordinating with the Junction tool (`gui/ingestion/widgets.py`) to integrate preview on asset selection. Moderate complexity but spans multiple GUI modules and depends on understanding existing Qt/NodeGraphQt integration.

## How to Implement

1. **Define a preview interface** in `src/python/lib/rmtc/gui/common/preview.py` (file already exists; currently a stub):
   - Base class `AssetPreviewWidget(QWidget)` with abstract `set_asset(artifact)` and `clear()` methods.
   - Concrete subclasses: `ImagePreviewWidget` (QPixmap/QLabel thumbnail), `TensorPreviewWidget` (table display for numeric tensors), `MeshPreviewWidget` (basic wireframe or polygon-count summary), `CameraPreviewWidget` (intrinsics matrix + extrinsics summary), `AudioPreviewWidget` (placeholder for future).

2. **Extend the Object Property editor** (`gui/common/properties.py`):
   - Add a horizontal splitter to the existing property-list layout: left side remains property list, right side hosts the preview widget.
   - On entity selection, introspect artifact type (check `artifact.__class__.__name__` or `type_name` from Factory) and instantiate the appropriate preview widget.
   - Wire the preview to update whenever a property changes (listen to entity broadcasts; coordinate with existing `system/objects.py` notification patterns).

3. **Integrate into Junction ingestion** (`gui/ingestion/widgets.py`):
   - When a user selects or drags an asset onto a node in the DAG, show a preview panel next to or below the node properties.
   - Read the asset's URI, load it via the appropriate IO class (resolved from Factory), and display a thumbnail/summary before the user commits to ingestion.

4. **IO layer glue**:
   - Lean on existing IO classes (`rmtc.core.ops.io.*`) to read asset data on-demand for preview (e.g., `EXR` IO for images, `TensorJSONFile` for tensors).
   - Cache loaded tensor/mesh data in a `_preview_cache` dict on the preview widget to avoid re-reading on every repaint; clear cache on widget destruction.

5. **Registration**:
   - No module YAML registration needed (these are GUI-only, not trackable artifacts).
   - Add preview widget mappings in a simple dict: `PREVIEW_WIDGET_MAP = {"Image": ImagePreviewWidget, "Tensor": TensorPreviewWidget, ...}` in `preview.py`.

## Considerations

- **Blast radius**: Changes touch `gui/common/properties.py` (cited in critique.md's HACK list for Qt object deletion races; any layout changes must not regress that workaround at line 28).
- **Performance**: Loading large tensor/mesh assets into preview on every selection could be slow. Must implement loading in a background thread or defer to user triggering a "Load Preview" button.
- **Incomplete asset types**: RMTC's asset IO coverage is incomplete (critique.md notes OIIO only reads first subimage, ONNX IO is partially stubbed). Preview will gracefully fall back to a "Preview unavailable" label rather than crashing on unsupported types.
- **DCC integration**: USD camera assets (`USDCamera`, `USDCameraSequence` in `res/modules/rmtc_core.yaml`) have incomplete IO (camera framerate unimplemented per technical_notes.md). Preview of cameras should surface this limitation without breaking.
- **Integration with Junction node naming workaround**: Junction nodes are currently name-mangled to avoid NodeGraphQt clashes (critique.md HACK #2). Preview widgets should be keyed by node ID, not node name, to avoid similar collision issues.

---
SPDX-License-Identifier: Apache-2.0 - Copyright Contributors to the RMTC Project
