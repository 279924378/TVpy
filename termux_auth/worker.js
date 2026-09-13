// 段德机器人 TVBox订阅鉴权代理 Worker
// 部署到Cloudflare Workers，无需公网IP/内网穿透

const GITHUB_RAW = "https://raw.githubusercontent.com/jwarrenrzflynn/TVpy/main";
const TOKEN_FILE = "termux_auth/tokens.json"; // token存在GitHub这个文件里

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // 1. 根路径返回说明
    if (url.pathname === "/" || url.pathname === "") {
      return new Response(`
        <h1>段德机器人 TVBox订阅鉴权服务</h1>
        <p>使用方式: /tvbox.json?token=你的token</p>
        <p>获取token: 在Telegram群 @机器人 发送 "订阅地址"</p>
      `, {headers: {"Content-Type": "text/html; charset=utf-8"}});
    }
    
    // 2. 获取token（从query参数或header）
    const token = url.searchParams.get("token") || request.headers.get("X-Token");
    if (!token) {
      return new Response(JSON.stringify({error: "缺少token", msg: "请在群里@机器人获取订阅地址"}), 
        {status: 403, headers: {"Content-Type": "application/json"}});
    }
    
    // 3. 从GitHub获取token列表并验证
    try {
      const tokenResp = await fetch(`${GITHUB_RAW}/${TOKEN_FILE}`);
      if (!tokenResp.ok) throw new Error("无法获取token列表");
      const tokenData = await tokenResp.json();
      
      const validToken = tokenData.tokens.find(t => 
        t.token === token && 
        t.status === "active" && 
        (!t.expire_at || new Date(t.expire_at) > new Date())
      );
      
      if (!validToken) {
        return new Response(JSON.stringify({error: "token无效或已过期", msg: "请重新在群里@机器人获取"}), 
          {status: 403, headers: {"Content-Type": "application/json"}});
      }
      
      // 4. token有效，从GitHub拉取tvbox.json并返回
      const path = url.pathname.startsWith("/") ? url.pathname.substring(1) : "tvbox.json";
      const targetUrl = `${GITHUB_RAW}/${path}`;
      
      const fileResp = await fetch(targetUrl);
      if (!fileResp.ok) {
        return new Response(JSON.stringify({error: "文件不存在", path: path}), 
          {status: 404, headers: {"Content-Type": "application/json"}});
      }
      
      const content = await fileResp.text();
      const contentType = path.endsWith(".json") ? "application/json; charset=utf-8" : 
                         path.endsWith(".py") ? "text/plain; charset=utf-8" : 
                         "application/octet-stream";
      
      return new Response(content, {
        status: 200,
        headers: {
          "Content-Type": contentType,
          "Cache-Control": "no-cache",
          "X-Auth-User": validToken.user || "unknown"
        }
      });
      
    } catch (e) {
      return new Response(JSON.stringify({error: "鉴权服务异常", msg: e.message}), 
        {status: 500, headers: {"Content-Type": "application/json"}});
    }
  }
};
