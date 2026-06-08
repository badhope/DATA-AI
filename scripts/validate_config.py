#!/usr/bin/env python3
"""
DATA-AI 配置文件验证脚本
验证 config/config.toml 的正确性和完整性
"""
import sys
import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class ConfigValidator:
    """配置文件验证器"""
    
    def __init__(self, config_path: str = "config/config.toml"):
        self.config_path = Path(config_path)
        self.config = None
        self.errors = []
        self.warnings = []
        
    def validate(self) -> bool:
        """执行完整验证"""
        print("=" * 60)
        print("🔍 DATA-AI 配置验证工具")
        print("=" * 60)
        
        # 1. 检查文件存在
        if not self.check_file_exists():
            return False
            
        # 2. 解析配置文件
        if not self.parse_config():
            return False
            
        # 3. 验证必需字段
        self.validate_required_fields()
        
        # 4. 验证 LLM 配置
        self.validate_llm_config()
        
        # 5. 验证记忆配置
        self.validate_memory_config()
        
        # 6. 验证沙箱配置
        self.validate_sandbox_config()
        
        # 输出结果
        self.print_results()
        
        return len(self.errors) == 0
    
    def check_file_exists(self) -> bool:
        """检查配置文件是否存在"""
        if not self.config_path.exists():
            self.errors.append(f"配置文件不存在: {self.config_path}")
            print(f"\n❌ 配置文件不存在: {self.config_path}")
            print(f"   请运行: cp config/config.example.toml config/config.toml")
            return False
        
        print(f"\n✓ 找到配置文件: {self.config_path}")
        return True
    
    def parse_config(self) -> bool:
        """解析配置文件"""
        try:
            with open(self.config_path, 'rb') as f:
                self.config = tomllib.load(f)
            print("✓ 配置文件格式正确 (TOML)")
            return True
        except Exception as e:
            self.errors.append(f"配置文件解析失败: {e}")
            print(f"\n❌ 配置文件解析失败: {e}")
            return False
    
    def validate_required_fields(self):
        """验证必需字段"""
        if not self.config:
            return
            
        # 检查 LLM 配置
        if 'llm' not in self.config:
            self.errors.append("缺少 [llm] 配置节")
        else:
            llm = self.config['llm']
            required_fields = ['model', 'base_url', 'api_key']
            for field in required_fields:
                if field not in llm:
                    self.errors.append(f"[llm] 缺少必需字段: {field}")
                elif field == 'api_key' and llm.get('api_key') in ['', 'YOUR_API_KEY', None]:
                    self.warnings.append(f"[llm] api_key 未设置或为占位符")
    
    def validate_llm_config(self):
        """验证 LLM 配置"""
        if not self.config or 'llm' not in self.config:
            return
            
        llm = self.config['llm']
        
        # 检查 max_tokens
        if 'max_tokens' in llm:
            max_tokens = llm['max_tokens']
            if not isinstance(max_tokens, int) or max_tokens <= 0:
                self.errors.append("[llm] max_tokens 必须是正整数")
            elif max_tokens > 100000:
                self.warnings.append(f"[llm] max_tokens 值较大 ({max_tokens})，可能影响响应速度")
        
        # 检查 temperature
        if 'temperature' in llm:
            temp = llm['temperature']
            if not isinstance(temp, (int, float)):
                self.errors.append("[llm] temperature 必须是数字")
            elif temp < 0 or temp > 2:
                self.errors.append("[llm] temperature 应在 0-2 范围内")
    
    def validate_memory_config(self):
        """验证记忆配置"""
        if not self.config or 'memory' not in self.config:
            self.warnings.append("未找到 [memory] 配置节，记忆系统将使用默认设置")
            return
            
        memory = self.config['memory']
        
        # 检查 keep_recent_messages
        if 'keep_recent_messages' in memory:
            val = memory['keep_recent_messages']
            if not isinstance(val, int) or val <= 0:
                self.errors.append("[memory] keep_recent_messages 必须是正整数")
        
        # 检查 summary_interval
        if 'summary_interval' in memory:
            val = memory['summary_interval']
            if not isinstance(val, int) or val <= 0:
                self.errors.append("[memory] summary_interval 必须是正整数")
    
    def validate_sandbox_config(self):
        """验证沙箱配置"""
        if not self.config or 'sandbox' not in self.config:
            self.warnings.append("未找到 [sandbox] 配置节，沙箱将使用默认设置")
            return
            
        sandbox = self.config['sandbox']
        
        # 检查 sandbox_type
        if 'sandbox_type' in sandbox:
            valid_types = ['local', 'docker', 'daytona']
            if sandbox['sandbox_type'] not in valid_types:
                self.errors.append(f"[sandbox] sandbox_type 必须是 {valid_types} 之一")
        
        # 检查 timeout
        if 'timeout' in sandbox:
            val = sandbox['timeout']
            if not isinstance(val, int) or val <= 0:
                self.errors.append("[sandbox] timeout 必须是正整数")
    
    def print_results(self):
        """打印验证结果"""
        print("\n" + "=" * 60)
        print("📊 验证结果")
        print("=" * 60)
        
        # 错误
        if self.errors:
            print(f"\n❌ 发现 {len(self.errors)} 个错误:")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        # 警告
        if self.warnings:
            print(f"\n⚠️  发现 {len(self.warnings)} 个警告:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        # 总结
        if not self.errors and not self.warnings:
            print("\n✅ 配置验证通过！")
        elif not self.errors:
            print("\n⚠️  配置验证通过，但有警告")
        else:
            print("\n❌ 配置验证失败，请修复上述错误")
        
        print("=" * 60)


def main():
    """主函数"""
    # 支持命令行参数
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.toml"
    
    # 切换到项目根目录
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # 执行验证
    validator = ConfigValidator(config_path)
    success = validator.validate()
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
