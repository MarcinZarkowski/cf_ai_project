import { useState, useEffect } from "react";
import Chat from "./Chat";

function App() {
  const [tickers, setTickers] = useState([]);

  useEffect(() => {
    const fetchTickers = async () => {
      try {
        const resp = await fetch(`${import.meta.env.VITE_BACK_URL}/ticker-list`);
        const data = await resp.json();

        setTickers(Object.values(data));
      } catch (err) {
        console.error("Failed to fetch SEC tickers:", err);
      }
    };

    fetchTickers();
  }, []);

  return <Chat tickers={tickers} />;
}

export default App;
