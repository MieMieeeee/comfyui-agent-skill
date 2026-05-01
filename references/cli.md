# ComfyUI CLI Contract

This file is the detailed CLI contract for Agents. Keep `SKILL.md` focused on the most common commands; load this file for full options, output paths, async jobs, and JSON error handling.

## Table of Contents

- [Invocation Rules](#invocation-rules)
- [Subcommands](#subcommands)
- [Server URL Resolution](#server-url-resolution)
- [Generate Options](#generate-options)
- [Output Paths](#output-paths)
- [Progress](#progress)
- [Async Submit and Poll](#async-submit-and-poll)
- [JSON Output](#json-output)
- [Error Codes](#error-codes)

## Invocation Rules

Run commands from the skill root, the directory containing `SKILL.md` and `scripts/`.

Use `uv run --no-sync python -m comfyui` for runtime commands. Do not use bare `python -m comfyui` in Agent instructions.

Run `uv sync` only during setup or dependency changes. `--no-sync` prevents runtime invocations from mutating `.venv`, which matters in multi-agent environments.

Do not pass `--check` or `--save-server` to `generate`; they are top-level compatibility flags or subcommands handled outside the generate parser. Prefer the explicit subcommands below.

## Subcommands

| Command | Purpose |
|---------|---------|
| `uv run --no-sync python -m comfyui check` | Health check via `GET /system_stats` |
| `uv run --no-sync python -m comfyui save-server URL` | Persist a ComfyUI server URL to `config.local.json` |
| `uv run --no-sync python -m comfyui generate [options]` | Execute or submit a registered workflow |

Health check:

```bash
uv run --no-sync python -m comfyui check
```

Save server:

```bash
uv run --no-sync python -m comfyui save-server http://192.168.1.100:8188
```

## Server URL Resolution

Priority:

1. `--server` CLI flag
2. `COMFYUI_URL` environment variable
3. `config.local.json`
4. Default `http://127.0.0.1:8188`

Do not create or edit `config.local.json` unless the user explicitly wants a persistent server URL. For one-off calls, use `--server` or `COMFYUI_URL`.

Tests may override the config path with `COMFYUI_CONFIG_FILE`.

## Generate Options

| Flag | Default | Description |
|------|---------|-------------|
| `--workflow` | `z_image_turbo` | Registered workflow id. `--submit` requires this flag explicitly. |
| `--prompt`, `-p` | none | Prompt text for image/video/music workflows. May also be positional for sync generation. |
| `--speech-text` | none | Spoken content for `qwen3_tts` only. |
| `--instruct` | none | Voice/style instruction for `qwen3_tts` only. |
| `--image` | none | `key=path` or bare path when the workflow has exactly one image role. Repeat for multiple roles. |
| `--count` | `1` | Repeat count per prompt for synchronous generation. |
| `--width`, `--height` | workflow default | Must be provided together. Only valid for workflows with both mapped dimensions and no `workflow_managed` size strategy. |
| `--server` | resolved URL | Server URL for this invocation only. |
| `--output` | task directory under `results/` | Optional output directory override. Prefer omitting it and reading `outputs[].path` from JSON. |
| `--progress` | off | Print progress JSON lines to stderr. |
| `--preflight` | off | Run node/model preflight for the selected workflow and exit; no prompt required. |
| `--skip-preflight` | off | Skip automatic preflight before generation or submit. Use only for debugging. |
| `--submit` | off | Queue job without waiting for outputs. |
| `--poll JOB_ID` | none | Read/update one async job snapshot. |
| `--poll-all` | off | Poll all submitted/executing jobs in the local job store. |

Automatic preflight runs after server health check and before enqueue/execution. Failed preflight returns `PREFLIGHT_*` and does not submit the workflow.

## Output Paths

Recommended Agent behavior: do not pass `--output` unless the user requested a fixed directory. Parse stdout JSON and use `outputs[].path`.

Default output root:

```text
results/%Y%m%d/%H%M%S_{job_id}/
```

Rules:

- No `--output`: create the default task directory.
- Relative `--output my_folder`: append under the task directory, e.g. `results/20260501/121314_job/my_folder/`.
- Absolute `--output E:\path\to\dir`: write the batch to that fixed directory.
- Path ending with a common media extension such as `.png`, `.mp4`, or `.mp3`: use its parent directory as the save directory.

The workflow/ComfyUI node determines filenames. Always trust returned JSON paths.

## Progress

For long jobs, use:

```bash
uv run --no-sync python -m comfyui generate --workflow ltx_23_t2v_distill -p "prompt" --progress
```

Progress events are JSON lines on stderr. Stdout remains reserved for the final structured result.

Programmatic callers can pass `progress_callback=fn` to `execute_workflow(...)`; the callback receives dictionaries with phases such as `queued`, `executing`, `status`, and `finished`.

## Async Submit and Poll

Use async submit for long-running jobs when the Agent should queue work and return job ids instead of blocking.

Submit rules:

- `--submit` requires an explicit `--workflow`.
- `--submit`, `--poll`, and `--poll-all` are mutually exclusive.
- `--submit` accepts a single prompt only. Submit multiple prompts as multiple commands.
- TTS submit must use `--speech-text` and `--instruct`.
- Server-down failures normalize to `SERVER_UNAVAILABLE`.

Submit TTS:

```bash
uv run --no-sync python -m comfyui generate --submit --workflow qwen3_tts --speech-text "……" --instruct "……"
```

Submit video:

```bash
uv run --no-sync python -m comfyui generate --submit --workflow ltx_23_t2v_distill -p "Cinematic shot, slow camera move"
```

Poll one:

```bash
uv run --no-sync python -m comfyui generate --poll JOB_ID
```

Poll all pending:

```bash
uv run --no-sync python -m comfyui generate --poll-all
```

## JSON Output

CLI writes one structured JSON object to stdout for success or failure.

Success:

```json
{
  "success": true,
  "workflow_id": "z_image_turbo",
  "status": "completed",
  "outputs": [{"path": "results/20260501/121314_job/file.png", "filename": "file.png", "size_bytes": 123456}],
  "job_id": "a806c637-xxxx",
  "error": null,
  "metadata": {"prompt": "...", "prompt_id": "a806c637-xxxx", "width": 832, "height": 1280, "seed": 12345}
}
```

Failure:

```json
{
  "success": false,
  "workflow_id": "z_image_turbo",
  "status": "failed",
  "outputs": [],
  "job_id": null,
  "error": {"code": "SERVER_UNAVAILABLE", "message": "ComfyUI server not available at http://127.0.0.1:8188"},
  "metadata": {}
}
```

For `--count > 1`, stdout uses a wrapper:

```json
{
  "count": 2,
  "success": true,
  "results": [{"...": "single-result-schema"}, {"...": "single-result-schema"}]
}
```

Agent-only preflight before CLI for `reference_to_image` may return:

```json
{
  "source": "agent",
  "success": false,
  "error": {"code": "VISION_UNAVAILABLE", "message": "Cannot read reference image in this runtime."}
}
```

Agent-only codes are `NO_REFERENCE_IMAGE` and `VISION_UNAVAILABLE`. Do not use `SERVER_UNAVAILABLE` for Agent-only vision failures.

## Error Codes

| Code | Meaning | Agent action |
|------|---------|--------------|
| `SERVER_UNAVAILABLE` | Target ComfyUI URL did not pass health check or connection failed | Stop generation; ask whether ComfyUI is running locally or on another machine |
| `WORKFLOW_NOT_REGISTERED` | Requested workflow lacks reviewed `*.config.json` registration | Do not auto-run arbitrary workflow; offer maintainer registration steps |
| `EMPTY_PROMPT` | Prompt required but missing | Ask for prompt or construct it from user request |
| `INVALID_ARGS` | Arguments are incompatible with the selected workflow (e.g. TTS with positional prompts) | Retry with the correct flags for that workflow |
| `EMPTY_SPEECH_TEXT` | `--speech-text` required but missing | Ask for the spoken content |
| `EMPTY_INSTRUCT` | `--instruct` required but missing | Ask for the voice/style instruction |
| `NO_INPUT_IMAGE` | Workflow requires an image role that was not provided | Ask for the missing input image |
| `INPUT_IMAGE_NOT_FOUND` | Provided local path does not exist | Ask for a valid local path |
| `IMAGE_UPLOAD_FAILED` | Upload to ComfyUI failed | Report upload failure and keep original path visible |
| `INVALID_PARAM` | Unsupported flag/value for selected workflow | Adjust CLI flags according to workflow rules |
| `INVALID_PARAM_TYPE` | Parameter type is wrong | Correct the value type |
| `MULTIPLE_PROMPTS_NOT_SUPPORTED` | `--submit` received multiple prompts | Submit each prompt separately |
| `WORKFLOW_REQUIRED` | `--submit` was used without an explicit `--workflow` flag | Re-run with `--workflow <id>` |
| `MUTUAL_EXCLUSION` | `--submit`, `--poll`, and `--poll-all` were used together | Use only one async mode at a time |
| `PREFLIGHT_SERVER_UNREACHABLE` | Preflight could not reach ComfyUI metadata endpoints | Treat like server/setup issue |
| `PREFLIGHT_MISSING_NODES` | Required custom nodes are not registered | Ask user to install/enable missing nodes |
| `PREFLIGHT_MISSING_MODELS` | Required models are not listed by ComfyUI | Ask user to install/download missing models |
| `PREFLIGHT_FAILED` | Other preflight failure | Report structured details |
| `DEPENDENCY_UNAVAILABLE` | Transitive Python dependency missing after package import succeeds | Run `uv sync` |
| `CONFIG_ERROR` | Invalid workflow config | Maintainer action required |
| `MAPPING_NOT_FOUND` | Config lacks required node mapping | Maintainer action required |
| `WORKFLOW_FILE_NOT_FOUND` | Registered workflow JSON is missing | Maintainer action required |
| `WORKFLOW_LOAD_FAILED` | Workflow JSON could not be parsed/loaded | Maintainer action required |
| `EXECUTION_FAILED` | ComfyUI accepted but execution failed | Report message; check ComfyUI UI/logs |
| `NO_OUTPUT` | Execution completed without retrievable media | Check output nodes, models, and [workflow_nodes.md](workflow_nodes.md) |
| `SAVE_FAILED` | Output retrieval or local save failed | Report local save error |
| `SUBMISSION_FAILED` | Non-connection submission error | Report submission failure |
| `POLL_FAILED` | Async poll failed | Report poll failure; job may still exist |

If `uv run --no-sync python -m comfyui` cannot import the `comfyui` package itself, Python may emit a non-JSON traceback before `__main__.py` runs. Treat non-JSON stdout/stderr as an environment setup issue and run `uv sync`.
