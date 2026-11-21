from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2]
PROFILE_ROOT = SKILL_ROOT / "references" / "comsol-6.4" / "profiles"


class ProfileError(ValueError):
    pass


def load_profile(profile_id: str, root: str | Path | None = None, require_validated: bool = True) -> dict[str, Any]:
    if not profile_id or Path(profile_id).name != profile_id or profile_id in {".", ".."}:
        raise ProfileError("profile_id must be a simple file stem")
    base = Path(root).resolve() if root else PROFILE_ROOT
    path = base / f"{profile_id}.json"
    if not path.is_file():
        raise ProfileError(f"Profile not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        profile = json.load(stream)
    if profile.get("profile_id") != profile_id:
        raise ProfileError("Profile file profile_id does not match its filename")
    if profile.get("comsol_version") != "6.4":
        raise ProfileError("Profile is not scoped to COMSOL 6.4")
    state = profile.get("verification", {}).get("state", "discovered")
    allowed = {"discovered", "probe_passed", "integration_tested", "validated"}
    if state not in allowed:
        raise ProfileError(f"Unknown profile verification state: {state}")
    if require_validated and state != "validated":
        raise ProfileError(
            f"Profile {profile_id} is {state}, not validated. "
            "A COMSOL 6.4 probe and scientific benchmark are required before production use."
        )
    if require_validated:
        verification = profile.get("verification", {})
        if not verification.get("test_id") or not verification.get("evidence_files"):
            raise ProfileError("A validated profile must include test_id and evidence_files")
    return profile


def list_profiles(root: str | Path | None = None) -> list[dict[str, str]]:
    base = Path(root).resolve() if root else PROFILE_ROOT
    if not base.exists():
        return []
    items = []
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({
                "profile_id": str(data.get("profile_id", path.stem)),
                "state": str(data.get("verification", {}).get("state", "discovered")),
                "comsol_version": str(data.get("comsol_version", "unknown")),
                "path": str(path)
            })
        except Exception as exc:
            items.append({"profile_id": path.stem, "state": "invalid", "error": str(exc), "path": str(path)})
    return items
