"""Gate i18n : parité des clés, clés orphelines et chaînes en dur."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project
from ..paths import PathSecurityError, resolve_within
from .gates import (
    ControlResult,
    Evidence,
    Finding,
    GateEvaluation,
    evaluate_gate,
    persist_gate_run,
)


@dataclass(frozen=True)
class LocaleData:
    """Clés aplaties d'une locale."""

    name: str
    keys: frozenset[str]
    path: str


@dataclass(frozen=True)
class HardcodedString:
    """Chaîne codée en dur signalée."""

    key: str
    message: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class I18nGateResult:
    """Résultat du gate i18n."""

    evaluation: GateEvaluation
    run: GateRun
    locales: tuple[LocaleData, ...]
    hardcoded: tuple[HardcodedString, ...]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _flatten(data: Mapping[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            keys.update(_flatten(value, name))
        else:
            keys.add(name)
    return keys


def load_locale(path: str | Path, *, root: str | Path | None = None) -> LocaleData:
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"locale illisible : {path} : {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"locale invalide (objet attendu) : {path}")
    name = str(payload.get("locale") or source.stem)
    return LocaleData(
        name=name,
        keys=frozenset(_flatten(payload)),
        path=_relative(source, root_path),
    )


def collect_locale_paths(
    *,
    root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    locale_paths: Sequence[str | Path] | None = None,
) -> list[Path]:
    root_path = Path(root or Path.cwd()).resolve()
    base = Path(evidence_root or root_path)
    if locale_paths is None:
        candidates = sorted(
            list((base / "reports" / "i18n").glob("*.json"))
            + list((base / "locales").glob("*.json"))
        )
    else:
        candidates = [Path(item) for item in locale_paths]
    paths: list[Path] = []
    for candidate in candidates:
        try:
            path = resolve_within(root_path, candidate)
        except (PathSecurityError, FileNotFoundError, OSError):
            continue
        if path.is_file() and path not in paths:
            paths.append(path)
    return paths


def _hardcoded_item(item: Mapping[str, Any]) -> HardcodedString:
    line = item.get("line")
    try:
        line_number = int(line) if line is not None else None
    except (TypeError, ValueError):
        line_number = None
    return HardcodedString(
        key=str(item.get("key") or item.get("id") or "hardcoded"),
        message=str(item.get("message") or item.get("text") or "chaîne codée en dur"),
        file=str(item["file"]) if item.get("file") else None,
        line=line_number,
    )


def load_hardcoded(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> tuple[HardcodedString, ...]:
    root_path = Path(root or Path.cwd()).resolve()
    try:
        source = resolve_within(root_path, path)
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError):
        return ()
    items: Any = payload.get("hardcoded") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return ()
    return tuple(
        _hardcoded_item(item) for item in items if isinstance(item, Mapping)
    )


def run_i18n_gate(
    session: Session,
    project: Project,
    *,
    locale_paths: Sequence[str | Path] | None = None,
    hardcoded_paths: Sequence[str | Path] | None = None,
    hardcoded: Sequence[Mapping[str, Any]] = (),
    reference: str = "fr",
    evidence_root: str | Path | None = None,
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> I18nGateResult:
    """Évalue la parité i18n et persiste le rapport."""
    root_path = Path(root or Path.cwd()).resolve()
    paths = collect_locale_paths(
        root=root_path,
        evidence_root=evidence_root,
        locale_paths=locale_paths,
    )
    locales: list[LocaleData] = []
    for path in paths:
        try:
            locales.append(load_locale(path, root=root_path))
        except ValueError:
            continue
    hardcoded_items: list[HardcodedString] = [
        _hardcoded_item(item) for item in hardcoded
    ]
    for hardcoded_path in hardcoded_paths or []:
        hardcoded_items.extend(load_hardcoded(hardcoded_path, root=root_path))
    evidence = tuple(
        Evidence(path=_relative(path, root_path), kind="locale", description=path.name)
        for path in paths
    )
    if not locales:
        control = ControlResult(
            key="i18n",
            verdict="not_run",
            reason="aucune locale trouvée dans reports/i18n/ ou locales/",
        )
        evaluation = evaluate_gate(
            "i18n",
            [control],
            gate_name="i18n",
            config=config,
            root=root_path,
        )
        run = persist_gate_run(
            session,
            project,
            evaluation,
            reports_dir=reports_dir,
            config=config,
            root=root_path,
        )
        return I18nGateResult(evaluation, run, (), ())
    if len(locales) < 2:
        control = ControlResult(
            key="parity",
            verdict="not_applicable",
            expected=False,
            reason="une seule locale déclarée : parité non applicable",
            evidence=evidence,
        )
        evaluation = evaluate_gate(
            "i18n",
            [control],
            gate_name="i18n",
            config=config,
            root=root_path,
        )
        run = persist_gate_run(
            session,
            project,
            evaluation,
            reports_dir=reports_dir,
            config=config,
            root=root_path,
        )
        return I18nGateResult(evaluation, run, tuple(locales), ())

    reference_locale = next(
        (locale for locale in locales if locale.name == reference),
        sorted(locales, key=lambda locale: locale.name)[0],
    )
    parity_findings: list[Finding] = []
    rates: dict[str, float] = {}
    for locale in locales:
        if locale.name == reference_locale.name:
            continue
        missing = sorted(reference_locale.keys - locale.keys)
        orphan = sorted(locale.keys - reference_locale.keys)
        rates[locale.name] = round(
            (len(reference_locale.keys) - len(missing)) * 100 / len(reference_locale.keys),
            2,
        ) if reference_locale.keys else 100.0
        for key in missing:
            parity_findings.append(
                Finding(
                    key=f"i18n:missing:{locale.name}:{key}",
                    severity="warning",
                    message=f"clé manquante dans {locale.name} : {key}",
                    file=locale.path,
                )
            )
        for key in orphan:
            parity_findings.append(
                Finding(
                    key=f"i18n:orphan:{locale.name}:{key}",
                    severity="warning",
                    message=f"clé orpheline dans {locale.name} : {key}",
                    file=locale.path,
                )
            )
    hardcoded_findings = [
        Finding(
            key=f"i18n:hardcoded:{item.key}",
            severity="warning",
            message=item.message,
            file=item.file,
            line=item.line,
        )
        for item in hardcoded_items
    ]
    parity_verdict = "warn" if parity_findings else "pass"
    hardcoded_verdict = "warn" if hardcoded_findings else (
        "pass" if hardcoded_paths or hardcoded else "not_applicable"
    )
    controls = [
        ControlResult(
            key="parity",
            verdict=parity_verdict,
            expected=True,
            reason=(
                f"{len(parity_findings)} écart(s) de parité"
                if parity_findings
                else "clés alignées"
            ),
            evidence=evidence,
            findings=tuple(parity_findings),
            details={"reference": reference_locale.name, "rates": rates},
        ),
        ControlResult(
            key="hardcoded",
            verdict=hardcoded_verdict,
            expected=bool(hardcoded_paths or hardcoded),
            reason=(
                f"{len(hardcoded_findings)} chaîne(s) en dur"
                if hardcoded_findings
                else "aucune chaîne en dur signalée"
            ),
            evidence=evidence,
            findings=tuple(hardcoded_findings),
        ),
    ]
    evaluation = evaluate_gate(
        "i18n",
        controls,
        gate_name="i18n",
        config=config,
        root=root_path,
    )
    run = persist_gate_run(
        session,
        project,
        evaluation,
        reports_dir=reports_dir,
        config=config,
        root=root_path,
    )
    return I18nGateResult(
        evaluation=evaluation,
        run=run,
        locales=tuple(locales),
        hardcoded=tuple(hardcoded_items),
    )
