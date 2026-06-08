"""数据驻留模块导出"""

from .router import (
    DEFAULT_REGIONS,
    Region,
    RegionStatus,
    ResidencyAssignment,
    ResidencyPolicy,
    ResidencyRouter,
    get_residency_router,
    reset_residency_router,
)

__all__ = [
    "DEFAULT_REGIONS",
    "Region",
    "RegionStatus",
    "ResidencyAssignment",
    "ResidencyPolicy",
    "ResidencyRouter",
    "get_residency_router",
    "reset_residency_router",
]
