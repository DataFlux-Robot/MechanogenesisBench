from __future__ import annotations

from dataclasses import dataclass

from .errors import IRValidationError
from .ir import ShapeNode, Vec3Q


PI_LOWER_NUMERATOR = 3_141_592
PI_UPPER_NUMERATOR = 3_141_593
PI_DENOMINATOR = 1_000_000


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


@dataclass(frozen=True)
class IntervalQ:
    lower: int
    upper: int

    def __post_init__(self) -> None:
        if self.lower < 0 or self.upper < self.lower:
            raise ValueError("invalid nonnegative interval")


@dataclass(frozen=True)
class AABBQ:
    minimum_um: Vec3Q
    maximum_um: Vec3Q

    @property
    def size_um(self) -> Vec3Q:
        return Vec3Q(
            self.maximum_um.x - self.minimum_um.x,
            self.maximum_um.y - self.minimum_um.y,
            self.maximum_um.z - self.minimum_um.z,
        )

    def contains(self, other: "AABBQ") -> bool:
        return (
            self.minimum_um.x <= other.minimum_um.x
            and self.minimum_um.y <= other.minimum_um.y
            and self.minimum_um.z <= other.minimum_um.z
            and self.maximum_um.x >= other.maximum_um.x
            and self.maximum_um.y >= other.maximum_um.y
            and self.maximum_um.z >= other.maximum_um.z
        )

    def disjoint(self, other: "AABBQ") -> bool:
        return (
            self.maximum_um.x <= other.minimum_um.x
            or other.maximum_um.x <= self.minimum_um.x
            or self.maximum_um.y <= other.minimum_um.y
            or other.maximum_um.y <= self.minimum_um.y
            or self.maximum_um.z <= other.minimum_um.z
            or other.maximum_um.z <= self.minimum_um.z
        )


@dataclass(frozen=True)
class GeometryFacts:
    aabb: AABBQ
    volume_um3: IntervalQ
    primitive_count: int
    labels: tuple[str, ...]


def _half_bounds(center: int, extent: int) -> tuple[int, int]:
    lower = center - extent // 2
    return lower, lower + extent


def primitive_aabb(shape: ShapeNode) -> AABBQ:
    if shape.kind == "box":
        assert shape.center_um is not None and shape.size_um is not None
        x0, x1 = _half_bounds(shape.center_um.x, shape.size_um.x)
        y0, y1 = _half_bounds(shape.center_um.y, shape.size_um.y)
        z0, z1 = _half_bounds(shape.center_um.z, shape.size_um.z)
        return AABBQ(Vec3Q(x0, y0, z0), Vec3Q(x1, y1, z1))
    if shape.kind == "cylinder":
        assert shape.center_um is not None
        assert shape.radius_um is not None and shape.height_um is not None
        radius = shape.radius_um
        half0, half1 = _half_bounds(0, shape.height_um)
        extents = {
            "x": (half0, half1, -radius, radius, -radius, radius),
            "y": (-radius, radius, half0, half1, -radius, radius),
            "z": (-radius, radius, -radius, radius, half0, half1),
        }[shape.axis or "z"]
        return AABBQ(
            Vec3Q(shape.center_um.x + extents[0], shape.center_um.y + extents[2], shape.center_um.z + extents[4]),
            Vec3Q(shape.center_um.x + extents[1], shape.center_um.y + extents[3], shape.center_um.z + extents[5]),
        )
    raise IRValidationError("primitive_aabb requires a primitive shape")


def primitive_volume(shape: ShapeNode) -> IntervalQ:
    if shape.kind == "box":
        assert shape.size_um is not None
        value = shape.size_um.x * shape.size_um.y * shape.size_um.z
        return IntervalQ(value, value)
    if shape.kind == "cylinder":
        assert shape.radius_um is not None and shape.height_um is not None
        base = shape.radius_um * shape.radius_um * shape.height_um
        return IntervalQ(
            base * PI_LOWER_NUMERATOR // PI_DENOMINATOR,
            ceil_div(base * PI_UPPER_NUMERATOR, PI_DENOMINATOR),
        )
    raise IRValidationError("primitive_volume requires a primitive shape")


def validate_geometry(shape: ShapeNode) -> GeometryFacts:
    if shape.kind in {"box", "cylinder"}:
        return GeometryFacts(
            aabb=primitive_aabb(shape),
            volume_um3=primitive_volume(shape),
            primitive_count=1,
            labels=(shape.label,),
        )

    child_facts = [validate_geometry(child) for child in shape.children]
    labels = (shape.label, *(label for facts in child_facts for label in facts.labels))
    if len(set(labels)) != len(labels):
        raise IRValidationError(f"geometry {shape.label!r} contains duplicate labels")

    if shape.kind == "difference":
        base, *cutters = child_facts
        for index, cutter in enumerate(cutters):
            if not base.aabb.contains(cutter.aabb):
                raise IRValidationError(
                    f"difference cutter {shape.children[index + 1].label!r} escapes its base"
                )
        for left_index, left in enumerate(cutters):
            for right in cutters[left_index + 1 :]:
                if not left.aabb.disjoint(right.aabb):
                    raise IRValidationError(
                        "reference difference semantics requires disjoint cutter AABBs"
                    )
        lower = base.volume_um3.lower - sum(item.volume_um3.upper for item in cutters)
        upper = base.volume_um3.upper - sum(item.volume_um3.lower for item in cutters)
        if lower <= 0:
            raise IRValidationError("difference removes the entire conservative base volume")
        return GeometryFacts(
            aabb=base.aabb,
            volume_um3=IntervalQ(lower, upper),
            primitive_count=sum(item.primitive_count for item in child_facts),
            labels=labels,
        )

    if shape.kind == "union":
        for left_index, left in enumerate(child_facts):
            for right in child_facts[left_index + 1 :]:
                if not left.aabb.disjoint(right.aabb):
                    raise IRValidationError(
                        "reference union semantics requires disjoint child AABBs"
                    )
        minimum = Vec3Q(
            min(item.aabb.minimum_um.x for item in child_facts),
            min(item.aabb.minimum_um.y for item in child_facts),
            min(item.aabb.minimum_um.z for item in child_facts),
        )
        maximum = Vec3Q(
            max(item.aabb.maximum_um.x for item in child_facts),
            max(item.aabb.maximum_um.y for item in child_facts),
            max(item.aabb.maximum_um.z for item in child_facts),
        )
        return GeometryFacts(
            aabb=AABBQ(minimum, maximum),
            volume_um3=IntervalQ(
                sum(item.volume_um3.lower for item in child_facts),
                sum(item.volume_um3.upper for item in child_facts),
            ),
            primitive_count=sum(item.primitive_count for item in child_facts),
            labels=labels,
        )
    raise IRValidationError(f"unknown CSG operation {shape.kind!r}")


def find_shape(shape: ShapeNode, label: str) -> ShapeNode:
    if shape.label == label:
        return shape
    for child in shape.children:
        try:
            return find_shape(child, label)
        except IRValidationError:
            pass
    raise IRValidationError(f"shape label {label!r} not found")
