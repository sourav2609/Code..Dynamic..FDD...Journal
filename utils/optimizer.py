import random
from itertools import product

import cvxpy as cp
import numpy as np

from .helper import Helper


class Optimizer:
    def __init__(self, algoName):
        self.algo = algoName
        self.helper = Helper()
        self.delta_f_values = []

    @staticmethod
    def _activity_from_power(power, tol=1e-9):
        return (np.asarray(power) > tol).astype(float)

    def run(self, satellites, UEs, L, B, time, antSpacing):
        K = len(UEs)
        J = len(satellites)
        T = 290
        k0 = 1.38e-23
        sigma = k0 * T * B[0]

        if self.algo != "fractionalProgramming":
            raise NameError("The algorithm is not implemented!")

        r_combinations = np.array(list(product([0, 1], repeat=J)))
        r_all = r_combinations.T
        M = 5
        max_iters = 20

        sat_t_bound = np.tile(
            np.sqrt(np.array([sat.maxPow for sat in satellites], dtype=float)), (K, 1)
        )
        ue_t_bound = np.repeat(
            np.sqrt(np.array([ue.maxPow for ue in UEs], dtype=float))[:, None], J, axis=1
        )

        solutions = []
        for rIdx in range(2**J):
            r = r_all[:, rIdx]
            d_val, u_val, p_dl_val, p_ul_val, chi_dl_val, chi_ul_val = self.helper.initializeValues(
                K, J, r, satellites, UEs
            )

            if J == 1:
                d = None
                u = None
                t_dl = None
                t_ul = None
                z_dl = cp.Variable((K, J), nonneg=True)
                z_ul = cp.Variable((K, J), nonneg=True)
            else:
                d = cp.Variable((K, J), boolean=True)
                u = cp.Variable((K, J), boolean=True)
                t_dl = cp.Variable((K, J), nonneg=True)
                t_ul = cp.Variable((K, J), nonneg=True)
                z_dl = cp.Variable((K, J))
                z_ul = cp.Variable((K, J))

            const_param = cp.Parameter((K, J))
            lin_dl_param = cp.Parameter((K, J))
            lin_ul_param = cp.Parameter((K, J))
            quad_dl_param = cp.Parameter((K, J), nonneg=True)
            quad_ul_param = cp.Parameter((K, J), nonneg=True)

            objective_expr = cp.sum(
                const_param
                + cp.multiply(lin_dl_param, z_dl)
                + cp.multiply(lin_ul_param, z_ul)
                - cp.multiply(quad_dl_param, cp.square(z_dl))
                - cp.multiply(quad_ul_param, cp.square(z_ul))
            )

            if J == 1:
                constraints = []
            else:
                constraints = [
                    cp.sum(d, axis=1) <= 1,
                    cp.sum(u, axis=1) <= 1,
                    cp.abs(d @ r - u @ r)
                    <= M * (2 - cp.sum(d, axis=1) - cp.sum(u, axis=1)),
                    t_dl <= sat_t_bound,
                    t_ul <= ue_t_bound,
                    z_dl >= 0,
                    z_ul >= 0,
                    z_dl <= t_dl,
                    z_ul <= t_ul,
                    z_dl >= t_dl - M * (1 - d),
                    z_dl <= M * d,
                    z_ul >= t_ul - M * (1 - u),
                    z_ul <= M * u,
                ]
            constraints.extend(
                cp.sum_squares(z_ul[k, :]) <= UEs[k].maxPow for k in range(K)
            )
            constraints.extend(
                cp.sum_squares(z_dl[:, j]) <= satellites[j].maxPow for j in range(J)
            )

            prob = cp.Problem(cp.Maximize(objective_expr), constraints)

            objectiveWithIterations = []
            f0_withIterations = []
            for _ in range(max_iters):
                chi_dl_val, chi_ul_val = self.helper.updateChi(
                    d_val,
                    r,
                    u_val,
                    p_dl_val,
                    p_ul_val,
                    time,
                    sigma,
                    satellites,
                    UEs,
                    L,
                    antSpacing,
                )
                xi_dl, xi_ul = self.helper.updateXi(
                    d_val,
                    r,
                    u_val,
                    p_dl_val,
                    p_ul_val,
                    chi_dl_val,
                    chi_ul_val,
                    time,
                    sigma,
                    satellites,
                    UEs,
                    L,
                    antSpacing,
                )

                coeffs = self.helper.objective_coefficients(
                    r,
                    chi_dl_val,
                    chi_ul_val,
                    xi_dl,
                    xi_ul,
                    time,
                    sigma,
                    satellites,
                    UEs,
                    L,
                    antSpacing,
                )
                const_param.value = coeffs["constant"]
                lin_dl_param.value = coeffs["linear_dl"]
                lin_ul_param.value = coeffs["linear_ul"]
                quad_dl_param.value = coeffs["quad_dl"]
                quad_ul_param.value = coeffs["quad_ul"] + coeffs["quad_cross"]

                prob.solve(solver=cp.MOSEK, verbose=False, warm_start=False)

                if J == 1:
                    if z_dl.value is None or z_ul.value is None:
                        raise RuntimeError(
                            f"Solver returned no primal solution for numSat=1, spin={r.tolist()}, "
                            f"status={prob.status}"
                        )
                    p_dl_val = np.square(z_dl.value)
                    p_ul_val = np.square(z_ul.value)
                    d_val = self._activity_from_power(p_dl_val)
                    u_val = self._activity_from_power(p_ul_val)
                else:
                    if (
                        d.value is None
                        or u.value is None
                        or t_dl.value is None
                        or t_ul.value is None
                    ):
                        raise RuntimeError(
                            f"Solver returned no primal solution for spin={r.tolist()}, "
                            f"status={prob.status}"
                        )
                    d_val = d.value
                    u_val = u.value
                    p_dl_val = np.square(t_dl.value)
                    p_ul_val = np.square(t_ul.value)

                f_0 = self.helper.objective_f0(
                    r, d_val, u_val, p_dl_val, p_ul_val, time, sigma, satellites, UEs, L, antSpacing
                )
                f0_withIterations.append(f_0)
                objectiveWithIterations.append(prob.value)

            with open("f2_J_4_K_10.txt", "w") as f:
                for item in objectiveWithIterations:
                    f.write(str(item) + "\n")

            with open("f0withIterations.txt", "w") as f:
                for item in f0_withIterations:
                    f.write(str(item) + "\n")

            solutions.append(f_0)

        bestSolution_wOspin = solutions[0] if random.random() < 0.5 else solutions[-1]
        bestSolution_wspin = max(solutions)
        return bestSolution_wspin, bestSolution_wOspin
