from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tomllib
from typing import Any

from .canonical import digest, tree_digest
from .errors import SchemaError
from .models import GuidanceLevel, TaskManifest, require_mapping


@dataclass(frozen=True)
class TaskPackage:
    root: Path
    manifest: TaskManifest
    world: dict[str, Any]
    inventory: dict[str, Any]
    equipment: dict[str, Any]
    access: dict[str, Any]
    disturbances: dict[str, Any]
    public_contract: dict[str, Any]
    package_digest: str
    evaluator_digest: str

    @classmethod
    def load(cls, root: str | Path) -> "TaskPackage":
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise SchemaError(f"task directory does not exist: {root_path}")
        manifest_path = root_path / "task.toml"
        if not manifest_path.is_file():
            raise SchemaError("task.toml is missing")
        with manifest_path.open("rb") as handle:
            raw_manifest = tomllib.load(handle)
        manifest = TaskManifest.from_mapping(raw_manifest)

        def load_json(relative: str) -> dict[str, Any]:
            path = root_path / relative
            if not path.is_file():
                raise SchemaError(f"required task file is missing: {relative}")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise SchemaError(f"invalid JSON in {relative}: {error}") from error
            return dict(require_mapping(value, relative))

        for level in manifest.guidance_levels:
            if not (root_path / "guidance" / f"{level.value}.md").is_file():
                raise SchemaError(f"guidance/{level.value}.md is missing")
        evaluator_path = root_path / manifest.evaluator_command[-1]
        if not evaluator_path.is_file():
            raise SchemaError("the task evaluator entry point is missing")
        private_dir = root_path / "private"
        if not private_dir.is_dir():
            raise SchemaError("private evaluator assets directory is missing")
        package = cls(
            root=root_path,
            manifest=manifest,
            world=load_json("public/world.json"),
            inventory=load_json("public/inventory.json"),
            equipment=load_json("public/equipment.json"),
            access=load_json("public/access.json"),
            disturbances=load_json("public/disturbances.json"),
            public_contract=load_json("public/evaluator_contract.json"),
            package_digest=tree_digest(root_path, exclude=("private",)),
            evaluator_digest=digest(
                {
                    "evaluator": tree_digest(root_path / "evaluator"),
                    "private": tree_digest(root_path / "private"),
                }
            ),
        )
        package._validate_semantics()
        return package

    def _validate_semantics(self) -> None:
        baseline = self.world.get("baseline_process_hash")
        if not isinstance(baseline, str) or not baseline.startswith("sha256:"):
            raise SchemaError("public/world.json requires baseline_process_hash")
        baseline_world = self.world.get("baseline_world_hash")
        if not isinstance(baseline_world, str) or not baseline_world.startswith("sha256:"):
            raise SchemaError("public/world.json requires baseline_world_hash")
        processes = self.equipment.get("fabrication_processes")
        if not isinstance(processes, list) or not processes:
            raise SchemaError("equipment requires at least one fabrication process")
        if not isinstance(self.inventory.get("materials"), list):
            raise SchemaError("inventory.materials must be a list")
        if not isinstance(self.access.get("interventions"), list):
            raise SchemaError("access.interventions must be a list")
        if not isinstance(self.disturbances.get("factors"), list):
            raise SchemaError("disturbances.factors must be a list")

    def guidance(self, level: GuidanceLevel) -> str:
        if level not in self.manifest.guidance_levels:
            raise SchemaError(f"task does not support guidance level {level.value}")
        return (self.root / "guidance" / f"{level.value}.md").read_text(encoding="utf-8")

    def materialize_public(self, destination: Path, level: GuidanceLevel) -> Path:
        if destination.exists():
            raise SchemaError(f"public task destination already exists: {destination}")
        destination.mkdir(parents=True)
        shutil.copy2(self.root / "task.toml", destination / "task.toml")
        shutil.copytree(self.root / "public", destination / "public")
        (destination / "mission.md").write_text(self.guidance(level), encoding="utf-8")
        (destination / "PACKAGE_DIGEST").write_text(self.package_digest + "\n", encoding="utf-8")
        return destination
