#!/usr/bin/env python3
"""
DATA-AI 项目初始化脚本

自动完成以下任务：
1. 创建和检查配置文件
2. 安装依赖（可选）
3. 设置项目目录
4. 验证项目完整性
"""

import os
import sys
import subprocess
from pathlib import Path


def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("  DATA-AI 项目初始化")
    print("=" * 60)


def check_config_file():
    """检查并创建配置文件"""
    config_file = Path("config/config.toml")
    config_example = Path("config/config.example.toml")

    if not config_file.exists():
        if config_example.exists():
            print("✅ 正在从模板创建配置文件...")
            import shutil
            shutil.copy(config_example, config_file)
            print(f"✅ 已创建: {config_file}")
            print("⚠️  请编辑 config/config.toml 填入您的 API 密钥")
        else:
            print("❌ 找不到配置模板文件!")
            return False
    else:
        print(f"✅ 配置文件已存在: {config_file}")
    return True


def create_directories():
    """创建所需目录"""
    dirs = ["data", "logs", "examples", "docs", "tests"]
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ 创建目录: {dir_name}")
        else:
            print(f"✅ 目录已存在: {dir_name}")


def check_requirements():
    """检查 requirements.txt"""
    req_file = Path("requirements.txt")
    if req_file.exists():
        print(f"✅ 找到依赖文件: {req_file}")
        return True
    else:
        print("❌ 找不到 requirements.txt!")
        return False


def install_dependencies():
    """安装依赖（可选）"""
    print("\n是否要安装项目依赖?")
    response = input("(这可能需要几分钟) [y/N]: ").strip().lower()

    if response == "y":
        print("\n正在安装依赖...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
            ])
            print("✅ 依赖安装完成!")
        except Exception as e:
            print(f"❌ 依赖安装失败: {e}")
            return False
    else:
        print("⚠️  跳过依赖安装")
    return True


def validate_project():
    """验证项目结构"""
    print("\n正在验证项目结构...")

    required_paths = [
        "app/",
        "config/",
        "requirements.txt",
        "README.md",
        "config/config.example.toml"
    ]

    all_good = True
    for path in required_paths:
        if Path(path).exists():
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
            all_good = False

    return all_good


def print_summary():
    """打印总结信息"""
    print("\n" + "=" * 60)
    print("  初始化完成!")
    print("=" * 60)
    print("\n下一步:")
    print("1. 编辑 config/config.toml 填入您的 API 密钥")
    print("2. 运行测试: pytest tests/")
    print("3. 查看文档: 参考 README.md 和 docs/ 目录")
    print("\n祝您使用愉快!")


def main():
    """主函数"""
    print_banner()

    # 切换到项目根目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    print(f"当前目录: {Path.cwd()}\n")

    # 执行初始化步骤
    success = True

    success &= check_config_file()
    create_directories()
    success &= check_requirements()

    if success:
        success &= install_dependencies()

    if success:
        success &= validate_project()

    if success:
        print_summary()
        return 0
    else:
        print("\n❌ 初始化过程中遇到问题，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
