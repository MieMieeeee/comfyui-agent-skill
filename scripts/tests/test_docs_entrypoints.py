import json
import re
from pathlib import Path


def test_readme_has_quickstart_troubleshooting_and_short_cli():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "README.md").read_text(encoding="utf-8")
    assert "## Install" in text
    assert "Troubleshooting" in text
    assert "SERVER_UNAVAILABLE" in text
    assert "PREFLIGHT_MISSING_NODES" in text
    assert "NO_OUTPUT" in text
    assert "comfyui-agent-skill-mie" in text
    assert "comfyui-skill" in text
    assert text.index("pipx install comfyui-agent-skill-mie") < text.index("uv tool install comfyui-agent-skill-mie")


def test_maintainer_mentions_import_workflow():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "MAINTAINER.md").read_text(encoding="utf-8")
    assert "import-workflow" in text


def test_cli_reference_mentions_import_workflow():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "references" / "cli.md").read_text(encoding="utf-8")
    assert "import-workflow" in text


def test_skill_frontmatter_name_matches_package_name():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "name: comfyui-agent-skill-mie" in text


def test_skill_hard_rule_does_not_treat_every_image_to_video_as_image_only():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "For `image_to_image` and `image_to_video`, upload the provided local image with `--image`." not in text
    rules = text.split("## Hard Rules", 1)[1].split("## Workflow Selection Policy", 1)[0]
    assert "liveportrait" in rules
    assert "--video" in rules
    assert "qwen3_tts_clone" in rules
    assert '--text-input "ref_text=..."' in rules
    assert "--audio" in rules


def test_capability_boundaries_split_video_and_speech_workflows():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "references" / "workflows.md").read_text(encoding="utf-8")
    section = text.split("## Capability Boundaries", 1)[1].split("## Input and Size Mapping", 1)[0]
    assert "liveportrait" in section
    assert "--video" in section
    assert "qwen3_tts_clone" in section
    assert '--text-input "ref_text=..."' in section
    assert "--audio" in section
    assert "`image_to_video` uses `ltx_23_i2v_distilled`." not in section
    mapping = text.split("## Input and Size Mapping", 1)[1].split("Width/height are valid", 1)[0]
    assert "liveportrait" in mapping
    assert "qwen3_tts_clone" in mapping


def test_skill_still_guides_agent_when_server_is_unavailable():
    """Server-down is a handled outcome, not a reason to skip the skill."""
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "Do not use it when the ComfyUI server is unavailable." not in text
    assert "A ComfyUI server being unavailable is not a reason to skip this skill." in text
    assert "SERVER_UNAVAILABLE" in text
    assert "`check`" in text
    assert "`doctor`" in text


def test_skill_frontmatter_covers_all_supported_media_tasks():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    for term in ("matting", "expression transfer", "voice cloning"):
        assert term in frontmatter, f"frontmatter description missing: {term}"
    assert "does not execute arbitrary unreviewed workflow JSON" in frontmatter
    assert "private registry" in frontmatter
    assert "preflight" in frontmatter
    assert "save the server" in frontmatter.lower() or "save the server URL" in frontmatter
    # Out of scope: packaging, SVG, directory sync.
    for banned in ("SVG", "clawhub", "zip"):
        assert banned not in frontmatter


def test_skill_use_this_skill_when_lists_new_capabilities():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("Use this skill when", 1)[1].split("## Hard Rules", 1)[0]
    assert "Cut out or mask an object" in section
    assert "driving video" in section
    assert "Clone a specific voice" in section


def test_skill_size_rule_is_in_hard_rules():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    rules = text.split("## Hard Rules", 1)[1].split("## Workflow Selection Policy", 1)[0]
    assert "size_strategy" in rules
    assert "INVALID_PARAM" in rules
    assert "--submit" in rules


def test_size_rule_names_the_media_workflows():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "references" / "workflows.md").read_text(encoding="utf-8")
    section = text.split("Width/height are valid only", 1)[1].split("Registered defaults", 1)[0]
    for wid in (
        "klein_edit",
        "ltx_23_i2v_distilled",
        "sam3_mat_image",
        "liveportrait",
        "ace_step_15_music",
        "qwen3_tts",
        "qwen3_tts_clone",
    ):
        assert f"`{wid}`" in section, f"size rule omits {wid}"
    assert "INVALID_PARAM" in section
    assert "--submit" in section


