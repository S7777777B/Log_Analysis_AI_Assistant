## ClickHouse Docker 快速部署手册

### 一、快速部署 ClickHouse

#### 1. 拉取镜像并启动容器

```bash
# 拉取官方镜像
docker pull clickhouse/clickhouse-server:latest

# 启动 ClickHouse 容器
docker run -d \
  --name clickhouse-server \
  --ulimit nofile=262144:262144 \
  -p 8123:8123 \
  -p 9000:9000 \
  --restart unless-stopped \
  clickhouse/clickhouse-server:latest
```

**参数说明：**
- `-d`: 后台运行
- `--name`: 容器名称
- `--ulimit nofile=262144:262144`: 设置文件句柄限制（ClickHouse 需要）
- `-p 8123:8123`: HTTP 接口端口
- `-p 9000:9000`: Native 协议端口（客户端连接）
- `--restart unless-stopped`: 自动重启策略

#### 2. 验证容器状态

```bash
# 查看容器运行状态
docker ps | grep clickhouse

# 查看容器日志
docker logs clickhouse-server --tail 20
```

#### 3. 测试连接

```bash
# 方式1：使用 clickhouse-client（进入容器）
docker exec -it clickhouse-server clickhouse-client

# 方式2：直接执行 SQL
docker exec -it clickhouse-server clickhouse-client --query "SELECT version()"
```

---

### 二、用户管理

#### 1. 登录 ClickHouse（默认用户）

```bash
docker exec -it clickhouse-server clickhouse-client
```

默认用户名：`default`，密码：**空**

#### 2. 创建新用户

```sql
-- 创建用户（基本语法）
CREATE USER username IDENTIFIED BY 'password';

-- 示例：创建 lingluody 用户
CREATE USER lingluody IDENTIFIED BY 'your_password';

-- 带主机限制（更安全）
CREATE USER lingluody IDENTIFIED BY 'password' HOST IP '192.168.1.%';
```

#### 3. 查看所有用户

```sql
SHOW USERS;
```

---

### 三、权限管理

#### 1. 授予权限的基本语法

```sql
-- 基本语法
GRANT privilege ON database.table TO username;

-- 撤销权限
REVOKE privilege ON database.table FROM username;
```

#### 2. 常见权限配置方案

##### 方案A：全部权限（管理员）

```sql
GRANT ALL ON *.* TO lingluody WITH GRANT OPTION;
```

##### 方案B：数据库完整权限

```sql
GRANT ALL ON log_analysis.* TO lingluody;
```

##### 方案C：读写+建表权限

```sql
GRANT SELECT, INSERT, CREATE, ALTER, TRUNCATE ON log_analysis.* TO lingluody;
```

##### 方案D：只读权限（数据分析师）

```sql
GRANT SELECT ON log_analysis.* TO lingluody;
```

##### 方案E：表级别权限

```sql
-- 只授权特定表的访问
GRANT SELECT, INSERT ON log_analysis.logs TO lingluody;
```

#### 3. 查看用户权限

```sql
-- 查看指定用户的权限
SHOW GRANTS FOR lingluody;

-- 查看当前用户权限
SHOW GRANTS;
```

#### 4. 修改用户信息

```sql
-- 修改密码
ALTER USER lingluody IDENTIFIED BY 'new_password';

-- 修改用户主机限制
ALTER USER lingluody HOST IP '10.0.0.%';
```

#### 5. 删除用户

```sql
DROP USER lingluody;
```

---

### 四、完整部署示例

#### Step 1：启动容器

```bash
docker run -d \
  --name clickhouse-server \
  --ulimit nofile=262144:262144 \
  -p 8123:8123 \
  -p 9000:9000 \
  --restart unless-stopped \
  clickhouse/clickhouse-server:latest
```

#### Step 2：创建用户并授权

```bash
# 进入 ClickHouse 客户端
docker exec -it clickhouse-server clickhouse-client
```

