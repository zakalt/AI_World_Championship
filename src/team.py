from dataclasses import dataclass, field
from typing import Any


@dataclass
class Team:
    name: str
    rating: float = 50.0
    tactic: str = 'balanced'        # 'defensive' | 'balanced' | 'attacking'
    ai_policy: Any = 'baseline'     # policy name or BasePolicy instance

    # --- Player attribute stats (all 0-100) ---
    # pace:      speed of transitions and counter-attacks
    # passing:   pass completion rate and chance creation quality
    # shooting:  shot accuracy and conversion rate
    # defending: reduces opponent shooting effectiveness
    # stamina:   how quickly stats degrade late in the match
    pace:      float = 65.0
    passing:   float = 65.0
    shooting:  float = 65.0
    defending: float = 65.0
    stamina:   float = 65.0

    stats: dict = field(default_factory=lambda: {
        'GF': 0, 'GA': 0, 'W': 0, 'D': 0, 'L': 0, 'Pts': 0
    })

    def attack_modifier(self) -> float:
        """Tactic multiplier applied to attacking strength."""
        return {'defensive': 0.88, 'balanced': 1.00, 'attacking': 1.13}.get(self.tactic, 1.0)

    def defense_modifier(self) -> float:
        """Tactic multiplier applied to defensive solidity."""
        return {'defensive': 1.12, 'balanced': 1.00, 'attacking': 0.88}.get(self.tactic, 1.0)

    def set_tactic(self, tactic: str) -> None:
        self.tactic = tactic
