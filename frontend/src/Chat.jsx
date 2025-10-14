import React, { useState, useRef, useEffect, useMemo } from "react";
import MarkdownIt from "markdown-it";
import markdownItAnchor from "markdown-it-anchor";
import markdownItLinkAttrs from "markdown-it-link-attributes";
import markdownItTaskLists from "markdown-it-task-lists";
import markdownItFootnote from "markdown-it-footnote";
import markdownItMultimdTable from "markdown-it-multimd-table";
import "./Chat.css";

export default function Chat({ tickers }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const [filteredTickers, setFilteredTickers] = useState([]);
  const [showTickerSuggestions, setShowTickerSuggestions] = useState(false);
  const wsRef = useRef(null);

  const preparedTickers = useMemo(
    () =>
      tickers.map((t) => ({
        ...t,
        tickerLower: t.ticker.toLowerCase(),
        titleLower: t.title.toLowerCase(),
      })),
    [tickers]
  );

  const md = new MarkdownIt({
    html: true,
    linkify: true,
    breaks: true,
  })
    .use(markdownItAnchor)
    .use(markdownItLinkAttrs, {
      pattern: /^https?:\/\//,
      attrs: { target: "_blank", rel: "noopener" },
    })
    .use(markdownItTaskLists, { enabled: true })
    .use(markdownItFootnote)
    .use(markdownItMultimdTable);

  function genId() {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  const getBestImage = (images) => {
    if (!images) return null;
    if (Array.isArray(images)) {
      const small = images.find((i) => i.size?.toLowerCase?.() === "small");
      if (small?.url) return small.url;
      const thumb = images.find((i) => i.size?.toLowerCase?.() === "thumb");
      if (thumb?.url) return thumb.url;
      return images[0]?.url || null;
    }
    if (typeof images === "object") {
      return images.small || images.thumb || images.url || images.src || null;
    }
    return null;
  };

  const parseHeadlineFromUrl = (url) => {
    if (!url) return "";
    try {
      const last = url.split("/").filter(Boolean).pop() || url;
      const clean = last.split("?")[0].split("#")[0];
      return clean
        .split("-")
        .map((w) => (w.length ? w[0].toUpperCase() + w.slice(1) : ""))
        .join(" ");
    } catch {
      return url;
    }
  };

  // -------- TICKER SEARCH HANDLING --------
  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);

    let query = val;
    const hashIndex = val.lastIndexOf("#");
    if (hashIndex !== -1) query = val.slice(hashIndex + 1);

    query = query.trim().toLowerCase();

    if (query.length > 0) {
        const results = preparedTickers
        .filter(
            (t) => t.tickerLower.includes(query) || t.titleLower.includes(query)
        )
        .slice(0, 10);
        setFilteredTickers(results);
        setShowTickerSuggestions(results.length > 0);
    } else {
        setShowTickerSuggestions(false);
    }
    };

    const selectTicker = (ticker) => {
    const hashIndex = input.lastIndexOf("#");
    const newInput =
        hashIndex !== -1
        ? input.slice(0, hashIndex) + ticker.toUpperCase() + " "
        : ticker.toUpperCase() + " ";
    setInput(newInput);
    setShowTickerSuggestions(false);
    };


  // -------- EXISTING CHAT LOGIC --------
  const sendQuery = (query) => {
    if (!query.trim()) return;

    setMessages((prev) => [
      ...prev,
      { sender: "user", text: query },
    ]);

    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`${import.meta.env.VITE_BACK_URL}/chat`);
    wsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({ query }));

    ws.onmessage = async (evt) => {
      let parsed;
      try { parsed = JSON.parse(evt.data); } 
      catch { parsed = { response: String(evt.data) }; }

      setMessages((prev) => {
        const last = prev[prev.length - 1];
        const lastIsBot = last?.sender === "bot";
        const lastStreaming = lastIsBot && !last.done;

        const createBotEntry = (resp = "") => ({
          sender: "bot",
          text: resp || "",
          latestUpdate: parsed.update || null,
          resources: [],
          done: Boolean(parsed.done),
          showResources: false,
        });

        const isResourceUpdate = parsed.update && (parsed.pic || parsed.url || parsed.headline);
        const imagesArr = parsed.pic ?? null;

        if (!lastIsBot || !lastStreaming) {
          const newEntry = createBotEntry(parsed.response || "");
          if (isResourceUpdate) {
            const resourceUrl = parsed.update || parsed.url || null;
            const headline = parsed.headline || null;
            const thumbnail = getBestImage(imagesArr);
            if (resourceUrl) {
              newEntry.resources = [{
                id: genId(),
                url: resourceUrl,
                headline,
                images: Array.isArray(imagesArr) ? imagesArr : [],
                thumbnail,
              }];
            }
          }
          return [...prev, newEntry];
        } else {
          const updated = { ...last };
          if (parsed.response !== undefined) updated.text = String(parsed.response);
          if (parsed.update && !isResourceUpdate) updated.latestUpdate = parsed.update;

          if (isResourceUpdate) {
            const resourceUrl = parsed.update || parsed.url || null;
            const headline = parsed.headline || null;
            const thumbnail = getBestImage(imagesArr);
            const resources = Array.isArray(updated.resources) ? [...updated.resources] : [];
            const exists = resourceUrl && resources.some((r) => r.url === resourceUrl);
            if (resourceUrl && !exists) resources.push({ id: genId(), url: resourceUrl, headline, images: Array.isArray(imagesArr) ? imagesArr : [], thumbnail });
            updated.resources = resources;
            updated.latestUpdate = parsed.update || resourceUrl;
          }

          if (parsed.done) { updated.done = true; updated.latestUpdate = null; }

          return [...prev.slice(0, -1), updated];
        }
      });
    };

    ws.onerror = () => setError("Hmm... something went wrong. Try again later.");
  };

  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  return (
   <div
    style={{
    padding: 20,
    fontFamily: "'Inter', 'Open Sans', sans-serif",
    fontWeight: 400,
    lineHeight: 1.6,
    letterSpacing: "0.01em",
    color: "#fff",
    height: "90vh",
    width: "90vw",
    display: "flex",
    flexDirection: "column",
    background: "var(--background, #0b1220)",
  }}
    >
      <div style={{ flex: 1, overflowY: "auto", marginBottom: 20, paddingRight: 10 }}>
        {error && <div style={{ color: "red" }}>{error}</div>}
        {messages.map((m, i) => {
          const isUser = m.sender === "user";
          return (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: isUser ? "flex-end" : "flex-start",
                marginBottom: 20,
                textAlign: "left"
              }}
            >
              <div
                style={{
                  maxWidth: "75%",
                  color: "#fff",
                  padding: "14px 16px",
                  fontWeight: "540",
                  borderRadius: 12,
                  border: "none",
                  background: isUser ? "rgba(255,255,255,0.02)" : "transparent",
                  fontSize: 15,
                  lineHeight: 1.65,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {m.sender === "bot" ? (
                  m.text ? (
                    <div
                      className="bot-markdown"
                      style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
                      dangerouslySetInnerHTML={{ __html: md.render(m.text) }}
                    />
                  ) : null
                ) : <div>{m.text}</div>}

                {/* streaming updates, toggle & expanded resources */}
                {m.sender === "bot" && !m.done && m.latestUpdate && (
                  <div style={{ marginTop: 10, fontSize: 13, opacity: 0.75, fontStyle: "italic" }}>
                    {String(m.latestUpdate)}
                  </div>
                )}
                {m.sender === "bot" && m.done && Array.isArray(m.resources) && m.resources.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <button
                      onClick={() => setMessages((prev) =>
                        prev.map((msg, idx) => idx === i ? { ...msg, showResources: !msg.showResources } : msg)
                      )}
                      style={{ padding: "6px 10px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#fff", border: "none", cursor: "pointer", fontSize: 13 }}
                    >
                      {m.showResources ? "Hide resources" : `Show ${m.resources.length} resource${m.resources.length>1?"s":""}`}
                    </button>
                  </div>
                )}
                {m.sender === "bot" && m.showResources && Array.isArray(m.resources) && m.resources.length>0 && (
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                    {m.resources.map((r) => {
                      const headline = r.headline || parseHeadlineFromUrl(r.url);
                      const thumbnail = r.thumbnail || (Array.isArray(r.images)?getBestImage(r.images):null);
                      return (
                        <a key={r.id} href={r.url||"#"} target="_blank" rel="noopener noreferrer" style={{ display: "flex", alignItems:"center", gap:10, textDecoration:"none", color:"inherit", background:"rgba(255,255,255,0.02)", padding:"8px", borderRadius:8 }}>
                          {thumbnail && <img src={thumbnail} alt={headline||"thumb"} style={{ width:84,height:56,objectFit:"cover",borderRadius:6 }}/>}
                          <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
                            <span style={{ fontSize:14, fontWeight:600 }}>{headline}</span>
                            {r.url && <span style={{ fontSize:12,color:"rgba(255,255,255,0.65)"}}>{r.url.replace(/^https?:\/\//,"")}</span>}
                          </div>
                        </a>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* INPUT BAR WITH TICKER SUGGESTIONS */}
      <form
        onSubmit={(e) => { e.preventDefault(); if(!input.trim()) return; sendQuery(input); setInput(""); }}
        style={{
        display: "flex",
        gap: 8,
        position: "relative",
        width: "100%",
        maxWidth: "90%",
        alignSelf: "center",
    }}
      >
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Ask me about stocks... (Use '#' to bring up ticker reccomendation based on your input, always include ticker symbols of the companies you want to talk about.)"
          style={{ flex:1, padding:"10px 12px", borderRadius:6, background:"transparent", color:"#fff", fontSize:15, border:"none", outline:"none" }}
        />
        <button type="submit" style={{ padding:"10px 14px", borderRadius:8, border:"1px #39ff14", cursor:"pointer", fontWeight:600, fontSize:15 }}>Send</button>

        {showTickerSuggestions && filteredTickers.length>0 && (
          <div style={{
            position:"absolute",
            bottom:"50px",
            left:0,
            background:"#1a2b1a",
            borderRadius:6,
            maxHeight:220,
            overflowY:"auto",
            width:"100%",
            zIndex:10,
            padding:4,
            color: "#22c55e"
          }}>
            {filteredTickers.map((t)=>(
              <div key={t.ticker} onClick={()=>selectTicker(t.ticker)} style={{ padding:"6px 10px", cursor:"pointer", borderBottom:"1px solid rgba(255,255,255,0.05)" }}>
                {t.ticker} — {t.title}
              </div>
            ))}
          </div>
        )}
      </form>
    </div>
  );
}
