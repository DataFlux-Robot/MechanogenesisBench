"""Demand-conditioned two-generation microfactory reference semantics.

The task is deliberately larger than the fixture conformance slice.  A model
must emit a complete product and capital plan: demand beliefs, a low-speed
mobility product, a mechanical assembly fixture, a PCB test fixture and a
battery calibration station.  The operator bundle made in generation zero is
the exact production input to generation one.

This module owns deterministic simulation semantics.  It does not label
synthetic preference outcomes as real human endorsement and it does not claim
hardware evidence.  Those stronger claims require separately registered
adapters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from .canonical import digest
from .errors import SchemaError


PLAN_SCHEMA = "demand-microfactory-plan/v1"
OPERATOR_SCHEMA = "microfactory-operator-bundle/v1"
EXECUTION_SCHEMA = "demand-microfactory-execution/v1"
PPM = 1_000_000
DEMAND_ATTRIBUTES = (
    "accessibility",
    "cargo",
    "range",
    "repairability",
    "weather",
)
NOVEL_AFFORDANCES = {
    "none",
    "guided_docking",
    "self_leveling_cargo",
    "tool_free_service",
}
FACTORY_CAPITAL_COST_MILLIUSD = {
    "locator_span_mm": 30_000,
    "fixture_calibration_sample": 200_000,
    "pcb_pogo_pin": 50_000,
    "pcb_test_vector": 5_000,
    "battery_calibration_point": 200_000,
}
PRODUCT_UNIT_COST_MILLIUSD = {
    "base_platform": 400_000,
    "battery_wh": 180,
    "motor_power_w": 80,
    "cargo_l": 500,
    "modular_port": 20_000,
    "non_none_novel_affordance": 120_000,
}


def _nat(value: object, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{field} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        suffix = f"..{maximum}" if maximum is not None else "+"
        raise SchemaError(f"{field} must lie in {minimum}{suffix}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field} must be nonempty text")
    return value


def _hash(value: object, field: str) -> str:
    text = _text(value, field)
    if not (
        text.startswith("sha256:")
        and len(text) == 71
        and all(character in "0123456789abcdef" for character in text[7:])
    ):
        raise SchemaError(f"{field} must be a canonical sha256 digest")
    return text


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise SchemaError(f"{field} must be an object")
    return value


def _clamp(value: int, lower: int = 0, upper: int = PPM) -> int:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class OperatorBundle:
    schema_version: str
    generation: int
    mechanical_position_error_um: int
    pcb_escape_rate_ppm: int
    battery_calibration_error_mv: int
    parent_bundle_hash: str | None
    bundle_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("bundle_hash")
        return value

    @classmethod
    def create(
        cls,
        *,
        generation: int,
        mechanical_position_error_um: int,
        pcb_escape_rate_ppm: int,
        battery_calibration_error_mv: int,
        parent_bundle_hash: str | None,
    ) -> "OperatorBundle":
        unsigned = {
            "schema_version": OPERATOR_SCHEMA,
            "generation": generation,
            "mechanical_position_error_um": mechanical_position_error_um,
            "pcb_escape_rate_ppm": pcb_escape_rate_ppm,
            "battery_calibration_error_mv": battery_calibration_error_mv,
            "parent_bundle_hash": parent_bundle_hash,
        }
        result = cls(**unsigned, bundle_hash=digest(unsigned))
        result.validate()
        return result

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "OperatorBundle":
        result = cls(
            schema_version=_text(raw.get("schema_version"), "operator.schema_version"),
            generation=_nat(raw.get("generation"), "operator.generation"),
            mechanical_position_error_um=_nat(
                raw.get("mechanical_position_error_um"),
                "operator.mechanical_position_error_um",
                minimum=1,
            ),
            pcb_escape_rate_ppm=_nat(
                raw.get("pcb_escape_rate_ppm"),
                "operator.pcb_escape_rate_ppm",
                maximum=PPM,
            ),
            battery_calibration_error_mv=_nat(
                raw.get("battery_calibration_error_mv"),
                "operator.battery_calibration_error_mv",
                minimum=1,
            ),
            parent_bundle_hash=(
                None
                if raw.get("parent_bundle_hash") is None
                else _hash(raw.get("parent_bundle_hash"), "operator.parent_bundle_hash")
            ),
            bundle_hash=_hash(raw.get("bundle_hash"), "operator.bundle_hash"),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if self.schema_version != OPERATOR_SCHEMA:
            raise SchemaError("unsupported microfactory operator schema")
        _nat(self.generation, "operator.generation")
        _nat(
            self.mechanical_position_error_um,
            "operator.mechanical_position_error_um",
            minimum=1,
        )
        _nat(self.pcb_escape_rate_ppm, "operator.pcb_escape_rate_ppm", maximum=PPM)
        _nat(
            self.battery_calibration_error_mv,
            "operator.battery_calibration_error_mv",
            minimum=1,
        )
        if self.parent_bundle_hash is not None:
            _hash(self.parent_bundle_hash, "operator.parent_bundle_hash")
        if self.bundle_hash != digest(self.unsigned_dict()):
            raise SchemaError("operator bundle hash mismatch")


@dataclass(frozen=True)
class DemandBelief:
    attribute_weights_ppm: tuple[tuple[str, int], ...]
    outcome_forecast_ppm: tuple[tuple[str, int], ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "DemandBelief":
        weights_raw = _mapping(raw.get("attribute_weights_ppm"), "demand.attribute_weights_ppm")
        if set(weights_raw) != set(DEMAND_ATTRIBUTES):
            raise SchemaError("demand belief must cover all five demand attributes")
        weights = tuple(
            (name, _nat(weights_raw[name], f"demand.attribute_weights_ppm.{name}", maximum=PPM))
            for name in DEMAND_ATTRIBUTES
        )
        outcomes_raw = _mapping(raw.get("outcome_forecast_ppm"), "demand.outcome_forecast_ppm")
        if set(outcomes_raw) != {"reject", "adopt", "delight"}:
            raise SchemaError("outcome forecast must contain reject/adopt/delight")
        outcomes = tuple(
            (name, _nat(outcomes_raw[name], f"demand.outcome_forecast_ppm.{name}", maximum=PPM))
            for name in ("reject", "adopt", "delight")
        )
        if sum(value for _, value in weights) != PPM:
            raise SchemaError("demand attribute weights must sum to 1,000,000 ppm")
        if sum(value for _, value in outcomes) != PPM:
            raise SchemaError("outcome forecast must sum to 1,000,000 ppm")
        return cls(weights, outcomes)

    @property
    def weight_map(self) -> dict[str, int]:
        return dict(self.attribute_weights_ppm)

    @property
    def outcome_map(self) -> dict[str, int]:
        return dict(self.outcome_forecast_ppm)


@dataclass(frozen=True)
class ProductPlan:
    wheelbase_mm: int
    track_mm: int
    battery_wh: int
    motor_power_w: int
    max_speed_mm_s: int
    payload_kg: int
    cargo_l: int
    seat_height_mm: int
    ramp_slope_milli: int
    weather_seal_ppm: int
    diagnostic_coverage_ppm: int
    modular_ports: int
    novel_affordance: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ProductPlan":
        affordance = _text(raw.get("novel_affordance"), "product.novel_affordance")
        if affordance not in NOVEL_AFFORDANCES:
            raise SchemaError("product.novel_affordance is outside the registry")
        return cls(
            wheelbase_mm=_nat(raw.get("wheelbase_mm"), "product.wheelbase_mm", minimum=1000, maximum=2200),
            track_mm=_nat(raw.get("track_mm"), "product.track_mm", minimum=700, maximum=1400),
            battery_wh=_nat(raw.get("battery_wh"), "product.battery_wh", minimum=500, maximum=4000),
            motor_power_w=_nat(raw.get("motor_power_w"), "product.motor_power_w", minimum=500, maximum=5000),
            max_speed_mm_s=_nat(raw.get("max_speed_mm_s"), "product.max_speed_mm_s", minimum=1500, maximum=8000),
            payload_kg=_nat(raw.get("payload_kg"), "product.payload_kg", minimum=20, maximum=250),
            cargo_l=_nat(raw.get("cargo_l"), "product.cargo_l", minimum=20, maximum=500),
            seat_height_mm=_nat(raw.get("seat_height_mm"), "product.seat_height_mm", minimum=250, maximum=650),
            ramp_slope_milli=_nat(raw.get("ramp_slope_milli"), "product.ramp_slope_milli", minimum=20, maximum=250),
            weather_seal_ppm=_nat(raw.get("weather_seal_ppm"), "product.weather_seal_ppm", maximum=PPM),
            diagnostic_coverage_ppm=_nat(raw.get("diagnostic_coverage_ppm"), "product.diagnostic_coverage_ppm", maximum=PPM),
            modular_ports=_nat(raw.get("modular_ports"), "product.modular_ports", maximum=8),
            novel_affordance=affordance,
        )

    @property
    def estimated_unit_cost_milliusd(self) -> int:
        """Registered low-volume BOM and assembly cost in milli-USD."""

        return (
            PRODUCT_UNIT_COST_MILLIUSD["base_platform"]
            + self.battery_wh * PRODUCT_UNIT_COST_MILLIUSD["battery_wh"]
            + self.motor_power_w * PRODUCT_UNIT_COST_MILLIUSD["motor_power_w"]
            + self.cargo_l * PRODUCT_UNIT_COST_MILLIUSD["cargo_l"]
            + self.modular_ports * PRODUCT_UNIT_COST_MILLIUSD["modular_port"]
            + (
                PRODUCT_UNIT_COST_MILLIUSD["non_none_novel_affordance"]
                if self.novel_affordance != "none"
                else 0
            )
        )


@dataclass(frozen=True)
class FactoryInvestment:
    locator_span_mm: int
    fixture_calibration_samples: int
    pcb_pogo_pins: int
    pcb_test_vectors: int
    battery_calibration_points: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "FactoryInvestment":
        return cls(
            locator_span_mm=_nat(raw.get("locator_span_mm"), "factory.locator_span_mm", minimum=100, maximum=800),
            fixture_calibration_samples=_nat(raw.get("fixture_calibration_samples"), "factory.fixture_calibration_samples", minimum=1, maximum=100),
            pcb_pogo_pins=_nat(raw.get("pcb_pogo_pins"), "factory.pcb_pogo_pins", minimum=10, maximum=500),
            pcb_test_vectors=_nat(raw.get("pcb_test_vectors"), "factory.pcb_test_vectors", minimum=10, maximum=5000),
            battery_calibration_points=_nat(raw.get("battery_calibration_points"), "factory.battery_calibration_points", minimum=2, maximum=100),
        )

    @property
    def capital_cost_milliusd(self) -> int:
        return (
            self.locator_span_mm
            * FACTORY_CAPITAL_COST_MILLIUSD["locator_span_mm"]
            + self.fixture_calibration_samples
            * FACTORY_CAPITAL_COST_MILLIUSD["fixture_calibration_sample"]
            + self.pcb_pogo_pins
            * FACTORY_CAPITAL_COST_MILLIUSD["pcb_pogo_pin"]
            + self.pcb_test_vectors
            * FACTORY_CAPITAL_COST_MILLIUSD["pcb_test_vector"]
            + self.battery_calibration_points
            * FACTORY_CAPITAL_COST_MILLIUSD["battery_calibration_point"]
        )


@dataclass(frozen=True)
class MicrofactoryPlan:
    schema_version: str
    generation: int
    input_operator_bundle_hash: str
    demand_belief: DemandBelief
    product: ProductPlan
    factory: FactoryInvestment
    hypothesis: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "MicrofactoryPlan":
        schema = _text(raw.get("schema_version"), "plan.schema_version")
        if schema != PLAN_SCHEMA:
            raise SchemaError("unsupported demand microfactory plan schema")
        return cls(
            schema_version=schema,
            generation=_nat(raw.get("generation"), "plan.generation"),
            input_operator_bundle_hash=_hash(
                raw.get("input_operator_bundle_hash"),
                "plan.input_operator_bundle_hash",
            ),
            demand_belief=DemandBelief.from_mapping(
                _mapping(raw.get("demand_belief"), "plan.demand_belief")
            ),
            product=ProductPlan.from_mapping(
                _mapping(raw.get("product"), "plan.product")
            ),
            factory=FactoryInvestment.from_mapping(
                _mapping(raw.get("factory"), "plan.factory")
            ),
            hypothesis=_text(raw.get("hypothesis"), "plan.hypothesis"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generation": self.generation,
            "input_operator_bundle_hash": self.input_operator_bundle_hash,
            "demand_belief": {
                "attribute_weights_ppm": self.demand_belief.weight_map,
                "outcome_forecast_ppm": self.demand_belief.outcome_map,
            },
            "product": asdict(self.product),
            "factory": asdict(self.factory),
            "hypothesis": self.hypothesis,
        }


@dataclass(frozen=True)
class MicrofactoryExecution:
    schema_version: str
    generation: int
    plan_hash: str
    parent_world_hash: str
    child_world_hash: str
    input_operator: OperatorBundle
    output_operator: OperatorBundle
    capital_cost_milliusd: int
    product_cost_milliusd: int
    total_cost_milliusd: int
    product_hash: str
    product_metrics: tuple[tuple[str, int | bool | str], ...]
    construction_receipts: tuple[dict[str, object], ...]
    execution_hash: str

    def unsigned_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generation": self.generation,
            "plan_hash": self.plan_hash,
            "parent_world_hash": self.parent_world_hash,
            "child_world_hash": self.child_world_hash,
            "input_operator": asdict(self.input_operator),
            "output_operator": asdict(self.output_operator),
            "capital_cost_milliusd": self.capital_cost_milliusd,
            "product_cost_milliusd": self.product_cost_milliusd,
            "total_cost_milliusd": self.total_cost_milliusd,
            "product_hash": self.product_hash,
            "product_metrics": dict(self.product_metrics),
            "construction_receipts": list(self.construction_receipts),
        }

    @property
    def metrics(self) -> dict[str, int | bool | str]:
        return dict(self.product_metrics)


def initial_operator_from_world(world: Mapping[str, object]) -> OperatorBundle:
    raw = _mapping(world.get("initial_operator_bundle"), "world.initial_operator_bundle")
    return OperatorBundle.from_mapping(raw)


def infer_demand_weights(observations: Sequence[Mapping[str, object]]) -> dict[str, int]:
    """Open baseline estimator from aggregate pairwise-choice evidence."""

    wins = {name: 1 for name in DEMAND_ATTRIBUTES}
    for index, raw in enumerate(observations):
        preferred = _text(raw.get("preferred"), f"observations[{index}].preferred")
        other = _text(raw.get("other"), f"observations[{index}].other")
        if preferred not in wins or other not in wins or preferred == other:
            raise SchemaError("demand comparison names invalid attributes")
        count = _nat(raw.get("count"), f"observations[{index}].count", minimum=1)
        wins[preferred] += count
    total = sum(wins.values())
    allocated: dict[str, int] = {}
    remaining = PPM
    for name in DEMAND_ATTRIBUTES[:-1]:
        value = wins[name] * PPM // total
        allocated[name] = value
        remaining -= value
    allocated[DEMAND_ATTRIBUTES[-1]] = remaining
    return allocated


def build_output_operator(
    input_operator: OperatorBundle,
    investment: FactoryInvestment,
    *,
    generation: int,
) -> OperatorBundle:
    mechanical = max(
        40,
        input_operator.mechanical_position_error_um * 3 // 10
        + 300
        - investment.locator_span_mm // 2
        - investment.fixture_calibration_samples * 3,
    )
    pcb_escape = max(
        300,
        input_operator.pcb_escape_rate_ppm // 4
        + 8000
        - investment.pcb_test_vectors * 2
        - investment.pcb_pogo_pins * 8,
    )
    battery_error = max(
        3,
        input_operator.battery_calibration_error_mv // 3
        + 30
        - investment.battery_calibration_points // 2,
    )
    return OperatorBundle.create(
        generation=generation,
        mechanical_position_error_um=mechanical,
        pcb_escape_rate_ppm=pcb_escape,
        battery_calibration_error_mv=battery_error,
        parent_bundle_hash=input_operator.bundle_hash,
    )


def product_metrics(
    product: ProductPlan,
    operator: OperatorBundle,
    *,
    disturbance: Mapping[str, object] | None = None,
) -> dict[str, int | bool | str]:
    disturbance = disturbance or {}
    surface_error = _nat(
        disturbance.get("surface_error_um", 0), "disturbance.surface_error_um"
    )
    pcb_shift = _nat(
        disturbance.get("pcb_escape_shift_ppm", 0),
        "disturbance.pcb_escape_shift_ppm",
        maximum=PPM,
    )
    battery_shift = _nat(
        disturbance.get("battery_error_shift_mv", 0),
        "disturbance.battery_error_shift_mv",
    )
    assembly_error = (
        operator.mechanical_position_error_um
        + surface_error
        + max(0, 1100 - product.track_mm) // 2
    )
    complexity_penalty = product.modular_ports * 700 + (
        2500 if product.novel_affordance != "none" else 0
    )
    electronics_reliability = _clamp(
        PPM
        - operator.pcb_escape_rate_ppm
        - pcb_shift
        - complexity_penalty
        + product.diagnostic_coverage_ppm // 20
    )
    calibrated_battery_error = operator.battery_calibration_error_mv + battery_shift
    vehicle_mass_kg = 38 + product.battery_wh // 120 + product.cargo_l // 40
    range_m = max(
        0,
        product.battery_wh * 25
        - product.payload_kg * 45
        - calibrated_battery_error * 20,
    )
    stopping_distance_mm = product.max_speed_mm_s**2 // 7000
    stability_margin_milli = (
        product.track_mm * 1000
        - product.seat_height_mm * 800
        - product.max_speed_mm_s * 40
        - assembly_error * 100
    )
    physical_pass = bool(
        assembly_error <= 1000
        and electronics_reliability >= 965_000
        and calibrated_battery_error <= 180
        and range_m >= 12_000
        and stopping_distance_mm <= 8_000
        and stability_margin_milli >= 150_000
    )
    accessibility = _clamp(
        PPM
        - abs(product.seat_height_mm - 340) * 2800
        - product.ramp_slope_milli * 1200
    )
    cargo = _clamp(product.cargo_l * 2500 + product.payload_kg * 3500)
    range_score = _clamp(range_m * 20)
    repairability = _clamp(
        product.modular_ports * 115_000 + product.diagnostic_coverage_ppm * 55 // 100
    )
    weather = product.weather_seal_ppm
    physical_quality = _clamp(
        electronics_reliability
        - assembly_error * 180
        - calibrated_battery_error * 300
        + min(range_m, 50_000) * 2
    )
    product_payload = {
        "product_plan": asdict(product),
        "input_operator_bundle_hash": operator.bundle_hash,
        "assembly_error_um": assembly_error,
        "electronics_reliability_ppm": electronics_reliability,
        "battery_error_mv": calibrated_battery_error,
        "range_m": range_m,
        "stopping_distance_mm": stopping_distance_mm,
        "stability_margin_milli": stability_margin_milli,
    }
    return {
        "product_hash": digest(product_payload),
        "assembly_error_um": assembly_error,
        "electronics_reliability_ppm": electronics_reliability,
        "battery_error_mv": calibrated_battery_error,
        "vehicle_mass_kg": vehicle_mass_kg,
        "range_m": range_m,
        "stopping_distance_mm": stopping_distance_mm,
        "stability_margin_milli": stability_margin_milli,
        "physical_quality_ppm": physical_quality,
        "physical_pass": physical_pass,
        "accessibility_score_ppm": accessibility,
        "cargo_score_ppm": cargo,
        "range_score_ppm": range_score,
        "repairability_score_ppm": repairability,
        "weather_score_ppm": weather,
    }


def _construction_receipts(
    *,
    parent_world_hash: str,
    child_world_hash: str,
    plan_hash: str,
    generation: int,
    product_mass_kg: int,
) -> tuple[dict[str, object], ...]:
    product_input_mg = product_mass_kg * 1_000_000
    product_output_mg = product_input_mg * 95 // 100
    materials = (
        (
            "mobility_platform_components",
            product_input_mg,
            product_output_mg,
        ),
        ("aluminum_6061", 2_400_000 + generation * 100_000, 2_100_000 + generation * 80_000),
        ("pcb_and_components", 420_000, 390_000),
        ("battery_fixture_copper", 310_000, 285_000),
    )
    values = []
    current_parent = parent_world_hash
    for index, (material, input_q, output_q) in enumerate(materials):
        current_child = (
            child_world_hash
            if index == len(materials) - 1
            else digest(
                {
                    "parent_world_hash": current_parent,
                    "plan_hash": plan_hash,
                    "operation_index": index,
                }
            )
        )
        values.append(
            {
                "operation_hash": digest(
                    {
                        "plan_hash": plan_hash,
                        "generation": generation,
                        "operation_index": index,
                        "material": material,
                    }
                ),
                "parent_world_hash": current_parent,
                "child_world_hash": current_child,
                "balances": [
                    {
                        "material": material,
                        "input_q": input_q,
                        "reserve_draw_q": 0,
                        "output_q": output_q,
                        "waste_q": input_q - output_q,
                    }
                ],
            }
        )
        current_parent = current_child
    return tuple(values)


def execute_plan(
    plan: MicrofactoryPlan,
    input_operator: OperatorBundle,
    *,
    parent_world_hash: str,
    capital_budget_milliusd: int,
) -> MicrofactoryExecution:
    if plan.generation != input_operator.generation:
        raise SchemaError("plan generation does not match the available operator")
    if plan.input_operator_bundle_hash != input_operator.bundle_hash:
        raise SchemaError("plan did not use the exact available operator bundle")
    if plan.factory.capital_cost_milliusd > capital_budget_milliusd:
        raise SchemaError("factory plan exceeds the capital budget")
    plan_hash = digest(plan.to_dict())
    output_operator = build_output_operator(
        input_operator, plan.factory, generation=plan.generation + 1
    )
    metrics = product_metrics(plan.product, input_operator)
    product_hash = str(metrics.pop("product_hash"))
    child_world_hash = digest(
        {
            "parent_world_hash": parent_world_hash,
            "plan_hash": plan_hash,
            "product_hash": product_hash,
            "output_operator_bundle_hash": output_operator.bundle_hash,
        }
    )
    receipts = _construction_receipts(
        parent_world_hash=parent_world_hash,
        child_world_hash=child_world_hash,
        plan_hash=plan_hash,
        generation=plan.generation,
        product_mass_kg=int(metrics["vehicle_mass_kg"]),
    )
    product_cost_milliusd = plan.product.estimated_unit_cost_milliusd
    total_cost_milliusd = (
        plan.factory.capital_cost_milliusd + product_cost_milliusd
    )
    unsigned = {
        "schema_version": EXECUTION_SCHEMA,
        "generation": plan.generation,
        "plan_hash": plan_hash,
        "parent_world_hash": parent_world_hash,
        "child_world_hash": child_world_hash,
        "input_operator": asdict(input_operator),
        "output_operator": asdict(output_operator),
        "capital_cost_milliusd": plan.factory.capital_cost_milliusd,
        "product_cost_milliusd": product_cost_milliusd,
        "total_cost_milliusd": total_cost_milliusd,
        "product_hash": product_hash,
        "product_metrics": metrics,
        "construction_receipts": list(receipts),
    }
    result = MicrofactoryExecution(
        schema_version=EXECUTION_SCHEMA,
        generation=plan.generation,
        plan_hash=plan_hash,
        parent_world_hash=parent_world_hash,
        child_world_hash=child_world_hash,
        input_operator=input_operator,
        output_operator=output_operator,
        capital_cost_milliusd=plan.factory.capital_cost_milliusd,
        product_cost_milliusd=product_cost_milliusd,
        total_cost_milliusd=total_cost_milliusd,
        product_hash=product_hash,
        product_metrics=tuple(metrics.items()),
        construction_receipts=receipts,
        execution_hash=digest(unsigned),
    )
    return result


def demand_calibration_error_ppm(
    belief: DemandBelief, truth: Mapping[str, object]
) -> int:
    if set(truth) != set(DEMAND_ATTRIBUTES):
        raise SchemaError("private demand truth must cover all attributes")
    return sum(
        abs(belief.weight_map[name] - _nat(truth[name], f"truth.{name}", maximum=PPM))
        for name in DEMAND_ATTRIBUTES
    )


def evaluate_demand_outcome(
    plan: MicrofactoryPlan,
    metrics: Mapping[str, int | bool | str],
    truth_weights: Mapping[str, object],
    *,
    latent_novel_affordance: str,
) -> dict[str, object]:
    scores = {
        "accessibility": int(metrics["accessibility_score_ppm"]),
        "cargo": int(metrics["cargo_score_ppm"]),
        "range": int(metrics["range_score_ppm"]),
        "repairability": int(metrics["repairability_score_ppm"]),
        "weather": int(metrics["weather_score_ppm"]),
    }
    utility = sum(
        scores[name] * _nat(truth_weights[name], f"truth.{name}", maximum=PPM)
        for name in DEMAND_ATTRIBUTES
    ) // PPM
    physical_quality = int(metrics["physical_quality_ppm"])
    utility = utility * physical_quality // PPM
    proxy_surprise = bool(
        metrics["physical_pass"]
        and plan.product.novel_affordance == latent_novel_affordance
        and plan.product.novel_affordance != "none"
        and utility >= 720_000
    )
    outcome = (
        "delight"
        if proxy_surprise
        else "adopt"
        if metrics["physical_pass"] and utility >= 620_000
        else "reject"
    )
    brier = sum(
        (probability - (PPM if label == outcome else 0)) ** 2
        for label, probability in plan.demand_belief.outcome_forecast_ppm
    )
    return {
        "utility_micro": utility,
        "synthetic_outcome": outcome,
        "outcome_brier_ppm2": brier,
        "synthetic_positive_surprise_proxy": proxy_surprise,
        "human_endorsed_positive_surprise": False,
    }


def reference_plan(
    *,
    generation: int,
    input_operator: OperatorBundle,
    observations: Sequence[Mapping[str, object]],
) -> MicrofactoryPlan:
    weights = infer_demand_weights(observations)
    if generation == 0:
        product = {
            "wheelbase_mm": 1550,
            "track_mm": 1100,
            "battery_wh": 1900,
            "motor_power_w": 2200,
            "max_speed_mm_s": 5600,
            "payload_kg": 105,
            "cargo_l": 185,
            "seat_height_mm": 360,
            "ramp_slope_milli": 90,
            "weather_seal_ppm": 820000,
            "diagnostic_coverage_ppm": 850000,
            "modular_ports": 4,
            "novel_affordance": "self_leveling_cargo",
        }
        outcome = {"reject": 120000, "adopt": 650000, "delight": 230000}
        factory = {
            "locator_span_mm": 600,
            "fixture_calibration_samples": 30,
            "pcb_pogo_pins": 190,
            "pcb_test_vectors": 2800,
            "battery_calibration_points": 55,
        }
    else:
        product = {
            "wheelbase_mm": 1500,
            "track_mm": 1120,
            "battery_wh": 2100,
            "motor_power_w": 2300,
            "max_speed_mm_s": 5200,
            "payload_kg": 95,
            "cargo_l": 150,
            "seat_height_mm": 330,
            "ramp_slope_milli": 55,
            "weather_seal_ppm": 900000,
            "diagnostic_coverage_ppm": 940000,
            "modular_ports": 6,
            "novel_affordance": "tool_free_service",
        }
        outcome = {"reject": 70000, "adopt": 520000, "delight": 410000}
        factory = {
            "locator_span_mm": 650,
            "fixture_calibration_samples": 38,
            "pcb_pogo_pins": 230,
            "pcb_test_vectors": 3400,
            "battery_calibration_points": 75,
        }
    return MicrofactoryPlan.from_mapping(
        {
            "schema_version": PLAN_SCHEMA,
            "generation": generation,
            "input_operator_bundle_hash": input_operator.bundle_hash,
            "demand_belief": {
                "attribute_weights_ppm": weights,
                "outcome_forecast_ppm": outcome,
            },
            "product": product,
            "factory": factory,
            "hypothesis": (
                "Jointly trade current product utility against three reusable "
                "production operators; use observed preferences rather than a "
                "fixed product template."
            ),
        }
    )


__all__ = [
    "DEMAND_ATTRIBUTES",
    "EXECUTION_SCHEMA",
    "FACTORY_CAPITAL_COST_MILLIUSD",
    "NOVEL_AFFORDANCES",
    "OPERATOR_SCHEMA",
    "PLAN_SCHEMA",
    "PRODUCT_UNIT_COST_MILLIUSD",
    "DemandBelief",
    "FactoryInvestment",
    "MicrofactoryExecution",
    "MicrofactoryPlan",
    "OperatorBundle",
    "ProductPlan",
    "build_output_operator",
    "demand_calibration_error_ppm",
    "evaluate_demand_outcome",
    "execute_plan",
    "infer_demand_weights",
    "initial_operator_from_world",
    "product_metrics",
    "reference_plan",
]
