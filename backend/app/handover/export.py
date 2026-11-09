"""Handover export generator: Markdown, JSON, and print-optimized HTML.

Applies pre-export clearance firewall filtering per viewer role.
Includes:
- Version cryptographic hash and sign-off signatures.
- Completeness scorecard table.
- Claims organized by section with grounded citations as footnotes.
- Standalone HTML print stylesheets for zero-dependency "Print to PDF".
"""

from __future__ import annotations

import html
import logging
from typing import Any

from sqlmodel import Session, select

from app.db import audit
from app.errors import AppError
from app.handover.views import mask_scorecard
from app.models import Handover, HandoverVersion, Signoff, User
from app.policy import effective_clearance, mask_claim

logger = logging.getLogger("relayops.handover.export")


def get_export_snapshot(session: Session, handover_id: str) -> HandoverVersion:
    """Retrieve the latest HandoverVersion for export."""
    # Find latest version with dual signoffs, or latest version
    signoffs = session.exec(select(Signoff).where(Signoff.handover_id == handover_id)).all()
    roles_by_v: dict[int, set[str]] = {}
    for s in signoffs:
        roles_by_v.setdefault(s.version, set()).add(s.role)

    signed_vs = [v for v, r in roles_by_v.items() if "outgoing" in r and "lead" in r]
    if signed_vs:
        target_v = max(signed_vs)
        hv = session.exec(
            select(HandoverVersion).where(
                HandoverVersion.handover_id == handover_id,
                HandoverVersion.version == target_v,
            )
        ).first()
        if hv:
            return hv

    # Fallback to latest snapshot
    hv = session.exec(
        select(HandoverVersion)
        .where(HandoverVersion.handover_id == handover_id)
        .order_by(HandoverVersion.version.desc())
        .limit(1)
    ).first()

    if not hv:
        raise AppError("NOT_FOUND", "No handover version snapshot found to export", status_code=404)
    return hv


