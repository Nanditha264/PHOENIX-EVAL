"""Dependency generator constructing directed cryptographic and architectural relationships between components.

Edge Semantics Invariant:
For every DependencyRelationship(source_component_id=u, target_component_id=v):
  u is the CALLER / CONSUMER / DEPENDENT
  v is the CALLEE / PROVIDER / PREREQUISITE
"""

from typing import Optional

from phoenix_eval.generator.seed_manager import SeedManager
from phoenix_eval.schemas.components import ComponentType, CryptographicComponent
from phoenix_eval.schemas.dependencies import (
    DependencyCriticality,
    DependencyRelationship,
    RelationshipType,
)


def _determine_relationship_type(
    source_type: ComponentType,
    target_type: ComponentType,
) -> RelationshipType:
    """Infer the most realistic cryptographic/architectural relationship based on component types."""
    if target_type == ComponentType.HARDWARE_SECURITY_MODULE:
        return RelationshipType.HARDWARE_DEPENDENCY
    if target_type == ComponentType.DATABASE:
        return RelationshipType.STORES_DATA_IN
    if target_type == ComponentType.CERTIFICATE_AUTHORITY:
        return RelationshipType.CERTIFICATE_ISSUED_BY
    if target_type == ComponentType.KEY_MANAGEMENT_SERVICE:
        return RelationshipType.EXCHANGES_KEYS_WITH
    if target_type == ComponentType.MESSAGE_BROKER:
        return RelationshipType.ENCRYPTS_WITH
    if target_type == ComponentType.CRYPTOGRAPHIC_LIBRARY:
        return RelationshipType.USES_LIBRARY
    return RelationshipType.CALLS


def generate_dependencies(
    components: list[CryptographicComponent],
    seed_mgr: SeedManager,
    density_factor: float = 1.0,
    create_cycle: bool = False,
    hidden_dependency_target: Optional[str] = None,
) -> list[DependencyRelationship]:
    """Synthesize directed dependency relationships connecting enterprise components.

    Components are organized by architectural tiers:
      Tier 0 (Clients / Edge) -> Tier 1 (Microservices) -> Tier 2 (Brokers) -> Tier 3 (HSM/DB/CAs).
    Callers (source) point to prerequisites (target).
    """
    if len(components) < 2:
        return []

    # Partition components by tier
    tiered: dict[int, list[CryptographicComponent]] = {0: [], 1: [], 2: [], 3: []}
    for c in components:
        tier = c.metadata.get("tier", 1)
        tiered.setdefault(tier, []).append(c)

    dependencies: list[DependencyRelationship] = []
    edge_counter = 0

    def add_edge(
        src: CryptographicComponent,
        tgt: CryptographicComponent,
        rel_type: Optional[RelationshipType] = None,
        criticality: DependencyCriticality = DependencyCriticality.CRITICAL,
        desc: str = "",
    ) -> None:
        nonlocal edge_counter
        if src.component_id == tgt.component_id:
            return
        # Avoid duplicate edges
        if any(
            d.source_component_id == src.component_id and d.target_component_id == tgt.component_id
            for d in dependencies
        ):
            return

        edge_counter += 1
        edge_id = f"edge-{src.component_id.replace('comp-', '')}-to-{tgt.component_id.replace('comp-', '')}"
        # Ensure edge_id is valid
        if len(edge_id) > 64:
            edge_id = f"edge-{edge_counter:03d}-{src.component_id[:8]}-{tgt.component_id[:8]}"

        rtype = rel_type or _determine_relationship_type(src.component_type, tgt.component_type)
        dependencies.append(
            DependencyRelationship(
                edge_id=edge_id,
                source_component_id=src.component_id,
                target_component_id=tgt.component_id,
                relationship_type=rtype,
                confidence=1.0,
                criticality=criticality,
                description=desc or f"{src.component_name} depends on {tgt.component_name}",
                evidence_references=[],  # Populated during evidence generation
            )
        )

    # 1. Connect Tier 0 (Edge/Clients) to Tier 1 (Microservices)
    t0 = tiered.get(0, [])
    t1 = tiered.get(1, [])
    t2 = tiered.get(2, [])
    t3 = tiered.get(3, [])

    if t0 and t1:
        for client in t0:
            target_svc = seed_mgr.choice(t1)
            add_edge(client, target_svc, RelationshipType.CALLS, DependencyCriticality.CRITICAL)

    # 2. Connect Tier 1 (Microservices) to Tier 3 (HSM, KMS, DB) or Tier 2 (Brokers)
    if t1:
        for svc in t1:
            if t3:
                # Every service typically has at least one foundational prerequisite (DB, HSM, CA)
                sink = seed_mgr.choice(t3)
                add_edge(svc, sink, None, DependencyCriticality.CRITICAL)
            if t2 and seed_mgr.uniform(0.0, 1.0) < 0.6 * density_factor:
                broker = seed_mgr.choice(t2)
                add_edge(svc, broker, RelationshipType.ENCRYPTS_WITH, DependencyCriticality.HIGH)

    # 3. Connect Tier 2 (Brokers) to Tier 3 (Sinks)
    if t2 and t3:
        for broker in t2:
            sink = seed_mgr.choice(t3)
            add_edge(broker, sink, None, DependencyCriticality.HIGH)

    # 4. Intra-tier or cross-tier extra edges based on density
    all_comps = list(components)
    extra_edges_count = int(len(components) * 0.4 * density_factor)
    for _ in range(extra_edges_count):
        c1 = seed_mgr.choice(all_comps)
        c2 = seed_mgr.choice(all_comps)
        tier1 = c1.metadata.get("tier", 1)
        tier2 = c2.metadata.get("tier", 1)
        # Preserve DAG direction: c1 (lower tier / caller) calls c2 (higher tier / prerequisite)
        if tier1 < tier2:
            add_edge(c1, c2, None, DependencyCriticality.HIGH)

    # 5. Hidden downstream dependency injection (if requested for T01)
    if hidden_dependency_target and t1 and t3:
        target_comp = next(
            (c for c in components if c.component_id == hidden_dependency_target), None
        )
        if target_comp:
            # Pick a middle tier service and link it to this hidden target
            middle_svc = seed_mgr.choice(t1)
            add_edge(
                middle_svc,
                target_comp,
                None,
                DependencyCriticality.CRITICAL,
                "Indirect downstream dependency.",
            )

    # 6. Intentional Cycle Generation (if requested for T06 or adversarial cycle pairs)
    if create_cycle and len(dependencies) >= 2:
        # Create a reverse edge from a higher tier back to a lower tier
        # e.g. from a Tier 3 sink or Tier 1 service back to a Tier 0 edge or Tier 1 caller
        src_for_cycle = dependencies[0].target_component_id
        tgt_for_cycle = dependencies[0].source_component_id
        src_comp = next((c for c in components if c.component_id == src_for_cycle), None)
        tgt_comp = next((c for c in components if c.component_id == tgt_for_cycle), None)
        if src_comp and tgt_comp:
            add_edge(
                src_comp,
                tgt_comp,
                RelationshipType.CALLS,
                DependencyCriticality.CRITICAL,
                "Circular dependency back-edge.",
            )

    return dependencies
