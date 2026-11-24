"""Post-reduction graph integrity validator."""

from __future__ import annotations

import networkx as nx

from knowledgereduce.models import IntegrityValidationError, LayerData, ValidationReport
from knowledgereduce.storage.base import layer_data_to_networkx


class IntegrityValidator:
    """Validates structural consistency, referential integrity, and telemetry of a LayerData."""

    def validate(self, layer_data: LayerData, *, strict: bool = False) -> ValidationReport:
        """Validate *layer_data* and return a ``ValidationReport``."""
        errors: list[str] = []
        warnings: list[str] = []

        entity_ids = [e.entity_id for e in layer_data.entities]
        claim_ids = [c.claim_id for c in layer_data.claims]
        relation_ids = [r.relation_id for r in layer_data.relations]
        conflict_ids = [cf.conflict_id for cf in layer_data.conflicts]

        if len(entity_ids) != len(set(entity_ids)):
            errors.append("Duplicate entity_id detected in layer.")
        if len(claim_ids) != len(set(claim_ids)):
            errors.append("Duplicate claim_id detected in layer.")
        if len(relation_ids) != len(set(relation_ids)):
            errors.append("Duplicate relation_id detected in layer.")
        if len(conflict_ids) != len(set(conflict_ids)):
            errors.append("Duplicate conflict_id detected in layer.")

        entity_set = set(entity_ids)
        node_set = entity_set | set(claim_ids)

        for rel in layer_data.relations:
            if rel.source_id not in node_set:
                errors.append(
                    f"Dangling relation {rel.relation_id!r}: source_id {rel.source_id!r} missing."
                )
            if rel.target_id not in node_set:
                errors.append(
                    f"Dangling relation {rel.relation_id!r}: target_id {rel.target_id!r} missing."
                )

        for clm in layer_data.claims:
            if clm.subject_id is not None and clm.subject_id not in entity_set:
                errors.append(
                    f"Claim {clm.claim_id!r} references missing subject_id {clm.subject_id!r}."
                )
            if clm.object_id is not None and clm.object_id not in entity_set:
                errors.append(
                    f"Claim {clm.claim_id!r} references missing object_id {clm.object_id!r}."
                )
            if not clm.evidence:
                warnings.append(f"Claim {clm.claim_id!r} has no Evidence provenance attached.")

        for ent in layer_data.entities:
            if not ent.evidence:
                warnings.append(f"Entity {ent.entity_id!r} has no Evidence provenance attached.")

        graph = layer_data_to_networkx(layer_data)
        isolated_count = len(list(nx.isolates(graph)))
        components = (
            nx.number_weakly_connected_components(graph) if graph.number_of_nodes() > 0 else 0
        )
        density = float(nx.density(graph)) if graph.number_of_nodes() > 1 else 0.0
        mean_quality = (
            round(
                sum(c.quality_score for c in layer_data.claims) / len(layer_data.claims),
                2,
            )
            if layer_data.claims
            else 0.0
        )

        metrics = {
            "sources": len(layer_data.sources),
            "entities": len(layer_data.entities),
            "claims": len(layer_data.claims),
            "relations": len(layer_data.relations),
            "conflicts": len(layer_data.conflicts),
            "open_conflicts": sum(1 for cf in layer_data.conflicts if cf.needs_review),
            "isolated_nodes": isolated_count,
            "connected_components": components,
            "edge_density": round(density, 6),
            "mean_quality_score": mean_quality,
        }

        report = ValidationReport(
            layer_id=layer_data.layer.layer_id,
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
        )
        if strict and not report.valid:
            raise IntegrityValidationError(
                f"Layer {layer_data.layer.layer_id!r} failed integrity validation: "
                + "; ".join(errors)
            )
        return report
