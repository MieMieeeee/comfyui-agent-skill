# z_image_turbo Workflow Nodes

## Overview

9-node ComfyUI API-format workflow for text-to-image generation using the Z-Image Turbo model.

## Nodes

| ID | Title | class_type | Purpose |
|----|-------|-----------|---------|
| 16 | Load Diffusion Model | UNETLoader | Loads `Z-Image\z_image_turbo_bf16.safetensors` |
| 18 | Load CLIP | CLIPLoader | Loads `Qwen\qwen_3_4b.safetensors` (type: lumina2) |
| 17 | Load VAE | VAELoader | Loads `Flux\ae.sft` |
| 6 | CLIP Text Encode (Positive Prompt) | CLIPTextEncode | **User prompt input** — set `text` parameter |
| 7 | CLIP Text Encode (Negative Prompt) | CLIPTextEncode | Negative prompt, default: `"blurry ugly bad"` |
| 13 | EmptySD3LatentImage | EmptySD3LatentImage | Latent dimensions: width=832, height=1280, batch=1 |
| 3 | KSampler | KSampler | Sampling: seed=77, steps=9, cfg=1, sampler=res_multistep, scheduler=sgm_uniform |
| 8 | VAE Decode | VAEDecode | Decodes latent to pixel space |
| 9 | Save Image | SaveImage | **Output node** — saves generated image |

## Required Model Files

- `Z-Image/z_image_turbo_bf16.safetensors` — Diffusion model
- `Qwen/qwen_3_4b.safetensors` — Text encoder (CLIP)
- `Flux/ae.sft` — VAE

## Default Parameters

| Parameter | Value |
|-----------|-------|
| Width | 832 |
| Height | 1280 |
| Seed | 77 |
| Steps | 9 |
| CFG | 1.0 |
| Sampler | res_multistep |
| Scheduler | sgm_uniform |
| Denoise | 1.0 |
| Negative Prompt | blurry ugly bad |

## Modifiable Inputs (MVP)

Only the positive prompt text is exposed via the MVP:

```python
wf.set_node_param("CLIP Text Encode (Positive Prompt)", "text", prompt)
```

## Output

The `Save Image` node produces PNG images returned as bytes by the wrapper.
