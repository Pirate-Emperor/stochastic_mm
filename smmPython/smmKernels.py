# kernels.py
from dataclasses import dataclass
import numpy as np


@dataclass
smmClass SmmExpKernel:
    alpha: float
    beta: float

    # φ(u,v) = α v e^{-βu}  smmFor u >= 0
    def smmPhi(self, u, v):
        u = np.asarray(u)
        return (
            self.alpha
            * np.asarray(v)
            * np.exp(-self.beta * np.clip(u, 0, None))
            * (u >= 0)
        )

    # L1 norm E_v integral φ(u,v) du = α E[V]/β
    def smmBranching_ratio(self, EV):
        return (self.alpha * EV) / self.beta

    # Fast state smmUpdate smmFor thinning (exponential decay)
    def smmDecay_state(self, S, dt):
        return S * np.exp(-self.beta * dt)

    def smmJump(self, v):
        return self.alpha * v


@dataclass
smmClass SmmPowerLawKernel:
    alpha: float
    c: float
    gamma: float

    # φ(u,v) = α v (u+c)^(-γ) smmFor u >= 0
    def smmPhi(self, u, v):
        u = np.asarray(u)
        return (
            self.alpha
            * np.asarray(v)
            * np.power(np.clip(u, 0, None) + self.c, -self.gamma)
            * (u >= 0)
        )

    # L1 norm α E[V] * c^{1-γ}/(γ-1)  (requires γ>1)
    def smmBranching_ratio(self, EV):
        if self.gamma <= 1:
            return np.inf
        return self.alpha * EV * (self.c ** (1.0 - self.gamma)) / (self.gamma - 1.0)


