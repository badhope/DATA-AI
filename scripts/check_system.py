#!/usr/bin/env python3
"""
DATA-AI 系统完整性检查
检查所有模块是否可以正常导入和使用
"""

import sys
from pathlib import Path
from typing import List

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class SystemCheck:
    """系统完整性检查"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def check_import(self, name: str, description: str):
        """检查模块导入"""
        try:
            __import__(name)
            self.results.append((True, name, description))
            self.passed += 1
            print(f"  ✅ {name}: {description}")
            return True
        except Exception as e:
            self.results.append((False, name, f"{description} - {e}"))
            self.failed += 1
            print(f"  ❌ {name}: {description}")
            return False
    
    def run(self):
        """运行检查"""
        print("=" * 70)
        print("                   DATA-AI 系统完整性检查")
        print("=" * 70)
        
        # 检查标准库
        print("\n📦 标准库:")
        self.check_import("json", "JSON 处理")
        self.check_import("pathlib", "路径处理")
        self.check_import("datetime", "日期时间")
        self.check_import("uuid", "唯一标识")
        self.check_import("random", "随机数")
        self.check_import("math", "数学运算")
        self.check_import("re", "正则表达式")
        self.check_import("collections", "集合工具")
        self.check_import("logging", "日志")
        self.check_import("argparse", "命令行参数")
        
        # 检查第三方依赖
        print("\n🔌 第三方依赖:")
        self.check_import("pydantic", "数据验证")
        self.check_import("httpx", "HTTP 客户端")
        
        # 检查可选依赖
        print("\n🎯 可选依赖 (仅警告):")
        try:
            from loguru import logger
            self.check_import("loguru", "日志增强")
        except ImportError:
            print("  ⚠️ loguru: 日志增强 (使用标准 logging 替代)")
        
        # 检查核心模块
        print("\n⚡ 核心模块:")
        self.check_import("app.workflow_executor", "工作流执行器")
        self.check_import("app.resource_loader", "资源加载器")
        self.check_import("app.context_manager", "上下文管理器")
        self.check_import("app.memory", "记忆基础")
        self.check_import("app.memory_semantic", "语义记忆")
        self.check_import("app.memory_episodic", "情景记忆")
        self.check_import("app.memory_procedural", "程序记忆")
        self.check_import("app.memory_coordinator", "记忆协调器")
        self.check_import("app.data_memory", "数据记忆")
        
        # 检查智能体模块
        print("\n🤖 智能体模块:")
        self.check_import("app.agent", "智能体基础")
        self.check_import("app.agent.data", "数据智能体")
        self.check_import("app.agent.base", "基础智能体")
        
        # 检查工具模块
        print("\n🔧 工具模块:")
        self.check_import("app.tools", "核心工具")
        
        # 检查新增功能模块
        print("\n🚀 新增功能:")
        self.check_import("app.memory_explorer", "记忆探索器")
        self.check_import("app.prompt_studio", "提示词工作室")
        
        # 检查子模块
        print("\n📄 记忆探索器子模块:")
        self.check_import("app.memory_explorer.base", "基础探索器")
        self.check_import("app.memory_explorer.search", "搜索引擎")
        self.check_import("app.memory_explorer.exporter", "导出工具")
        self.check_import("app.memory_explorer.cleaner", "清理工具")
        self.check_import("app.memory_explorer.analytics", "分析工具")
        self.check_import("app.memory_explorer.cli", "命令行界面")
        
        print("\n✨ 提示词工作室子模块:")
        self.check_import("app.prompt_studio.manager", "模板管理器")
        self.check_import("app.prompt_studio.ab_testing", "A/B 测试引擎")
        self.check_import("app.prompt_studio.evaluator", "评估工具")
        self.check_import("app.prompt_studio.cli", "命令行界面")
        
        # 检查提示词模块
        print("\n📝 提示词模块:")
        self.check_import("app.prompt", "提示词基础")
        
        # 检查主入口
        print("\n🎬 主入口:")
        self.check_import("main", "主程序入口")
        
        # 汇总结果
        print("\n" + "=" * 70)
        print("                             检查结果")
        print("=" * 70)
        print(f"  ✅ 通过: {self.passed}")
        print(f"  ❌ 失败: {self.failed}")
        print(f"  📊 总计: {self.passed + self.failed}")
        
        if self.failed == 0:
            print("\n🎉 所有检查通过！系统完整可用！")
        else:
            print(f"\n⚠️ 有 {self.failed} 个检查失败，请检查相关模块")
        
        print("=" * 70)
        
        return self.failed == 0


def main():
    """主函数"""
    checker = SystemCheck()
    success = checker.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
