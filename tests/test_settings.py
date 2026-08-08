"""Tests for settings behavior and regression boundaries."""

from fedresearch.settings import load_settings


def test_experiment_overrides_default_fields_without_inheritance(tmp_path, monkeypatch):
    """Verify experiment overrides default fields without inheritance."""
    monkeypatch.setenv("FEDRESEARCH_GENERATION_MODEL", "")
    monkeypatch.setenv("FEDRESEARCH_EMBEDDING_MODEL", "")
    config = tmp_path / "configs"
    experiments = config / "experiments"
    experiments.mkdir(parents=True)
    default = config / "default.yaml"
    default.write_text(
        "retrieval:\n  candidate_limit: 8\n  top_k: 4\n  evidence_tokens: 1200\n"
        "generation:\n  model: my-deployment\n"
    )
    experiment = experiments / "custom.yaml"
    experiment.write_text("retrieval:\n  top_k: 2\n")
    monkeypatch.chdir(tmp_path.parent)

    baseline = load_settings(default)
    settings = load_settings(experiment)
    assert baseline.retrieval.top_k == 4
    assert settings.retrieval.top_k == 2
    assert settings.retrieval.candidate_limit == 8
    assert settings.retrieval.evidence_tokens == 1200
    assert settings.generation.model == "my-deployment"
    assert settings.paths.raw == tmp_path / "data/raw"
