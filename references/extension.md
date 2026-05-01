# ComfyUI Skill Extension Guide

Use this file when maintaining the skill or adding registered workflows. Runtime Agents should not execute arbitrary ComfyUI graphs; they should only use reviewed workflow registrations.

## Table of Contents

- [Adding a Workflow](#adding-a-workflow)
- [Analyzer Safety](#analyzer-safety)
- [Workflow Config Fields](#workflow-config-fields)
- [node_mapping Schema](#node_mapping-schema)
- [Review Checklist](#review-checklist)
- [Tests](#tests)

## Adding a Workflow

1. Place the exported ComfyUI workflow JSON in `assets/workflows/`.
2. Generate a review template:

   ```bash
   uv run --no-sync python scripts/analyze_workflow.py assets/workflows/new_workflow.json
   ```

3. Review `assets/workflows/new_workflow.config.template.json`.
4. Fill in `capability`, `description`, `node_mapping`, `output_kind`, and optional size metadata.
5. Remove `_discovered_nodes`; it is for review only.
6. Rename the reviewed template to `new_workflow.config.json`.
7. Run preflight:

   ```bash
   uv run --no-sync python -m comfyui generate --workflow new_workflow --preflight
   ```

8. Add/update tests if executor, CLI validation, config loading, or output handling changed.

The workflow becomes available only after a reviewed `*.config.json` exists under `assets/workflows/`.

## Analyzer Safety

`scripts/analyze_workflow.py` is a maintainer helper, not an activation tool. By default it writes:

```text
assets/workflows/<workflow>.config.template.json
```

This avoids auto-registering heuristic analyzer output. Use `--force` only when you intentionally want to overwrite or activate a `*.config.json` directly.

Never treat analyzer output as reviewed. It guesses node roles from workflow structure and names; human review is required before activation.

## Workflow Config Fields

Common top-level fields:

| Field | Purpose |
|-------|---------|
| `workflow_id` | Stable id used by `--workflow` |
| `workflow_file` | Workflow JSON path/name under `assets/workflows/` |
| `capability` | Agent-facing capability such as `text_to_image`, `image_to_video`, `text_to_speech` |
| `description` | Short human/Agent summary |
| `node_mapping` | Role-to-node mapping used by executor |
| `size_strategy` | Optional. `workflow_managed` means executor/CLI should not apply mapped width/height |
| `output_kind` | `image`, `audio`, or `video` |
| `resolution_presets` | Optional Agent-facing named `{width,height,label}` choices |
| `default_resolution` | Optional key into `resolution_presets` |

`output_kind: "video"` should be used for video workflows even when Comfy history exposes files under `gifs`; the executor checks `images`, `gifs`, and `videos`.

## node_mapping Schema

Each workflow config uses a `node_mapping` dictionary. Keys are logical role names used by CLI and executor.

Example:

```json
{
  "prompt": {
    "node_title": "CLIP Text Encode (Positive Prompt)",
    "param": "text",
    "value_type": "string",
    "required": true
  },
  "negative_prompt": {
    "node_title": "CLIP Text Encode (Negative Prompt)",
    "param": "text",
    "value_type": "string"
  },
  "seed": {
    "node_title": "KSampler",
    "param": "seed",
    "value_type": "integer",
    "auto_random": true
  },
  "width": {
    "node_title": "EmptySD3LatentImage",
    "param": "width",
    "value_type": "integer",
    "default": 832
  },
  "height": {
    "node_title": "EmptySD3LatentImage",
    "param": "height",
    "value_type": "integer",
    "default": 1280
  },
  "input_image": {
    "node_title": "Load Image",
    "param": "image",
    "value_type": "image",
    "input_strategy": "upload",
    "required": true
  }
}
```

Mapping entry fields:

| Field | Meaning |
|-------|---------|
| `node_title` | Exact title/name used to find the workflow node |
| `param` | Node input/widget parameter to write |
| `value_type` | `string`, `integer`, or `image` |
| `input_strategy` | `upload` for files sent to ComfyUI, `direct` for literal values |
| `required` | Whether the role must be provided |
| `auto_random` | Generate a random value, typically for seed |
| `default` | Default value when CLI does not override |

For image roles, the mapping key is the CLI role. `"input_image"` means:

```bash
uv run --no-sync python -m comfyui generate --workflow some_workflow --image input_image=photo.png -p "..."
```

`input_strategy: "upload"` uploads the local file to ComfyUI first and writes the returned `subfolder/name` value into the workflow. `input_strategy: "direct"` writes the literal value directly.

## Review Checklist

- The workflow id is stable and matches file/config naming.
- `capability` matches the user-facing behavior.
- Required prompt/text/image roles are marked `required`.
- `width` and `height` are both present or both absent.
- `size_strategy: "workflow_managed"` is set when workflow internals control dimensions.
- `output_kind` matches the media that should be fetched.
- `resolution_presets` are only guidance and do not imply extra CLI flags.
- Custom nodes and model names are documented in [workflow_nodes.md](workflow_nodes.md) when needed.
- `--preflight` passes against the intended ComfyUI server before advertising the workflow in `SKILL.md`.
- Tests cover any new validation branch or output kind behavior.

## Tests

Run the full test suite before committing maintenance changes:

```powershell
$env:PYTHONPATH="E:\CC\comfyui\scripts"; python -m pytest -q scripts/tests
```

Focused tests:

```powershell
$env:PYTHONPATH="E:\CC\comfyui\scripts"; python -m pytest -q scripts/tests/test_workflow_config.py scripts/tests/test_executor.py scripts/tests/test_cli.py
```
