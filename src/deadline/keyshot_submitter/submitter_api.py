# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from deadline.client.submitter_api import SubmitterAPI, SubmitterSettings


@dataclass
class KeyShotSubmitterSettings(SubmitterSettings):
    """KeyShot-specific submission settings."""

    render_device: str = "CPU"
    override_render_device: bool = False
    scene_file: str = ""
    auto_detected_input_filenames: list[str] = field(default_factory=list)
    referenced_paths: list[str] = field(default_factory=list)


class KeyShotSubmitterAPI(SubmitterAPI):
    """SubmitterAPI implementation for KeyShot submissions."""

    def get_settings(self) -> KeyShotSubmitterSettings:
        import lux  # type: ignore[import]

        settings = KeyShotSubmitterSettings()
        scene_file = lux.getSceneFileName() or ""
        settings.scene_file = scene_file
        settings.name = os.path.basename(scene_file) if scene_file else "Untitled"
        settings.project_path = os.path.dirname(scene_file) if scene_file else ""
        settings.input_filenames = [scene_file] if scene_file else []

        frame_count = lux.getAnimationFrames()
        if frame_count > 1:
            settings.frame_list = f"1-{frame_count}"
        else:
            settings.frame_list = "1"

        render_options = lux.getRenderOptions()
        if render_options:
            output_path = render_options.get("output", "")
            if output_path:
                settings.output_path = output_path
                settings.output_directories = [os.path.dirname(output_path)]

        current_engine = lux.getRenderEngine()
        is_gpu = current_engine in [lux.RENDER_ENGINE_PRODUCT_GPU, lux.RENDER_ENGINE_INTERIOR_GPU]
        settings.render_device = "GPU" if is_gpu else "CPU"

        return settings

    def get_job_template(
        self,
        settings: SubmitterSettings,
        host_requirements: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        from submitter import construct_job_template

        job_template = construct_job_template(settings.name)

        if host_requirements:
            for step in job_template.get("steps", []):
                step["hostRequirements"] = host_requirements

        if isinstance(settings, KeyShotSubmitterSettings) and settings.render_device == "GPU":
            for step in job_template.get("steps", []):
                if "hostRequirements" not in step:
                    step["hostRequirements"] = {}
                step["hostRequirements"]["amounts"] = [{"name": "amount.worker.gpu", "min": 1}]

        return job_template

    def get_parameter_values(
        self,
        settings: SubmitterSettings,
        queue_parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        import lux  # type: ignore[import]

        parameter_values: list[dict[str, Any]] = []

        if isinstance(settings, KeyShotSubmitterSettings):
            parameter_values.append({"name": "KeyShotFile", "value": settings.scene_file})
            parameter_values.append({"name": "RenderDevice", "value": settings.render_device})
            parameter_values.append(
                {"name": "OverrideRenderDevice", "value": str(settings.override_render_device)}
            )

        major_version, _ = lux.getKeyShotDisplayVersion()
        parameter_values.append({"name": "CondaPackages", "value": f"keyshot={major_version}.*"})
        parameter_values.append({"name": "CondaChannels", "value": ""})

        if settings.frame_list:
            parameter_values.append({"name": "Frames", "value": settings.frame_list})

        parameter_values.extend(
            {"name": param["name"], "value": param["value"]} for param in queue_parameters
        )

        return parameter_values

    def get_asset_references(self, settings: SubmitterSettings) -> dict[str, Any]:
        from submitter import Settings as NativeSettings, construct_asset_references

        native = NativeSettings()
        native.input_filenames = list(settings.input_filenames)
        native.input_directories = list(settings.input_directories)
        native.output_directories = list(settings.output_directories)
        native.referenced_paths = (
            settings.referenced_paths if isinstance(settings, KeyShotSubmitterSettings) else []
        )
        native.auto_detected_input_filenames = (
            settings.auto_detected_input_filenames
            if isinstance(settings, KeyShotSubmitterSettings)
            else []
        )
        native.parameter_values = []

        return construct_asset_references(native)
