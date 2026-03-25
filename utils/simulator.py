import json
from pathlib import Path

import numpy as np


class Simulator:
    def __init__(
        self,
        net,
        optimizer,
        L,
        B,
        Ns,
        Nu,
        satMaxPow,
        ueMaxPow,
        antSpacing,
        nIter,
        outfile,
        layout_callback=None,
    ):
        self.network = net
        self.optimizer = optimizer
        self.freqs = L
        self.bws = B
        self.Ns = Ns
        self.Nu = Nu
        self.satMaxPow = satMaxPow
        self.ueMaxPow = ueMaxPow
        self.antSpacing = antSpacing
        self.nIter = nIter
        self.results_with_spin = []
        self.results_without_spin = []
        self.iteration_results = []
        self.outfile = outfile
        self.layout_callback = layout_callback

    @staticmethod
    def _write_json_atomic(filename, payload):
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = filename.with_suffix(filename.suffix + ".tmp")
        with open(tmp_path, "w", newline="\n") as file:
            json.dump(payload, file, indent=2)
        tmp_path.replace(filename)

    def run(self, checkpoint_file=None, metadata=None, plot_file=None):
        self.results_with_spin = []
        self.results_without_spin = []
        self.iteration_results = []
        checkpoint_path = Path(checkpoint_file) if checkpoint_file is not None else None
        plot_path = Path(plot_file) if plot_file is not None else None

        try:
            for i in range(self.nIter):
                print(f"Iteration {i + 1}/{self.nIter}")
                if self.layout_callback is not None:
                    self.layout_callback(i)

                self.network.generateLayout(
                    self.Ns, self.Nu, self.satMaxPow, self.ueMaxPow, self.outfile
                )

                sum_rate1, sum_rate2 = self.optimizer.run(
                    self.network.satellites,
                    self.network.ues,
                    self.freqs,
                    self.bws,
                    self.network.time,
                    self.antSpacing,
                )
                self.results_with_spin.append(float(sum_rate1))
                self.results_without_spin.append(float(sum_rate2))
                self.iteration_results.append(
                    {
                        "iteration": i + 1,
                        "with_spin": float(sum_rate1),
                        "without_spin": float(sum_rate2),
                    }
                )

                if checkpoint_path is not None:
                    self.save(
                        checkpoint_path,
                        metadata=metadata,
                        completed_iterations=i + 1,
                        status="running" if (i + 1) < self.nIter else "completed",
                    )
                if plot_path is not None and self.results_with_spin and self.results_without_spin:
                    self.plot(plot_path)
        except Exception as exc:
            if checkpoint_path is not None:
                self.save(
                    checkpoint_path,
                    metadata=metadata,
                    completed_iterations=len(self.results_with_spin),
                    status="failed",
                    error_message=str(exc),
                )
            raise

        return self.results_with_spin, self.results_without_spin

    def save(
        self,
        filename,
        metadata=None,
        completed_iterations=None,
        status="completed",
        error_message=None,
    ):
        payload = {
            "metadata": metadata or {},
            "status": status,
            "completed_iterations": (
                len(self.results_with_spin)
                if completed_iterations is None
                else int(completed_iterations)
            ),
            "target_iterations": int(self.nIter),
            "iteration_results": list(self.iteration_results),
            "results_with_spin": list(self.results_with_spin),
            "results_without_spin": list(self.results_without_spin),
        }
        if error_message is not None:
            payload["error_message"] = error_message
        self._write_json_atomic(filename, payload)

    def plot(self, output_path):
        if not self.results_with_spin or not self.results_without_spin:
            raise ValueError("No simulation results available to plot.")

        import matplotlib.pyplot as plt

        sorted_spin = np.sort(self.results_with_spin)
        sorted_no_spin = np.sort(self.results_without_spin)

        cdf_spin = np.arange(1, len(sorted_spin) + 1) / len(sorted_spin)
        cdf_no_spin = np.arange(1, len(sorted_no_spin) + 1) / len(sorted_no_spin)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = output_path.suffix.lstrip(".") or None

        plt.figure(figsize=(8, 6))
        plt.plot(sorted_spin, cdf_spin, label="With Spin", color="blue")
        plt.plot(sorted_no_spin, cdf_no_spin, label="Without Spin", color="red")
        plt.xlabel("Sum Rate")
        plt.ylabel("CDF")
        plt.grid(True)
        plt.legend()
        plt.savefig(output_path, format=fmt)
        plt.close()
