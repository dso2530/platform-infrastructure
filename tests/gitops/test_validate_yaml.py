import yaml


def test_validate_file_accepts_valid_yaml(
    tmp_path,
    monkeypatch,
    yaml_validator,
):
    validator = yaml_validator

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = tmp_path / "gitops" / "valid.yaml"
    path.parent.mkdir()
    path.write_text("kind: Application\nmetadata:\n  name: test\n")

    assert validator.validate_file(path) is True
    assert validator.errors == []


def test_validate_file_accepts_multiple_documents(
    tmp_path,
    monkeypatch,
    yaml_validator,
):
    validator = yaml_validator

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = tmp_path / "gitops" / "multiple.yaml"
    path.parent.mkdir()
    path.write_text(
        "kind: Application\n---\nkind: AppProject\n",
    )

    assert validator.validate_file(path) is True
    assert validator.errors == []


def test_validate_file_rejects_invalid_yaml(
    tmp_path,
    monkeypatch,
    yaml_validator,
):
    validator = yaml_validator

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = tmp_path / "gitops" / "invalid.yaml"
    path.parent.mkdir()
    path.write_text("kind: [Application\n")

    assert validator.validate_file(path) is False
    assert any("YAML invalide" in error for error in validator.errors)


def test_validate_file_rejects_empty_file(
    tmp_path,
    monkeypatch,
    yaml_validator,
):
    validator = yaml_validator

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = tmp_path / "gitops" / "empty.yaml"
    path.parent.mkdir()
    path.write_text("")

    assert validator.validate_file(path) is False
    assert any("fichier YAML vide" in error for error in validator.errors)


def test_validate_file_rejects_empty_document(
    tmp_path,
    monkeypatch,
    yaml_validator,
):
    validator = yaml_validator

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = tmp_path / "gitops" / "empty-document.yaml"
    path.parent.mkdir()
    path.write_text("kind: Application\n---\n")

    assert validator.validate_file(path) is False
    assert any("document YAML vide" in error for error in validator.errors)


def test_validate_file_handles_read_error(
    tmp_path,
    monkeypatch,
    yaml_validator,
):
    validator = yaml_validator

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    path = tmp_path / "gitops" / "directory.yaml"
    path.mkdir(parents=True)

    assert validator.validate_file(path) is False
    assert any("erreur de lecture" in error for error in validator.errors)


def test_main_validates_all_yaml_files(
    tmp_path,
    monkeypatch,
    yaml_validator,
    capsys,
):
    validator = yaml_validator

    gitops_dir = tmp_path / "gitops"
    gitops_dir.mkdir()

    (gitops_dir / "first.yaml").write_text("kind: Application\n")
    (gitops_dir / "second.yaml").write_text("kind: AppProject\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "GITOPS_DIR", gitops_dir)

    assert validator.main() == 0
    assert validator.validated == 2
    assert validator.errors == []

    assert "Fichiers YAML valides   : 2" in capsys.readouterr().out


def test_main_fails_when_yaml_directory_is_missing(
    tmp_path,
    monkeypatch,
    yaml_validator,
    capsys,
):
    validator = yaml_validator

    monkeypatch.setattr(
        validator,
        "GITOPS_DIR",
        tmp_path / "missing",
    )

    assert validator.main() == 1
    assert "Répertoire gitops manquant" in capsys.readouterr().err


def test_main_fails_when_no_yaml_files_exist(
    tmp_path,
    monkeypatch,
    yaml_validator,
    capsys,
):
    validator = yaml_validator

    gitops_dir = tmp_path / "gitops"
    gitops_dir.mkdir()

    monkeypatch.setattr(validator, "GITOPS_DIR", gitops_dir)

    assert validator.main() == 1
    assert "Aucun fichier YAML trouvé" in capsys.readouterr().err


def test_main_fails_when_yaml_file_is_invalid(
    tmp_path,
    monkeypatch,
    yaml_validator,
    capsys,
):
    validator = yaml_validator

    gitops_dir = tmp_path / "gitops"
    gitops_dir.mkdir()

    (gitops_dir / "invalid.yaml").write_text("kind: [Application\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "GITOPS_DIR", gitops_dir)

    assert validator.main() == 1
    assert validator.validated == 0
    assert "Erreurs détectées : 1" in capsys.readouterr().err