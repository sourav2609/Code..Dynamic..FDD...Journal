import numpy as np
import cvxpy as cp


class Helper:
    def __init__(self):
        self._base_cache_key = None
        self._base_cache = None
        self._spin_cache = {}

    def arrayResponse(self, N1, N2, antSpacing, wavelength, theta_az, theta_el):
        """
        Computes the array response vector for a given azimuth and elevation angle.

        Parameters:
        N1 : int  -> Number of antennas along x-axis
        N2 : int  -> Number of antennas along y-axis
        wavelength : float -> Wavelength of the signal
        theta_az : float -> Azimuth angle in radians
        theta_el : float -> Elevation angle in radians

        Returns:
        v : numpy array -> Array response vector size (N1 X N2) X 1 || a vector
        """
        d = antSpacing
        phi_x = np.cos(theta_el) * np.cos(theta_az)
        phi_y = np.cos(theta_el) * np.sin(theta_az)

        D_x, D_y = np.meshgrid(np.arange(N1) * d, np.arange(N2) * d)
        D_x, D_y = D_x.ravel(), D_y.ravel()

        v_1Darray = (1 / np.sqrt(N1 * N2)) * np.exp(
            -1j * ((2 * np.pi) / wavelength) * (D_x * phi_x + D_y * phi_y)
        )
        return v_1Darray.reshape(-1, 1)

    def getDistance(self, obj1, obj2):
        """Calculate Euclidean distance between two objects."""
        x1, y1, z1 = obj1.position.km
        x2, y2, z2 = obj2.position.km
        return np.linalg.norm([x2 - x1, y2 - y1, z2 - z1])

    def pathLoss(self, f_c, d):
        """
        Computes free-space path loss based on frequency and distance.

        Parameters:
        f_c : float -> Carrier frequency in Hz
        d   : float -> Distance in km

        Returns:
        beta : float -> Path loss factor
        """
        c = 3 * 10**5
        lamda = c / f_c
        return (lamda / (4 * np.pi * d)) ** 2

    def ecef_to_geodetic(self, x, y, z):
        """
        Convert ECEF coordinates to geodetic coordinates.
        """
        a = 6378.137
        e2 = 0.00669437999014

        lon = np.degrees(np.arctan2(y, x))
        p = np.sqrt(x**2 + y**2)
        lat = np.degrees(np.arctan2(z, p * (1 - e2)))

        lat_rad = np.radians(lat)
        while True:
            N = a / np.sqrt(1 - e2 * np.sin(lat_rad) ** 2)
            z_new = np.degrees(np.arctan2(z + N * e2 * np.sin(lat_rad), p))
            if abs(z_new - lat) < 1e-10:
                break
            lat = z_new
            lat_rad = np.radians(lat)

        N = a / np.sqrt(1 - e2 * np.sin(np.radians(lat)) ** 2)
        alt = p / np.cos(np.radians(lat)) - N

        return lat, lon, alt

    def azimuth_elevation_from_sat(self, sat, ue):
        """
        Computes azimuth and elevation of a ground station with respect to a satellite.
        """
        [xSat, ySat, zSat] = sat.position.km
        [xGS, yGS, zGS] = ue.position.km
        sat_lat, sat_lon, _ = self.ecef_to_geodetic(xSat, ySat, zSat)

        lat_sat_rad = np.radians(sat_lat)
        lon_sat_rad = np.radians(sat_lon)

        x_N = np.array(
            [
                -np.sin(lat_sat_rad) * np.cos(lon_sat_rad),
                -np.sin(lat_sat_rad) * np.sin(lon_sat_rad),
                np.cos(lat_sat_rad),
            ]
        )
        y_E = np.array([-np.sin(lon_sat_rad), np.cos(lon_sat_rad), 0])
        z_D = np.array(
            [
                -np.cos(lat_sat_rad) * np.cos(lon_sat_rad),
                -np.cos(lat_sat_rad) * np.sin(lon_sat_rad),
                -np.sin(lat_sat_rad),
            ]
        )

        x_N /= np.linalg.norm(x_N)
        y_E /= np.linalg.norm(y_E)
        z_D /= np.linalg.norm(z_D)

        R = np.vstack([x_N, y_E, z_D])
        r_ecef = np.array([xGS - xSat, yGS - ySat, zGS - zSat])
        r_ned = R @ r_ecef

        el = np.degrees(np.arcsin(r_ned[2] / np.linalg.norm(r_ned)))
        az = np.degrees(np.arctan2(r_ned[1], r_ned[0]))
        if az < 0:
            az += 360

        return az, el

    def channelAndPrecoder(self, obj1, obj2, antSpacing, freq, t, text):
        """
        Two options:
        (sat, Ns, ue, Nu, freq, 'ul'/'dl') || sat<->ue channel  returns Nt X 1
        (ue1, Nu, ue2, Nu, freq, 'u2u')    || ue1->ue2 channel
        """
        pos1 = obj1.location.at(t)
        pos2 = obj2.location.at(t)
        distance = self.getDistance(pos1, pos2)

        if text == "u2u":
            return self.pathLoss(freq, distance), 1

        wavelength = (3 * 10**8) / freq
        az, el = self.azimuth_elevation_from_sat(pos1, pos2)
        ant_spacing = self._spacing_for_frequency(antSpacing, freq)
        v = self.arrayResponse(obj1.numAnt[0], obj1.numAnt[1], ant_spacing, wavelength, az, el)
        channel = np.sqrt(obj1.numAnt[0] * obj1.numAnt[1] * self.pathLoss(freq, distance)) * v
        precoder = np.conj(v)
        return channel, precoder

    def _time_key(self, t):
        return float(np.asarray(t.tt).reshape(-1)[0])

    def _spacing_for_frequency(self, antSpacing, freq):
        ant_spacings = np.asarray(antSpacing, dtype=float).reshape(-1)
        if ant_spacings.size == 1:
            return float(ant_spacings[0])
        half_wavelength = (3 * 10**8) / (2 * freq)
        return float(ant_spacings[np.argmin(np.abs(ant_spacings - half_wavelength))])

    def _normalize_ant_spacings(self, antSpacing, num_bands):
        ant_spacings = np.asarray(antSpacing, dtype=float).reshape(-1)
        if ant_spacings.size == 1:
            ant_spacings = np.repeat(ant_spacings, num_bands)
        elif ant_spacings.size != num_bands:
            raise ValueError(
                f"Expected 1 or {num_bands} antenna spacing values, got {ant_spacings.size}."
            )
        return tuple(float(value) for value in ant_spacings.tolist())

    def _base_cache_signature(self, satellites, UEs, L, antSpacing, t):
        ant_spacings = self._normalize_ant_spacings(antSpacing, len(L))
        return (
            tuple(id(sat) for sat in satellites),
            tuple(id(ue) for ue in UEs),
            tuple(float(freq) for freq in L),
            ant_spacings,
            self._time_key(t),
        )

    def _spin_cache_signature(self, base_key, r):
        return base_key + (tuple(int(x) for x in np.asarray(r).tolist()),)

    def _ensure_base_cache(self, satellites, UEs, L, antSpacing, t):
        base_key = self._base_cache_signature(satellites, UEs, L, antSpacing, t)
        if self._base_cache_key == base_key and self._base_cache is not None:
            return self._base_cache
        ant_spacings = base_key[3]

        J = len(satellites)
        K = len(UEs)
        num_ant = satellites[0].numAnt[0] * satellites[0].numAnt[1] if J else 0

        sat_positions = [sat.location.at(t) for sat in satellites]
        ue_positions = [ue.location.at(t) for ue in UEs]

        h = np.zeros((J, K, len(L), num_ant), dtype=np.complex128)
        beam = np.zeros_like(h)

        for j, sat in enumerate(satellites):
            sat_pos = sat_positions[j]
            for k, ue_pos in enumerate(ue_positions):
                az, el = self.azimuth_elevation_from_sat(sat_pos, ue_pos)
                distance = self.getDistance(sat_pos, ue_pos)
                for l_idx, freq in enumerate(L):
                    wavelength = (3 * 10**8) / freq
                    v = self.arrayResponse(
                        sat.numAnt[0], sat.numAnt[1], ant_spacings[l_idx], wavelength, az, el
                    ).reshape(-1)
                    scale = np.sqrt(
                        sat.numAnt[0] * sat.numAnt[1] * self.pathLoss(freq, distance)
                    )
                    h[j, k, l_idx, :] = scale * v
                    beam[j, k, l_idx, :] = np.conj(v)

        g = np.zeros((K, K, len(L)), dtype=np.float64)
        for k_tx in range(K):
            for k_rx in range(k_tx + 1, K):
                distance = self.getDistance(ue_positions[k_tx], ue_positions[k_rx])
                for l_idx, freq in enumerate(L):
                    gain = self.pathLoss(freq, distance)
                    g[k_tx, k_rx, l_idx] = gain
                    g[k_rx, k_tx, l_idx] = gain

        self._base_cache_key = base_key
        self._base_cache = {
            "key": base_key,
            "K": K,
            "J": J,
            "h": h,
            "beam": beam,
            "g": g,
        }
        self._spin_cache = {}
        return self._base_cache

    def _ensure_spin_cache(self, satellites, UEs, L, r, antSpacing, t):
        base = self._ensure_base_cache(satellites, UEs, L, antSpacing, t)
        r = np.asarray(r, dtype=int)
        spin_key = self._spin_cache_signature(base["key"], r)
        if spin_key in self._spin_cache:
            return self._spin_cache[spin_key]

        K = base["K"]
        J = base["J"]
        h = base["h"]
        beam = base["beam"]
        g = base["g"]

        dl_band_idx = np.where(r == 1, 0, 1).astype(int)
        ul_band_idx = 1 - dl_band_idx
        same_spin = 1 - np.abs(r[:, None] - r[None, :])
        diff_spin = np.abs(r[:, None] - r[None, :])

        num_ant = h.shape[-1]
        gamma_dl = np.zeros((K, J, J, num_ant), dtype=np.complex128)
        gamma_ul = np.zeros((K, J, J, num_ant), dtype=np.complex128)
        nu = np.zeros((K, J, K, J), dtype=np.float64)
        dl_beam = np.zeros((K, J, num_ant), dtype=np.complex128)
        ul_beam = np.zeros((K, J, num_ant), dtype=np.complex128)
        signal_dl_norm = np.zeros((K, J), dtype=np.float64)
        signal_ul_norm = np.zeros((K, J), dtype=np.float64)

        for j in range(J):
            dl_beam[:, j, :] = beam[j, :, dl_band_idx[j], :]
            ul_beam[:, j, :] = beam[j, :, ul_band_idx[j], :]
            signal_dl_norm[:, j] = np.linalg.norm(h[j, :, dl_band_idx[j], :], axis=1)
            signal_ul_norm[:, j] = np.linalg.norm(h[j, :, ul_band_idx[j], :], axis=1)

            for j_ in range(J):
                gamma_dl[:, j, j_, :] = same_spin[j, j_] * h[j_, :, dl_band_idx[j_], :]
                gamma_ul[:, j, j_, :] = same_spin[j, j_] * h[j, :, ul_band_idx[j_], :]
                nu[:, j, :, j_] = diff_spin[j, j_] * g[:, :, dl_band_idx[j_]].T

        dl_gain = np.zeros((K, J, K, J), dtype=np.float64)
        ul_gain = np.zeros((K, J, K, J), dtype=np.float64)
        for j in range(J):
            for j_ in range(J):
                dl_gain[:, j, :, j_] = np.abs(gamma_dl[:, j, j_, :] @ dl_beam[:, j_, :].T) ** 2
                ul_gain[:, j, :, j_] = np.abs(ul_beam[:, j, :] @ gamma_ul[:, j, j_, :].T) ** 2

        ue_mask = (~np.eye(K, dtype=bool))[:, None, :, None]
        cross_mask = ue_mask & (~np.eye(J, dtype=bool))[None, :, None, :]

        ctx = {
            "signal_dl_norm": signal_dl_norm,
            "signal_ul_norm": signal_ul_norm,
            "signal_dl_sq": signal_dl_norm**2,
            "signal_ul_sq": signal_ul_norm**2,
            "gamma_dl": gamma_dl,
            "gamma_ul": gamma_ul,
            "nu": nu,
            "dl_gain": dl_gain,
            "ul_gain": ul_gain,
            "nu_gain": np.abs(nu) ** 2,
            "ue_mask": ue_mask.astype(np.float64),
            "cross_mask": cross_mask.astype(np.float64),
        }
        self._spin_cache[spin_key] = ctx
        return ctx

    def objective_coefficients(self, r, chi_dl, chi_ul, xi_dl, xi_ul, time, sigma, satellites, UEs, L, antSpacing):
        ctx = self._ensure_spin_cache(satellites, UEs, L, r, antSpacing, time)
        chi_dl = np.asarray(chi_dl, dtype=float)
        chi_ul = np.asarray(chi_ul, dtype=float)
        xi_dl = np.asarray(xi_dl, dtype=float)
        xi_ul = np.asarray(xi_ul, dtype=float)

        xi_dl_sq = np.square(xi_dl)
        xi_ul_sq = np.square(xi_ul)

        linear_dl = 2 * xi_dl * np.sqrt(1 + chi_dl) * ctx["signal_dl_norm"]
        linear_ul = 2 * xi_ul * np.sqrt(1 + chi_ul) * ctx["signal_ul_norm"]
        constant = (
            np.log2(1 + chi_dl)
            + np.log2(1 + chi_ul)
            - chi_dl
            - chi_ul
            - xi_dl_sq * sigma
            - xi_ul_sq * sigma
        )

        cross_mask_t = np.transpose(ctx["cross_mask"], (2, 3, 0, 1))

        quad_dl = np.sum(ctx["dl_gain"] * xi_dl_sq[:, :, None, None], axis=(0, 1))
        quad_ul = np.sum(ctx["ul_gain"] * xi_ul_sq[:, :, None, None], axis=(0, 1))
        quad_cross = np.sum(
            ctx["nu_gain"] * xi_dl_sq[:, :, None, None] * cross_mask_t, axis=(0, 1)
        )

        return {
            "constant": constant,
            "linear_dl": linear_dl,
            "linear_ul": linear_ul,
            "quad_dl": quad_dl,
            "quad_ul": quad_ul,
            "quad_cross": quad_cross,
        }

    def gammaDL(self, k, j, j_, satellites, UEs, L, r, antSpacing, t):
        ctx = self._ensure_spin_cache(satellites, UEs, L, r, antSpacing, t)
        return ctx["gamma_dl"][k, j, j_, :][None, :]

    def gammaUL(self, k_, j, j_, satellites, UEs, L, r, antSpacing, t):
        ctx = self._ensure_spin_cache(satellites, UEs, L, r, antSpacing, t)
        return ctx["gamma_ul"][k_, j, j_, :][:, None]

    def nu(self, k, k_, j, j_, UEs, L, r, antSpacing, t):
        rel_spin = np.abs(r[j] - r[j_])
        g_k_kl1, _ = self.channelAndPrecoder(UEs[k_], UEs[k], antSpacing, L[0], t, "u2u")
        g_k_kl2, _ = self.channelAndPrecoder(UEs[k_], UEs[k], antSpacing, L[1], t, "u2u")
        return rel_spin * (r[j_] * g_k_kl1 + (1 - r[j_]) * g_k_kl2)

    def objective(self, r, chi_dl, chi_ul, xi_dl, xi_ul, z_dl, z_ul, time, sigma, satellites, UEs, L, antSpacing):
        coeffs = self.objective_coefficients(
            r, chi_dl, chi_ul, xi_dl, xi_ul, time, sigma, satellites, UEs, L, antSpacing
        )
        quad_ul_total = coeffs["quad_ul"] + coeffs["quad_cross"]
        return cp.sum(
            coeffs["constant"]
            + cp.multiply(coeffs["linear_dl"], z_dl)
            + cp.multiply(coeffs["linear_ul"], z_ul)
            - cp.multiply(coeffs["quad_dl"], cp.square(z_dl))
            - cp.multiply(quad_ul_total, cp.square(z_ul))
        )

    def updateXi(self, d, r, u, p_dl, p_ul, chi_dl, chi_ul, time, sigma, satellites, UEs, L, antSpacing):
        ctx = self._ensure_spin_cache(satellites, UEs, L, r, antSpacing, time)
        d = np.asarray(d, dtype=float)
        u = np.asarray(u, dtype=float)
        p_dl = np.asarray(p_dl, dtype=float)
        p_ul = np.asarray(p_ul, dtype=float)
        chi_dl = np.asarray(chi_dl, dtype=float)
        chi_ul = np.asarray(chi_ul, dtype=float)

        dl_weight = d * p_dl
        ul_weight = u * p_ul

        num_dl = d * np.sqrt((1 + chi_dl) * p_dl) * ctx["signal_dl_norm"]
        num_ul = u * np.sqrt((1 + chi_ul) * p_ul) * ctx["signal_ul_norm"]

        I_dl = np.sum(ctx["dl_gain"] * dl_weight[None, None, :, :], axis=(2, 3))
        I_dl += np.sum(
            ctx["nu_gain"] * ul_weight[None, None, :, :] * ctx["cross_mask"], axis=(2, 3)
        )
        I_ul = np.sum(ctx["ul_gain"] * ul_weight[None, None, :, :], axis=(2, 3))

        xi_dl = num_dl / (sigma + I_dl)
        xi_ul = num_ul / (sigma + I_ul)
        return xi_dl, xi_ul

    def updateChi(self, d, r, u, p_dl, p_ul, time, sigma, satellites, UEs, L, antSpacing):
        ctx = self._ensure_spin_cache(satellites, UEs, L, r, antSpacing, time)
        d = np.asarray(d, dtype=float)
        u = np.asarray(u, dtype=float)
        p_dl = np.asarray(p_dl, dtype=float)
        p_ul = np.asarray(p_ul, dtype=float)

        dl_weight = d * p_dl
        ul_weight = u * p_ul

        num_dl = dl_weight * ctx["signal_dl_sq"]
        num_ul = ul_weight * ctx["signal_ul_sq"]

        I_dl = np.sum(
            ctx["dl_gain"] * dl_weight[None, None, :, :] * ctx["ue_mask"], axis=(2, 3)
        )
        I_dl += np.sum(
            ctx["nu_gain"] * ul_weight[None, None, :, :] * ctx["cross_mask"], axis=(2, 3)
        )
        I_ul = np.sum(
            ctx["ul_gain"] * ul_weight[None, None, :, :] * ctx["ue_mask"], axis=(2, 3)
        )

        chi_dl = num_dl / (sigma + I_dl)
        chi_ul = num_ul / (sigma + I_ul)
        return chi_dl, chi_ul

    def initializeValues(self, K, J, r, satellites, UEs):
        """Initialize optimization variables."""
        p_dl = np.zeros((K, J))
        p_ul = np.zeros((K, J))
        chi_dl = np.zeros((K, J))
        chi_ul = np.zeros((K, J))

        d, u = self.init_d_u_given_r(K, J, r)

        for k in range(K):
            for j in range(J):
                if d[k][j] != 0:
                    chi_dl[k][j] = 0.1
                    if np.sum(d[:, j]) != 0:
                        p_dl[k][j] = satellites[j].maxPow / np.sum(d[:, j])
                    else:
                        p_dl[k][j] = satellites[j].maxPow
                else:
                    p_dl[k][j] = 0
                    chi_dl[k][j] = 0

                if u[k][j] != 0:
                    p_ul[k][j] = UEs[k].maxPow
                    chi_ul[k][j] = 0.1
                else:
                    p_ul[k][j] = 0
                    chi_ul[k][j] = 0

        return d, u, p_dl, p_ul, chi_dl, chi_ul

    def init_d_u_given_r(self, K, J, r):
        """
        Given binary vector r (length J), return feasible d and u matrices (K x J).
        Ensures constraints 9(c) and 9(f) are satisfied.
        """
        d = np.zeros((K, J), dtype=int)
        u = np.zeros((K, J), dtype=int)

        active_idx = np.where(r == 1)[0]
        if active_idx.size == 0:
            active_idx = np.arange(J)

        for k in range(K):
            j = np.random.choice(active_idx)
            d[k, j] = 1
            u[k, j] = 1

        return d, u

    def objective_f0(self, r, d, u, p_dl, p_ul, time, sigma, satellites, UEs, L, antSpacing):
        """
        Compute the objective function f0.
        """
        ctx = self._ensure_spin_cache(satellites, UEs, L, r, antSpacing, time)
        d = np.asarray(d, dtype=float)
        u = np.asarray(u, dtype=float)
        p_dl = np.asarray(p_dl, dtype=float)
        p_ul = np.asarray(p_ul, dtype=float)

        dl_weight = d * p_dl
        ul_weight = u * p_ul

        signal_dl = dl_weight * ctx["signal_dl_sq"]
        signal_ul = ul_weight * ctx["signal_ul_sq"]

        I_dl = sigma
        I_dl += np.sum(
            ctx["dl_gain"] * dl_weight[None, None, :, :] * ctx["ue_mask"], axis=(2, 3)
        )
        I_dl += np.sum(
            ctx["nu_gain"] * ul_weight[None, None, :, :] * ctx["cross_mask"], axis=(2, 3)
        )

        I_ul = sigma
        I_ul += np.sum(
            ctx["ul_gain"] * ul_weight[None, None, :, :] * ctx["ue_mask"], axis=(2, 3)
        )

        term_dl = np.log2(1 + signal_dl / I_dl)
        term_ul = np.log2(1 + signal_ul / I_ul)
        return float(np.sum(term_dl + term_ul))
