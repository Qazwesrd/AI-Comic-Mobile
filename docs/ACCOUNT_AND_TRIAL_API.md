# 账号与试用 API（原型阶段）

Base URL: `/api/v1`

## 注册
`POST /auth/register`
```json
{ "email": "user@example.com", "password": "at-least-10-chars" }
```
成功返回 bearer access token 和用户资料。

## 登录
`POST /auth/login`
请求体与注册相同。错误凭据统一返回 401。

## 当前用户
`GET /auth/me`
请求头：`Authorization: Bearer <access_token>`

## 激活设备/开始试用
`POST /license/activate`
```json
{ "device_id": "client-generated-stable-uuid", "platform": "android" }
```
同一账号的试用开始时间只记录一次，重装/换设备不能重置。设备 ID 是客户端标识，不应被视为强身份凭据；正式版需补充设备迁移策略和异常风控。

## 查询授权状态
`GET /license/status`
状态：
- `not_activated`：尚未开始试用
- `trial`：72 小时试用中
- `expired`：试用已结束
- `permanent`：服务端永久授权

## 安全与未完成项
当前是开发原型：JWT 使用 HS256；密码使用 pwdlib 推荐哈希；生产环境必须配置高熵 APP_SECRET_KEY、HTTPS、数据库迁移、速率限制、邮箱验证、密码找回、审计日志和密钥管理。
当前没有支付接口，也没有任何客户端可调用的永久授权授予接口。永久授权只能在未来由经过验签的服务端支付事件授予。
