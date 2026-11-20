"""Convert a saved factorized placement/route policy to pair logits."""

import torch


def factorized_action_head_to_flat(weight: torch.Tensor, bias: torch.Tensor, *, num_nodes: int):
    """Expand independent placement and route scores into ordered pair scores."""
    if num_nodes <= 0 or weight.ndim != 2 or bias.ndim != 1:
        raise ValueError("factorized action head must have a positive node count and linear weights/bias")
    if weight.shape[0] != 2 * num_nodes or bias.shape[0] != 2 * num_nodes:
        raise ValueError(
            f"factorized action head must contain 2N={2 * num_nodes} logits, "
            f"got weight={weight.shape[0]} bias={bias.shape[0]}"
        )
    place_weight, route_weight = weight[:num_nodes], weight[num_nodes:]
    place_bias, route_bias = bias[:num_nodes], bias[num_nodes:]
    flat_weight = (place_weight[:, None, :] + route_weight[None, :, :]).reshape(
        num_nodes * num_nodes, weight.shape[1]
    )
    flat_bias = (place_bias[:, None] + route_bias[None, :]).reshape(num_nodes * num_nodes)
    return flat_weight, flat_bias