def test_cli_error_table_lists_media_and_plugin_codes():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "references" / "cli.md").read_text(encoding="utf-8")
    for code in (
        "NO_INPUT_IMAGE",
        "NO_INPUT_MEDIA",
        "INPUT_IMAGE_NOT_FOUND",
        "INPUT_MEDIA_NOT_FOUND",
        "IMAGE_UPLOAD_FAILED",
        "MEDIA_UPLOAD_FAILED",
        "MISSING_INPUT",
        "PREFLIGHT_MISSING_NODES",
        "PREFLIGHT_MISSING_PLUGINS",
    ):
        assert f"| `{code}` |" in text, f"error table missing {code}"
    # A missing video/audio input must not be documented as NO_INPUT_IMAGE.
    assert "do not report it as `NO_INPUT_IMAGE`" in text


def test_skill_error_code_line_separates_media_types():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "NO_INPUT_MEDIA" in text
    assert "INPUT_MEDIA_NOT_FOUND" in text
    assert "MISSING_INPUT" in text
    assert "Do not report a missing video or audio input as `NO_INPUT_IMAGE`." in text


def test_results_dir_is_documented_under_user_data_root():
    root = Path(__file__).resolve().parent.parent.parent
    cli = (root / "references" / "cli.md").read_text(encoding="utf-8")
    assert r"%APPDATA%\comfyui-skill" in cli
    assert "<user_data_root>/results/" in cli
    assert "task directory under `results/`" not in cli
    assert "The file lives in the same per-user data root as generated media" in cli
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "inside the per-user data root" in skill
    assert "outputs[].path" in skill


def test_output_help_text_points_at_user_data_root():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "scripts" / "comfyui" / "cli_generate.py").read_text(encoding="utf-8")
    assert "under the skill root" not in text
    assert "per-user data root" in text


def test_validate_cases_use_registered_workflow_ids():
    root = Path(__file__).resolve().parent.parent.parent
    text = (root / "scripts" / "comfyui" / "cli_validate.py").read_text(encoding="utf-8")
    assert '"ltx-23-t2v"' not in text
    assert '"ltx-23-i2v"' not in text
    assert '"ltx_23_t2v_distill"' in text
    assert '"ltx_23_i2v_distilled"' in text


def test_krea2_copy_is_aligned_across_docs_and_config():
    root = Path(__file__).resolve().parent.parent.parent
    guidance = json.loads(
        (root / "assets" / "workflows" / "krea2_turbo.config.json").read_text(encoding="utf-8")
    )["selection_guidance"]
    best_for = " ".join(guidance["best_for"])
    # The config advertises product visualization, so the docs may keep it.
    assert "product visualization" in best_for

    en = (root / "README.md").read_text(encoding="utf-8")
    zh = (root / "README.zh-CN.md").read_text(encoding="utf-8")
    wf = (root / "references" / "workflows.md").read_text(encoding="utf-8")

    for doc, name in ((en, "en"), (zh, "zh"), (wf, "workflows.md")):
        line = next(l for l in doc.splitlines() if l.strip().startswith("- `krea2_turbo`") or "| Artistic / painterly" in l)
        assert "product" in line.lower() or "产品" in line, f"{name} drops product visualization"

    section = wf.split("### `krea2_turbo`", 1)[1].split("### `klein_edit`", 1)[0]
    assert "product visualization" in section
    assert "qwen_image_2512_4step" in section  # embedded text is an avoid_for in the config
    for avoid in guidance["avoid_for"]:
        for wid in ("anima_turbo", "z_image_turbo", "qwen_image_2512_4step"):
            if wid in avoid:
                assert wid in section, f"krea2 section omits avoid_for target {wid}"


def test_sam3_mat_image_avoid_for_has_no_unregistered_workflow():
    root = Path(__file__).resolve().parent.parent.parent
    data = json.loads(
        (root / "assets" / "workflows" / "sam3_mat_image.config.json").read_text(encoding="utf-8")
    )
    registered = {p.name[: -len(".config.json")] for p in (root / "assets" / "workflows").glob("*.config.json")}
    avoid_for = data["selection_guidance"]["avoid_for"]
    assert any("video matting" in a for a in avoid_for)
    for entry in avoid_for:
        for ref in re.findall(r"use ([a-z0-9_]+)", entry):
            assert ref in registered, f"avoid_for references unregistered workflow: {ref}"
