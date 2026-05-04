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

This repo supports two paths:

- User path: import a workflow you already validated in ComfyUI, then register it as a capability.
- Maintainer path: same mechanics, but you also update docs/tests and keep the shipped workflow registry consistent.

### User Path (Recommended)

1. Export a working workflow from ComfyUI as API-format JSON.
2. Import it (writes the workflow JSON + a reviewed template):

   ```bash
   uv run --no-sync python -m comfyui import-workflow path/to/new_workflow.json --id new_workflow
   ```

3. Review the generated template under the per-user registry:

   ```text
   <user_data_root>/custom_workflows/new_workflow/workflow.config.template.json
   ```

   - Confirm the minimal required fields: `description`, `capability`, `output_kind`, and exposed inputs in `node_mapping`.
   - Optional: add selection metadata (`intent_categories`, `priority`, `keywords_any`, `selection_guidance`) so Agents can prefer your workflow.
4. Rename the reviewed template to activate it:

   ```text
   workflow.config.json
   ```

5. Optional preflight:

   ```bash
   uv run --no-sync python -m comfyui generate --workflow new_workflow --preflight
   ```

### Maintainer Path

- Maintainers may import into the built-in workflow registry (packaged assets) explicitly:

  ```bash
  uv run --no-sync python -m comfyui import-workflow path/to/new_workflow.json --id new_workflow --into-project
  ```

- After activating a workflow registration, also update docs and tests when needed (executor, CLI validation, config loading, output handling).

The workflow becomes available only after a reviewed config exists:

- User registry: `<user_data_root>/custom_workflows/<id>/workflow.config.json`
- Built-in registry (maintainer): `assets/workflows/<id>.config.json`

## Analyzer Safety

The import/analyze step generates a template. The template is not an activation artifact.

Never treat analyzer output as reviewed. It guesses node roles from workflow structure and names; human review is required before activation.

## Workflow Config Fields

Common top-level fields:

| Field | Purpose |
|-------|---------|
| `workflow_id` | Stable id used by `--workflow` |
| `workflow_file` | Workflow JSON path/name under the workflow registry root |
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
