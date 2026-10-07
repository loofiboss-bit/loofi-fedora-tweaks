"""Visibility-aware sampling adapters for the Monitor presentation widgets.

Readers and formatters are supplied by the widget so existing service seams
remain injectable; these helpers own scheduling and worker lifecycle only.
"""
from __future__ import annotations

import typing


class PerformanceSamplingMixin:
    """Render shared immutable dashboard samples without separate readers."""

    def set_dashboard_controller(self, controller):
        self.refresh_timer.stop()
        previous = self._dashboard_controller
        if previous is controller:
            return
        if previous is not None:
            previous.set_consumer_active("monitor", False)
            previous.snapshotReady.disconnect(self._show_dashboard_snapshot)
            previous.failed.disconnect(self._dashboard_failed)
        self._dashboard_controller = controller
        controller.snapshotReady.connect(self._show_dashboard_snapshot)
        controller.failed.connect(self._dashboard_failed)

    def _dashboard_failed(self, reason):
        if self._stopping:
            return
        for label in (self.lbl_cpu, self.lbl_mem, self.lbl_net, self.lbl_disk):
            label.setText(self.tr("Unavailable: %1").replace("%1", reason))

    def _show_dashboard_snapshot(self, snapshot):
        if self._stopping:
            return
        readings = {reading.id: reading for reading in snapshot.metrics}

        def valid(identifier):
            reading = readings.get(identifier)
            return reading is not None and reading.status == "ready" and reading.value is not None

        def unknown(identifiers, label):
            reasons = [readings[key].reason or readings[key].status for key in identifiers if key in readings]
            label.setText(self.tr("Unavailable: %1").replace("%1", " · ".join(reasons) or self.tr("No measurement")))

        def fresh(identifier):
            reading = readings[identifier]
            if self._shared_times.get(identifier) == reading.sampled_at:
                return False
            self._shared_times[identifier] = reading.sampled_at
            return True

        if valid("cpu.usage"):
            reading = readings["cpu.usage"]
            if fresh("cpu.usage"):
                self.cpu_graph.add_value(reading.value)
            cores = getattr(snapshot, "cpu_per_core", ())
            self._ensure_core_bars(len(cores))
            for bar, percent in zip(self.cpu_core_bars, cores):
                bar.set_value(percent)
            self.lbl_cpu.setText(self.tr("CPU: {pct}% | Cores: {cores}").format(pct=reading.value, cores=len(cores)))
        else:
            self._ensure_core_bars(0)
            unknown(("cpu.usage",), self.lbl_cpu)
        if valid("memory.usage"):
            reading = readings["memory.usage"]
            if fresh("memory.usage"):
                self.mem_graph.add_value(reading.value)
            self.lbl_mem.setText(self.tr("Memory: {pct}% | {detail}").format(pct=reading.value, detail=reading.detail))
        else:
            unknown(("memory.usage",), self.lbl_mem)
        for first, second, graph, label, title_a, title_b in (
            ("network.receive", "network.send", self.net_graph, self.lbl_net, self.tr("Recv"), self.tr("Send")),
            ("disk.read", "disk.write", self.disk_graph, self.lbl_disk, self.tr("Read"), self.tr("Write")),
        ):
            if valid(first) and valid(second):
                a, b = readings[first].value, readings[second].value
                if fresh(first):
                    graph.add_values(a, b)
                label.setText(f"{title_a}: {self._bytes_to_human(int(a))}/s | "
                              f"{title_b}: {self._bytes_to_human(int(b))}/s")
            else:
                unknown((first, second), label)


class ProcessSamplingMixin:
    """Keep process reads off the UI thread with one reader and bounded waits."""

    def set_active(self: typing.Any, active: bool) -> None:
        if self._active == active or self._closed:
            return
        self._active = active
        self._generation += 1
        self._process_baseline = False
        if active:
            self.refresh_processes()
            self.refresh_timer.start(3000)
        else:
            self.refresh_timer.stop()

    @property
    def sampling_busy(self) -> bool:
        return self._process_worker is not None

    def request_stop(self: typing.Any) -> None:
        if not self._closed:
            self.set_active(False)
            self._closed = True
        self.refresh_timer.stop()
        if self._process_worker is not None:
            self._process_worker.requestInterruption()

    def wait_for_stop(self, timeout_ms: int) -> bool:
        worker = self._process_worker
        return worker is None or worker.wait(max(0, int(timeout_ms)))

    def cleanup(self, timeout_ms: int = 5000) -> bool:
        self.request_stop()
        return self.wait_for_stop(timeout_ms)

    def refresh_processes(self: typing.Any) -> typing.Any:
        """Schedule one process read; all tree rendering stays on the UI thread."""
        if self.__dict__.get("_async_refresh", False):
            self._start_process_read()
            return
        # Lightweight legacy consumers supply already mocked synchronous readers.
        counts = self._process_manager().get_process_count()
        processes = self._process_manager().get_all_processes()
        self._render_processes(counts, processes)

    def _start_process_read(self):
        if not self._active or self._closed or self._process_worker is not None:
            return
        from PyQt6.QtCore import QThread, pyqtSignal

        class _ProcessWorker(QThread):
            resultReady = pyqtSignal(object, int)
            failed = pyqtSignal(str, int)

            def __init__(worker_self, generation, baseline, parent):
                super().__init__(parent)
                worker_self.generation = generation
                worker_self.baseline = baseline

            def run(worker_self):
                try:
                    processes = self._process_manager().get_all_processes()
                    if not processes:
                        raise OSError("No readable process data")
                    if worker_self.isInterruptionRequested():
                        return
                    counts = {"total": len(processes), "running": 0, "sleeping": 0, "zombie": 0}
                    for process in processes:
                        if process.state == "R":
                            counts["running"] += 1
                        elif process.state in ("S", "D", "I"):
                            counts["sleeping"] += 1
                        elif process.state == "Z":
                            counts["zombie"] += 1
                    worker_self.resultReady.emit((counts, processes, worker_self.baseline), worker_self.generation)
                except (OSError, RuntimeError, ValueError, TypeError) as exc:
                    worker_self.failed.emit(str(exc), worker_self.generation)

        worker = _ProcessWorker(self._generation, self._process_baseline, self)
        self._process_worker = worker
        worker.resultReady.connect(self._process_result)
        worker.failed.connect(self._process_failure)
        worker.finished.connect(self._process_finished)
        worker.start()

    def _process_result(self, result, generation):
        if self._closed or not self._active or generation != self._generation:
            return
        counts, processes, baseline = result
        self._process_baseline = True
        self._cached_processes = (counts, processes, baseline)
        self._render_processes(counts, list(processes), baseline)

    def _process_failure(self, reason, generation):
        if not self._closed and self._active and generation == self._generation:
            self.lbl_summary.setText(self.tr("Process read failed: %1").replace("%1", reason))

    def _process_finished(self):
        worker = self._process_worker
        self._process_worker = None
        if worker is not None:
            worker.deleteLater()
        self.workerStopped.emit()