def export_handover(
    session: Session,
    handover_id: str,
    user: User,
    *,
    format: str = "json",
) -> tuple[str | dict[str, Any], str]:
    """Export handover in Markdown, HTML, or JSON format filtered by viewer clearance."""
    handover = session.get(Handover, handover_id)
    if not handover:
        raise AppError("NOT_FOUND", "Handover not found", status_code=404)

    hv = get_export_snapshot(session, handover_id)
    snapshot = hv.snapshot or {}

    # Clearance filtering: Apply strict ABAC mask to all claims
    eff_clearance = effective_clearance(user)
    viewer_ctx = {"id": user.id, "role": user.role, "clearance": eff_clearance}

    raw_claims = snapshot.get("claims", [])
    filtered_claims: list[dict[str, Any]] = []
    for c in raw_claims:
        masked = mask_claim(c, viewer_ctx)
        # If masked, ensure no sensitive text survives
        filtered_claims.append(masked)

    # Fetch signatures for verification block
    signoffs = session.exec(
        select(Signoff).where(Signoff.handover_id == handover_id, Signoff.version == hv.version)
    ).all()

    scorecard = snapshot.get("scorecard", {})
    plan_items = snapshot.get("plan_items", [])

    # Audit export request
    audit(
        session,
        actor_id=user.id,
        action="handover_exported",
        target_type="handover",
        target_id=handover_id,
        payload={"format": format, "version": hv.version, "clearance": eff_clearance},
    )

    clean_format = format.lower().strip()
    masked_scorecard = mask_scorecard(scorecard, raw_claims, eff_clearance, user.role)

    # 1. JSON Export
    if clean_format == "json":
        export_dict = {
            "handover_id": handover_id,
            "project_id": handover.project_id,
            "version": hv.version,
            "hash": hv.hash,
            "prev_hash": hv.prev_hash,
            "exported_for": user.email,
            "viewer_clearance": eff_clearance,
            "status": handover.status,
            "scorecard": masked_scorecard,
            "claims": filtered_claims,
            "plan_items": plan_items,
            "signatures": [
                {
                    "user_id": s.user_id,
                    "role": s.role,
                    "signature": s.signature,
                    "signed_at": s.signed_at.isoformat(),
                    "comment": s.comment,
                }
                for s in signoffs
            ],
        }
        return export_dict, "application/json"

    # 2. Markdown Export
    if clean_format in ("md", "markdown"):
        md_lines = [
            f"# RelayOps Engineering Handover: {handover.project_id.upper()}",
            f"**Version**: v{hv.version}  ",
            f"**Cryptographic Hash**: `{hv.hash}`  ",
            f"**Status**: {handover.status.upper()}  ",
            f"**Viewer Clearance**: Level {eff_clearance} ({user.role})  ",
            "",
            "---",
            "",
            "## Verification Scorecard",
            f"- **Completeness Score**: {scorecard.get('completeness_score', 0)} / 100",
            f"- **Verified Claims**: {scorecard.get('verified_claims_count', len(filtered_claims))}",
            f"- **Rejected Claims**: {scorecard.get('rejected_claims_count', 0)}",
            f"- **Open Ambiguities**: {scorecard.get('open_ambiguities_count', 0)}",
            "",
            "---",
            "",
            "## Architectural Decisions & Verified Runbooks",
            "",
        ]

        footnotes: list[str] = []
        fn_idx = 1

        # Group claims by section
        sections: dict[str, list[dict[str, Any]]] = {}
        for c in filtered_claims:
            sec = c.get("section", "general").title()
            sections.setdefault(sec, []).append(c)

        for sec, s_claims in sections.items():
            md_lines.append(f"### {sec}")
            for c in s_claims:
                text = c.get("text", "")
                status_badge = f"[{c.get('status', 'draft').upper()}]"
                evidence = c.get("evidence", [])

                fn_refs = []
                if not c.get("is_masked") and evidence:
                    for ev in evidence:
                        uri = ev.get("source_uri", "#")
                        snip = ev.get("snippet", "Evidence reference")
                        fn_num = fn_idx
                        fn_idx += 1
                        footnotes.append(f'[^{fn_num}]: [{uri}]({uri}) - "{snip}"')
                        fn_refs.append(f"[^{fn_num}]")

                ref_str = " ".join(fn_refs)
                md_lines.append(f"- **{status_badge}** {text} {ref_str}")
            md_lines.append("")

        # 30-Day Plan section
        if plan_items:
            md_lines.extend(["---", "", "## 30-Day Onboarding Plan", ""])
            for p in plan_items:
                bucket = p.get("day_bucket", "d1_7").upper()
                p_status = p.get("status", "todo").upper()
                p_desc = p.get("description", "")
                md_lines.append(f"- **[{bucket}] {p.get('title', '')}** ({p_status}): {p_desc}")
            md_lines.append("")

        # Sign-off Signatures
        md_lines.extend(["---", "", "## Dual Sign-off Signatures", ""])
        if signoffs:
            for s in signoffs:
                sig_short = s.signature[:16]
                signed_time = s.signed_at.isoformat()
                role_label = s.role.upper()
                md_lines.append(
                    f"- **{role_label}** (User `{s.user_id}`): " f"Signed `{sig_short}...` at {signed_time}"
                )
                if s.comment:
                    md_lines.append(f'  *Note*: "{s.comment}"')
        else:
            md_lines.append("*No signatures recorded yet.*")
        md_lines.append("")

        # Footnotes list
        if footnotes:
            md_lines.extend(["---", "", "## Evidence Footnotes & Citations", ""])
            md_lines.extend(footnotes)
            md_lines.append("")

        return "\n".join(md_lines), "text/markdown; charset=utf-8"

    # 3. HTML Export with Print-to-PDF styles
    if clean_format == "html":
        # Group claims by section
        sections: dict[str, list[dict[str, Any]]] = {}
        for c in filtered_claims:
            sec = c.get("section", "general").title()
            sections.setdefault(sec, []).append(c)

        footnotes_html: list[str] = []
        fn_idx = 1

        claims_body_html = ""
        for sec, s_claims in sections.items():
            claims_body_html += f"<h3>{html.escape(sec)}</h3><ul>"
            for c in s_claims:
                text = html.escape(c.get("text", ""))
                c_status = html.escape(c.get("status", "draft"))
                evidence = c.get("evidence", [])

                fn_refs = []
                if not c.get("is_masked") and evidence:
                    for ev in evidence:
                        uri = html.escape(str(ev.get("source_uri", "#")))
                        snip = html.escape(str(ev.get("snippet", "Evidence reference")))
                        fn_num = fn_idx
                        fn_idx += 1
                        footnotes_html.append(
                            f'<div class="footnote" id="fn-{fn_num}">'
                            f'<sup>{fn_num}</sup> <a href="{uri}">{uri}</a> &mdash; <em>"{snip}"</em>'
                            f"</div>"
                        )
                        fn_refs.append(f'<sup><a href="#fn-{fn_num}">[{fn_num}]</a></sup>')

                ref_html = " ".join(fn_refs)
                claims_body_html += (
                    f'<li><span class="badge badge-{c_status}">{c_status}</span> {text} {ref_html}</li>'
                )
            claims_body_html += "</ul>"

        plan_html = ""
        if plan_items:
            plan_html = "<h2>30-Day Onboarding Plan</h2><ul>"
            for p in plan_items:
                b = html.escape(p.get("day_bucket", "").upper())
                t = html.escape(p.get("title", ""))
                d = html.escape(p.get("description", ""))
                st = html.escape(p.get("status", "todo").upper())
                plan_html += f"<li><strong>[{b}] {t}</strong> ({st})<br/><small>{d}</small></li>"
            plan_html += "</ul>"

        sig_html = "<h2>Dual Sign-Off Signatures</h2><ul>"
        for s in signoffs:
            sig_html += (
                f"<li><strong>{html.escape(s.role.upper())}</strong>: "
                f"<code>{html.escape(s.signature[:16])}...</code> "
                f"&mdash; {html.escape(s.signed_at.isoformat())}"
                f"{f' <br/><em>{html.escape(s.comment)}</em>' if s.comment else ''}</li>"
            )
        sig_html += "</ul>"

        fn_section_html = ""
        if footnotes_html:
            fn_section_html = "<h2>Evidence Footnotes</h2>" + "".join(footnotes_html)

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>RelayOps Handover Document - {html.escape(handover.project_id)}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.6;
      color: #1e293b;
      max-width: 850px;
      margin: 40px auto;
      padding: 0 20px;
    }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
    h2 {{ color: #1e293b; margin-top: 32px; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; }}
    h3 {{ color: #334155; margin-top: 20px; }}
    .meta-box {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 16px;
      margin-bottom: 24px;
      font-size: 0.9em;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 6px;
      font-size: 0.75rem;
      font-weight: 600;
      border-radius: 4px;
      text-transform: uppercase;
    }}
    .badge-accepted {{ background: #dcfce7; color: #166534; }}
    .badge-edited {{ background: #e0e7ff; color: #3730a3; }}
    .badge-rejected {{ background: #fee2e2; color: #991b1b; }}
    .badge-draft {{ background: #f1f5f9; color: #475569; }}
    .footnote {{
      font-size: 0.85em;
      color: #475569;
      margin-bottom: 8px;
    }}
    code {{
      font-family: "JetBrains Mono", Consolas, monospace;
      background: #f1f5f9;
      padding: 2px 4px;
      border-radius: 3px;
      font-size: 0.9em;
    }}
    @media print {{
      body {{ max-width: 100%; margin: 0; padding: 15mm; font-size: 11pt; }}
      h1, h2 {{ page-break-after: avoid; }}
      ul, li {{ page-break-inside: avoid; }}
      a {{ text-decoration: none; color: #0f172a; }}
      .meta-box {{ border: 1px solid #94a3b8; }}
      @page {{ margin: 15mm; }}
    }}
  </style>
</head>
<body>
  <h1>Engineering Handover: {html.escape(handover.project_id.upper())}</h1>
  <div class="meta-box">
    <div><strong>Version:</strong> v{hv.version}</div>
    <div><strong>Cryptographic Hash:</strong> <code>{html.escape(hv.hash)}</code></div>
    <div><strong>Status:</strong> {html.escape(handover.status.upper())}</div>
    <div><strong>Viewer Clearance:</strong> Level {eff_clearance} ({html.escape(user.role)})</div>
  </div>

  <h2>Verification Scorecard</h2>
  <ul>
    <li><strong>Completeness Score:</strong> {scorecard.get("completeness_score", 0)} / 100</li>
    <li><strong>Verified Claims:</strong> {scorecard.get("verified_claims_count", len(filtered_claims))}</li>
    <li><strong>Rejected Claims:</strong> {scorecard.get("rejected_claims_count", 0)}</li>
    <li><strong>Open Ambiguities:</strong> {scorecard.get("open_ambiguities_count", 0)}</li>
  </ul>

  <h2>Verified Architectural Decisions & Runbooks</h2>
  {claims_body_html}

  {plan_html}

  {sig_html}

  {fn_section_html}
</body>
</html>"""
        return html_doc, "text/html; charset=utf-8"

    raise AppError(
        "BAD_REQUEST",
        f"Unsupported export format '{format}'. Supported formats: json, md, html",
        status_code=400,
    )
