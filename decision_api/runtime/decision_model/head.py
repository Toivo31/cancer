"""Shared candidate attention with no candidate positions or ordered flattening."""

from dataclasses import dataclass
import math

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class HeadConfig:
    embedding_dim: int = 4096
    width: int = 96
    layers: int = 2
    attention_heads: int = 8
    expansion: int = 4

    def __post_init__(self):
        if min(self.embedding_dim, self.width, self.layers,
               self.attention_heads, self.expansion) <= 0:
            raise ValueError("All configuration dimensions must be positive")
        if self.width % self.attention_heads:
            raise ValueError("Width must be divisible by attention_heads")


PRESETS = {
    "1m": HeadConfig(width=96),
    "15m": HeadConfig(width=600),
    "100m": HeadConfig(width=1752),
}


class InteractionBlock(nn.Module):
    def __init__(self, config: HeadConfig):
        super().__init__()
        d = config.width
        self.attention_norm = nn.LayerNorm(d)
        self.attention = nn.MultiheadAttention(
            d, config.attention_heads, dropout=0.0, batch_first=True
        )
        self.mlp_norm = nn.LayerNorm(d)
        self.mlp = nn.Sequential(
            nn.Linear(d, config.expansion * d),
            nn.GELU(),
            nn.Linear(config.expansion * d, d),
        )

    def forward(self, hidden: Tensor, valid: Tensor) -> Tensor:
        normalized = self.attention_norm(hidden)
        update, _ = self.attention(
            normalized, normalized, normalized,
            key_padding_mask=~valid, need_weights=False,
        )
        hidden = hidden + update
        hidden = hidden + self.mlp(self.mlp_norm(hidden))
        return hidden.masked_fill(~valid.unsqueeze(-1), 0)


class ValueHead(nn.Module):
    """Return [batch, choices] logits from independently encoded embeddings.

    context: [B, E]; choices: [B, N, E]; valid: optional bool [B, N].
    True denotes a real candidate. Each example needs at least one candidate.
    Invalid choice payloads are discarded before projection, including NaNs.
    Use question-level cross entropy on the returned logits. Padding is -inf.
    Inputs may be BF16; projections cast to the parameter dtype, and external
    torch.autocast can select mixed-precision compute without changing weights.
    """

    def __init__(self, config: HeadConfig):
        super().__init__()
        self.config = config
        d = config.width
        self.context_projection = nn.Linear(config.embedding_dim, d)
        self.choice_projection = nn.Linear(config.embedding_dim, d)
        self.fusion = nn.Sequential(nn.Linear(3 * d, d), nn.GELU())
        self.blocks = nn.ModuleList(
            InteractionBlock(config) for _ in range(config.layers)
        )
        self.output_norm = nn.LayerNorm(d)
        self.scorer = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))

    @property
    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def forward(self, context: Tensor, choices: Tensor,
                valid: Tensor | None = None) -> Tensor:
        if context.ndim != 2 or choices.ndim != 3:
            raise ValueError("Expected context [B,E] and choices [B,N,E]")
        b, n, e = choices.shape
        if n == 0 or b == 0 or context.shape != (b, e) or e != self.config.embedding_dim:
            raise ValueError("Empty batch/choices or incompatible embedding shapes")
        if context.device != choices.device:
            raise ValueError("Context and choices must share a device")
        if not context.is_floating_point() or not choices.is_floating_point():
            raise ValueError("Embeddings must be floating point")
        if valid is None:
            valid = torch.ones((b, n), dtype=torch.bool, device=choices.device)
        if valid.shape != (b, n) or valid.dtype != torch.bool or valid.device != choices.device:
            raise ValueError("valid must be bool [B,N] on the embedding device")
        if not valid.any(dim=1).all():
            raise ValueError("Every example must contain a valid choice")
        choices = choices.masked_fill(~valid.unsqueeze(-1), 0)
        dtype = self.context_projection.weight.dtype
        c = self.context_projection(context.to(dtype))
        x = self.choice_projection(choices.to(dtype))
        expanded_context = c.unsqueeze(1).expand_as(x)
        hidden = self.fusion(torch.cat((expanded_context, x, expanded_context * x), dim=-1))
        hidden = hidden.masked_fill(~valid.unsqueeze(-1), 0)
        for block in self.blocks:
            hidden = block(hidden, valid)
        # FP32 accumulation stabilizes the direct compatibility term under AMP.
        direct = (c.float().unsqueeze(1) * x.float()).sum(-1) / math.sqrt(self.config.width)
        logits = direct + self.scorer(self.output_norm(hidden)).squeeze(-1).float()
        return logits.masked_fill(~valid, -torch.inf)
