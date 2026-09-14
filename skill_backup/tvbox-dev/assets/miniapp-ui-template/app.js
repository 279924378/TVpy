(function () {
  'use strict';
  function getHost() {
    var base = new Date(2026, 1, 1, 17, 0, 0);
    var now = new Date();
    var cut = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 17, 0, 0);
    if (now.getTime() < cut.getTime()) cut.setDate(cut.getDate() - 1);
    var diff = Math.floor((cut.getTime() - base.getTime()) / 86400000);
    var num = 232 + diff;
    var map = ['零','壹','贰','叁','肆','伍','陆','柒','捌','玖'];
    var s = String(num), prefix = '';
    for (var i = 0; i < s.length; i++) prefix += map[parseInt(s[i])];
    try {
      var u = new URL('https://' + prefix + '.avzxmf127.sbs');
      return 'https://' + u.host;
    } catch (e) {
      return 'https://' + prefix + '.avzxmf127.sbs';
    }
  }
  var HOST = getHost();
  var UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
  var CATS = [
    { id: "23", name: "国产视频" }, { id: "25", name: "国产传媒" },
    { id: "26", name: "日本有码" }, { id: "27", name: "日本无码" },
    { id: "28", name: "欧美无码" }, { id: "29", name: "强奸乱伦" },
    { id: "30", name: "制服诱惑" }, { id: "31", name: "国产主播" },
    { id: "32", name: "激情动漫" }, { id: "33", name: "明星换脸" },
    { id: "34", name: "抖阴视频" }, { id: "35", name: "女优明星" },
    { id: "36", name: "网曝黑料" }, { id: "37", name: "伦理三级" },
    { id: "38", name: "AV解说" }, { id: "39", name: "SM调教" },
    { id: "40", name: "萝莉少女" }, { id: "41", name: "极品媚黑" },
    { id: "42", name: "女同性恋" }, { id: "43", name: "网红头条" },
    { id: "44", name: "人妖系列" }, { id: "45", name: "韩国主播" },
    { id: "46", name: "VR视角" }, { id: "71", name: "偷拍自拍" },
    { id: "72", name: "国产大制作" }, { id: "73", name: "乱伦毁三观" },
    { id: "74", name: "嫖妓全过程" }, { id: "75", name: "淫乱学生妹" },
    { id: "76", name: "黑料不打烊" }, { id: "77", name: "监控摄像头" },
    { id: "78", name: "主播网红" }, { id: "79", name: "高清无码" },
    { id: "80", name: "中文字幕" }, { id: "81", name: "成人综艺" },
    { id: "82", name: "媚黑母狗" }, { id: "83", name: "为国争光" },
    { id: "84", name: "少女破处" }, { id: "85", name: "人兽典藏" },
    { id: "86", name: "中文剧情" }, { id: "87", name: "燃烧荷尔蒙" },
    { id: "88", name: "女同口交" }, { id: "89", name: "重口味" },
    { id: "90", name: "3D动漫" }, { id: "91", name: "剧情故事" },
    { id: "92", name: "同人动漫" }, { id: "93", name: "激情中字" },
    { id: "94", name: "东南亚" },
  ];
  var FEED_CATS = ["26", "27", "23", "25", "29", "30", "35", "79", "80"];
  var HOT_WORDS = ["三上悠亚","河北彩花","桃乃木香奈","波多野结衣","深田咏美","葵司","松本一香","明里紬","中出","制服","人妻","巨乳","OL","学生","护士","女教师"];
  var TREE_CATS = [
    { name: "国产视频", children: [
      { id: "23", name: "国产视频" }, { id: "36", name: "网曝黑料" },
      { id: "34", name: "抖阴视频" }, { id: "38", name: "AV解说" },
      { id: "71", name: "偷拍自拍" }, { id: "77", name: "监控摄像头" },
      { id: "84", name: "少女破处" }, { id: "83", name: "为国争光" },
    ]},
    { name: "国产传媒", children: [
      { id: "25", name: "国产传媒" }, { id: "72", name: "国产大制作" },
      { id: "86", name: "中文剧情" }, { id: "91", name: "剧情故事" },
      { id: "87", name: "燃烧荷尔蒙" }, { id: "74", name: "嫖妓全过程" },
      { id: "75", name: "淫乱学生妹" }, { id: "76", name: "黑料不打烊" },
    ]},
    { name: "日本有码", children: [
      { id: "26", name: "日本有码" }, { id: "30", name: "制服诱惑" },
      { id: "35", name: "女优明星" }, { id: "80", name: "中文字幕" },
      { id: "93", name: "激情中字" }, { id: "37", name: "伦理三级" },
      { id: "81", name: "成人综艺" },
    ]},
    { name: "日本无码", children: [
      { id: "27", name: "日本无码" }, { id: "79", name: "高清无码" },
      { id: "29", name: "强奸乱伦" }, { id: "73", name: "乱伦毁三观" },
      { id: "39", name: "SM调教" }, { id: "89", name: "重口味" },
      { id: "85", name: "人兽典藏" },
    ]},
    { name: "主播网红", children: [
      { id: "31", name: "国产主播" }, { id: "45", name: "韩国主播" },
      { id: "78", name: "主播网红" }, { id: "43", name: "网红头条" },
      { id: "33", name: "明星换脸" }, { id: "41", name: "极品媚黑" },
      { id: "82", name: "媚黑母狗" },
    ]},
    { name: "动漫二次元", children: [
      { id: "32", name: "激情动漫" }, { id: "90", name: "3D动漫" },
      { id: "92", name: "同人动漫" }, { id: "40", name: "萝莉少女" },
      { id: "42", name: "女同性恋" }, { id: "88", name: "女同口交" },
      { id: "44", name: "人妖系列" }, { id: "94", name: "东南亚" },
    ]},
    { name: "其他精选", children: [
      { id: "28", name: "欧美无码" }, { id: "46", name: "VR视角" },
      { id: "24", name: "中文字幕" }, { id: "20", name: "更多精彩" },
      { id: "22", name: "稀缺资源" },
    ]},
  ];

  var state = {
    feedItems: [],
    feedPage: 1,
    feedTotalPages: 1,
    feedLoading: false,
    feedCatIdx: 0,
    currentFeedIdx: -1,
    feedMuted: false,
    playUrlCache: {},
    catId: CATS[0].id,
    catPage: 1,
    catTotalPages: 1,
    catLoading: false,
    treePrimaryIdx: 0,
    searchKw: "",
    searchPage: 1,
    searchTotalPages: 1,
    searchLoading: false,
    mineTab: "fav",
  };

  var fullHls = null;
  var fullSpeedIdx = 0;
  var SPEEDS = [1.0, 1.25, 1.5, 2.0, 0.5];

  function $(id) { return document.getElementById(id); }
  function esc(s) { var d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }
  function fmt(t) {
    if (!isFinite(t) || t < 0) t = 0;
    var m = Math.floor(t / 60), s = Math.floor(t % 60);
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  function toast(msg) {
    var t = $("toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(t._t); t._t = setTimeout(function () { t.classList.remove("show"); }, 2000);
  }

  /* ========== 数据层 ========== */
  function fetchHTML(url) {
    return ant.request({
      url: url, method: "GET",
      headers: { "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9" },
      timeout: 15000,
    }).then(function (resp) {
      if (resp.statusCode !== 200) throw new Error("HTTP " + resp.statusCode);
      return resp.data;
    });
  }

  function parseList(html) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    var items = [], seen = {};
    var boxes = doc.querySelectorAll(".stui-vodlist__box");
    for (var i = 0; i < boxes.length; i++) {
      var a = boxes[i].querySelector('a[href*="/vodhtml/"]');
      if (!a) continue;
      var m = (a.getAttribute("href") || "").match(/\/vodhtml\/(\d+)\.html/);
      if (!m || seen[m[1]]) continue;
      seen[m[1]] = 1;
      var pic = a.getAttribute("data-original") || "";
      if (!pic) { var img = a.querySelector("img"); if (img) pic = img.getAttribute("src") || img.getAttribute("data-original") || ""; }
      items.push({
        vod_id: m[1],
        vod_name: a.getAttribute("title") || a.textContent.trim(),
        vod_pic: pic,
      });
    }
    var totalPages = 1, links = doc.querySelectorAll("a");
    for (var j = 0; j < links.length; j++) {
      var href = links[j].getAttribute("href") || "";
      var pm = href.match(/\/page\/(\d+)\.html/);
      if (pm && parseInt(pm[1]) > totalPages) totalPages = parseInt(pm[1]);
    }
    return { items: items, totalPages: totalPages };
  }

  function fetchPlayUrl(vodId) {
    if (state.playUrlCache[vodId]) return Promise.resolve(state.playUrlCache[vodId]);
    return fetchHTML(HOST + "/vodplayhtml/" + vodId + "/index_1_1.html").then(function (html) {
      var m = html.match(/var player_aaaa\s*=\s*(\{.*?\})/);
      var url = "";
      if (m) {
        try {
          var obj = JSON.parse(m[1]);
          url = obj.url || "";
        } catch (e) {
          var um = m[1].match(/"url"\s*:\s*"([^"]+)"/);
          if (um) url = um[1].replace(/\\\//g, "/");
        }
      }
      state.playUrlCache[vodId] = url;
      return url;
    }).catch(function () { return ""; });
  }

  function preloadPlayUrls(startIdx, count) {
    for (var i = startIdx; i < Math.min(startIdx + count, state.feedItems.length); i++) {
      if (!state.playUrlCache[state.feedItems[i].vod_id]) {
        fetchPlayUrl(state.feedItems[i].vod_id);
      }
    }
  }

  /* ========== HLS 播放器 ========== */
  function loadHls(video, url, onError) {
    if (video._hls) { try { video._hls.destroy(); } catch (e) {} video._hls = null; }
    var native = video.canPlayType && video.canPlayType("application/vnd.apple.mpegurl");
    if (native || (typeof Hls === "undefined") || !Hls.isSupported()) {
      video.src = url;
      return null;
    }
    var hls = new Hls({ enableWorker: false, lowLatencyMode: false, maxBufferLength: 30 });
    video._hls = hls;
    if (onError) {
      hls.on(Hls.Events.ERROR, function (event, data) {
        if (data.fatal) onError(data.type + ":" + data.details);
      });
    }
    hls.loadSource(url);
    hls.attachMedia(video);
    return hls;
  }

  /* ========== 视频流 ========== */
  function loadFeedPage(reset) {
    if (state.feedLoading) return;
    if (reset) {
      state.feedPage = 1;
      state.feedItems = [];
      $("feedContainer").innerHTML = "";
      state.currentFeedIdx = -1;
    }
    if (state.feedPage > state.feedTotalPages && !reset) return;
    state.feedLoading = true;
    $("feedTip").classList.remove("hidden");
    $("feedTip").textContent = "正在加载视频...";
    var catId = FEED_CATS[state.feedCatIdx % FEED_CATS.length];
    var url = state.feedPage <= 1
      ? HOST + "/index.php/vod/show/id/" + catId + ".html"
      : HOST + "/index.php/vod/show/id/" + catId + "/page/" + state.feedPage + ".html";
    fetchHTML(url).then(function (html) {
      var res = parseList(html);
      state.feedTotalPages = res.totalPages;
      state.feedItems = state.feedItems.concat(res.items);
      renderFeedItems(res.items);
      preloadPlayUrls(state.feedItems.length - res.items.length, 5);
      state.feedPage++;
      state.feedLoading = false;
      $("feedTip").classList.add("hidden");
      if (state.currentFeedIdx < 0) playFeedAt(0);
    }).catch(function (e) {
      state.feedLoading = false;
      $("feedTip").textContent = "加载失败，上拉重试";
      toast("加载失败: " + (e.message || e));
    });
  }

  function renderFeedItems(items) {
    var frag = "";
    for (var i = 0; i < items.length; i++) {
      var v = items[i];
      var idx = state.feedItems.length - items.length + i;
      var code = v.vod_name.match(/^([A-Z]{2,6}-\d+)/);
      frag += '<div class="feed-item" data-idx="' + idx + '" data-id="' + v.vod_id + '">' +
        '<video class="feed-video" playsinline webkit-playsinline x5-playsinline loop muted></video>' +
        '<div class="feed-cover"><img src="' + esc(v.vod_pic) + '" alt=""></div>' +
        '<div class="feed-loading hidden"><div class="spinner"></div></div>' +
        '<div class="feed-center-play hidden"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></div>' +
        '<div class="feed-side-bar">' +
          '<div style="display:flex;flex-direction:column;align-items:center">' +
            '<div class="feed-avatar">' + (code ? code[1].charAt(0) : "影") + '</div>' +
            '<div class="feed-follow">+</div>' +
          '</div>' +
          '<div class="feed-side-btn feed-like" data-idx="' + idx + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>' +
            '<span>点赞</span></div>' +
          '<div class="feed-side-btn feed-fav" data-idx="' + idx + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>' +
            '<span>收藏</span></div>' +
          '<div class="feed-side-btn feed-share" data-idx="' + idx + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.59 13.51 6.83 3.98M15.41 6.51l-6.82 3.98"/></svg>' +
            '<span>分享</span></div>' +
        '</div>' +
        '<div class="feed-bottom-bar">' +
          '<div class="feed-author">@' + esc(code ? code[1] : "红果影视") + '</div>' +
          '<div class="feed-desc">' + esc(v.vod_name) + '</div>' +
          '<div class="feed-music"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg><span>原声 - 红果影视</span></div>' +
        '</div>' +
        '<div class="feed-progress"><div class="feed-progress-bar"></div></div>' +
      '</div>';
    }
    $("feedContainer").insertAdjacentHTML("beforeend", frag);
  }

  function playFeedAt(idx) {
    if (idx < 0 || idx >= state.feedItems.length) return;
    if (idx === state.currentFeedIdx) return;
    var items = $("feedContainer").querySelectorAll(".feed-item");
    for (var i = 0; i < items.length; i++) {
      var video = items[i].querySelector(".feed-video");
      if (video) { video.pause(); }
      var center = items[i].querySelector(".feed-center-play");
      if (center) center.classList.add("hidden");
    }
    state.currentFeedIdx = idx;
    var item = items[idx];
    if (!item) return;
    var video = item.querySelector(".feed-video");
    var cover = item.querySelector(".feed-cover");
    var loading = item.querySelector(".feed-loading");
    var v = state.feedItems[idx];
    preloadPlayUrls(idx + 1, 3);
    var url = state.playUrlCache[v.vod_id];
    if (url) {
      startFeedVideo(video, url, cover, loading, item);
    } else {
      loading.classList.remove("hidden");
      fetchPlayUrl(v.vod_id).then(function (u) {
        if (state.currentFeedIdx !== idx) return;
        loading.classList.add("hidden");
        if (u) startFeedVideo(video, u, cover, loading, item);
        else toast("播放地址获取失败");
      });
    }
    addHistory(v);
  }

  function startFeedVideo(video, url, cover, loading, item) {
    video.muted = state.feedMuted;
    loadHls(video, url, function (err) {
      loading.classList.add("hidden");
      cover.classList.remove("hidden");
    });
    video._progressBar = item.querySelector(".feed-progress-bar");
    video.addEventListener("loadeddata", function () {
      cover.classList.add("hidden");
      loading.classList.add("hidden");
    }, { once: true });
    video.addEventListener("timeupdate", function () {
      if (video._progressBar && video.duration) {
        video._progressBar.style.width = (video.currentTime / video.duration * 100) + "%";
      }
    });
    var p = video.play();
    if (p && p.catch) p.catch(function () {
      if (!video.muted) {
        video.muted = true;
        video.play().catch(function () {});
      }
    });
  }

  function bindFeedEvents() {
    var container = $("feedContainer");
    container.addEventListener("scroll", function () {
      var h = container.clientHeight;
      var scrollTop = container.scrollTop;
      var idx = Math.round(scrollTop / h);
      if (idx !== state.currentFeedIdx) playFeedAt(idx);
      if (scrollTop + h >= container.scrollHeight - h * 2) {
        loadFeedPage(false);
      }
    });

    container.addEventListener("click", function (e) {
      var sideBtn = e.target.closest(".feed-side-btn");
      if (sideBtn) {
        var idx = parseInt(sideBtn.getAttribute("data-idx"));
        var v = state.feedItems[idx];
        if (sideBtn.classList.contains("feed-like")) {
          sideBtn.classList.toggle("active");
          toast(sideBtn.classList.contains("active") ? "已点赞" : "已取消");
        } else if (sideBtn.classList.contains("feed-fav")) {
          toggleFav(v, function (faved) {
            sideBtn.classList.toggle("active", faved);
          });
        } else if (sideBtn.classList.contains("feed-share")) {
          toast("分享链接已复制");
        }
        return;
      }
      var item = e.target.closest(".feed-item");
      if (!item) return;
      var video = item.querySelector(".feed-video");
      if (!video) return;
      if (video.paused) {
        var p = video.play();
        if (p && p.catch) p.catch(function () {});
        item.querySelector(".feed-center-play").classList.add("hidden");
      } else {
        video.pause();
        item.querySelector(".feed-center-play").classList.remove("hidden");
      }
    });

    container.addEventListener("dblclick", function (e) {
      var item = e.target.closest(".feed-item");
      if (!item || e.target.closest(".feed-side-btn")) return;
      var sideBtn = item.querySelector(".feed-like");
      if (sideBtn) {
        sideBtn.classList.add("active");
        toast("已点赞");
      }
    });

    $("feedCatBtn").addEventListener("click", function () {
      state.feedCatIdx = (state.feedCatIdx + 1) % FEED_CATS.length;
      var catName = "";
      for (var i = 0; i < CATS.length; i++) {
        if (CATS[i].id === FEED_CATS[state.feedCatIdx]) { catName = CATS[i].name; break; }
      }
      this.textContent = catName || "分类";
      loadFeedPage(true);
      toast("已切换到: " + (catName || "推荐"));
    });
    $("feedSearchBtn").addEventListener("click", function () { switchTab("search"); });
  }

  /* ========== 分类页 ========== */
  function renderTreePrimary() {
    var html = "";
    for (var i = 0; i < TREE_CATS.length; i++) {
      html += '<div class="tree-primary-item' + (i === state.treePrimaryIdx ? ' active' : '') + '" data-idx="' + i + '">' + TREE_CATS[i].name + '</div>';
    }
    $("treePrimary").innerHTML = html;
  }

  function renderTreeSecondary() {
    var parent = TREE_CATS[state.treePrimaryIdx];
    if (!parent) return;
    var html = "";
    for (var i = 0; i < parent.children.length; i++) {
      var c = parent.children[i];
      html += '<span class="tree-secondary-tag' + (c.id === state.catId ? ' active' : '') + '" data-id="' + c.id + '">' + c.name + '</span>';
    }
    $("treeSecondary").innerHTML = html;
  }

  function selectTreePrimary(idx) {
    state.treePrimaryIdx = idx;
    renderTreePrimary();
    renderTreeSecondary();
    $("catGrid").innerHTML = "";
    $("catEmpty").textContent = "请选择子分类";
    $("catEmpty").style.display = "block";
    $("catLoadMore").textContent = "上拉加载更多";
  }

  function loadCatPage(reset) {
    if (state.catLoading) return;
    if (reset) { state.catPage = 1; state.catTotalPages = 1; $("catGrid").innerHTML = ""; $("catEmpty").style.display = "none"; }
    if (state.catPage > state.catTotalPages && !reset) { $("catLoadMore").textContent = "没有更多了"; return; }
    state.catLoading = true;
    $("catLoadMore").textContent = "加载中...";
    var url = state.catPage <= 1 ? HOST + "/index.php/vod/show/id/" + state.catId + ".html" : HOST + "/index.php/vod/show/id/" + state.catId + "/page/" + state.catPage + ".html";
    fetchHTML(url).then(function (html) {
      var res = parseList(html);
      state.catTotalPages = res.totalPages;
      var frag = "";
      for (var i = 0; i < res.items.length; i++) frag += videoCardHTML(res.items[i]);
      $("catGrid").insertAdjacentHTML("beforeend", frag);
      state.catPage++;
      state.catLoading = false;
      if ($("catGrid").children.length === 0) { $("catEmpty").textContent = "暂无数据"; $("catEmpty").style.display = "block"; }
      $("catLoadMore").textContent = state.catPage > state.catTotalPages ? "没有更多了" : "上拉加载更多";
    }).catch(function (e) {
      state.catLoading = false;
      $("catLoadMore").textContent = "加载失败，点击重试";
      toast("加载失败: " + (e.message || e));
    });
  }

  function videoCardHTML(v) {
    var badge = "";
    var m = v.vod_name.match(/^([A-Z]{2,6}-\d+)/);
    if (m) badge = '<div class="video-badge">' + m[1] + '</div>';
    return '<div class="video-card" data-id="' + v.vod_id + '" data-name="' + esc(v.vod_name) + '" data-pic="' + esc(v.vod_pic) + '">' +
      '<div class="video-cover">' + (v.vod_pic ? '<img src="' + esc(v.vod_pic) + '" alt="" loading="lazy">' : '') + badge + '</div>' +
      '<div class="video-info"><div class="video-title">' + esc(v.vod_name) + '</div></div></div>';
  }

  /* ========== 搜索 ========== */
  function renderHotTags() {
    var html = "";
    for (var i = 0; i < HOT_WORDS.length; i++) {
      html += '<span class="hot-tag' + (i < 3 ? ' hot' : '') + '" data-kw="' + esc(HOT_WORDS[i]) + '">' + esc(HOT_WORDS[i]) + '</span>';
    }
    $("hotTags").innerHTML = html;
  }

  function doSearch(kw) {
    if (!kw || !kw.trim()) { toast("请输入搜索关键词"); return; }
    state.searchKw = kw.trim();
    state.searchPage = 1; state.searchTotalPages = 1; state.searchLoading = false;
    $("searchHot").style.display = "none";
    $("searchResults").style.display = "block";
    $("searchGrid").innerHTML = "";
    loadSearchPage();
  }

  function loadSearchPage() {
    if (state.searchLoading) return;
    if (state.searchPage > state.searchTotalPages) { $("searchLoadMore").textContent = "没有更多了"; return; }
    state.searchLoading = true;
    $("searchLoadMore").textContent = "加载中...";
    var enc = encodeURIComponent(state.searchKw);
    var url = state.searchPage <= 1 ? HOST + "/index.php/vod/search.html?wd=" + enc : HOST + "/index.php/vod/search/wd/" + enc + "/page/" + state.searchPage + ".html";
    fetchHTML(url).then(function (html) {
      var res = parseList(html);
      state.searchTotalPages = res.totalPages;
      var frag = "";
      for (var i = 0; i < res.items.length; i++) frag += videoCardHTML(res.items[i]);
      $("searchGrid").insertAdjacentHTML("beforeend", frag);
      state.searchPage++;
      state.searchLoading = false;
      if ($("searchGrid").children.length === 0) $("searchGrid").innerHTML = '<div class="empty-tip">未找到相关影片</div>';
      $("searchLoadMore").textContent = state.searchPage > state.searchTotalPages ? "没有更多了" : "上拉加载更多";
    }).catch(function (e) {
      state.searchLoading = false;
      $("searchLoadMore").textContent = "加载失败";
      toast("搜索失败: " + (e.message || e));
    });
  }

  /* ========== 收藏/历史 ========== */
  function getFav() { return ant.storage.getJSON("fav_list").then(function (d) { return d || []; }, function () { return []; }); }
  function setFav(l) { return ant.storage.setJSON("fav_list", l); }
  function getHistory() { return ant.storage.getJSON("history_list").then(function (d) { return d || []; }, function () { return []; }); }
  function setHistory(l) { return ant.storage.setJSON("history_list", l); }

  function addHistory(v) {
    getHistory().then(function (list) {
      list = list.filter(function (x) { return x.vod_id !== v.vod_id; });
      list.unshift({ vod_id: v.vod_id, vod_name: v.vod_name, vod_pic: v.vod_pic, time: Date.now() });
      if (list.length > 100) list = list.slice(0, 100);
      setHistory(list);
    });
  }

  function toggleFav(v, cb) {
    getFav().then(function (list) {
      var idx = -1;
      for (var i = 0; i < list.length; i++) { if (list[i].vod_id === v.vod_id) { idx = i; break; } }
      var faved;
      if (idx >= 0) { list.splice(idx, 1); faved = false; toast("已取消收藏"); }
      else { list.unshift({ vod_id: v.vod_id, vod_name: v.vod_name, vod_pic: v.vod_pic, time: Date.now() }); faved = true; toast("已收藏"); }
      setFav(list);
      if (cb) cb(faved);
    });
  }

  function renderMine() {
    var getter = state.mineTab === "fav" ? getFav : getHistory;
    getter().then(function (list) {
      if (!list || list.length === 0) { $("mineGrid").innerHTML = ""; $("mineEmpty").style.display = "block"; return; }
      $("mineEmpty").style.display = "none";
      var html = "";
      for (var i = 0; i < list.length; i++) html += videoCardHTML(list[i]);
      $("mineGrid").innerHTML = html;
    });
  }

  /* ========== 全屏播放器 ========== */
  function openFullPlayer(v) {
    $("fullPlayerPage").classList.add("show");
    $("fullPlayerTitle").textContent = v.vod_name;
    $("fullPlayerLoading").style.display = "flex";
    $("fullCenterPlay").style.display = "none";
    fullSpeedIdx = 0;
    $("fullSpeedBtn").textContent = "1.0x";
    var video = $("fullVideo");
    video.muted = false;
    video.loop = false;
    video.currentTime = 0;
    addHistory(v);
    var loadTimer = setTimeout(function () {
      $("fullPlayerLoading").style.display = "none";
      toast("播放加载超时，请重试");
    }, 20000);
    fetchPlayUrl(v.vod_id).then(function (url) {
      if (!url) { clearTimeout(loadTimer); $("fullPlayerLoading").style.display = "none"; toast("播放地址获取失败"); return; }
      loadHls(video, url, function (err) {
        clearTimeout(loadTimer);
        $("fullPlayerLoading").style.display = "none";
        toast("播放器错误: " + err);
      });
      video.addEventListener("loadedmetadata", function () {
        clearTimeout(loadTimer);
        $("fullPlayerLoading").style.display = "none";
        $("fullTime").textContent = "00:00 / " + fmt(video.duration);
        var p = video.play();
        if (p && p.catch) p.catch(function () { video.muted = true; video.play().catch(function () {}); });
      }, { once: true });
      video.addEventListener("error", function () {
        clearTimeout(loadTimer);
        $("fullPlayerLoading").style.display = "none";
        toast("视频加载失败: " + (video.error ? video.error.code : "unknown"));
      }, { once: true });
    }).catch(function (e) {
      clearTimeout(loadTimer);
      $("fullPlayerLoading").style.display = "none";
      toast("播放地址请求失败: " + (e.message || e));
    });
  }

  function closeFullPlayer() {
    var video = $("fullVideo");
    video.pause();
    if (video._hls) { try { video._hls.destroy(); } catch (e) {} video._hls = null; }
    video.removeAttribute("src");
    video.load();
    $("fullPlayerPage").classList.remove("show");
  }

  function bindFullPlayer() {
    var video = $("fullVideo");
    $("fullPlayerBack").addEventListener("click", closeFullPlayer);
    $("fullPlayPauseBtn").addEventListener("click", function () {
      if (video.paused) { video.play(); } else { video.pause(); }
    });
    video.addEventListener("play", function () {
      $("fullPlayPauseBtn").querySelector(".icon-play").style.display = "none";
      $("fullPlayPauseBtn").querySelector(".icon-pause").style.display = "";
      $("fullCenterPlay").style.display = "none";
    });
    video.addEventListener("pause", function () {
      $("fullPlayPauseBtn").querySelector(".icon-play").style.display = "";
      $("fullPlayPauseBtn").querySelector(".icon-pause").style.display = "none";
      if (!video.ended) $("fullCenterPlay").style.display = "flex";
    });
    video.addEventListener("timeupdate", function () {
      if (video.duration) {
        $("fullPlayed").style.width = (video.currentTime / video.duration * 100) + "%";
        $("fullThumb").style.left = (video.currentTime / video.duration * 100) + "%";
        $("fullTime").textContent = fmt(video.currentTime) + " / " + fmt(video.duration);
      }
    });
    video.addEventListener("progress", function () {
      if (video.buffered.length && video.duration) {
        $("fullBuffered").style.width = (video.buffered.end(video.buffered.length - 1) / video.duration * 100) + "%";
      }
    });
    var seeking = false;
    $("fullProgressBar").addEventListener("click", function (e) {
      var rect = this.getBoundingClientRect();
      var pct = (e.clientX - rect.left) / rect.width;
      if (video.duration) video.currentTime = pct * video.duration;
    });
    $("fullSpeedBtn").addEventListener("click", function () {
      fullSpeedIdx = (fullSpeedIdx + 1) % SPEEDS.length;
      video.playbackRate = SPEEDS[fullSpeedIdx];
      this.textContent = SPEEDS[fullSpeedIdx] + "x";
      toast("倍速: " + SPEEDS[fullSpeedIdx] + "x");
    });
    $("fullMuteBtn").addEventListener("click", function () {
      video.muted = !video.muted;
      toast(video.muted ? "已静音" : "取消静音");
    });
    $("fullPlayerPage").addEventListener("click", function (e) {
      if (e.target.closest(".player-top-bar") || e.target.closest(".player-bottom-bar") || e.target.closest(".player-center-play")) return;
      if (video.paused) { video.play(); } else { video.pause(); }
    });
  }

  /* ========== 页面切换 ========== */
  function switchTab(tab) {
    var items = document.querySelectorAll(".tab-item");
    for (var i = 0; i < items.length; i++) items[i].classList.remove("active");
    var target = document.querySelector('.tab-item[data-tab="' + tab + '"]');
    if (target) target.classList.add("active");
    $("categoryPage").classList.remove("show");
    $("searchPage").classList.remove("show");
    $("minePage").classList.remove("show");
    $("fullPlayerPage").classList.remove("show");
    $("feedPage").style.display = "";
    if (tab === "category") {
      $("categoryPage").classList.add("show");
      if (!$("treePrimary").children.length) { renderTreePrimary(); renderTreeSecondary(); }
      if (!$("catGrid").children.length) { $("catEmpty").textContent = "请选择子分类"; $("catEmpty").style.display = "block"; }
    }
    else if (tab === "search") { $("searchPage").classList.add("show"); $("searchInput").focus(); }
    else if (tab === "mine") { $("minePage").classList.add("show"); renderMine(); }
    else {
      $("feedPage").style.display = "";
      if (state.currentFeedIdx >= 0) {
        var items2 = $("feedContainer").querySelectorAll(".feed-item");
        var cur = items2[state.currentFeedIdx];
        if (cur) { var v = cur.querySelector(".feed-video"); if (v) { var p = v.play(); if (p && p.catch) p.catch(function(){}); } }
      }
    }
  }

  function bindGlobalEvents() {
    $("tabbar").addEventListener("click", function (e) {
      var item = e.target.closest(".tab-item");
      if (!item) return;
      switchTab(item.getAttribute("data-tab"));
    });

    document.querySelectorAll("[data-close]").forEach(function (el) {
      el.addEventListener("click", function () {
        var page = this.getAttribute("data-close");
        $("categoryPage").classList.remove("show");
        $("searchPage").classList.remove("show");
        switchTab("feed");
      });
    });

    $("treePrimary").addEventListener("click", function (e) {
      var item = e.target.closest(".tree-primary-item");
      if (!item) return;
      var idx = parseInt(item.getAttribute("data-idx"));
      if (idx === state.treePrimaryIdx) return;
      selectTreePrimary(idx);
    });

    $("treeSecondary").addEventListener("click", function (e) {
      var tag = e.target.closest(".tree-secondary-tag");
      if (!tag) return;
      var id = tag.getAttribute("data-id");
      if (id === state.catId && $("catGrid").children.length > 0) return;
      state.catId = id;
      renderTreeSecondary();
      $("catEmpty").style.display = "none";
      loadCatPage(true);
    });

    $("catGrid").addEventListener("click", function (e) {
      var card = e.target.closest(".video-card");
      if (!card) return;
      openFullPlayer({ vod_id: card.getAttribute("data-id"), vod_name: card.getAttribute("data-name"), vod_pic: card.getAttribute("data-pic") });
    });

    $("catLoadMore").addEventListener("click", function () { if (this.textContent.indexOf("失败") > -1) loadCatPage(false); });

    $("searchSubmit").addEventListener("click", function () { doSearch($("searchInput").value); });
    $("searchInput").addEventListener("keydown", function (e) { if (e.key === "Enter") doSearch(this.value); });
    $("hotTags").addEventListener("click", function (e) {
      var tag = e.target.closest(".hot-tag");
      if (!tag) return;
      $("searchInput").value = tag.getAttribute("data-kw");
      doSearch(tag.getAttribute("data-kw"));
    });
    $("searchGrid").addEventListener("click", function (e) {
      var card = e.target.closest(".video-card");
      if (!card) return;
      openFullPlayer({ vod_id: card.getAttribute("data-id"), vod_name: card.getAttribute("data-name"), vod_pic: card.getAttribute("data-pic") });
    });

    var mineTabs = document.querySelectorAll(".mine-tab");
    for (var i = 0; i < mineTabs.length; i++) {
      mineTabs[i].addEventListener("click", function () {
        for (var j = 0; j < mineTabs.length; j++) mineTabs[j].classList.remove("active");
        this.classList.add("active");
        state.mineTab = this.getAttribute("data-tab");
        renderMine();
      });
    }
    $("mineGrid").addEventListener("click", function (e) {
      var card = e.target.closest(".video-card");
      if (!card) return;
      openFullPlayer({ vod_id: card.getAttribute("data-id"), vod_name: card.getAttribute("data-name"), vod_pic: card.getAttribute("data-pic") });
    });
  }

  /* ========== 初始化 ========== */
  function init() {
    renderTreePrimary();
    renderTreeSecondary();
    renderHotTags();
    bindFeedEvents();
    bindFullPlayer();
    bindGlobalEvents();
    loadFeedPage(true);
    ant.env.getSystemInfo().then(function (info) {
      if (info.isTV) {
        document.body.classList.add("tv");
        if (ant.tv && ant.tv.onKey) {
          ant.tv.onKey(function (event) {
            var items = Array.prototype.slice.call(document.querySelectorAll(".video-card,.cat-tag,.tab-item,.feed-side-btn,button,input"));
            if (!items.length) return;
            var idx = items.indexOf(document.activeElement);
            if (event.key === "ArrowDown" || event.key === "ArrowRight") idx = (idx + 1) % items.length;
            else if (event.key === "ArrowUp" || event.key === "ArrowLeft") idx = idx <= 0 ? items.length - 1 : idx - 1;
            else if (event.key === "Enter" || event.key === "Select") { if (document.activeElement) document.activeElement.click(); return; }
            else return;
            items[idx].focus();
            items[idx].scrollIntoView({ block: "nearest" });
          });
        }
      }
    }).catch(function () {});
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        var items = $("feedContainer").querySelectorAll(".feed-video");
        for (var i = 0; i < items.length; i++) items[i].pause();
      } else if ($("feedPage").style.display !== "none" && !$("categoryPage").classList.contains("show")) {
        if (state.currentFeedIdx >= 0) {
          var items2 = $("feedContainer").querySelectorAll(".feed-item");
          var cur = items2[state.currentFeedIdx];
          if (cur) { var v = cur.querySelector(".feed-video"); if (v) { var p = v.play(); if (p && p.catch) p.catch(function(){}); } }
        }
      }
    });
  }

  if (typeof ant !== "undefined" && ant.env) {
    init();
  } else {
    window.addEventListener("load", init);
  }
})();
