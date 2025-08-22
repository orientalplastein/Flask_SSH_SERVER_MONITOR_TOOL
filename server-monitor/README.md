# 远程服务器监控系统

基于Flask和Bootstrap开发的服务器监控仪表盘，支持本地和远程服务器监控。

## 功能特性

- ✅ 实时CPU使用率监控（图表+数字显示）
- ✅ 内存使用情况监控（总量/已用/百分比）
- ✅ 进程列表管理（支持搜索和排序）
- ✅ 网络连接状态监控
- ✅ 数据自动刷新（每5秒）
- ✅ 响应式设计（支持桌面/平板/手机）
- ✅ SSH远程服务器连接
- ✅ 深色主题界面

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动应用
```bash
python app.py
```

访问 http://127.0.0.1:5000 查看监控界面

## SSH远程监控配置

### 1. 基本连接测试
首先使用测试脚本验证SSH连接：
```bash
python test_ssh.py your-server.com username password
```

### 2. Web界面配置
1. 点击右上角"SSH设置"按钮
2. 填写服务器信息：
   - 主机地址：服务器IP或域名
   - 端口：默认22
   - 用户名：SSH登录用户名
   - 密码：SSH登录密码

3. 点击"测试连接"验证配置
4. 点击"保存并连接"建立监控连接

### 3. 支持的Linux系统
- Ubuntu/CentOS/Debian等主流发行版
- 需要安装基本工具：`ps`, `free`, `ss`, `cat /proc/stat`

## API接口

### 本地监控
- `GET /api/stats` - 获取本地系统状态
- `GET /api/processes` - 获取进程列表

### SSH远程监控
- `POST /api/ssh/configure` - 配置SSH连接参数
- `POST /api/ssh/connect` - 建立SSH连接
- `POST /api/ssh/disconnect` - 断开SSH连接
- `GET /api/ssh/status` - 获取连接状态
- `GET /api/remote/stats` - 获取远程服务器状态

## 故障排除

### SSH连接常见问题

1. **认证失败**
   - 检查用户名和密码是否正确
   - 确认服务器允许密码登录

2. **连接超时**
   - 检查网络连通性
   - 确认防火墙设置

3. **命令执行错误**
   - 确保目标服务器安装了基本系统工具
   - 检查用户权限是否足够

4. **连接被拒绝**
   - 确认SSH服务正在运行
   - 检查端口是否正确

### 本地监控问题
- 确保有足够的权限读取系统信息
- Windows系统可能需要管理员权限

## 技术栈

### 后端
- Flask - Web框架
- paramiko - SSH连接库
- psutil - 系统信息获取
- python-dotenv - 环境变量管理

### 前端
- Bootstrap 5 - UI框架
- Chart.js - 数据图表
- JavaScript - 动态交互

## 部署建议

### 开发环境
```bash
python app.py
```

### 生产环境
建议使用WSGI服务器：
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

或使用Docker部署。

## 许可证

MIT License

## 支持

如遇问题，请检查：
1. 服务器SSH服务状态
2. 网络连接和防火墙
3. 系统工具是否完整安装
4. 用户权限设置