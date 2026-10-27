from app.workflow import ModelFiles


def test_model_names_read_dotenv_without_mutating_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("FACETRUE_RESTORE_LORA", raising=False)
    env_file = tmp_path / "settings.env"
    env_file.write_text("FACETRUE_RESTORE_LORA=folder/custom.safetensors\n")
    assert ModelFiles.from_env(env_file).restore_lora == "folder/custom.safetensors"
    monkeypatch.setenv("FACETRUE_RESTORE_LORA", "env-override.safetensors")
    assert ModelFiles.from_env(env_file).restore_lora == "env-override.safetensors"
