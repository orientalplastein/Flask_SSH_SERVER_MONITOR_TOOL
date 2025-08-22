# 远程服务器监控系统

## 核心功能

- ✅ **实时资源监控** - CPU使用率、内存使用情况实时显示
- ✅ **进程管理** - 当前运行进程列表显示（PID、名称、CPU%、内存、状态）
- ✅ **网络状态显示** - 网络连接数量统计
- ✅ **数据自动刷新** - 1秒间隔自动更新监控数据
- ✅ **响应式设计** - Bootstrap 5框架支持各种设备
- ✅ **SSH远程连接** - 支持通过SSH连接远程服务器进行监控

## 技术栈

**后端：**
- Flask (Python Web框架)
- paramiko (SSH连接库)
- psutil (系统监控库)

**前端：**
- Bootstrap 5 (响应式UI框架)
- Chart.js (实时图表库)
- jQuery (DOM操作辅助)

## 系统架构

```
server-monitor/
├── app.py              # Flask主应用
├── requirements.txt    # Python依赖
├── templates/
│   └── index.html     # 主页面模板
├── static/
│   ├── css/
│   │   └── style.css  # 自定义样式
│   └── js/
│       └── app.js     # 前端逻辑
└── ssh_connections.json # SSH连接配置历史
```

## API接口

- `GET /` - 主页面
- `GET /api/stats` - 获取本地服务器状态
- `GET /api/remote/stats` - 获取远程服务器状态
- `GET /api/ssh/status` - 获取SSH连接状态
- `POST /api/ssh/configure` - 配置SSH连接参数
- `POST /api/ssh/connect` - 建立SSH连接
- `POST /api/ssh/disconnect` - 断开SSH连接

## 使用说明

1. **本地监控**：直接访问 http://127.0.0.1:5000 查看本地服务器状态
2. **远程监控**：
   - 点击"SSH设置"按钮
   - 填写远程服务器信息（主机、端口、用户名、密码）
   - 点击"测试连接"验证配置
   - 点击"保存并连接"建立SSH连接
3. **数据查看**：
   - 实时图表显示CPU和内存使用趋势
   - 进程列表显示当前运行进程
   - 系统运行时间显示

## 部署运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py

# 访问应用
http://127.0.0.1:5000
```

## 特性说明

- 🚀 **实时性**：1秒间隔自动刷新数据
- 📱 **响应式**：支持桌面、平板、手机等设备
- 🔐 **安全性**：SSH连接支持，密码安全传输
- 📊 **可视化**：图表直观展示系统负载趋势
- ⚡ **高性能**：异步数据获取，避免界面卡顿

## 注意事项

- 确保远程服务器SSH服务正常运行
- 防火墙需要开放SSH端口（默认22）
- 生产环境建议使用WSGI服务器部署
- 监控数据仅供参考，不作为精确计量依据