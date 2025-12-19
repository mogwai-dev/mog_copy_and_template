
# copy_and_template: TOML指示でファイルコピー・zip化するライブラリ/CLI
import tomli
import shutil
import zipfile
from pathlib import Path
from jinja2 import Template
from datetime import datetime
import csv
import pyminizip

import sys
import argparse


def load_toml(toml_path: str) -> dict:
    """TOMLファイルを読み込む"""
    with open(toml_path, 'rb') as f:
        return tomli.load(f)



def render_path(path_template: str, variables: dict) -> str:
    """Jinja2テンプレートを使って変数を展開"""
    template = Template(path_template)
    return template.render(variables)


# ファイルコピー＆zip化の本体
def process_files(config: dict, base_dir: Path, verbose: bool = True, log_path: Path = None) -> tuple[Path, Path]:
    """
    設定に従ってファイルをコピーしてzipを作成します。
    コピー時はshutil.copy2を使うため、作成日時・変更日時なども維持されます。
    戻り値: (作成ディレクトリ, zipファイルパス)
    """
    variables = config.get('variables', {})
    zip_config = config.get('zip', {})
    if not zip_config:
        raise ValueError("[zip] section is required in TOML")
    zip_file_name = zip_config.get('file_name', 'output.zip')
    zip_file_name = render_path(zip_file_name, variables)
    zip_password = zip_config.get('password')  # パスワード取得
    zip_output_enabled = zip_config.get('output_enabled', True)
    temp_dir_name = Path(zip_file_name).stem
    temp_dir = base_dir / temp_dir_name
    # すでにあっても消さない
    # if temp_dir.exists():
    #     shutil.rmtree(temp_dir)
    # temp_dir.mkdir(parents=True, exist_ok=True)
    
    # ログファイル初期化（指定されている場合）
    if log_path:
        with log_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'operation', 'source', 'destination'])
    
    file_sections = {k: v for k, v in config.items() if k.startswith('file') and isinstance(v, dict)}
    for section_name, file_config in file_sections.items():
        from_path = file_config.get('from')
        to_path = file_config.get('to')
        if not from_path or not to_path:
            if verbose:
                print(f"Warning: {section_name} is missing 'from' or 'to' field")
            continue
        from_path_rendered = render_path(from_path, variables)
        to_path_rendered = render_path(to_path, variables)
        # 絶対パス対応
        source = Path(from_path_rendered) if Path(from_path_rendered).is_absolute() else base_dir / from_path_rendered
        destination = temp_dir / to_path_rendered
        if not source.exists():
            if verbose:
                print(f"Error: Source file not found: {source}")
                sys.exit()
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)  # 作成日時・変更日時なども維持
        
        # ログ記録
        if log_path:
            with log_path.open('a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().isoformat(), 'copy', str(source), str(destination)])
        
        if verbose:
            print(f"Copied: {from_path_rendered} -> {temp_dir_name}/{to_path_rendered}")
    
    zip_path = base_dir / zip_file_name
    
    if zip_output_enabled:
        # パスワード付きzipの場合はpyminizipを使用
        if zip_password:
            file_list = [str(f) for f in temp_dir.rglob('*') if f.is_file()]
            arcname_list = [str(f.relative_to(temp_dir)) for f in temp_dir.rglob('*') if f.is_file()]
            
            if file_list:
                pyminizip.compress_multiple(
                    file_list,
                    arcname_list,
                    str(zip_path),
                    zip_password,
                    5  # 圧縮レベル (0-9)
                )
                
                # ログ記録
                if log_path:
                    for file, arcname in zip(file_list, arcname_list):
                        with log_path.open('a', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow([datetime.now().isoformat(), 'zip', file, arcname])
                
                if verbose:
                    for arcname in arcname_list:
                        print(f"Added to zip: {arcname}")
        else:
            # パスワードなしの場合は標準zipfileを使用
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in temp_dir.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(temp_dir)
                        zipf.write(file, arcname)
                        
                        # ログ記録
                        if log_path:
                            with log_path.open('a', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow([datetime.now().isoformat(), 'zip', str(file), str(arcname)])
                        
                        if verbose:
                            print(f"Added to zip: {arcname}")
        
        if verbose:
            print(f"\nCreated: {zip_file_name}")
            if zip_password:
                print(f"Password protected: enabled")
            print(f"Directory preserved: {temp_dir_name}/")
    else:
        if verbose:
            print(f"\nZip output disabled. Files are in directory: {temp_dir_name}/")
    return temp_dir, zip_path



# CLIエントリポイント
def main():
    parser = argparse.ArgumentParser(description="TOML指示でファイルコピー・zip化するツール")
    parser.add_argument("config", help="設定TOMLファイルのパス")
    parser.add_argument("--quiet", action="store_true", help="出力を最小限にする")
    parser.add_argument("--log", default="operation.log", help="操作ログをCSVファイルに保存（デフォルト: operation.log、タイムスタンプ付き、複数回実行対応）")
    args = parser.parse_args()

    toml_path = args.config
    base_dir = Path(toml_path).parent
    
    # ログパス生成（タイムスタンプ付きで重複回避）
    log_base = Path(args.log)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_base.parent / f"{log_base.stem}_{timestamp}{log_base.suffix}" if log_base.parent == Path('.') else base_dir / f"{log_base.stem}_{timestamp}{log_base.suffix}"
    
    try:
        config = load_toml(toml_path)
        process_files(config, base_dir, verbose=not args.quiet, log_path=log_path)
        print(f"Log saved: {log_path}")
    except FileNotFoundError:
        print(f"Error: TOML file not found: {toml_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
