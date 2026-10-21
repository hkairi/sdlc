"""Gate de données : migrations, PII, sauvegarde, rétention et chiffrement."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import GateRun, Project
from ..paths import PathSecurityError, resolve_within
from .gate_config import data_config
from .gates import (
    ControlResult,
    Evidence,
    Finding,
    GateEvaluation,
    evaluate_gate,
    persist_gate_run,
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LARGE_TABLE_ROWS = 1_000_000


@dataclass(frozen=True)
class MigrationRisk:
    """Risque détecté dans une migration."""

    file: str
    line: int
    statement: str
    reason: str
    table: str | None = None


@dataclass(frozen=True)
class PiiFinding:
    """PII détectée dans un log."""

    file: str
    line: int
    value: str
    kind: str = "email"


@dataclass(frozen=True)
class BackupStatus:
    """État d'une sauvegarde vérifiée."""

    verified: bool
    restore_tested: bool
    age_hours: float | None = None
    source: str | None = None


@dataclass(frozen=True)
class DataGateResult:
    """Résultat du gate données."""

    evaluation: GateEvaluation
    run: GateRun
    migrations: tuple[MigrationRisk, ...]
    pii: tuple[PiiFinding, ...]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _line_for(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _strip_comments(statement: str) -> str:
    return "\n".join(
        line for line in statement.splitlines() if not line.strip().startswith("--")
    ).strip()


def _statements(text: str) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for match in re.finditer(r"[^;]+;?", text):
        raw = match.group(0)
        cleaned = _strip_comments(raw)
        if cleaned:
            results.append((_line_for(text, match.start()), cleaned))
    return results


def scan_migrations(
    paths: Sequence[str | Path],
    *,
    root: str | Path | None = None,
    large_tables: Mapping[str, int] | None = None,
) -> tuple[MigrationRisk, ...]:
    """Détecte les migrations destructives dans les fichiers SQL."""
    root_path = Path(root or Path.cwd()).resolve()
    risks: list[MigrationRisk] = []
    for path in paths:
        try:
            source = resolve_within(root_path, path)
            text = source.read_text(encoding="utf-8")
        except (PathSecurityError, FileNotFoundError, OSError):
            continue
        for line, statement in _statements(text):
            normalized = re.sub(r"\s+", " ", statement).strip().lower()
            if not normalized:
                continue
            table = None
            reason = None
            alter = re.search(
                r"alter\s+table\s+([a-zA-Z0-9_.\"`]+)\s+add\s+(?:column\s+)?(.+)",
                statement,
                re.IGNORECASE | re.DOTALL,
            )
            if (
                alter
                and re.search(r"\bnot\s+null\b", alter.group(2), re.IGNORECASE)
                and not re.search(r"\bdefault\b", alter.group(2), re.IGNORECASE)
            ):
                table = alter.group(1).strip('"`')
                reason = "ajout NOT NULL sans DEFAULT"
                rows = (large_tables or {}).get(table)
                if rows is not None:
                    reason += f" sur une table de {rows} ligne(s)"
            if re.search(r"\bdrop\s+table\b", normalized):
                reason = "DROP TABLE"
            elif re.search(r"\bdrop\s+column\b", normalized):
                reason = "DROP COLUMN"
            elif re.search(r"\btruncate\b", normalized):
                reason = "TRUNCATE"
            elif re.search(r"\bdelete\s+from\b", normalized) and " where " not in f" {normalized} ":
                reason = "DELETE sans WHERE"
            if reason:
                risks.append(
                    MigrationRisk(
                        file=_relative(source, root_path),
                        line=line,
                        statement=statement.strip(),
                        reason=reason,
                        table=table,
                    )
                )
    return tuple(risks)


def scan_pii_logs(
    paths: Sequence[str | Path],
    *,
    root: str | Path | None = None,
) -> tuple[PiiFinding, ...]:
    """Détecte les emails en clair dans les logs."""
    root_path = Path(root or Path.cwd()).resolve()
    findings: list[PiiFinding] = []
    for path in paths:
        try:
            source = resolve_within(root_path, path)
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        except (PathSecurityError, FileNotFoundError, OSError):
            continue
        for number, line in enumerate(lines, start=1):
            for match in EMAIL_RE.finditer(line):
                findings.append(
                    PiiFinding(
                        file=_relative(source, root_path),
                        line=number,
                        value=match.group(0),
                    )
                )
    return tuple(findings)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_backup_status(
    path: str | Path | None = None,
    *,
    root: str | Path | None = None,
    status: Mapping[str, Any] | None = None,
) -> BackupStatus | None:
    payload: Mapping[str, Any] | None = status
    source = None
    if payload is None and path is not None:
        root_path = Path(root or Path.cwd()).resolve()
        try:
            source_path = resolve_within(root_path, path)
            loaded = json.loads(source_path.read_text(encoding="utf-8"))
        except (PathSecurityError, FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if isinstance(loaded, dict):
            payload = loaded
            source = _relative(source_path, root_path)
    if payload is None:
        return None
    verified = bool(payload.get("verified", False))
    restore_tested = bool(
        payload.get("restore_tested", payload.get("tested", False))
    )
    last_verified = payload.get("last_verified_at") or payload.get("verified_at")
    age_hours = _number(payload.get("age_hours"))
    if age_hours is None and last_verified:
        try:
            parsed = datetime.fromisoformat(str(last_verified).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age_hours = (datetime.now(UTC) - parsed).total_seconds() / 3600
        except ValueError:
            age_hours = None
    return BackupStatus(
        verified=verified,
        restore_tested=restore_tested,
        age_hours=age_hours,
        source=source,
    )


def collect_data_paths(
    *,
    root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    migration_paths: Sequence[str | Path] | None = None,
    log_paths: Sequence[str | Path] | None = None,
    backup_path: str | Path | None = None,
) -> tuple[list[Path], list[Path], Path | None]:
    root_path = Path(root or Path.cwd()).resolve()
    base = Path(evidence_root or root_path)
    data_dir = base / "reports" / "data"
    migrations = (
        [Path(item) for item in migration_paths]
        if migration_paths is not None
        else sorted((data_dir / "migrations").glob("*.sql"))
    )
    logs = (
        [Path(item) for item in log_paths]
        if log_paths is not None
        else sorted(
            path
            for path in (data_dir / "logs").glob("*")
            if path.suffix.lower() in {".log", ".txt", ".jsonl"}
        )
    )

    def resolved(items: Sequence[str | Path]) -> list[Path]:
        result: list[Path] = []
        for item in items:
            try:
                path = resolve_within(root_path, item)
            except (PathSecurityError, FileNotFoundError, OSError):
                continue
            if path.is_file() and path not in result:
                result.append(path)
        return result

    backup = None
    candidate = Path(backup_path) if backup_path is not None else data_dir / "backup.json"
    try:
        backup = resolve_within(root_path, candidate)
    except (PathSecurityError, FileNotFoundError, OSError):
        backup = None
    return resolved(migrations), resolved(logs), backup


def run_data_gate(
    session: Session,
    project: Project,
    *,
    migration_paths: Sequence[str | Path] | None = None,
    log_paths: Sequence[str | Path] | None = None,
    backup_path: str | Path | None = None,
    backup_status: Mapping[str, Any] | None = None,
    retention_days: int | None = None,
    encrypted: bool | None = None,
    large_tables: Mapping[str, int] | None = None,
    evidence_root: str | Path | None = None,
    reports_dir: str | Path = "reports/gates",
    root: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
) -> DataGateResult:
    """Évalue le gate données et persiste le rapport."""
    root_path = Path(root or Path.cwd()).resolve()
    migrations, logs, backup_file = collect_data_paths(
        root=root_path,
        evidence_root=evidence_root,
        migration_paths=migration_paths,
        log_paths=log_paths,
        backup_path=backup_path,
    )
    risks = scan_migrations(migrations, root=root_path, large_tables=large_tables)
    pii = scan_pii_logs(logs, root=root_path)
    status = load_backup_status(
        backup_file,
        root=root_path,
        status=backup_status,
    )
    configured = data_config(config)
    if retention_days is None:
        raw_retention = configured.get("retention_days")
        if isinstance(raw_retention, int):
            retention_days = raw_retention
    if encrypted is None:
        raw_encrypted = configured.get("encrypted")
        if isinstance(raw_encrypted, bool):
            encrypted = raw_encrypted

    evidence = tuple(
        [Evidence(path=_relative(path, root_path), kind="migration", description=path.name) for path in migrations]
        + [Evidence(path=_relative(path, root_path), kind="log", description=path.name) for path in logs]
        + (
            [
                Evidence(
                    path=status.source or _relative(backup_file, root_path),
                    kind="backup",
                    description="sauvegarde vérifiée",
                )
            ]
            if status is not None and backup_file is not None
            else []
        )
    )
    if not evidence and status is None:
        control = ControlResult(
            key="data",
            verdict="not_run",
            reason="aucune preuve de données (migrations, logs, sauvegarde)",
        )
        evaluation = evaluate_gate(
            "data",
            [control],
            gate_name="Données",
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
        return DataGateResult(evaluation, run, (), ())

    migration_findings = [
        Finding(
            key=f"data:migration:{risk.file}:{risk.line}",
            severity="error",
            message=f"{risk.reason} — {risk.statement[:300]}",
            file=risk.file,
            line=risk.line,
        )
        for risk in risks
    ]
    pii_findings = [
        Finding(
            key=f"data:pii:{item.file}:{item.line}",
            severity="error",
            message=f"PII en clair dans les logs : {item.value}",
            file=item.file,
            line=item.line,
        )
        for item in pii
    ]
    backup_findings: list[Finding] = []
    if status is None:
        backup_verdict = "not_run"
        backup_reason = "aucune sauvegarde vérifiée"
        backup_findings.append(
            Finding(
                key="data:backup:missing",
                severity="error",
                message="aucune sauvegarde vérifiée ou testée",
            )
        )
    elif not status.restore_tested:
        backup_verdict = "fail"
        backup_reason = "restauration non testée"
        backup_findings.append(
            Finding(
                key="data:backup:restore",
                severity="error",
                message="sauvegarde non testée par une restauration",
            )
        )
    elif not status.verified:
        backup_verdict = "fail"
        backup_reason = "sauvegarde non vérifiée"
        backup_findings.append(
            Finding(
                key="data:backup:verify",
                severity="error",
                message="sauvegarde non vérifiée",
            )
        )
    elif status.age_hours is not None and status.age_hours > 24:
        backup_verdict = "warn"
        backup_reason = f"sauvegarde ancienne ({status.age_hours:.1f} h)"
        backup_findings.append(
            Finding(
                key="data:backup:age",
                severity="warning",
                message=backup_reason,
            )
        )
    else:
        backup_verdict = "pass"
        backup_reason = "sauvegarde vérifiée et restauration testée"

    retention_findings: list[Finding] = []
    if retention_days is None or retention_days <= 0:
        retention_verdict = "warn"
        retention_reason = "rétention non définie"
        retention_findings.append(
            Finding(
                key="data:retention",
                severity="warning",
                message="rétention non définie",
            )
        )
    else:
        retention_verdict = "pass"
        retention_reason = f"rétention {retention_days} jour(s)"

    encryption_findings: list[Finding] = []
    if encrypted is not True:
        encryption_verdict = "warn"
        encryption_reason = "chiffrement absent"
        encryption_findings.append(
            Finding(
                key="data:encryption",
                severity="warning",
                message="chiffrement des données non déclaré",
            )
        )
    else:
        encryption_verdict = "pass"
        encryption_reason = "chiffrement déclaré"

    migration_verdict = "fail" if risks else ("pass" if migrations else "not_applicable")
    pii_verdict = "fail" if pii else ("pass" if logs else "not_applicable")
    controls = [
        ControlResult(
            key="migrations",
            verdict=migration_verdict,
            expected=bool(migrations),
            reason=(
                f"{len(risks)} migration(s) destructive(s)"
                if risks
                else "aucune migration destructive"
            ),
            evidence=evidence,
            findings=tuple(migration_findings),
            details={"migrations": len(migrations)},
        ),
        ControlResult(
            key="pii",
            verdict=pii_verdict,
            expected=bool(logs),
            reason=f"{len(pii)} PII détectée(s)" if pii else "aucune PII détectée",
            evidence=evidence,
            findings=tuple(pii_findings),
            details={"logs": len(logs)},
        ),
        ControlResult(
            key="backup",
            verdict=backup_verdict,
            expected=True,
            reason=backup_reason,
            evidence=evidence,
            findings=tuple(backup_findings),
            details={
                "age_hours": status.age_hours if status is not None else None,
                "verified": status.verified if status is not None else None,
                "restore_tested": status.restore_tested if status is not None else None,
            },
        ),
        ControlResult(
            key="retention",
            verdict=retention_verdict,
            expected=False,
            reason=retention_reason,
            evidence=evidence,
            findings=tuple(retention_findings),
            details={"retention_days": retention_days},
        ),
        ControlResult(
            key="encryption",
            verdict=encryption_verdict,
            expected=False,
            reason=encryption_reason,
            evidence=evidence,
            findings=tuple(encryption_findings),
            details={"encrypted": encrypted},
        ),
    ]
    evaluation = evaluate_gate(
        "data",
        controls,
        gate_name="Données",
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
    return DataGateResult(
        evaluation=evaluation,
        run=run,
        migrations=risks,
        pii=pii,
    )
