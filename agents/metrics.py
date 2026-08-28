"""Latency and call metrics for scaled agent simulations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentCallMetrics:
    successful_calls: int = 0
    failed_calls: int = 0
    total_call_latency_seconds: float = 0.0
    round_latencies_seconds: list[float] = field(default_factory=list)
    agent_count: int = 5
    max_concurrency: int = 1

    @property
    def total_calls(self) -> int:
        return self.successful_calls + self.failed_calls

    @property
    def average_call_latency_seconds(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_call_latency_seconds / self.total_calls

    @property
    def total_round_latency_seconds(self) -> float:
        return sum(self.round_latencies_seconds)

    def record_success(self, latency_seconds: float) -> None:
        self.successful_calls += 1
        self.total_call_latency_seconds += latency_seconds

    def record_failure(self, latency_seconds: float) -> None:
        self.failed_calls += 1
        self.total_call_latency_seconds += latency_seconds

    def record_round_latency(self, latency_seconds: float) -> None:
        self.round_latencies_seconds.append(latency_seconds)

    def reset(self) -> None:
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_call_latency_seconds = 0.0
        self.round_latencies_seconds.clear()


def display_simulation_metrics(metrics: AgentCallMetrics) -> None:
    print("\n=== Simulation Performance ===")
    print(f"  Agent count:              {metrics.agent_count}")
    print(f"  Max concurrency:          {metrics.max_concurrency}")
    print(f"  Total round latency:      {metrics.total_round_latency_seconds:.3f}s")
    print(f"  Average persona-call latency: {metrics.average_call_latency_seconds:.3f}s")
    print(f"  Successful calls:         {metrics.successful_calls}")
    print(f"  Failed calls:             {metrics.failed_calls}")
