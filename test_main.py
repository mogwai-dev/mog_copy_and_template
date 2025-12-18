import os
import shutil
import zipfile
from pathlib import Path
import tomli
import pytest
from main import load_toml, render_path, process_files

def setup_test_files(tmp_path, variables):
    # テスト用のコピー元ファイルを作成
    src_dir = tmp_path / variables["name"]
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "foobar.txt").write_text("test1")
    (src_dir / "foobar2.txt").write_text("test2")
    return src_dir

def test_render_path():
    variables = {"name": "testuser", "id": 1}
    assert render_path("{{name}}/foo.txt", variables) == "testuser/foo.txt"
    assert render_path("id_{{id}}", variables) == "id_1"

def test_process_files(tmp_path):
    # テスト用TOML
    toml_content = '''
[variables]
name = "testuser"
id = 1

[zip]
file_name = "sample.zip"

[file1]
from = "{{name}}/foobar.txt"
to = "renamed_foobar.txt"

[file2]
from = "{{name}}/foobar2.txt"
to = "new_dir/renamed_foobar2.txt"
'''
    toml_path = tmp_path / "config.toml"
    toml_path.write_text(toml_content)
    config = load_toml(str(toml_path))
    variables = config["variables"]
    setup_test_files(tmp_path, variables)
    process_files(config, tmp_path)
    # sample ディレクトリとファイルの存在確認
    sample_dir = tmp_path / "sample"
    assert (sample_dir / "renamed_foobar.txt").exists()
    assert (sample_dir / "new_dir" / "renamed_foobar2.txt").exists()
    # zipファイルの存在と内容確認
    zip_path = tmp_path / "sample.zip"
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as z:
        assert "renamed_foobar.txt" in z.namelist()
        assert "new_dir/renamed_foobar2.txt" in z.namelist()
