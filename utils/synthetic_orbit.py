import numpy as np


class _Position:
    def __init__(self, km):
        self.km = np.asarray(km, dtype=float)


class SyntheticGeocentric:
    def __init__(self, position_km):
        self.position = _Position(position_km)


class SyntheticOrbitLocation:
    def __init__(self, epoch_tt, radius_km, omega_rad_s, r_hat0, t_hat0):
        self.epoch_tt = float(epoch_tt)
        self.radius_km = float(radius_km)
        self.omega_rad_s = float(omega_rad_s)
        self.r_hat0 = self._normalize(r_hat0)
        tangent = np.asarray(t_hat0, dtype=float)
        tangent -= np.dot(tangent, self.r_hat0) * self.r_hat0
        self.t_hat0 = self._normalize(tangent)

    @staticmethod
    def _normalize(vec):
        arr = np.asarray(vec, dtype=float)
        norm = np.linalg.norm(arr)
        if norm == 0:
            raise ValueError("Cannot normalize a zero vector.")
        return arr / norm

    def at(self, t):
        dt_sec = (float(np.asarray(t.tt).reshape(-1)[0]) - self.epoch_tt) * 86400.0
        theta = self.omega_rad_s * dt_sec
        position = self.radius_km * (
            np.cos(theta) * self.r_hat0 + np.sin(theta) * self.t_hat0
        )
        return SyntheticGeocentric(position)

    def to_record(self):
        return {
            "epoch_tt": self.epoch_tt,
            "radius_km": self.radius_km,
            "omega_rad_s": self.omega_rad_s,
            "r_hat0": self.r_hat0.tolist(),
            "t_hat0": self.t_hat0.tolist(),
        }

    @classmethod
    def from_record(cls, record):
        return cls(
            epoch_tt=record["epoch_tt"],
            radius_km=record["radius_km"],
            omega_rad_s=record["omega_rad_s"],
            r_hat0=record["r_hat0"],
            t_hat0=record["t_hat0"],
        )
