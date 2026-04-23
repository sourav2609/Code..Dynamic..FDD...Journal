import json
from pathlib import Path

import numpy as np


class Simulator:
    CASE_ORDER = (
        "bestSolution_wspin",
        "bestSolution_spin0",
        "bestSolution_spin1",
        "bestSolution_randSpin",
    )
    PLOT_STYLES = {
        "bestSolution_wspin": ("Best Over All Spins", "blue"),
        "bestSolution_spin0": ("All-Zero Spin", "red"),
        "bestSolution_spin1": ("All-One Spin", "green"),
        "bestSolution_randSpin": ("Random Spin-0/1", "orange"),
    }

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
        self.results_by_case = {case_name: [] for case_name in self.CASE_ORDER}
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
        self.results_by_case = {case_name: [] for case_name in self.CASE_ORDER}
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

                case_results = self.optimizer.run(
                    self.network.satellites,
                    self.network.ues,
                    self.freqs,
                    self.bws,
                    self.network.time,
                    self.antSpacing,
                )

                iteration_payload = {"iteration": i + 1}
                for case_name in self.CASE_ORDER:
                    case_value = float(case_results[case_name])
                    self.results_by_case[case_name].append(case_value)
                    iteration_payload[case_name] = case_value
                iteration_payload["with_spin"] = iteration_payload["bestSolution_wspin"]
                iteration_payload["without_spin"] = iteration_payload["bestSolution_randSpin"]
                self.iteration_results.append(iteration_payload)

                if checkpoint_path is not None:
                    self.save(
                        checkpoint_path,
                        metadata=metadata,
                        completed_iterations=i + 1,
                        status="running" if (i + 1) < self.nIter else "completed",
                    )
                if plot_path is not None and self._has_results():
                    self.plot(plot_path)
        except Exception as exc:
            if checkpoint_path is not None:
                self.save(
                    checkpoint_path,
                    metadata=metadata,
                    completed_iterations=self.completed_iterations,
                    status="failed",
                    error_message=str(exc),
                )
            raise

        return {case_name: list(values) for case_name, values in self.results_by_case.items()}

    @property
    def completed_iterations(self):
        return len(self.iteration_results)

    def _has_results(self):
        return any(self.results_by_case[case_name] for case_name in self.CASE_ORDER)

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
                self.completed_iterations
                if completed_iterations is None
                else int(completed_iterations)
            ),
            "target_iterations": int(self.nIter),
            "result_case_order": list(self.CASE_ORDER),
            "iteration_results": list(self.iteration_results),
            "results_by_case": {
                case_name: list(self.results_by_case[case_name]) for case_name in self.CASE_ORDER
            },
            "results_with_spin": list(self.results_by_case["bestSolution_wspin"]),
            "results_without_spin": list(self.results_by_case["bestSolution_randSpin"]),
        }
        if error_message is not None:
            payload["error_message"] = error_message
        self._write_json_atomic(filename, payload)

    def plot(self, output_path):
        if not self._has_results():
            raise ValueError("No simulation results available to plot.")

        import matplotlib.pyplot as plt

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fmt = output_path.suffix.lstrip(".") or None

        plt.figure(figsize=(8, 6))
        for case_name in self.CASE_ORDER:
            case_values = self.results_by_case[case_name]
            if not case_values:
                continue
            sorted_values = np.sort(case_values)
            cdf_values = np.arange(1, len(sorted_values) + 1) / len(sorted_values)
            label, color = self.PLOT_STYLES[case_name]
            plt.plot(sorted_values, cdf_values, label=label, color=color)
        plt.xlabel("Sum Rate")
        plt.ylabel("CDF")
        plt.grid(True)
        plt.legend()
        plt.savefig(output_path, format=fmt)
        plt.close()
