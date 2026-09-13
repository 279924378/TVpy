/**
 * 段德机器人 - Cloudflare Workers 订阅鉴权服务 (Service Worker格式)
 */

const CONFIG = {
  SECRET: 'lw93YfoPaOlQczMnKB8HhJ49-bWm7rIN6gGbC55aqao',
  BOT_TOKEN: '8851237263:AAFcAx3PjZuPB34Jt3aqg82UgQpEu4hNJH4',
  CHAT_ID: '-1003795519678',
  GITHUB_REPO: 'jwarrenrzflynn/TVpy',
  GITHUB_BRANCH: 'main',
  GITHUB_FILE: 'tvbox.json',
  TOKEN_VALID_HOURS: 24,
};

async function hmacSha256(message, secret) {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(secret);
  const messageData = encoder.encode(message);
  const key = await crypto.subtle.importKey('raw', keyData, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const signature = await crypto.subtle.sign('HMAC', key, messageData);
  return btoa(String.fromCharCode(...new Uint8Array(signature)));
}

function base64UrlEncode(str) {
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  return atob(str);
}

async function generateToken(userId, username) {
  const expires = Date.now() + CONFIG.TOKEN_VALID_HOURS * 60 * 60 * 1000;
  const payload = JSON.stringify({ userId, username, expires });
  const payloadB64 = base64UrlEncode(payload);
  const signature = await hmacSha256(payloadB64, CONFIG.SECRET);
  // hmacSha256返回的已是标准base64字符串，只做urlsafe字符替换，避免URL中+被解析为空格
  const signatureB64 = signature.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return payloadB64 + '.' + signatureB64;
}

async function verifyToken(token) {
  if (!token || !token.includes('.')) return { valid: false, message: '无效的Token格式' };
  const parts = token.split('.');
  const payloadB64 = parts[0];
  const signatureUrlSafe = parts[1];
  // 把urlsafe签名转换回标准base64再比较（尾部=可能已被去掉，比较时统一去掉）
  const signature = signatureUrlSafe.replace(/-/g, '+').replace(/_/g, '/').replace(/=+$/, '');
  const expectedSignature = (await hmacSha256(payloadB64, CONFIG.SECRET)).replace(/=+$/, '');
  if (signature !== expectedSignature) return { valid: false, message: 'Token签名验证失败' };
  try {
    const payload = JSON.parse(base64UrlDecode(payloadB64));
    if (Date.now() > payload.expires) return { valid: false, message: 'Token已过期，请重新获取' };
    return { valid: true, payload };
  } catch (e) {
    return { valid: false, message: 'Token解析失败' };
  }
}

async function checkUserInGroup(userId) {
  const url = 'https://api.telegram.org/bot' + CONFIG.BOT_TOKEN + '/getChatMember?chat_id=' + CONFIG.CHAT_ID + '&user_id=' + userId;
  try {
    const response = await fetch(url);
    const data = await response.json();
    if (data.ok) {
      const status = data.result.status;
      return ['creator', 'administrator', 'member', 'restricted'].includes(status);
    }
    return false;
  } catch (e) {
    console.error('检查群成员失败:', e);
    return true;
  }
}

async function fetchTvboxJson() {
  // 优先从KV读取，失败时回退到GitHub
  try {
    if (typeof TVBOX_KV !== 'undefined') {
      const content = await TVBOX_KV.get('tvbox.json');
      if (content) {
        console.log('[KV] 从KV读取tvbox.json成功');
        return content;
      }
    }
  } catch (e) {
    console.error('[KV] 读取tvbox.json失败，回退到GitHub:', e);
  }
  // 回退到GitHub
  const url = 'https://raw.githubusercontent.com/' + CONFIG.GITHUB_REPO + '/' + CONFIG.GITHUB_BRANCH + '/' + CONFIG.GITHUB_FILE;
  try {
    const response = await fetch(url, { headers: { 'User-Agent': 'TVBox-Auth-Worker' } });
    if (!response.ok) return null;
    return await response.text();
  } catch (e) {
    console.error('获取tvbox.json失败:', e);
    return null;
  }
}

async function fetchPyFile(fileName) {
  // 从KV读取py文件
  try {
    if (typeof TVBOX_KV !== 'undefined') {
      const key = 'py/' + fileName;
      const content = await TVBOX_KV.get(key);
      if (content) {
        console.log('[KV] 读取py文件成功:', fileName);
        return content;
      }
    }
  } catch (e) {
    console.error('[KV] 读取py文件失败:', fileName, e);
  }
  return null;
}

async function getTokenFromKV(token) {
  // 从KV查找短token对应的用户信息
  try {
    if (typeof TVBOX_KV !== 'undefined') {
      const key = 'token:' + token;
      const content = await TVBOX_KV.get(key);
      if (content) {
        const data = JSON.parse(content);
        // 检查是否过期
        if (data.expires && Date.now() / 1000 > data.expires) {
          return { valid: false, message: '订阅Token已过期，请重新获取' };
        }
        return { valid: true, payload: data };
      }
    }
    return { valid: false, message: '无效的订阅Token，请在群里重新获取' };
  } catch (e) {
    console.error('[KV] 查找Token失败:', e);
    return { valid: false, message: 'Token验证服务异常，请稍后重试' };
  }
}

function jsonResponse(data, status) {
  return new Response(JSON.stringify(data, null, 2), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*' }
  });
}

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const url = new URL(request.url);
  const path = url.pathname;
  const token = url.searchParams.get('token');
  const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';

  console.log('[访问] IP:', clientIP, '路径:', path, 'Token:', token ? '有' : '无');

  // 免鉴权公开地址（测试用）
  if (path === '/free' || path === '/free.json' || path === '/public' || path === '/test' || path === '/tvbox_free.json') {
    const content = await fetchTvboxJson();
    if (!content) return jsonResponse({ error: '获取订阅内容失败' }, 502);
    return new Response(content, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'max-age=300',
        'Access-Control-Allow-Origin': '*',
        'X-Content-Type-Options': 'nosniff',
        'Content-Length': content.length.toString()
      }
    });
  }

  if (path === '/get' || path === '/tvbox.json' || path === '/subscribe') {
    if (!token) return jsonResponse({ error: '缺少订阅Token，请在群里向机器人发送 /subscribe 获取' }, 401);
    
    // 短token（tk_开头）从KV查找，长token用JWT验证
    let result;
    if (token.startsWith('tk_')) {
      result = await getTokenFromKV(token);
    } else {
      result = await verifyToken(token);
    }
    
    if (!result.valid) {
      console.log('[拒绝] Token验证失败:', result.message);
      return jsonResponse({ error: result.message }, 403);
    }
    const inGroup = await checkUserInGroup(result.payload.userId);
    if (!inGroup) {
      console.log('[拒绝] 用户已退群:', result.payload.userId);
      return jsonResponse({ error: '您已不在群里，订阅地址已失效，请重新入群后获取' }, 403);
    }
    const content = await fetchTvboxJson();
    if (!content) return jsonResponse({ error: '获取订阅内容失败，请稍后重试' }, 502);
    console.log('[通过] 用户:', result.payload.username, '路径:', path);
    return new Response(content, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'max-age=300',
        'Access-Control-Allow-Origin': '*',
        'X-Content-Type-Options': 'nosniff',
        'Content-Length': content.length.toString()
      }
    });
  }

  // py文件分发（TVBox加载spider时调用，不需要Token）
  if (path.startsWith('/py/')) {
    const fileName = decodeURIComponent(path.substring(4));
    console.log('[PY] 请求py文件:', fileName);
    const content = await fetchPyFile(fileName);
    if (content) {
      return new Response(content, {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'public, max-age=3600, no-transform',
          'Access-Control-Allow-Origin': '*',
          'Content-Length': content.length.toString()
        }
      });
    }
    return jsonResponse({ error: 'py文件不存在: ' + fileName }, 404);
  }

  if (path === '/status') {
    const kvEnabled = typeof TVBOX_KV !== 'undefined';
    let kvDebug = {};
    if (kvEnabled) {
      try {
        const tvboxContent = await TVBOX_KV.get('tvbox.json');
        kvDebug.tvbox_json_size = tvboxContent ? tvboxContent.length : 0;
        if (tvboxContent) {
          try {
            const parsed = JSON.parse(tvboxContent);
            kvDebug.tvbox_spider_count = (parsed.spider || []).length;
          } catch (e) {
            kvDebug.tvbox_parse_error = e.message;
          }
        }
        // 测试读取一个py
        const pyContent = await TVBOX_KV.get('py/JavDB.py');
        kvDebug.py_javdb_size = pyContent ? pyContent.length : 0;
      } catch (e) {
        kvDebug.error = e.message;
      }
    }
    return jsonResponse({
      service: '段德机器人订阅鉴权服务 (Cloudflare Workers + KV)',
      status: 'running',
      token_valid_hours: CONFIG.TOKEN_VALID_HOURS,
      kv_enabled: kvEnabled,
      storage: kvEnabled ? 'Cloudflare KV' : 'GitHub (回退)',
      kv_debug: kvDebug,
      github_repo: CONFIG.GITHUB_REPO,
      chat_id: CONFIG.CHAT_ID,
      time: new Date().toISOString()
    });
  }

  if (path === '/generate') {
    const userId = url.searchParams.get('user_id') || 'test_user';
    const username = url.searchParams.get('username') || '测试用户';
    const newToken = await generateToken(userId, username);
    const subscribeUrl = url.origin + '/tvbox.json?token=' + newToken;
    return jsonResponse({ token: newToken, subscribe_url: subscribeUrl, expires_in_hours: CONFIG.TOKEN_VALID_HOURS });
  }

  if (path === '/verify') {
    const result = await verifyToken(token);
    return jsonResponse({ valid: result.valid, message: result.message, payload: result.payload });
  }

  return jsonResponse({ error: '页面不存在', usage: { subscribe: '/tvbox.json?token=你的Token', status: '/status' } }, 404);
}
