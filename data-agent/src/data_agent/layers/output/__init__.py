"""Client-safe exports for the DATA structured output layer DTOs.

The runtime layer implementation lives in ``output_layer.py`` and imports
server-side execution dependencies. Keep this package root import-safe for
client code that only needs to build run requests.
"""

from data_agent.layers.output.configs import DATA_OUTPUT_LAYER_TYPE_ID, DATAOutputLayerConfig

__all__ = ["DATA_OUTPUT_LAYER_TYPE_ID", "DATAOutputLayerConfig"]