执行以下 SQL：

```sql
-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS log_analysis;

-- 2. 创建用户
CREATE USER IF NOT EXISTS lingluody IDENTIFIED BY 'YourStrongPassword123!';

-- 3. 授予权限（根据需求选择一种）
-- 选项1：完整权限
GRANT ALL ON log_analysis.* TO lingluody;

-- 选项2：读写权限
-- GRANT SELECT, INSERT, CREATE, ALTER ON log_analysis.* TO lingluody;

-- 4. 验证权限
SHOW GRANTS FOR lingluody;

-- 5. 退出
exit;
```

#### Step 3：验证新用户

```bash
# 使用新用户登录测试
docker exec -it clickhouse-server clickhouse-client \
  --user lingluody \
  --password 'YourStrongPassword123!'

# 测试权限
SHOW DATABASES;
USE log_analysis;
CREATE TABLE test (id Int32) ENGINE = MergeTree() ORDER BY id;
SELECT * FROM test;
DROP TABLE test;

# 退出
exit;
```

#### Step 4：持久化数据（推荐生产环境）

```bash
# 停止并删除已有容器
docker stop clickhouse-server
docker rm clickhouse-server

# 创建数据目录
mkdir -p ~/clickhouse/data

# 启动容器并挂载数据卷
docker run -d \
  --name clickhouse-server \
  --ulimit nofile=262144:262144 \
  -p 8123:8123 \
  -p 9000:9000 \
  -v ~/clickhouse/data:/var/lib/clickhouse \
  --restart unless-stopped \
  clickhouse/clickhouse-server:latest
```

---

### 五、常用命令速查

| 操作 | 命令 |
|------|------|
| 启动容器 | `docker start clickhouse-server` |
| 停止容器 | `docker stop clickhouse-server` |
| 重启容器 | `docker restart clickhouse-server` |
| 查看日志 | `docker logs clickhouse-server -f` |
| 进入容器 | `docker exec -it clickhouse-server bash` |
| 客户端连接 | `docker exec -it clickhouse-server clickhouse-client` |
| 带用户连接 | `docker exec -it clickhouse-server clickhouse-client --user lingluody --password 'pass'` |
| 直接执行SQL | `docker exec -it clickhouse-server clickhouse-client --query "SELECT 1"` |

---

### 六、MySQL 风格语法对照

ClickHouse 支持 MySQL 风格的用户管理：

```sql
-- 创建用户（MySQL 风格）
CREATE USER IF NOT EXISTS 'username'@'host' IDENTIFIED BY 'password';

-- 授予权限
GRANT ALL PRIVILEGES ON database.* TO 'username'@'host';

-- 刷新权限（ClickHouse 自动生效，无需此命令）
-- FLUSH PRIVILEGES;  -- 不需要执行
```

---

### 七、安全建议

1. **修改 default 用户密码**
   ```sql
   ALTER USER default IDENTIFIED BY 'secure_password';
   ```

2. **限制远程访问**
   ```sql
   CREATE USER lingluody IDENTIFIED BY 'password' HOST IP '192.168.1.%';
   ```

3. **使用强密码策略**
   - 至少 12 位字符
   - 包含大小写字母、数字、特殊符号

4. **定期备份**
   ```bash
   docker exec clickhouse-server clickhouse-client --query "BACKUP DATABASE log_analysis TO Disk('backups', 'backup.zip')"
   ```

---

### 八、故障排查

| 问题 | 解决方案 |
|------|----------|
| 无法连接 | 检查端口映射：`docker ps` |
| 权限拒绝 | 确认用户名和密码正确 |
| 容器 unhealthy | 通常不影响使用，重启容器即可 |
| 数据丢失 | 检查是否挂载了数据卷 |

---

这份手册涵盖了 ClickHouse Docker 部署的核心操作，保存备用即可。需要我补充其他内容吗？