"""Fixed, reference-independent analysis settings."""
from dataclasses import dataclass, asdict
import numpy as np
@dataclass(frozen=True)
class Config:
    pdm_fs: int = 2_500_000
    pcm_fs: int = 50_000
    decimation: int = 50
    microphones: int = 16
    spacing: float = .04
    sound_speed: float = 343.
    numtaps: int = 2001
    cutoff: float = 20_000.
    beta: float = 8.6
    frame_size: int = 4096
    nfft: int = 8192
    hop: int = 1024
    freq_min: float = 300.
    freq_max: float = 4000.
    angle_step: float = .25
    bin_relative_threshold: float = .01
    noise_multiplier: float = 3.
    minimum_coherence: float = .4
    window_seconds: float = .5
    hop_seconds: float = .25
    def dictionary(self): return asdict(self)
    @property
    def angles(self): return np.arange(-90.,90.+self.angle_step/2,self.angle_step)
BANDS = [(300,500),(500,1000),(1000,1500),(1500,2000),(2000,2500),(2500,3000),(3000,3500),(3500,4000)]
