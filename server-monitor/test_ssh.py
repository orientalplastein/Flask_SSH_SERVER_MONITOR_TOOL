#!/usr/bin/env python3
"""
SSH连接测试脚本
用于测试远程服务器连接功能
"""

import paramiko
import sys

def test_ssh_connection(hostname, username, password, port=22):
    """测试SSH连接"""
    try:
        print(f"正在连接到 {username}@{hostname}:{port}...")
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname, port, username, password, timeout=10)
        
        print("✓ SSH连接成功！")
        
        # 测试基本命令
        test_commands = [
            "hostname",
            "uname -a",
            "cat /etc/os-release | grep PRETTY_NAME",
            "free -h"
        ]
        
        for cmd in test_commands:
            print(f"\n执行命令: {cmd}")
            stdin, stdout, stderr = ssh_client.exec_command(cmd)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if output:
                print(f"输出: {output}")
            if error:
                print(f"错误: {error}")
        
        ssh_client.close()
        print("\n✓ 所有测试完成！")
        return True
        
    except paramiko.AuthenticationException:
        print("✗ 认证失败：用户名或密码错误")
    except paramiko.SSHException as e:
        print(f"✗ SSH连接错误: {e}")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
    
    return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python test_ssh.py <主机地址> <用户名> <密码>")
        print("示例: python test_ssh.py example.com root mypassword")
        sys.exit(1)
    
    hostname = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    test_ssh_connection(hostname, username, password)