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

