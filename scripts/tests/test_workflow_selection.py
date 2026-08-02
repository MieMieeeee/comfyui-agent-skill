from __future__ import annotations

from comfyui.services.workflow_config import WorkflowConfig
from comfyui.workflow_selection import select_text_to_image_workflow_id


def test_empty_prompt_returns_default():
    registry = {
        "z_image_turbo": WorkflowConfig(workflow_id="z_image_turbo", workflow_file="z.json", output_node_title="Out"),
    }
    assert select_text_to_image_workflow_id("", registry=registry, default_workflow_id="z_image_turbo") == "z_image_turbo"
    assert select_text_to_image_workflow_id("   ", registry=registry, default_workflow_id="z_image_turbo") == "z_image_turbo"


def test_poster_keyword_selects_qwen_image():
    registry = {
        "z_image_turbo": WorkflowConfig(
            workflow_id="z_image_turbo",
            workflow_file="z.json",
            output_node_title="Out",
            intent_categories=["text_to_image"],
            input_modes=["text"],
            output_kind="image",
            priority=50,
            keywords_any=[],
        ),
        "qwen_image_2512_4step": WorkflowConfig(
            workflow_id="qwen_image_2512_4step",
            workflow_file="q.json",
            output_node_title="Out",
            intent_categories=["text_to_image"],
            input_modes=["text"],
            output_kind="image",
            priority=80,
            keywords_any=["海报", "poster"],
        ),
    }
    assert (
        select_text_to_image_workflow_id(
            "帮我做一张海报，标题写“夏日促销”",
            registry=registry,
            default_workflow_id="z_image_turbo",
        )
        == "qwen_image_2512_4step"
    )


def test_non_text_to_image_workflows_are_ignored():
    registry = {
        "z_image_turbo": WorkflowConfig(
            workflow_id="z_image_turbo",
            workflow_file="z.json",
            output_node_title="Out",
            intent_categories=["text_to_image"],
            input_modes=["text"],
            output_kind="image",
            priority=50,
            keywords_any=[],
        ),
        "qwen3_tts": WorkflowConfig(
            workflow_id="qwen3_tts",
            workflow_file="tts.json",
            output_node_title="Out",
            intent_categories=["text_to_speech"],
            input_modes=["text"],
            output_kind="audio",
            priority=100,
            keywords_any=["海报", "poster"],
        ),
    }
    assert (
        select_text_to_image_workflow_id(
            "poster banner",
            registry=registry,
            default_workflow_id="z_image_turbo",
        )
        == "z_image_turbo"
    )


def test_priority_breaks_ties_when_both_match():
    registry = {
        "w1": WorkflowConfig(
            workflow_id="w1",
            workflow_file="w1.json",
            output_node_title="Out",
            intent_categories=["text_to_image"],
            input_modes=["text"],
            output_kind="image",
            priority=70,
            keywords_any=["poster"],
        ),
        "w2": WorkflowConfig(
            workflow_id="w2",
            workflow_file="w2.json",
            output_node_title="Out",
            intent_categories=["text_to_image"],
            input_modes=["text"],
            output_kind="image",
            priority=80,
            keywords_any=["poster"],
        ),
    }
    assert select_text_to_image_workflow_id("poster", registry=registry, default_workflow_id="w1") == "w2"


def _full_t2i_registry():
    """A registry mirroring the shipped text_to_image workflows for selection tests."""
    base = dict(
        workflow_file="x.json",
        output_node_title="Out",
        intent_categories=["text_to_image"],
        input_modes=["text"],
        output_kind="image",
    )
    return {
        "z_image_turbo": WorkflowConfig(workflow_id="z_image_turbo", priority=50, keywords_any=[], **base),
        "qwen_image_2512_4step": WorkflowConfig(
            workflow_id="qwen_image_2512_4step", priority=80, keywords_any=["海报", "poster"], **base
        ),
        "anima_turbo": WorkflowConfig(
            workflow_id="anima_turbo", priority=60, keywords_any=["动漫", "anime", "插画", "二次元"], **base
        ),
        "krea2_turbo": WorkflowConfig(
            workflow_id="krea2_turbo", priority=55, keywords_any=["写实", "concept art", "概念设计", "艺术"], **base
        ),
    }


def test_anime_keyword_selects_anima_turbo():
    reg = _full_t2i_registry()
    assert (
        select_text_to_image_workflow_id("画一个动漫风格的女孩子", registry=reg, default_workflow_id="z_image_turbo")
        == "anima_turbo"
    )
    assert (
        select_text_to_image_workflow_id("an anime girl with blue hair", registry=reg, default_workflow_id="z_image_turbo")
        == "anima_turbo"
    )


def test_artistic_keyword_selects_krea2_turbo():
    reg = _full_t2i_registry()
    assert (
        select_text_to_image_workflow_id("一张概念设计的飞船", registry=reg, default_workflow_id="z_image_turbo")
        == "krea2_turbo"
    )


def test_generic_prompt_still_falls_back_to_default():
    reg = _full_t2i_registry()
    assert (
        select_text_to_image_workflow_id("a cat sitting on a windowsill", registry=reg, default_workflow_id="z_image_turbo")
        == "z_image_turbo"
    )

